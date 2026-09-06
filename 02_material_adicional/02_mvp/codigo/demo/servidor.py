"""El servicio, levantado como se levanta de verdad.

`prueba_api` monta la aplicación con `TestClient` dentro del propio proceso —lo
que prueba es la aplicación, no el servidor—. Para las capturas hace falta lo
contrario: un proceso escuchando en un puerto, con el navegador al otro lado,
porque lo que el anexo enseña es la interfaz y la interfaz habla HTTP.

    python -m demo.servidor            # 127.0.0.1:8088
    python -m demo.servidor --puerto 9000

Un solo trabajador y sin recarga automática: el estado que muestran las
capturas se construye con `demo.poblar` contra este mismo proceso, y un
reinicio a mitad de la secuencia dejaría media bandeja.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from comun import config  # noqa: E402

PUERTO = 8088


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--puerto", type=int, default=PUERTO)
    p.add_argument("--host", default="127.0.0.1")
    args = p.parse_args()

    config.configurar_consola()
    import uvicorn

    print(f"app-mesa   http://{args.host}:{args.puerto}/app/#/bandeja")
    print(f"openapi    http://{args.host}:{args.puerto}/docs")
    uvicorn.run("api.principal:app", host=args.host, port=args.puerto,
                workers=1, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
