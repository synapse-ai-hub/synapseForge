"""CLI entry point — ``synapseforge init``, ``synapseforge launch``, ``synapseforge colors``, ``synapseforge run``.

Installed via ``pyproject.toml`` entry point::

    synapseforge init [target_dir]
    synapseforge launch <repo_path> <exe_name> [--skip-frontend] [--no-embed]
    synapseforge colors [project_dir]
    synapseforge run [project_dir]

Examples:
    synapseforge init                    # Create project in current directory
    synapseforge init ./mi-proyecto      # Create project in ./mi-proyecto
    synapseforge launch . mi-app         # Build distribution zip
    synapseforge launch . mi-app --skip-frontend  # Skip frontend build
    synapseforge colors                  # Edit colors in current project
    synapseforge colors ./mi-proyecto    # Edit colors in specific project
    synapseforge run                     # Start dev servers (uvicorn + npm)
    synapseforge run ./mi-proyecto       # Start dev servers in specific project
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
    ("primary", "Color principal (botones, headers, burbujas)"),
    ("secondary", "Color secundario (hover, detalles light)"),
    ("primary_text", "Color de texto (botones, headers)"),
    ("gradient_secondary", "Color secundario del gradiente"),
]


def main() -> None:
    """Parse arguments and dispatch to ``pipeline.init`` or ``pipeline.launch``."""
    parser = argparse.ArgumentParser(
        prog="synapseforge",
        description="synapseForge — AI agent project scaffolding & distribution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    # ── init ────────────────────────────────────────────────────────────
    init_p = subparsers.add_parser(
        "init",
        help="Create a new synapseForge project from template",
        description="Create a new synapseForge project from template. Opens a GUI to collect project configuration (name, description, colors, etc.) and generates the complete project structure.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  synapseforge init                    # Create project in current directory
  synapseforge init ./mi-proyecto      # Create project in ./mi-proyecto
  synapseforge init /ruta/absoluta     # Create project in absolute path

The GUI will prompt for:
  - Project name, description, client/task names
  - Logo files (company + client)
  - Primary, secondary, text color and gradient colors for the UI

Output: Complete project structure with backend/, frontend/, config/, pipeline/, .commands/""",
    )
    init_p.add_argument(
        "target_dir",
        nargs="?",
        default=".",
        help="Target directory (default: current working directory)",
    )

    # ── launch ──────────────────────────────────────────────────────────
    launch_p = subparsers.add_parser(
        "launch",
        help="Build a standalone distribution zip from a project",
        description="Build a standalone distribution zip from a synapseForge project. Packages the backend (with embedded Python), frontend (built), and creates a Windows installer/executable.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  synapseforge launch . mi-app                    # Build distribution
  synapseforge launch ./mi-proyecto mi-app        # Build from specific project
  synapseforge launch . mi-app --skip-frontend    # Use existing frontend/dist
  synapseforge launch . mi-app --no-embed         # Use system Python (no embed)

Arguments:
  repo_path    Path to the project root (default: current directory)
  exe_name     Name for the executable (e.g., mi-app -> mi-app.exe)

Options:
  --skip-frontend   Skip npm build, use existing frontend/dist/
  --no-embed        Use existing venv instead of downloading embedded Python

Output: pipeline/dist/<exe_name>.zip containing installer + portable version""",
    )
    launch_p.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Path to the project root (default: current working directory)",
    )
    launch_p.add_argument("exe_name", help="Name for the executable (e.g., mi-app)")
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
        "colors",
        help="Edit runtime colors.json (frontend/public/colors.json) via GUI",
        description="Open a tkinter GUI to edit the runtime colors.json file. Changes apply immediately on browser reload — no rebuild needed.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  synapseforge colors                  # Edit colors in current project
  synapseforge colors ./mi-proyecto    # Edit colors in specific project

The GUI allows editing:
  - Primary color (buttons, headers, bubbles)
  - Secondary color (hover, details light)
  - Text color for buttons and headers
  - Gradient secondary color (with toggle to enable/disable gradients)

Changes are saved to frontend/public/colors.json and take effect on browser refresh.""",
    )
    colors_p.add_argument(
        "project_dir",
        nargs="?",
        default=".",
        help="Project directory containing frontend/public/colors.json (default: current)",
    )

    # ── run ─────────────────────────────────────────────────────────────
    run_p = subparsers.add_parser(
        "run",
        help="Start development servers (uvicorn + npm run dev) and open browser",
        description="Start both backend (uvicorn with --reload) and frontend (npm run dev) development servers. First executes .commands/init.ps1 to activate the project's venv and load aliases. Opens the default browser to the frontend URL.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  synapseforge run                     # Start dev servers in current project
  synapseforge run ./mi-proyecto       # Start dev servers in specific project

What it does:
  1. Executes .commands/init.ps1 (activates venv, loads aliases from commands.json)
  2. Starts uvicorn on port 8000 (backend/main.py:app with --reload)
  3. Starts npm run dev (Vite) on port 5173 (frontend/)
  4. Waits 3 seconds for servers to start
  5. Opens default browser to http://localhost:5173

Press Ctrl+C to stop both servers gracefully.

Requirements:
  - Project created with synapseforge init (has .commands/init.ps1)
  - Node.js + npm installed
  - Frontend dependencies installed (npm install in frontend/)""",
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
            _init(args.target_dir)
        elif args.command == "launch":
            _launch(args.repo_path, args.exe_name, args.skip_frontend, args.no_embed)
        elif args.command == "colors":
           _colors(args.project_dir)
        elif args.command == "run":
            _run(args.project_dir)
        else:
            parser.print_help()
            sys.exit(1)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


def _init(target_dir: str) -> None:
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


def _launch(
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


def _colors(project_dir: str) -> None:
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


def _run(project_dir: str) -> None:
    """Start uvicorn + npm run dev and open the browser."""
    import os

    # ── Verificar que el entorno virtual esté activado ────────────────
    if not os.environ.get("VIRTUAL_ENV"):
        raise RuntimeError(
            "No hay un entorno virtual activado. "
            "Activá el venv antes de ejecutar 'synapseforge run'.\n"
            "Ejemplo: .\\venv\\Scripts\\activate (Windows) o source venv/bin/activate (Linux/Mac)"
        )

    project_path = Path(project_dir).resolve()
    frontend_path = project_path / "frontend"
    backend_module = "backend.main:app"

    if not frontend_path.is_dir():
        print(f"ERROR: No se encontró el directorio frontend en {project_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Starting dev servers for {project_path} ...")

    # Start uvicorn (backend) — venv debe estar activo manualmente
    print("  Iniciando backend (uvicorn)...")
    uvicorn_proc = subprocess.Popen(
        ["python", "-m", "uvicorn", backend_module, "--reload", "--port", "8000"],
        cwd=str(project_path),
        shell=True,
    )

    # Wait a few seconds and check if backend is alive
    time.sleep(3)
    if uvicorn_proc.poll() is not None:
        print("  ERROR: Backend falló al iniciar (¿olvidaste activar el venv?)", file=sys.stderr)
        sys.exit(1)

    print("  Backend iniciado correctamente")

    # Start npm run dev (frontend)
    print("  Iniciando frontend (npm run dev)...")
    npm_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(frontend_path),
        shell=True,
    )

    time.sleep(3)
    if npm_proc.poll() is not None:
        print("  ERROR: Frontend falló al iniciar", file=sys.stderr)
        uvicorn_proc.terminate()
        uvicorn_proc.wait()
        sys.exit(1)

    print("  Frontend iniciado correctamente")

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