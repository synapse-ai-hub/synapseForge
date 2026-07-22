"""Steps 6-8 — Copy logo, generate .ico, extract colors."""

import shutil
from pathlib import Path
from typing import Dict, Optional


def handle_logo(config: dict, logo_dest: Path, config_key: str = "logo.path") -> None:
    """Copy the user's logo to the template assets directory.

    Args:
        config: User config dictionary.
        logo_dest: Destination path for the logo.
        config_key: Dotted config key to read the source from
            (``logo.path`` for company, ``logo_cliente`` for client).
    """
    if config_key == "logo_cliente":
        logo_src_raw: Optional[str] = config.get("logo_cliente")
    else:
        logo_src_raw = config.get("logo", {}).get("path")

    if not logo_src_raw:
        print(f"  WARNING: no logo path in config, skipping")
        return

    logo_src = Path(logo_src_raw).resolve()
    if not logo_src.is_file():
        print(f"  WARNING: logo source not found: {logo_src}, skipping")
        return

    logo_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(logo_src), str(logo_dest))
    print(f"  Copied: {logo_src} → {logo_dest}")
