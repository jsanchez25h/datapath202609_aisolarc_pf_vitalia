"""Ingesta del corpus normativo de Vitalia Salud — sesión 04 del curso.

Hace lo que el ciclo de vida de una versión describe en `08_modelo_de_datos.md` §3.2,
recortado a lo que un MVP puede sostener:

    documento fuente (Markdown)
       -> sha256 del documento
       -> segmentación POR CLÁUSULA, no por número fijo de tokens        (ADR-19)
       -> jerarquía repetida en cada fragmento + ventana de vecinos
       -> embeddings text-embedding-3-large (3,072 dims)
       -> colección NUEVA por versión; la anterior sigue viva            (ADR-21)
       -> registro en politica_version con firma del curador
       -> invalidación total del caché semántico
       -> el alias `politica_actual` apunta a la colección nueva

Uso:
    python -m ingesta.pipeline_politica --version v2026_09 --aprobado-por "curador@vitalia.pe"
    python -m ingesta.pipeline_politica --version v2026_10 --publicar-alias
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comun import config  # noqa: E402
from qdrant_client import models as qm  # noqa: E402

PLANES = {"VIT-ESE": ("esencial",), "VIT-INT": ("integral",), "VIT-PRE": ("premium",)}

TIPO_NORMA = {
    "exclusiones": "exclusion",
    "carencias_y_preexistencias": "carencia",
    "deducibles_y_copagos": "copago",
    "planes_y_coberturas": "cobertura",
    "autorizaciones": "procedimiento",
    "protocolos_de_procedimientos_quirurgicos": "protocolo",
    "reembolsos": "reembolso",
    "red_de_clinicas": "red",
    "afiliacion_y_dependientes": "afiliacion",
    "facturacion_y_pagos": "facturacion",
    "faq_atencion": "atencion",
}


# --------------------------------------------------------------------------
# 1 · Segmentación por cláusula
# --------------------------------------------------------------------------

def segmentar(texto: str, doc_id: str, version_id: str, sha256_doc: str) -> list[dict]:
    """Cada `###` es una cláusula. El encabezado jerárquico se repite en el
    fragmento porque una cláusula que dice «lo señalado en el numeral anterior
    no aplica» es inútil fuera de contexto."""
    titulo = ""
    capitulo = ""
    fragmentos: list[dict] = []
    actual: dict | None = None
    offset = 0

    for linea in texto.splitlines(keepends=True):
        desnuda = linea.rstrip("\n")
        if desnuda.startswith("# "):
            titulo = desnuda[2:].strip()
        elif desnuda.startswith("## "):
            capitulo = desnuda[3:].strip()
        elif desnuda.startswith("### "):
            if actual:
                actual["offset_fin"] = offset
                fragmentos.append(actual)
            articulo = desnuda[4:].strip()
            actual = {
                "articulo": articulo,
                "jerarquia": " > ".join(x for x in (titulo, capitulo, articulo) if x),
                "cuerpo": [],
                "offset_ini": offset,
            }
        elif actual is not None:
            actual["cuerpo"].append(desnuda)
        offset += len(linea)

    if actual:
        actual["offset_fin"] = offset
        fragmentos.append(actual)

    salida = []
    for i, f in enumerate(fragmentos):
        cuerpo = "\n".join(f["cuerpo"]).strip()
        if not cuerpo:
            continue
        texto_literal = f"{f['jerarquia']}\n\n{cuerpo}"
        salida.append({
            "chunk_id": f"{doc_id}-{version_id}-c{i+1:02d}",
            "doc_id": doc_id,
            "version_id": version_id,
            "sha256_doc": sha256_doc,
            "jerarquia": f["jerarquia"],
            "articulo": f["articulo"],
            "planes": detectar_planes(cuerpo),
            "tipo_norma": TIPO_NORMA.get(doc_id, "general"),
            "offset_ini": f["offset_ini"],
            "offset_fin": f["offset_fin"],
            "texto_literal": texto_literal,
            "tokens_aprox": len(texto_literal) // 4,
        })

    # Ventana de vecinos (sentence-window): la cláusula se recupera y se entrega
    # con la anterior y la siguiente como contexto.
    for i, f in enumerate(salida):
        f["chunk_anterior"] = salida[i - 1]["chunk_id"] if i > 0 else None
        f["chunk_siguiente"] = salida[i + 1]["chunk_id"] if i < len(salida) - 1 else None
    return salida


def detectar_planes(cuerpo: str) -> list[str]:
    bajo = cuerpo.lower()
    encontrados = [c for c, alias in PLANES.items()
                   if c.lower() in bajo or any(a in bajo for a in alias)]
    return encontrados or list(PLANES)


# --------------------------------------------------------------------------
# 2 · Embeddings y carga
# --------------------------------------------------------------------------

def embeber(textos: list[str]) -> list[list[float]]:
    cli = config.cliente_openai()
    vectores: list[list[float]] = []
    for i in range(0, len(textos), 64):
        lote = textos[i:i + 64]
        r = cli.embeddings.create(model=config.MODELO_EMBEDDING, input=lote)
        vectores.extend(d.embedding for d in r.data)
    return vectores


def crear_coleccion(qc, nombre: str) -> None:
    if qc.collection_exists(nombre):
        qc.delete_collection(nombre)
    qc.create_collection(
        collection_name=nombre,
        vectors_config=qm.VectorParams(size=config.DIM_EMBEDDING, distance=qm.Distance.COSINE),
    )
    for campo, tipo in (("version_id", "keyword"), ("tipo_norma", "keyword"),
                        ("planes", "keyword"), ("doc_id", "keyword")):
        qc.create_payload_index(collection_name=nombre, field_name=campo, field_schema=tipo)


# --------------------------------------------------------------------------
# 3 · Orquestación
# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=config.VERSION_ID)
    ap.add_argument("--aprobado-por", default="curador.politica@vitaliasalud.pe")
    ap.add_argument("--publicar-alias", action="store_true",
                    help="apunta politica_actual a esta colección al terminar")
    ap.add_argument("--diff", default="", help="qué cambió respecto de la versión anterior")
    args = ap.parse_args()

    version_id = args.version
    carpeta = config.CORPUS_DIR / version_id
    if not carpeta.is_dir():
        print(f"ERROR: no existe {carpeta}")
        return 1

    coleccion = f"vitalia_politica_{version_id}"
    t0 = time.time()
    print(f"[ingesta] versión {version_id} · carpeta {carpeta.name} · colección {coleccion}")

    documentos = sorted(p for p in carpeta.glob("*.md") if not p.name.startswith("00_"))
    fragmentos: list[dict] = []
    for ruta in documentos:
        texto = ruta.read_text(encoding="utf-8")
        sha = hashlib.sha256(texto.encode("utf-8")).hexdigest()
        doc_id = ruta.stem
        trozos = segmentar(texto, doc_id, version_id, sha)
        fragmentos.extend(trozos)
        print(f"  {doc_id:<45} {len(texto):>6} bytes  sha256 {sha[:12]}…  {len(trozos):>3} cláusulas")

    print(f"[ingesta] {len(documentos)} documentos -> {len(fragmentos)} fragmentos "
          f"(promedio {sum(f['tokens_aprox'] for f in fragmentos)//max(len(fragmentos),1)} tokens)")

    print(f"[ingesta] embeddings con {config.MODELO_EMBEDDING} ({config.DIM_EMBEDDING} dims)…")
    vectores = embeber([f["texto_literal"] for f in fragmentos])

    qc = config.cliente_qdrant()
    crear_coleccion(qc, coleccion)
    qc.upsert(
        collection_name=coleccion,
        points=[
            qm.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL, f["chunk_id"])),
                           vector=v, payload=f)
            for f, v in zip(fragmentos, vectores)
        ],
        wait=True,
    )
    n = qc.count(coleccion, exact=True).count
    print(f"[ingesta] cargados {n} puntos en {coleccion}")

    # Registro de la versión en Neon, con la firma del curador.
    sha_corpus = hashlib.sha256(
        "".join(sorted(f["sha256_doc"] for f in fragmentos)).encode()).hexdigest()
    cn = config.conexion_pg()
    with cn.cursor() as cur:
        cur.execute("""
            INSERT INTO politica_version
                (version_id, sha256, vigencia_desde, aprobado_por, diff_vs_anterior,
                 coleccion_qdrant, fragmentos)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (version_id) DO UPDATE SET
                sha256=EXCLUDED.sha256, aprobado_por=EXCLUDED.aprobado_por,
                diff_vs_anterior=EXCLUDED.diff_vs_anterior,
                coleccion_qdrant=EXCLUDED.coleccion_qdrant, fragmentos=EXCLUDED.fragmentos
        """, (version_id, sha_corpus, dt.date.today(), args.aprobado_por,
              args.diff or None, coleccion, n))
    cn.commit()
    cn.close()
    print(f"[ingesta] politica_version registrada · sha256 corpus {sha_corpus[:16]}… "
          f"· aprobada por {args.aprobado_por}")

    if args.publicar_alias:
        # Invalidación total del caché semántico ANTES de mover el alias:
        # una respuesta cacheada bajo la versión anterior es política derogada.
        if qc.collection_exists(config.COLECCION_CACHE):
            qc.delete_collection(config.COLECCION_CACHE)
            print(f"[ingesta] caché semántico invalidado ({config.COLECCION_CACHE})")
        operaciones = []
        if config.ALIAS in [a.alias_name for a in qc.get_aliases().aliases]:
            operaciones.append(qm.DeleteAliasOperation(
                delete_alias=qm.DeleteAlias(alias_name=config.ALIAS)))
        operaciones.append(qm.CreateAliasOperation(create_alias=qm.CreateAlias(
            collection_name=coleccion, alias_name=config.ALIAS)))
        qc.update_collection_aliases(change_aliases_operations=operaciones)
        print(f"[ingesta] alias {config.ALIAS} -> {coleccion}")

    resumen = {
        "version_id": version_id,
        "coleccion": coleccion,
        "documentos": len(documentos),
        "fragmentos": n,
        "sha256_corpus": sha_corpus,
        "modelo_embedding": config.MODELO_EMBEDDING,
        "dims": config.DIM_EMBEDDING,
        "alias_publicado": bool(args.publicar_alias),
        "segundos": round(time.time() - t0, 1),
        "por_documento": {
            d: sum(1 for f in fragmentos if f["doc_id"] == d)
            for d in sorted({f["doc_id"] for f in fragmentos})
        },
    }
    config.EVIDENCIAS_DIR.mkdir(exist_ok=True)
    salida = config.EVIDENCIAS_DIR / f"E04_ingesta_{version_id}.json"
    salida.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ingesta] listo en {resumen['segundos']} s · evidencia en {salida.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
