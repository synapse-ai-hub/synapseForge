"""Orchestrates the full init pipeline (steps 1-10)."""

import subprocess
import sys
from pathlib import Path

from .input_handler import get_user_input
from .template_handler import extract_template
from .venv_handler import setup_venv, install_requirements
from .config_handler import save_config
from .logo_handler import handle_logo
from .placeholder_handler import replace_all_placeholders


def run(target_dir: str, config: dict | None = None) -> None:
    """Execute the full init pipeline inside *target_dir*.

    When *config* is provided the pipeline uses it directly (GUI mode)
    and skips the interactive ``get_user_input()`` prompt.

    Args:
        target_dir: Absolute or relative path to the (empty) project directory.
        config: Pre-collected configuration dict (from GUI). When ``None``
            the pipeline prompts via terminal.
    """
    target = Path(target_dir).resolve()
    if not target.is_dir():
        print(f"  Creating directory: {target}")
        target.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  synapseForge — Init Pipeline")
    print("=" * 60)

    # Step 1: User input
    if config is None:
        print("\n[1/10] User input ...")
        config = get_user_input()
    else:
        print("\n[1/10] Using provided configuration ...")

    # Step 2: Download & extract template
    print("\n[2/10] Downloading & extracting template ...")
    extract_template(target)

    # Step 3: Create virtual environment
    print("\n[3/10] Creating virtual environment ...")
    venv_path = setup_venv(target, config["repo"])

    # Step 4: Install Python requirements
    print("\n[4/10] Installing Python requirements ...")
    install_requirements(venv_path, target)

    # Step 5: npm install
    print("\n[5/10] Installing npm dependencies ...")
    _run_npm_install(target)

    # Step 6: Copy logos
    print("\n[6/10] Copying logos ...")
    company_logo_dest = target / "frontend" / "src" / "assets" / "logo_empresa.png"
    handle_logo(config, company_logo_dest, config_key="logo.path")
    client_logo_dest = target / "frontend" / "src" / "assets" / "logo_cliente.png"
    handle_logo(config, client_logo_dest, config_key="logo_cliente")

    # Step 7: Generate .ico from client logo
    print("\n[7/10] Generating favicon (.ico) ...")
    _run_generate_ico(venv_path, client_logo_dest)

    # Step 8: Extract colors from client logo
    print("\n[8/10] Resolving colors ...")
    _resolve_colors(config, client_logo_dest)

    # Step 9: Save user config (colors already in dict)
    print("\n[9/10] Saving configuration ...")
    save_config(target, config)

    # Step 10: Replace placeholders
    print("\n[10/10] Replacing placeholders ...")
    replace_all_placeholders(target, config)

    print("\n" + "=" * 60)
    print("  Done! Project initialized in:", target)
    print("=" * 60)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_npm_install(target: Path) -> None:
    """Run ``npm install`` in the frontend directory."""
    frontend_dir = target / "frontend"
    if not (frontend_dir / "package.json").is_file():
        print("  WARNING: package.json not found, skipping npm install")
        return
    try:
        subprocess.run(
            "npm install",
            cwd=str(frontend_dir),
            shell=True,
            check=True,
        )
        print("  npm install completed")
    except subprocess.CalledProcessError as exc:
        print(f"  WARNING: npm install failed (exit code {exc.returncode})")
    except FileNotFoundError:
        print("  WARNING: npm not found, skipping npm install")


def _run_generate_ico(venv_path: Path, logo_png: Path) -> None:
    """Generate ``.ico`` from the logo PNG using Pillow (inline)."""
    if not logo_png.is_file():
        print("  WARNING: logo PNG not found, skipping .ico generation")
        return
    try:
        from PIL import Image
    except ImportError:
        print("  WARNING: Pillow not available, skipping .ico generation")
        return

    ico_path = logo_png.with_suffix(".ico")
    try:
        img = Image.open(str(logo_png))
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        img.save(str(ico_path), format="ICO", sizes=sizes)
        print(f"  Generated: {ico_path}")
    except Exception as exc:
        print(f"  WARNING: .ico generation failed: {exc}")


def _resolve_colors(config: dict, logo_png: Path) -> None:
    """Validate that all 4 color fields exist in config."""
    keys = ["primary", "secondary", "primary_text", "gradient_secondary"]
    colors = config.setdefault("colors", {})
    missing = [k for k in keys if not colors.get(k)]
    if missing:
        print(f"  WARNING: missing colors in config: {missing}")
        return
    for k in keys:
        print(f"  {k}: {colors[k]}")
    usar = colors.get("usar_gradiente", True)
    print(f"  gradient: {'ON' if usar else 'OFF'}")