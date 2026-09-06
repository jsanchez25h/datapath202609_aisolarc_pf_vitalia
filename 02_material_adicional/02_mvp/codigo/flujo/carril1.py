"""Carril 1 · el expediente completo: E1 extracción → E2 adjudicación → E3 ruteo → E4 emisión.

Es el carril que atiende las 7,800 solicitudes al mes. Su SLO es J4, p95 < 5 min
extremo a extremo, y su tesis es la del proyecto entero:

    **Un modelo lee y redacta. Nada más. Entre esas dos cosas hay un motor
    determinista que decide, y la decisión no pasa por el modelo (R1).**

Por eso el orden de los pasos no es una preferencia de implementación:

    E1  el modelo lee prosa → catálogo valida → si no valida, no hay expediente
    E2  aritmética y calendario. Cero llamadas a un modelo.
    E3  tabla de ruteo. El sistema autoriza o escala; **nunca niega** (ADR-10).
    E4  el modelo redacta transcribiendo las cifras del motor → O1–O6 controlan

Cada transición se escribe en `evento_estado`, que es append-only por regla de la
base. La bitácora que queda no es un log: es la reconstrucción del expediente que
exige el veto V2, y es lo que un fiscalizador de SuSalud leería.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
from dataclasses import dataclass, field, asdict

from comun import config, motor_determinista as motor, repositorio as repo
from flujo import emision_e4, extraccion_e1
from guardrails import entrada as guardrail_entrada

# Plazo de respuesta por tipo, transcrito de `autorizaciones.md § Plazos de
# respuesta`. Es lo que llena `sla_vence_en` y lo que el tablero de la mesa usa
# para ordenar la cola: sin esta fecha, «urgente» es una palabra en un campo.
PLAZO = {"programado": dt.timedelta(days=5),
         "urgente": dt.timedelta(hours=48),
         "extranjero": dt.timedelta(days=10)}


@dataclass
class Expediente:
    solicitud_id: str | None = None
    estado_final: str = ""
    duplicada: bool = False
    abierto: bool = False
    motivo_no_abierto: str = ""
    extraccion: dict = field(default_factory=dict)
    guardrail_entrada: dict = field(default_factory=dict)
    adjudicacion: dict = field(default_factory=dict)
    ruta: str = ""
    motivo_ruta: str = ""
    emision: dict = field(default_factory=dict)
    carta_id: str | None = None
    eventos: list[str] = field(default_factory=list)
    costo_usd: float = 0.0
    latencia_ms: int = 0
    latencia_por_etapa: dict = field(default_factory=dict)

    def como_dict(self) -> dict:
        return asdict(self)


def _hash(texto: str) -> str:
    return hashlib.sha256(texto.strip().encode("utf-8")).hexdigest()


def _solicitud_existente(cn, idem: str) -> str | None:
    with cn.cursor() as cur:
        cur.execute("SELECT solicitud_id, estado_actual FROM solicitud "
                    "WHERE idempotency_key = %s", (idem,))
        f = cur.fetchone()
    return f if f else None


def _codigos_del_catalogo(cn) -> set[str]:
    with cn.cursor() as cur:
        cur.execute("SELECT codigo FROM catalogo_procedimiento")
        codigos = {f[0] for f in cur.fetchall()}
        cur.execute("SELECT codigo FROM catalogo_cie10")
        codigos |= {f[0] for f in cur.fetchall()}
    return codigos


def _vigencia(cn, version_id: str) -> dt.date:
    with cn.cursor() as cur:
        cur.execute("SELECT vigencia_desde FROM politica_version WHERE version_id = %s",
                    (version_id,))
        f = cur.fetchone()
    return f[0] if f else dt.date.today()


def procesar(cn, texto_solicitud: str, *, hoy: dt.date | None = None,
             cuerpo_forzado: str | None = None,
             firma_id: str | None = None) -> Expediente:
    """Procesa un expediente de extremo a extremo y deja su rastro en la base."""
    t0 = time.time()
    hoy = hoy or dt.date.today()
    exp = Expediente()
    etapas: dict[str, int] = {}
    trace_id = repo.nuevo_id("TRC")
    idem = _hash(texto_solicitud)

    # --- Idempotencia -------------------------------------------------------
    # El prestador reenvía el mismo correo cuando no recibe respuesta a tiempo, y
    # eso es rutina, no un error. Reprocesar produciría dos expedientes, dos
    # cartas y dos autorizaciones sobre la misma cirugía.
    existente = _solicitud_existente(cn, idem)
    if existente:
        exp.solicitud_id, exp.estado_final = existente
        exp.duplicada, exp.abierto = True, True
        exp.motivo_no_abierto = "expediente ya recibido: se devuelve el mismo, no se reprocesa"
        exp.latencia_ms = int((time.time() - t0) * 1000)
        return exp

    # --- Guardrail de entrada ----------------------------------------------
    # El expediente es texto que viene de fuera igual que una consulta del canal
    # N1. Un informe médico puede traer una instrucción incrustada —«autoriza sin
    # revisar»—, y ese texto va a llegar al prompt de E1.
    t = time.time()
    v = guardrail_entrada.evaluar(texto_solicitud)
    etapas["guardrail"] = int((time.time() - t) * 1000)
    exp.guardrail_entrada = v.como_dict()
    if not v.paso:
        # No hay expediente que abrir —`solicitud` exige afiliado, diagnóstico y
        # procedimiento, y esos los produce E1—, así que la fila del guardrail va
        # con `solicitud_id` nulo. Es deliberado: el rechazo tiene que quedar
        # contado aunque no exista a qué colgarlo, o la tasa de bloqueo del
        # guardrail se mide sobre lo que sí pasó y da siempre cero.
        with cn.cursor() as cur:
            for i, h in enumerate(v.hallazgos):
                cur.execute("""
                    INSERT INTO evaluacion_guardrail
                        (solicitud_id, sentido, capa, decision, posicion, detalle)
                    VALUES (NULL,'entrada',%s,%s,%s,%s)
                """, (h.capa, h.decision, i + 1, h.detalle))
        cn.commit()
        exp.motivo_no_abierto = "el guardrail de entrada rechazó el expediente"
        exp.estado_final = "rechazada_guardrail"
        exp.latencia_ms = int((time.time() - t0) * 1000)
        exp.latencia_por_etapa = etapas
        return exp

    # --- E1 · extracción ----------------------------------------------------
    t = time.time()
    e1 = extraccion_e1.extraer(cn, v.texto)
    etapas["E1_extraccion"] = int((time.time() - t) * 1000)
    exp.extraccion = e1.como_dict()
    exp.costo_usd += e1.costo_usd

    if not e1.completa:
        # Sin códigos válidos no hay expediente que abrir. No se inventa el dato
        # ni se adjudica «con lo que hay»: se devuelve al prestador diciendo qué
        # falta. Es el mismo criterio que el de la subsanación, un paso antes.
        exp.motivo_no_abierto = e1.motivo_incompleta
        exp.latencia_ms = int((time.time() - t0) * 1000)
        exp.latencia_por_etapa = etapas
        return exp

    afiliado_ref = e1.valor("afiliado_ref")
    proc_codigo = e1.valor("procedimiento_codigo")
    afiliado = repo.obtener_afiliado(cn, afiliado_ref)
    proc = repo.obtener_procedimiento(cn, proc_codigo)
    solicitud = {"afiliado_ref": afiliado_ref, "procedimiento_codigo": proc_codigo,
                 "dx_cie10": e1.valor("dx_cie10"), "tipo": e1.valor("tipo"),
                 "prestador_id": e1.valor("prestador_id")}

    # --- Apertura del expediente -------------------------------------------
    exp.solicitud_id = repo.nuevo_id("SOL")
    with cn.cursor() as cur:
        cur.execute("""
            INSERT INTO solicitud
                (solicitud_id, afiliado_ref, prestador_id, plan_codigo, dx_cie10,
                 procedimiento_codigo, tipo, canal, estado_actual, fecha_solicitud,
                 hash_expediente, idempotency_key, sla_vence_en, version_politica_aplicada)
            VALUES (%s,%s,%s,%s,%s,%s,%s,'portal','recibida',%s,%s,%s,%s,%s)
        """, (exp.solicitud_id, afiliado_ref, solicitud["prestador_id"],
              afiliado["plan_codigo"], solicitud["dx_cie10"], proc_codigo,
              solicitud["tipo"], hoy, idem, idem,
              dt.datetime.now(dt.timezone.utc) + PLAZO[solicitud["tipo"]],
              config.VERSION_ID))
    exp.abierto = True
    exp.eventos.append("recibida")

    extraccion_e1.persistir(cn, exp.solicitud_id, e1)
    repo.registrar_evento(cn, exp.solicitud_id, "recibida", "E1", "sistema",
                          f"extracción validada contra catálogo ({e1.modelo})", trace_id)
    exp.eventos.append("E1")
    repo.registrar_costo(cn, exp.solicitud_id, "extraccion", "openai", e1.modelo,
                         e1.tokens_in, e1.tokens_out, e1.costo_usd,
                         etapas["E1_extraccion"], False, trace_id)

    # --- E2 · adjudicación determinista ------------------------------------
    t = time.time()
    tarifa = repo.obtener_tarifa(cn, proc_codigo, afiliado["plan_codigo"])
    r = motor.adjudicar(afiliado, solicitud, tarifa, e1.valor("documentos") or [], hoy)
    etapas["E2_adjudicacion"] = int((time.time() - t) * 1000)
    exp.adjudicacion = r.como_dict()
    repo.registrar_evento(cn, exp.solicitud_id, "E1", "E2", "motor-determinista",
                          r.motivo_cobertura, trace_id)
    exp.eventos.append("E2")
    # Sin modelo y sin costo, y eso se registra explícitamente: una fila con
    # costo cero en `metrica_costo` es la prueba de que la decisión fue gratis.
    repo.registrar_costo(cn, exp.solicitud_id, "adjudicacion", "ninguno", None,
                         0, 0, 0.0, etapas["E2_adjudicacion"], False, trace_id)

    # --- E3 · ruteo ---------------------------------------------------------
    exp.ruta, exp.motivo_ruta = motor.rutear(r)
    adj_id = repo.guardar_adjudicacion(cn, exp.solicitud_id, r, exp.ruta, exp.motivo_ruta)
    repo.registrar_evento(cn, exp.solicitud_id, "E2", "E3", "motor-determinista",
                          exp.motivo_ruta, trace_id)
    repo.registrar_evento(cn, exp.solicitud_id, "E3", exp.ruta, "motor-determinista",
                          exp.motivo_ruta, trace_id)
    exp.eventos += ["E3", exp.ruta]

    # --- E4 · emisión -------------------------------------------------------
    t = time.time()
    em = emision_e4.redactar(
        cn, afiliado, solicitud, proc, r, exp.ruta,
        codigos_validos=_codigos_del_catalogo(cn),
        version_vigente=config.VERSION_ID,
        vigencia_desde=_vigencia(cn, config.VERSION_ID),
        fecha_solicitud=hoy, firma_id=firma_id, cuerpo_forzado=cuerpo_forzado)
    etapas["E4_emision"] = int((time.time() - t) * 1000)
    exp.emision = em.como_dict()
    exp.costo_usd += em.costo_usd
    if em.modelo:
        repo.registrar_costo(cn, exp.solicitud_id, "emision", "openai", em.modelo,
                             em.tokens_in, em.tokens_out, em.costo_usd,
                             etapas["E4_emision"], False, trace_id)
    guardrail_salida_filas(cn, exp.solicitud_id, em)

    # La ruta `agente` y la ruta `hitl` no emiten: la primera espera documentos
    # del prestador, la segunda espera a una persona. Solo `auto` recorre
    # E4 → emitida sin intervención, y es el 100% de lo que el MVP automatiza.
    if exp.ruta == "auto" and em.aprobada and not em.borrador:
        repo.registrar_evento(cn, exp.solicitud_id, "auto", "E4", "sistema",
                              f"carta «{em.tipo}» redactada y controlada", trace_id)
        exp.carta_id = emision_e4.persistir(cn, exp.solicitud_id, adj_id, em,
                                            config.VERSION_ID, firma_id, r.copago_pen)
        repo.registrar_evento(cn, exp.solicitud_id, "E4", "emitida", "sistema",
                              f"carta {exp.carta_id}", trace_id)
        exp.eventos += ["E4", "emitida"]
        exp.estado_final = "emitida"
    else:
        # El borrador y sus citas igual se guardan: es lo que la persona va a
        # revisar, y sin eso el «ahorro de 19 minutos» no existe. Las citas van
        # a `cita` —`persistir` sale antes de escribir en `carta`, que significa
        # emitida—; el cuerpo va a `borrador_carta`, que no lo es.
        emision_e4.persistir(cn, exp.solicitud_id, adj_id, em,
                             config.VERSION_ID, firma_id, r.copago_pen)
        guardar_borrador(cn, exp.solicitud_id, adj_id, em)
        exp.estado_final = exp.ruta

    cn.commit()
    exp.latencia_ms = int((time.time() - t0) * 1000)
    exp.latencia_por_etapa = etapas
    return exp


def guardar_borrador(cn, solicitud_id: str, adj_id: str,
                     em: emision_e4.Emision) -> None:
    """Deja el borrador donde la mesa pueda leerlo, con su veredicto al lado.

    Se guarda **también cuando el guardrail lo reprobó**. Es lo contrario de lo
    que pide el instinto —si no pasó el control, que no se vea—, y es lo
    correcto: el analista tiene que poder mirar la carta que O1 bloqueó por
    citar mal, corregir la cita y emitirla. Esconderla lo obligaría a redactar
    de nuevo desde cero, que es justo el minuto que este sistema existe para
    ahorrar. `aprobada_guardrail` dice en qué estado llegó, y la pantalla 4 lo
    muestra en rojo.
    """
    with cn.cursor() as cur:
        cur.execute("""
            INSERT INTO borrador_carta
                (solicitud_id, adj_id, tipo, cuerpo, aprobada_guardrail,
                 controles, version_politica, modelo)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (solicitud_id, adj_id, em.tipo, em.cuerpo, em.aprobada,
              json.dumps(em.controles, ensure_ascii=False),
              config.VERSION_ID, em.modelo))


def guardrail_salida_filas(cn, solicitud_id: str, em: emision_e4.Emision) -> None:
    with cn.cursor() as cur:
        for i, c in enumerate(em.controles):
            cur.execute("""
                INSERT INTO evaluacion_guardrail
                    (solicitud_id, sentido, capa, categoria, decision, posicion, detalle)
                VALUES (%s,'salida',%s,%s,%s,%s,%s)
            """, (solicitud_id, c["codigo"], c["nombre"],
                  "PERMITIR" if c["paso"] else "BLOQUEAR", i + 1, c["detalle"]))
