#!/usr/bin/env python3
"""Build the document inventory from files under data/raw/.

Phase 1 of the ICCashForecast pipeline. Walks the raw-document tree, hashes
every file, classifies it (auto rules + manual overrides), and writes
``data/extracted/document_inventory.csv``. Also writes a human-readable
``data/extracted/inventory_summary.md``.

The builder is idempotent: re-running preserves ``date_added``, ``processed``,
and ``status`` for documents already present in the inventory (keyed by
``document_id``), so later pipeline stages can mark progress without it being
overwritten.

Classification in this phase uses filename, folder, and extension signals plus
manual overrides. First-page-text classification is intentionally deferred to a
later phase (it requires the extraction layer / pdfplumber).

Run from anywhere:

    python scripts/inventory/build_document_inventory.py
"""
from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
INVENTORY_PATH = REPO_ROOT / "data" / "extracted" / "document_inventory.csv"
MANUAL_PATH = REPO_ROOT / "data" / "manual" / "document_classification_manual.csv"
SUMMARY_PATH = REPO_ROOT / "data" / "extracted" / "inventory_summary.md"

INVENTORY_FIELDS = [
    "document_id",
    "file_hash",
    "file_path",
    "meeting_date",
    "agenda_item",
    "document_type",
    "title",
    "source_url",
    "date_added",
    "processed",
    "status",
    "notes",
]

# Files that are not source documents and should never be inventoried.
IGNORE_NAMES = {
    ".gitkeep",
    ".ds_store",
    "source_urls.md",
    "source.txt",
    "readme.md",
    "provenance.md",
    "blank.txt",
    "text.txt",
    # Per-folder board-packet metadata (generated indices / structure), not
    # standalone source documents.
    "meeting.json",
    "agenda.md",
    "manifest.md",
}

# A ".txt" that sits next to a same-stem document is that document's extracted
# text (a sidecar), not a separate source document — skip it when inventorying.
SIDECAR_EXTS = {".txt"}
DOCUMENT_EXTS = {".pdf", ".docx", ".doc", ".xlsx", ".xls"}

# Document types we treat as "not yet meaningfully classified".
UNKNOWN_TYPES = {"", "generic_pdf", "generic_excel"}

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


# --------------------------------------------------------------------------- #
# Pure helpers (unit-testable in isolation)
# --------------------------------------------------------------------------- #
def compute_file_hash(path: Path, *, chunk_size: int = 1 << 16) -> str:
    """Return the SHA-256 hex digest of a file's contents."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def infer_meeting_date(rel_path: Path) -> str:
    """Infer a meeting/report date (YYYY-MM-DD) from the path, else ''.

    Looks for a full ISO date in a folder name first (e.g.
    ``board_packets/2026-05-12/...``), then in the filename. Placeholder
    folders such as ``2026-05-xx`` do not match and yield ''.
    """
    for part in rel_path.parts:
        m = _DATE_RE.search(part)
        if m:
            return m.group(1)
    return ""


def infer_agenda_item(filename: str) -> str:
    """Derive an agenda-item label from a filename like ``section_f_consent``."""
    m = re.search(r"section[_-]([a-z])(?:[_-]|\.|$)", filename.lower())
    if m:
        return f"Section {m.group(1).upper()}"
    return ""


def make_title(filename: str) -> str:
    """Human-readable title from a filename stem."""
    stem = Path(filename).stem
    return stem.replace("_", " ").replace("-", " ").strip()


def make_document_id(rel_path: Path, meeting_date: str) -> str:
    """Stable, human-readable id independent of classification.

    Uses the meeting date (or ``undated``) plus a slug of the filename stem, so
    re-running and re-classifying never changes a document's id. The immediate
    parent folder is included when it adds information (i.e. when it isn't just
    the date folder already used as the prefix), so files that share a filename
    across folders — e.g. ``district-extractions/Iowa_City_CSD.csv`` and
    ``notes-extractions/Iowa_City_CSD.csv`` — get distinct ids.
    """
    def slugify(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")

    stem_slug = slugify(rel_path.stem)
    prefix = meeting_date if meeting_date else "undated"
    parent_slug = slugify(rel_path.parent.name)
    date_slug = slugify(meeting_date)

    parts = [prefix]
    if parent_slug and parent_slug not in {date_slug, "raw", ""}:
        parts.append(parent_slug)
    parts.append(stem_slug)
    return "_".join(parts)


def classify_document(rel_path: Path) -> str:
    """Auto-classify a document by filename / folder / extension signals.

    Returns one of the recognized document_type values from the data
    dictionary. Falls back to ``generic_pdf`` / ``generic_excel`` / '' so that
    unknowns are surfaced by duplicate/quality detection rather than guessed.
    """
    name = rel_path.name.lower()
    parts = {p.lower() for p in rel_path.parts}
    ext = rel_path.suffix.lower()

    def has(*needles: str) -> bool:
        return all(n in name for n in needles)

    # Most specific first.
    if has("quarterly") and "financial" in name:
        return "quarterly_financial_report"
    if has("monthly") and "financial" in name:
        return "monthly_financial_report"
    if "accounts_payable" in name or re.search(r"\bap\b", name):
        return "accounts_payable_report"
    if "cfo" in name:
        return "cfo_update"
    if "financial" in name and ("update" in name or "leadership" in name):
        return "board_financial_update"
    if "minutes" in name:
        return "board_minutes"
    if "agenda" in name:
        return "board_packet"
    if "amendment" in name and "budget" in name:
        return "budget_amendment"
    if "certified" in name and "budget" in name:
        return "certified_budget"
    if "annual" in name and ("report" in name or "financial" in name):
        return "annual_financial_report"
    if "audit" in name or {"audits", "auditreports"} & parts:
        return "audit"
    if "debt" in name:
        return "debt_schedule"
    if "interfund" in name and ("loan" in name or "transfer" in name):
        return "interfund_loan_document"
    if "property" in name and ("sale" in name or "closing" in name):
        return "property_sale_document"
    if "capital" in name and ("project" in name or "update" in name):
        return "capital_project_update"
    if "transcript" in name or ext == ".txt" or "transcripts" in parts:
        return "transcript"
    if "packet" in name:
        return "board_packet"
    if "financial" in name and "report" in name:
        return "quarterly_financial_report"

    # Extension fallbacks.
    if ext in {".xlsx", ".xls", ".csv"}:
        return "generic_excel"
    if ext == ".pdf":
        return "generic_pdf"
    return ""


# --------------------------------------------------------------------------- #
# I/O
# --------------------------------------------------------------------------- #
def load_manual_classifications(manual_path: Path) -> dict[str, str]:
    """Map ``file_path`` -> overridden ``document_type`` from the manual file."""
    overrides: dict[str, str] = {}
    if not manual_path.exists():
        return overrides
    with open(manual_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            fp = (row.get("file_path") or "").strip()
            dt = (row.get("document_type") or "").strip()
            if fp and dt:
                overrides[fp] = dt
    return overrides


def load_existing_inventory(inventory_path: Path) -> dict[str, dict]:
    """Map ``document_id`` -> existing row, to preserve progress fields."""
    existing: dict[str, dict] = {}
    if not inventory_path.exists():
        return existing
    with open(inventory_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            doc_id = (row.get("document_id") or "").strip()
            if doc_id:
                existing[doc_id] = row
    return existing


def is_sidecar_text(path: Path) -> bool:
    """True if ``path`` is the extracted-text sidecar of a same-stem document."""
    if path.suffix.lower() not in SIDECAR_EXTS:
        return False
    return any(path.with_suffix(ext).exists() for ext in DOCUMENT_EXTS)


def iter_source_files(raw_dir: Path):
    """Yield source-document paths under ``raw_dir``, skipping ignored files."""
    for path in sorted(raw_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name.lower() in IGNORE_NAMES or path.name.startswith("."):
            continue
        if is_sidecar_text(path):
            continue
        yield path


# --------------------------------------------------------------------------- #
# Core
# --------------------------------------------------------------------------- #
def build_inventory(
    raw_dir: Path,
    inventory_path: Path,
    manual_path: Path,
    repo_root: Path,
    *,
    today: str | None = None,
) -> list[dict]:
    """Scan ``raw_dir`` and return inventory rows (also written to CSV)."""
    today = today or date.today().isoformat()
    overrides = load_manual_classifications(manual_path)
    existing = load_existing_inventory(inventory_path)

    rows: list[dict] = []
    seen_ids: set[str] = set()
    for path in iter_source_files(raw_dir):
        rel_path = path.relative_to(repo_root)
        rel_str = rel_path.as_posix()
        meeting_date = infer_meeting_date(rel_path)
        doc_id = make_document_id(rel_path, meeting_date)
        if doc_id in seen_ids:  # guarantee uniqueness even on a slug collision
            suffix = 2
            while f"{doc_id}_{suffix}" in seen_ids:
                suffix += 1
            doc_id = f"{doc_id}_{suffix}"
        seen_ids.add(doc_id)

        auto_type = classify_document(rel_path)
        override_type = overrides.get(rel_str)
        document_type = override_type or auto_type

        prior = existing.get(doc_id, {})
        notes = prior.get("notes", "") or ""
        if override_type and override_type != auto_type:
            note = f"document_type manually set (auto guess: {auto_type or 'none'})"
            notes = note if note not in notes else notes

        rows.append(
            {
                "document_id": doc_id,
                "file_hash": compute_file_hash(path),
                "file_path": rel_str,
                "meeting_date": meeting_date,
                "agenda_item": infer_agenda_item(path.name),
                "document_type": document_type,
                "title": make_title(path.name),
                "source_url": prior.get("source_url", "") or "",
                "date_added": prior.get("date_added") or today,
                "processed": prior.get("processed") or "false",
                "status": prior.get("status") or "new",
                "notes": notes,
            }
        )

    write_inventory(inventory_path, rows)
    return rows


def write_inventory(inventory_path: Path, rows: list[dict]) -> None:
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    with open(inventory_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=INVENTORY_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in INVENTORY_FIELDS})


def summarize_inventory(rows: list[dict]) -> str:
    """Build a Markdown summary report of the inventory."""
    total = len(rows)
    by_type = Counter(r["document_type"] or "(unclassified)" for r in rows)
    by_status = Counter(r["status"] or "(none)" for r in rows)

    hashes = Counter(r["file_hash"] for r in rows)
    dup_hashes = {h for h, c in hashes.items() if c > 1}
    dup_files = sum(c for h, c in hashes.items() if c > 1)

    unknown = sum(1 for r in rows if (r["document_type"] or "") in UNKNOWN_TYPES)
    missing_url = sum(1 for r in rows if not (r.get("source_url") or "").strip())
    missing_date = sum(1 for r in rows if not (r.get("meeting_date") or "").strip())

    lines = [
        "# Inventory summary",
        "",
        f"- **Total documents:** {total}",
        f"- **Duplicate file groups:** {len(dup_hashes)} "
        f"({dup_files} files share content with another)",
        f"- **Unknown / generic document type:** {unknown}",
        f"- **Missing source URL:** {missing_url}",
        f"- **Missing meeting/report date:** {missing_date}",
        "",
        "## By document type",
        "",
        "| document_type | count |",
        "|---------------|-------|",
    ]
    for dt, count in sorted(by_type.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| {dt} | {count} |")
    lines += ["", "## By status", "", "| status | count |", "|--------|-------|"]
    for st, count in sorted(by_status.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| {st} | {count} |")
    lines.append("")
    return "\n".join(lines)


def write_summary(summary_path: Path, rows: list[dict]) -> str:
    text = summarize_inventory(rows)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(text, encoding="utf-8")
    return text


def main() -> None:
    rows = build_inventory(RAW_DIR, INVENTORY_PATH, MANUAL_PATH, REPO_ROOT)
    write_summary(SUMMARY_PATH, rows)
    print(f"Inventoried {len(rows)} document(s).")
    print(f"  -> {INVENTORY_PATH.relative_to(REPO_ROOT)}")
    print(f"  -> {SUMMARY_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
