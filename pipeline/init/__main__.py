"""Allow running as ``python -m pipeline.init [target_dir]``."""

import os
import sys

from .main import run

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    run(target)
