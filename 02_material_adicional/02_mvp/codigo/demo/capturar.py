# -*- coding: utf-8 -*-
"""Rehace las capturas del Anexo K con el navegador, no con la mano.

    python -m demo.capturar              # las siete, contra 127.0.0.1:8088
    python -m demo.capturar P4a P4b      # solo algunas

Existe por el veto **V2**. Una captura obtenida pulsando tres botones en un
orden que nadie anotó no se rehace: se reconstruye de memoria, y entonces la
evidencia depende de que quien la hizo se acuerde. Aquí cada pantalla es una
URL y cada URL está escrita abajo, así que la imagen dice cómo se produjo.

Eso es también lo que obligó a que la interfaz enrutase por *hash*: sin
`#/expediente/SOL-…` no habría forma de pedirle a un navegador sin manos que
abriera la pantalla 4, y la pantalla 4 es la que hay que enseñar en la defensa.

**Los identificadores no se escriben aquí.** Se leen de la bandeja viva en el
momento de capturar: `SOL-…` cambia en cada repoblado, y una lista de ids fijos
en el código convierte la captura en algo que solo funciona el día que se
escribió. Se busca por *ruta* y *estado*, que es lo que la evidencia afirma.

Chrome en modo headless con `--virtual-time-budget`: el reloj del navegador
avanza solo cuando la red está quieta, así que el presupuesto se agota cuando la
página terminó de cargar y no cuando pasaron N segundos de pared. Es lo que
permite dar 90 s a la pantalla 2 —que espera un modelo— sin esperar 90 s en las
demás.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# El destino se puede cambiar sin tocar el código: las mismas evidencias tienen
# que poder rehacerse contra el servicio local y contra el de Cloud Run, y una
# captura que solo se puede repetir en una máquina no cumple el veto V2.
#     VITALIA_BASE=https://…run.app python -m demo.capturar
BASE = os.environ.get("VITALIA_BASE", "http://127.0.0.1:8088").rstrip("/")
DESTINO = RAIZ.parent / "evidencias" / "pantallas"

CHROME = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
]

# La pregunta de la pantalla 2 va en la URL. Es la misma que la demostración
# consulta al poblar, así que para cuando se captura ya está en el caché
# semántico: la captura sale en medio segundo y sin gastar un token, que es
# justo lo que la pantalla tiene que demostrar.
PREGUNTA_N1 = "¿Cuántos días de carencia tiene la cesárea programada en el plan VIT-INT?"


def _cromo() -> str:
    for c in CHROME:
        if c.exists():
            return str(c)
    hallado = shutil.which("chrome") or shutil.which("msedge")
    if hallado:
        return hallado
    raise SystemExit("no encuentro Chrome ni Edge; edita CHROME en demo/capturar.py")


def _api(ruta: str) -> dict:
    with urllib.request.urlopen(BASE + ruta, timeout=30) as r:
        return json.load(r)


def resolver_expedientes() -> dict[str, str]:
    """Qué `SOL-…` toca a cada captura, leído de la bandeja de ahora mismo.

    Si falta alguno, no se captura una pantalla vacía y se calla: se dice cuál
    falta. Una imagen que dice «no hay expedientes» dentro de un anexo que
    afirma que los hay es peor que una imagen que no está.
    """
    exps = _api("/solicitudes?limite=200")["expedientes"]
    por = lambda f: next((e["solicitud_id"] for e in exps if f(e)), None)  # noqa: E731
    elegidos = {
        # La 4a es un expediente que sigue esperando a una persona: es donde se
        # ve el ADR-10 —el borrador está escrito y no se emitió solo—.
        "P4a": por(lambda e: e["estado_actual"] == "hitl"),
        # La 4b es el mismo diseño con el ciclo cerrado: carta, firma y folio.
        "P4b": por(lambda e: e["estado_actual"] == "emitida"),
        # La 4c es la subsanación: el único agente del diseño, pidiendo lo que
        # falta en lugar de rechazar por falta de papeles.
        "P4c": por(lambda e: e["estado_actual"] == "agente"),
    }
    faltan = [k for k, v in elegidos.items() if not v]
    if faltan:
        print("aviso     sin expediente para " + ", ".join(faltan) +
              " -- corre `python -m demo.poblar` antes")
    return {k: v for k, v in elegidos.items() if v}


def pantallas(ids: dict[str, str]) -> list[tuple[str, str, int, int, int]]:
    """(nombre, ruta hash, ancho, alto, presupuesto de tiempo virtual en ms).

    Las alturas están ajustadas al contenido de cada pantalla. No es estética:
    una captura con 700 px de banda vacía debajo obliga a quien la mira a
    buscar dónde está lo que el anexo dice que enseña.
    """
    p = [
        ("P1_ingreso", "#/ingreso", 1440, 900, 15000),
        ("P2_consulta_n1", "#/n1/" + urllib.parse.quote(PREGUNTA_N1, safe=""),
         1440, 700, 90000),
        ("P3_bandeja", "#/bandeja", 1440, 1000, 20000),
    ]
    if "P4a" in ids:
        p.append(("P4a_expediente_pendiente", "#/expediente/" + ids["P4a"],
                  1440, 2150, 25000))
    if "P4b" in ids:
        p.append(("P4b_expediente_emitido", "#/expediente/" + ids["P4b"],
                  1440, 2100, 25000))
    if "P4c" in ids:
        p.append(("P4c_expediente_subsanacion", "#/expediente/" + ids["P4c"],
                  1440, 2050, 25000))
    p.append(("P5_panel", "#/panel", 1440, 900, 20000))
    return p


def main(argv: list[str]) -> int:
    cromo = _cromo()
    DESTINO.mkdir(parents=True, exist_ok=True)
    perfil = Path(__file__).resolve().parent / "_perfil_chrome"

    salud = _api("/salud")
    if not salud.get("ok"):
        raise SystemExit("el servicio responde pero alguna dependencia esta caida: "
                         + json.dumps(salud, ensure_ascii=False))

    ids = resolver_expedientes()
    filtro = {a.split("_")[0] for a in argv} or None
    hechas = []

    for nombre, hash_, ancho, alto, presupuesto in pantallas(ids):
        if filtro and nombre.split("_")[0] not in filtro:
            continue
        salida = DESTINO / (nombre + ".png")
        url = BASE + "/app/" + hash_
        t0 = time.time()
        subprocess.run(
            [cromo, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             "--no-first-run", "--no-default-browser-check",
             "--user-data-dir=" + str(perfil),
             "--force-device-scale-factor=1",
             "--window-size=%d,%d" % (ancho, alto),
             "--virtual-time-budget=%d" % presupuesto,
             "--screenshot=" + str(salida), url],
            check=True, capture_output=True, timeout=300)
        kb = salida.stat().st_size // 1024 if salida.exists() else 0
        hechas.append({"pantalla": nombre, "url": url,
                       "ventana": f"{ancho}x{alto}", "kb": kb})
        print(f"{nombre:<28} {kb:>5} kB  {time.time()-t0:5.1f}s  {hash_}")

    shutil.rmtree(perfil, ignore_errors=True)

    # Una corrida filtrada (`... P4b P4c`) no puede dejar un índice que solo
    # nombre dos pantallas: el índice describe la carpeta, y la carpeta sigue
    # teniendo siete. Se mezcla por nombre y las no rehechas conservan su ficha.
    indice = DESTINO / "INDICE.json"
    previas = []
    if filtro and indice.exists():
        previas = json.loads(indice.read_text(encoding="utf-8")).get("capturas", [])
    nombres = {h["pantalla"] for h in hechas}
    todas = hechas + [c for c in previas if c["pantalla"] not in nombres]
    todas.sort(key=lambda c: c["pantalla"])
    indice.write_text(json.dumps(
        {"generado": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "parcial": sorted(nombres) if filtro else None,
         "base": BASE, "version_politica": salud["version_politica"],
         "expedientes": ids, "capturas": todas},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nescrito   pantallas/INDICE.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
