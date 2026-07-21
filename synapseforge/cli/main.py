"""CLI entry point — ``synapseforge init`` and ``synapseforge launch``.

Installed via ``pyproject.toml`` entry point::

    synapseforge init [target_dir]
    synapseforge launch <repo_path> <exe_name> [--skip-frontend]
"""

from __future__ import annotations

import argparse
import sys


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
    launch_p.add_argument("repo_path", help="Absolute path to the project root")
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

    args = parser.parse_args()

    try:
        if args.command == "init":
            _run_init(args.target_dir)
        elif args.command == "launch":
            _run_launch(args.repo_path, args.exe_name, args.skip_frontend, args.no_embed)
        else:
            parser.print_help()
            sys.exit(1)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


def _run_init(target_dir: str) -> None:
    """Import and run pipeline.init.main.run()."""
    try:
        from pipeline.init.main import run
    except ImportError as exc:
        print(f"ERROR: could not load init module — {exc}", file=sys.stderr)
        sys.exit(1)
    run(target_dir)


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


if __name__ == "__main__":
    main()
