"""Disyuntor y cadena de respaldo (sesión 08).

Un rate limit, un timeout, un proveedor caído: en producción no son excepciones,
son parte del tráfico. La sesión 08 propone tres patrones que se combinan —
backoff exponencial, circuit breaker y fallback chain— y aquí están los dos que
este MVP necesita. El backoff no: reintentar dentro de una llamada MCP que tiene
que responder en el presupuesto de J1 (p95 < 2 s) gasta el presupuesto en
esperar, y lo que el diseño quiere en ese caso no es insistir sino **degradar**.

Y ahí está el punto que hace que esto no sea un patrón copiado del temario. La
cadena de respaldo de Vitalia **es la escalera de degradación N0–N5 del diseño**,
no una lista arbitraria de reintentos. Cada eslabón es un nivel declarado:

    N0  operación normal          Groq + Qdrant + corpus
    N2  sin caché semántico       Qdrant caído para el caché: se paga el token
    N3  sin recuperación densa    solo BM25 sobre el corpus en memoria
    N5  sin modelo                se deriva a la mesa con la frase de la regla 1

Un eslabón que no corresponde a un nivel declarado sería una degradación que
nadie aprobó, y el afiliado no tiene forma de saber en qué modo le contestaron.
Por eso `Resultado.nivel` viaja hasta la respuesta MCP: **una degradación que no
se declara es una mentira sobre la calidad de la respuesta.**
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class Estado(str, Enum):
    CERRADO = "cerrado"          # todo pasa
    ABIERTO = "abierto"          # nada pasa; se falla de inmediato
    SEMIABIERTO = "semiabierto"  # pasa una sola llamada de prueba


@dataclass
class Disyuntor:
    """Circuit breaker: CERRADO → ABIERTO → SEMIABIERTO → CERRADO.

    Lo que evita no es el error —el error ya ocurrió— sino la cascada: seguir
    llamando a un proveedor caído convierte un fallo en cien fallos lentos, y
    cada uno de esos cien se come el presupuesto de latencia de una consulta que
    podría haberse degradado en milisegundos.

    Si la llamada de prueba en SEMIABIERTO falla, vuelve a ABIERTO **y reinicia
    el reloj**. Volver a CERRADO tras un solo acierto sí es deliberado: el coste
    de un falso «ya se recuperó» es una llamada perdida que la cadena de respaldo
    absorbe, y el de un falso «sigue caído» es servir degradado a todo el mundo.
    """
    nombre: str
    umbral_fallos: int = 3
    espera_s: float = 30.0
    estado: Estado = Estado.CERRADO
    fallos: int = 0
    abierto_desde: float = 0.0
    aperturas: int = 0

    def _permite(self) -> bool:
        if self.estado is Estado.CERRADO:
            return True
        if self.estado is Estado.ABIERTO:
            if time.time() - self.abierto_desde >= self.espera_s:
                self.estado = Estado.SEMIABIERTO
                return True
            return False
        return True  # SEMIABIERTO: deja pasar la llamada de prueba

    def _exito(self) -> None:
        self.estado, self.fallos = Estado.CERRADO, 0

    def _fallo(self) -> None:
        self.fallos += 1
        if self.estado is Estado.SEMIABIERTO or self.fallos >= self.umbral_fallos:
            self.estado = Estado.ABIERTO
            self.abierto_desde = time.time()
            self.aperturas += 1

    def llamar(self, fn: Callable[[], Any]) -> Any:
        if not self._permite():
            raise CircuitoAbierto(f"disyuntor «{self.nombre}» abierto")
        try:
            r = fn()
        except Exception:
            self._fallo()
            raise
        self._exito()
        return r

    def como_dict(self) -> dict:
        return {"nombre": self.nombre, "estado": self.estado.value,
                "fallos": self.fallos, "aperturas": self.aperturas}


class CircuitoAbierto(RuntimeError):
    pass


@dataclass
class Eslabon:
    nivel: str                       # N0 · N2 · N3 · N5 — de la escalera del diseño
    descripcion: str
    fn: Callable[[], Any]
    disyuntor: Disyuntor | None = None


@dataclass
class Resultado:
    valor: Any
    nivel: str
    descripcion: str
    intentos: list[dict] = field(default_factory=list)
    degradado: bool = False


def cadena_de_respaldo(eslabones: list[Eslabon]) -> Resultado:
    """El primero que responde, gana. El último no puede fallar.

    El último eslabón de toda cadena de esta mesa es N5 —la respuesta que deriva
    a la mesa sin llamar a ningún modelo— precisamente porque no puede fallar:
    una cadena cuyo último eslabón puede lanzar deja al llamador con una
    excepción y al prestador con una pantalla en blanco, que es la peor forma de
    degradar. Si aun así todos fallan, se propaga el último error en vez de
    inventar una respuesta.
    """
    intentos: list[dict] = []
    ultimo: Exception | None = None
    for i, e in enumerate(eslabones):
        t0 = time.time()
        try:
            valor = e.disyuntor.llamar(e.fn) if e.disyuntor else e.fn()
        except Exception as exc:                       # noqa: BLE001
            ultimo = exc
            intentos.append({"nivel": e.nivel, "resultado": "falla",
                             "error": f"{type(exc).__name__}: {exc}"[:200],
                             "ms": int((time.time() - t0) * 1000)})
            continue
        intentos.append({"nivel": e.nivel, "resultado": "ok",
                         "ms": int((time.time() - t0) * 1000)})
        return Resultado(valor=valor, nivel=e.nivel, descripcion=e.descripcion,
                         intentos=intentos, degradado=i > 0)
    raise ultimo if ultimo else RuntimeError("cadena de respaldo vacía")


# Los disyuntores son de proceso, no de llamada: se comparten entre skills para
# que el fallo que ve una lo vea la siguiente. Uno por dependencia externa,
# porque abrir el de Qdrant cuando el que falla es Groq degradaría un carril sano.
DISYUNTORES = {
    "groq": Disyuntor("groq"),
    "openai": Disyuntor("openai"),
    "qdrant": Disyuntor("qdrant"),
}
