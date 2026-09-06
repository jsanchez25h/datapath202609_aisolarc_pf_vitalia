"""Guardrail de salida O1–O6 — `06_seguridad_y_evaluacion.md` §4.

El de entrada protege al sistema; este protege al afiliado, y es el que sostiene
R2 y R3. **Es determinista: son verificaciones, no un modelo juzgando a otro.**

    O1  la cita existe literalmente        → descarta y escala
    O2  la versión citada estaba vigente   → reindexa con la versión correcta
    O3  copago del texto == copago del motor → bloquea la emisión
    O4  sin negación clínica sin firma     → rechazo de la transacción
    O5  sin PII fuera de destino           → enmascara
    O6  todo código emitido existe en el catálogo vigente → escala

O3 es la verificación más valiosa y es gratis: existe porque el cálculo
determinista y la redacción son caminos separados que deben coincidir. Si el
copago se lo hubiéramos pedido al modelo, no habría con qué contrastarlo.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field, asdict
from decimal import Decimal

from comun import recuperacion

# «S/ 1,210.00», «S/1210», «S/. 1 210,00» — todas las formas en que un texto en
# español peruano puede escribir un monto.
MONTO = re.compile(r"S/\.?\s*([0-9][0-9\s.,]*)")


@dataclass
class Control:
    codigo: str
    nombre: str
    paso: bool
    detalle: str = ""
    accion: str = ""


@dataclass
class Resultado:
    aprobado: bool
    controles: list[Control] = field(default_factory=list)
    texto: str = ""

    def como_dict(self) -> dict:
        return {"aprobado": self.aprobado, "controles": [asdict(c) for c in self.controles]}


def _montos(texto: str) -> list[Decimal]:
    """Extrae todo monto en soles que aparezca en la prosa."""
    salida = []
    for bruto in MONTO.findall(texto):
        limpio = bruto.strip().rstrip(".,")
        limpio = re.sub(r"\s", "", limpio)
        # Separador de miles y decimal a la peruana: 1,210.00
        if "," in limpio and "." in limpio:
            limpio = limpio.replace(",", "")
        elif "," in limpio:
            entero, _, resto = limpio.rpartition(",")
            limpio = f"{entero.replace(',', '')}.{resto}" if len(resto) == 2 else limpio.replace(",", "")
        try:
            salida.append(Decimal(limpio))
        except Exception:
            continue
    return salida


# --------------------------------------------------------------------------

def o1_citas_literales(citas: list[dict], fragmentos_por_chunk: dict,
                       sin_origen: list[str] | None = None,
                       exige_al_menos_una: bool = True) -> Control:
    """`citas` son los fragmentos que la carta invoca; cada uno trae el `texto`
    que la redacción presentó como cita textual.

    `sin_origen` son los tramos entrecomillados que la carta presentó como cita
    y que **no correspondieron a ningún fragmento**. Van aparte porque no tienen
    `chunk_id` con el que entrar en la lista anterior, y omitirlos convertiría el
    peor caso —una cita inventada de raíz— en el único que O1 no mira.

    `exige_al_menos_una` cierra el agujero por el que este control se dejaba
    aprobar por vacío. Verificar que «todas las citas son correctas» es una
    afirmación trivialmente cierta sobre una carta que no cita nada, y el MVP
    produjo exactamente eso: una carta de negación administrativa, con su causal
    redactada, **sin una sola comilla**, aprobada por O1 con «las 0 citas
    coinciden carácter por carácter». Es el defecto más grave que apareció en el
    Carril 1, porque no se manifiesta como un fallo sino como un acierto.

    R2 no dice «las citas que haya deben ser correctas»: dice que ninguna
    afirmación sobre la política va sin cita textual de la versión vigente. Toda
    carta de esta mesa afirma algo sobre la política —autoriza según una tabla,
    niega por una carencia, observa porque un protocolo exige un documento—, así
    que ninguna puede salir sin al menos una cita verificada.
    """
    fallidas = []
    for c in citas:
        fr = fragmentos_por_chunk.get(c["chunk_id"])
        if fr is None or not recuperacion.verificar_cita_literal(c["texto"], fr):
            fallidas.append(c["chunk_id"])
    huerfanas = list(sin_origen or [])
    verificadas = len(citas) - len(fallidas)
    sin_ninguna = exige_al_menos_una and verificadas == 0
    paso = not fallidas and not huerfanas and not sin_ninguna
    if paso:
        detalle = f"las {len(citas)} citas coinciden carácter por carácter"
    else:
        partes = []
        if sin_ninguna:
            partes.append("la carta afirma sobre la política y no cita ninguna cláusula")
        if fallidas:
            partes.append(f"no verificadas: {', '.join(fallidas)}")
        if huerfanas:
            partes.append(f"{len(huerfanas)} cita(s) sin fragmento de origen: "
                          + "; ".join(f"«{h[:60]}…»" for h in huerfanas))
        detalle = " · ".join(partes)
    return Control("O1", "La cita existe literalmente", paso, detalle,
                   "" if paso else "descartar la respuesta y escalar")


def o2_version_vigente(citas: list[dict], version_vigente: str,
                       fecha_solicitud: dt.date, vigencia_desde: dt.date,
                       vigencia_hasta: dt.date | None = None) -> Control:
    ajenas = sorted({c["version_id"] for c in citas if c["version_id"] != version_vigente})
    en_rango = (vigencia_desde <= fecha_solicitud
                and (vigencia_hasta is None or fecha_solicitud <= vigencia_hasta))
    paso = not ajenas and en_rango
    detalle = (f"todas las citas son de {version_vigente}, vigente el {fecha_solicitud}"
               if paso else
               (f"citas de otra versión: {', '.join(ajenas)}" if ajenas
                else f"{version_vigente} no estaba vigente el {fecha_solicitud}"))
    return Control("O2", "La versión citada estaba vigente", paso, detalle,
                   "" if paso else "reindexar la consulta con la versión correcta")


def o3_consistencia(texto: str, copago_motor: Decimal | float | None,
                    desglose: dict | None = None,
                    exige_presencia: bool = False) -> Control:
    """El contraste determinista ↔ prosa.

    Lo que este control persigue es la **contradicción**, no la omisión: ningún
    importe de la carta puede ser un número que el motor no haya calculado. Una
    carta de autorización que no menciona el copago está incompleta y el afiliado
    vuelve a preguntar; una carta que dice S/ 640.00 donde el motor calculó
    S/ 1,660.00 le da al afiliado un número que la clínica no va a respetar, y ese
    es el reclamo de S/ 340 del caso de negocio.

    **El universo de comparación es el desglose, no solo el copago.** La primera
    versión comparaba cada importe de la prosa contra el copago y nada más, y
    bloqueó una carta correcta: el motor calculó S/ 1,210.00 de copago, la carta
    lo dijo bien y además explicó que el deducible del plan es de S/ 600 —cifra
    que el propio motor calculó, y que estaba en la cláusula citada—. Prohibirle a
    la carta que explique la aritmética que la sustenta no es controlarla: es
    obligarla a dar el resultado sin el razonamiento, que es justo lo que el
    afiliado no entiende hoy. Lo que sí queda prohibido es un importe que no salga
    de ningún cálculo del motor.

    `exige_presencia` añade la omisión como falla, y se activa solo para la carta
    de autorización, que es donde el copago **es** el contenido operativo.
    """
    montos = _montos(texto)
    calculados = set()
    if copago_motor is not None:
        calculados.add(Decimal(str(copago_motor)))
    for k, v in (desglose or {}).items():
        # `coaseguro_pct` es un porcentaje, no soles. Admitirlo dejaría pasar
        # «S/ 5.00» en la prosa por el solo hecho de que el coaseguro es 5%.
        if "pct" in k:
            continue
        if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
            calculados.add(Decimal(str(v)))

    if copago_motor is None:
        # Sin copago no hay aritmética que explicar: cualquier importe en la
        # prosa es un número que la carta se inventó.
        paso = not montos
        return Control("O3", "Consistencia determinista ↔ prosa", paso,
                       "el motor no calculó copago y la carta no afirma ninguno" if paso
                       else f"la carta menciona {', '.join('S/ ' + str(m) for m in montos)} "
                            f"sin respaldo del motor",
                       "" if paso else "bloquear la emisión")

    esperado = Decimal(str(copago_motor))
    ajenos = [m for m in montos if m not in calculados]
    ausente = exige_presencia and esperado not in montos
    paso = not ajenos and not ausente
    if paso:
        detalle = (f"la carta dice S/ {esperado} y el motor calculó S/ {esperado}"
                   + (f"; los demás importes ({len(montos) - 1}) son del desglose"
                      if len(montos) > 1 else "")
                   if esperado in montos
                   else f"la carta no cita montos y el motor calculó S/ {esperado}")
    elif ajenos:
        detalle = (f"el motor calculó S/ {esperado} y la carta afirma "
                   f"{', '.join('S/ ' + str(m) for m in ajenos)}, que no sale de "
                   f"ningún cálculo del motor")
    else:
        detalle = f"la carta autoriza sin decir el copago de S/ {esperado}"
    return Control("O3", "Consistencia determinista ↔ prosa", paso, detalle,
                   "" if paso else "bloquear la emisión: un desacuerdo aquí es un defecto")


def o4_firma_si_niega(tipo_carta: str, firma_id: str | None) -> Control:
    """Espejo en código de la restricción `r3_firma_obligatoria` de la base.

    La verificación está aquí *además de* en el CHECK porque una carta que llega
    hasta el INSERT y revienta ya consumió el flujo; el control la detiene antes.
    """
    paso = tipo_carta != "niega_necesidad_medica" or bool(firma_id)
    return Control("O4", "Sin negación clínica sin firma", paso,
                   "no es una negación por necesidad médica" if tipo_carta != "niega_necesidad_medica"
                   else (f"firmada por {firma_id}" if firma_id else "negación clínica sin firma"),
                   "" if paso else "rechazo de la transacción")


def o5_sin_pii(texto: str, destino: str) -> tuple[Control, str]:
    """La carta al titular sí lleva su nombre: es suya. Todo lo demás —traza,
    tablero, log— va enmascarado."""
    if destino == "carta_titular":
        return Control("O5", "Sin PII fuera de destino", True,
                       "destino es el titular: la carta lleva sus datos por diseño"), texto
    from guardrails import entrada as ge
    hallazgo, limpio = ge.capa5_pii(texto)
    hubo = hallazgo.decision == ge.TRANSFORMAR
    return Control("O5", "Sin PII fuera de destino", True,
                   f"destino «{destino}»: {hallazgo.detalle}" if hubo
                   else f"destino «{destino}»: sin PII detectada",
                   "enmascarado" if hubo else ""), limpio


CODIGO_EMITIDO = re.compile(r"\b(PRC-\d{4}|[A-TV-Z]\d{2}(?:\.\d)?)\b")


def o6_catalogo(texto: str, codigos_validos: set[str],
                fuentes_huerfanas: list[str] | None = None,
                fundamentos_sin_fragmento: list | None = None) -> Control:
    """Tres huérfanos distintos, un solo control: nada de lo que la carta nombra
    puede apuntar fuera del catálogo y del corpus vigentes.

    - un código de procedimiento o diagnóstico que no existe;
    - un identificador declarado en `FUENTES:` que no estuvo en el contexto
      —la carta cita bien y firma una fuente que nadie puede abrir—;
    - un fundamento del motor que no resolvió a ninguna cláusula, es decir una
      conclusión declarada sin norma que la sustente.

    Los tres rompen la reconstruibilidad (veto V2): quien fiscalice la carta
    tiene que poder llegar del párrafo al artículo, y con cualquiera de los tres
    el camino se corta.
    """
    encontrados = set(CODIGO_EMITIDO.findall(texto))
    huerfanos = sorted(encontrados - codigos_validos)
    fuentes = list(fuentes_huerfanas or [])
    fundamentos = [f"{d} § {a}" for d, a in (fundamentos_sin_fragmento or [])]
    paso = not huerfanos and not fuentes and not fundamentos
    if paso:
        detalle = (f"{len(encontrados)} código(s), las fuentes declaradas y los "
                   f"fundamentos del motor resuelven contra el corpus vigente")
    else:
        partes = []
        if huerfanos:
            partes.append(f"códigos inexistentes: {', '.join(huerfanos)}")
        if fuentes:
            partes.append(f"FUENTES fuera del contexto: {', '.join(fuentes)}")
        if fundamentos:
            partes.append(f"fundamentos sin cláusula: {', '.join(fundamentos)}")
        detalle = " · ".join(partes)
    return Control("O6", "Esquema y catálogo", paso, detalle,
                   "" if paso else "escalar")


# --------------------------------------------------------------------------

def evaluar(texto: str, *, citas: list[dict], fragmentos_por_chunk: dict,
            copago_motor, version_vigente: str, fecha_solicitud: dt.date,
            vigencia_desde: dt.date, tipo_carta: str, firma_id: str | None,
            codigos_validos: set[str], copago_desglose: dict | None = None,
            destino: str = "carta_titular",
            citas_sin_verificar: list[str] | None = None,
            fuentes_huerfanas: list[str] | None = None,
            fundamentos_sin_fragmento: list | None = None) -> Resultado:
    """Los seis controles corren **siempre y completos**, aunque uno ya haya
    fallado. Es lo contrario del guardrail de entrada, que corta en la primera
    capa que bloquea: allí lo que importa es no gastar, aquí lo que importa es
    que el expediente diga todo lo que estaba mal con la carta. Un auditor que
    lee «falló O1» y arregla la cita no puede descubrir después que además el
    monto no cuadraba.
    """
    controles = [
        o1_citas_literales(citas, fragmentos_por_chunk, citas_sin_verificar),
        o2_version_vigente(citas, version_vigente, fecha_solicitud, vigencia_desde),
        o3_consistencia(texto, copago_motor, copago_desglose,
                        exige_presencia=tipo_carta == "autoriza"),
        o4_firma_si_niega(tipo_carta, firma_id),
    ]
    c5, limpio = o5_sin_pii(texto, destino)
    controles.append(c5)
    controles.append(o6_catalogo(texto, codigos_validos, fuentes_huerfanas,
                                 fundamentos_sin_fragmento))
    return Resultado(aprobado=all(c.paso for c in controles),
                     controles=controles, texto=limpio)


def persistir(cn, solicitud_id: str, r: Resultado) -> None:
    with cn.cursor() as cur:
        for i, c in enumerate(r.controles):
            cur.execute("""
                INSERT INTO evaluacion_guardrail
                    (solicitud_id, sentido, capa, categoria, decision, posicion, detalle)
                VALUES (%s,'salida',%s,%s,%s,%s,%s)
            """, (solicitud_id, c.codigo, c.nombre,
                  "PERMITIR" if c.paso else "BLOQUEAR", i + 1, c.detalle))
