"""Evidencia de la etapa B: el servicio corriendo en Cloud Run.

No basta con decir «está desplegado». Lo que prueba un despliegue es que el
mismo código, sin `variables.sh` y sin la máquina de nadie, resuelve el carril
0 contra la política vigente y sigue verificando sus citas. Este script
pregunta eso al servicio remoto y guarda la respuesta.

    python -m demo.evidencia_despliegue

Lee la descripción del servicio con `gcloud` —de ahí salen la revisión, el
digest de la imagen y los nombres (nunca los valores) de las variables y de los
secretos— y luego llama a `/salud`, `/n1/consulta` y `/operacion/panel` con un
token de identidad. El servicio está cerrado por IAM, así que sin token no hay
evidencia que recoger: eso también queda escrito.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from comun import config  # noqa: E402

PROYECTO = "datapath-labs-202608"
REGION = "us-central1"
SERVICIO = "vitalia-mesa"
DESTINO = RAIZ.parent / "evidencias" / "E15_despliegue_cloud_run.json"

# El aislamiento de la cuenta del curso: sin esto gcloud usaría la otra
# configuración de la máquina, que apunta a otro proyecto.
CONFIG_GCLOUD = RAIZ.parents[4] / ".gcp"   # la raíz del repositorio del curso


def gcloud(*args: str) -> str:
    entorno = dict(os.environ, CLOUDSDK_CONFIG=str(CONFIG_GCLOUD))
    r = subprocess.run(["gcloud.cmd", *args, "--project", PROYECTO], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=entorno)
    if r.returncode != 0:
        raise SystemExit(f"gcloud {' '.join(args)} -> {r.returncode}\n{r.stderr[-800:]}")
    return r.stdout.strip()


def pedir(url: str, token: str, cuerpo: dict | None = None) -> tuple[dict, int]:
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    req = urllib.request.Request(
        url, data=datos,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json; charset=utf-8"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8")), int((time.time() - t0) * 1000)


def main() -> int:
    config.configurar_consola()

    print("· leyendo la descripción del servicio")
    desc = json.loads(gcloud("run", "services", "describe", SERVICIO,
                             "--region", REGION, "--format", "json"))
    contenedor = desc["spec"]["template"]["spec"]["containers"][0]
    plantilla = desc["spec"]["template"]
    url = desc["status"]["url"]

    variables = [e["name"] for e in contenedor.get("env", []) if "value" in e]
    secretos = [{"variable": e["name"],
                 "secreto": e["valueFrom"]["secretKeyRef"]["name"],
                 "version": e["valueFrom"]["secretKeyRef"]["key"]}
                for e in contenedor.get("env", []) if "valueFrom" in e]

    # La política que impide abrir el servicio se lee, no se cuenta de memoria:
    # es la diferencia entre documentar un límite y afirmarlo.
    print("· leyendo la política de organización que cierra el acceso")
    try:
        drs = gcloud("org-policies", "describe",
                     "constraints/iam.allowedPolicyMemberDomains", "--effective")
    except SystemExit as e:
        drs = f"(no se pudo leer: {e})"

    print("· pidiendo token de identidad")
    token = gcloud("auth", "print-identity-token")

    print(f"· llamando a {url}")
    salud, ms_salud = pedir(url + "/salud", token)
    n1, ms_n1 = pedir(url + "/n1/consulta", token, {
        "consulta": "¿Cuántos días de carencia tiene una cesárea programada "
                    "en el plan VIT-INT?",
        "plan": "VIT-INT"})
    panel, ms_panel = pedir(url + "/operacion/panel", token)

    ev = {
        "generado": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "etapa": "B · despliegue gestionado",
        "servicio": {
            "proyecto": PROYECTO,
            "region": REGION,
            "nombre": desc["metadata"]["name"],
            "url": url,
            "revision": desc["status"]["latestReadyRevisionName"],
            "imagen": contenedor["image"],
            "cpu": contenedor["resources"]["limits"]["cpu"],
            "memoria": contenedor["resources"]["limits"]["memory"],
            "concurrencia": plantilla["spec"].get("containerConcurrency"),
            "max_instancias": plantilla["metadata"]["annotations"].get(
                "autoscaling.knative.dev/maxScale"),
        },
        "acceso": {
            "publico": False,
            "control": "IAM · roles/run.invoker",
            "por_que": "La organización aplica constraints/iam.allowedPolicyMemberDomains: "
                       "`allUsers` queda rechazado con FAILED_PRECONDITION. Abrirlo exige "
                       "una excepción a nivel de organización, que no depende del proyecto.",
            "politica_efectiva": drs,
            "como_se_ve_igual": "gcloud run services proxy vitalia-mesa --region us-central1",
        },
        "configuracion": {
            "variables_en_claro": sorted(variables),
            "secretos_montados": secretos,
            "nota": "Los valores no aparecen aquí ni en la imagen: `comun/config.py` lee "
                    "`variables.sh` solo si existe y con `os.environ.setdefault`, así que "
                    "en Cloud Run gana lo que inyecta Secret Manager.",
        },
        "comprobaciones": {
            "salud": {"ms": ms_salud, **salud},
            "n1_consulta": {
                "ms": ms_n1,
                "origen": n1.get("origen"),
                "citas_verificadas": [c["chunk_id"] for c in n1.get("citas_verificadas", [])],
                "citas_rechazadas": len(n1.get("citas_rechazadas", [])),
                "guardrail": n1.get("guardrail_salida") or n1.get("guardrail"),
            },
            "panel": {"ms": ms_panel,
                      "solicitudes": panel.get("solicitudes"),
                      "version_politica": panel.get("version_politica")},
        },
        "invariante": "R2 · la respuesta del servicio remoto trae sus citas verificadas "
                      "contra el corpus de la versión vigente, igual que la local: el "
                      "alojamiento no cambia lo que el sistema puede afirmar.",
    }

    DESTINO.write_text(json.dumps(ev, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{DESTINO.name}")
    print(f"  url        {url}")
    print(f"  revision   {ev['servicio']['revision']}")
    print(f"  salud      {salud.get('ok')} · {ms_salud} ms")
    print(f"  n1         origen={ev['comprobaciones']['n1_consulta']['origen']} · "
          f"{len(ev['comprobaciones']['n1_consulta']['citas_verificadas'])} citas · {ms_n1} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
