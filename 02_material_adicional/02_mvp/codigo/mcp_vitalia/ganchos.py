"""Cadena de ganchos · lo transversal, enganchado sin tocar el núcleo (sesión 08).

Un gancho es una función que corre en un punto fijo del flujo. La skill no sabe
que existen: el servidor ejecuta `PRE.correr(ctx)`, llama a la skill, ejecuta
`POST.correr(ctx)`. Es el middleware de siempre, y aquí sirve para algo muy
concreto: **el MCP expone este sistema a un cliente que no es nuestro código.**

Esa frase decide el diseño entero de esta capa. Dentro del monolito, N1 ya
verifica sus citas antes de cachearlas y el Carril 1 ya corre O1–O6 antes de
emitir. En la frontera MCP se vuelven a correr, y no por olvido: **un gancho que
confía en la skill no es un control.** El día que alguien registre una skill
nueva —o una versión nueva de una existente— el control de frontera es lo único
que no depende de que ese alguien se acordara.

Dos diferencias deliberadas respecto del patrón del temario:

1. **La cadena de entrada corta; la de salida no del todo.** Si un pre-gancho
   aborta, los siguientes no corren: no se paga un control sobre una llamada que
   ya no va a ocurrir. Pero un post-gancho marcado `siempre` corre aunque otro
   haya abortado, y hay exactamente uno así: el que anota el costo. Una llamada
   que gastó y fue bloqueada **gastó igual**, y dejarla fuera de `metrica_costo`
   repetiría el defecto 2 de `E12` en un sitio nuevo: el panel volvería a
   reportar de menos, ahora por el lado del error.

2. **El aborto de salida no borra la evidencia.** Cuando O1 u O5 reprueban, la
   respuesta que va al cliente MCP se sustituye, pero el veredicto completo
   queda en `ctx.anotaciones`. Quien audite tiene que poder ver qué se bloqueó,
   no solo que se bloqueó (veto V2).
"""

from __future__ import annotations

import datetime as dt
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

from comun import config, recuperacion, repositorio as repo
from guardrails import entrada as guardrail_entrada, salida as guardrail_salida

from mcp_vitalia.registro import Skill

# El presupuesto se mide en caracteres y no en tokens a propósito: contar tokens
# exige cargar el tokenizador del proveedor, y este gancho corre **antes** de que
# se haya decidido proveedor. Un tope de 6.000 caracteres son ~1.500 tokens de
# español, holgado para una consulta de prestador y estrecho para un intento de
# meter un documento entero por el canal de consultas.
TOPE_CARACTERES = 6000

# Anillo de trazas de la sesión MCP. La traza *persistente* ya existe y no se
# duplica aquí: es `metrica_costo` para lo que cuesta y `evento_estado` para lo
# que cambia de estado. Esto es solo la ventana de la sesión, que el servidor
# expone como recurso MCP para poder mirarla desde el cliente.
TRAZAS: deque[dict] = deque(maxlen=200)


@dataclass
class Contexto:
    """El objeto mutable que comparten todos los ganchos de una llamada."""
    skill: Skill
    argumentos: dict
    cn: Any = None
    solo_lectura: bool = False
    texto_entrada: str = ""
    salida: dict | None = None
    abortado: bool = False
    motivo_aborto: str = ""
    anotaciones: dict = field(default_factory=dict)
    t0: float = field(default_factory=time.time)

    @property
    def ms(self) -> int:
        return int((time.time() - self.t0) * 1000)

    def abortar(self, motivo: str, respuesta: dict) -> None:
        self.abortado = True
        self.motivo_aborto = motivo
        self.salida = respuesta


@dataclass(frozen=True)
class Gancho:
    codigo: str
    nombre: str
    fn: Callable[[Contexto], None]
    siempre: bool = False        # corre aunque la cadena ya esté abortada


@dataclass
class Cadena:
    nombre: str
    ganchos: list[Gancho]

    def correr(self, ctx: Contexto) -> Contexto:
        for g in self.ganchos:
            if ctx.abortado and not g.siempre:
                continue
            t = time.time()
            g.fn(ctx)
            ctx.anotaciones.setdefault("ganchos", []).append(
                {"cadena": self.nombre, "codigo": g.codigo, "nombre": g.nombre,
                 "ms": int((time.time() - t) * 1000),
                 "abortado_aqui": ctx.abortado and ctx.motivo_aborto.startswith(g.codigo)})
        return ctx


# --------------------------------------------------------------------------
# Pre-ganchos · en orden de costo creciente, igual que las ocho capas
# --------------------------------------------------------------------------

def _g1_ambito(ctx: Contexto) -> None:
    """El más barato: una comparación de banderas, sin tocar nada.

    Existe porque el mismo servidor se arranca de dos maneras. En la defensa se
    arranca en solo lectura y el cliente MCP puede mirar el expediente entero
    sin poder escribir una línea en él; en la mesa se arranca completo. La
    diferencia no debería estar repartida por dentro de cada skill.
    """
    if ctx.solo_lectura and ctx.skill.escribe:
        ctx.abortar(
            "G1 · el servidor está en modo solo lectura",
            {"ok": False, "error": "solo_lectura",
             "detalle": f"la skill «{ctx.skill.nombre}» escribe y este servidor "
                        f"se arrancó en modo solo lectura"})


def _g2_presupuesto(ctx: Contexto) -> None:
    """Tope de contexto. Aborta antes de que el texto llegue al guardrail.

    El orden importa: correr las ocho capas sobre 200.000 caracteres para luego
    descubrir que no caben es pagar el control más caro del sistema por una
    llamada que nunca iba a ocurrir.
    """
    if not ctx.skill.campo_texto_libre:
        return
    n = len(ctx.texto_entrada)
    ctx.anotaciones["caracteres_entrada"] = n
    if n > TOPE_CARACTERES:
        ctx.abortar(
            f"G2 · entrada de {n} caracteres sobre un tope de {TOPE_CARACTERES}",
            {"ok": False, "error": "presupuesto_excedido",
             "detalle": f"la consulta tiene {n} caracteres y el tope del canal es "
                        f"{TOPE_CARACTERES}. Una solicitud completa no entra por "
                        f"aquí: se registra por el canal de la mesa."})


def _g3_guardrail_entrada(ctx: Contexto) -> None:
    """Las ocho capas del diseño, sobre el argumento de texto libre.

    Solo corre si la skill declara uno. Las skills que reciben únicamente
    identificadores del catálogo —`SOL-…`, `AF-…`, `PRC-…`— no lo necesitan: lo
    que valida un identificador es el catálogo, y hacerle pasar ocho capas de
    detección de inyección a la cadena «PRC-4712» es gasto sin hallazgo posible.
    """
    campo = ctx.skill.campo_texto_libre
    if not campo:
        return
    v = guardrail_entrada.evaluar(ctx.texto_entrada)
    ctx.anotaciones["guardrail_entrada"] = v.como_dict()
    if not v.paso:
        ctx.abortar(
            f"G3 · guardrail de entrada: {v.decision}",
            {"ok": False, "error": "bloqueada_por_guardrail",
             "detalle": "No puedo atender esa consulta por este canal.",
             "capas": [h.capa for h in v.hallazgos
                       if h.decision == guardrail_entrada.BLOQUEAR]})
        return
    # El texto que sigue es el **transformado**: si la capa 5 enmascaró un DNI o
    # la 6 quitó una URL, lo que ve la skill es el texto limpio y no el original.
    ctx.texto_entrada = v.texto
    ctx.argumentos[campo] = v.texto


# --------------------------------------------------------------------------
# Post-ganchos
# --------------------------------------------------------------------------

def _g4_guardrail_salida(ctx: Contexto) -> None:
    """O1 y O2 en la frontera, sobre lo que la skill dice que son sus citas.

    Es redundante con lo que N1 ya hizo, y la redundancia es el punto. O1 aquí
    no revisa el trabajo del modelo —eso ya pasó— sino el de la skill: comprueba
    que lo que sale por el canal MCP sigue siendo verificable contra el corpus
    después de haber pasado por caché, por versiones y por una capa de código
    que este gancho no controla.

    O2 es el que de verdad puede saltar. La clave del caché lleva delante
    `config.VERSION_ID`, así que un acierto no puede venir de una versión
    retirada; pero eso lo garantiza el **cliente** del caché, no el caché, y el
    día que el alias `politica_actual` se mueva sin que la configuración cambie,
    este es el control que lo ve.
    """
    if not ctx.skill.cita_politica or not ctx.salida:
        return
    citas = ctx.salida.get("citas") or []
    if not citas:
        return
    # El fragmento se busca aquí, no se acepta el que traiga la respuesta. Si el
    # control se verificara contra el contexto que la propia skill adjunta, una
    # skill que devolviera cita y fragmento coherentes entre sí pero ajenos al
    # corpus pasaría O1 sin despeinarse: el control estaría comprobando que la
    # respuesta es consistente consigo misma.
    fragmentos = {}
    for c in citas:
        fr = recuperacion.fragmento_por_chunk(c["chunk_id"])
        if fr is not None:
            fragmentos[c["chunk_id"]] = fr
    hoy = dt.date.today()
    c1 = guardrail_salida.o1_citas_literales(
        [{"chunk_id": c["chunk_id"], "texto": c["texto"]} for c in citas],
        fragmentos, ctx.salida.get("citas_rechazadas") or [])
    c2 = guardrail_salida.o2_version_vigente(
        citas, config.VERSION_ID, hoy, ctx.anotaciones.get("vigencia_desde", hoy))
    ctx.anotaciones["guardrail_salida"] = [c.__dict__ for c in (c1, c2)]
    if not (c1.paso and c2.paso):
        ctx.abortar(
            f"G4 · guardrail de salida: {'O1' if not c1.paso else 'O2'}",
            {"ok": False, "error": "salida_no_verificable",
             "detalle": "La respuesta no pudo verificarse contra la política "
                        "vigente y no se entrega. Consulte a la mesa de "
                        "preautorización.",
             "controles": [{"codigo": c.codigo, "paso": c.paso, "detalle": c.detalle}
                           for c in (c1, c2)]})


def _g5_pii_salida(ctx: Contexto) -> None:
    """O5 sobre el texto que sale.

    El destino es `traza_mcp` y nunca `carta_titular`: al otro lado de este
    canal hay un agente, no el titular, y el nombre del afiliado en una carta
    dirigida a él es correcto mientras que el mismo nombre en la respuesta a una
    herramienta es una fuga. La única skill que devuelve nombres propios —el
    estado del expediente— los devuelve enmascarados por esto.
    """
    if not ctx.salida or not ctx.salida.get("ok", True):
        return
    # Lo que la skill **sabe** que es un dato personal se retira por igualdad de
    # cadena, antes de preguntarle a nadie. Medido: el reconocedor de entidades
    # detecta «Rosa Milagros Quispe Ayala» con puntaje 0.85 dentro de «La
    # paciente Rosa Milagros Quispe Ayala solicita una cirugía», y **no lo
    # detecta en absoluto** en «Expediente SOL-2a722746d2d4 de Rosa Milagros
    # Quispe Ayala (AF-100234), Colecistectomía laparoscópica». El nombre es el
    # mismo; lo que cambia es que la segunda no es una frase sino una línea de
    # campos, y el modelo de lenguaje necesita sintaxis para reconocer un nombre.
    # La respuesta de una herramienta es siempre una línea de campos.
    #
    # El nombre no hay que adivinarlo: viene de `core_afiliado`, la skill lo tiene
    # delante. Un detector estadístico es la red que recoge lo que no se sabía de
    # antemano; usarlo para lo que sí se sabe es cambiar una certeza por una
    # probabilidad.
    conocidos = [c for c in (ctx.salida.get("_pii") or []) if isinstance(c, str) and c.strip()]
    for campo in ("texto", "mensaje"):
        valor = ctx.salida.get(campo)
        if not isinstance(valor, str) or not valor:
            continue
        enmascarado = False
        for dato in conocidos:
            if dato in valor:
                valor = valor.replace(dato, "<PERSON>")
                enmascarado = True
        control, limpio = guardrail_salida.o5_sin_pii(valor, "traza_mcp")
        if control.accion == "enmascarado" or enmascarado:
            ctx.salida[campo] = limpio
            ctx.anotaciones.setdefault("pii_enmascarada", []).append(
                {"campo": campo,
                 "por_catalogo": enmascarado,
                 "por_deteccion": control.accion == "enmascarado"})


def _g6_traza_y_costo(ctx: Contexto) -> None:
    """Corre **siempre**, incluso sobre una llamada abortada. Es el único así.

    Una llamada que el guardrail bloqueó después de haber pagado tokens gastó
    igual, y el panel que compara el costo real contra el S/ 0.86 del caso de
    negocio no puede enterarse solo de las que salieron bien.

    La fila de costo la escribe este gancho **únicamente si nadie aguas abajo la
    escribió ya**. El gancho no puede saberlo por sí mismo; la skill sí, y lo
    declara con `_costo_anotado_aguas_abajo`. Duplicar la fila no sería un
    detalle contable: el panel divide el costo entre el número de solicitudes,
    así que una fila repetida infla justo el número que se compara contra el
    caso de negocio.
    """
    s = ctx.salida or {}
    costo = s.get("_costo") or {}
    traza = {"skill": ctx.skill.ref, "ms": ctx.ms, "ok": bool(s.get("ok", False)),
             "abortado": ctx.abortado, "motivo": ctx.motivo_aborto,
             "nivel": s.get("nivel", "N0"),
             "costo_usd": costo.get("costo_usd", 0.0),
             "ts": dt.datetime.now().isoformat(timespec="seconds")}
    TRAZAS.append(traza)
    ctx.anotaciones["traza"] = traza

    if ctx.cn is None or not costo or s.get("_costo_anotado_aguas_abajo"):
        return
    repo.registrar_costo(
        ctx.cn, costo.get("solicitud_id"), f"mcp_{ctx.skill.nombre}",
        costo.get("proveedor", "mcp"), costo.get("modelo"),
        costo.get("tokens_in", 0), costo.get("tokens_out", 0),
        costo.get("costo_usd", 0.0), ctx.ms, bool(costo.get("cache_hit", False)))
    ctx.cn.commit()


PRE = Cadena("pre", [
    Gancho("G1", "ámbito de escritura", _g1_ambito),
    Gancho("G2", "presupuesto de contexto", _g2_presupuesto),
    Gancho("G3", "guardrail de entrada · 8 capas", _g3_guardrail_entrada),
])

POST = Cadena("post", [
    Gancho("G4", "guardrail de salida · O1 y O2", _g4_guardrail_salida),
    Gancho("G5", "sin PII fuera de destino · O5", _g5_pii_salida),
    Gancho("G6", "traza y costo", _g6_traza_y_costo, siempre=True),
])
