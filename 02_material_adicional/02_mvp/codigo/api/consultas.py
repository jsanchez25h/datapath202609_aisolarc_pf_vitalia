"""Lecturas de la mesa — lo que ven las pantallas 3, 4 y 5.

Todo lo que hay aquí es SELECT. Ninguna de estas funciones decide nada ni
llama a un modelo: la bandeja, el expediente y el panel se arman leyendo la
bitácora que el Carril 1 ya escribió.

Que sea así no es una separación de capas por gusto. Es la forma de que la
pantalla 4 sea **evidencia** y no una segunda opinión: el analista y el
fiscalizador de SuSalud leen exactamente las mismas filas, y si la pantalla
recalculara el copago para mostrarlo, dejaría de probar que lo calculó el motor.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal


def _f(v):
    """Nada de `Decimal` ni `date` cruza la frontera HTTP sin convertirse."""
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    return v


def _filas(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [{c: _f(v) for c, v in zip(cols, fila)} for fila in cur.fetchall()]


# --- Pantalla 3 · bandeja ---------------------------------------------------

def bandeja(cn, estado: str | None = None, limite: int = 50) -> list[dict]:
    """Los expedientes con su estado, su ruta y su tiempo en cola.

    `horas_en_cola` y `horas_para_vencer` se calculan en la base y no en el
    cliente: el reloj del SLA es uno solo, y si cada pantalla lo calculara con
    su propia hora local, dos analistas verían vencimientos distintos.
    """
    where = "WHERE s.estado_actual = %s" if estado else ""
    args = ([estado] if estado else []) + [limite]
    with cn.cursor() as cur:
        cur.execute(f"""
            SELECT s.solicitud_id, s.afiliado_ref, a.nombre AS afiliado,
                   s.plan_codigo, s.procedimiento_codigo, p.descripcion AS procedimiento,
                   s.dx_cie10, s.tipo, s.canal, s.estado_actual,
                   adj.ruta, adj.motivo_ruta, adj.cobertura, adj.copago_pen,
                   s.creada_en, s.sla_vence_en,
                   ROUND(EXTRACT(EPOCH FROM (now() - s.creada_en)) / 3600, 1) AS horas_en_cola,
                   ROUND(EXTRACT(EPOCH FROM (s.sla_vence_en - now())) / 3600, 1) AS horas_para_vencer
              FROM solicitud s
              JOIN core_afiliado a  ON a.afiliado_ref = s.afiliado_ref
              JOIN catalogo_procedimiento p ON p.codigo = s.procedimiento_codigo
              LEFT JOIN adjudicacion adj ON adj.solicitud_id = s.solicitud_id
             {where}
             ORDER BY s.sla_vence_en NULLS LAST, s.creada_en
             LIMIT %s
        """, args)
        return _filas(cur)


def resumen_bandeja(cn) -> list[dict]:
    with cn.cursor() as cur:
        cur.execute("""
            SELECT estado_actual AS estado, COUNT(*) AS n
              FROM solicitud GROUP BY 1 ORDER BY 2 DESC
        """)
        return _filas(cur)


# --- Pantalla 4 · detalle del expediente ------------------------------------

def expediente(cn, solicitud_id: str) -> dict | None:
    """El expediente completo, con la frontera R1 marcada en el propio dato.

    `adjudicacion.determinista` viene de la base y vale `true` siempre: es la
    columna que sostiene, sin necesidad de que nadie lo explique en la
    pantalla, que la cobertura y el copago no pasaron por un modelo. Las
    extracciones traen `modelo` lleno; la adjudicación lo trae vacío. Esa
    asimetría **es** la evidencia de R1.
    """
    with cn.cursor() as cur:
        cur.execute("""
            SELECT s.*, a.nombre AS afiliado_nombre, a.afiliado_desde, a.estado AS afiliado_estado,
                   a.deducible_anual, a.deducible_consumido, a.preexistencias,
                   p.descripcion AS procedimiento_desc, c.descripcion AS dx_desc
              FROM solicitud s
              JOIN core_afiliado a ON a.afiliado_ref = s.afiliado_ref
              JOIN catalogo_procedimiento p ON p.codigo = s.procedimiento_codigo
              LEFT JOIN catalogo_cie10 c ON c.codigo = s.dx_cie10
             WHERE s.solicitud_id = %s
        """, (solicitud_id,))
        cab = _filas(cur)
        if not cab:
            return None
        exp = cab[0]

        cur.execute("""
            SELECT campo, valor, confianza, validado_catalogo, modelo, ts
              FROM extraccion WHERE solicitud_id = %s ORDER BY extr_id
        """, (solicitud_id,))
        exp["extraccion"] = _filas(cur)

        cur.execute("""
            SELECT adj_id, elegible, carencia_ok, carencia_dias_exigidos,
                   carencia_dias_afiliado, cobertura, motivo, copago_pen,
                   copago_desglose, ruta, motivo_ruta, determinista, modelo, ts
              FROM adjudicacion WHERE solicitud_id = %s ORDER BY ts DESC LIMIT 1
        """, (solicitud_id,))
        adj = _filas(cur)
        exp["adjudicacion"] = adj[0] if adj else None

        cur.execute("""
            SELECT cita_id, chunk_id, version_id, articulo, texto_literal,
                   verificada_literal
              FROM cita WHERE solicitud_id = %s ORDER BY cita_id
        """, (solicitud_id,))
        exp["citas"] = _filas(cur)

        cur.execute("""
            SELECT borrador_id, tipo, cuerpo, aprobada_guardrail, controles,
                   version_politica, modelo, creado_en
              FROM borrador_carta WHERE solicitud_id = %s ORDER BY creado_en DESC
        """, (solicitud_id,))
        exp["borradores"] = _filas(cur)

        cur.execute("""
            SELECT carta_id, tipo, version_politica, firma_id, cuerpo,
                   copago_pen, core_folio, emitida_en
              FROM carta WHERE solicitud_id = %s ORDER BY emitida_en DESC
        """, (solicitud_id,))
        exp["cartas"] = _filas(cur)

        cur.execute("""
            SELECT desde, hacia, actor, motivo, ts
              FROM evento_estado WHERE solicitud_id = %s ORDER BY ev_id
        """, (solicitud_id,))
        exp["bitacora"] = _filas(cur)

        cur.execute("""
            SELECT sentido, capa, decision, confianza, latencia_ms, detalle
              FROM evaluacion_guardrail WHERE solicitud_id = %s ORDER BY eval_id
        """, (solicitud_id,))
        exp["guardrail"] = _filas(cur)

        cur.execute("""
            SELECT span, proveedor, modelo, tokens_in, tokens_out,
                   costo_usd, latencia_ms, cache_hit
              FROM metrica_costo WHERE solicitud_id = %s ORDER BY metrica_id
        """, (solicitud_id,))
        exp["costos"] = _filas(cur)
        exp["costo_usd_total"] = round(sum(c["costo_usd"] for c in exp["costos"]), 6)

    return exp


# --- Pantalla 5 · panel de operación ----------------------------------------

def panel(cn, tipo_cambio: float = 3.75) -> dict:
    """Costo, latencia y calidad en una sola vista: S02 y S10 juntas.

    Los percentiles se calculan con `percentile_cont`, que interpola, y sobre
    todas las filas de `metrica_costo`. Con las decenas de solicitudes de un
    MVP un p95 es una cifra frágil —el 95 de veinte casos es el segundo peor—,
    y se declara como tal en la evidencia en lugar de presentarse como una
    medición de producción.
    """
    salida: dict = {}
    with cn.cursor() as cur:
        cur.execute("""
            SELECT span,
                   COUNT(*)                       AS llamadas,
                   SUM(costo_usd)                 AS costo_usd,
                   SUM(tokens_in)                 AS tokens_in,
                   SUM(tokens_out)                AS tokens_out,
                   ROUND(AVG(latencia_ms))        AS p50_ms_aprox,
                   PERCENTILE_CONT(0.5)  WITHIN GROUP (ORDER BY latencia_ms) AS p50_ms,
                   PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latencia_ms) AS p95_ms,
                   SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) AS aciertos_cache
              FROM metrica_costo
             GROUP BY span ORDER BY 3 DESC
        """)
        salida["por_span"] = _filas(cur)

        cur.execute("SELECT COUNT(*) FROM solicitud")
        n = cur.fetchone()[0] or 0
        cur.execute("SELECT COALESCE(SUM(costo_usd), 0) FROM metrica_costo")
        usd = float(cur.fetchone()[0] or 0)
        salida["solicitudes"] = n
        salida["costo_usd_total"] = round(usd, 6)
        salida["costo_pen_por_solicitud"] = round(usd * tipo_cambio / n, 4) if n else 0.0

        # Hit-rate del caché semántico. Se mide sobre las lecturas del span
        # `n1`, no sobre todas las llamadas: un acierto de caché en la
        # extracción no existe, y meterlo en el denominador rebajaría el
        # indicador con filas que nunca pudieron acertar.
        cur.execute("""
            SELECT COUNT(*) AS lecturas,
                   SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) AS aciertos
              FROM metrica_costo WHERE span IN ('n1', 'recuperacion')
        """)
        f = _filas(cur)[0]
        lecturas = f["lecturas"] or 0
        salida["cache"] = {
            "lecturas": lecturas,
            "aciertos": f["aciertos"] or 0,
            "hit_rate": round((f["aciertos"] or 0) / lecturas, 3) if lecturas else None,
        }

        cur.execute("""
            SELECT ruta, COUNT(*) AS n FROM adjudicacion GROUP BY 1 ORDER BY 2 DESC
        """)
        salida["ruteo"] = _filas(cur)

        cur.execute("""
            SELECT sentido, decision, COUNT(*) AS n
              FROM evaluacion_guardrail GROUP BY 1, 2 ORDER BY 1, 3 DESC
        """)
        salida["guardrail"] = _filas(cur)

        cur.execute("""
            SELECT COUNT(*) FILTER (WHERE util)     AS pulgar_arriba,
                   COUNT(*) FILTER (WHERE NOT util) AS pulgar_abajo
              FROM feedback
        """)
        salida["feedback"] = _filas(cur)[0]

        cur.execute("""
            SELECT COUNT(*) AS citas, COUNT(*) FILTER (WHERE verificada_literal) AS verificadas
              FROM cita
        """)
        salida["citas"] = _filas(cur)[0]

        cur.execute("""
            SELECT version_id, vigencia_desde, vigencia_hasta, fragmentos, coleccion_qdrant
              FROM politica_version ORDER BY vigencia_desde DESC
        """)
        salida["politica"] = _filas(cur)

    return salida
