#!/usr/bin/env python3
"""PDF text extraction layer.

Returns the text of a PDF as a list of per-page strings, using ``pdfplumber``.
Falls back to a same-stem ``.txt`` sidecar when pdfplumber is unavailable or a
PDF yields no text (the merged board-packet corpus ships extracted-text
sidecars next to each PDF).

This module is intentionally thin: extractors consume ``page_texts(path)`` and
do their own parsing. ``pdfplumber`` is imported lazily so this module (and the
extractors that import it) load even in environments where pdfplumber isn't
installed — they just rely on the sidecar fallback.
"""
from __future__ import annotations

from pathlib import Path


def _pdfplumber_pages(pdf_path: Path) -> list[str] | None:
    try:
        import pdfplumber  # lazy: optional dependency
    except Exception:
        return None
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            return [(page.extract_text() or "") for page in pdf.pages]
    except Exception:
        return None


def sidecar_text(pdf_path: Path) -> str | None:
    """Return the text of the same-stem ``.txt`` sidecar, if present."""
    side = Path(pdf_path).with_suffix(".txt")
    if side.exists():
        return side.read_text(encoding="utf-8", errors="replace")
    return None


def page_texts(pdf_path: Path) -> list[str]:
    """Per-page text for a PDF.

    Prefers pdfplumber; if it's unavailable or extracts nothing, falls back to
    the ``.txt`` sidecar (returned as a single page). Returns ``[]`` if no text
    can be obtained.
    """
    pdf_path = Path(pdf_path)
    pages = _pdfplumber_pages(pdf_path)
    if pages and any(p.strip() for p in pages):
        return pages
    side = sidecar_text(pdf_path)
    if side is not None:
        return [side]
    return []


def extract_text(pdf_path: Path) -> str:
    """Whole-document text (pages joined by newlines)."""
    return "\n".join(page_texts(pdf_path))


def extraction_method(pdf_path: Path) -> str:
    """Report which text source page_texts() would use, for provenance."""
    if _pdfplumber_pages(Path(pdf_path)):
        return "pdfplumber"
    if sidecar_text(Path(pdf_path)) is not None:
        return "txt_sidecar"
    return "none"
