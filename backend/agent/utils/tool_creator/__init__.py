"""Tool creator module.

Encapsula la creación de tools externas para synapseForge:

- ``creator.py`` — Orquestación principal (``iterar_tool``, ``create_tool``).
- ``helpers.py`` — Helpers de bajo nivel (listar tools, evaluar existencia).
- ``tool_agent.py`` — Runner del agente con tools (read/write/edit/shell).

Las tools externas viven en ``~/.config/synapseForge/tools/`` como archivos
``.py`` autocontenidos. Ver ``docs/tools/guia-creacion-tools.md`` para el
estándar de estructura.
"""

from __future__ import annotations

from backend.agent.utils.tool_creator.creator import create_tool, iterar_tool

__all__ = ["create_tool", "iterar_tool", "run_tool_agent"]