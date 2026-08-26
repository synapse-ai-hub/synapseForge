"""
Script para correr tests E2E rapidamente.

Uso:
    python .commands/commands/quick_test.py              # Todos los escenarios
    python .commands/commands/quick_test.py rag          # Solo escenarios con "rag" en el nombre
    python .commands/commands/quick_test.py scheduler    # Solo escenarios con "scheduler"

Parametros:
    scenario : Substring para filtrar escenarios (opcional, default: todos)
    --url    : Backend base URL (opcional, default: http://127.0.0.1:8000)
"""
import sys
import subprocess
import argparse


def main():
    """Funcion principal"""
    parser = argparse.ArgumentParser(
        description="Correr tests E2E del proyecto",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python .commands/commands/quick_test.py
  python .commands/commands/quick_test.py rag
  python .commands/commands/quick_test.py scheduler --url http://127.0.0.1:8000
        """,
    )

    parser.add_argument(
        "scenario",
        nargs="?",
        default=None,
        help="Substring para filtrar escenarios (ej: rag, scheduler, creators)",
    )

    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000",
        help="Backend base URL (default: http://127.0.0.1:8000)",
    )

    args = parser.parse_args()

    cmd = [sys.executable, "-m", "tests.e2e.runner", "--base-url", args.url]

    if args.scenario:
        cmd.extend(["--only", args.scenario])

    print(f"\n🧪 Ejecutando tests E2E...\n")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
