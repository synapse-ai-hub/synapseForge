"""Step 5 — Save the user-provided config as ``config/replace.json`` and ``frontend/public/colors.json``."""

import json
from pathlib import Path


CONFIGURABLE_COLOR_KEYS = ("primary", "secondary", "primary_text", "gradient_secondary", "usar_gradiente")


def save_config(target: Path, config: dict) -> None:
    """Write the user config to ``{target}/config/replace.json`` and colors to ``frontend/public/colors.json``.

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

    # Also generate colors.json for runtime in frontend/public/
    colors = config.get("colors", {})
    runtime_colors = {k: colors.get(k) for k in CONFIGURABLE_COLOR_KEYS if colors.get(k)}
    if runtime_colors:
        public_dir = target / "frontend" / "public"
        public_dir.mkdir(parents=True, exist_ok=True)
        colors_dest = public_dir / "colors.json"
        with open(colors_dest, "w", encoding="utf-8") as f:
            json.dump(runtime_colors, f, indent=2, ensure_ascii=False)
        print(f"  Saved: {colors_dest}")
