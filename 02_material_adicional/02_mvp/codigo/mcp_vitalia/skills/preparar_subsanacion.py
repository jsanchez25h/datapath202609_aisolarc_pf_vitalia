"""Skill 4 · `preparar_subsanacion` — el único agente del diseño.

Todo el resto del flujo es determinista o es un paso de un flujo fijo. Aquí, y
solo aquí, hay un modelo decidiendo cómo decir algo. Conviene ser exacto sobre
qué decide:

    la lista de documentos que faltan   → la escribe el motor determinista
    la cláusula que la sustenta         → la resuelve el corpus, por clave exacta
    la redacción del mensaje            → la escribe el modelo

Y hay un control que cierra el círculo: después de generar, la skill comprueba
que **el modelo no cambió la lista**. Cada documento faltante tiene que aparecer
literalmente con su nombre de catálogo, y ninguno de los que ya están adjuntos
puede aparecer. Si el texto no pasa esa comprobación no se corrige el prompt ni
se reintenta: se descarta y se arma el mensaje por plantilla, sin modelo.

Esa es la diferencia entre un agente y un generador suelto. El agente puede
elegir las palabras; no puede elegir los hechos. Pedirle a un prestador un
documento que no hacía falta cuesta días de trámite, y decirle que ya está todo
cuando falta algo produce una autorización que después se cae — la asimetría del
error del veto V1, en el carril más barato del sistema.

**No emite nada.** Prepara el texto y lo devuelve; enviarlo es del canal, y
autorizar es de la mesa.
"""

from __future__ import annotations

import datetime as dt
import json

from pydantic import BaseModel, Field

from api import consultas
from comun import motor_determinista as motor, recuperacion, repositorio as repo, router_modelos
from mcp_vitalia import resiliencia
from mcp_vitalia.registro import Skill

SISTEMA = """Eres el asistente de subsanación de la mesa de preautorización de
Vitalia Salud EPS. Escribes al prestador que envió una solicitud a la que le
falta sustento clínico, para pedirle exactamente lo que falta.

Reglas que no puedes romper:

1. Pide **solo** los documentos de la lista que se te entrega, y nómbralos
   copiando su descripción **palabra por palabra**, cada uno en su propia línea
   empezando por «- ». No agregues documentos, no quites ninguno y no cambies su
   redacción, ni siquiera para acortarla.
2. Incluye una vez, entre comillas angulares « », el texto de la cláusula que se
   te entrega, copiado carácter por carácter. No la parafrasees.
3. No digas si la solicitud será aprobada o rechazada. No la niegues. No
   menciones copagos, montos ni plazos que no estén en este mensaje.
4. Español peruano, tono cordial y directo, tratamiento de usted. Máximo diez
   líneas en total.
5. Cierra indicando que al recibir lo pedido la solicitud continúa su
   evaluación en la mesa."""

PLANTILLA = """Expediente: {solicitud_id}
Procedimiento: {procedimiento} ({codigo})

Documentos que faltan (cópialos tal cual):
{faltantes}

Cláusula que lo sustenta ({jerarquia}):
{clausula}"""


class Argumentos(BaseModel):
    solicitud_id: str = Field(
        description="Identificador del expediente al que le falta sustento, "
                    "con el formato SOL-cd8878b820aa.")


DESCRIPCION = """Prepara el mensaje de subsanación para un expediente al que le
faltan documentos: lista exactamente qué falta, citando la cláusula que lo
exige.

Úsala solo sobre expedientes que estén en ruta `agente` — los que el motor
enrutó por falta de sustento clínico. Sobre cualquier otro devuelve un error en
vez de inventar un motivo.

Devuelve el texto preparado. No lo envía, no cambia el estado del expediente, no
autoriza y no niega."""


def _texto_por_plantilla(faltantes: list[str], clausula: str, jerarquia: str) -> str:
    """El mensaje sin modelo. Es el respaldo N5 y también el patrón de contraste.

    Se construye con las mismas descripciones de catálogo y con el cuerpo
    literal de la cláusula, así que cumple R2 por construcción: no hay forma de
    que la cita no coincida, porque no la escribió nadie.
    """
    lineas = "\n".join(f"- {motor.NOMBRE_DOCUMENTO.get(d, d)}" for d in faltantes)
    return ("Estimado prestador:\n\n"
            "Para continuar con la evaluación de la solicitud necesitamos que "
            "adjunte lo siguiente:\n\n"
            f"{lineas}\n\n"
            f"Este requisito se sustenta en {jerarquia}: «{clausula}»\n\n"
            "Al recibir estos documentos la solicitud continúa su evaluación en "
            "la mesa de preautorización.")


def _lista_de_documentos(valor) -> list[str]:
    """Lo que la base devuelve como texto, convertido a la lista que era."""
    if valor is None:
        return []
    if isinstance(valor, list):
        return [str(x) for x in valor]
    if isinstance(valor, str):
        try:
            cargado = json.loads(valor)
        except (ValueError, TypeError):
            return [valor]
        return [str(x) for x in cargado] if isinstance(cargado, list) else [str(cargado)]
    return []


def _fuera_de_cita(texto: str) -> str:
    """El mensaje sin lo que es cita textual de la norma.

    Hace falta porque la cláusula que el mensaje está obligado a copiar **nombra
    todos los documentos del protocolo**: dice que la solicitud debe incluir la
    orden médica, el informe médico, el código y el diagnóstico. Un control que
    busque nombres de documentos en el mensaje entero encuentra ahí los que no se
    están pidiendo y da por alterada una lista que está intacta.

    Es un error de lectura del control, no del modelo: confunde la norma con la
    petición. Y era invisible desde fuera, porque el respaldo N5 producía un
    mensaje correcto por plantilla — el sistema respondía bien y pagaba una
    llamada al modelo que tiraba a la basura en cada subsanación.
    """
    limpio = texto
    for cita in recuperacion.citas_de(texto):
        limpio = limpio.replace(cita, " ")
    return limpio


def _lista_intacta(texto: str, faltantes: list[str], exigidos: list[str]) -> tuple[bool, str]:
    """El modelo pudo elegir las palabras; no pudo elegir los hechos.

    La comprobación es literal y no semántica, por la misma razón que las citas:
    «informe médico» y «informe médico que sustenta la indicación» se parecen lo
    bastante como para que un juicio por similitud los dé por iguales, y son
    documentos distintos en la ventanilla del prestador.

    Se mira **lo que el mensaje pide**, no lo que cita: el texto entrecomillado
    se retira antes de contar (ver `_fuera_de_cita`).
    """
    pedido = _fuera_de_cita(texto)
    faltan_en_texto = [d for d in faltantes
                       if motor.NOMBRE_DOCUMENTO.get(d, d) not in pedido]
    sobran = [d for d in exigidos
              if d not in faltantes and motor.NOMBRE_DOCUMENTO.get(d, d) in pedido]
    if faltan_en_texto:
        return False, ("el mensaje no nombra: "
                       + ", ".join(faltan_en_texto))
    if sobran:
        return False, ("el mensaje pide documentos que ya estaban adjuntos: "
                       + ", ".join(sobran))
    return True, "la lista del mensaje coincide con la del motor"


def _cita_verificada(texto: str, fragmento) -> bool:
    """Al menos un tramo entrecomillado del mensaje tiene que existir en la cláusula."""
    return any(recuperacion.verificar_cita_literal(c, fragmento)
               for c in recuperacion.citas_de(texto))


def _ejecutar(solicitud_id: str, *, cn=None) -> dict:
    if cn is None:
        return {"ok": False, "error": "sin_conexion",
                "detalle": "la skill necesita conexión a la base"}

    exp = consultas.expediente(cn, solicitud_id)
    if exp is None:
        return {"ok": False, "error": "expediente_inexistente",
                "detalle": f"no hay expediente «{solicitud_id}»"}

    # Los documentos presentes se leen de la extracción E1 y la lista de
    # faltantes se **recalcula** con el motor, en vez de parsearse del
    # `motivo_ruta` que guardó el Carril 1. Ese motivo es una frase en prosa
    # pensada para que la lea un analista; convertirla otra vez en datos es
    # exactamente la clase de acoplamiento que hace que un cambio de redacción
    # rompa un cálculo.
    # `extraccion.valor` es TEXT: la lista de documentos vuelve de la base como
    # el JSON con el que se guardó, no como lista. Tratarla como cadena suelta no
    # da error —da una lista de faltantes con **todo** dentro, porque ninguno de
    # los códigos coincide—, y el mensaje resultante le pide al prestador los tres
    # documentos que ya mandó. Un defecto de frontera, no de lógica: el motor
    # calculaba bien sobre un insumo que llegó mal.
    presentes = _lista_de_documentos(
        next((e["valor"] for e in exp.get("extraccion") or []
              if e["campo"] == "documentos"), None))

    # Dónde está el expediente, no solo qué le falta. Un expediente emitido puede
    # seguir teniendo documentos ausentes en su extracción —la mesa completó el
    # sustento por fuera y la extracción guarda lo que llegó, no lo que se
    # resolvió después—, y prepararle una subsanación sería pedirle papeles a un
    # prestador cuya solicitud ya está autorizada.
    estado = exp["estado_actual"]
    if estado != "agente":
        return {"ok": False, "error": "no_procede",
                "detalle": f"el expediente {solicitud_id} está en estado «{estado}» "
                           f"y la subsanación solo aplica a los que el motor enrutó "
                           f"al agente por falta de sustento clínico"}

    afiliado = repo.obtener_afiliado(cn, exp["afiliado_ref"])
    tarifa = repo.obtener_tarifa(cn, exp["procedimiento_codigo"], afiliado["plan_codigo"])
    r = motor.adjudicar(afiliado, {"procedimiento_codigo": exp["procedimiento_codigo"]},
                        tarifa, list(presentes), dt.date.today())

    if not r.documentos_faltantes:
        # Negarse a actuar es la respuesta correcta. Un agente que produce un
        # mensaje de subsanación para un expediente completo le pide al
        # prestador algo que ya mandó.
        return {"ok": False, "error": "no_procede",
                "detalle": f"al expediente {solicitud_id} no le falta ningún "
                           f"documento del protocolo: no hay nada que subsanar"}

    fragmentos = recuperacion.fragmentos_de([motor.FUNDAMENTO["documentos"]])
    if not fragmentos:
        return {"ok": False, "error": "fundamento_sin_clausula",
                "detalle": "el fundamento documental del motor no resuelve a "
                           "ninguna cláusula del corpus vigente"}
    fr = fragmentos[0]
    clausula = recuperacion.cuerpo_citable(fr)
    exigidos = motor.DOCUMENTOS_EXIGIDOS.get(exp["procedimiento_codigo"], [])

    def con_modelo():
        ruta = router_modelos.elegir("agente_subsanacion")
        usuario = PLANTILLA.format(
            solicitud_id=solicitud_id, procedimiento=exp["procedimiento_desc"],
            codigo=exp["procedimiento_codigo"],
            faltantes="\n".join(f"- {motor.NOMBRE_DOCUMENTO.get(d, d)}"
                                for d in r.documentos_faltantes),
            jerarquia=fr.jerarquia, clausula=clausula)
        resp = router_modelos.completar(ruta, SISTEMA, usuario)
        if resp.truncada:
            raise RuntimeError("respuesta truncada del modelo de subsanación")
        ok_lista, detalle = _lista_intacta(resp.texto, r.documentos_faltantes, exigidos)
        if not ok_lista:
            raise RuntimeError(f"el modelo alteró la lista determinista: {detalle}")
        if not _cita_verificada(resp.texto, fr):
            raise RuntimeError("el modelo no reprodujo la cláusula literalmente")
        return resp, detalle

    def sin_modelo():
        return None, "mensaje armado por plantilla, sin modelo"

    res = resiliencia.cadena_de_respaldo([
        resiliencia.Eslabon("N0", "redacción con modelo, verificada contra el motor",
                            con_modelo, resiliencia.DISYUNTORES["openai"]),
        resiliencia.Eslabon("N5", "sin modelo: mensaje por plantilla", sin_modelo),
    ])
    resp, detalle = res.valor

    texto = (resp.texto if resp is not None
             else _texto_por_plantilla(r.documentos_faltantes, clausula, fr.jerarquia))

    citas = [{"chunk_id": fr.chunk_id, "articulo": fr.articulo,
              "jerarquia": fr.jerarquia, "version_id": fr.version_id,
              "texto": c}
             for c in recuperacion.citas_de(texto)
             if recuperacion.verificar_cita_literal(c, fr)]

    salida = {
        "ok": True,
        "solicitud_id": solicitud_id,
        "mensaje": texto,
        "documentos_faltantes": [
            {"codigo": d, "descripcion": motor.NOMBRE_DOCUMENTO.get(d, d)}
            for d in r.documentos_faltantes],
        "documentos_presentes": list(presentes),
        "control_lista_determinista": detalle,
        "citas": citas,
        "nivel": res.nivel,
        "degradado": res.degradado,
        "intentos": res.intentos,
        "aviso": "Texto preparado, no enviado. No cambia el estado del "
                 "expediente ni resuelve la solicitud.",
    }
    if resp is not None:
        # Esta fila sí la escribe el gancho G6: el gasto es de esta skill y
        # nadie aguas abajo lo anotó. Va con `solicitud_id` porque es
        # atribuible a un expediente concreto, a diferencia del Carril 0.
        salida["_costo"] = {"solicitud_id": solicitud_id, "proveedor": resp.proveedor,
                            "modelo": resp.modelo, "tokens_in": resp.tokens_in,
                            "tokens_out": resp.tokens_out, "costo_usd": resp.costo_usd,
                            "cache_hit": False}
        salida["_costo_anotado_aguas_abajo"] = False
    return salida


V1_0_0 = Skill(
    nombre="preparar_subsanacion", version="1.0.0",
    descripcion=DESCRIPCION, esquema=Argumentos, ejecutar=_ejecutar,
    campo_texto_libre=None,
    # Escribe: gasta tokens contra la cuenta y deja fila en `metrica_costo`
    # atribuida al expediente. El modo solo lectura del servidor no significa
    # «no cambies datos» sino «no gastes ni cambies», y es el modo con el que se
    # arranca el servidor para la defensa.
    escribe=True, cita_politica=True)
