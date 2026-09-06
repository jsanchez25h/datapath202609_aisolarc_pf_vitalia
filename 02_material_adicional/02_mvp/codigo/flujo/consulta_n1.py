"""Carril 0 · N1, la consulta anticipada.

Es el carril que el diseño puso primero porque atiende el 41% de las llamadas
sin abrir expediente: el prestador pregunta antes de mandar, y si pregunta bien,
manda bien. Su SLO es J1, p95 < 2 s.

    guardrail de entrada (8 capas)
      -> caché semántico            si acierta, termina aquí y no cuesta un token
      -> recuperación híbrida       densa + BM25 sobre el alias politica_actual
      -> generación con citas       Groq, temperatura 0, prohibido responder sin cita
      -> O1 verificación literal    la cita se comprueba carácter por carácter
      -> caché

Lo que N1 **no** hace es adjudicar. Puede decir «la carencia de maternidad es de
300 días»; no puede decir «su cesárea está aprobada». Eso es Carril 1.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict

from comun import cache_semantico, recuperacion, repositorio as repo, router_modelos
from guardrails import entrada as guardrail_entrada

SISTEMA = """Eres el asistente de consultas de Vitalia Salud EPS y respondes a
prestadores y afiliados sobre las condiciones del plan.

Reglas que no puedes romper:

1. Responde **solo** con lo que digan los fragmentos de política que se te
   entregan. Si no alcanzan, di exactamente: «No tengo la cláusula que responde
   eso; la mesa de preautorización puede confirmarlo.»
2. Toda afirmación sobre la política va acompañada de una cita **textual** entre
   comillas, copiada carácter por carácter del fragmento. No parafrasees dentro
   de las comillas. Si necesitas omitir texto intermedio usa «…», y no juntes
   dentro de unas mismas comillas fragmentos de cláusulas distintas.
3. Ninguna respuesta puede quedarse sin comillas. Aunque el dato esté clarísimo
   en el fragmento y la respuesta quepa en una línea, copia la frase de donde lo
   sacaste. Si no hay ninguna frase que puedas copiar, no contestes de memoria:
   usa la frase de la regla 1.
4. Cierra con una línea `FUENTES:` y los identificadores de los fragmentos que
   usaste, separados por comas.
5. No calcules copagos, deducibles ni fechas. Si te lo piden, indica que el
   cálculo lo hace la mesa con los datos del afiliado.
6. Español peruano, tono claro, sin jerga. Máximo seis oraciones antes de FUENTES.
"""

PLANTILLA = """Fragmentos de la política vigente ({version}):

{contexto}

---
Consulta: {consulta}"""

SIN_CLAUSULA = ("No tengo la cláusula que responde eso; la mesa de preautorización "
                "puede confirmarlo.")


@dataclass
class RespuestaN1:
    texto: str
    origen: str                       # cache | modelo | bloqueada
    citas_verificadas: list[dict] = field(default_factory=list)
    citas_rechazadas: list[str] = field(default_factory=list)
    fragmentos: list[dict] = field(default_factory=list)
    guardrail: dict = field(default_factory=dict)
    modelo: str = ""
    costo_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    latencia_ms: int = 0
    latencia_cache_ms: int = 0
    latencia_recuperacion_ms: int = 0
    latencia_generacion_ms: int = 0
    latencia_guardrail_ms: int = 0
    similitud_cache: float | None = None
    clave_cache: str = ""
    truncada: bool = False
    sin_cita: bool = False
    finish_reason: str = ""

    def como_dict(self) -> dict:
        return asdict(self)


def _anotar(cn, span: str, proveedor: str, r: RespuestaN1, cache_hit: bool) -> None:
    """Escribe el gasto del Carril 0 en `metrica_costo`.

    Durante buena parte del MVP este carril no escribió nada, y el efecto se vio
    en la pantalla 5: el panel del supervisor mostraba «aciertos de caché —» y un
    costo por solicitud que solo contaba los expedientes. El caso dice que el
    41% del volumen entra por aquí, así que el carril más barato era además el
    invisible, y el ahorro del caché —el número que justifica la sesión 02— vivía
    en el JSON de una prueba y no en la base que lee el panel. Un ahorro que
    nadie puede consultar no está medido.

    `solicitud_id` va en NULL porque N1 responde **sin abrir expediente**: esa
    columna es anulable en el esquema justamente para esto, y la fila en NULL es
    la que dice que hubo una consulta que no llegó a ser una solicitud.

    Los tres desenlaces no comparten span. La consulta que el guardrail bloqueó
    se anota como `n1_bloqueada` y no como `n1`, porque el hit-rate del panel
    cuenta las lecturas del span `n1` y una consulta bloqueada nunca llegó a
    preguntarle al caché: meterla en el denominador rebajaría el indicador con
    filas que no pudieron acertar. Es el mismo argumento que ya excluía a la
    extracción.
    """
    if cn is None:
        return
    repo.registrar_costo(cn, None, span, proveedor, r.modelo or None,
                         r.tokens_in, r.tokens_out, r.costo_usd,
                         r.latencia_ms, cache_hit)
    cn.commit()


def responder(consulta: str, plan: str | None = None,
              usar_cache: bool = True, cn=None) -> RespuestaN1:
    t0 = time.time()

    v = guardrail_entrada.evaluar(consulta)
    ms_guardrail = int((time.time() - t0) * 1000)
    if not v.paso:
        bloqueada = RespuestaN1(
            texto="No puedo atender esa consulta por este canal. "
                  "Si necesita ayuda con una solicitud, comuníquese con la mesa de "
                  "preautorización.",
            origen="bloqueada", guardrail=v.como_dict(),
            latencia_guardrail_ms=ms_guardrail,
            latencia_ms=int((time.time() - t0) * 1000))
        _anotar(cn, "n1_bloqueada", "guardrail", bloqueada, False)
        return bloqueada
    consulta_limpia = v.texto

    vector = None
    if usar_cache:
        acierto, ms_cache, vector = cache_semantico.buscar(consulta_limpia, plan)
        if acierto:
            desde_cache = RespuestaN1(
                texto=acierto.respuesta, origen="cache", guardrail=v.como_dict(),
                # Una respuesta servida desde el caché llega con las mismas
                # citas verificadas que tenía cuando se generó. La clave del
                # caché empieza por `config.VERSION_ID`, así que un acierto solo
                # puede venir de la versión vigente: publicar una versión nueva
                # cambia la clave y ninguna entrada vieja resulta alcanzable.
                # Esa es la razón por la que estas citas siguen cumpliendo O2
                # sin volver a comprobarse, y por la que la clave lleva la
                # versión delante y no como un campo más del payload.
                citas_verificadas=list(acierto.citas or []),
                similitud_cache=acierto.similitud, clave_cache=acierto.clave,
                latencia_cache_ms=ms_cache, latencia_guardrail_ms=ms_guardrail,
                latencia_ms=int((time.time() - t0) * 1000))
            _anotar(cn, "n1", "qdrant", desde_cache, True)
            return desde_cache
    else:
        ms_cache = 0

    # El vector de la consulta ya está calculado por la consulta al caché: se le
    # pasa a la recuperación para no pagar dos veces el mismo embedding.
    t_rec = time.time()
    fragmentos = recuperacion.buscar_hibrido(consulta_limpia, plan=plan, vector=vector)
    ms_recuperacion = int((time.time() - t_rec) * 1000)
    contexto = "\n\n".join(
        f"[{f.chunk_id}] {f.jerarquia}\n{f.texto_literal}" for f in fragmentos)

    ruta = router_modelos.elegir("n1_consulta")
    t_gen = time.time()
    r = router_modelos.completar(
        ruta, SISTEMA,
        PLANTILLA.format(version=fragmentos[0].version_id if fragmentos else "—",
                         contexto=contexto, consulta=consulta_limpia))
    ms_generacion = int((time.time() - t_gen) * 1000)

    # Una respuesta truncada no es una respuesta corta: es una respuesta que no
    # existe. Devolverla vacía dejaría al prestador delante de una pantalla en
    # blanco creyendo que la mesa no tiene la cláusula. Se declara el fallo con
    # la misma frase de la regla 1 y no se cachea.
    if r.truncada:
        cortada = RespuestaN1(
            texto=SIN_CLAUSULA, origen="modelo",
            fragmentos=[f.como_dict() for f in fragmentos],
            guardrail=v.como_dict(), modelo=r.modelo, costo_usd=r.costo_usd,
            tokens_in=r.tokens_in, tokens_out=r.tokens_out,
            truncada=True, finish_reason=r.finish_reason,
            latencia_cache_ms=ms_cache, latencia_recuperacion_ms=ms_recuperacion,
            latencia_generacion_ms=ms_generacion, latencia_guardrail_ms=ms_guardrail,
            latencia_ms=int((time.time() - t0) * 1000))
        _anotar(cn, "n1", ruta.proveedor, cortada, False)
        return cortada

    # Control O1 sobre cada cita: la que no exista literalmente se retira del
    # texto. No se reintenta con otro prompt — eso es maquillar el defecto.
    verificadas, rechazadas = [], []
    texto = r.texto
    for cita in recuperacion.citas_de(r.texto):
        origen = next((f for f in fragmentos
                       if recuperacion.verificar_cita_literal(cita, f)), None)
        if origen:
            verificadas.append({"texto": cita, "chunk_id": origen.chunk_id,
                                "articulo": origen.articulo, "jerarquia": origen.jerarquia,
                                "version_id": origen.version_id})
        else:
            rechazadas.append(cita)
            texto = texto.replace(cita, "[cita no verificada, retirada]")

    # R2 en el borde del Carril 0: una afirmacion sobre la politica sin cita
    # textual no es una respuesta, aunque sea cierta. O1 solo puede rechazar las
    # citas que existen; si el modelo no entrecomilla nada, no hay nada que
    # rechazar y el control aprueba por vacio. Es el mismo agujero que en la
    # emision se cerro con `exige_al_menos_una=True`, y aqui estaba abierto.
    #
    # Se midio: la respuesta correcta «300 dias calendario» venia sin comillas
    # las 6 de 6 veces con un juego de fragmentos y con comillas con otro que
    # solo cambiaba en el quinto —un fragmento que la respuesta ni usa—. Es
    # decir, el cumplimiento de la regla 2 dependia de algo ajeno a la pregunta.
    # Reforzar la regla en el prompt subio el cumplimiento de 5/7 a 6/7; el
    # septimo caso es el que este control atrapa. Una regla que el prompt pide
    # y nadie comprueba es una regla que se cumple casi siempre, y R2 no admite
    # «casi»: se declara la falta de clausula, que es lo que de verdad hubo.
    sin_cita = not verificadas and texto.strip() != SIN_CLAUSULA
    if sin_cita:
        texto = SIN_CLAUSULA

    respuesta = RespuestaN1(
        texto=texto, origen="modelo", citas_verificadas=verificadas,
        sin_cita=sin_cita,
        citas_rechazadas=rechazadas,
        fragmentos=[f.como_dict() for f in fragmentos],
        guardrail=v.como_dict(), modelo=r.modelo, costo_usd=r.costo_usd,
        tokens_in=r.tokens_in, tokens_out=r.tokens_out,
        latencia_cache_ms=ms_cache, latencia_recuperacion_ms=ms_recuperacion,
        latencia_generacion_ms=ms_generacion, latencia_guardrail_ms=ms_guardrail,
        clave_cache=cache_semantico._clave(plan, consulta_limpia),
        latencia_ms=int((time.time() - t0) * 1000))

    # Solo se cachea una respuesta cuyas citas pasaron O1.
    if usar_cache and not rechazadas and verificadas:
        cache_semantico.guardar(consulta_limpia, texto, plan, vector=vector,
                                citas=verificadas)

    _anotar(cn, "n1", ruta.proveedor, respuesta, False)
    return respuesta
