"""Publicación de las skills en el registro.

Cuatro nombres, cinco versiones. La única familia con dos es
`consultar_politica`, y la activa es la `1.1.0` —la que consulta el caché
semántico antes de preguntarle al modelo—. La `1.0.0` se deja publicada y no se
borra: es contra ella contra la que se mide el ahorro, y una versión anterior
que ya no existe no permite comparar nada.

Lo que **no** hay en esta lista importa tanto como lo que hay. No existe una
skill que emita una carta, ni una que niegue, ni una que cambie el estado de un
expediente. No es que estén restringidas por permisos: no están escritas. Un
agente conectado a este servidor puede leerlo todo, calcular cualquier cosa y
preparar el texto de una subsanación, y no tiene forma de resolver una
solicitud. Eso es el ADR-10 —el sistema nunca niega solo— llevado a la
superficie de herramientas, donde no depende de que nadie recuerde aplicarlo.
"""

from __future__ import annotations

from mcp_vitalia.registro import REGISTRO
from mcp_vitalia.skills import (consultar_politica, estado_expediente,
                                preparar_subsanacion, simular_cobertura)


def publicar() -> None:
    REGISTRO.registrar(consultar_politica.V1_0_0)
    REGISTRO.registrar(consultar_politica.V1_1_0, latest=True)
    REGISTRO.registrar(simular_cobertura.V1_0_0, latest=True)
    REGISTRO.registrar(estado_expediente.V1_0_0, latest=True)
    REGISTRO.registrar(preparar_subsanacion.V1_0_0, latest=True)


publicar()
