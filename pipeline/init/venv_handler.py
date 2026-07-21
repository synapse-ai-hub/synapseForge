"""Steps 3-4 — Create virtual environment and install dependencies."""

import subprocess
import sys
from pathlib import Path


def setup_venv(target: Path, repo_name: str) -> Path:
    """Create a Python virtual environment at ``{target}/.{repo_name}``.

    Args:
        target: Project root directory.
        repo_name: Used as the venv folder name (``.{{repo_name}}``).

    Returns:
        Path to the venv root.
    """
    venv_dir = target / f".{repo_name}"
    if venv_dir.is_dir():
        print(f"  Virtual env already exists: {venv_dir}")
        return venv_dir

    result = subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  ERROR creating venv: {result.stderr.strip()}")
        sys.exit(1)

    print(f"  Created: {venv_dir}")
    return venv_dir


def install_requirements(venv_path: Path, target: Path) -> None:
    """Run ``pip install -r requirements.txt`` inside the venv.

    Args:
        venv_path: Path to the virtual environment root.
        target: Project root (where ``requirements.txt`` lives).
    """
    req_file = target / "requirements.txt"
    if not req_file.is_file():
        print("  WARNING: requirements.txt not found, skipping install")
        return

    python = _venv_python(venv_path)
    result = subprocess.run(
        [str(python), "-m", "pip", "install", "-r", str(req_file)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  WARNING: pip install failed:\n{result.stderr.strip()}")
        return

    # Print last line of pip output (usually "Successfully installed ...")
    last_line = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    if last_line:
        print(f"  {last_line}")
    else:
        print("  Requirements installed.")


def _venv_python(venv_path: Path) -> Path:
    """Return the path to the venv's Python executable."""
    return venv_path / "Scripts" / "python.exe"
