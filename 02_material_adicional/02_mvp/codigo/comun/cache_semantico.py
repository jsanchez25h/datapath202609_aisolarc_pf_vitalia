"""Caché semántico — sesión 02 del curso (AI FinOps).

Dos preguntas distintas con la misma respuesta no deberían costar dos veces:
«¿cuánto pago por una artroscopia en el plan Esencial?» y «cuál es mi copago si
me operan la rodilla y tengo Vitalia Esencial» son la misma consulta.

Tres decisiones que el diseño obliga y que un caché ingenuo se salta:

1. **La clave incluye la versión de política y el plan.** Sin eso, el caché
   sirve respuestas de política derogada, que es exactamente lo que ADR-21
   prohíbe. Al publicar una versión nueva, `pipeline_politica` borra la
   colección entera antes de mover el alias.
2. **La clave incluye además la cobertura y la intención de la pregunta**, y se
   deducen sin modelo. Esta es la corrección que impuso la medición, y merece
   explicación porque contradice la implementación obvia. Tomando como ancla
   «¿Cuántos días de carencia tiene la cobertura de maternidad?» y midiendo el
   coseno con `text-embedding-3-large`:

       reformulaciones legítimas      0.598 · 0.647 · 0.673 · 0.787
       preguntas de otra cobertura    0.780 (salud mental) · 0.756 (oncológico)
       otra intención, misma cobertura 0.627 (copago) · 0.602 (plan aplicable)
       preguntas ajenas               0.288 · 0.214

   Las dos primeras franjas se solapan por completo: «carencia de salud mental»
   se parece **más** al ancla que tres de sus cuatro reformulaciones válidas.
   No existe un umbral de similitud que admita las legítimas y rechace las
   peligrosas, porque lo que distingue una respuesta de otra —«maternidad» vs
   «salud mental», «carencia» vs «copago»— son justo los tokens que el embedding
   pesa poco. Bajar el umbral para «conseguir aciertos» habría servido la
   carencia de maternidad a quien preguntaba por salud mental: 300 días en vez
   de 90. Eso es el veto V1 exactamente.

   Así que la seguridad la da la clave discriminante, que es determinista, y la
   similitud queda como segundo filtro *dentro* de la clave. Si la consulta no
   se puede clasificar, no se lee ni se escribe caché: fail-close.
3. **Solo cachea el Carril 0.** Ninguna adjudicación se cachea nunca: el copago
   depende del deducible ya consumido, que cambia con cada atención.
"""

from __future__ import annotations

import hashlib
import re
import time
import unicodedata
import uuid
from dataclasses import dataclass

from qdrant_client import models as qm

from comun import config

# Umbral aplicado **dentro** de una clave ya discriminada. El mínimo medido
# entre reformulaciones legítimas fue 0.598; se deja el corte justo por debajo.
# El número no es lo que protege al afiliado —eso lo hace la clave—; lo que
# filtra aquí es que dos preguntas de la misma cobertura e intención sigan
# siendo la misma pregunta.
UMBRAL = 0.55
TTL_SEGUNDOS = 7 * 24 * 3600

INDETERMINADO = "?"


# --------------------------------------------------------------------------
# Discriminante determinista de la clave
# --------------------------------------------------------------------------

COBERTURAS = {
    "maternidad": r"maternidad|parto|cesarea|embarazo|gestaci|obstetric|prenatal|puerperio",
    "salud_mental": r"salud mental|psiquiatr|psicolog|psicoterap",
    "oncologico": r"oncolog|cancer|quimioterap|radioterap|tumor|neoplas",
    "terapia_fisica": r"terapia fisica|fisioterap|rehabilitaci",
    "protesis": r"protesis|implante|osteosintesis",
    "bariatrica": r"bariatric|manga gastrica|bypass gastrico|obesidad morbida",
    "emergencia": r"emergencia|urgencia",
    "reembolso": r"reembolso|reem-?\d\d|devoluci[oó]n de gastos|fuera de red",
    "consulta": r"consulta ambulatoria|consulta externa|consulta medica",
    "examenes": r"examen|laboratorio|imagenolog|tomograf|ecograf(?!ia obstetrica)",
    "hospitalizacion": (r"hospitalizaci|cirug|quirurg|operaci[oó]n|artroscop|"
                        r"colecistectom|histerectom|internamiento|sala de operaciones"),
}

INTENCIONES = {
    "carencia": (r"carencia|periodo de espera|per[ií]odo de espera|tiempo de espera|"
                 r"dias de espera|d[ií]as debo esperar|cuanto tiempo debo esperar|"
                 r"tiempo m[ií]nimo de afiliaci|desde que me afili|antiguedad"),
    "copago": (r"copago|coaseguro|deducible|gasto de bolsillo|tope|cuanto pago|"
               r"cuanto me cuesta|cuanto cuesta|cuanto debo pagar"),
    "documentos": (r"documento|requisito|que necesito|que debo presentar|sustento|"
                   r"adjuntar|exige|exigible|papeles"),
    "plazo": r"plazo|cuanto demora|cuando responden|tiempo de respuesta|en cuanto tiempo",
    "exclusion": r"exclusi|excluye|no cubre|no est[aá] cubierto",
    "significado": r"que significa|que quiere decir|a que se refiere|motivo del rechazo",
    "cobertura": r"cubre|cobertura|est[aá] cubierto|aplica|incluye|tengo derecho",
}

# Orden de especificidad para deshacer empates de **intención**. «¿Cuántos días
# de carencia tiene la cobertura de maternidad?» nombra las dos cosas y empata
# 1-1 entre `carencia` y `cobertura`; es evidentemente una pregunta de carencia.
# `cobertura` va al final porque «cubre» y «cobertura» aparecen en casi toda
# consulta del dominio: es el cajón de sastre, no una señal.
#
# El empate de **cobertura** no se deshace, y la asimetría es deliberada:
# equivocar la intención manda la consulta a otro cajón del caché y a lo sumo
# cuesta un acierto; equivocar la cobertura sirve la carencia de maternidad a
# quien preguntó por salud mental. Ante un empate de cobertura, no hay caché.
ORDEN_INTENCIONES = ["carencia", "copago", "documentos", "plazo",
                     "exclusion", "significado", "cobertura"]


def _plano(texto: str) -> str:
    d = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in d if not unicodedata.combining(c))


def _clasificar(texto: str, lexico: dict[str, str],
                desempate: list[str] | None = None) -> str:
    """Devuelve la etiqueta con más coincidencias, o `?` si no hay ganador.

    Sin `desempate`, un empate se declara indeterminado a propósito: ante la
    duda el caché no responde, y una consulta que no se cachea solo cuesta
    dinero, mientras que una servida desde la clave equivocada cuesta una
    respuesta incorrecta.
    """
    plano = _plano(texto)
    marcador = {etiqueta: len(re.findall(patron, plano))
                for etiqueta, patron in lexico.items()}
    mejor = max(marcador.values())
    if mejor == 0:
        return INDETERMINADO
    ganadores = [e for e, n in marcador.items() if n == mejor]
    if len(ganadores) == 1:
        return ganadores[0]
    if desempate:
        return min(ganadores, key=lambda e: desempate.index(e)
                   if e in desempate else len(desempate))
    return INDETERMINADO


def discriminar(consulta: str) -> tuple[str, str]:
    return (_clasificar(consulta, COBERTURAS),
            _clasificar(consulta, INTENCIONES, ORDEN_INTENCIONES))


def _clave(plan: str | None, consulta: str | None = None) -> str:
    if consulta is None:                       # compatibilidad con `vaciar()`
        return f"{config.VERSION_ID}|{plan or 'todos'}"
    cobertura, intencion = discriminar(consulta)
    return f"{config.VERSION_ID}|{plan or 'todos'}|{cobertura}|{intencion}"


def clasificable(consulta: str) -> bool:
    return INDETERMINADO not in discriminar(consulta)


@dataclass
class Acierto:
    respuesta: str
    similitud: float
    consulta_original: str
    edad_segundos: int
    clave: str = ""
    # Las citas viajan con la respuesta, y no es un adorno. Solo se cachean
    # respuestas cuyas citas pasaron O1 enteras, así que el acierto arrastra un
    # texto ya verificado; si el caché guardara la prosa y tirara los
    # `chunk_id`, el prestador que recibe la respuesta reutilizada no tendría
    # contra qué contrastarla y el mismo contenido valdría menos por haber
    # llegado más barato. La verificación se hizo una vez; se conserva.
    citas: list = None


def _asegurar_coleccion(qc) -> None:
    if not qc.collection_exists(config.COLECCION_CACHE):
        qc.create_collection(
            collection_name=config.COLECCION_CACHE,
            vectors_config=qm.VectorParams(size=config.DIM_EMBEDDING,
                                           distance=qm.Distance.COSINE))
        qc.create_payload_index(collection_name=config.COLECCION_CACHE,
                                field_name="clave", field_schema="keyword")


def vector_de(consulta: str) -> list[float]:
    """El embedding de la consulta. Lo devuelve `buscar` para que la
    recuperación híbrida lo reutilice en vez de pedir el mismo dos veces."""
    from comun import recuperacion
    return recuperacion.vectorizar([consulta])[0]


def buscar(consulta: str, plan: str | None = None
           ) -> tuple[Acierto | None, int, list[float] | None]:
    """Devuelve el acierto (o None), la latencia, y el embedding calculado.

    El embedding se devuelve siempre —haya acierto o no— porque la recuperación
    que viene después necesita exactamente ese vector.
    """
    t0 = time.time()
    if not clasificable(consulta):
        # Sin clave discriminante no hay lectura de caché. Una consulta que no
        # se sabe clasificar es la que más riesgo tiene de recibir la respuesta
        # de otra pregunta.
        return None, int((time.time() - t0) * 1000), None

    vector = vector_de(consulta)
    qc = config.cliente_qdrant()
    _asegurar_coleccion(qc)
    clave = _clave(plan, consulta)
    puntos = qc.query_points(
        collection_name=config.COLECCION_CACHE, query=vector, limit=1,
        query_filter=qm.Filter(must=[qm.FieldCondition(
            key="clave", match=qm.MatchValue(value=clave))]),
        with_payload=True).points
    ms = int((time.time() - t0) * 1000)
    if not puntos or puntos[0].score < UMBRAL:
        return None, ms, vector
    p = puntos[0]
    edad = int(time.time() - p.payload.get("ts", 0))
    if edad > TTL_SEGUNDOS:
        qc.delete(collection_name=config.COLECCION_CACHE,
                  points_selector=qm.PointIdsList(points=[p.id]))
        return None, ms, vector
    return Acierto(p.payload["respuesta"], round(p.score, 4),
                   p.payload["consulta"], edad, clave,
                   p.payload.get("citas") or []), ms, vector


def guardar(consulta: str, respuesta: str, plan: str | None = None,
            vector: list[float] | None = None,
            citas: list | None = None) -> bool:
    """Guarda la respuesta. Devuelve False si la consulta no era clasificable:
    lo que no se puede discriminar tampoco se puede reutilizar con seguridad."""
    if not clasificable(consulta):
        return False
    qc = config.cliente_qdrant()
    _asegurar_coleccion(qc)
    clave = _clave(plan, consulta)
    # El id se deriva de la consulta normalizada: repreguntar lo mismo actualiza
    # la entrada en vez de acumular duplicados.
    semilla = f"{clave}|{consulta.strip().lower()}"
    cobertura, intencion = discriminar(consulta)
    qc.upsert(collection_name=config.COLECCION_CACHE, wait=True, points=[
        qm.PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, semilla)),
            vector=vector if vector is not None else vector_de(consulta),
            payload={"clave": clave, "consulta": consulta, "respuesta": respuesta,
                     "plan": plan, "cobertura": cobertura, "intencion": intencion,
                     "citas": citas or [],
                     "version_id": config.VERSION_ID, "ts": int(time.time()),
                     "sha256": hashlib.sha256(respuesta.encode()).hexdigest()})])
    return True


def vaciar() -> int:
    """Invalidación total. La llama el pipeline de ingesta antes de mover el
    alias, y también sirve para medir el caché desde cero en la evidencia."""
    qc = config.cliente_qdrant()
    if not qc.collection_exists(config.COLECCION_CACHE):
        return 0
    n = qc.count(config.COLECCION_CACHE, exact=True).count
    qc.delete_collection(config.COLECCION_CACHE)
    return n
