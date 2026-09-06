"""Los tres casos de la rebanada, resueltos por el motor determinista.

Cada caso demuestra una ruta distinta de E3, y el tercero demuestra la tesis del
proyecto: ante una carencia incumplida el sistema **no niega**, escala.

    python -m pruebas.prueba_motor
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comun import config, motor_determinista as motor, repositorio as repo  # noqa: E402

CASOS = [
    {
        "id": "C1",
        "titulo": "Colecistectomía laparoscópica · VIT-INT · 14 meses de afiliación",
        "demuestra": "autorización automática (STP): determinista puro, sin modelo",
        "afiliado_ref": "AF-100234",
        "procedimiento_codigo": "PRC-4712",
        "dx_cie10": "K80.2",
        "documentos": ["orden_medica", "informe_medico", "ecografia_abdominal"],
        "espera_ruta": "auto",
    },
    {
        "id": "C2",
        "titulo": "Artroscopia de rodilla · VIT-ESE · sin informe de terapia física",
        "demuestra": "subsanación: el único punto del flujo donde hay un agente",
        "afiliado_ref": "AF-100777",
        "procedimiento_codigo": "PRC-2933",
        "dx_cie10": "M23.2",
        "documentos": ["orden_medica", "informe_medico", "resonancia_magnetica"],
        "espera_ruta": "agente",
    },
    {
        "id": "C3",
        "titulo": "Cesárea programada · VIT-INT · 220 días de afiliación",
        "demuestra": "ruteo a médico auditor: el sistema no puede negar (ADR-10)",
        "afiliado_ref": "AF-100512",
        "procedimiento_codigo": "PRC-5901",
        "dx_cie10": "O82.0",
        "documentos": ["orden_medica", "informe_medico",
                       "ecografia_obstetrica", "control_prenatal"],
        "espera_ruta": "hitl",
    },
]


def main() -> int:
    config.configurar_consola()
    cn = config.conexion_pg()
    salida = []
    fallos = 0

    for caso in CASOS:
        afiliado = repo.obtener_afiliado(cn, caso["afiliado_ref"])
        tarifa = repo.obtener_tarifa(cn, caso["procedimiento_codigo"], afiliado["plan_codigo"])
        proc = repo.obtener_procedimiento(cn, caso["procedimiento_codigo"])

        r = motor.adjudicar(afiliado, caso, tarifa, caso["documentos"])
        ruta, motivo_ruta = motor.rutear(r)
        ok = ruta == caso["espera_ruta"]
        fallos += 0 if ok else 1

        print(f"\n{'=' * 78}\n{caso['id']} · {caso['titulo']}\n{'-' * 78}")
        print(f"  demuestra ............ {caso['demuestra']}")
        print(f"  afiliado ............. {afiliado['nombre']} · {afiliado['plan_codigo']} "
              f"· {afiliado['estado']} · {r.carencia_dias_afiliado} días")
        print(f"  procedimiento ........ {proc['descripcion']} ({proc['codigo']})")
        print(f"  tarifa ............... "
              f"{'S/ ' + str(tarifa['tarifa_pen']) if tarifa else 'sin fila en el tarifario del plan'}")
        print(f"  carencia ............. exige {r.carencia_dias_exigidos} · "
              f"{'CUMPLE' if r.carencia_ok else 'NO CUMPLE'}")
        print(f"  cobertura ............ {r.cobertura} — {r.motivo_cobertura}")
        print(f"  copago ............... "
              f"{'S/ ' + str(r.copago_pen) if r.copago_pen is not None else '—'}")
        for k, v in r.copago_desglose.items():
            print(f"      {k:<22} {v}")
        if r.documentos_faltantes:
            print(f"  falta ................ "
                  f"{', '.join(motor.NOMBRE_DOCUMENTO[d] for d in r.documentos_faltantes)}")
        print(f"  fundamento ........... "
              + "; ".join(f"{d} § {a}" for d, a in r.fundamentos))
        print(f"  RUTA ................. {ruta}  ({motivo_ruta})")
        print(f"  esperado {caso['espera_ruta']:<8} {'OK' if ok else 'FALLA'}")

        salida.append({**caso, "resultado": r.como_dict(),
                       "ruta": ruta, "motivo_ruta": motivo_ruta, "correcto": ok})

    cn.close()

    config.EVIDENCIAS_DIR.mkdir(exist_ok=True)
    destino = config.EVIDENCIAS_DIR / "E02_motor_determinista.json"
    destino.write_text(json.dumps(
        {"version_politica": config.VERSION_ID, "casos": salida,
         "invariante": "R1 · ningún modelo de lenguaje participa de estas cifras"},
        ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'=' * 78}\n{len(CASOS) - fallos}/{len(CASOS)} casos con la ruta esperada "
          f"· evidencia en {destino.name}")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
