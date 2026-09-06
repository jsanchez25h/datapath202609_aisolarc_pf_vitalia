"""Skill 2 · `simular_cobertura` — el motor determinista expuesto como herramienta.

Esta es la skill que hace visible el invariante **R1** en la superficie MCP.
Devuelve `determinista: true` y `modelo: null` porque no hay modelo: la carencia
es una resta de fechas, el copago es deducible pendiente más coaseguro sobre el
saldo, y la suficiencia documental es una diferencia de conjuntos. Un agente que
llame a esta herramienta obtiene el mismo número que obtendría la mesa, y lo
obtiene sin que nadie haya generado un token.

Tres cosas que **no** hace, y que no son omisiones:

- **No abre expediente.** Es una simulación; el expediente lo abre el canal de
  la mesa con la solicitud real. Un agente que pudiera abrir expedientes al
  consultar llenaría la bandeja de trámites que nadie pidió.
- **No niega.** Puede devolver `cobertura: "no_cubierto"`, que es una lectura de
  la tabla, y la ruta que le corresponde —`hitl`—, que es una instrucción de
  escalamiento. La negación la firma una persona (ADR-10), y por eso el campo
  se llama `ruta` y no `decision`.
- **No adivina el diagnóstico.** Valida el procedimiento contra el catálogo y
  nada más. Que no exista una tabla que relacione diagnóstico con procedimiento
  es la brecha 3 declarada en `E12`, y esta skill la hereda entera.

Las citas que devuelve no vienen de una búsqueda semántica sino de resolver los
fundamentos del motor por `(doc_id, articulo)` exacto. Una cláusula *parecida*
en una simulación de copago es una cita falsa.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from comun import motor_determinista as motor, recuperacion, repositorio as repo
from mcp_vitalia.registro import Skill

DOCUMENTOS_VALIDOS = sorted(motor.NOMBRE_DOCUMENTO)


class Argumentos(BaseModel):
    afiliado_ref: str = Field(
        description="Código del afiliado, con el formato AF-100234.")
    procedimiento_codigo: str = Field(
        description="Código del procedimiento en el catálogo de Vitalia, con el "
                    "formato PRC-4712.")
    documentos_presentes: list[str] = Field(
        default_factory=list,
        description="Documentos ya adjuntos, usando SOLO estas etiquetas: "
                    + ", ".join(DOCUMENTOS_VALIDOS) + ". Lo que no esté en esa "
                    "lista se ignora.")
    fecha_prevista: str | None = Field(
        default=None,
        description="Fecha prevista del procedimiento en formato AAAA-MM-DD. "
                    "Si se omite se calcula a hoy. Cambia el resultado porque "
                    "las carencias se cuentan en días.")


DESCRIPCION = """Calcula, para un afiliado y un procedimiento concretos, si hay
carencia pendiente, si el plan cubre, cuánto sería el copago con su desglose, y
qué documentos faltan. Es aritmética y calendario sobre los datos del afiliado:
no interviene ningún modelo de lenguaje y el resultado es reproducible.

Úsala cuando la pregunta sea sobre **un afiliado concreto**. Para lo que dice la
norma en general, usa `consultar_politica`.

No abre expediente, no autoriza y no niega: devuelve el cálculo y la ruta que le
correspondería a esa solicitud si se presentara."""


def _ejecutar(afiliado_ref: str, procedimiento_codigo: str,
              documentos_presentes: list[str] | None = None,
              fecha_prevista: str | None = None, *, cn=None) -> dict:
    if cn is None:
        return {"ok": False, "error": "sin_conexion",
                "detalle": "la skill necesita conexión a la base"}

    hoy = dt.date.fromisoformat(fecha_prevista) if fecha_prevista else dt.date.today()

    afiliado = repo.obtener_afiliado(cn, afiliado_ref)
    if afiliado is None:
        return {"ok": False, "error": "afiliado_inexistente",
                "detalle": f"«{afiliado_ref}» no está en el padrón"}

    procedimiento = repo.obtener_procedimiento(cn, procedimiento_codigo)
    if procedimiento is None:
        # El catálogo dispone. Un código que no existe no se aproxima al más
        # parecido: se rechaza, igual que hace E1 en el Carril 1.
        return {"ok": False, "error": "procedimiento_inexistente",
                "detalle": f"«{procedimiento_codigo}» no está en el catálogo de "
                           f"procedimientos"}

    presentes = [d for d in (documentos_presentes or []) if d in motor.NOMBRE_DOCUMENTO]
    ignorados = [d for d in (documentos_presentes or []) if d not in motor.NOMBRE_DOCUMENTO]

    tarifa = repo.obtener_tarifa(cn, procedimiento_codigo, afiliado["plan_codigo"])
    r = motor.adjudicar(afiliado, {"procedimiento_codigo": procedimiento_codigo},
                        tarifa, presentes, hoy)
    ruta, motivo_ruta = motor.rutear(r)

    # Los fundamentos que el motor declaró, resueltos a la cláusula exacta. Un
    # fundamento que no resuelve es un defecto —una conclusión sin norma que la
    # sustente— y se declara como tal en vez de desaparecer del resultado.
    fragmentos = recuperacion.fragmentos_de(r.fundamentos)
    por_clave = {(f.doc_id, f.articulo): f for f in fragmentos}
    citas, sin_fragmento = [], []
    for doc_id, articulo in r.fundamentos:
        f = por_clave.get((doc_id, articulo))
        if f is None:
            sin_fragmento.append(f"{doc_id} § {articulo}")
            continue
        citas.append({"chunk_id": f.chunk_id, "articulo": f.articulo,
                      "jerarquia": f.jerarquia, "version_id": f.version_id,
                      "texto": recuperacion.cuerpo_citable(f)})

    d = r.como_dict()
    return {
        "ok": True,
        "afiliado_ref": afiliado_ref,
        "plan_codigo": afiliado["plan_codigo"],
        "procedimiento": {"codigo": procedimiento_codigo,
                          "descripcion": procedimiento["descripcion"]},
        "fecha_evaluada": hoy.isoformat(),
        # La marca de R1, en el propio dato y no en la documentación.
        "determinista": True,
        "modelo": None,
        "elegible": d["elegible"],
        "motivo_elegibilidad": d["motivo_elegibilidad"],
        "carencia": {"cumplida": d["carencia_ok"],
                     "dias_exigidos": d["carencia_dias_exigidos"],
                     "dias_afiliado": d["carencia_dias_afiliado"]},
        "cobertura": d["cobertura"],
        "motivo_cobertura": d["motivo_cobertura"],
        "copago_pen": d["copago_pen"],
        "copago_desglose": d["copago_desglose"],
        "documentos_faltantes": [
            {"codigo": c, "descripcion": motor.NOMBRE_DOCUMENTO.get(c, c)}
            for c in d["documentos_faltantes"]],
        "documentos_ignorados": ignorados,
        "ruta": ruta,
        "motivo_ruta": motivo_ruta,
        "citas": citas,
        "fundamentos_sin_fragmento": sin_fragmento,
        "nivel": "N0",
        "aviso": "Simulación. No abre expediente, no autoriza y no niega: una "
                 "resolución sobre una solicitud real la firma la mesa.",
    }


V1_0_0 = Skill(
    nombre="simular_cobertura", version="1.0.0",
    descripcion=DESCRIPCION, esquema=Argumentos, ejecutar=_ejecutar,
    campo_texto_libre=None, escribe=False, cita_politica=True)
