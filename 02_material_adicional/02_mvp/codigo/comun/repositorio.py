"""Acceso a datos del MVP.

Dos familias de tablas que no se mezclan:

- `core_*` simula el core asegurador de Vitalia. La plataforma **lee** y no
  administra ese dato (ADR-18): aquí no hay un solo UPDATE contra `core_*`.
- el resto son tablas de la plataforma, y sí se escriben.

`evento_estado` se escribe siempre a través de `registrar_evento`, que valida la
transición contra `transicion_valida` antes de insertar. La tabla tiene reglas
que anulan UPDATE y DELETE, así que la bitácora es append-only de verdad.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from . import config


# --------------------------------------------------------------------------
# Lecturas al core (solo lectura)
# --------------------------------------------------------------------------

def obtener_afiliado(cn, afiliado_ref: str) -> dict | None:
    with cn.cursor() as cur:
        cur.execute("""
            SELECT afiliado_ref, nombre, plan_codigo, afiliado_desde, estado,
                   deducible_anual, deducible_consumido, preexistencias
              FROM core_afiliado WHERE afiliado_ref = %s
        """, (afiliado_ref,))
        f = cur.fetchone()
    if not f:
        return None
    return dict(zip(("afiliado_ref", "nombre", "plan_codigo", "afiliado_desde", "estado",
                     "deducible_anual", "deducible_consumido", "preexistencias"), f))


def obtener_tarifa(cn, procedimiento_codigo: str, plan_codigo: str) -> dict | None:
    """Devuelve None cuando el plan no tiene fila para el procedimiento.

    Esa ausencia **es** la regla: que VIT-ESE no tenga fila para PRC-5901 es
    como el modelo de datos expresa que el plan Esencial no cubre maternidad.
    """
    with cn.cursor() as cur:
        cur.execute("""
            SELECT procedimiento_codigo, plan_codigo, tarifa_pen, coaseguro_pct,
                   copago_fijo_pen, tope_copago_pen
              FROM core_tarifario
             WHERE procedimiento_codigo = %s AND plan_codigo = %s
        """, (procedimiento_codigo, plan_codigo))
        f = cur.fetchone()
    if not f:
        return None
    return dict(zip(("procedimiento_codigo", "plan_codigo", "tarifa_pen",
                     "coaseguro_pct", "copago_fijo_pen", "tope_copago_pen"), f))


def obtener_procedimiento(cn, codigo: str) -> dict | None:
    with cn.cursor() as cur:
        cur.execute("SELECT codigo, descripcion, requiere_preauth "
                    "FROM catalogo_procedimiento WHERE codigo = %s", (codigo,))
        f = cur.fetchone()
    return dict(zip(("codigo", "descripcion", "requiere_preauth"), f)) if f else None


# --------------------------------------------------------------------------
# Escrituras de la plataforma
# --------------------------------------------------------------------------

def nuevo_id(prefijo: str) -> str:
    return f"{prefijo}-{uuid.uuid4().hex[:12]}"


def registrar_evento(cn, solicitud_id: str, desde: str | None, hacia: str,
                     actor: str, motivo: str = "", trace_id: str | None = None) -> None:
    """Escribe en la bitácora append-only validando la transición.

    Si `desde -> hacia` no está en `transicion_valida`, revienta. Es la máquina
    de estados del diseño hecha restricción, no convención.
    """
    if desde is not None:
        with cn.cursor() as cur:
            cur.execute("SELECT 1 FROM transicion_valida WHERE desde=%s AND hacia=%s",
                        (desde, hacia))
            if cur.fetchone() is None:
                raise ValueError(f"transición inválida: {desde} -> {hacia}")
    with cn.cursor() as cur:
        cur.execute("""
            INSERT INTO evento_estado (solicitud_id, desde, hacia, actor, motivo, trace_id)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (solicitud_id, desde, hacia, actor, motivo or None, trace_id))
        cur.execute("UPDATE solicitud SET estado_actual = %s WHERE solicitud_id = %s",
                    (hacia, solicitud_id))


def registrar_costo(cn, solicitud_id: str | None, span: str, proveedor: str,
                    modelo: str | None = None, tokens_in: int = 0, tokens_out: int = 0,
                    costo_usd: float = 0.0, latencia_ms: int | None = None,
                    cache_hit: bool = False, trace_id: str | None = None) -> None:
    """Atribución de costo por span — sesión 02 (FinOps) y sesión 10 (LLMOps).

    Sin esta tabla el «S/0.86 por solicitud» del caso de negocio es una promesa;
    con ella es una consulta.
    """
    with cn.cursor() as cur:
        cur.execute("""
            INSERT INTO metrica_costo (solicitud_id, trace_id, span, proveedor, modelo,
                                       tokens_in, tokens_out, costo_usd, latencia_ms, cache_hit)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (solicitud_id, trace_id, span, proveedor, modelo,
              tokens_in, tokens_out, costo_usd, latencia_ms, cache_hit))


def guardar_adjudicacion(cn, solicitud_id: str, resultado: Any,
                         ruta: str, motivo_ruta: str) -> str:
    """`determinista=true` sin excepción: este INSERT solo lo escribe el motor.

    Cuando un modelo participe de una adjudicación —no ocurre en el MVP— la fila
    tendrá `modelo`, `modelo_version` y `prompt_sha`, y `determinista=false`.
    """
    adj_id = nuevo_id("ADJ")
    d = resultado.como_dict()
    with cn.cursor() as cur:
        cur.execute("""
            INSERT INTO adjudicacion
                (adj_id, solicitud_id, elegible, carencia_ok,
                 carencia_dias_exigidos, carencia_dias_afiliado, cobertura, motivo,
                 copago_pen, copago_desglose, ruta, motivo_ruta, determinista)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true)
        """, (adj_id, solicitud_id, d["elegible"], d["carencia_ok"],
              d["carencia_dias_exigidos"], d["carencia_dias_afiliado"], d["cobertura"],
              d["motivo_cobertura"], d["copago_pen"],
              json.dumps(d["copago_desglose"], ensure_ascii=False),
              ruta, motivo_ruta))
    return adj_id
