"""Router de modelos y atribución de costo — sesiones 01 y 02 del curso.

La sesión 01 dice que la selección de modelo es una decisión de arquitectura y no
un ajuste; la 02, que sin atribución de costo por tarea el FinOps es un deseo.
Aquí van las dos juntas: cada tarea declara qué necesita, el router elige, y toda
llamada devuelve su costo para que `metrica_costo` se llene sola.

El criterio de ruteo, en el orden en que manda:

1. **Latencia.** La consulta anticipada N1 tiene J1 p95 < 2 s y compite con un
   analista que responde por teléfono. Ahí manda el proveedor más rápido.
2. **Consecuencia del error.** La carta es el artefacto que el afiliado puede
   llevar a SuSalud. Ahí manda el modelo más capaz, y el ahorro no discute.
3. **Volumen.** La extracción corre 7,800 veces al mes. Ahí manda el precio.

Ningún ruteo toca el copago ni la carencia: eso es R1 y no pasa por un modelo.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from comun import config

# USD por 1M de tokens. Es la tabla que convierte tokens en el S/0.86 por
# solicitud del caso de negocio; si envejece, el número de negocio envejece.
PRECIOS = {
    "gpt-4o":                   (2.50, 10.00),
    "gpt-4o-mini":              (0.15,  0.60),
    "gpt-4.1-mini":             (0.40,  1.60),
    "openai/gpt-oss-20b":       (0.10,  0.50),
    "openai/gpt-oss-120b":      (0.15,  0.75),
    "text-embedding-3-large":   (0.13,  0.00),
}


@dataclass(frozen=True)
class Ruta:
    tarea: str
    proveedor: str
    modelo: str
    razon: str
    temperatura: float = 0.0
    max_tokens: int = 1024


CATALOGO = {
    # Carril 0 · el afiliado o el prestador espera en línea.
    "n1_consulta": Ruta("n1_consulta", "groq", "openai/gpt-oss-20b",
                        "J1 exige p95 < 2 s: manda la latencia, no la capacidad",
                        # 1400 y no 700: con 700, la consulta de la artroscopia
                        # —que cita dos cláusulas largas— agotó el presupuesto y
                        # devolvió texto vacío, porque este modelo razona dentro
                        # del mismo `max_tokens`. Ahorrar tokens de salida al
                        # precio de perder la respuesta entera no es ahorrar.
                        temperatura=0.0, max_tokens=1400),
    # E1 · alto volumen, salida estructurada, verificable contra catálogo.
    "e1_extraccion": Ruta("e1_extraccion", "openai", "gpt-4o-mini",
                          "7,800 corridas al mes con salida validada contra catálogo: manda el precio",
                          temperatura=0.0, max_tokens=800),
    # E4 · el artefacto que el afiliado puede llevar a SuSalud.
    "e4_redaccion": Ruta("e4_redaccion", "openai", "gpt-4o",
                         "la carta es el artefacto reclamable: manda la consecuencia del error",
                         temperatura=0.2, max_tokens=900),
    # El único agente del flujo.
    "agente_subsanacion": Ruta("agente_subsanacion", "openai", "gpt-4o-mini",
                               "conversación acotada con herramientas y tope de turnos",
                               temperatura=0.3, max_tokens=600),
}

# Escalamiento: una negación se redacta con el modelo mayor aunque la tarea de
# origen fuera barata. Es el veto V1 (asimetría del error) hecho ruteo.
TIPOS_QUE_ESCALAN = {"niega_administrativa", "niega_necesidad_medica", "autoriza_parcial"}


def elegir(tarea: str, *, tipo_carta: str | None = None) -> Ruta:
    ruta = CATALOGO[tarea]
    if tarea == "e4_redaccion" or tipo_carta not in TIPOS_QUE_ESCALAN:
        return ruta
    return Ruta(ruta.tarea, "openai", "gpt-4o",
                f"escalado: la carta es «{tipo_carta}» y una negación no se redacta con el modelo barato",
                ruta.temperatura, ruta.max_tokens)


def costo_usd(modelo: str, tokens_in: int, tokens_out: int) -> float:
    entrada, salida = PRECIOS.get(modelo, (0.0, 0.0))
    return round(tokens_in / 1e6 * entrada + tokens_out / 1e6 * salida, 8)


@dataclass
class Respuesta:
    texto: str
    modelo: str
    proveedor: str
    tokens_in: int
    tokens_out: int
    costo_usd: float
    latencia_ms: int
    razon_ruteo: str
    finish_reason: str = ""
    truncada: bool = False


def completar(ruta: Ruta, sistema: str, usuario: str,
              formato_json: bool = False) -> Respuesta:
    """Una sola puerta para todas las llamadas de generación del MVP.

    Que sea una sola es lo que hace que la atribución de costo sea completa: no
    hay una llamada suelta en otro archivo que se escape de `metrica_costo`.

    `formato_json` obliga al proveedor a devolver un objeto JSON. Es para E1,
    que necesita campos y no prosa; se pide aquí y no con un `json.loads` a la
    salida porque un parseo optimista convierte un preámbulo cortés del modelo
    en un expediente vacío.
    """
    t0 = time.time()
    mensajes = [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]

    if ruta.proveedor == "groq":
        from groq import Groq
        cliente = Groq(api_key=config.var("GROQ_API_KEY"))
    else:
        cliente = config.cliente_openai()

    extra = {"response_format": {"type": "json_object"}} if formato_json else {}
    r = cliente.chat.completions.create(
        model=ruta.modelo, messages=mensajes,
        temperature=ruta.temperatura, max_tokens=ruta.max_tokens, **extra)

    ms = int((time.time() - t0) * 1000)
    uso = r.usage
    t_in, t_out = uso.prompt_tokens, uso.completion_tokens
    eleccion = r.choices[0]
    texto = (eleccion.message.content or "").strip()

    # Los modelos de la familia gpt-oss razonan antes de contestar y ese
    # razonamiento gasta el mismo presupuesto que la respuesta. Si `max_tokens`
    # se agota, `content` llega **vacío** y la llamada parece exitosa: usage
    # reporta cientos de tokens de salida y el texto es «». Se marca aquí, en la
    # única puerta de generación, para que ningún llamador confunda una
    # respuesta truncada con una respuesta corta.
    truncada = eleccion.finish_reason == "length" or not texto
    return Respuesta(
        texto=texto,
        modelo=ruta.modelo, proveedor=ruta.proveedor,
        tokens_in=t_in, tokens_out=t_out,
        costo_usd=costo_usd(ruta.modelo, t_in, t_out),
        latencia_ms=ms, razon_ruteo=ruta.razon,
        finish_reason=eleccion.finish_reason or "", truncada=truncada)
