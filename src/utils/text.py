"""Text normalization helpers."""

from __future__ import annotations


def normalize_block(text: str) -> str:
    """Normalize whitespace while preserving line breaks."""

    cleaned = text.replace("\r\n", "\n").replace("\x0c", "\n")
    cleaned = "\n".join(line.rstrip() for line in cleaned.splitlines())
    return cleaned.strip()


__all__ = ["normalize_block"]
