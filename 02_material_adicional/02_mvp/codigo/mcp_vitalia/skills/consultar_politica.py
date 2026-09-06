"""Skill 1 · `consultar_politica` — el Carril 0 expuesto como herramienta.

Dos versiones publicadas, y la diferencia entre ellas es exactamente la sesión
02 del curso: `v1.0.0` pregunta siempre al modelo, `v1.1.0` consulta antes el
caché semántico. Es un hot-swap con consecuencia medible —costo y latencia— y no
un cambio cosmético para enseñar el mecanismo.

Conviene no confundir dos cosas que acaban en la misma llamada:

- que una **versión** de la skill no use caché es una decisión de producto;
- que una **ejecución** no use caché porque Qdrant no responde es una
  degradación, el nivel N2 de la escalera del diseño.

La primera se elige en el registro; la segunda la elige la cadena de respaldo en
caliente. Por eso `v1.0.0` no reporta `degradado=True`: está haciendo lo que se
publicó que hacía.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from flujo import consulta_n1
from mcp_vitalia import resiliencia
from mcp_vitalia.registro import Skill


class Argumentos(BaseModel):
    consulta: str = Field(
        description="La pregunta sobre las condiciones del plan, en español y "
                    "en lenguaje natural. Por ejemplo: «¿cuántos días de "
                    "carencia tiene una colecistectomía en el plan Integral?»")
    plan: str | None = Field(
        default=None,
        description="Código del plan si se conoce: VIT-ESE, VIT-INT o VIT-PRE. "
                    "Acota la búsqueda a las cláusulas de ese plan.")


DESCRIPCION = """Responde preguntas sobre las condiciones del plan de salud de
Vitalia (carencias, deducibles, coaseguros, copagos, exclusiones, requisitos
documentales) citando textualmente la cláusula que lo sustenta.

Úsala cuando la pregunta sea sobre **qué dice la política**. No la uses para
saber cuánto pagaría un afiliado concreto ni si su procedimiento procede: eso
depende de sus datos y lo calcula `simular_cobertura`.

Nunca autoriza, niega ni promete un resultado: devuelve lo que dice la norma."""


def _envolver(r, nivel: str, degradado: bool, intentos: list[dict]) -> dict:
    return {
        "ok": True,
        "texto": r.texto,
        "citas": [{"chunk_id": c["chunk_id"], "articulo": c["articulo"],
                   "jerarquia": c["jerarquia"], "version_id": c["version_id"],
                   "texto": c["texto"]} for c in r.citas_verificadas],
        "citas_rechazadas": list(r.citas_rechazadas),
        "origen": r.origen,
        "nivel": nivel,
        "degradado": degradado,
        "intentos": intentos,
        "latencia_ms": r.latencia_ms,
        # `consulta_n1.responder` ya escribió su propia fila en `metrica_costo`
        # cuando se le pasa conexión. Se declara aquí para que el gancho G6 no
        # escriba una segunda: la fila duplicada inflaría el costo por solicitud
        # del panel, que es el número que se compara contra el S/ 0.86 del caso.
        "_costo": {"proveedor": "groq", "modelo": r.modelo,
                   "tokens_in": r.tokens_in, "tokens_out": r.tokens_out,
                   "costo_usd": r.costo_usd, "cache_hit": r.origen == "cache"},
        "_costo_anotado_aguas_abajo": True,
    }


def _derivar_a_la_mesa() -> dict:
    """N5 · el último eslabón, que no puede fallar porque no llama a nadie.

    Devuelve la misma frase que la regla 1 del prompt de N1 obliga a decir
    cuando los fragmentos no alcanzan, y no una disculpa técnica. Al prestador
    le sirve saber a dónde ir; que el proveedor de modelos esté caído es un
    detalle nuestro.
    """
    return {"ok": True, "texto": consulta_n1.SIN_CLAUSULA, "citas": [],
            "citas_rechazadas": [], "origen": "degradado", "nivel": "N5",
            "degradado": True, "intentos": [], "latencia_ms": 0}


def _ejecutar(consulta: str, plan: str | None = None, *, cn=None,
              usar_cache: bool = True) -> dict:
    def normal():
        return consulta_n1.responder(consulta, plan=plan, usar_cache=usar_cache, cn=cn)

    def sin_cache():
        return consulta_n1.responder(consulta, plan=plan, usar_cache=False, cn=cn)

    eslabones = [resiliencia.Eslabon(
        "N0", "operación normal", normal,
        resiliencia.DISYUNTORES["groq"])]
    if usar_cache:
        # Solo tiene sentido como respaldo si la versión activa sí usa caché:
        # para `v1.0.0` este eslabón sería idéntico al primero y reintentar lo
        # mismo tras un fallo es el antipatrón que el disyuntor existe para
        # evitar.
        eslabones.append(resiliencia.Eslabon(
            "N2", "sin caché semántico: el caché no responde y se paga el token",
            sin_cache, resiliencia.DISYUNTORES["groq"]))
    eslabones.append(resiliencia.Eslabon(
        "N5", "sin modelo: se deriva a la mesa", _derivar_a_la_mesa))

    res = resiliencia.cadena_de_respaldo(eslabones)
    if res.nivel == "N5":
        salida = dict(res.valor)
        salida["intentos"] = res.intentos
        return salida
    return _envolver(res.valor, res.nivel, res.degradado, res.intentos)


V1_0_0 = Skill(
    nombre="consultar_politica", version="1.0.0",
    descripcion=DESCRIPCION, esquema=Argumentos,
    ejecutar=lambda **kw: _ejecutar(**kw, usar_cache=False),
    campo_texto_libre="consulta", escribe=False, cita_politica=True)

V1_1_0 = Skill(
    nombre="consultar_politica", version="1.1.0",
    descripcion=DESCRIPCION, esquema=Argumentos,
    ejecutar=lambda **kw: _ejecutar(**kw, usar_cache=True),
    campo_texto_libre="consulta", escribe=False, cita_politica=True)
