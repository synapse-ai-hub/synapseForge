"""Quick preview of both tkinter GUIs — close each window to see the next."""

import sys
import os
import tempfile
from pathlib import Path

# ── Point sys.path to project root ────────────────────────────────────
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

# ── 1. InitApp with empty fields (like real usage) ────────────────────
from synapseforge.tk.init_app import InitApp

print("Opening InitApp — close the window when done.")
InitApp.launch(target_dir=".")

# ── 2. ColorsApp with dummy data ──────────────────────────────────────
from synapseforge.tk.colors_app import ColorsApp

# Create a temp colors.json so it doesn't complain about missing file
tmp = HERE / "frontend" / "public"
tmp.mkdir(parents=True, exist_ok=True)
dummy_colors = tmp / "colors.json"
dummy_colors.write_text("""{
  "avatar_asistente": "#8b5cf6",
  "avatar_usuario": "#f97316",
  "btn_nuevo_chat_bg": "#452913",
  "btn_nuevo_chat_text": "#e0c097",
  "btn_adjuntar": "#452913",
  "btn_enviar": "#452913",
  "btn_detener": "#452913",
  "flecha_autoscroll": "#452913"
}
""")

print("Opening ColorsApp — close the window when done.")
ColorsApp.launch(str(HERE))

# Cleanup dummy file (don't leave garbage)
dummy_colors.unlink(missing_ok=True)

print("Preview finished.")
