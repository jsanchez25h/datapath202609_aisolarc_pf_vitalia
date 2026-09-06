"""Motor gestionado del guardrail: Model Armor de Google Cloud — sesión 09.

Es la alternativa administrada a las capas propias. Con
`GUARDRAIL_ENGINE=model_armor`, una sola llamada a la plantilla
`vitalia-preauth` sustituye a **cinco** de las ocho capas locales:

    2  inyección de prompt   ->  pi_and_jailbreak
    3  toxicidad             ->  rai (dangerous, harassment, hate_speech, sexually_explicit)
    6  URL                   ->  malicious_uris
    7  Prompt Guard 2        ->  pi_and_jailbreak
    8  Llama Guard           ->  rai + csam

Lo que **no** sustituye, y por eso sigue corriendo siempre:

    1  secretos    una clave `sk-proj-…` en el texto es un incidente nuestro, no
                   una categoría de daño universal.
    4  dominio     «niega sin firma», «aplica la política del año pasado» o
                   «no cobres el copago» no son ataques para nadie más que para
                   Vitalia: son los invariantes R1/R3 y los vetos del diseño.
                   Ningún proveedor gestionado conoce nuestras reglas.
    5  PII         la plantilla trae `sdp` en modo básico, que **inspecciona**
                   pero no enmascara; la anonimización que exige el diseño la
                   sigue haciendo Presidio.

Si el servicio no responde dentro de `MODEL_ARMOR_TIMEOUT_SECONDS`, la capa se
marca `omitida` y el orquestador vuelve a las cinco capas locales. No se
reporta como capa aprobada: una capa que no se ejecutó no protege nada.

Credenciales: se usan las de aplicación por defecto (ADC). Si están caducadas
—pasa a menudo en una máquina de laboratorio— se cae al token de la sesión de
`gcloud`, que es la misma cuenta y el mismo proyecto. Nada de esto guarda
claves en disco.
"""

from __future__ import annotations

import os
import subprocess
import time
from functools import lru_cache

from comun import config
from guardrails.entrada import (BLOQUEAR, CONFIRMAR, PERMITIR, TRANSFORMAR,  # noqa: F401
                                Hallazgo)

CAPA = "model_armor"

PROYECTO = config.var("MODEL_ARMOR_PROJECT_ID")
UBICACION = config.var("MODEL_ARMOR_LOCATION", "us-central1")
PLANTILLA = config.var("MODEL_ARMOR_TEMPLATE_ID")
TIMEOUT = float(config.var("MODEL_ARMOR_TIMEOUT_SECONDS", "3"))

# El mismo aislamiento de cuenta que usa el resto del proyecto: sin esto,
# gcloud y ADC leerían la otra configuración de la máquina.
CONFIG_GCLOUD = config.RAIZ_FASE2.parents[3] / ".gcp"

# Los filtros que bloquean y los que solo marcan. `sdp` marca porque la capa 5
# local ya enmascara, y porque tirar una solicitud por traer un DNI convertiría
# el guardrail en un obstáculo administrativo (veto V3).
BLOQUEANTES = ("pi_and_jailbreak", "rai", "malicious_uris", "csam")


def _credenciales():
    """ADC si sirven; si no, el token de la sesión de gcloud."""
    entorno = dict(os.environ, CLOUDSDK_CONFIG=str(CONFIG_GCLOUD))
    os.environ.setdefault("CLOUDSDK_CONFIG", str(CONFIG_GCLOUD))
    try:
        import google.auth
        from google.auth.transport.requests import Request
        cred, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"])
        cred.refresh(Request())
        return cred
    except Exception:
        from google.oauth2.credentials import Credentials
        r = subprocess.run(["gcloud.cmd", "auth", "print-access-token"],
                           capture_output=True, text=True, env=entorno, timeout=30)
        if r.returncode != 0:
            raise RuntimeError(f"sin credenciales para Model Armor: {r.stderr.strip()[-200:]}")
        return Credentials(token=r.stdout.strip())


@lru_cache(maxsize=1)
def _cliente():
    from google.api_core.client_options import ClientOptions
    from google.cloud import modelarmor_v1
    # El endpoint es **regional**. Contra el global la misma cuenta recibe
    # PERMISSION_DENIED aunque la API esté habilitada, y el error no lo dice.
    return modelarmor_v1.ModelArmorClient(
        credentials=_credenciales(),
        client_options=ClientOptions(
            api_endpoint=f"modelarmor.{UBICACION}.rep.googleapis.com"))


def ruta_plantilla() -> str:
    return f"projects/{PROYECTO}/locations/{UBICACION}/templates/{PLANTILLA}"


def _lee(resultado) -> tuple[list[str], str | None, float | None]:
    """Traduce la respuesta a (categorías que dieron positivo, texto anonimizado, confianza)."""
    from google.cloud import modelarmor_v1 as ma
    coincidencias: list[str] = []
    texto_sdp = None
    confianza = None
    for clave, fr in resultado.filter_results.items():
        cual = fr._pb.WhichOneof("filter_result")
        detalle = getattr(fr, cual) if cual else None
        if detalle is None:
            continue
        if getattr(detalle, "match_state", None) != ma.FilterMatchState.MATCH_FOUND:
            continue
        if clave == "rai":
            for tipo, tr in detalle.rai_filter_type_results.items():
                if tr.match_state == ma.FilterMatchState.MATCH_FOUND:
                    coincidencias.append(f"rai:{tipo}")
        else:
            coincidencias.append(clave)
        if clave == "sdp":
            di = getattr(detalle, "deidentify_result", None)
            if di is not None and getattr(di, "data", None) and di.data.text:
                texto_sdp = di.data.text
    return coincidencias, texto_sdp, confianza


def capa_model_armor(texto: str) -> tuple[Hallazgo, str]:
    """Una llamada, un veredicto. Devuelve `(hallazgo, texto)` como la capa 5,
    porque `sdp` en modo avanzado puede devolver el texto ya enmascarado."""
    if not PROYECTO or not PLANTILLA:
        return (Hallazgo(CAPA, PERMITIR, "sin_configurar", None,
                         "faltan MODEL_ARMOR_PROJECT_ID o MODEL_ARMOR_TEMPLATE_ID",
                         omitida=True), texto)
    t0 = time.time()
    try:
        from google.cloud import modelarmor_v1 as ma
        r = _cliente().sanitize_user_prompt(
            request=ma.SanitizeUserPromptRequest(
                name=ruta_plantilla(),
                user_prompt_data=ma.DataItem(text=texto)),
            timeout=TIMEOUT)
        res = r.sanitization_result
        if res.invocation_result != ma.InvocationResult.SUCCESS:
            raise RuntimeError(f"invocation_result={res.invocation_result.name}")
    except Exception as e:
        # A diferencia de las capas 7 y 8, aquí no se hace fail-close: se marca
        # omitida y el orquestador ejecuta las cinco capas locales que esta
        # sustituía. Bloquear sería más seguro y más caro; caer a lo propio es
        # igual de seguro, porque lo propio es lo que había antes.
        return (Hallazgo(CAPA, PERMITIR, "capa_no_disponible", None,
                         f"{type(e).__name__}: {str(e)[:160]} — se cae a las capas locales",
                         int((time.time() - t0) * 1000), omitida=True), texto)

    ms = int((time.time() - t0) * 1000)
    coincidencias, texto_sdp, confianza = _lee(res)
    actual = texto_sdp or texto
    if not coincidencias:
        return (Hallazgo(CAPA, PERMITIR, "sin_coincidencias", confianza,
                         f"plantilla {PLANTILLA}: NO_MATCH_FOUND", ms), actual)

    bloquea = [c for c in coincidencias if c.split(":")[0] in BLOQUEANTES]
    if bloquea:
        return (Hallazgo(CAPA, BLOQUEAR, ",".join(bloquea), confianza,
                         f"plantilla {PLANTILLA}: MATCH_FOUND en {', '.join(coincidencias)}",
                         ms), actual)
    decision = TRANSFORMAR if texto_sdp else CONFIRMAR
    return (Hallazgo(CAPA, decision, ",".join(coincidencias), confianza,
                     f"plantilla {PLANTILLA}: {', '.join(coincidencias)} "
                     f"(la capa 5 local es la que anonimiza)", ms), actual)
