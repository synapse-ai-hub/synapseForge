"""Step 2 — Locate bundled (or download) template.zip and extract into target."""

import sys
import urllib.request
import zipfile
from pathlib import Path
from importlib.resources import files as resources_files

# ---------------------------------------------------------------------------
# URL used as fallback when the bundled zip is not available.
# ---------------------------------------------------------------------------
TEMPLATE_URL = (
    "https://github.com/synapse-ai-hub/synapseForge/raw/main/pipeline/template.zip"
)


def extract_template(target: Path) -> None:
    """Extract the template zip into *target*.

    Looks for a bundled copy first (from pip install or development mode),
    otherwise downloads from the GitHub raw URL.

    The bundled zip inside the installed package is **never** deleted so
    that every invocation stays offline-capable.
    """
    bundled = _get_bundled_zip()
    was_downloaded = False

    if bundled is not None and bundled.is_file():
        zip_path = bundled
        print(f"  Using bundled template: {zip_path}")
    else:
        zip_path = _download_template(target)
        if zip_path is None:
            print("  ERROR: could not obtain template.zip")
            sys.exit(1)
        was_downloaded = True

    _safe_extract(zip_path, target)

    # Only delete the zip if it was the downloaded copy —
    # never touch the bundled copy inside site-packages.
    if was_downloaded:
        zip_path.unlink(missing_ok=True)

    print(f"  Extracted to: {target}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_bundled_zip() -> Path | None:
    """Locate the ``template.zip`` shipped inside the ``pipeline`` package.

    Works both in development mode (``pip install -e .``) and when installed
    from PyPI — the file lives in the ``pipeline`` directory of the package.
    """
    try:
        return Path(resources_files("pipeline").joinpath("template.zip"))  # type: ignore[arg-type]
    except (ModuleNotFoundError, TypeError):
        return None


def _download_template(target: Path) -> Path | None:
    """Download template.zip from GitHub into *target*."""
    try:
        dest = target / "template.zip"
        print("  Downloading template from GitHub …")
        urllib.request.urlretrieve(TEMPLATE_URL, dest)
        print(f"  Downloaded: {dest}")
        return dest
    except Exception as exc:
        print(f"  Download failed: {exc}")
        return None


def _safe_extract(zip_path: Path, target: Path) -> None:
    """Extract zip, overwriting existing files silently."""
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(path=target)
    except zipfile.BadZipFile:
        print(f"  ERROR: corrupted zip file: {zip_path}")
        sys.exit(1)
    except Exception as exc:
        print(f"  ERROR extracting zip: {exc}")
        sys.exit(1)
