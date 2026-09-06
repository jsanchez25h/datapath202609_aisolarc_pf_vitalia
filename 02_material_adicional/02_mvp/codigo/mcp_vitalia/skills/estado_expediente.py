"""Skill 3 · `estado_expediente` — la lectura del expediente, sin poder tocarlo.

Devuelve el estado, la ruta, la adjudicación determinista, las citas que se
verificaron, los borradores con su veredicto de guardrail, las cartas emitidas y
la bitácora de eventos. Es la pantalla 4 en forma de herramienta.

Dos decisiones que se ven en el retorno:

**El nombre del afiliado va dentro de `texto`, no en un campo propio.** No es
descuido de estructura: `texto` es uno de los campos que el gancho G5 enmascara
con O5, y al otro lado de este canal hay un agente, no el titular. La carta al
titular lleva su nombre porque es suya; la respuesta a una herramienta, no. El
campo estructurado que sí viaja es `afiliado_ref`, que identifica sin exponer.

**La bitácora viaja entera.** Se podría resumir a «último estado» y sería más
corto, pero el veto V2 pide que quien fiscalice pueda reconstruir el camino, y
un expediente que solo dice dónde está no permite explicar cómo llegó. Es
también lo que hace auditable que el sistema no negó solo: la bitácora enseña la
transición `hitl → E4` con el actor humano que la firmó.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from api import consultas
from mcp_vitalia.registro import Skill


class Argumentos(BaseModel):
    solicitud_id: str = Field(
        description="Identificador del expediente, con el formato SOL-cd8878b820aa.")


DESCRIPCION = """Devuelve el estado completo de un expediente de preautorización:
en qué etapa está, por qué ruta se enrutó, qué calculó el motor determinista,
qué cláusulas se citaron, si el guardrail de salida aprobó el borrador y qué
carta se emitió, con la bitácora de todos los cambios de estado.

Úsala cuando ya exista un expediente y se pregunte por él. Es de solo lectura:
no cambia el estado, no aprueba y no emite."""


def _corto(cadena: str | None, n: int = 240) -> str:
    if not cadena:
        return ""
    return cadena if len(cadena) <= n else cadena[:n].rstrip() + "…"


def _ejecutar(solicitud_id: str, *, cn=None) -> dict:
    if cn is None:
        return {"ok": False, "error": "sin_conexion",
                "detalle": "la skill necesita conexión a la base"}

    exp = consultas.expediente(cn, solicitud_id)
    if exp is None:
        return {"ok": False, "error": "expediente_inexistente",
                "detalle": f"no hay expediente «{solicitud_id}»"}

    adj = exp.get("adjudicacion") or {}
    borradores = exp.get("borradores") or []
    cartas = exp.get("cartas") or []

    return {
        "ok": True,
        "solicitud_id": exp["solicitud_id"],
        "afiliado_ref": exp["afiliado_ref"],
        "estado": exp["estado_actual"],
        "canal": exp["canal"],
        "procedimiento": {"codigo": exp["procedimiento_codigo"],
                          "descripcion": exp["procedimiento_desc"]},
        "dx_cie10": exp.get("dx_cie10"),
        # El texto que el gancho G5 enmascara. Es el único sitio del retorno
        # donde aparece un nombre propio, y aparece aquí a propósito.
        "texto": (f"Expediente {exp['solicitud_id']} de {exp['afiliado_nombre']} "
                  f"({exp['afiliado_ref']}), {exp['procedimiento_desc']}. "
                  f"Estado: {exp['estado_actual']}."),
        "adjudicacion": {
            # La asimetría que sostiene R1 sin necesidad de explicarla: la
            # adjudicación viene con `modelo` vacío y `determinista` en true; las
            # extracciones, más abajo, vienen con su modelo declarado.
            "determinista": adj.get("determinista"),
            "modelo": adj.get("modelo"),
            "elegible": adj.get("elegible"),
            "carencia_ok": adj.get("carencia_ok"),
            "carencia_dias_exigidos": adj.get("carencia_dias_exigidos"),
            "carencia_dias_afiliado": adj.get("carencia_dias_afiliado"),
            "cobertura": adj.get("cobertura"),
            "motivo": adj.get("motivo"),
            "copago_pen": adj.get("copago_pen"),
            "copago_desglose": adj.get("copago_desglose"),
            "ruta": adj.get("ruta"),
            "motivo_ruta": adj.get("motivo_ruta"),
        } if adj else None,
        "extraccion": [{"campo": e["campo"], "valor": e["valor"],
                        "confianza": e["confianza"],
                        "validado_catalogo": e["validado_catalogo"],
                        "modelo": e["modelo"]} for e in exp.get("extraccion") or []],
        "citas": [{"chunk_id": c["chunk_id"], "version_id": c["version_id"],
                   "articulo": c["articulo"],
                   "verificada_literal": c["verificada_literal"],
                   "texto": _corto(c["texto_literal"])}
                  for c in exp.get("citas") or []],
        "borradores": [{"borrador_id": b["borrador_id"], "tipo": b["tipo"],
                        "aprobada_guardrail": b["aprobada_guardrail"],
                        "controles": b["controles"], "modelo": b["modelo"],
                        "cuerpo": _corto(b["cuerpo"], 400)} for b in borradores],
        "cartas": [{"carta_id": c["carta_id"], "tipo": c["tipo"],
                    "firma_id": c["firma_id"], "copago_pen": c["copago_pen"],
                    "core_folio": c["core_folio"],
                    "emitida_en": str(c["emitida_en"])} for c in cartas],
        "bitacora": [{"desde": b["desde"], "hacia": b["hacia"],
                      "actor": b["actor"], "motivo": b["motivo"],
                      "ts": str(b["ts"])} for b in exp.get("bitacora") or []],
        "costo_usd_total": exp.get("costo_usd_total"),
        "nivel": "N0",
        # Lo que esta skill sabe que es dato personal, para que el gancho G5 lo
        # retire por igualdad y no dependa de que un detector lo reconozca. Es
        # campo de servicio: el servidor lo quita antes de responder.
        "_pii": [exp["afiliado_nombre"]],
    }


V1_0_0 = Skill(
    nombre="estado_expediente", version="1.0.0",
    descripcion=DESCRIPCION, esquema=Argumentos, ejecutar=_ejecutar,
    campo_texto_libre=None, escribe=False, cita_politica=False)
