"""E1 · Extracción del expediente — sesión 04 (data pipelines, document processing).

El prestador manda texto libre: un correo, el cuerpo de un formulario, lo que el
OCR sacó de una orden médica. E1 lo convierte en los seis campos con los que el
motor determinista puede trabajar.

La regla que gobierna este archivo:

    **El modelo propone, el catálogo dispone.**

El modelo es bueno leyendo prosa y malo garantizando que `PRC-4712` exista. Así
que todo campo que salga de aquí se contrasta contra la tabla que manda —
`catalogo_procedimiento`, `catalogo_cie10`, `core_afiliado`— y el resultado de
ese contraste, no la confianza que declaró el modelo, es lo que decide si el
expediente sigue. La confianza se guarda para la traza y no decide nada: un
modelo seguro de un código inexistente sigue estando equivocado.

Consecuencia de diseño: E1 nunca inventa un campo faltante. Si el procedimiento
no está en el catálogo, el expediente no avanza a E2 —se va a subsanación con el
agente—, porque adjudicar sobre un código que no existe es adjudicar sobre nada.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, asdict

from comun import repositorio as repo, router_modelos

CAMPOS_OBLIGATORIOS = ("afiliado_ref", "prestador_id", "dx_cie10",
                       "procedimiento_codigo", "tipo")

# Los cinco campos van descritos por su **forma**, no por su significado. La
# primera versión describía `prestador_id` como «el identificador de la clínica
# tal como aparece» —era el único de los cinco sin una forma— y el modelo devolvió
# `null` sobre un texto que decía «Clínica San Felipe (PRE-0031)» en la primera
# línea. No se equivocó al leer: se equivocó al decidir qué contaba como
# identificador. Un campo descrito por su rol es un campo que el modelo tiene que
# interpretar; uno descrito por su forma es un campo que solo tiene que encontrar.

# Vocabulario cerrado de documentos. Es catálogo igual que los códigos: si el
# prestador adjunta «eco abdominal», el valor que entra al expediente es
# `ecografia_abdominal` o no entra.
TIPOS_DOCUMENTO = (
    "orden_medica", "informe_medico", "ecografia_abdominal", "resonancia_magnetica",
    "informe_terapia_fisica", "ecografia_obstetrica", "control_prenatal",
    "radiografia", "informe_conservador", "ecografia_transvaginal",
)

SISTEMA = """Extraes los datos de una solicitud de preautorización de Vitalia Salud
EPS y devuelves **solo** un objeto JSON, sin texto alrededor.

Claves y formato exacto:

  afiliado_ref           "AF-" y seis dígitos
  prestador_id           "PRE-" y cuatro dígitos; suele ir entre paréntesis
                         junto al nombre de la clínica o el policlínico
  dx_cie10               código CIE-10, letra y dos dígitos, con decimal si lo trae
  procedimiento_codigo   "PRC-" y cuatro dígitos
  tipo                   uno de: programado, urgente, extranjero
  documentos             lista con los documentos adjuntos, usando SOLO estas
                         etiquetas: {etiquetas}
  confianza              objeto con un número de 0 a 1 por cada clave anterior

Reglas:

- Si un dato no aparece en el texto, pon null y confianza 0. **No lo deduzcas ni
  lo completes con un valor plausible.**
- No traduzcas ni normalices los códigos: cópialos como están escritos.
- Un documento que se menciona como faltante, pendiente o por enviar **no** va en
  `documentos`."""


@dataclass
class Campo:
    campo: str
    valor: str | list | None
    confianza: float
    validado_catalogo: bool
    nota: str = ""


@dataclass
class Extraccion:
    campos: list[Campo] = field(default_factory=list)
    completa: bool = False
    motivo_incompleta: str = ""
    modelo: str = ""
    costo_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    latencia_ms: int = 0
    truncada: bool = False

    def valor(self, campo: str):
        return next((c.valor for c in self.campos if c.campo == campo), None)

    def como_dict(self) -> dict:
        d = asdict(self)
        d["campos"] = [asdict(c) for c in self.campos]
        return d


def _validadores(cn) -> dict:
    """Las tres validaciones son consultas al catálogo, no expresiones regulares.

    Una expresión regular confirma que `PRC-9999` tiene la forma de un código;
    solo la tabla confirma que existe, y la diferencia entre ambas cosas es la
    solicitud que se adjudica contra un procedimiento inventado.
    """
    return {
        "procedimiento_codigo": lambda v: repo.obtener_procedimiento(cn, v) is not None,
        "afiliado_ref": lambda v: repo.obtener_afiliado(cn, v) is not None,
        "dx_cie10": lambda v: _existe_cie10(cn, v),
        "tipo": lambda v: v in ("programado", "urgente", "extranjero"),
        # `prestador_id` es el único campo obligatorio sin tabla contra la cual
        # contrastarlo: el MVP no tiene registro de prestadores, así que aquí solo
        # se verifica la forma. **Es una brecha conocida y no un descuido**: un
        # prestador con el código mal escrito entra al expediente y solo se
        # detecta al facturar. El diseño lo resuelve leyendo el maestro de
        # prestadores del core (ADR-18), que en el MVP no está montado; hasta
        # entonces, `validado_catalogo` de este campo dice menos que el de los
        # otros cuatro, y la evidencia tiene que decirlo así.
        "prestador_id": lambda v: bool(re.fullmatch(r"[A-Za-z]{2,6}-?\d{2,6}", v)),
    }


# Campos cuyo `validado_catalogo` significa «existe en una tabla». El resto se
# valida por forma, y la distinción importa para leer la evidencia.
CON_CATALOGO = ("procedimiento_codigo", "afiliado_ref", "dx_cie10")


def _existe_cie10(cn, codigo: str) -> bool:
    with cn.cursor() as cur:
        cur.execute("SELECT 1 FROM catalogo_cie10 WHERE codigo = %s", (codigo,))
        return cur.fetchone() is not None


def extraer(cn, texto_solicitud: str) -> Extraccion:
    ruta = router_modelos.elegir("e1_extraccion")
    t0 = time.time()
    r = router_modelos.completar(
        ruta, SISTEMA.format(etiquetas=", ".join(TIPOS_DOCUMENTO)),
        texto_solicitud, formato_json=True)
    ms = int((time.time() - t0) * 1000)

    if r.truncada:
        return Extraccion(completa=False, motivo_incompleta="la extracción se truncó",
                          modelo=r.modelo, costo_usd=r.costo_usd, tokens_in=r.tokens_in,
                          tokens_out=r.tokens_out, latencia_ms=ms, truncada=True)

    try:
        crudo = json.loads(r.texto)
    except json.JSONDecodeError:
        return Extraccion(completa=False, motivo_incompleta="la extracción no devolvió JSON",
                          modelo=r.modelo, costo_usd=r.costo_usd, tokens_in=r.tokens_in,
                          tokens_out=r.tokens_out, latencia_ms=ms)

    confianzas = crudo.get("confianza") or {}
    validadores = _validadores(cn)
    campos: list[Campo] = []
    faltantes: list[str] = []

    for nombre in CAMPOS_OBLIGATORIOS:
        valor = crudo.get(nombre)
        conf = float(confianzas.get(nombre) or 0.0)
        if valor in (None, "", "null"):
            campos.append(Campo(nombre, None, 0.0, False, "ausente en el texto"))
            faltantes.append(nombre)
            continue
        valor = str(valor).strip()
        ok = validadores[nombre](valor)
        nota = "" if ok else ("no existe en el catálogo vigente" if nombre in CON_CATALOGO
                              else "no tiene la forma esperada")
        campos.append(Campo(nombre, valor, round(min(max(conf, 0.0), 1.0), 3), ok, nota))
        if not ok:
            faltantes.append(nombre)

    # Los documentos se filtran contra el vocabulario cerrado. Lo que el modelo
    # nombre fuera de esa lista se descarta con nota: no es un dato del que el
    # motor pueda concluir nada, y dejarlo pasar contaminaría la suficiencia
    # documental con etiquetas que `DOCUMENTOS_EXIGIDOS` nunca va a reconocer.
    brutos = crudo.get("documentos") or []
    reconocidos = [d for d in brutos if d in TIPOS_DOCUMENTO]
    ajenos = [d for d in brutos if d not in TIPOS_DOCUMENTO]
    campos.append(Campo("documentos", reconocidos,
                        round(float(confianzas.get("documentos") or 0.0), 3),
                        not ajenos,
                        "" if not ajenos else f"etiquetas descartadas: {', '.join(map(str, ajenos))}"))

    completa = not faltantes
    return Extraccion(
        campos=campos, completa=completa,
        motivo_incompleta="" if completa else
        f"campos sin valor válido en el catálogo: {', '.join(faltantes)}",
        modelo=r.modelo, costo_usd=r.costo_usd, tokens_in=r.tokens_in,
        tokens_out=r.tokens_out, latencia_ms=ms)


def persistir(cn, solicitud_id: str, e: Extraccion) -> None:
    with cn.cursor() as cur:
        for c in e.campos:
            cur.execute("""
                INSERT INTO extraccion
                    (solicitud_id, campo, valor, confianza, validado_catalogo, modelo)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (solicitud_id, c.campo,
                  json.dumps(c.valor, ensure_ascii=False) if isinstance(c.valor, list)
                  else c.valor,
                  c.confianza, c.validado_catalogo, e.modelo))
