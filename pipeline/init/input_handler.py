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
    logo_cliente: str = _prompt("Logo del cliente (para la app, opcional, sin comillas)", default="")
    descripcion: str = _prompt("Descripción del proyecto", required=True)
    tarea: str = _prompt("Nombre de la tarea / rubro", required=True)

    # ── Colors (opcionales) ─────────────────────────────────────────────
    print("\nColores (opcionales — dejá vacío para extraer del logo):")
    print("  Avatar asistente: 2do color más fuerte")
    print("  Avatar usuario: 3er color más fuerte")
    print("  Botón Nuevo Chat / header MCP: color más fuerte - 20% (degradé 1ro-2do)")
    print("  Texto Nuevo Chat / header MCP: color más claro detectado")
    print("  Botones adjuntar/enviar/detener/flecha autoscroll: color más fuerte con transparencia\n")

    colors: Dict[str, str] = {}

    c = _prompt_hex("Avatar asistente (ej: #658665)")
    if c: colors["avatar_asistente"] = c

    c = _prompt_hex("Avatar usuario (ej: #928c8c)")
    if c: colors["avatar_usuario"] = c

    c = _prompt_hex("Botón Nuevo Chat / header MCP — fondo (ej: #452913)")
    if c: colors["btn_nuevo_chat_bg"] = c

    c = _prompt_hex("Botón Nuevo Chat / header MCP — texto (ej: #e0c097)")
    if c: colors["btn_nuevo_chat_text"] = c

    c = _prompt_hex("Botón adjuntar (ej: #452913)")
    if c: colors["btn_adjuntar"] = c

    c = _prompt_hex("Botón enviar (ej: #452913)")
    if c: colors["btn_enviar"] = c

    c = _prompt_hex("Botón detener (ej: #452913)")
    if c: colors["btn_detener"] = c

    c = _prompt_hex("Flecha autoscroll (ej: #452913)")
    if c: colors["flecha_autoscroll"] = c

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