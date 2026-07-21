"""Step 2 — Download (or locate) template.zip and extract into target."""

import sys
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# The template.zip is bundled inside the synapseForge package.
# ---------------------------------------------------------------------------
TEMPLATE_URL = (
    "https://github.com/synapse-ai-hub/synapseForge/raw/main/template.zip"
)


def extract_template(target: Path) -> None:
    """Extract the template zip into *target*.

    Looks for a local copy first (development mode), otherwise downloads
    from the GitHub raw URL.
    """
    local_zip = _package_root() / "template.zip"

    if local_zip.is_file():
        zip_path = local_zip
        print(f"  Using local template: {zip_path}")
    else:
        zip_path = _download_template(target)
        if zip_path is None:
            print("  ERROR: could not obtain template.zip")
            sys.exit(1)

    _safe_extract(zip_path, target)
    zip_path.unlink(missing_ok=True)
    print(f"  Extracted to: {target}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _package_root() -> Path:
    """Return the absolute path to the synapseForge package root."""
    return Path(__file__).resolve().parent.parent.parent


def _download_template(target: Path) -> Path:
    """Download template.zip from GitHub into *target*."""
    try:
        import urllib.request
        dest = target / "template.zip"
        print(f"  Downloading template from GitHub …")
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
