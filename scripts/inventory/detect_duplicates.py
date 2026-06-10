#!/usr/bin/env python3
"""Detect duplicate documents and basic inventory-quality issues.

Phase 1 of the ICCashForecast pipeline. Reads
``data/extracted/document_inventory.csv`` and flags:

- **Exact duplicates** — two or more files with identical content hashes
  (same document re-saved under different names / in different folders).
- **Unknown document types** — files still classified as generic/unclassified.
- **Missing source URLs** — inventoried files with no recorded provenance URL.
- **Missing meeting dates** — files with no inferred meeting/report date.

Findings are written to ``data/normalized/data_quality_issues.csv``. Only the
issue types this stage owns are rewritten; rows produced by other stages are
preserved, so the run is idempotent and safe to interleave.

Run from anywhere:

    python scripts/inventory/detect_duplicates.py
"""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = REPO_ROOT / "data" / "extracted" / "document_inventory.csv"
ISSUES_PATH = REPO_ROOT / "data" / "normalized" / "data_quality_issues.csv"

ISSUE_FIELDS = [
    "run_date",
    "severity",
    "issue_type",
    "fund_code",
    "document_id",
    "description",
    "recommended_action",
    "status",
]

# Issue types owned by this stage (rewritten on each run; others preserved).
MANAGED_ISSUE_TYPES = {
    "duplicate_document",
    "unknown_document_type",
    "missing_source_url",
    "missing_meeting_date",
}

UNKNOWN_TYPES = {"", "generic_pdf", "generic_excel"}


def read_inventory(inventory_path: Path) -> list[dict]:
    if not inventory_path.exists():
        return []
    with open(inventory_path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def find_duplicate_groups(rows: list[dict]) -> list[list[dict]]:
    """Return groups of rows that share an identical file_hash (size > 1)."""
    by_hash: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        h = (row.get("file_hash") or "").strip()
        if h:
            by_hash[h].append(row)
    return [g for g in by_hash.values() if len(g) > 1]


def detect_issues(rows: list[dict], *, run_date: str | None = None) -> list[dict]:
    """Build issue rows for duplicates and basic provenance gaps."""
    run_date = run_date or date.today().isoformat()
    issues: list[dict] = []

    def add(severity, issue_type, document_id, description, action):
        issues.append(
            {
                "run_date": run_date,
                "severity": severity,
                "issue_type": issue_type,
                "fund_code": "",
                "document_id": document_id,
                "description": description,
                "recommended_action": action,
                "status": "open",
            }
        )

    # Exact duplicates.
    for group in find_duplicate_groups(rows):
        paths = ", ".join(sorted(r.get("file_path", "") for r in group))
        ids = ", ".join(sorted(r.get("document_id", "") for r in group))
        add(
            "warning",
            "duplicate_document",
            ids,
            f"{len(group)} files share identical content: {paths}",
            "Keep one canonical copy or confirm the duplicate is intentional; "
            "mark extras as status=duplicate.",
        )

    # Per-document provenance / classification gaps.
    for row in rows:
        doc_id = row.get("document_id", "")
        dtype = (row.get("document_type") or "").strip()
        if dtype in UNKNOWN_TYPES:
            add(
                "info",
                "unknown_document_type",
                doc_id,
                f"Document '{row.get('file_path', '')}' is unclassified "
                f"(type={dtype or 'none'}).",
                "Classify in data/manual/document_classification_manual.csv.",
            )
        if not (row.get("source_url") or "").strip():
            add(
                "info",
                "missing_source_url",
                doc_id,
                f"No source_url recorded for '{row.get('file_path', '')}'.",
                "Record the public URL in the inventory or a source_urls.md.",
            )
        if not (row.get("meeting_date") or "").strip():
            add(
                "info",
                "missing_meeting_date",
                doc_id,
                f"No meeting/report date for '{row.get('file_path', '')}'.",
                "Place the file in a dated folder (YYYY-MM-DD) or set the date "
                "via a manual override.",
            )
    return issues


def write_issues(issues_path: Path, new_issues: list[dict]) -> None:
    """Replace this stage's managed issues; preserve other stages' rows."""
    preserved: list[dict] = []
    if issues_path.exists():
        with open(issues_path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if (row.get("issue_type") or "") not in MANAGED_ISSUE_TYPES:
                    preserved.append(row)

    issues_path.parent.mkdir(parents=True, exist_ok=True)
    with open(issues_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=ISSUE_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in preserved + new_issues:
            writer.writerow({k: row.get(k, "") for k in ISSUE_FIELDS})


def main() -> None:
    rows = read_inventory(INVENTORY_PATH)
    issues = detect_issues(rows)
    write_issues(ISSUES_PATH, issues)

    dup_groups = find_duplicate_groups(rows)
    by_type: dict[str, int] = defaultdict(int)
    for issue in issues:
        by_type[issue["issue_type"]] += 1

    print(f"Scanned {len(rows)} inventoried document(s).")
    print(f"  Duplicate groups: {len(dup_groups)}")
    for issue_type in sorted(MANAGED_ISSUE_TYPES):
        print(f"  {issue_type}: {by_type.get(issue_type, 0)}")
    print(f"  -> {ISSUES_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
