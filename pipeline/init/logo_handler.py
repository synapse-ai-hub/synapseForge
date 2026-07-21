"""Steps 6-8 — Copy logo, generate .ico, extract colors."""

import shutil
from pathlib import Path
from typing import Dict, Optional


def handle_logo(config: dict, logo_dest: Path) -> None:
    """Copy the user's logo to the template assets directory.

    Args:
        config: User config dictionary (must contain ``logo.path``).
        logo_dest: Destination path for the logo (``frontend/src/assets/logo_empresa.png``).
    """
    logo_src_raw: Optional[str] = config.get("logo", {}).get("path")
    if not logo_src_raw:
        print("  WARNING: no logo path in config, skipping")
        return

    logo_src = Path(logo_src_raw).resolve()
    if not logo_src.is_file():
        print(f"  WARNING: logo source not found: {logo_src}, skipping")
        return

    logo_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(logo_src), str(logo_dest))
    print(f"  Copied: {logo_src} → {logo_dest}")
