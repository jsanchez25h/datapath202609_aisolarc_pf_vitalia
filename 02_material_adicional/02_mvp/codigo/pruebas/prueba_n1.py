"""Carril 0 en vivo: consulta anticipada, caché semántico y verificación de citas.

Produce dos evidencias a la vez:
  E01 · el router eligió Groq por latencia y no por capacidad
  E02 · el caché semántico responde una pregunta *distinta* con la misma respuesta

    python -m pruebas.prueba_n1
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comun import cache_semantico, config, recuperacion, router_modelos  # noqa: E402
from flujo import consulta_n1  # noqa: E402

CONSULTAS = [
    ("Q1", "¿Cuántos días de carencia tiene la cobertura de maternidad?", "VIT-INT"),
    ("Q2", "¿Qué documentos exige Vitalia para autorizar una artroscopia de rodilla?", "VIT-ESE"),
    ("Q3", "¿Qué significa el código REEM-06 en un rechazo de reembolso?", None),
]

# Reformulaciones de Q1: distintas palabras, misma respuesta. Si el caché las
# atrapa, la sesión 02 queda demostrada; si no, el umbral está mal puesto.
REFORMULACIONES = [
    ("Q1b", "cuanto tiempo debo esperar desde que me afilio para que me cubran el parto", "VIT-INT"),
    ("Q1c", "periodo de espera de la cobertura de maternidad en Vitalia", "VIT-INT"),
]


def imprimir(rid: str, consulta: str, r) -> None:
    print(f"\n{'=' * 78}\n{rid} · {consulta}\n{'-' * 78}")
    print(f"  origen ........ {r.origen}"
          + (f"  (similitud {r.similitud_cache})" if r.similitud_cache else ""))
    print(f"  clave caché ... {r.clave_cache or '— (consulta no clasificable)'}")
    print(f"  modelo ........ {r.modelo or '—'}   costo US$ {r.costo_usd:.6f}"
          f"   {r.tokens_in}+{r.tokens_out} tokens")
    print(f"  latencia ...... {r.latencia_ms} ms  = guardrail {r.latencia_guardrail_ms}"
          f" + caché {r.latencia_cache_ms}"
          f" + recuperación {r.latencia_recuperacion_ms}"
          f" + generación {r.latencia_generacion_ms}")
    print(f"  citas ......... {len(r.citas_verificadas)} verificadas · "
          f"{len(r.citas_rechazadas)} rechazadas")
    for c in r.citas_verificadas:
        print(f"      ✔ {c['jerarquia']}")
    for c in r.citas_rechazadas:
        print(f"      ✘ retirada: “{c[:70]}…”")
    print("  ---")
    for linea in r.texto.splitlines():
        print(f"  {linea}")


# Cuasi-aciertos: preguntas parecidas a Q1 cuya respuesta es **distinta**. Un
# caché por similitud pura las sirve con la respuesta de Q1; el caché del MVP
# tiene que fallarlas todas. Sin esta parte, la evidencia de la sesión 02
# demostraría que el caché acierta, no que acierta cuando debe.
# La tercera es de otra naturaleza y se etiqueta aparte: es la consulta ancla
# **palabra por palabra**, con otro plan. Su coseno es 1.0000 por construcción,
# así que mezclarla con las otras dos arruinaría la lectura de la calibración
# —el solapamiento hay que demostrarlo con las que se parecen sin ser iguales—.
# Lo que N3 prueba es lo otro: que el plan de la clave discrimina cuando el
# texto es incapaz de hacerlo.
CUASI_ACIERTOS = [
    ("N1", "¿Cuántos días de carencia tiene la cobertura de salud mental?",
     "VIT-INT", "cuasi_acierto"),
    ("N2", "¿Cuál es el copago de un parto por cesárea?",
     "VIT-INT", "cuasi_acierto"),
    ("N3", "¿Cuántos días de carencia tiene la cobertura de maternidad?",
     "VIT-PRE", "otro_plan"),
]


def calibracion_umbral() -> dict:
    """Mide el coseno entre la consulta ancla y sus vecinas.

    Es la medición que obligó a poner una clave discriminante en el caché: la
    franja de las reformulaciones legítimas y la de las preguntas peligrosas se
    solapan, así que ningún umbral de similitud separa unas de otras.
    """
    import numpy as np
    ancla = CONSULTAS[0][1]
    vecinas = ([("reformulacion", t) for _, t, _ in REFORMULACIONES]
               + [(clase, t) for _, t, _, clase in CUASI_ACIERTOS]
               + [("ajena", CONSULTAS[1][1]), ("ajena", CONSULTAS[2][1])])
    vs = recuperacion.vectorizar([ancla] + [t for _, t in vecinas])
    a = np.array(vs[0])
    filas = []
    for (clase, texto), v in zip(vecinas, vs[1:]):
        v = np.array(v)
        filas.append({"clase": clase, "consulta": texto,
                      "coseno": round(float(a @ v / (np.linalg.norm(a) * np.linalg.norm(v))), 4),
                      "clave": "|".join(cache_semantico.discriminar(texto))})
    return {"ancla": ancla, "vecinas": filas,
            "minimo_reformulacion": min(f["coseno"] for f in filas
                                        if f["clase"] == "reformulacion"),
            "maximo_cuasi_acierto": max(f["coseno"] for f in filas
                                        if f["clase"] == "cuasi_acierto")}


def main() -> int:
    config.configurar_consola()
    print(f"caché vaciado: {cache_semantico.vaciar()} entradas previas\n")

    calibracion = calibracion_umbral()
    print(f"{'#' * 78}\n# Por qué el caché no puede decidir solo por similitud\n"
          f"# ancla: {calibracion['ancla']}\n{'#' * 78}")
    for f in calibracion["vecinas"]:
        print(f"  {f['coseno']:.4f}  {f['clase']:<14} clave={f['clave']:<26} {f['consulta'][:44]}")
    print(f"\n  mínimo entre reformulaciones legítimas : {calibracion['minimo_reformulacion']:.4f}")
    print(f"  máximo entre cuasi-aciertos peligrosos : {calibracion['maximo_cuasi_acierto']:.4f}")
    if calibracion["maximo_cuasi_acierto"] >= calibracion["minimo_reformulacion"]:
        print("  -> las dos franjas se solapan: NO existe umbral que las separe.")
        print("     La seguridad la da la clave discriminante, no el número.")

    filas = []

    for rid, consulta, plan in CONSULTAS:
        r = consulta_n1.responder(consulta, plan)
        imprimir(rid, consulta, r)
        filas.append({"id": rid, "consulta": consulta, "plan": plan, **r.como_dict()})

    print(f"\n\n{'#' * 78}\n# Caché semántico: las mismas preguntas escritas de otra forma\n{'#' * 78}")
    for rid, consulta, plan in REFORMULACIONES:
        r = consulta_n1.responder(consulta, plan)
        imprimir(rid, consulta, r)
        filas.append({"id": rid, "consulta": consulta, "plan": plan, **r.como_dict()})

    print(f"\n\n{'#' * 78}\n# Cuasi-aciertos: se parecen a Q1 y su respuesta es OTRA.\n"
          f"# Ninguno puede salir del caché.\n{'#' * 78}")
    fallos_cache = 0
    for rid, consulta, plan, clase in CUASI_ACIERTOS:
        r = consulta_n1.responder(consulta, plan)
        imprimir(rid, consulta, r)
        if r.origen == "cache":
            fallos_cache += 1
            print("  *** FALSO ACIERTO DE CACHÉ: respuesta de otra pregunta ***")
        filas.append({"id": rid, "consulta": consulta, "plan": plan,
                      "clase": clase, "es_control": True, **r.como_dict()})

    # El ahorro se mide solo sobre el tráfico legítimo. Los cuasi-aciertos son
    # una prueba de seguridad, no de costo: mezclarlos inflaría el denominador.
    legitimas = [f for f in filas if not f.get("es_control")]
    generadas = [f for f in legitimas if f["origen"] == "modelo"]
    cacheadas = [f for f in legitimas if f["origen"] == "cache"]
    costo_real = sum(f["costo_usd"] for f in legitimas)
    costo_medio = sum(f["costo_usd"] for f in generadas) / max(len(generadas), 1)
    costo_sin_cache = costo_real + len(cacheadas) * costo_medio

    def maximo(campo, origen="modelo"):
        return max((f[campo] for f in filas if f["origen"] == origen), default=0)

    resumen = {
        "ruta_elegida": router_modelos.elegir("n1_consulta").__dict__,
        "calibracion_umbral_cache": calibracion,
        "umbral_en_clave": cache_semantico.UMBRAL,
        "consultas_legitimas": len(legitimas),
        "generadas": len(generadas),
        "aciertos_cache": len(cacheadas),
        "tasa_acierto": round(len(cacheadas) / len(legitimas), 3),
        "cuasi_aciertos_probados": len(CUASI_ACIERTOS),
        "falsos_aciertos_cache": fallos_cache,
        "citas_verificadas_total": sum(len(f["citas_verificadas"]) for f in filas),
        "citas_rechazadas_total": sum(len(f["citas_rechazadas"]) for f in filas),
        "respuestas_truncadas": sum(1 for f in filas if f.get("truncada")),
        "latencia_p_max_ms": max(f["latencia_ms"] for f in filas),
        "latencia_max_generada_ms": maximo("latencia_ms"),
        "latencia_max_cache_ms": maximo("latencia_ms", "cache"),
        "desglose_max_generada_ms": {
            "guardrail": maximo("latencia_guardrail_ms"),
            "cache": maximo("latencia_cache_ms"),
            "recuperacion": maximo("latencia_recuperacion_ms"),
            "generacion": maximo("latencia_generacion_ms"),
        },
        "costo_usd_real": round(costo_real, 6),
        "costo_usd_sin_cache": round(costo_sin_cache, 6),
        "ahorro_pct": round(100 * (1 - costo_real / costo_sin_cache), 1) if costo_sin_cache else 0,
        "casos": filas,
    }

    config.EVIDENCIAS_DIR.mkdir(exist_ok=True)
    destino = config.EVIDENCIAS_DIR / "E01_E02_router_y_cache.json"
    destino.write_text(json.dumps(resumen, ensure_ascii=False, indent=2, default=str),
                       encoding="utf-8")

    d = resumen["desglose_max_generada_ms"]
    print(f"\n{'=' * 78}")
    print(f"  aciertos de caché ........ {len(cacheadas)}/{len(legitimas)} legítimas")
    print(f"  falsos aciertos .......... {fallos_cache}/{len(CUASI_ACIERTOS)} "
          f"cuasi-aciertos (debe ser 0)")
    print(f"  citas verificadas por O1 . {resumen['citas_verificadas_total']}")
    print(f"  citas rechazadas por O1 .. {resumen['citas_rechazadas_total']}")
    print(f"  latencia máx generada .... {resumen['latencia_max_generada_ms']} ms"
          f"   (J1 exige p95 < 2000 ms)")
    print(f"      guardrail {d['guardrail']} · caché {d['cache']} · "
          f"recuperación {d['recuperacion']} · generación {d['generacion']}")
    print(f"  latencia máx desde caché . {resumen['latencia_max_cache_ms']} ms")
    print(f"  costo real ............... US$ {costo_real:.6f}"
          f"  vs US$ {costo_sin_cache:.6f} sin caché  ({resumen['ahorro_pct']}% menos)")
    print(f"  evidencia ................ {destino.name}")
    return 1 if fallos_cache else 0


if __name__ == "__main__":
    raise SystemExit(main())
