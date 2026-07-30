"""Módulo skill_creator — creación de skills con agente + tools.

Estructura:
- ``creator.py`` — Orquestación (``iterar_skill``, ``create_skill``).
- ``helpers.py`` — Funciones internas (``_generar_skill``, etc.).
- ``skill_agent.py`` — Loop del agente con tools (``run_skill_agent``).

Uso desde routes::

    from backend.agent.utils.skill_creator import create_skill, iterar_skill
"""

from backend.agent.utils.skill_creator.creator import create_skill, iterar_skill
from backend.agent.utils.skill_creator.skill_agent import run_skill_agent

__all__ = ["create_skill", "iterar_skill", "run_skill_agent"]
