"""CLI entry point — ``synapseforge init``, ``synapseforge launch`` and ``synapseforge colors``.

Installed via ``pyproject.toml`` entry point::

    synapseforge init [target_dir]
    synapseforge launch <repo_path> <exe_name> [--skip-frontend]
    synapseforge colors [project_dir]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path


HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

COLOR_FIELDS = [
    ("avatar_asistente", "Avatar asistente (2do color más fuerte)"),
    ("avatar_usuario", "Avatar usuario (3er color más fuerte)"),
    ("btn_nuevo_chat_bg", "Botón Nuevo Chat / header MCP — fondo (más fuerte - 20%)"),
    ("btn_nuevo_chat_text", "Botón Nuevo Chat / header MCP — texto (color más claro)"),
    ("btn_adjuntar", "Botón adjuntar (más fuerte con transparencia)"),
    ("btn_enviar", "Botón enviar (más fuerte con transparencia)"),
    ("btn_detener", "Botón detener (más fuerte con transparencia)"),
    ("flecha_autoscroll", "Flecha autoscroll (más fuerte con transparencia)"),
]


def main() -> None:
    """Parse arguments and dispatch to ``pipeline.init`` or ``pipeline.launch``."""
    parser = argparse.ArgumentParser(
        prog="synapseforge",
        description="synapseForge — AI agent project scaffolding & distribution",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── init ────────────────────────────────────────────────────────────
    init_p = subparsers.add_parser("init", help="Create a new project from template")
    init_p.add_argument(
        "target_dir",
        nargs="?",
        default=".",
        help="Target directory (default: current working directory)",
    )

    # ── launch ──────────────────────────────────────────────────────────
    launch_p = subparsers.add_parser(
        "launch", help="Build a distribution zip from a project"
    )
    launch_p.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Path to the project root (default: current working directory)",
    )
    launch_p.add_argument("exe_name", help="Name for the executable")
    launch_p.add_argument(
        "--skip-frontend",
        action="store_true",
        help="Skip npm build (use existing frontend/dist/)",
    )
    launch_p.add_argument(
        "--no-embed",
        action="store_true",
        help="Use existing venv instead of downloading embedded Python",
    )

    # ── colors ──────────────────────────────────────────────────────────
    colors_p = subparsers.add_parser(
        "colors", help="Edit runtime colors.json (frontend/public/colors.json)"
    )
    colors_p.add_argument(
        "project_dir",
        nargs="?",
        default=".",
        help="Project directory containing frontend/public/colors.json (default: current)",
    )

    # ── run ─────────────────────────────────────────────────────────────
    run_p = subparsers.add_parser(
        "run", help="Start development servers (uvicorn + npm run dev) and open browser"
    )
    run_p.add_argument(
        "project_dir",
        nargs="?",
        default=".",
        help="Project root directory (default: current working directory)",
    )

    args = parser.parse_args()

    try:
        if args.command == "init":
            _run_init(args.target_dir)
        elif args.command == "launch":
            _run_launch(args.repo_path, args.exe_name, args.skip_frontend, args.no_embed)
        elif args.command == "colors":
            _run_colors(args.project_dir)
        elif args.command == "run":
            _run_run(args.project_dir)
        else:
            parser.print_help()
            sys.exit(1)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


def _run_init(target_dir: str) -> None:
    """Open tkinter GUI to collect config, then run pipeline.init.main.run()."""
    try:
        from synapseforge.tk.init_app import InitApp
    except ImportError as exc:
        print(f"ERROR: could not load GUI module — {exc}", file=sys.stderr)
        sys.exit(1)

    config = InitApp.launch(target_dir)
    if config is None:
        print("  Inicialización cancelada.")
        return

    print("  Proyecto creado correctamente.")


def _run_launch(
    repo_path: str, exe_name: str, skip_frontend: bool, no_embed: bool
) -> None:
    """Import and run pipeline.launch.forge.build()."""
    try:
        from pipeline.launch.forge import build
    except ImportError as exc:
        print(f"ERROR: could not load launch module — {exc}", file=sys.stderr)
        sys.exit(1)
    build(
        repo_path,
        exe_name,
        skip_frontend=skip_frontend,
        use_embed=not no_embed,
    )


def _run_colors(project_dir: str) -> None:
    """Open tkinter GUI for editing frontend/public/colors.json."""
    try:
        from synapseforge.tk.colors_app import ColorsApp
    except ImportError as exc:
        print(f"ERROR: could not load GUI module — {exc}", file=sys.stderr)
        sys.exit(1)

    result = ColorsApp.launch(project_dir)
    if result is not None:
        project_path = Path(project_dir).resolve()
        colors_path = project_path / "frontend" / "public" / "colors.json"
        print(f"\n✓ Colores actualizados en {colors_path}")
        print("  Recargá el navegador para ver los cambios (sin rebuild).")


def _run_run(project_dir: str) -> None:
    """Start uvicorn + npm run dev and open the browser."""
    project_path = Path(project_dir).resolve()
    frontend_path = project_path / "frontend"
    backend_module = "backend.main:app"

    if not frontend_path.is_dir():
        print(f"ERROR: No se encontró el directorio frontend en {project_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Starting dev servers for {project_path} ...")

    # Start uvicorn (backend)
    uvicorn_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", backend_module, "--reload", "--port", "8000"],
        cwd=str(project_path),
    )

    # Start npm run dev (frontend)
    npm_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(frontend_path),
        shell=True,
    )

    # Wait a moment for servers to start
    time.sleep(3)

    print("\nPresioná Ctrl+C para detener ambos servidores.\n")
    try:
        uvicorn_proc.wait()
    except KeyboardInterrupt:
        print("\nDeteniendo servidores...")
        uvicorn_proc.terminate()
        npm_proc.terminate()
        uvicorn_proc.wait()
        npm_proc.wait()
        print("Servidores detenidos.")


if __name__ == "__main__":
    main()
