"""Step 1 — Interactive user input for all replace.json fields."""

import re
import sys
from pathlib import Path
from typing import Dict, Optional


def get_user_input() -> Dict[str, object]:
    """Prompt the user for every field and return a validated config dict.

    Returns:
        A dictionary with the same structure as ``config/replace.json``.
    """
    print("\nIngresá los datos del proyecto (dejá vacío para omitir):\n")

    # ── Logo ────────────────────────────────────────────────────────────
    logo_path: Optional[str] = _prompt("Logo de la empresa (para README, sin comillas)", required=True)
    logo_resolved = _resolve_logo(logo_path)

    width: Optional[str] = _prompt("Logo — ancho (px, opcional)", default="")
    height: Optional[str] = _prompt("Logo — alto (px, opcional)", default="")

    # ── Project info ────────────────────────────────────────────────────
    empresa: str = _prompt("Nombre de la empresa desarrolladora", required=True)
    owner: str = _prompt("Owner del repo (usuario de GitHub)", required=True)
    legal: str = _prompt("Nombre legal / razón social", required=True)
    repo: str = _prompt("Nombre del repo", required=True)
    cliente: str = _prompt("Nombre del cliente", required=True)
    logo_cliente: str = _prompt("Logo del cliente (para la app, opcional)", default="")
    descripcion: str = _prompt("Descripción del proyecto", required=True)
    tarea: str = _prompt("Nombre de la tarea / rubro", required=True)

    # ── Colors (opcionales) ─────────────────────────────────────────────
    print("\nColores (opcionales — dejá vacío para extraer del logo):")
    color_primary: Optional[str] = _prompt_hex("Color primary (ej: #D76F10)")
    color_secondary: Optional[str] = _prompt_hex("Color secondary (ej: #F0A347)")
    color_background: Optional[str] = _prompt_hex("Color background (ej: #FFFFFF)")
    color_text: Optional[str] = _prompt_hex("Color texto (ej: #151515)")

    colors: Dict[str, str] = {}
    if color_primary:
        colors["primary"] = color_primary
    if color_secondary:
        colors["secondary"] = color_secondary
    if color_background:
        colors["background"] = color_background
    if color_text:
        colors["text"] = color_text

    return {
        "logo": {
            "path": str(logo_resolved),
            "width": width or None,
            "height": height or None,
        },
        "empresa": empresa,
        "owner": owner,
        "legal": legal,
        "repo": repo,
        "cliente": cliente,
        "logo_cliente": logo_cliente or None,
        "descripcion": descripcion,
        "tarea": tarea,
        "colors": colors,
    }


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _prompt(label: str, *, required: bool = False, default: str = "") -> str:
    """Ask for a text value. Loop until non-empty if *required*."""
    hint = f" [{default}]" if default else ""
    suffix = " *" if required else ""
    while True:
        value = input(f"  {label}{suffix}{hint}: ").strip()
        if not value:
            value = default
        if value:
            return value
        if not required:
            return ""
        print("    ⚠ Este campo es obligatorio.")


def _prompt_hex(label: str) -> Optional[str]:
    """Ask for an optional hex color. Return ``None`` if skipped."""
    value = input(f"  {label}: ").strip()
    if not value:
        return None
    if _HEX_RE.match(value):
        return value
    print("    ⚠ Formato inválido. Usá #RRGGBB (ej: #D76F10). Se ignora.")
    return None


def _resolve_logo(raw: str) -> Path:
    """Resolve and validate the logo path."""
    p = Path(raw).resolve()
    if not p.is_file():
        print(f"  ⚠ Archivo no encontrado: {p}")
        sys.exit(1)
    return p
