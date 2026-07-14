"""
Memory management helpers for Ollama model lifecycle.

Provides functions to unload models from VRAM, check server health,
and restart the server if it crashes.
"""

from __future__ import annotations

import gc
import logging
import subprocess
import time
import os
import sys

_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agent.utils.error_logger import log_error

logger = logging.getLogger(__name__)


def liberar_modelo(modelo: str, session_id: str | None = None, turn_number: int | None = None, parent_id: str | None = None, source: str = "clean_memory.py:liberar_modelo") -> None:
    """Pide a ollama que descargue el modelo de RAM + GC de Python.

    Usa dos mecanismos:
    1. ollama stop via CLI
    2. API REST /api/generate con keep_alive=0 (fuerza descarga)
    Espera 3s para que la RAM se libere antes de continuar.

    Args:
        modelo: Nombre del modelo a descargar.
        session_id: Optional session identifier for error logging.
        turn_number: Optional turn number for error logging.
        parent_id: Optional parent session ID for error logging.
        source: Source label for error logging.
    """
    try:
        subprocess.run(
            ["ollama", "stop", modelo],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as e:
        log_error(str(e), session_id=session_id, turn_number=turn_number, parent_id=parent_id, source=source + "(ollama_stop)")
        pass
    try:
        import requests
        requests.post(
            "http://localhost:11434/api/generate",
            json={"model": modelo, "keep_alive": 0},
            timeout=5,
        )
    except Exception as e:
        log_error(str(e), session_id=session_id, turn_number=turn_number, parent_id=parent_id, source=source + "(keep_alive)")
        pass
    time.sleep(3)
    gc.collect()
    gc.collect()

    try:
        import requests
        r = requests.get("http://localhost:11434/api/ps", timeout=5)
        if r.status_code == 200:
            modelos_activos = r.json().get("models", [])
            for m in modelos_activos:
                if m.get("name") == modelo:
                    logger.warning(f"  ⚠ El modelo {modelo} sigue en VRAM pese a keep_alive=0")
                    requests.post(
                        "http://localhost:11434/api/generate",
                        json={"model": modelo, "keep_alive": 0},
                        timeout=5,
                    )
                    time.sleep(3)
                    gc.collect()
    except Exception as e:
        log_error(str(e), session_id=session_id, turn_number=turn_number, parent_id=parent_id, source=source + "(check_ps)")
        pass

    logger.info(f"Memoria liberada para modelo: {modelo}")


def ollama_server_vivo(session_id: str | None = None, turn_number: int | None = None, parent_id: str | None = None) -> bool:
    """Verifica si llama-server está corriendo y responde."""
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception as e:
        log_error(str(e), session_id=session_id, turn_number=turn_number, parent_id=parent_id, source="clean_memory.py:ollama_server_vivo")
        return False


def liberar_todos_los_modelos(session_id: str | None = None, turn_number: int | None = None, parent_id: str | None = None) -> None:
    """Libera TODOS los modelos de VRAM y mata procesos zombie de llama-server.
    
    Útil antes de cargar un modelo nuevo para asegurar VRAM disponible.
    
    Pasos:
    1. Matar todos los procesos de llama-server.exe (zombies)
    2. Obtener lista de modelos cargados via API
    3. Liberar cada modelo con keep_alive=0
    4. GC de Python
    5. Esperar 3s para que se libere VRAM
    """
    # 1. Matar procesos zombie de llama-server
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "llama-server.exe"],
            capture_output=True, timeout=10,
        )
        logger.info("Procesos llama-server terminados")
    except Exception as e:
        log_error(str(e), session_id=session_id, turn_number=turn_number, parent_id=parent_id, source="clean_memory.py:liberar_todos(taskkill)")
        logger.debug(f"No se pudieron matar procesos llama-server: {e}")
    
    # 2. Obtener modelos cargados y liberarlos
    try:
        import requests
        r = requests.get("http://localhost:11434/api/ps", timeout=5)
        if r.status_code == 200:
            modelos_activos = r.json().get("models", [])
            if modelos_activos:
                logger.info(f"Liberando {len(modelos_activos)} modelos de VRAM...")
                for m in modelos_activos:
                    nombre = m.get("name", "")
                    if nombre:
                        try:
                            requests.post(
                                "http://localhost:11434/api/generate",
                                json={"model": nombre, "keep_alive": 0},
                                timeout=5,
                            )
                            logger.debug(f"Modelo {nombre} liberado")
                        except Exception as e:
                            log_error(str(e), session_id=session_id, turn_number=turn_number, parent_id=parent_id, source="clean_memory.py:liberar_todos(liberar_modelo)")
                            logger.debug(f"Error liberando {nombre}: {e}")
            else:
                logger.debug("No hay modelos cargados en VRAM")
    except Exception as e:
        log_error(str(e), session_id=session_id, turn_number=turn_number, parent_id=parent_id, source="clean_memory.py:liberar_todos(api_ps)")
        logger.debug(f"Error consultando modelos activos: {e}")
    
    # 3. GC y espera
    time.sleep(3)
    gc.collect()
    gc.collect()
    
    logger.info("VRAM liberada completamente")


def reiniciar_llama_server(session_id: str | None = None, turn_number: int | None = None, parent_id: str | None = None) -> bool:
    """Intenta reiniciar llama-server si esta caido."""
    if ollama_server_vivo(session_id=session_id, turn_number=turn_number, parent_id=parent_id):
        return True

    logger.warning("  llama-server caido. Intentando reiniciar...")

    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "llama-server.exe"],
            capture_output=True, timeout=10,
        )
    except Exception as e:
        log_error(str(e), session_id=session_id, turn_number=turn_number, parent_id=parent_id, source="clean_memory.py:reiniciar_llama_server(taskkill)")
        pass
    time.sleep(3)

    if ollama_server_vivo(session_id=session_id, turn_number=turn_number, parent_id=parent_id):
        logger.info("  llama-server recuperado.")
        return True

    logger.error("  No se pudo reiniciar llama-server.")
    return False


if __name__ == '__main__':
    print('clean_memory module — gestión de VRAM para Ollama.')
    print(f'  ollama_server_vivo(): {ollama_server_vivo()}')
    print('  liberar_modelo(model), reiniciar_llama_server() disponibles.')
