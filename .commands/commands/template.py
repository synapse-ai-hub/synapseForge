#!/usr/bin/env python3
"""Regenera pipeline/template.zip desde la carpeta template/ con procesos automáticos."""

import zipfile
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path


AR_TZ = timezone(timedelta(hours=-3))

ROOT = Path(__file__).resolve().parents[2]  # synapseForge root
TEMPLATE_DIR = ROOT / "template"
ZIP_PATH = ROOT / "pipeline" / "template.zip"


def main() -> None:
    if not TEMPLATE_DIR.is_dir():
        print(f"ERROR: No existe {TEMPLATE_DIR}")
        return

    # ========================================================================
    # PASOS DE PREPARACIÓN (siempre se ejecutan al inicio)
    # ========================================================================
    
    # 1. Borrar carpeta backend completa de template/
    if (TEMPLATE_DIR / "backend").is_dir():
        shutil.rmtree(TEMPLATE_DIR / "backend")

    # 2. Borrar carpeta frontend completa de template/
    if (TEMPLATE_DIR / "frontend").is_dir():
        shutil.rmtree(TEMPLATE_DIR / "frontend")

    # 3. Copiar backend completo desde D:\...\ synapseForge\backend a template/backend
    SOURCE_BACKEND = ROOT / "backend"
    
    shutil.copytree(SOURCE_BACKEND, TEMPLATE_DIR / "backend")

    # 4. Copiar frontend completo desde D:\... \synapseForge\frontend a template/frontend
    SOURCE_FRONTEND = ROOT / "frontend"
    
    shutil.copytree(SOURCE_FRONTEND, TEMPLATE_DIR / "frontend")

    # ========================================================================
    # LIMPIEZA EN TEMPLATE/ (nunca en las carpetas originales)
    # ========================================================================
    
    BACKEND_TEMPLATE = TEMPLATE_DIR / "backend"
    FRONTEND_TEMPLATE = TEMPLATE_DIR / "frontend"

    # 5. Limpiar backend: borrar __pycache__ recursivo y .db archivo específico
    for path in BACKEND_TEMPLATE.rglob("__pycache__"):
        if path.is_dir():
            shutil.rmtree(path)

    # 5b. Limpiar agent_db: dejar solo .gitkeep (borra agent.db, -wal, -shm, etc.)
    _agent_db_dir = BACKEND_TEMPLATE / "agent" / "agent_db"
    if _agent_db_dir.is_dir():
        for _agent_db_file in _agent_db_dir.iterdir():
            if _agent_db_file.name != ".gitkeep":
                if _agent_db_file.is_dir():
                    shutil.rmtree(_agent_db_file)
                else:
                    _agent_db_file.unlink()

    # 6. Limpiar frontend: borrar solo node_modules/ en template/frontend (no en el origen)
    for path in FRONTEND_TEMPLATE.rglob("node_modules"):
        if path.is_dir():
            shutil.rmtree(path)

    # Borrar zip anterior antes de crear uno nuevo
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    # Crear carpeta destino del zip (si no existe)
    ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in TEMPLATE_DIR.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(TEMPLATE_DIR)
                zf.write(file_path, arcname)

    print(f"[{datetime.now(AR_TZ):%H:%M:%S}] OK template.zip regenerado en {ZIP_PATH}")


if __name__ == "__main__":
    main()
