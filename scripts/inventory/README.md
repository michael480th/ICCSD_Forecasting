# scripts/inventory

Phase 1 — the document inventory system. Implemented.

| Script | What it does | Writes |
|--------|--------------|--------|
| `build_document_inventory.py` | Walks `data/raw/`, hashes every file (SHA-256), infers meeting date + agenda item, classifies the document (auto rules + manual overrides), and builds the registry. Idempotent: preserves `processed`/`status`/`date_added` for known documents. | `data/extracted/document_inventory.csv`, `data/extracted/inventory_summary.md` |
| `detect_duplicates.py` | Reads the inventory and flags exact duplicates (identical content hash), unknown/generic document types, missing source URLs, and missing meeting dates. Preserves issues owned by other stages. | `data/normalized/data_quality_issues.csv` |

## Run

```bash
python scripts/inventory/build_document_inventory.py
python scripts/inventory/detect_duplicates.py
```

Both run safely against an empty `data/raw/` (they produce header-only output).

## Classification

Auto-classification uses filename, folder, and extension signals plus manual
overrides in `data/manual/document_classification_manual.csv` (matched by
`file_path`). First-page-text classification is deferred to a later phase
because it depends on the extraction layer (pdfplumber).

To override a document's type, add a row to the manual file:

```csv
document_id,file_path,document_type,reason,date_entered,editor,notes
,data/raw/board_packets/2026-06-09/section_l_action_items.pdf,board_packet,reviewed,2026-06-06,mh,
```

## Tests

`tests/test_inventory.py` covers hashing, classification, date/agenda inference,
manual-override precedence, idempotency, duplicate detection, and quality-issue
flagging — run against synthetic fixtures in `tests/fixtures/sample_raw/`.

```bash
python -m pytest tests/test_inventory.py -q
```
