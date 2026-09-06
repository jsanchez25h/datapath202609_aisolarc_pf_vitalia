"""Carril 1 de extremo a extremo, y el banco de pruebas del guardrail de salida.

    python -m pruebas.prueba_carril1

Tres partes, en este orden y no en otro:

G · **Guarda de fundamentos.** Que cada pareja `(doc_id, artículo)` de
    `motor.FUNDAMENTO` resuelva a un fragmento real del corpus vigente. Corre
    primero porque si un fundamento no resuelve, las cartas de más abajo salen
    con una conclusión que ninguna cláusula sustenta, y el defecto se ve como una
    cita de menos, no como un error. Ya pasó una vez con `elegibilidad`.

C · **Los tres casos de la rebanada**, ahora con el expediente completo: texto
    libre del prestador → E1 → E2 → E3 → E4, con las filas en la base y el costo
    por span. Es lo que J4 mide.

X · **Cartas construidas para fallar.** Los controles O1–O6 no se demuestran con
    cartas correctas: una carta correcta prueba que el guardrail no estorba, no
    que sirva. Cada caso X fuerza un cuerpo con un defecto concreto y verifica
    que el control que le toca —y solo ese— bloquee.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comun import (config, motor_determinista as motor,  # noqa: E402
                   recuperacion, repositorio as repo)
from flujo import carril1, emision_e4  # noqa: E402
from guardrails import salida as gs  # noqa: E402

HOY = dt.date(2026, 9, 5)

# El texto es el que llega de verdad: un correo del prestador, con saludo, con el
# dato disperso y con el nombre del documento escrito como lo escribe una
# secretaria. E1 tiene que sacar seis campos de aquí, no de un formulario.
CASOS = [
    {
        "id": "C1",
        "titulo": "Colecistectomía laparoscópica · VIT-INT · expediente completo",
        "demuestra": "STP: E1 extrae, el motor adjudica, E4 redacta y la carta se emite",
        "espera_ruta": "auto",
        "espera_tipo": "autoriza",
        "espera_estado": "emitida",
        "texto": """Estimados, Clínica San Felipe (PRE-0031) solicita preautorización
programada para la afiliada AF-100234, quien tiene indicación de colecistectomía
laparoscópica, código PRC-4712, por diagnóstico K80.2 (colelitiasis con colecistitis
aguda). Adjuntamos la orden médica firmada por el Dr. Ramírez, el informe médico
del servicio de cirugía general y la ecografía abdominal con su informe
radiológico. Quedamos atentos. Coordinación de Autorizaciones.""",
    },
    {
        "id": "C2",
        "titulo": "Artroscopia de rodilla · VIT-ESE · falta el informe de terapia física",
        "demuestra": "subsanación: el sistema no rechaza por falta de papeles, pide lo que falta",
        "espera_ruta": "agente",
        "espera_tipo": "observa",
        "espera_estado": "agente",
        "espera_copago": Decimal("1660.00"),
        "texto": """Buenos días. Desde el Policlínico Los Olivos (PRE-0104) remitimos
solicitud de artroscopia de rodilla PRC-2933 para el afiliado AF-100777, con
diagnóstico M23.2, trastorno de menisco por desgarro antiguo. Va adjunta la orden
médica, el informe médico del traumatólogo y la resonancia magnética de rodilla
derecha. El informe de terapia física todavía está pendiente, lo remitiremos en
cuanto el servicio lo emita. Es una solicitud programada.""",
    },
    {
        "id": "C3",
        "titulo": "Parto por cesárea · VIT-INT · 220 días de afiliación (carencia 300)",
        "demuestra": "ADR-10: ante una carencia incumplida el sistema no niega, escala con el borrador",
        "espera_ruta": "hitl",
        "espera_tipo": "niega_administrativa",
        "espera_estado": "hitl",
        "texto": """Clínica Materno Infantil Belén (PRE-0077) solicita autorización
programada de parto por cesárea, procedimiento PRC-5901, para la afiliada
AF-100512, diagnóstico O82.0. Se adjunta la orden médica del gineco-obstetra, el
informe médico con la indicación de cesárea electiva por presentación podálica, la
ecografía obstétrica del tercer trimestre y el control prenatal vigente.""",
    },
]


def guarda_fundamentos() -> tuple[list[dict], int]:
    """Cada fundamento del motor tiene que resolver a una cláusula que exista."""
    filas, fallos = [], 0
    for clave, par in motor.FUNDAMENTO.items():
        resuelve = bool(recuperacion.fragmentos_de([par]))
        filas.append({"clave": clave, "doc_id": par[0], "articulo": par[1],
                      "resuelve": resuelve})
        if not resuelve:
            fallos += 1
        print(f"  {'OK  ' if resuelve else 'FALTA'} {clave:22} {par[0]} § {par[1]}")
    return filas, fallos


def _contexto_del_banco(cn):
    """El caso sobre el que se montan las cartas forzadas: C1, adjudicado limpio.

    No se toma de la base ni del resultado de arriba a propósito. El banco X mide
    el guardrail de salida, no el carril: si dependiera de cuál expediente se
    abrió, un fallo de E1 cambiaría en silencio qué carta se está inspeccionando
    y los controles pasarían a medir otra cosa. Aquí el contexto es fijo, con
    copago calculado y documentos completos, que es el caso donde los seis
    controles tienen algo que verificar.
    """
    afiliado = repo.obtener_afiliado(cn, "AF-100234")
    solicitud = {"afiliado_ref": "AF-100234", "procedimiento_codigo": "PRC-4712",
                 "dx_cie10": "K80.2", "tipo": "programado", "prestador_id": "PRE-0031"}
    proc = repo.obtener_procedimiento(cn, "PRC-4712")
    tarifa = repo.obtener_tarifa(cn, "PRC-4712", afiliado["plan_codigo"])
    r = motor.adjudicar(afiliado, solicitud, tarifa,
                        motor.DOCUMENTOS_EXIGIDOS["PRC-4712"], HOY)
    return afiliado, solicitud, proc, r


# La carta base del banco X. Es una carta **correcta**: cita textualmente una
# cláusula del corpus vigente, dice el copago que calculó el motor y declara en
# FUENTES el identificador del fragmento que citó. Cada caso X le introduce un
# solo defecto, para que el control que bloquea señale ese defecto y no otro.
CUERPO_OK = """Estimada señora {nombre}:

Su solicitud de {procedimiento} ({codigo}) ha sido autorizada.

El copago que le corresponde asumir es de {copago}, según la política vigente:
«{cita}».

Si tiene alguna consulta puede escribirnos respondiendo esta carta.

Atentamente,
Mesa de Preautorización de Vitalia Salud EPS
FUENTES: {chunk}"""


def cartas_forzadas(cn, afiliado, solicitud, proc, r, vigencia_desde, codigos):
    """Devuelve la lista de casos X ya evaluados por el guardrail de salida."""
    fragmentos = recuperacion.fragmentos_de(r.fundamentos)
    fr = fragmentos[0]
    chunk = fr.chunk_id
    # Un tramo real de la cláusula, cortado en un espacio para no partir palabra.
    # Sale del **cuerpo**, no del `texto_literal` completo: ese empieza por la
    # ruta de títulos, y desde que O1 dejó de aceptar títulos como cita, tomar los
    # primeros 140 caracteres del fragmento produciría una carta base que falla.
    cita = recuperacion.cuerpo_citable(fr).strip()[:140].rsplit(" ", 1)[0]
    copago = f"S/ {r.copago_pen:,.2f}".replace(",", " ") if r.copago_pen else "S/ 0.00"
    base = CUERPO_OK.format(nombre=afiliado["nombre"], procedimiento=proc["descripcion"],
                            codigo=proc["codigo"], copago=copago, cita=cita, chunk=chunk)

    casos = [
        {"id": "X1", "control": "O3",
         "defecto": "la carta afirma un copago distinto del que calculó el motor",
         "por_que_importa": "el afiliado llega a la clínica con un número que nadie va a respetar; "
                            "es el reclamo de S/ 340 del caso de negocio",
         "cuerpo": base.replace(copago, "S/ 640.00")},
        {"id": "X2", "control": "O1",
         "defecto": "la carta presenta como cita textual un texto que no está en ningún fragmento",
         "por_que_importa": "una cláusula inventada en una carta de preautorización es "
                            "exactamente lo que R2 existe para impedir",
         "cuerpo": base.replace(cita, "el copago se reduce a la mitad cuando el afiliado "
                                      "tiene más de un año de antigüedad")},
        {"id": "X3", "control": "O6",
         "defecto": "la carta nombra un código de procedimiento que no existe en el catálogo",
         "por_que_importa": "el prestador factura contra el código de la carta",
         "cuerpo": base.replace(proc["codigo"], "PRC-9999")},
        {"id": "X4", "control": "O6",
         "defecto": "la carta declara en FUENTES un identificador que no estuvo en el contexto",
         "por_que_importa": "es el identificador con el que un fiscalizador va al documento, "
                            "y se midió en el Carril 0 que el modelo llega a firmar fuentes inventadas",
         "cuerpo": base.replace(f"FUENTES: {chunk}",
                                f"FUENTES: {chunk}, deducibles_y_copagos-v2026_09-c99")},
        {"id": "X5", "control": "O1",
         "defecto": "la carta cita bien el principio de la cláusula y le cambia el final",
         "por_que_importa": "es el fallo que una revisión humana no ve: parece la cláusula correcta",
         "cuerpo": base.replace(cita, cita[:70] + " y no admite excepción alguna")},
        {"id": "X8", "control": "O1",
         "defecto": "la carta no cita ninguna cláusula: resuelve «según la política vigente»",
         "por_que_importa": "es el defecto que el propio MVP produjo y que O1 aprobaba por vacío, "
                            "porque «las 0 citas coinciden» es trivialmente cierto",
         "cuerpo": base.replace(f"según la política vigente:\n«{cita}».",
                                "conforme a lo establecido en la política vigente.")},
        {"id": "X9", "control": "O1",
         "defecto": "la carta entrecomilla la ruta de títulos del fragmento en vez de la cláusula",
         "por_que_importa": "es la cita más fácil de producir —está en la primera línea de todos "
                            "los fragmentos— y no sustenta nada: un título dice dónde está la "
                            "norma, no qué ordena. Lo produjo el modelo en la primera corrida real",
         "cuerpo": base.replace(cita, fr.jerarquia)},
        {"id": "X10", "control": "O3",
         "defecto": "la carta explica el desglose: copago S/ 1,210.00 con deducible de S/ 600.00",
         "es_control_negativo": True,
         "por_que_importa": "el control tiene que dejar pasar los importes que el motor sí calculó; "
                            "una carta que da el resultado sin la aritmética es la carta que el "
                            "afiliado no entiende hoy",
         "cuerpo": base.replace(
             f"El copago que le corresponde asumir es de {copago}",
             f"El copago que le corresponde asumir es de {copago}, del que "
             f"S/ {r.copago_desglose['deducible']:,.2f} corresponden al deducible anual de su plan")},
        {"id": "X11", "control": "O1",
         "defecto": "la carta entrecomilla una palabra corriente además de citar la cláusula",
         "es_control_negativo": True,
         "por_que_importa": "lo produjo una carta real del MVP. La expresión que recorta las "
                            "citas abría con una clase de comillas y cerraba con otra sin "
                            "emparejarlas, así que la comilla recta de una palabra del cuerpo "
                            "se casaba con el «»» de la cita verdadera y fabricaba un tramo "
                            "que no está en ningún fragmento. O1 lo reprobaba con razón —ese "
                            "texto no existe— y bloqueaba una carta correcta: el control "
                            "acertaba y el insumo mentía",
         "cuerpo": base.replace(
             "ha sido autorizada.",
             'ha sido autorizada. Su afiliación figura en estado "activo".')},
    ]

    filas = []
    for c in casos:
        e = emision_e4.redactar(
            cn, afiliado, solicitud, proc, r, "auto",
            codigos_validos=codigos, version_vigente=config.VERSION_ID,
            vigencia_desde=vigencia_desde, fecha_solicitud=HOY,
            cuerpo_forzado=c["cuerpo"])
        bloqueantes = [k["codigo"] for k in e.controles if not k["paso"]]
        # Un control negativo mide lo contrario: la carta es correcta y el control
        # tiene que **dejarla pasar**. Sin al menos uno de estos, «seis controles
        # que bloquean» no distingue un guardrail que discrimina de uno que
        # rechaza todo, y esa distinción es la que decide si la mesa lo usa.
        if c.get("es_control_negativo"):
            ok = e.aprobada and not bloqueantes
        else:
            ok = c["control"] in bloqueantes and not e.aprobada
        filas.append({**c, "cuerpo": c["cuerpo"], "aprobada": e.aprobada,
                      "controles_que_bloquearon": bloqueantes,
                      "detalle": next((k["detalle"] for k in e.controles
                                       if k["codigo"] == c["control"]), ""),
                      "detectado": ok})
        etiqueta = "debe pasar" if c.get("es_control_negativo") else "debe bloquear"
        print(f"  {'OK  ' if ok else 'FALLA'} {c['id']} · {c['control']} · {etiqueta} · "
              f"bloquearon {bloqueantes or '—'}")

    # X6 · la política avanzó a v2026_10 y la carta sigue citando v2026_09. No se
    # construye un cuerpo distinto: el mismo texto correcto deja de serlo cuando
    # cambia la versión vigente, y ese es el punto de O2.
    e = emision_e4.redactar(
        cn, afiliado, solicitud, proc, r, "auto",
        codigos_validos=codigos, version_vigente="v2026_10",
        vigencia_desde=dt.date(2026, 10, 1), fecha_solicitud=HOY,
        cuerpo_forzado=base)
    bloq = [k["codigo"] for k in e.controles if not k["paso"]]
    ok6 = "O2" in bloq
    filas.append({"id": "X6", "control": "O2",
                  "defecto": "la carta cita v2026_09 cuando la versión vigente es v2026_10",
                  "por_que_importa": "una cita correcta de una norma derogada es una cita falsa "
                                     "con otro nombre; es lo que ADR-21 y el alias resuelven",
                  "aprobada": e.aprobada, "controles_que_bloquearon": bloq,
                  "detalle": next((k["detalle"] for k in e.controles if k["codigo"] == "O2"), ""),
                  "detectado": ok6})
    print(f"  {'OK  ' if ok6 else 'FALLA'} X6 · O2 · bloquearon {bloq or '—'}")

    # X7 · O4 se verifica sobre el control y no sobre una carta: `tipificar` nunca
    # devuelve `niega_necesidad_medica` en el MVP, precisamente porque el sistema
    # no niega por necesidad médica (ADR-10). El control existe para el día en que
    # un médico auditor firme desde el tablero, y se demuestra en ese nivel.
    sin_firma = gs.o4_firma_si_niega("niega_necesidad_medica", None)
    con_firma = gs.o4_firma_si_niega("niega_necesidad_medica", "FIR-000123")
    ok7 = not sin_firma.paso and con_firma.paso
    filas.append({"id": "X7", "control": "O4",
                  "defecto": "negación por necesidad médica sin firma de médico colegiado",
                  "por_que_importa": "R3: es la única regla del diseño que además está como "
                                     "CHECK en la base, y el control la detiene antes del INSERT",
                  "aprobada": False, "controles_que_bloquearon": ["O4"] if not sin_firma.paso else [],
                  "detalle": f"sin firma → {sin_firma.detalle} · con firma → {con_firma.detalle}",
                  "detectado": ok7, "nivel": "control, no carta"})
    print(f"  {'OK  ' if ok7 else 'FALLA'} X7 · O4 · verificado sobre el control")

    return filas


def limpiar(cn) -> None:
    """Deja las tablas de la plataforma vacías antes de correr.

    La bitácora es append-only por regla —ni UPDATE ni DELETE— y eso es correcto
    en operación. Para una prueba reproducible hace falta partir de cero, y el
    único camino que las reglas dejan abierto es TRUNCATE. Se hace aquí, en la
    prueba, y nunca en el flujo: `carril1` no borra nada.

    `core_*`, los catálogos y `politica_version` no se tocan: son el dato que la
    plataforma lee y no administra (ADR-18).
    """
    with cn.cursor() as cur:
        cur.execute("TRUNCATE solicitud, metrica_costo, evaluacion_guardrail CASCADE")
    cn.commit()


def main() -> int:
    config.configurar_consola()
    cn = config.conexion_pg()
    limpiar(cn)

    print("\nG · Fundamentos del motor contra el corpus vigente")
    print("-" * 78)
    fundamentos, fallos_fund = guarda_fundamentos()

    print("\nC · Expedientes de extremo a extremo (E1 → E2 → E3 → E4)")
    print("-" * 78)
    filas, fallos = [], fallos_fund
    for caso in CASOS:
        exp = carril1.procesar(cn, caso["texto"], hoy=HOY)
        ok = (exp.ruta == caso["espera_ruta"]
              and exp.emision.get("tipo") == caso["espera_tipo"]
              and exp.estado_final == caso["espera_estado"])
        if "espera_copago" in caso:
            ok = ok and (exp.adjudicacion.get("copago_pen") is not None
                         and Decimal(str(exp.adjudicacion["copago_pen"]))
                         == caso["espera_copago"])
        if not ok:
            fallos += 1
        bloq = [c["codigo"] for c in exp.emision.get("controles", []) if not c["paso"]]
        filas.append({**{k: v for k, v in caso.items() if k != "texto"},
                      "texto_recibido": caso["texto"],
                      "espera_copago": str(caso.get("espera_copago", "")),
                      "resultado": exp.como_dict(), "correcto": ok,
                      "controles_que_bloquearon": bloq})
        print(f"  {'OK  ' if ok else 'FALLA'} {caso['id']} · ruta {exp.ruta or '—'} · "
              f"carta {exp.emision.get('tipo') or '—'} · estado {exp.estado_final or '—'} · "
              f"{exp.latencia_ms} ms · US$ {exp.costo_usd:.6f}")
        if not exp.abierto:
            print(f"        expediente no abierto: {exp.motivo_no_abierto}")
            for c in exp.extraccion.get("campos", []):
                print(f"        {c['campo']:22} {str(c['valor'])[:40]:42} "
                      f"conf {c['confianza']}  {'✓' if c['validado_catalogo'] else '✗ ' + c['nota']}")
        for c in exp.emision.get("controles", []):
            print(f"        {c['codigo']} {'✓' if c['paso'] else '✗'} {c['detalle'][:88]}")

    # Idempotencia: el prestador reenvía el mismo correo. Se reenvía el primer
    # expediente que efectivamente se abrió; uno que no llegó a abrirse no tiene
    # con qué chocar y probaría otra cosa.
    abierto = next((f for f in filas if f["resultado"]["solicitud_id"]), None)
    if abierto is None:
        print("  FALLA ningún expediente se abrió: no hay idempotencia que probar")
        cn.close()
        return 1
    original = CASOS[[f["id"] for f in filas].index(abierto["id"])]["texto"]
    repetido = carril1.procesar(cn, original, hoy=HOY)
    idem_ok = repetido.duplicada and repetido.solicitud_id == abierto["resultado"]["solicitud_id"]
    if not idem_ok:
        fallos += 1
    print(f"  {'OK  ' if idem_ok else 'FALLA'} reenvío del mismo expediente → "
          f"{'devuelve el mismo, no reprocesa' if idem_ok else 'abrió un expediente duplicado'}")

    print("\nX · Cartas construidas para fallar (banco del guardrail de salida)")
    print("-" * 78)
    with cn.cursor() as cur:
        cur.execute("SELECT vigencia_desde FROM politica_version WHERE version_id = %s",
                    (config.VERSION_ID,))
        vigencia_desde = cur.fetchone()[0]
    afiliado, solicitud, proc, r = _contexto_del_banco(cn)
    forzadas = cartas_forzadas(cn, afiliado, solicitud, proc, r, vigencia_desde,
                               carril1._codigos_del_catalogo(cn))
    fallos += sum(1 for f in forzadas if not f["detectado"])

    # --- Trazas y costo, leídos de la base y no del proceso -----------------
    with cn.cursor() as cur:
        cur.execute("SELECT span, count(*), sum(costo_usd), max(latencia_ms) "
                    "FROM metrica_costo GROUP BY span ORDER BY span")
        costo_por_span = [{"span": s, "llamadas": n, "costo_usd": float(c or 0),
                           "latencia_max_ms": lm} for s, n, c, lm in cur.fetchall()]
        cur.execute("SELECT count(*) FROM evento_estado")
        eventos = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM cita WHERE verificada_literal")
        citas_ok = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM carta")
        cartas = cur.fetchone()[0]

    total_usd = sum(c["costo_usd"] for c in costo_por_span)
    por_solicitud_pen = total_usd / max(len(CASOS), 1) * 3.75

    resumen = {
        "fecha": HOY.isoformat(),
        "version_politica": config.VERSION_ID,
        "fundamentos_del_motor": fundamentos,
        "fundamentos_sin_resolver": fallos_fund,
        "casos": filas,
        "idempotencia_ok": idem_ok,
        "cartas_forzadas": forzadas,
        "controles_ejercitados": sorted({f["control"] for f in forzadas}),
        "eventos_de_estado": eventos,
        "citas_verificadas_en_base": citas_ok,
        "cartas_emitidas": cartas,
        "costo_por_span": costo_por_span,
        "costo_usd_total": round(total_usd, 6),
        "costo_pen_por_solicitud": round(por_solicitud_pen, 4),
        "fallos": fallos,
    }
    config.EVIDENCIAS_DIR.mkdir(exist_ok=True)
    destino = config.EVIDENCIAS_DIR / "E03_carril1_e1_a_e4.json"
    destino.write_text(json.dumps(resumen, ensure_ascii=False, indent=2, default=str),
                       encoding="utf-8")

    print(f"\n{'=' * 78}")
    print(f"  fundamentos que no resuelven . {fallos_fund} (debe ser 0)")
    print(f"  controles ejercitados ........ {', '.join(resumen['controles_ejercitados'])}")
    print(f"  eventos de estado ............ {eventos}")
    print(f"  citas verificadas en base .... {citas_ok}")
    print(f"  cartas emitidas .............. {cartas} (solo el carril auto emite)")
    print(f"  costo total .................. US$ {total_usd:.6f}"
          f"   ≈ S/ {por_solicitud_pen:.4f} por solicitud")
    for c in costo_por_span:
        print(f"      {c['span']:14} {c['llamadas']:2} llamada(s)  "
              f"US$ {c['costo_usd']:.6f}  máx {c['latencia_max_ms']} ms")
    print(f"  evidencia .................... {destino.name}")
    print(f"  fallos ....................... {fallos}")
    cn.close()
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
