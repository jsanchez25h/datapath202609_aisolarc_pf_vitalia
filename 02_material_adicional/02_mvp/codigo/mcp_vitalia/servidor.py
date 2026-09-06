"""Servidor MCP de Vitalia · el sistema expuesto a un cliente que no es nuestro.

    cliente MCP  →  herramienta (nombre estable)
                      → registro: resuelve la versión `latest`
                      → cadena PRE   G1 ámbito · G2 presupuesto · G3 guardrail
                      → skill
                      → cadena POST  G4 O1/O2 · G5 O5 · G6 traza y costo
                    ←  respuesta

La herramienta que ve el cliente es un **nombre**; la versión se resuelve en
cada llamada. Esa indirección de una línea es lo que hace que publicar una
versión nueva y marcarla `latest` cambie el comportamiento sin reiniciar el
proceso ni tocar el cliente.

Modos de arranque:

    python -m mcp_vitalia.servidor                 stdio, completo
    python -m mcp_vitalia.servidor --solo-lectura  stdio, sin skills que escriban

El modo solo lectura es el de la defensa. No es un permiso de base de datos: es
el gancho G1, que corta antes de ejecutar cualquier skill marcada `escribe`. La
única marcada así es `preparar_subsanacion`, y lo está porque gasta tokens
contra la cuenta y deja fila de costo atribuida a un expediente — «no gastes ni
cambies», no solo «no cambies».
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from functools import lru_cache
from pathlib import Path

if __package__ in (None, ""):                       # ejecución directa del archivo
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server.fastmcp import FastMCP

from comun import config
from mcp_vitalia import ganchos
from mcp_vitalia.registro import REGISTRO
import mcp_vitalia.skills  # noqa: F401  — publica las skills al importarse

SOLO_LECTURA = "--solo-lectura" in sys.argv

servidor = FastMCP("vitalia-preautorizacion")


class _Cn:
    """Una conexión por llamada, igual que en la API.

    Neon corta las conexiones ociosas, y un servidor MCP pasa la mayor parte de
    su vida ocioso esperando al cliente: un pool de larga vida aquí sería un
    pool de conexiones muertas que fallan en la primera herramienta que se use
    después de una pausa.
    """

    def __enter__(self):
        self.cn = config.conexion_pg()
        return self.cn

    def __exit__(self, *a):
        try:
            self.cn.rollback()
        finally:
            self.cn.close()


@lru_cache(maxsize=1)
def _vigencia_desde() -> dt.date:
    """Desde cuándo rige la versión de política que la configuración declara.

    Lo necesita O2 en el gancho G4. Se lee de `politica_version` y no se asume
    «hoy»: dar por vigente lo que se está evaluando convierte O2 en un control
    que siempre aprueba, que es la forma más silenciosa de que un control deje
    de existir.
    """
    with _Cn() as cn, cn.cursor() as cur:
        cur.execute("SELECT vigencia_desde FROM politica_version WHERE version_id = %s",
                    (config.VERSION_ID,))
        f = cur.fetchone()
    return f[0] if f else dt.date.today()


def invocar(nombre: str, argumentos: dict) -> dict:
    """El único camino de entrada a una skill. Todo lo demás son envoltorios."""
    skill = REGISTRO.obtener(nombre)
    with _Cn() as cn:
        ctx = ganchos.Contexto(
            skill=skill, argumentos=dict(argumentos), cn=cn,
            solo_lectura=SOLO_LECTURA,
            texto_entrada=str(argumentos.get(skill.campo_texto_libre, ""))
            if skill.campo_texto_libre else "")
        ctx.anotaciones["vigencia_desde"] = _vigencia_desde()

        ganchos.PRE.correr(ctx)
        if not ctx.abortado:
            try:
                ctx.salida = skill.ejecutar(**ctx.argumentos, cn=cn)
            except Exception as exc:                # noqa: BLE001
                # El error no se propaga como excepción MCP: se devuelve como
                # dato. Un cliente que recibe una traza de Python no puede hacer
                # nada con ella, y el gancho G6 tiene que correr igual para que
                # la llamada fallida quede en la traza.
                ctx.salida = {"ok": False, "error": type(exc).__name__,
                              "detalle": str(exc)[:300]}
        ganchos.POST.correr(ctx)

    salida = dict(ctx.salida or {})
    salida["_skill"] = skill.ref
    salida["_ganchos"] = ctx.anotaciones.get("ganchos", [])
    if ctx.abortado:
        salida["_abortado_en"] = ctx.motivo_aborto
    if "guardrail_salida" in ctx.anotaciones:
        salida["_controles_frontera"] = ctx.anotaciones["guardrail_salida"]
    if "pii_enmascarada" in ctx.anotaciones:
        salida["_pii_enmascarada"] = ctx.anotaciones["pii_enmascarada"]
    # Los campos de servicio no salen al cliente: son para la evidencia.
    for interno in ("_costo", "_costo_anotado_aguas_abajo", "_pii"):
        salida.pop(interno, None)
    return salida


# --------------------------------------------------------------------------
# Las cuatro herramientas. La firma es el `args_schema`; el docstring es el
# contrato que lee el modelo, y se toma del registro para que no pueda quedar
# desincronizado con la skill que de verdad se ejecuta.
# --------------------------------------------------------------------------

@servidor.tool()
def consultar_politica(consulta: str, plan: str | None = None) -> dict:
    return invocar("consultar_politica", {"consulta": consulta, "plan": plan})


@servidor.tool()
def simular_cobertura(afiliado_ref: str, procedimiento_codigo: str,
                      documentos_presentes: list[str] | None = None,
                      fecha_prevista: str | None = None) -> dict:
    return invocar("simular_cobertura", {
        "afiliado_ref": afiliado_ref, "procedimiento_codigo": procedimiento_codigo,
        "documentos_presentes": documentos_presentes or [],
        "fecha_prevista": fecha_prevista})


@servidor.tool()
def estado_expediente(solicitud_id: str) -> dict:
    return invocar("estado_expediente", {"solicitud_id": solicitud_id})


@servidor.tool()
def preparar_subsanacion(solicitud_id: str) -> dict:
    return invocar("preparar_subsanacion", {"solicitud_id": solicitud_id})


for _fn in (consultar_politica, simular_cobertura, estado_expediente,
            preparar_subsanacion):
    _fn.__doc__ = REGISTRO.obtener(_fn.__name__).descripcion


# --------------------------------------------------------------------------
# Recursos · lo que el cliente puede leer sin invocar nada
# --------------------------------------------------------------------------

@servidor.resource("vitalia://skills")
def recurso_skills() -> str:
    """Catálogo de skills publicadas, con sus versiones y cuál está activa."""
    return json.dumps({"version_politica": config.VERSION_ID,
                       "solo_lectura": SOLO_LECTURA,
                       "skills": REGISTRO.catalogo()},
                      ensure_ascii=False, indent=2)


@servidor.resource("vitalia://trazas")
def recurso_trazas() -> str:
    """Las últimas llamadas de esta sesión: skill, versión, nivel, costo y desenlace."""
    return json.dumps(list(ganchos.TRAZAS), ensure_ascii=False, indent=2)


@servidor.resource("vitalia://disyuntores")
def recurso_disyuntores() -> str:
    """Estado de los circuit breakers por dependencia externa."""
    from mcp_vitalia import resiliencia
    return json.dumps({k: d.como_dict() for k, d in resiliencia.DISYUNTORES.items()},
                      ensure_ascii=False, indent=2)


if __name__ == "__main__":
    config.configurar_consola()
    servidor.run()
