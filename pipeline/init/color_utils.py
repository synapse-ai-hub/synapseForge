"""Color utility functions for palette extraction and manipulation."""

from __future__ import annotations


def lighten_hex(hex_color: str, factor: float) -> str:
    """Lighten a hex color by *factor* (0-1)."""
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    r = min(255, int(r + (255 - r) * factor))
    g = min(255, int(g + (255 - g) * factor))
    b = min(255, int(b + (255 - b) * factor))
    return f"#{r:02x}{g:02x}{b:02x}"


def darken_hex(hex_color: str, factor: float) -> str:
    """Darken a hex color by *factor* (0-1)."""
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    r = max(0, int(r * (1 - factor)))
    g = max(0, int(g * (1 - factor)))
    b = max(0, int(b * (1 - factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


def mix_hex(hex1: str, hex2: str, ratio: float) -> str:
    """Mix two hex colors. ``ratio=1`` -> all *hex1*, ``ratio=0`` -> all *hex2*."""
    r1, g1, b1 = int(hex1[1:3], 16), int(hex1[3:5], 16), int(hex1[5:7], 16)
    r2, g2, b2 = int(hex2[1:3], 16), int(hex2[3:5], 16), int(hex2[5:7], 16)
    r = int(r1 * ratio + r2 * (1 - ratio))
    g = int(g1 * ratio + g2 * (1 - ratio))
    b = int(b1 * ratio + b2 * (1 - ratio))
    return f"#{r:02x}{g:02x}{b:02x}"


def luminance(hex_color: str) -> float:
    """Return relative luminance (0-1) of a hex color."""
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def is_dark(hex_color: str) -> bool:
    """Return True if the color is dark (luminance < 0.5)."""
    return luminance(hex_color) < 0.5