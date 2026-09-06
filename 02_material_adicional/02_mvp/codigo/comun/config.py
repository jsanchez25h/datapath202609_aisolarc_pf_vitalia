"""Configuración compartida del MVP.

Las credenciales viven en `fase2/variables.sh`, que está fuera de git por el
`.gitignore` de la raíz del repositorio. Este módulo lo lee directamente para
que ningún script dependa de que alguien haya hecho `source` antes, y para que
no exista una segunda copia de las claves en archivos `.env` sueltos.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

RAIZ_FASE2 = Path(__file__).resolve().parents[2]
ARCHIVO_VARIABLES = RAIZ_FASE2 / "variables.sh"

_PATRON = re.compile(r'^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=\s*(.*)$')


def _valor(bruto: str) -> str:
    """Toma el lado derecho de un `export X=...` y devuelve el valor.

    Si viene entrecomillado, el valor termina en la comilla de cierre y lo que
    siga es comentario; si no, termina en el primer ` #`. Sin esto un
    `export X="groq"   # nota` deja el comentario dentro del valor.
    """
    bruto = bruto.strip()
    if bruto[:1] in ("\"", "'"):
        comilla = bruto[0]
        fin = bruto.find(comilla, 1)
        if fin != -1:
            return bruto[1:fin]
        return bruto[1:]
    return re.split(r"\s+#", bruto, maxsplit=1)[0].strip()


def cargar_variables() -> dict[str, str]:
    """Carga variables.sh en os.environ sin pisar lo que ya venga del entorno."""
    valores: dict[str, str] = {}
    if ARCHIVO_VARIABLES.exists():
        for linea in ARCHIVO_VARIABLES.read_text(encoding="utf-8-sig").splitlines():
            if not linea.strip() or linea.lstrip().startswith("#"):
                continue
            m = _PATRON.match(linea)
            if not m:
                continue
            valores[m.group(1)] = _valor(m.group(2))
    for clave, valor in valores.items():
        os.environ.setdefault(clave, valor)
    return valores


cargar_variables()


def var(nombre: str, defecto: str = "") -> str:
    return os.environ.get(nombre, defecto)


def configurar_consola() -> None:
    """La consola de Windows llega en cp1252 y revienta con «✔» o «≥».

    Las evidencias se generan en esta máquina, así que la salida por pantalla
    tiene que sobrevivir al español acentuado sin que el script muera a mitad.
    """
    import sys
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


# --- Constantes del MVP -----------------------------------------------------

VERSION_POLITICA = var("VERSION_POLITICA", "2026-09")
VERSION_ID = "v" + VERSION_POLITICA.replace("-", "_")          # v2026_09
COLECCION = var("QDRANT_COLLECTION_NAME", f"vitalia_politica_{VERSION_ID}")
ALIAS = var("QDRANT_COLLECTION_ALIAS", "politica_actual")
COLECCION_CACHE = var("QDRANT_CACHE_COLLECTION", "vitalia_cache_semantico")
RETRIEVAL_LIMIT = int(var("RETRIEVAL_LIMIT", "8"))
DB_SCHEMA = var("DB_SCHEMA", "vitalia_mvp")

MODELO_EMBEDDING = "text-embedding-3-large"     # 3,072 dims, como en el diseño
DIM_EMBEDDING = 3072

CORPUS_DIR = RAIZ_FASE2 / "codigo" / "corpus"
EVIDENCIAS_DIR = RAIZ_FASE2 / "evidencias"


def conexion_pg():
    """Conexión a Neon con el `search_path` del MVP puesto por dos vías.

    El endpoint de Neon es el *pooler*: multiplexa varias sesiones lógicas sobre
    menos conexiones reales y puede reasignar el backend entre transacciones, así
    que un `SET search_path` ejecutado al conectar sobrevive a la sesión pero no
    necesariamente al pooler.

    Se descubrió en el servidor MCP y no en la API por una cuestión de forma: la
    API abre la conexión, resuelve la petición en milisegundos y la cierra,
    mientras que una herramienta MCP la mantiene abierta mientras espera al
    modelo. En esos segundos el pooler reasignaba el backend y la consulta
    siguiente —el `INSERT` de costo, al final del camino— fallaba con «relation
    "metrica_costo" does not exist» sobre una base donde la tabla existe. Un
    error de configuración disfrazado de error de esquema.

    El arreglo de verdad no está aquí sino en el rol: `ALTER ROLE … SET
    search_path` lo deja como valor por defecto del usuario, que cualquier
    backend hereda al arrancar. El `SET` de abajo se conserva para las conexiones
    directas y para cualquier rol que no lo tenga configurado; no se pone en
    `options` porque el pooler de Neon rechaza ese parámetro de arranque.
    """
    import psycopg2
    cn = psycopg2.connect(var("DATABASE_URL"), connect_timeout=20)
    with cn.cursor() as cur:
        cur.execute(f"SET search_path TO {DB_SCHEMA}, public")
    cn.commit()
    return cn


# Los dos clientes se memorizan a propósito. Construirlos abre una conexión TLS
# nueva, y eso se midió: `cliente_qdrant()` cuesta ~630 ms y `cliente_openai()`
# ~430 ms cada vez. Una recuperación híbrida los construía cuatro veces, así que
# dos tercios de los 2.8 s de latencia eran apretones de manos, no búsqueda.
# Ambos clientes son reutilizables entre llamadas; el proceso es de vida corta.

@lru_cache(maxsize=1)
def cliente_qdrant():
    from qdrant_client import QdrantClient
    return QdrantClient(url=var("QDRANT_URL"), api_key=var("QDRANT_API_KEY"), timeout=60)


@lru_cache(maxsize=1)
def cliente_openai():
    from openai import OpenAI
    return OpenAI(api_key=var("OPENAI_API_KEY"))
