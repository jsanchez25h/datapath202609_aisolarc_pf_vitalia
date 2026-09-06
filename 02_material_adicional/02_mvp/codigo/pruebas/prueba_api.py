"""Prueba del servicio · lo que hace la mesa cuando el sistema no decide solo.

El Carril 1 ya está probado por `prueba_carril1`: esto no lo repite. Lo que se
ejercita aquí es lo que ocurre **después**, cuando el expediente queda en `hitl`
y la carta la tiene que emitir una persona. Es el trozo del diseño donde el
ADR-10 deja de ser una frase y se convierte en un flujo con dos actores.

La secuencia es una sola y va en orden, porque cada paso depende del estado que
dejó el anterior:

  A · Una persona edita la carta e inventa una cita.        → 409, bloquea O1
  B · La misma persona aprueba el borrador del sistema.     → 200, carta emitida
  C · Alguien intenta resolver el mismo expediente de nuevo.→ 409, ya no está en hitl
  D · La interfaz se pide al mismo proceso que la API.      → 200, text/html
  E · La misma consulta N1 dos veces.                       → citas iguales, US$ 0
  F · Y esas dos consultas en el panel del supervisor.      → +2 lecturas, +1 acierto

**A es el caso que justifica todo el endpoint.** Un guardrail que solo controla
lo que escribió el modelo deja sin controlar justo el texto que sí lleva firma
y sí sale de la empresa. Si A pasara, la carta con la cita inventada saldría
con el nombre de un analista debajo, y O1 habría servido para nada.

Corre contra Neon y Qdrant de verdad, sin servidor: `TestClient` monta la
aplicación en el proceso. Lo que se prueba es la aplicación, no el `uvicorn`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from fastapi.testclient import TestClient

from api.principal import app
from comun import cache_semantico, config

config.configurar_consola()
cliente = TestClient(app)

# La cita es falsa de raíz: la carencia de maternidad son 300 días, no 90. El
# número está mal *y* la frase no existe en ninguna cláusula. Que O1 la rechace
# no depende de que sepa de política: depende de que la frase no esté en el
# corpus.
#
# Lo que este caso **no** puede afirmar es cuáles controles caen además de O1.
# Se vio en una corrida: con un expediente de cesárea el fragmento firmado en
# `FUENTES:` sí estaba en su contexto y solo cayó O1; con uno de hernioplastía
# el mismo texto cayó por O1 y O6, porque allí esa cláusula era ajena al
# expediente. Exigir la lista exacta ataba el resultado a qué expediente hubiera
# quedado en la cola. Aquí se exige lo que el caso demuestra —O1 bloquea la
# frase que no existe— y O6 se prueba aparte, en A2, donde es deliberado.
CUERPO_INVENTADO = (
    "Estimada Ana Lucía Cavero Bendezú,\n\n"
    "Su solicitud no procede. Como dice la póliza, «la cobertura de maternidad "
    "se activa a los 90 días de afiliación y usted no los cumple», por lo que "
    "no podemos autorizar la cesárea PRC-5901.\n\n"
    "Atentamente,\nVitalia Salud EPS\n\n"
    "FUENTES: carencias_y_preexistencias-v2026_09-c03"
)


def fallo(msg: str, detalle: str = "") -> dict:
    print(f"  FALLA  {msg}" + (f" · {detalle}" if detalle else ""))
    return {"paso": msg, "detalle": detalle}


def main() -> int:
    fallos: list[dict] = []
    evidencia: dict = {}

    print("=" * 78)
    print("Servicio · resolución de un expediente por una persona")
    print("=" * 78)

    r = cliente.get("/salud")
    salud = r.json()
    evidencia["salud"] = salud
    print(f"  salud .......... neon={salud['neon'].get('ok')} "
          f"qdrant={salud['qdrant'].get('ok')} política={salud['version_politica']}")
    if not salud.get("ok"):
        fallos.append(fallo("/salud", json.dumps(salud, ensure_ascii=False)[:200]))
        return resumen(evidencia, fallos)

    cola = cliente.get("/solicitudes", params={"estado": "hitl"}).json()["expedientes"]
    if not cola:
        fallos.append(fallo("no hay ningún expediente en hitl",
                            "corre antes `python -m pruebas.prueba_carril1`"))
        return resumen(evidencia, fallos)
    sid = cola[0]["solicitud_id"]
    print(f"  expediente ..... {sid} · {cola[0]['afiliado']} · {cola[0]['procedimiento']}")

    det = cliente.get(f"/solicitudes/{sid}").json()
    evidencia["expediente"] = {
        "solicitud_id": sid,
        "estado_inicial": det["estado_actual"],
        "ruta": det["adjudicacion"]["ruta"],
        "motivo_ruta": det["adjudicacion"]["motivo_ruta"],
        # La frontera R1, leída del dato y no de la documentación: la extracción
        # declara qué modelo la produjo, la adjudicación declara que no hubo.
        "modelo_extraccion": next((c["modelo"] for c in det["extraccion"]), None),
        "modelo_adjudicacion": det["adjudicacion"]["modelo"],
        "adjudicacion_determinista": det["adjudicacion"]["determinista"],
        "borradores_previos": len(det["borradores"]),
    }
    print(f"  R1 ............. extracción por «{evidencia['expediente']['modelo_extraccion']}» · "
          f"adjudicación por «{evidencia['expediente']['modelo_adjudicacion']}» "
          f"(determinista={det['adjudicacion']['determinista']})")

    # --- A ------------------------------------------------------------------
    ra = cliente.post(f"/solicitudes/{sid}/resolver",
                      json={"actor": "analista.mesa@vitalia.pe",
                            "cuerpo": CUERPO_INVENTADO})
    da = ra.json()
    evidencia["A_carta_editada_con_cita_inventada"] = {
        "http": ra.status_code, "emitida": da.get("emitida"),
        "bloquearon": da.get("bloquearon"), "controles": da.get("controles"),
    }
    ok_a = ra.status_code == 409 and "O1" in (da.get("bloquearon") or [])
    print(f"  {'OK  ' if ok_a else 'FALLA'} A · carta editada por una persona, cita inventada "
          f"→ HTTP {ra.status_code}, bloquearon {da.get('bloquearon')}")
    if not ok_a:
        fallos.append(fallo("A", f"esperaba 409 y O1 entre los que bloquean, salió "
                                 f"{ra.status_code} {da.get('bloquearon')}"))

    # --- A2 -----------------------------------------------------------------
    # El mismo cuerpo que el guardrail ya aprobó, con una sola diferencia: la
    # línea `FUENTES:` declara además una cláusula de reembolsos que jamás
    # estuvo en el contexto de este expediente. Las citas del texto siguen
    # siendo las mismas y O1 sigue pasando, así que lo que caiga cae por O6 y
    # por nada más: la carta cita bien y firma un respaldo que quien fiscalice
    # no puede abrir. Es el tercer huérfano de O6 —el que no se ve leyendo el
    # párrafo, solo comparando la firma con el expediente—.
    aprobado = next((b for b in det["borradores"] if b["aprobada_guardrail"]), None)
    if aprobado:
        cuerpo_fuente_ajena = aprobado["cuerpo"].replace(
            "FUENTES:", "FUENTES: reembolsos-v2026_09-c10,", 1)
        ra2 = cliente.post(f"/solicitudes/{sid}/resolver",
                           json={"actor": "analista.mesa@vitalia.pe",
                                 "cuerpo": cuerpo_fuente_ajena})
        da2 = ra2.json()
        evidencia["A2_fuente_ajena_al_expediente"] = {
            "http": ra2.status_code, "emitida": da2.get("emitida"),
            "bloquearon": da2.get("bloquearon"), "controles": da2.get("controles"),
        }
        ok_a2 = ra2.status_code == 409 and da2.get("bloquearon") == ["O6"]
        print(f"  {'OK  ' if ok_a2 else 'FALLA'} A2 · cita buena, fuente ajena al expediente "
              f"→ HTTP {ra2.status_code}, bloquearon {da2.get('bloquearon')}")
        if not ok_a2:
            fallos.append(fallo("A2", f"esperaba 409 y ['O6'], salió {ra2.status_code} "
                                      f"{da2.get('bloquearon')}"))
    else:
        fallos.append(fallo("A2", "no hay borrador aprobado sobre el que montar el caso"))

    # --- B ------------------------------------------------------------------
    rb = cliente.post(f"/solicitudes/{sid}/resolver",
                      json={"actor": "analista.mesa@vitalia.pe"})
    db = rb.json()
    evidencia["B_aprueba_el_borrador_del_sistema"] = {
        "http": rb.status_code, "emitida": db.get("emitida"),
        "carta_id": db.get("carta_id"), "tipo": db.get("tipo"),
        "editada_por_persona": db.get("editada_por_persona"),
    }
    ok_b = rb.status_code == 200 and db.get("emitida") and db.get("carta_id")
    print(f"  {'OK  ' if ok_b else 'FALLA'} B · aprueba el borrador del sistema "
          f"→ HTTP {rb.status_code}, carta {db.get('carta_id')}")
    if not ok_b:
        fallos.append(fallo("B", json.dumps(db, ensure_ascii=False)[:220]))

    # --- C ------------------------------------------------------------------
    rc = cliente.post(f"/solicitudes/{sid}/resolver",
                      json={"actor": "otro.analista@vitalia.pe"})
    dc = rc.json()
    evidencia["C_reintento_sobre_expediente_ya_emitido"] = {
        "http": rc.status_code, "detalle": dc.get("detail", "")[:200]}
    ok_c = rc.status_code == 409 and "hitl" in str(dc.get("detail", ""))
    print(f"  {'OK  ' if ok_c else 'FALLA'} C · reintento sobre el mismo expediente "
          f"→ HTTP {rc.status_code}")
    if not ok_c:
        fallos.append(fallo("C", json.dumps(dc, ensure_ascii=False)[:220]))

    # --- D · la interfaz sale del mismo contenedor ---------------------------
    rd = cliente.get("/")
    ok_d = (rd.status_code == 200
            and "text/html" in rd.headers.get("content-type", "")
            and "Vitalia Salud EPS" in rd.text)
    evidencia["D_interfaz_servida_por_el_mismo_proceso"] = {
        "http": rd.status_code, "bytes": len(rd.content),
        "content_type": rd.headers.get("content-type"),
    }
    print(f"  {'OK  ' if ok_d else 'FALLA'} D · app-mesa servida por el mismo proceso "
          f"→ HTTP {rd.status_code}, {len(rd.content)} bytes")
    if not ok_d:
        fallos.append(fallo("D", "la interfaz no se sirve desde /"))

    # --- E · el caché no pierde las citas ------------------------------------
    # Solo se cachean respuestas cuyas citas pasaron O1 enteras. Si el acierto
    # devolviera la prosa sin los `chunk_id`, la misma respuesta valdría menos
    # por haber llegado más barata: el prestador no tendría contra qué
    # contrastarla. La clave del caché empieza por la versión de política, así
    # que estas citas siguen siendo de la versión vigente sin recomprobarse.
    cache_semantico.vaciar()
    # El estado del caché en la base **antes** de las dos llamadas: la base es
    # acumulativa entre corridas, así que lo que se mide es el delta y no el total.
    antes_cache = cliente.get("/operacion/panel").json()["cache"]
    Q = {"consulta": "¿Cuántos días de carencia tiene la cobertura de maternidad?",
         "plan": "VIT-INT"}
    fresca = cliente.post("/n1/consulta", json=Q).json()
    cacheada = cliente.post("/n1/consulta", json=Q).json()
    ok_e = (fresca["origen"] == "modelo" and cacheada["origen"] == "cache"
            and cacheada["citas_verificadas"] == fresca["citas_verificadas"]
            and len(cacheada["citas_verificadas"]) > 0
            and (cacheada.get("costo_usd") or 0) == 0)
    evidencia["E_acierto_de_cache_conserva_las_citas"] = {
        "fresca": {"origen": fresca["origen"], "citas": len(fresca["citas_verificadas"]),
                   "costo_usd": fresca.get("costo_usd"), "latencia_ms": fresca["latencia_ms"]},
        "cacheada": {"origen": cacheada["origen"], "citas": len(cacheada["citas_verificadas"]),
                     "costo_usd": cacheada.get("costo_usd"),
                     "similitud": cacheada.get("similitud_cache"),
                     "latencia_ms": cacheada["latencia_ms"],
                     "clave": cacheada.get("clave_cache")},
        "citas": cacheada["citas_verificadas"],
    }
    print(f"  {'OK  ' if ok_e else 'FALLA'} E · el acierto de caché conserva sus citas "
          f"→ {len(cacheada['citas_verificadas'])} cita(s), "
          f"{fresca['latencia_ms']} ms → {cacheada['latencia_ms']} ms, US$ 0")
    if not ok_e:
        fallos.append(fallo("E", f"fresca={fresca['origen']}/"
                                 f"{len(fresca['citas_verificadas'])} "
                                 f"cacheada={cacheada['origen']}/"
                                 f"{len(cacheada['citas_verificadas'])}"))

    # --- F · el Carril 0 deja rastro de lo que gasta -------------------------
    # Las dos llamadas de E son la única forma limpia de comprobarlo: una pagó
    # tokens y la otra no, así que si el carril anota, `metrica_costo` tiene que
    # haber recibido una lectura de más y un acierto de más. Durante buena parte
    # del MVP no anotaba nada, y el panel de la pantalla 5 mostraba «aciertos de
    # caché —»: el ahorro existía —la prueba `prueba_n1` lo medía en su propio
    # JSON— pero no llegaba a la base que el supervisor consulta. Un ahorro que
    # solo está en el archivo de una prueba no es un indicador de operación.
    pf = cliente.get("/operacion/panel").json()
    spans_n1 = [s for s in pf["por_span"] if s["span"] == "n1"]
    ok_f = (pf["cache"]["lecturas"] - antes_cache["lecturas"] >= 2
            and pf["cache"]["aciertos"] - antes_cache["aciertos"] >= 1
            and pf["cache"]["hit_rate"] is not None
            and len(spans_n1) == 1)
    evidencia["F_carril0_escribe_su_costo"] = {
        "cache_antes": antes_cache, "cache_despues": pf["cache"],
        "span_n1": spans_n1[0] if spans_n1 else None,
    }
    print(f"  {'OK  ' if ok_f else 'FALLA'} F · el Carril 0 escribe su costo "
          f"→ {pf['cache']['lecturas']} lecturas, {pf['cache']['aciertos']} aciertos, "
          f"hit-rate {pf['cache']['hit_rate']}")
    if not ok_f:
        fallos.append(fallo("F", f"antes={antes_cache} después={pf['cache']} "
                                 f"spans n1={len(spans_n1)}"))

    # --- lo que quedó escrito ------------------------------------------------
    fin = cliente.get(f"/solicitudes/{sid}").json()
    evidencia["bitacora_final"] = fin["bitacora"]
    evidencia["cartas"] = [{k: c[k] for k in ("carta_id", "tipo", "version_politica",
                                              "core_folio", "emitida_en")}
                           for c in fin["cartas"]]
    evidencia["borradores_finales"] = [
        {"aprobada_guardrail": b["aprobada_guardrail"], "creado_en": b["creado_en"]}
        for b in fin["borradores"]]

    print(f"\n  estado final ... {fin['estado_actual']}")
    for e in fin["bitacora"]:
        print(f"     {(e['desde'] or '—'):>8} → {e['hacia']:<9} {e['actor']:<26} "
              f"{(e['motivo'] or '')[:46]}")

    # El intento reprobado tiene que estar contado. Si la mesa pudiera reintentar
    # sin dejar rastro, la tasa de cartas que el guardrail bloquea se mediría
    # sobre las que pasaron y daría siempre cero —el mismo defecto que ya
    # apareció en el guardrail de entrada del Carril 1—.
    reprobados = sum(1 for b in fin["borradores"] if not b["aprobada_guardrail"])
    print(f"  borradores ..... {len(fin['borradores'])} "
          f"({reprobados} reprobados por el guardrail, conservados)")
    if reprobados == 0:
        fallos.append(fallo("trazabilidad",
                            "el intento que O1 reprobó no quedó registrado"))

    # --- panel ---------------------------------------------------------------
    panel = cliente.get("/operacion/panel").json()
    evidencia["panel"] = panel
    print(f"  panel .......... {panel['solicitudes']} solicitudes · "
          f"US$ {panel['costo_usd_total']:.6f} · "
          f"S/ {panel['costo_pen_por_solicitud']:.4f} por solicitud")
    for s in panel["por_span"]:
        print(f"     {s['span']:<14} {s['llamadas']:>2} llamada(s)  "
              f"US$ {float(s['costo_usd']):.6f}  p95 {s['p95_ms']:.0f} ms")

    v = cliente.post("/feedback", json={"solicitud_id": sid, "usuario": "supervisor",
                                        "util": True,
                                        "comentario": "la carta cita el artículo correcto"})
    evidencia["feedback"] = v.json()
    if v.status_code != 201:
        fallos.append(fallo("/feedback", str(v.status_code)))

    return resumen(evidencia, fallos)


def resumen(evidencia: dict, fallos: list) -> int:
    evidencia["fallos"] = fallos
    salida = config.EVIDENCIAS_DIR / "E11_servicio_y_mesa.json"
    salida.write_text(json.dumps(evidencia, ensure_ascii=False, indent=2, default=str),
                      encoding="utf-8")
    print("=" * 78)
    print(f"  evidencia ...... {salida.name}")
    print(f"  fallos ......... {len(fallos)}")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
