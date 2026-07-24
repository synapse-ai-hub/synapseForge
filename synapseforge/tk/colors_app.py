"""tkinter GUI for synapseforge colors — replaces terminal color editor."""

from __future__ import annotations

import io
import json
import re
import sys
import tkinter as tk
from tkinter import colorchooser, messagebox, ttk
from typing import Any, Dict, Optional
from pathlib import Path
from urllib.request import urlopen

_HERE = Path(__file__).resolve().parent
_ICO_PATH = _HERE / "logo.ico"

try:
    from PIL import Image, ImageTk
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment]
    ImageTk = None

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_LOGO_URL = "https://github.com/synapse-ai-hub/sources/raw/main/logo_transparente.png"

COLOR_FIELDS = [
    ("avatar_asistente", "Avatar asistente"),
    ("avatar_usuario", "Avatar usuario"),
    ("btn_nuevo_chat_bg", "Botón Nuevo Chat / header MCP — fondo"),
    ("btn_nuevo_chat_text", "Botón Nuevo Chat / header MCP — texto"),
    ("btn_adjuntar", "Botón adjuntar"),
    ("btn_enviar", "Botón enviar"),
    ("btn_detener", "Botón detener"),
    ("flecha_autoscroll", "Flecha autoscroll"),
]


class ColorsApp:
    """GUI for editing runtime colors.json."""

    def __init__(self, colors_path: Path, current: Dict[str, str]) -> None:
        self.colors_path = colors_path
        self.current = current
        self.result: Optional[Dict[str, str]] = None

        self.root = tk.Tk()
        self.root.title("synapseForge — Colors")
        self.root.resizable(False, False)
        if _ICO_PATH.is_file():
            try:
                self.root.iconbitmap(str(_ICO_PATH))
            except Exception:
                pass

        # ── Logo header ──────────────────────────────────────────────
        self._load_logo()

        # ── Instruction ──────────────────────────────────────────────
        ttk.Label(
            self.root,
            text="Editá los colores (dejá vacío para mantener el actual):",
            font=("", 10, ""),
        ).pack(pady=(5, 10))

        # ── Color fields ─────────────────────────────────────────────
        frame = ttk.Frame(self.root)
        frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        self._entries: Dict[str, tk.Entry] = {}
        self._previews: Dict[str, tk.Canvas] = {}

        for i, (key, desc) in enumerate(COLOR_FIELDS):
            ttk.Label(frame, text=desc).grid(
                row=i, column=0, sticky="w", pady=3, padx=(0, 10)
            )

            # Preview square (18×18)
            cv = tk.Canvas(frame, width=20, height=20, highlightthickness=1,
                           highlightbackground="#ccc")
            cv.grid(row=i, column=1, pady=3, padx=(0, 6))
            self._previews[key] = cv

            # Entry with current value
            ent = ttk.Entry(frame, width=14)
            ent.grid(row=i, column=2, pady=3, padx=(0, 6))
            cur_val = current.get(key, "")
            if cur_val:
                ent.insert(0, cur_val)
            ent.bind("<KeyRelease>", lambda _e, k=key: self._update_preview(k))
            self._entries[key] = ent

            # Color picker button
            ttk.Button(
                frame, text="Seleccionar", command=lambda k=key: self._pick_color(k)
            ).grid(row=i, column=3, pady=3, padx=(0, 0))

            # Initial preview
            self._update_preview(key)

        # ── Bottom buttons ───────────────────────────────────────────
        bottom = ttk.Frame(self.root)
        bottom.pack(fill="x", padx=15, pady=(0, 12))

        ttk.Button(bottom, text="Cancelar", command=self._on_cancel).pack(
            side="right", padx=(5, 0)
        )
        ttk.Button(bottom, text="Guardar", command=self._on_save).pack(side="right")

        # ── Center ───────────────────────────────────────────────────
        self._center(660, 500)

    # ------------------------------------------------------------------
    # Logo
    # ------------------------------------------------------------------
    def _load_logo(self) -> None:
        if Image is None or ImageTk is None:
            return
        try:
            raw = urlopen(_LOGO_URL, timeout=5).read()
            pil = Image.open(io.BytesIO(raw))
            pil.thumbnail((150, 150), Image.LANCZOS)
            self._logo_img = ImageTk.PhotoImage(pil)
            lbl = tk.Label(self.root, image=self._logo_img)
            lbl.pack(pady=(10, 2))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Color helpers
    # ------------------------------------------------------------------
    def _pick_color(self, key: str) -> None:
        result = colorchooser.askcolor(
            title=key,
            color=self._entries[key].get() or None,
            parent=self.root,
        )
        if result and result[1]:
            self._entries[key].delete(0, tk.END)
            self._entries[key].insert(0, result[1])
            self._update_preview(key)

    def _update_preview(self, key: str) -> None:
        cv = self._previews[key]
        raw = self._entries[key].get().strip()
        cv.delete("all")
        if raw and _HEX_RE.match(raw):
            cv.config(bg=raw)
        else:
            cv.config(bg="#ffffff")

    # ------------------------------------------------------------------
    # Save / Cancel
    # ------------------------------------------------------------------
    def _on_save(self) -> None:
        updated: Dict[str, str] = {}
        errors: list[str] = []
        for key, _desc in COLOR_FIELDS:
            raw = self._entries[key].get().strip()
            if not raw:
                updated[key] = self.current.get(key, "")
            elif _HEX_RE.match(raw):
                updated[key] = raw
            else:
                errors.append(f"'{key}': '{raw}' no es un color hex válido (#RRGGBB).")

        if errors:
            messagebox.showerror("Errores de validación",
                                 "\n".join(errors), parent=self.root)
            return

        # Write
        try:
            self.colors_path.write_text(
                json.dumps(updated, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            self.result = updated
            self.root.destroy()
        except Exception as exc:
            messagebox.showerror("Error al guardar",
                                 f"No se pudo escribir colors.json:\n{exc}",
                                 parent=self.root)

    def _on_cancel(self) -> None:
        self.result = None
        self.root.destroy()

    # ------------------------------------------------------------------
    # Window utils
    # ------------------------------------------------------------------
    def _center(self, w: int, h: int) -> None:
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    @staticmethod
    def launch(project_dir: str) -> Optional[Dict[str, str]]:
        """Open the colors GUI and return the updated dict (or None if cancelled).

        Args:
            project_dir: Path to project root containing frontend/public/colors.json.

        Returns:
            Updated colors dict, or ``None`` if the user cancelled.
        """
        colors_path = Path(project_dir).resolve() / "frontend" / "public" / "colors.json"
        if not colors_path.is_file():
            print(f"ERROR: No se encontró {colors_path}", file=sys.stderr)
            sys.exit(1)

        try:
            current = json.loads(colors_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"ERROR leyendo colors.json: {exc}", file=sys.stderr)
            sys.exit(1)

        app = ColorsApp(colors_path, current)
        app.root.mainloop()
        return app.result
