"""Orchestrates the full init pipeline (steps 1-9)."""

import sys
from pathlib import Path

from .input_handler import get_user_input
from .template_handler import extract_template
from .venv_handler import setup_venv, install_requirements
from .config_handler import save_config
from .logo_handler import handle_logo
from .placeholder_handler import replace_all_placeholders


def run(target_dir: str) -> None:
    """Execute the full init pipeline inside *target_dir*.

    Args:
        target_dir: Absolute or relative path to the (empty) project directory.
    """
    target = Path(target_dir).resolve()
    if not target.is_dir():
        print(f"ERROR: target directory does not exist: {target}")
        sys.exit(1)

    print("=" * 60)
    print("  synapseForge — Init Pipeline")
    print("=" * 60)

    # ── Step 1: User input ──────────────────────────────────────────────
    print("\n[1/9] User input …")
    config = get_user_input()

    # ── Step 2: Download & extract template ─────────────────────────────
    print("\n[2/9] Downloading & extracting template …")
    extract_template(target)

    # ── Step 3: Create virtual environment ──────────────────────────────
    print("\n[3/9] Creating virtual environment …")
    venv_path = setup_venv(target, config["repo"])

    # ── Step 4: Install requirements ───────────────────────────────────
    print("\n[4/9] Installing requirements …")
    install_requirements(venv_path, target)

    # ── Step 5: Save user config ────────────────────────────────────────
    print("\n[5/9] Saving configuration …")
    save_config(target, config)

    # ── Step 6: Copy logo ───────────────────────────────────────────────
    print("\n[6/9] Copying logo …")
    logo_dest = target / "frontend" / "src" / "assets" / "logo_empresa.png"
    handle_logo(config, logo_dest)

    # ── Step 7: Generate .ico ───────────────────────────────────────────
    print("\n[7/9] Generating favicon (.ico) …")
    _run_generate_ico(venv_path, logo_dest)

    # ── Step 8: Extract colors (if user didn't provide them) ────────────
    print("\n[8/9] Resolving colors …")
    _resolve_colors(config, logo_dest)

    # ── Step 9: Replace placeholders ────────────────────────────────────
    print("\n[9/9] Replacing placeholders …")
    replace_all_placeholders(target, config)

    print("\n" + "=" * 60)
    print("  ✅ Done! Project initialized in:", target)
    print("=" * 60)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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
    """If user did not provide colors, extract them from the logo with colorthief."""
    if _user_provided_colors(config):
        print("  Using user-provided colors")
        return

    try:
        from colorthief import ColorThief

        if not logo_png.is_file():
            print("  WARNING: logo not found, skipping color extraction")
            return

        ct = ColorThief(str(logo_png))
        palette = ct.get_palette(color_count=3)

        names = ["primary", "secondary", "background"]
        for i, (name, rgb) in enumerate(zip(names, palette)):
            hex_color = "#{:02x}{:02x}{:02x}".format(*rgb)
            config.setdefault("colors", {})[name] = hex_color
            print(f"  {name}: {hex_color}")

        # Derive text color from background luminance
        bg_rgb = palette[2] if len(palette) > 2 else palette[0]
        luminance = (0.299 * bg_rgb[0] + 0.587 * bg_rgb[1] + 0.114 * bg_rgb[2]) / 255
        config.setdefault("colors", {})["text"] = "#151515" if luminance > 0.5 else "#F5F5F5"
        print(f"  text: {config['colors']['text']} (derived)")

    except ImportError:
        print("  WARNING: colorthief not available, skipping color extraction")


def _user_provided_colors(config: dict) -> bool:
    """Return True if at least one color was explicitly provided."""
    colors = config.get("colors", {})
    return bool(colors.get("primary") or colors.get("secondary") or colors.get("background"))



