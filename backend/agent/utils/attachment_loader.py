"""Utility to retrieve email attachments from the database.

Provides functions to fetch attachment records and save them to disk
so they can be opened or processed by the user.

Typical usage:
    python backend/utils/attachment_loader.py <attachment_id> [output_dir]
"""

import os
import sys

_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agent.utils.error_logger import log_error



def get_attachment(attachment_id: int) -> dict | None:
    """Retrieve an attachment record from email_attachments by ID.

    Args:
        attachment_id: ID of the row in email_attachments.

    Returns:
        Dict with keys id, email_id, filename, content_type, size_bytes, data,
        or None if not found.
    """
    db = DB()
    if not db.sql:
        print("[DB] Sin conexión.")
        return None
    try:
        rows = db.execute_query(
            "SELECT id, email_id, filename, content_type, size_bytes, data "
            "FROM email_attachments WHERE id = ?",
            (attachment_id,),
        )
        return rows[0] if rows else None
    except Exception as e:
        log_error(str(e), source="attachment_loader.py:get_attachment")
        print(f"Error al obtener attachment: {e}")
        return None
    finally:
        db.close_connection()


def save_attachment_to_disk(
    attachment_id: int,
    output_dir: str = "descargas",
) -> str | None:
    """Save an attachment from the database to disk.

    Args:
        attachment_id: ID of the row in email_attachments.
        output_dir: Directory where the file will be saved.
            Defaults to "descargas" under the project root.

    Returns:
        Full path to the saved file, or None on failure.
    """
    record = get_attachment(attachment_id)
    if not record:
        print(f"Attachment ID {attachment_id} no encontrado.")
        return None

    filename = record.get("filename") or f"attachment_{attachment_id}"
    data = record.get("data")
    if not data:
        print(f"Attachment ID {attachment_id} no tiene datos binarios.")
        return None

    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "wb") as f:
        f.write(data)

    print(f"Guardado: {filepath} ({len(data)} bytes)")
    return filepath


def main():
    """CLI entry point: saves an attachment to disk.

    Usage:
        python backend/utils/attachment_loader.py <attachment_id> [output_dir]
    """
    if len(sys.argv) < 2:
        print("Uso: python attachment_loader.py <attachment_id> [output_dir]")
        sys.exit(1)

    try:
        attachment_id = int(sys.argv[1])
    except ValueError as e:
        log_error(str(e), source="attachment_loader.py:main")
        print("El attachment_id debe ser un número entero.")
        sys.exit(1)

    output_dir = sys.argv[2] if len(sys.argv) > 2 else "descargas"
    save_attachment_to_disk(attachment_id, output_dir)


if __name__ == "__main__":
    main()
