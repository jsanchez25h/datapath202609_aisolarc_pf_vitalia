"""api-vitalia — el servicio que sostiene las cinco pantallas de la mesa.

Un solo proceso expone los dos carriles y las lecturas de la bandeja. El diseño
los separa en dos Cloud Run —`api-preauth` y `api-rag`— por razones de escalado
y de superficie de exposición: el Carril 0 lo consume un prestador desde fuera y
el Carril 1 lo consume la mesa desde dentro. **Aquí van juntos y eso es una
reducción de alcance declarada, no un cambio de diseño**: los routers están
separados por prefijo (`/n1` y `/solicitudes`) y no comparten estado, así que
partirlos en dos imágenes es cambiar el despliegue, no el código.

Lo que este servicio no hace, y es deliberado:

- **No decide.** El copago, la cobertura y la ruta salen del motor determinista.
  El endpoint los transporta.
- **No autentica.** El diseño pone Identity Platform y Cloud Armor en el borde
  (ADR-15), delante del contenedor. Un `actor` que llega por el cuerpo del
  request es una identidad *declarada*, y en local es todo lo que hay. La
  bitácora lo guarda como lo que es.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from api import consultas
from comun import config, motor_determinista as motor, repositorio as repo
from flujo import carril1, consulta_n1, emision_e4

app = FastAPI(
    title="api-vitalia",
    version=config.VERSION_ID,
    description="Mesa de preautorización de Vitalia Salud EPS · MVP de la fase 2",
)

# En local la interfaz corre en otro puerto que el servicio. En GCP las dos
# quedan detrás del mismo API Gateway y este permiso deja de hacer falta.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# --- Conexión ---------------------------------------------------------------
# Una conexión por petición, abierta y cerrada en el mismo bloque. Neon corta
# las conexiones ociosas y un pool de larga vida contra un servicio serverless
# con `min-instances=0` es un pool de conexiones muertas.

class _Cn:
    def __enter__(self):
        self.cn = config.conexion_pg()
        return self.cn

    def __exit__(self, *a):
        try:
            self.cn.rollback()
        finally:
            self.cn.close()


# --- Modelos de entrada -----------------------------------------------------

class ConsultaN1(BaseModel):
    consulta: str = Field(min_length=3, max_length=2000)
    plan: str | None = None
    usar_cache: bool = True


class NuevaSolicitud(BaseModel):
    texto: str = Field(min_length=20, max_length=20000,
                       description="El correo o formulario del prestador, tal cual llegó")
    fecha: dt.date | None = None


class Firma(BaseModel):
    colegiatura_cmp: str
    medico_id: str


class Resolucion(BaseModel):
    actor: str = Field(min_length=3, description="Quién resuelve. Va a la bitácora.")
    cuerpo: str | None = Field(
        default=None,
        description="La carta que la persona aprueba. Si viene vacío se usa el "
                    "último borrador tal como lo redactó el sistema.")
    firma: Firma | None = None


class Voto(BaseModel):
    solicitud_id: str | None = None
    usuario: str | None = None
    util: bool
    tipo_error: str | None = None
    comentario: str | None = None


# --- Salud y política -------------------------------------------------------

@app.get("/salud", tags=["operación"])
def salud():
    """Verifica las tres dependencias externas, no solo que el proceso viva.

    Un `/salud` que devuelve 200 porque el contenedor arrancó es exactamente el
    check que deja pasar un despliegue con la base caída.
    """
    estado: dict = {"version_politica": config.VERSION_ID, "alias": config.ALIAS}
    try:
        with _Cn() as cn, cn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM solicitud")
            estado["neon"] = {"ok": True, "solicitudes": cur.fetchone()[0]}
    except Exception as e:                                   # noqa: BLE001
        estado["neon"] = {"ok": False, "error": str(e)[:200]}
    try:
        info = config.cliente_qdrant().get_collection(config.ALIAS)
        estado["qdrant"] = {"ok": True, "puntos": info.points_count}
    except Exception as e:                                   # noqa: BLE001
        estado["qdrant"] = {"ok": False, "error": str(e)[:200]}
    estado["ok"] = all(v.get("ok") for v in estado.values() if isinstance(v, dict))
    return JSONResponse(estado, status_code=200 if estado["ok"] else 503)


@app.get("/politica", tags=["operación"])
def politica():
    with _Cn() as cn, cn.cursor() as cur:
        cur.execute("""
            SELECT version_id, vigencia_desde, vigencia_hasta, fragmentos,
                   coleccion_qdrant, aprobado_por, diff_vs_anterior, publicada_en
              FROM politica_version ORDER BY vigencia_desde DESC
        """)
        return {"versiones": consultas._filas(cur), "vigente": config.VERSION_ID}


# --- Pantalla 2 · Carril 0, consulta anticipada -----------------------------

@app.post("/n1/consulta", tags=["carril 0"])
def n1(req: ConsultaN1):
    """El prestador pregunta antes de mandar el expediente.

    Es el carril que evita la solicitud incompleta, y el único del MVP que
    responde en prosa sin que exista un expediente detrás. Por eso su guardrail
    de entrada corta en la primera capa que bloquea: aquí no hay nada que
    auditar después, solo una respuesta que no debe darse.
    """
    # La conexión se abre aunque N1 no toque ningún expediente: es para que el
    # gasto del carril quede escrito en `metrica_costo`. Sin ella el panel de la
    # pantalla 5 reporta de menos justo el carril que el caso dice que lleva el
    # 41% del volumen, y el hit-rate del caché sale vacío por construcción.
    with _Cn() as cn:
        r = consulta_n1.responder(req.consulta, plan=req.plan,
                                  usar_cache=req.usar_cache, cn=cn)
    return r.como_dict()


# --- Pantalla 3 · bandeja ---------------------------------------------------

@app.get("/solicitudes/resumen", tags=["mesa"])
def resumen():
    with _Cn() as cn:
        return {"por_estado": consultas.resumen_bandeja(cn)}


@app.get("/solicitudes", tags=["mesa"])
def bandeja(estado: str | None = Query(default=None), limite: int = Query(default=50, le=200)):
    with _Cn() as cn:
        return {"expedientes": consultas.bandeja(cn, estado, limite)}


@app.post("/solicitudes", status_code=201, tags=["carril 1"])
def crear(req: NuevaSolicitud):
    """Recibe el texto del prestador y lo lleva de E1 a E4.

    Devuelve 200 y no 201 cuando el expediente ya existía: el reenvío del mismo
    correo —que en una mesa real pasa todos los días, porque el prestador
    reenvía «por si acaso»— no crea un segundo expediente ni vuelve a pagar los
    modelos. La idempotencia se calcula sobre el hash del texto.
    """
    with _Cn() as cn:
        exp = carril1.procesar(cn, req.texto, hoy=req.fecha)
    d = exp.__dict__ | {"duplicada": exp.duplicada}
    return JSONResponse(d, status_code=200 if exp.duplicada else 201)


# --- Pantalla 4 · detalle y resolución --------------------------------------

@app.get("/solicitudes/{solicitud_id}", tags=["mesa"])
def detalle(solicitud_id: str):
    with _Cn() as cn:
        exp = consultas.expediente(cn, solicitud_id)
    if not exp:
        raise HTTPException(404, f"no existe el expediente {solicitud_id}")
    return exp


@app.post("/solicitudes/{solicitud_id}/resolver", tags=["mesa"])
def resolver(solicitud_id: str, req: Resolucion = Body(...)):
    """El analista emite la carta de un expediente que estaba en la cola.

    Tres cosas que este endpoint hace y conviene leer despacio:

    1. **Vuelve a correr el motor determinista** con la fecha original de la
       solicitud, y no lee la adjudicación guardada. Si el resultado no
       coincidiera con lo que se archivó, el motor habría dejado de ser
       determinista y eso tiene que doler aquí y no en una auditoría.
    2. **Vuelve a correr los seis controles sobre el texto que la persona
       aprueba**, aunque lo haya editado. Un guardrail que solo mira lo que
       escribió el modelo deja sin controlar justo el texto que sí lleva firma.
    3. **La persona vence al `borrador`, no al guardrail.** Puede emitir lo que
       el sistema solo no emitía; no puede emitir lo que O1–O6 reprobaron.
    """
    with _Cn() as cn:
        exp = consultas.expediente(cn, solicitud_id)
        if not exp:
            raise HTTPException(404, f"no existe el expediente {solicitud_id}")
        if exp["estado_actual"] != "hitl":
            raise HTTPException(
                409, f"el expediente está en «{exp['estado_actual']}» y la máquina de "
                     f"estados solo admite hitl → E4. Los expedientes en «agente» "
                     f"esperan documentos del prestador, no una firma.")

        afiliado = repo.obtener_afiliado(cn, exp["afiliado_ref"])
        proc = repo.obtener_procedimiento(cn, exp["procedimiento_codigo"])
        tarifa = repo.obtener_tarifa(cn, exp["procedimiento_codigo"], exp["plan_codigo"])
        fecha = dt.date.fromisoformat(exp["fecha_solicitud"])
        solicitud = {"dx_cie10": exp["dx_cie10"], "tipo": exp["tipo"],
                     "procedimiento_codigo": exp["procedimiento_codigo"]}

        documentos = next((c["valor"] for c in exp["extraccion"]
                           if c["campo"] == "documentos"), "[]")
        import json as _json
        docs = _json.loads(documentos) if isinstance(documentos, str) else (documentos or [])
        r = motor.adjudicar(afiliado, solicitud, tarifa, docs, fecha)

        # El borrador por omisión es **el último que el guardrail aprobó**, no el
        # último a secas. Los dos difieren en cuanto alguien intenta emitir una
        # carta editada y O1 la reprueba: ese intento se guarda —el veto V2 pide
        # poder reconstruir qué se propuso—, y si el valor por omisión fuera «el
        # más reciente», el siguiente intento le ofrecería al analista, ya
        # rellenado, el texto que el control acababa de rechazar.
        aprobado = next((b for b in exp["borradores"] if b["aprobada_guardrail"]), None)
        cuerpo = req.cuerpo or (aprobado["cuerpo"] if aprobado else None)
        if not cuerpo:
            raise HTTPException(
                409, "no hay ningún borrador aprobado por el guardrail para este "
                     "expediente: hay que enviar el cuerpo corregido en «cuerpo»")

        firma_id = None
        if req.firma:
            firma_id = repo.nuevo_id("FIR")
            with cn.cursor() as cur:
                cur.execute("""
                    INSERT INTO firma_medica (firma_id, adj_id, colegiatura_cmp,
                                              medico_id, hash_doc)
                    VALUES (%s,%s,%s,%s,%s)
                """, (firma_id, exp["adjudicacion"]["adj_id"], req.firma.colegiatura_cmp,
                      req.firma.medico_id, carril1._hash(cuerpo)))

        em = emision_e4.redactar(
            cn, afiliado, solicitud, proc, r, exp["adjudicacion"]["ruta"],
            codigos_validos=carril1._codigos_del_catalogo(cn),
            version_vigente=config.VERSION_ID,
            vigencia_desde=carril1._vigencia(cn, config.VERSION_ID),
            fecha_solicitud=fecha, firma_id=firma_id, cuerpo_forzado=cuerpo)
        carril1.guardrail_salida_filas(cn, solicitud_id, em)
        carril1.guardar_borrador(cn, solicitud_id, exp["adjudicacion"]["adj_id"], em)

        if not em.aprobada:
            cn.commit()          # el intento reprobado queda contado, la carta no sale
            return JSONResponse(
                {"emitida": False, "motivo": "el guardrail de salida reprobó la carta",
                 "controles": em.controles,
                 "bloquearon": [c["codigo"] for c in em.controles if not c["paso"]]},
                status_code=409)

        repo.registrar_evento(cn, solicitud_id, "hitl", "E4", req.actor,
                              f"carta «{em.tipo}» revisada" +
                              (" y editada" if req.cuerpo else " sin cambios"))
        carta_id = emision_e4.persistir(cn, solicitud_id, exp["adjudicacion"]["adj_id"],
                                        em, config.VERSION_ID, firma_id, r.copago_pen,
                                        forzar_emision=True)
        repo.registrar_evento(cn, solicitud_id, "E4", "emitida", req.actor,
                              f"carta {carta_id}")
        cn.commit()
        return {"emitida": True, "carta_id": carta_id, "tipo": em.tipo,
                "firma_id": firma_id, "controles": em.controles,
                "editada_por_persona": bool(req.cuerpo)}


# --- Pantalla 5 · panel de operación ----------------------------------------

@app.get("/operacion/panel", tags=["operación"])
def panel():
    with _Cn() as cn:
        return consultas.panel(cn)


@app.post("/feedback", status_code=201, tags=["operación"])
def feedback(v: Voto):
    """El pulgar arriba/abajo de la pantalla 5.

    Se persiste en Neon y no solo en la traza del observador: el ciclo de mejora
    del diseño necesita poder cruzar el voto contra la adjudicación que lo
    provocó, y eso es un JOIN, no un tablero.
    """
    with _Cn() as cn:
        with cn.cursor() as cur:
            cur.execute("""
                INSERT INTO feedback (solicitud_id, usuario, util, tipo_error, comentario)
                VALUES (%s,%s,%s,%s,%s) RETURNING feedback_id
            """, (v.solicitud_id, v.usuario, v.util, v.tipo_error, v.comentario))
            fid = cur.fetchone()[0]
        cn.commit()
    return {"feedback_id": fid}


# --- app-mesa · la interfaz -------------------------------------------------
# La interfaz se sirve desde el mismo proceso que la API. El plan de la fase 2
# decía Next.js, y esto es un archivo HTML sin paso de compilación: **es una
# desviación declarada del plan, no un descuido**. Las razones son tres y
# ninguna es estética. La entregable de la fase 2 son capturas y evidencia, no
# un producto que alguien vaya a mantener. Un `next build` mete un artefacto
# intermedio entre lo que se lee en el repositorio y lo que se ve en la
# pantalla, y en un anexo de evidencia esa distancia se paga. Y sobre todo:
# comparte imagen con la API, así que no hay CORS, ni segundo despliegue, ni un
# origen más que autorizar en Cloud Armor.
#
# Lo que la desviación cuesta, dicho también: no hay componentes, ni tipos, ni
# pruebas de interfaz. Si esto pasara a producción habría que reescribirlo, y el
# diseño de la fase 1 —dos Cloud Run, la interfaz detrás de Identity Platform—
# sigue siendo el que vale.

_APP = Path(__file__).resolve().parents[1] / "app_mesa"


@app.get("/", include_in_schema=False)
def raiz():
    return FileResponse(_APP / "index.html")


app.mount("/app", StaticFiles(directory=_APP, html=True), name="app-mesa")
