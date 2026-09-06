"""E4 · Emisión de la carta — el artefacto que el afiliado puede llevar a SuSalud.

Es el único punto del flujo donde un modelo escribe algo que sale de la empresa,
y por eso es el punto con más controles. Tres decisiones de diseño lo gobiernan:

1. **El modelo no calcula: transcribe.** El copago llega redactado desde el motor
   determinista y la única tarea del modelo es ponerlo en una oración. O3
   verifica después que el número de la prosa sea el del motor, y bloquea la
   emisión si no coinciden. Si el copago se lo hubiéramos pedido al modelo, no
   habría con qué contrastarlo (R1).

2. **Las citas no se buscan: se resuelven.** El motor ya declaró qué cláusula
   sustenta cada conclusión; `fragmentos_de` las trae por correspondencia exacta.
   Un buscador semántico podría traer una cláusula *parecida*, y una cláusula
   parecida en una carta de preautorización es una cita falsa (R2).

3. **El sistema nunca niega solo** (ADR-10). Una carta de tipo negación se
   redacta, se controla y se guarda como borrador con su fundamento y su cita,
   pero no se emite: la firma la pone una persona. Lo que el MVP automatiza es
   la preparación completa del expediente, no la decisión.
"""

from __future__ import annotations

import datetime as dt
import re
import time
from dataclasses import dataclass, field, asdict
from decimal import Decimal

from comun import motor_determinista as motor, recuperacion, repositorio as repo, router_modelos
from guardrails import salida as guardrail_salida

FUENTES = re.compile(r"^FUENTES:\s*(.+)$", re.MULTILINE | re.IGNORECASE)

SISTEMA = """Redactas cartas de respuesta de la mesa de preautorización de Vitalia
Salud EPS. Quien la lee es el afiliado o su médico tratante, no un abogado.

Reglas que no puedes romper:

1. **No calcules nada.** Los importes, los plazos y los días de carencia vienen
   dados en la ficha de adjudicación. Cópialos exactamente como están, con el
   mismo número. No sumes, no redondees, no conviertas.
2. Toda afirmación sobre la política va con una cita **textual** entre comillas,
   copiada carácter por carácter de los fragmentos que se te entregan. No
   parafrasees dentro de las comillas. Para omitir texto intermedio usa «…», y
   no juntes dentro de unas mismas comillas fragmentos de cláusulas distintas.
   **Ninguna carta puede salir sin al menos una cita textual.** Si autorizas, cita
   la cláusula que lo permite; si rechazas, la que sustenta la causal; si observas,
   la que exige el documento que falta. «Conforme a la política vigente» no es una
   cita: es una promesa de que existe una.
   La primera línea de cada fragmento es su ruta de títulos —«Documento > Sección >
   Artículo»— y **no es texto citable**: sirve para ubicar la cláusula, no dice qué
   ordena. Nombrar el artículo («tal como se indica en la Tabla de carencias») es
   una referencia, no una cita.
   Cuando la cláusula es una tabla, la norma **es la fila**, y se cita la fila
   entera con sus barras verticales, así:
   «| Hospitalización y cirugía | 60 días | Los tres planes |».
   Queda algo áspero en una carta, y es preferible a parafrasearla: el afiliado
   puede contrastar esa línea contra el documento, y una paráfrasis no.
3. Cierra con una línea `FUENTES:` y los identificadores de los fragmentos que
   citaste, separados por comas. No pongas ahí ningún identificador que no esté
   entre los fragmentos entregados.
4. No menciones códigos de procedimiento ni de diagnóstico que no aparezcan en
   la ficha de adjudicación.
5. Español peruano, tono claro y respetuoso, sin jerga aseguradora ni tecnicismos
   sin explicar. Entre ocho y quince líneas.
6. Si la carta comunica un rechazo, di con todas sus letras cuál es la causal y
   qué puede hacer el afiliado a continuación. No la disfraces."""

FICHA = """FICHA DE ADJUDICACIÓN (calculada por el motor determinista, no discutible)

  Tipo de carta ........ {tipo}
  Afiliado ............. {nombre} ({afiliado_ref}) · plan {plan}
  Procedimiento ........ {procedimiento} ({procedimiento_codigo})
  Diagnóstico .......... {dx}
  Elegibilidad ......... {elegibilidad}
  Carencia ............. exige {dias_exigidos} días · el afiliado tiene {dias_afiliado}
  Cobertura ............ {cobertura} — {motivo}
  Copago del afiliado .. {copago}
  {documentos}

FRAGMENTOS CITABLES DE LA POLÍTICA VIGENTE ({version})

{contexto}

---
Redacta la carta."""

# Qué carta corresponde a cada salida del motor. Es una tabla y no una decisión
# del modelo a propósito: el tipo de carta determina si hace falta firma médica
# (R3), y eso no puede depender de cómo se redactó el párrafo.
def tipificar(r: motor.ResultadoDeterminista, ruta: str) -> str:
    if ruta == "agente" or r.documentos_faltantes:
        return "observa"
    if ruta == "auto" and r.cobertura == "cubierto":
        return "autoriza"
    # Carencia incumplida, afiliación no vigente y plan sin la cobertura son
    # causales **administrativas**: la política las distingue expresamente de la
    # negación por necesidad médica, y por eso no exigen firma de médico. Lo que
    # sí exigen es citar la cláusula que las sustenta.
    return "niega_administrativa"


@dataclass
class Emision:
    tipo: str
    cuerpo: str
    borrador: bool                      # true = no se emite, la firma una persona
    aprobada: bool                      # true = el guardrail de salida la dejó pasar
    citas: list[dict] = field(default_factory=list)
    citas_rechazadas: list[str] = field(default_factory=list)
    fuentes_declaradas: list[str] = field(default_factory=list)
    fuentes_huerfanas: list[str] = field(default_factory=list)
    controles: list[dict] = field(default_factory=list)
    fundamentos_sin_fragmento: list[list[str]] = field(default_factory=list)
    modelo: str = ""
    costo_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    latencia_ms: int = 0
    truncada: bool = False

    def como_dict(self) -> dict:
        return asdict(self)


def _copago_en_texto(copago: Decimal | None) -> str:
    if copago is None:
        return "no corresponde calcular copago"
    return f"S/ {copago:,.2f}".replace(",", " ")


def redactar(cn, afiliado: dict, solicitud: dict, proc: dict,
             r: motor.ResultadoDeterminista, ruta: str,
             codigos_validos: set[str], version_vigente: str,
             vigencia_desde: dt.date,
             fecha_solicitud: dt.date | None = None,
             firma_id: str | None = None,
             cuerpo_forzado: str | None = None) -> Emision:
    """Redacta, controla y decide si la carta sale.

    `cuerpo_forzado` sustituye la generación por un texto dado. Existe para el
    banco de pruebas del guardrail de salida: los controles O2–O6 solo se pueden
    demostrar con cartas que fallen, y esas cartas hay que construirlas a mano
    porque el modelo, haciendo su trabajo, no las produce.
    """
    fecha_solicitud = fecha_solicitud or dt.date.today()
    tipo = tipificar(r, ruta)

    # Las citas salen de los fundamentos del motor, por correspondencia exacta.
    fragmentos = recuperacion.fragmentos_de(r.fundamentos)
    resueltos = {(f.doc_id, f.articulo) for f in fragmentos}
    sin_fragmento = [list(f) for f in r.fundamentos if tuple(f) not in resueltos]

    contexto = "\n\n".join(
        f"[{f.chunk_id}] {f.jerarquia}\n{f.texto_literal}" for f in fragmentos)
    por_chunk = {f.chunk_id: f for f in fragmentos}

    faltan = (", ".join(motor.NOMBRE_DOCUMENTO.get(d, d) for d in r.documentos_faltantes)
              if r.documentos_faltantes else "")
    ficha = FICHA.format(
        tipo=tipo, nombre=afiliado["nombre"], afiliado_ref=afiliado["afiliado_ref"],
        plan=afiliado["plan_codigo"], procedimiento=proc["descripcion"],
        procedimiento_codigo=proc["codigo"], dx=solicitud["dx_cie10"],
        elegibilidad=r.motivo_elegibilidad,
        dias_exigidos=r.carencia_dias_exigidos, dias_afiliado=r.carencia_dias_afiliado,
        cobertura=r.cobertura, motivo=r.motivo_cobertura,
        copago=_copago_en_texto(r.copago_pen),
        documentos=(f"Documentos faltantes .. {faltan}" if faltan
                    else "Documentos ........... completos"),
        version=version_vigente, contexto=contexto)

    if cuerpo_forzado is not None:
        cuerpo, resp = cuerpo_forzado, None
        ms = 0
    else:
        ruta_modelo = router_modelos.elegir("e4_redaccion", tipo_carta=tipo)
        t0 = time.time()
        resp = router_modelos.completar(ruta_modelo, SISTEMA, ficha)
        ms = int((time.time() - t0) * 1000)
        if resp.truncada:
            return Emision(tipo=tipo, cuerpo="", borrador=True, aprobada=False,
                           modelo=resp.modelo, costo_usd=resp.costo_usd,
                           tokens_in=resp.tokens_in, tokens_out=resp.tokens_out,
                           latencia_ms=ms, truncada=True,
                           fundamentos_sin_fragmento=sin_fragmento)
        cuerpo = resp.texto

    # --- Citas declaradas por la carta -------------------------------------
    citas = []
    for texto_cita in recuperacion.citas_de(cuerpo):
        origen = next((f for f in fragmentos
                       if recuperacion.verificar_cita_literal(texto_cita, f)), None)
        citas.append({"texto": texto_cita,
                      "chunk_id": origen.chunk_id if origen else "",
                      "articulo": origen.articulo if origen else "",
                      "jerarquia": origen.jerarquia if origen else "",
                      "version_id": origen.version_id if origen else version_vigente,
                      "verificada": origen is not None})

    # --- FUENTES: identificadores que la carta declara haber usado ---------
    # Verificar los tramos entrecomillados no basta. Una carta puede citar bien y
    # aun así declarar en `FUENTES` un identificador que nunca estuvo en el
    # contexto —se midió en el Carril 0: el modelo firmó una fuente inventada—.
    # El identificador es lo que un fiscalizador usa para ir al documento, así
    # que un huérfano ahí es tan grave como una cita falsa.
    m = FUENTES.search(cuerpo)
    declaradas = [s.strip() for s in m.group(1).split(",") if s.strip()] if m else []
    huerfanas = [d for d in declaradas if d not in por_chunk]

    codigos_del_caso = codigos_validos | {proc["codigo"], solicitud["dx_cie10"]}
    res = guardrail_salida.evaluar(
        cuerpo,
        citas=[c for c in citas if c["chunk_id"]],
        fragmentos_por_chunk=por_chunk,
        copago_motor=r.copago_pen,
        copago_desglose=r.copago_desglose,
        version_vigente=version_vigente,
        fecha_solicitud=fecha_solicitud,
        vigencia_desde=vigencia_desde,
        tipo_carta=tipo, firma_id=firma_id,
        codigos_validos=codigos_del_caso,
        destino="carta_titular",
        citas_sin_verificar=[c["texto"] for c in citas if not c["verificada"]],
        fuentes_huerfanas=huerfanas,
        fundamentos_sin_fragmento=sin_fragmento)

    # Una negación no la emite el sistema (ADR-10): queda como borrador firmado
    # por nadie hasta que un médico auditor o un supervisor la resuelva.
    #
    # La ruta manda igual que el tipo. Una carta de observación es correcta y
    # puede aprobar los seis controles, pero si el expediente está en el carril
    # del agente o en la cola de la mesa, todavía no es de nadie: la máquina de
    # estados no tiene `agente -> E4` ni `hitl -> E4` sin que una persona lo
    # mueva. Emitirla aquí sería adelantarse a esa decisión.
    borrador = tipo.startswith("niega") or ruta != "auto" or not res.aprobado

    return Emision(
        tipo=tipo, cuerpo=res.texto or cuerpo, borrador=borrador,
        aprobada=res.aprobado, citas=citas,
        citas_rechazadas=[c["texto"] for c in citas if not c["verificada"]],
        fuentes_declaradas=declaradas, fuentes_huerfanas=huerfanas,
        controles=[asdict(c) for c in res.controles],
        fundamentos_sin_fragmento=sin_fragmento,
        modelo=resp.modelo if resp else "", costo_usd=resp.costo_usd if resp else 0.0,
        tokens_in=resp.tokens_in if resp else 0,
        tokens_out=resp.tokens_out if resp else 0, latencia_ms=ms)


def persistir(cn, solicitud_id: str, adj_id: str, e: Emision,
              version_vigente: str, firma_id: str | None,
              copago: Decimal | None, forzar_emision: bool = False) -> str | None:
    """Guarda las citas verificadas y, si la carta se emite, la carta.

    El orden importa: `carta_cita` tiene un trigger que rechaza toda cita cuyo
    `verificada_literal` no sea true. O1 se cumple aquí dos veces —en el código y
    en la base—, y esa redundancia es deliberada: la del código evita el gasto,
    la de la base evita el dato.

    `forzar_emision` es la puerta del analista de la pantalla 4, y define con
    precisión qué puede y qué no puede hacer una persona:

    - **`borrador` sí se puede vencer.** Dice que *el sistema solo* no emite
      esto; una persona que lo revisa es exactamente lo que faltaba.
    - **`aprobada` no.** Los seis controles siguen mandando aunque quien
      pulse el botón sea el supervisor de la mesa. Un guardrail que una firma
      humana puede saltar no es un guardrail: es una sugerencia, y R2 dejaría
      de ser un invariante para volverse una costumbre.
    """
    ids_cita = []
    with cn.cursor() as cur:
        for c in e.citas:
            if not c["chunk_id"]:
                continue
            cita_id = repo.nuevo_id("CIT")
            cur.execute("""
                INSERT INTO cita (cita_id, adj_id, solicitud_id, chunk_id, doc_id_corpus,
                                  version_id, articulo, texto_literal, verificada_literal)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (cita_id, adj_id, solicitud_id, c["chunk_id"],
                  c["chunk_id"].split("-v")[0], c["version_id"], c["articulo"],
                  c["texto"], c["verificada"]))
            ids_cita.append((cita_id, c["verificada"]))

    if not e.aprobada or (e.borrador and not forzar_emision):
        return None

    carta_id = repo.nuevo_id("CAR")
    with cn.cursor() as cur:
        cur.execute("""
            INSERT INTO carta (carta_id, solicitud_id, tipo, version_politica,
                               firma_id, cuerpo, copago_pen, core_folio)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (carta_id, solicitud_id, e.tipo, version_vigente, firma_id, e.cuerpo,
              copago, repo.nuevo_id("FOLIO")))
        for cita_id, verificada in ids_cita:
            if verificada:
                cur.execute("INSERT INTO carta_cita (carta_id, cita_id) VALUES (%s,%s)",
                            (carta_id, cita_id))
    return carta_id
