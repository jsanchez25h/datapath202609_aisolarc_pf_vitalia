"""Registro de skills · versionado y hot-swap (sesión 08).

Una skill es una capacidad atómica con tres partes, y **el modelo solo ve dos**:
el nombre y la descripción. Nunca ve el código. Por eso la descripción no es
documentación: es el contrato con el que el agente decide invocarla o no, y una
descripción ambigua no produce un error sino algo peor —una herramienta que
nadie llama, o que se llama cuando no toca.

Lo que este registro añade sobre una lista de funciones es el **versionado**.
Cada skill vive con su historial y una de sus versiones está marcada `latest`.
El servidor MCP registra el *nombre* como herramienta y resuelve la versión en
cada llamada, no al arrancar. Esa indirección es todo el hot-swap: publicar una
versión nueva y marcarla `latest` cambia lo que hace la herramienta sin tocar el
servidor, sin reiniciar el proceso y sin que el cliente MCP se entere.

Para este proyecto la indirección no es decorativa. La política de Vitalia se
versiona (`v2026_09`, y detrás vendrá `v2026_10`) y las skills que la leen
tienen que poder cambiar de comportamiento sin que se caiga la mesa. `Registro`
es donde ese cambio se hace explícito y auditable en vez de por despliegue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel


@dataclass(frozen=True)
class Skill:
    """Una capacidad. `descripcion` es lo que lee el modelo; lo demás es contrato.

    Los tres campos del final no son metadatos sueltos: cada uno decide qué
    ganchos corren sobre la llamada.

    - `campo_texto_libre` nombra el argumento que viene de un humano y que por
      tanto tiene que pasar por el guardrail de entrada. Si es `None` la skill
      no recibe texto libre —solo identificadores del catálogo— y la cadena de
      pre-ganchos se ahorra las ocho capas. Es la misma economía del veto V3:
      no se paga un control que no puede encontrar nada.
    - `escribe` marca las skills que tocan la base. El servidor puede arrancar
      en modo solo lectura y el gancho de ámbito las corta ahí.
    - `cita_politica` marca las que devuelven texto con citas, y es lo que
      enciende O1/O2 a la salida.
    """
    nombre: str
    version: str
    descripcion: str
    esquema: type[BaseModel]
    ejecutar: Callable[..., dict]
    campo_texto_libre: str | None = None
    escribe: bool = False
    cita_politica: bool = False

    @property
    def ref(self) -> str:
        return f"{self.nombre}@{self.version}"


class VersionDesconocida(KeyError):
    pass


@dataclass
class Registro:
    _versiones: dict[str, dict[str, Skill]] = field(default_factory=dict)
    _latest: dict[str, str] = field(default_factory=dict)

    # --- publicación ------------------------------------------------------

    def registrar(self, skill: Skill, *, latest: bool = False) -> Skill:
        """Publica una versión. `latest=True` la deja como la que se sirve.

        Registrar **no** promueve por defecto: publicar una versión y activarla
        son dos actos distintos, y confundirlos es cómo una skill a medio probar
        acaba atendiendo tráfico. La primera versión de un nombre sí se promueve
        sola, porque un nombre sin `latest` no es invocable y no tendría sentido.
        """
        familia = self._versiones.setdefault(skill.nombre, {})
        familia[skill.version] = skill
        if latest or skill.nombre not in self._latest:
            self._latest[skill.nombre] = skill.version
        return skill

    def marcar_latest(self, nombre: str, version: str) -> Skill:
        """El hot-swap. Devuelve la skill que queda activa."""
        familia = self._versiones.get(nombre) or {}
        if version not in familia:
            raise VersionDesconocida(f"{nombre}@{version} no está registrada")
        self._latest[nombre] = version
        return familia[version]

    # --- consulta ---------------------------------------------------------

    def obtener(self, nombre: str, version: str | None = None) -> Skill:
        familia = self._versiones.get(nombre)
        if not familia:
            raise VersionDesconocida(f"skill «{nombre}» no registrada")
        v = version or self._latest[nombre]
        if v not in familia:
            raise VersionDesconocida(f"{nombre}@{v} no está registrada")
        return familia[v]

    def nombres(self) -> list[str]:
        return sorted(self._versiones)

    def versiones(self, nombre: str) -> list[str]:
        return sorted(self._versiones.get(nombre, {}))

    def latest(self, nombre: str) -> str:
        return self._latest[nombre]

    def catalogo(self) -> list[dict[str, Any]]:
        """Lo que se enseña en la evidencia: qué hay publicado y qué está activo."""
        return [{"nombre": n,
                 "versiones": self.versiones(n),
                 "latest": self._latest[n],
                 "escribe": self.obtener(n).escribe,
                 "cita_politica": self.obtener(n).cita_politica,
                 "descripcion": self.obtener(n).descripcion.strip().splitlines()[0]}
                for n in self.nombres()]


REGISTRO = Registro()
