"""Email parser utilities for processing raw RFC 2822 email messages.

Parses raw email bytes from IMAP into structured Python objects.
Handles multipart messages, MIME headers, and attachments.
"""

import email
import email.message
from email.header import decode_header
from email.utils import parsedate_to_datetime
import os
import sys

_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


from backend.agent.utils.error_logger import log_error


def decode_mime_header(value: str | None) -> str:
    """Decode a MIME encoded-header into plain text.

    Args:
        value: Raw header value (may be encoded with =?charset?).

    Returns:
        Decoded plain text string.
    """
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError) as e:
                log_error(str(e), source="email_parser.py:decode_mime_header")
                decoded.append(part.decode("utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded).strip()


def parse_email(raw_bytes: bytes) -> dict:
    """Parse raw email bytes into a structured dictionary.

    Extracts sender, subject, date, body (plain text), and attachment info
    from a raw RFC 2822 message.

    Args:
        raw_bytes: Raw email bytes as returned by IMAP BODY[] fetch.

    Returns:
        Dictionary with keys:
            - message_id (str)
            - sender (str)
            - subject (str)
            - date (str)
            - date_parsed (datetime or None)
            - body (str): plain text body
            - attachments (list[dict]): each with filename, size_bytes, content_type, data
    """
    msg = email.message_from_bytes(raw_bytes)

    # ── Headers ──
    message_id = msg.get("Message-ID", "")
    sender = msg.get("From", "")
    subject = decode_mime_header(msg.get("Subject", ""))
    date_str = msg.get("Date", "")

    try:
        date_parsed = parsedate_to_datetime(date_str) if date_str else None
    except (ValueError, TypeError) as e:
        log_error(str(e), source="email_parser.py:parse_email(date)")
        date_parsed = None

    # ── Body (plain text) ──
    body = _extract_plain_text(msg)

    # ── Attachments ──
    attachments = _extract_attachments(msg)

    return {
        "message_id": message_id,
        "sender": sender,
        "subject": subject,
        "date": date_str,
        "date_parsed": date_parsed,
        "body": body,
        "attachments": attachments,
    }


def _extract_plain_text(msg: email.message.Message) -> str:
    """Extract plain text body from an email message.

    Args:
        msg: Parsed email.message.Message object.

    Returns:
        Plain text body string, empty if not found.
    """
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode("utf-8", errors="replace")
        return ""
    payload = msg.get_payload(decode=True)
    if payload:
        return payload.decode("utf-8", errors="replace")
    return ""


def _extract_attachments(msg: email.message.Message) -> list[dict]:
    """Extract attachment info and binary data from an email message.

    Args:
        msg: Parsed email.message.Message object.

    Returns:
        List of dictionaries with filename, size_bytes, content_type, and data (bytes).
    """
    attachments = []
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        filename = part.get_filename()
        if not filename:
            continue
        decoded_name = decode_mime_header(filename)
        payload = part.get_payload(decode=True)
        attachments.append({
            "filename": decoded_name,
            "size_bytes": len(payload) if payload else 0,
            "content_type": part.get_content_type(),
            "data": payload,
        })
    return attachments


if __name__ == '__main__':
    print('email_parser module — parseo de correos RFC 2822.')
    print('  parse_raw_email(data), extract_attachments(msg) disponibles.')
