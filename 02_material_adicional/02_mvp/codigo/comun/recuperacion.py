"""Recuperación sobre el corpus normativo — sesiones 05 y 06 del curso.

Tres cosas que el diseño exige y que la tarea de la sesión 06 no tenía:

1. **Búsqueda híbrida densa + BM25.** Medido en la tarea: una consulta por código
   exacto (`REEM-06`) puntuaba 0.56 con búsqueda densa sola y 0.74 preguntando lo
   mismo en lenguaje natural. Los códigos de procedimiento *son* identificadores,
   y la búsqueda densa es mala con identificadores.
2. **Expansión de consulta**, que quedó pendiente en la tarea.
3. **Verificación literal de la cita** (control O1 de `06` §4): el texto que la
   respuesta presenta como cita tiene que existir, carácter por carácter, dentro
   del `texto_literal` del fragmento recuperado.

El acceso es siempre por el alias `politica_actual`, nunca por el nombre de una
colección: es lo que hace imposible citar una versión derogada (ADR-21).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, asdict
from functools import lru_cache

from qdrant_client import models as qm
from rank_bm25 import BM25Okapi

from . import config

K_CANDIDATOS = 20      # 20 candidatos …
K_CONTEXTO = 5         # … de los que 5 llegan al contexto (08 §4.2)


@dataclass
class Fragmento:
    chunk_id: str
    doc_id: str
    version_id: str
    jerarquia: str
    articulo: str
    texto_literal: str
    tipo_norma: str
    planes: list[str]
    offset_ini: int = 0
    offset_fin: int = 0
    score: float = 0.0
    origen: list[str] = field(default_factory=list)

    def como_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------
# Índice BM25
# --------------------------------------------------------------------------

def _normalizar(texto: str) -> list[str]:
    plano = unicodedata.normalize("NFKD", texto.lower())
    plano = "".join(c for c in plano if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", plano)


@lru_cache(maxsize=1)
def _corpus_en_memoria() -> tuple[list[dict], BM25Okapi]:
    """El corpus del MVP son 112 fragmentos: cabe en memoria y el índice BM25 se
    arma al arrancar. En producción esto es un vector disperso en Qdrant; se deja
    dicho para no vender como escalable algo que aquí no lo es."""
    qc = config.cliente_qdrant()
    puntos: list[dict] = []
    siguiente = None
    while True:
        lote, siguiente = qc.scroll(collection_name=config.ALIAS, limit=256,
                                    offset=siguiente, with_payload=True, with_vectors=False)
        puntos.extend(p.payload for p in lote)
        if siguiente is None:
            break
    indice = BM25Okapi([_normalizar(p["texto_literal"]) for p in puntos])
    return puntos, indice


def invalidar_cache_corpus() -> None:
    _corpus_en_memoria.cache_clear()
    _puente_de_cobertura.cache_clear()


# --------------------------------------------------------------------------
# Búsquedas
# --------------------------------------------------------------------------

def _filtro(plan: str | None, tipo_norma: str | None) -> qm.Filter | None:
    condiciones = []
    if plan:
        condiciones.append(qm.FieldCondition(key="planes", match=qm.MatchValue(value=plan)))
    if tipo_norma:
        condiciones.append(qm.FieldCondition(key="tipo_norma", match=qm.MatchValue(value=tipo_norma)))
    return qm.Filter(must=condiciones) if condiciones else None


def vectorizar(consultas: list[str]) -> list[list[float]]:
    """Un solo viaje a OpenAI para todas las variantes de la consulta.

    Medido: dos variantes en una llamada cuestan 331 ms; las mismas dos en
    llamadas separadas, 665 ms. La expansión de consulta multiplica las
    variantes, así que embeberlas de a una convierte una mejora de calidad en
    una penalización de latencia contra J1.
    """
    datos = config.cliente_openai().embeddings.create(
        model=config.MODELO_EMBEDDING, input=consultas).data
    return [d.embedding for d in datos]


def buscar_denso(consulta: str, k: int = K_CANDIDATOS, plan: str | None = None,
                 tipo_norma: str | None = None,
                 vector: list[float] | None = None) -> list[Fragmento]:
    """`vector` permite reutilizar un embedding ya calculado —el del caché
    semántico, por ejemplo— en vez de pedir el mismo dos veces."""
    if vector is None:
        vector = vectorizar([consulta])[0]
    qc = config.cliente_qdrant()
    res = qc.query_points(collection_name=config.ALIAS, query=vector, limit=k,
                          query_filter=_filtro(plan, tipo_norma), with_payload=True).points
    return [_a_fragmento(p.payload, p.score, "denso") for p in res]


def buscar_bm25(consulta: str, k: int = K_CANDIDATOS, plan: str | None = None,
                tipo_norma: str | None = None) -> list[Fragmento]:
    puntos, indice = _corpus_en_memoria()
    puntuaciones = indice.get_scores(_normalizar(consulta))
    orden = sorted(range(len(puntos)), key=lambda i: puntuaciones[i], reverse=True)
    salida = []
    for i in orden:
        p = puntos[i]
        if plan and plan not in p.get("planes", []):
            continue
        if tipo_norma and p.get("tipo_norma") != tipo_norma:
            continue
        if puntuaciones[i] <= 0:
            continue
        salida.append(_a_fragmento(p, float(puntuaciones[i]), "bm25"))
        if len(salida) >= k:
            break
    return salida


def buscar_hibrido(consulta: str, k: int = K_CONTEXTO, plan: str | None = None,
                   tipo_norma: str | None = None, expandir: bool = True,
                   kk: int = 10, vector: list[float] | None = None) -> list[Fragmento]:
    """Fusión por rango recíproco (RRF) de densa y BM25.

    RRF y no una suma ponderada de puntajes porque los dos puntajes no están en
    la misma escala: el coseno vive en [0,1] y BM25 no tiene tope.

    `kk = 10` y no el 60 canónico. El 60 se calibró contra listas TREC de mil
    documentos, donde amortiguar la diferencia entre el puesto 1 y el 20 es lo
    correcto; sobre listas de 20 candidatos convierte la fusión en un recuento de
    apariciones: 1/61 y 1/80 se diferencian en un 24 %, así que un fragmento
    presente en seis listas en el puesto 15 le gana a uno presente en cuatro en
    el puesto 2. Medido con «¿cuántos días de carencia exige una colecistectomía
    en el plan Integral?»: con 60, la tabla de carencias —la cláusula que
    responde la pregunta— quedaba séptima, debajo de los tres artículos que
    *explican* qué es una carencia sin decir cuántos días; con 10 sube al segundo
    puesto y las demás consultas del banco no se mueven. RRF premiaba la
    presencia; se le pide que premie la posición.

    `vector` es el embedding de `consulta` si ya se calculó antes (el caché
    semántico lo calcula siempre); las expansiones se embeben en el mismo lote.
    """
    consultas = [consulta] + (expandir_consulta(consulta) if expandir else [])
    ranking: dict[str, float] = {}
    fragmentos: dict[str, Fragmento] = {}
    origenes: dict[str, set[str]] = {}

    if vector is not None:
        vectores = [vector] + (vectorizar(consultas[1:]) if len(consultas) > 1 else [])
    else:
        vectores = vectorizar(consultas)

    for q, vec in zip(consultas, vectores):
        for lista in (buscar_denso(q, K_CANDIDATOS, plan, tipo_norma, vector=vec),
                      buscar_bm25(q, K_CANDIDATOS, plan, tipo_norma)):
            for posicion, fr in enumerate(lista):
                ranking[fr.chunk_id] = ranking.get(fr.chunk_id, 0.0) + 1.0 / (kk + posicion + 1)
                fragmentos.setdefault(fr.chunk_id, fr)
                origenes.setdefault(fr.chunk_id, set()).update(fr.origen)

    mejores = sorted(ranking, key=ranking.get, reverse=True)[:k]
    salida = []
    for chunk_id in mejores:
        fr = fragmentos[chunk_id]
        fr.score = round(ranking[chunk_id], 6)
        fr.origen = sorted(origenes[chunk_id])
        salida.append(fr)
    return salida


# --------------------------------------------------------------------------
# Expansión de consulta — la deuda que dejó la tarea de la sesión 06
# --------------------------------------------------------------------------

SINONIMOS = {
    "copago": ["coaseguro", "deducible", "gasto de bolsillo"],
    "carencia": ["periodo de espera", "tiempo mínimo de afiliación"],
    "cesarea": ["parto", "maternidad"],
    "cesárea": ["parto", "maternidad"],
    "artroscopia": ["rodilla", "lesión meniscal", "terapia física"],
    "colecistectomia": ["vesícula", "colelitiasis", "cirugía general"],
    "colecistectomía": ["vesícula", "colelitiasis", "cirugía general"],
    "reembolso": ["devolución de gastos", "atención fuera de red"],
    "preautorizacion": ["autorización previa", "solicitud programada"],
    "preautorización": ["autorización previa", "solicitud programada"],
    "exclusion": ["no cubierto", "no cubre"],
    "exclusión": ["no cubierto", "no cubre"],
}

# El puente que faltaba entre la pregunta y la póliza. La tabla de carencias
# dice «Hospitalización y cirugía · 60 días» y no nombra ninguna colecistectomía;
# el prestador, en cambio, nunca pregunta por la cobertura, pregunta por el
# procedimiento. Medido: «¿cuántos días de carencia exige una colecistectomía en
# el plan Integral?» recuperaba el protocolo quirúrgico y los tres artículos que
# *explican* qué es una carencia, y no el cuadro que la fija — N1 respondía con la
# frase de la regla 1 teniendo la cláusula a mano. Es el mismo defecto que O1
# atrapa por el otro lado: allí el modelo cita lo que no existe, aquí no cita lo
# que sí existe y nadie le puso delante.
#
# La correspondencia no se inventa aquí: es `COBERTURA_DE`, la misma tabla con la
# que el motor adjudica. Lo único transcrito es cómo nombra la póliza a cada
# cobertura, palabra por palabra, para que la expansión empuje hacia el texto que
# de verdad está en el corpus.
COBERTURA_EN_LA_POLIZA = {
    "emergencia":      "emergencia por accidente emergencia por enfermedad",
    "consulta":        "consulta ambulatoria",
    "examenes":        "exámenes de laboratorio e imágenes",
    "hospitalizacion": "hospitalización y cirugía",
    "terapia_fisica":  "terapia física y rehabilitación",
    "salud_mental":    "salud mental",
    "maternidad":      "maternidad y parto",
    "oncologico":      "tratamiento oncológico",
    "bariatrica":      "cirugía bariátrica",
    "protesis":        "prótesis y órtesis",
}


@lru_cache(maxsize=1)
def _puente_de_cobertura() -> dict[str, str]:
    """De cómo se llama el procedimiento a cómo lo llama la póliza.

    Los nombres se leen del catálogo y no se escriben aquí: un procedimiento
    nuevo entra al catálogo, no al código — «el modelo propone, el catálogo
    dispone» también gobierna la recuperación. Si la base no responde, la
    expansión se queda sin este puente y la búsqueda funciona peor, que es
    preferible a que no funcione.
    """
    from . import motor_determinista as motor
    cn = None
    try:
        cn = config.conexion_pg()
        with cn.cursor() as cur:
            cur.execute("SELECT codigo, descripcion FROM catalogo_procedimiento")
            filas = cur.fetchall()
    except Exception:                                   # noqa: BLE001
        return {}
    finally:
        if cn is not None:
            cn.close()
    puente: dict[str, str] = {}
    for codigo, descripcion in filas:
        frase = COBERTURA_EN_LA_POLIZA.get(motor.COBERTURA_DE.get(codigo, ""))
        if frase:
            # La primera palabra de la descripción es el procedimiento; el resto
            # es la técnica («laparoscópica», «total de rodilla»), que cambia sin
            # cambiar la cobertura que lo gobierna.
            puente[descripcion.split()[0].lower()] = frase
    return puente


CODIGO = re.compile(r"\b[A-Z]{2,5}-?\d{2,4}\b")


def expandir_consulta(consulta: str, maximo: int = 3) -> list[str]:
    """Tres expansiones baratas y deterministas, sin llamar a un modelo:

    - de cobertura, con el catálogo: el procedimiento por el que se pregunta se
      traduce a la cobertura con la que la póliza lo nombra;
    - léxica, con el diccionario del dominio;
    - de identificadores: si la consulta trae un código (`REEM-06`, `AUT-100`),
      se genera una variante con y otra sin el guion, que es exactamente donde
      la búsqueda densa fallaba.

    La de cobertura va primera porque es la única que no depende de que alguien
    haya escrito el sinónimo correcto: sale de la misma tabla con la que se
    adjudica.
    """
    variantes: list[str] = []
    bajo = consulta.lower()
    coberturas = [f for palabra, f in _puente_de_cobertura().items() if palabra in bajo]
    if coberturas:
        variantes.append(f"{consulta} {' '.join(dict.fromkeys(coberturas))}")
    extra = [s for clave, sins in SINONIMOS.items() if clave in bajo for s in sins]
    if extra:
        variantes.append(f"{consulta} {' '.join(dict.fromkeys(extra))}")
    for codigo in CODIGO.findall(consulta.upper()):
        variantes.append(codigo.replace("-", " "))
        variantes.append(codigo.replace("-", ""))
    return list(dict.fromkeys(variantes))[:maximo]


# --------------------------------------------------------------------------
# Verificación literal de la cita — control O1
# --------------------------------------------------------------------------

# Tipografía que hay que neutralizar antes de comparar. No es cosmética: se
# midió contra el modelo. De las dos citas que O1 rechazó en la primera corrida,
# ninguna era una alucinación —una traía `CIE‑10` con guion U+2011 donde el
# corpus tiene el guion ASCII, y la otra había perdido los `**` con que el
# corpus marca la negrita—. Un control de citas que no normaliza esto produce
# falsos positivos, y un falso positivo en O1 convierte una respuesta correcta
# en «[cita no verificada, retirada]»: destruye la respuesta sin ganar nada.
# Lo que sigue sin tolerarse es la paráfrasis, que es lo que O1 vino a atrapar.

_GUIONES = dict.fromkeys(
    [0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2015, 0x2212, 0x00AD, 0x2043], "-")
_COMILLAS = {**dict.fromkeys([0x201C, 0x201D, 0x201E, 0x00AB, 0x00BB], '"'),
             **dict.fromkeys([0x2018, 0x2019, 0x201A, 0x2032], "'")}
_MARCAS_MD = re.compile(r"\*{1,3}|_{2,3}|`+")

# Puntos suspensivos con los que una cita señala que omite texto intermedio.
ELIPSIS = re.compile(r"\s*(?:…|\.{3,})\s*")

# Las comillas de una cita, **emparejadas**: la que abre y la que cierra tienen
# que ser del mismo tipo, y ninguna otra comilla puede quedar dentro del tramo.
#
# La versión anterior era `[«"“]([^»"”]{15,})[»"”]`, una clase de apertura y otra
# de cierre sin relación entre sí, y eso fabricó una cita fantasma en una carta
# del MVP. El cuerpo decía: `…en estado "suspendido". Según nuestra política,
# «vencido el periodo de gracia…»`. La comilla recta que cierra `"suspendido"`
# se emparejó con el `»` que cerraba la cita verdadera —`«` no estaba excluida
# de la clase interior, así que el tramo capturado se la tragó entera— y salió
# un texto que no está en ningún fragmento. O1 lo reportó como no verificable, e
# hizo bien: ese texto no existe. El defecto no estaba en el control sino aquí,
# y el costo lo pagó una carta correcta que se bloqueó.
#
# Es la misma familia del defecto 4 de la tarea de la sesión 02 —un control
# correcto reprobando contenido correcto por un error de quien le pasa el
# insumo—, y por eso ahora vive en un solo sitio: los dos carriles que citan
# política llamaban a su propia copia de la expresión, así que arreglarla en uno
# habría dejado el otro roto.
_CITAS = re.compile(r"«([^«»]{15,})»|“([^“”«»]{15,})”|\"([^\"«»“”]{15,})\"")


def citas_de(texto: str) -> list[str]:
    """Los tramos entrecomillados de un texto, en orden de aparición."""
    return [a or b or c for a, b, c in _CITAS.findall(texto)]


def cuerpo_citable(fragmento) -> str:
    """El fragmento sin su línea de jerarquía: lo único que es norma citable."""
    texto = fragmento.texto_literal
    titulo = (fragmento.jerarquia or "").strip()
    if titulo and texto.lstrip().startswith(titulo):
        return texto.lstrip()[len(titulo):]
    return texto


def _compactar(texto: str) -> str:
    plano = unicodedata.normalize("NFKD", texto.lower())
    plano = "".join(c for c in plano if not unicodedata.combining(c))
    plano = plano.translate(_GUIONES).translate(_COMILLAS)
    plano = _MARCAS_MD.sub("", plano)
    return re.sub(r"\s+", " ", plano).strip()


def verificar_cita_literal(cita: str, fragmento: Fragmento) -> bool:
    """La cita tiene que existir dentro del `texto_literal`, tolerando solo
    espacios, tildes, mayúsculas, variantes tipográficas del guion y de la
    comilla, y las marcas de negrita del corpus. La paráfrasis sigue fallando.

    Una cita con puntos suspensivos omite texto intermedio, que es una forma
    legítima de citar. Se verifica por tramos: cada tramo tiene que existir
    literalmente y **en orden** dentro del mismo fragmento. Así una elisión
    honesta pasa y un empalme de dos cláusulas distintas —o de dos documentos—
    no, porque el segundo tramo no aparecería después del primero.

    **La ruta de títulos no cuenta como cita.** La ingesta antepone la jerarquía
    al `texto_literal` para que el fragmento se explique solo, y eso abrió un
    hueco por el que se coló una carta real del MVP: el modelo entrecomilló
    «Carencias y preexistencias > Periodos de carencia > Tabla de carencias por
    cobertura» y O1 la aprobó, porque esa cadena efectivamente estaba dentro del
    fragmento. Es la cita más fácil de producir —está en la primera línea de
    todos— y no sustenta nada: un título dice dónde buscar la norma, no qué dice.
    R2 pide lo segundo, así que la verificación corre contra el cuerpo.
    """
    if not cita or not cita.strip():
        return False
    fuente = _compactar(cuerpo_citable(fragmento))
    desde = 0
    for tramo in ELIPSIS.split(cita):
        tramo = _compactar(tramo)
        if len(tramo) < 10:          # un tramo demasiado corto no prueba nada
            continue
        posicion = fuente.find(tramo, desde)
        if posicion == -1:
            return False
        desde = posicion + len(tramo)
    return desde > 0


def fragmentos_de(fundamentos: list[tuple[str, str]]) -> list[Fragmento]:
    """Resuelve los fundamentos que declaró el motor a los fragmentos exactos.

    **No es una búsqueda.** El motor determinista ya sabe qué cláusula sustenta
    cada conclusión suya; pedirle a un buscador semántico que la encuentre otra
    vez introduce la posibilidad de traer una parecida, y una cláusula parecida
    en una carta de preautorización es una cita falsa. Aquí la correspondencia
    es exacta por `doc_id` + `articulo` sobre el corpus vigente.

    Un fundamento que no resuelve devuelve menos fragmentos de los pedidos, y el
    llamador debe tratarlo como un defecto —no como un resultado vacío—: es una
    conclusión que la carta no podría sustentar.
    """
    puntos, _ = _corpus_en_memoria()
    indice: dict[tuple[str, str], dict] = {}
    for p in puntos:
        indice.setdefault((p["doc_id"], p.get("articulo", "")), p)
    salida = []
    for clave in dict.fromkeys(fundamentos):
        p = indice.get(tuple(clave))
        if p is not None:
            salida.append(_a_fragmento(p, 1.0, "fundamento"))
    return salida


def fragmento_por_chunk(chunk_id: str) -> Fragmento | None:
    """El fragmento exacto que lleva ese `chunk_id`, o None.

    Existe para los controles de frontera del servidor MCP. Una respuesta
    servida desde el caché semántico llega con sus citas pero **sin el contexto
    que las produjo**, y esa es justamente la respuesta cuya procedencia nadie
    volvió a mirar: se verificó una vez, al generarse, y desde entonces se
    entrega tal cual. Si O1 en la frontera dependiera de que la respuesta traiga
    su propio contexto, el acierto de caché sería el único caso que el control
    no puede revisar.

    Como el corpus vigente ya está en memoria —112 fragmentos, cargados una vez
    por el índice BM25—, buscar por `chunk_id` no cuesta ni una llamada de red.
    """
    puntos, _ = _corpus_en_memoria()
    for p in puntos:
        if p["chunk_id"] == chunk_id:
            return _a_fragmento(p, 1.0, "frontera")
    return None


def _a_fragmento(payload: dict, score: float, origen: str) -> Fragmento:
    return Fragmento(
        chunk_id=payload["chunk_id"], doc_id=payload["doc_id"],
        version_id=payload["version_id"], jerarquia=payload["jerarquia"],
        articulo=payload.get("articulo", ""), texto_literal=payload["texto_literal"],
        tipo_norma=payload.get("tipo_norma", "general"), planes=payload.get("planes", []),
        offset_ini=payload.get("offset_ini", 0), offset_fin=payload.get("offset_fin", 0),
        score=score, origen=[origen],
    )
