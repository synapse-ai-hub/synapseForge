"""Step 5 — Save the user-provided config as ``config/replace.json``."""

import json
from pathlib import Path


def save_config(target: Path, config: dict) -> None:
    """Write the user config to ``{target}/config/replace.json``.

    Args:
        target: Project root directory.
        config: Validated user config dictionary.
    """
    config_dir = target / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    dest = config_dir / "replace.json"
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"  Saved: {dest}")
