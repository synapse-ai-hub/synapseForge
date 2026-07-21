"""Allow running ``python -m synapseforge`` (delegates to CLI)."""

from .cli.main import main

if __name__ == "__main__":
    main()
