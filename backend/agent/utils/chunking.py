"""Intelligent chunking for the knowledge base (RAG).

Splits text into chunks with intelligent overlap, reusing the approach from
ProspectingAgent. The logic is:

1. **Base chunk**: fixed size (``chunk_size_chars``), no heuristic cutting.
2. **Overlap**: extension before/after that CAN cut by heuristic
   (delimiters ``.``, ``!``, ``?`` and space).
3. The next base chunk starts where the previous base chunk ended.

The defaults (500/60) are smaller than Prospecting's because this system
targets local embedding models.

Typical usage::

    from backend.agent.utils.chunking import chunk_file_content

    chunks = chunk_file_content("doc.txt", text, chunk_size_chars=500, overlap_chars=60)
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)

_DELIMITERS = [".", "!", "?", " "]


def _find_best_cut(text: str, start: int, end: int, find_last: bool = False) -> int:
    """Find the best cut point in the range ``[start, end)``.

    Args:
        text: Full text being searched.
        start: Range start (inclusive).
        end: Range end (exclusive).
        find_last: If ``True`` finds the LAST delimiter (highest index);
            if ``False`` finds the FIRST delimiter (lowest index).

    Returns:
        Index of the best cut, or ``end`` when no delimiter is found.
    """
    if start >= end:
        return end

    found_positions: list[int] = []
    for delim in _DELIMITERS:
        search_pos = start
        while True:
            idx = text.find(delim, search_pos, end)
            if idx == -1:
                break
            found_positions.append(idx)
            search_pos = idx + 1

    if not found_positions:
        return end

    if find_last:
        return max(found_positions) + 1  # +1 to include the delimiter
    return min(found_positions) + 1


def chunk_file_content(
    filename: str,
    text: str | None,
    chunk_size_chars: int = 500,
    overlap_chars: int = 60,
) -> list[dict[str, Any]]:
    """Split a file's content into chunks with intelligent overlap.

    Args:
        filename: File name (used for metadata).
        text: File content.
        chunk_size_chars: Fixed base chunk size (default 500).
        overlap_chars: Overlap characters (intelligent extension, default 60).

    Returns:
        List of dicts: ``[{chunk_id, chunk_number, chunk_text, byte_size}, ...]``.

    Raises:
        ValueError: If ``chunk_size_chars`` is not positive or ``overlap_chars``
            is negative.
    """
    if not text or len(text) == 0:
        return []

    if chunk_size_chars <= 0:
        raise ValueError("chunk_size_chars must be greater than 0.")
    if overlap_chars < 0:
        raise ValueError("overlap_chars cannot be negative.")

    chunks: list[dict[str, Any]] = []
    chunk_number = 0
    pos = 0
    text_len = len(text)

    while pos < text_len:
        # 1. BASE CHUNK (fixed size, no heuristic)
        chunk_base_end = min(pos + chunk_size_chars, text_len)

        # 2. PREVIOUS OVERLAP (look for a natural boundary)
        if pos == 0:
            chunk_start = 0
        else:
            overlap_start = max(0, pos - overlap_chars)
            best_cut_before = _find_best_cut(text, overlap_start, pos, find_last=False)
            if best_cut_before == pos:
                chunk_start = overlap_start
            else:
                chunk_start = best_cut_before

        # 3. NEXT OVERLAP (look for a natural boundary)
        if chunk_base_end >= text_len:
            chunk_end = text_len
        else:
            overlap_end = min(text_len, chunk_base_end + overlap_chars)
            best_cut_after = _find_best_cut(text, chunk_base_end, overlap_end, find_last=True)
            if best_cut_after == chunk_base_end:
                chunk_end = min(chunk_base_end + overlap_chars, text_len)
            else:
                chunk_end = best_cut_after

        # 4. EXTRACT FINAL CHUNK
        chunk_text = text[chunk_start:chunk_end].strip()

        if chunk_text:
            chunks.append(
                {
                    "chunk_id": str(uuid.uuid4()),
                    "chunk_number": chunk_number,
                    "chunk_text": chunk_text,
                    "byte_size": len(chunk_text.encode("utf-8")),
                }
            )
            chunk_number += 1

        # 5. ADVANCE (the next base chunk starts where this one ended)
        pos = chunk_base_end

        if pos >= text_len:
            break

    logger.info(
        "Chunking of '%s': %d chunk(s) (size=%d, overlap=%d)",
        filename,
        len(chunks),
        chunk_size_chars,
        overlap_chars,
    )
    return chunks