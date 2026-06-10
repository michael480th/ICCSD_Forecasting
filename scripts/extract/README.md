# scripts/extract

The text/table extraction layer that sits between raw PDFs and the
document-type-specific extractors in `scripts/extractors/`.

## Implemented

### `extract_pdf_text.py`
Returns a PDF's text as a list of per-page strings via **pdfplumber**, falling
back to a same-stem `.txt` sidecar when pdfplumber is unavailable or a PDF yields
no text (the board-packet corpus ships extracted-text sidecars). pdfplumber is
imported lazily, so extractors that import this module still load without it.

Key functions: `page_texts(path)`, `extract_text(path)`, `extraction_method(path)`.

> Requires `pdfplumber` (see `requirements.txt`). In some environments a stale
> system `cryptography` (pulled in by `pdfminer.six`) can break the import; a
> fresh `pip install --upgrade cryptography` resolves it. The sidecar fallback
> keeps extraction working regardless.

## Planned
`extract_pdf_tables.py`, `extract_excel_files.py`, `extract_transcripts.py`.
