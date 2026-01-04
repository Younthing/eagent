"""Service-layer helpers for input/output handling."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import tempfile
from typing import Iterator


@contextmanager
def temp_pdf(data: bytes, *, filename: str | None = None) -> Iterator[Path]:
    """Write PDF bytes to a temporary file and yield its path."""
    suffix = ".pdf"
    if filename and "." in filename:
        suffix = Path(filename).suffix or suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
        handle.write(data)
        handle.flush()
        path = Path(handle.name)
    try:
        yield path
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
