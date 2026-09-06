"""Motor determinista de adjudicación — el invariante R1 del diseño.

    «Lo determinista nunca pasa por un modelo.»

Elegibilidad, carencia y copago se resuelven con integración y reglas. Ningún
modelo de lenguaje participa en este archivo, y esa es la razón por la que el
58% del valor capturable del caso de negocio —la fuga de copago— se recupera
sin IA. El modelo aparece después, y solo para lo interpretativo.

Cada conclusión sale acompañada del `fundamento`: la cláusula del corpus que la
sustenta. Es lo que permite que la carta cumpla R2 sin inventar la cita.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, asdict
from decimal import Decimal, ROUND_HALF_UP

# --------------------------------------------------------------------------
# Tabla de carencias — transcrita de `carencias_y_preexistencias.md`
# --------------------------------------------------------------------------

CARENCIAS = {
    "emergencia":        (0,   {"VIT-ESE", "VIT-INT", "VIT-PRE"}),
    "consulta":          (30,  {"VIT-ESE", "VIT-INT", "VIT-PRE"}),
    "examenes":          (30,  {"VIT-ESE", "VIT-INT", "VIT-PRE"}),
    "hospitalizacion":   (60,  {"VIT-ESE", "VIT-INT", "VIT-PRE"}),
    "terapia_fisica":    (90,  {"VIT-ESE", "VIT-INT", "VIT-PRE"}),
    "salud_mental":      (90,  {"VIT-INT", "VIT-PRE"}),
    "maternidad":        (300, {"VIT-INT", "VIT-PRE"}),
    "oncologico":        (180, {"VIT-ESE", "VIT-INT", "VIT-PRE"}),
    "bariatrica":        (540, {"VIT-PRE"}),
    "protesis":          (365, {"VIT-INT", "VIT-PRE"}),
}

# Qué cobertura gobierna cada procedimiento del catálogo del MVP.
COBERTURA_DE = {
    "PRC-4712": "hospitalizacion",
    "PRC-2933": "hospitalizacion",
    "PRC-5901": "maternidad",
    "PRC-1180": "hospitalizacion",
    "PRC-8104": "protesis",
    "PRC-6620": "hospitalizacion",
}

# Sustento clínico mínimo — transcrito de `protocolos_de_procedimientos_quirurgicos.md`.
DOCUMENTOS_EXIGIDOS = {
    "PRC-4712": ["orden_medica", "informe_medico", "ecografia_abdominal"],
    "PRC-2933": ["orden_medica", "informe_medico", "resonancia_magnetica", "informe_terapia_fisica"],
    "PRC-5901": ["orden_medica", "informe_medico", "ecografia_obstetrica", "control_prenatal"],
    "PRC-1180": ["orden_medica", "informe_medico"],
    "PRC-8104": ["orden_medica", "informe_medico", "radiografia", "informe_conservador"],
    "PRC-6620": ["orden_medica", "informe_medico", "ecografia_transvaginal"],
}

NOMBRE_DOCUMENTO = {
    "orden_medica": "orden médica firmada por el médico tratante, con colegiatura",
    "informe_medico": "informe médico que sustenta la indicación",
    "ecografia_abdominal": "ecografía abdominal con informe radiológico",
    "resonancia_magnetica": "resonancia magnética con informe radiológico",
    "informe_terapia_fisica": "informe de terapia física de al menos seis semanas",
    "ecografia_obstetrica": "ecografía obstétrica del tercer trimestre",
    "control_prenatal": "control prenatal vigente",
    "radiografia": "radiografía con grado de artrosis (Kellgren-Lawrence)",
    "informe_conservador": "informe de tratamiento conservador de al menos seis meses",
    "ecografia_transvaginal": "ecografía transvaginal",
}

# Fundamento normativo de cada regla: doc_id del corpus + artículo.
#
# Estas parejas **tienen que resolver** a un fragmento real del corpus vigente:
# son las que la carta va a citar textualmente para cumplir R2. `elegibilidad`
# apuntaba a «Vigencia de la cobertura», un artículo que no existe en v2026_09;
# nadie lo notó mientras nada resolvía los fundamentos a fragmentos, y habría
# producido una carta con un fundamento declarado y sin cita que lo sustente.
# `prueba_carril1` verifica ahora que todas las parejas resuelvan, para que este
# defecto no pueda volver en silencio con la siguiente versión de política.
FUNDAMENTO = {
    "elegibilidad": ("afiliacion_y_dependientes", "Inicio de vigencia"),
    "suspension": ("facturacion_y_pagos", "Suspensión de cobertura por mora"),
    # Es la cláusula que separa el rechazo administrativo de la negación
    # clínica, y por tanto la que decide si la carta necesita firma (R3/O4).
    "causal_administrativa": ("protocolos_de_procedimientos_quirurgicos",
                              "Qué no puede resolverse sin médico colegiado"),
    "carencia": ("carencias_y_preexistencias", "Tabla de carencias por cobertura"),
    "carencia_maternidad": ("carencias_y_preexistencias", "Carencia de maternidad"),
    "deducible": ("deducibles_y_copagos", "Deducible anual por afiliado"),
    "coaseguro": ("deducibles_y_copagos", "Coaseguro hospitalario"),
    "copago_parto": ("deducibles_y_copagos", "Copago de parto"),
    "tope": ("deducibles_y_copagos", "Tope máximo de gasto anual del afiliado"),
    "documentos": ("protocolos_de_procedimientos_quirurgicos", "Documentos exigibles a toda solicitud programada"),
}

DOS = Decimal("0.01")


def _redondear(x: Decimal) -> Decimal:
    return Decimal(x).quantize(DOS, rounding=ROUND_HALF_UP)


@dataclass
class ResultadoDeterminista:
    elegible: bool
    motivo_elegibilidad: str
    carencia_ok: bool
    carencia_dias_exigidos: int
    carencia_dias_afiliado: int
    cobertura: str                      # cubierto | no_cubierto | requiere_juicio
    motivo_cobertura: str
    copago_pen: Decimal | None
    copago_desglose: dict = field(default_factory=dict)
    documentos_faltantes: list[str] = field(default_factory=list)
    fundamentos: list[tuple[str, str]] = field(default_factory=list)

    def como_dict(self) -> dict:
        d = asdict(self)
        d["copago_pen"] = None if self.copago_pen is None else float(self.copago_pen)
        d["copago_desglose"] = {k: (float(v) if isinstance(v, Decimal) else v)
                                for k, v in self.copago_desglose.items()}
        d["fundamentos"] = [list(f) for f in self.fundamentos]
        return d


def adjudicar(afiliado: dict, solicitud: dict, tarifa: dict | None,
              documentos_presentes: list[str],
              hoy: dt.date | None = None) -> ResultadoDeterminista:
    """Adjudica lo que es aritmética y calendario. Nada de esto es opinable."""
    hoy = hoy or dt.date.today()
    fundamentos: list[tuple[str, str]] = []
    plan = afiliado["plan_codigo"]
    proc = solicitud["procedimiento_codigo"]

    # --- 1 · Elegibilidad --------------------------------------------------
    elegible = afiliado["estado"] == "activo"
    motivo_eleg = ("afiliación activa" if elegible
                   else f"afiliación en estado «{afiliado['estado']}»")
    fundamentos.append(FUNDAMENTO["elegibilidad"])
    if not elegible:
        # La cláusula que sustenta el rechazo no es la de vigencia general sino
        # la de suspensión, y es la que la carta tiene que poder citar.
        fundamentos.append(FUNDAMENTO["suspension"])

    # --- 2 · Carencia ------------------------------------------------------
    clave = COBERTURA_DE.get(proc, "hospitalizacion")
    dias_exigidos, planes_con_cobertura = CARENCIAS[clave]
    dias_afiliado = (hoy - afiliado["afiliado_desde"]).days
    carencia_ok = dias_afiliado >= dias_exigidos
    fundamentos.append(FUNDAMENTO["carencia_maternidad"] if clave == "maternidad"
                       else FUNDAMENTO["carencia"])

    # --- 3 · Cobertura -----------------------------------------------------
    if plan not in planes_con_cobertura:
        cobertura, motivo = "no_cubierto", f"el plan {plan} no incluye la cobertura de {clave}"
    elif tarifa is None:
        cobertura, motivo = "no_cubierto", f"el procedimiento {proc} no está en el tarifario del plan {plan}"
    elif not elegible:
        cobertura, motivo = "no_cubierto", motivo_eleg
    elif not carencia_ok:
        cobertura = "no_cubierto"
        motivo = (f"carencia de {clave} no cumplida: exige {dias_exigidos} días "
                  f"y el afiliado tiene {dias_afiliado}")
    else:
        cobertura, motivo = "cubierto", "elegible, sin carencia pendiente y dentro del tarifario del plan"

    # --- 4 · Copago --------------------------------------------------------
    copago = None
    desglose: dict = {}
    if cobertura == "cubierto" and tarifa is not None:
        tarifa_pen = Decimal(str(tarifa["tarifa_pen"]))
        fijo = Decimal(str(tarifa["copago_fijo_pen"]))
        if fijo > 0:
            # Maternidad: copago fijo que reemplaza deducible y coaseguro.
            copago = _redondear(fijo)
            desglose = {"regla": "copago fijo de parto", "copago_fijo": fijo,
                        "deducible": Decimal("0.00"), "coaseguro": Decimal("0.00")}
            fundamentos.append(FUNDAMENTO["copago_parto"])
        else:
            pendiente = (Decimal(str(afiliado["deducible_anual"]))
                         - Decimal(str(afiliado["deducible_consumido"])))
            deducible = max(Decimal("0.00"), min(pendiente, tarifa_pen))
            base = tarifa_pen - deducible
            pct = Decimal(str(tarifa["coaseguro_pct"])) / Decimal("100")
            coaseguro = _redondear(base * pct)
            copago = _redondear(deducible + coaseguro)
            desglose = {"regla": "deducible pendiente + coaseguro sobre el saldo",
                        "tarifa": tarifa_pen, "deducible": _redondear(deducible),
                        "base_coaseguro": _redondear(base),
                        "coaseguro_pct": Decimal(str(tarifa["coaseguro_pct"])),
                        "coaseguro": coaseguro}
            fundamentos += [FUNDAMENTO["deducible"], FUNDAMENTO["coaseguro"]]

        tope = tarifa.get("tope_copago_pen")
        if tope is not None:
            # El acumulado de gasto de bolsillo del año lo lleva el core. Aquí el
            # único acumulador disponible es `deducible_consumido`, así que el MVP
            # lo usa como proxy: en producción es una lectura al core (ADR-18).
            tope = Decimal(str(tope))
            gastado = Decimal(str(afiliado["deducible_consumido"]))
            disponible = max(Decimal("0.00"), tope - gastado)
            if copago > disponible:
                desglose["tope_aplicado"] = tope
                desglose["copago_antes_del_tope"] = copago
                copago = _redondear(disponible)
                fundamentos.append(FUNDAMENTO["tope"])

    # --- 5 · Suficiencia documental ---------------------------------------
    exigidos = DOCUMENTOS_EXIGIDOS.get(proc, ["orden_medica", "informe_medico"])
    faltantes = [d for d in exigidos if d not in set(documentos_presentes)]
    if faltantes:
        fundamentos.append(FUNDAMENTO["documentos"])

    return ResultadoDeterminista(
        elegible=elegible, motivo_elegibilidad=motivo_eleg,
        carencia_ok=carencia_ok, carencia_dias_exigidos=dias_exigidos,
        carencia_dias_afiliado=dias_afiliado,
        cobertura=cobertura, motivo_cobertura=motivo,
        copago_pen=copago, copago_desglose=desglose,
        documentos_faltantes=faltantes,
        fundamentos=list(dict.fromkeys(fundamentos)),
    )


# --------------------------------------------------------------------------
# Ruteo E3 — qué hace el sistema con el resultado
# --------------------------------------------------------------------------

def rutear(r: ResultadoDeterminista) -> tuple[str, str]:
    """El sistema automático puede autorizar o escalar. **Nunca negar** (ADR-10).

    Por eso `no_cubierto` no produce una negación automática: produce un
    expediente escalado con el borrador y la cita, y la decisión la firma una
    persona.
    """
    if r.documentos_faltantes:
        return "agente", ("falta sustento clínico: "
                          + ", ".join(NOMBRE_DOCUMENTO.get(d, d) for d in r.documentos_faltantes))
    if r.cobertura == "cubierto":
        return "auto", "determinista completo, sin juicio clínico pendiente"
    if not r.elegible:
        return "hitl", "afiliación no vigente: causal administrativa, la revisa la mesa"
    if not r.carencia_ok:
        return "hitl", ("carencia no cumplida: el sistema no emite la negación, "
                        "escala con la cita y el borrador")
    return "hitl", r.motivo_cobertura
