"""Script to generate .ico file from logo_empresa.png.

Usage:
    python backend/agent/utils/generate_ico.py

Reads: frontend/src/assets/logo_empresa.png
Writes: frontend/src/assets/logo_empresa.ico
"""

from pathlib import Path
from PIL import Image


def generate_ico():
    """Generate .ico file from the company logo PNG."""
    project_root = Path(__file__).parent.parent.parent.parent
    png_path = project_root / "frontend" / "src" / "assets" / "logo_empresa.png"
    ico_path = project_root / "frontend" / "src" / "assets" / "logo_empresa.ico"

    if not png_path.exists():
        print(f"ERROR: Source PNG not found at {png_path}")
        return False

    try:
        img = Image.open(png_path)
        # ICO format supports multiple sizes; include common ones
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        img.save(ico_path, format="ICO", sizes=sizes)
        print(f"SUCCESS: Generated {ico_path}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to generate ICO: {e}")
        return False


if __name__ == "__main__":
    generate_ico()