#!/usr/bin/env python3
"""Regenera pipeline/template.zip desde la carpeta template/"""

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

    # 1. Borrar zip anterior
    if ZIP_PATH.is_file():
        ZIP_PATH.unlink()
        print(f"  Borrado: {ZIP_PATH}")

    # 2. Crear nuevo zip
    ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in TEMPLATE_DIR.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(TEMPLATE_DIR)
                zf.write(file_path, arcname)
                print(f"  + {arcname}")

    print(f"[{datetime.now(AR_TZ):%H:%M:%S}] OK template.zip regenerado en {ZIP_PATH}")


if __name__ == "__main__":
    main()