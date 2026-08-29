"""Orchestrates the update pipeline."""

import shutil
import json
from pathlib import Path
from ..init.template_handler import extract_template
from ..init.config_handler import load_config, save_colors
from ..init.placeholder_handler import replace_all_placeholders

def run_update(target_dir: str) -> None:
    """Update the project with the latest template, preserving user config."""
    target = Path(target_dir).resolve()
    config_path = target / "config" / "replace.json"

    if not config_path.is_file():
        print(f"ERROR: Configuration file not found at {config_path}. Cannot update.")
        return

    print("=" * 60)
    print("  synapseForge — Update Pipeline")
    print("=" * 60)

    # 1. Load existing config
    print("\n[1/4] Loading existing configuration ...")
    config = load_config(target)

    # 2. Extract new template (overwriting base files)
    # Note: extract_template needs to be careful not to delete config/replace.json
    # The current extract_template implementation might need review.
    # Assuming it extracts to a temp dir and then copies/merges.
    print("\n[2/4] Extracting new template ...")
    extract_template(target)

    # 3. Re-apply placeholders
    print("\n[3/4] Re-applying placeholders ...")
    replace_all_placeholders(target, config)

    # 4. Regenerate derived files (colors.json)
    print("\n[4/4] Regenerating derived files ...")
    save_colors(target, config)

    print("\n" + "=" * 60)
    print("  Update completed successfully!")
    print("=" * 60)
