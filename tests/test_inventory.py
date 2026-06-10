"""Tests for the Phase 1 inventory system.

These run against synthetic fixtures copied into a temporary repo layout, so
they never touch the real ``data/`` tree.
"""
import csv
import shutil
from pathlib import Path

import pytest

import build_document_inventory as bdi
import detect_duplicates as dd

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sample_raw"


@pytest.fixture
def repo(tmp_path):
    """A temp repo with data/raw populated from the synthetic fixtures."""
    raw = tmp_path / "data" / "raw"
    raw.parent.mkdir(parents=True)
    shutil.copytree(FIXTURES, raw)
    (tmp_path / "data" / "extracted").mkdir(parents=True)
    (tmp_path / "data" / "normalized").mkdir(parents=True)
    (tmp_path / "data" / "manual").mkdir(parents=True)
    return tmp_path


def _paths(repo: Path):
    return {
        "raw": repo / "data" / "raw",
        "inventory": repo / "data" / "extracted" / "document_inventory.csv",
        "manual": repo / "data" / "manual" / "document_classification_manual.csv",
        "summary": repo / "data" / "extracted" / "inventory_summary.md",
        "issues": repo / "data" / "normalized" / "data_quality_issues.csv",
    }


def _read(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #
def test_hash_is_deterministic_and_matches_for_identical_content(repo):
    p = _paths(repo)
    a = p["raw"] / "board_packets" / "2026-05-12" / "fy26_q3_financial_report_2026-05-12.pdf"
    b = p["raw"] / "board_packets" / "2026-06-09" / "q3_financial_report_resend.pdf"
    c = p["raw"] / "board_packets" / "2026-05-12" / "minutes.pdf"
    assert bdi.compute_file_hash(a) == bdi.compute_file_hash(a)
    assert bdi.compute_file_hash(a) == bdi.compute_file_hash(b)  # identical content
    assert bdi.compute_file_hash(a) != bdi.compute_file_hash(c)


@pytest.mark.parametrize(
    "rel, expected",
    [
        ("data/raw/board_packets/2026-05-12/fy26_q3_financial_report_2026-05-12.pdf", "quarterly_financial_report"),
        ("data/raw/board_packets/2026-05-12/minutes.pdf", "board_minutes"),
        ("data/raw/district_reports/accounts_payable_report_2026-06-09.xlsx", "accounts_payable_report"),
        ("data/raw/transcripts/2026-06-09_meeting_transcript.txt", "transcript"),
        ("data/raw/board_packets/2026-06-09/agenda.pdf", "board_packet"),
        ("data/raw/state_reports/fy25_certified_budget.pdf", "certified_budget"),
        ("data/raw/state_reports/random_thing.pdf", "generic_pdf"),
        # Audit classified by folder even when the filename lacks "audit".
        ("data/raw/district_reports/audits/Iowa City CSD-2020.pdf", "audit"),
        ("data/raw/peer_districts/audits/Ankeny CSD-2021.pdf", "audit"),
        # DOM workbooks fall through to generic_excel by extension.
        ("data/raw/state_reports/dom/UAB/Unspent Authorized Budget Report.xlsx", "generic_excel"),
    ],
)
def test_classify_document(rel, expected):
    assert bdi.classify_document(Path(rel)) == expected


def test_infer_meeting_date_prefers_full_iso_date():
    assert bdi.infer_meeting_date(Path("data/raw/board_packets/2026-05-12/x.pdf")) == "2026-05-12"
    # Placeholder folder with -xx does not parse to a real date.
    assert bdi.infer_meeting_date(Path("data/raw/board_packets/2026-05-xx/x.pdf")) == ""


def test_infer_agenda_item():
    assert bdi.infer_agenda_item("section_l_action_items.pdf") == "Section L"
    assert bdi.infer_agenda_item("minutes.pdf") == ""


def test_document_id_is_stable_across_classification():
    rel = Path("data/raw/board_packets/2026-05-12/fy26_q3_financial_report_2026-05-12.pdf")
    md = bdi.infer_meeting_date(rel)
    assert bdi.make_document_id(rel, md) == "2026-05-12_fy26_q3_financial_report_2026_05_12"


def test_document_id_disambiguates_same_filename_in_different_folders():
    a = Path("data/raw/manual_uploads/x/district-extractions/Iowa_City_CSD.csv")
    b = Path("data/raw/manual_uploads/x/notes-extractions/Iowa_City_CSD.csv")
    id_a = bdi.make_document_id(a, "")
    id_b = bdi.make_document_id(b, "")
    assert id_a != id_b
    assert "district_extractions" in id_a and "notes_extractions" in id_b


# --------------------------------------------------------------------------- #
# build_inventory
# --------------------------------------------------------------------------- #
def test_build_inventory_lists_all_source_files(repo):
    p = _paths(repo)
    rows = bdi.build_inventory(p["raw"], p["inventory"], p["manual"], repo, today="2026-06-06")
    assert len(rows) == 6  # 6 fixture files, source_urls.md/.gitkeep skipped
    assert p["inventory"].exists()
    on_disk = _read(p["inventory"])
    assert len(on_disk) == 6
    # Header matches the data dictionary.
    assert list(on_disk[0].keys()) == bdi.INVENTORY_FIELDS


def test_build_inventory_skips_metadata_files(repo):
    p = _paths(repo)
    # Metadata/provenance files next to real files must be skipped (not treated
    # as source documents — e.g. source.txt must NOT be classified as a transcript).
    (p["raw"] / "board_packets" / "2026-05-12" / "source_urls.md").write_text("x")
    (p["raw"] / "district_reports" / ".gitkeep").write_text("")
    (p["raw"] / "district_reports" / "source.txt").write_text("https://example.org")
    (p["raw"] / "district_reports" / "PROVENANCE.md").write_text("origin notes")
    rows = bdi.build_inventory(p["raw"], p["inventory"], p["manual"], repo, today="2026-06-06")
    paths = {r["file_path"] for r in rows}
    assert not any(fp.endswith("source_urls.md") for fp in paths)
    assert not any(fp.endswith(".gitkeep") for fp in paths)
    assert not any(fp.endswith("source.txt") for fp in paths)
    assert not any(fp.endswith("PROVENANCE.md") for fp in paths)


def test_skips_sidecar_text_but_keeps_standalone(repo):
    p = _paths(repo)
    folder = p["raw"] / "board_packets" / "2026-05-12"
    # A PDF with its extracted-text sidecar: the .txt must be skipped.
    (folder / "F_06_01_AP Board Report.pdf").write_text("pdf bytes")
    (folder / "F_06_01_AP Board Report.txt").write_text("extracted text")
    # The fixture transcript .txt has no same-stem document -> kept.
    rows = bdi.build_inventory(p["raw"], p["inventory"], p["manual"], repo, today="2026-06-06")
    paths = {r["file_path"] for r in rows}
    assert any(fp.endswith("F_06_01_AP Board Report.pdf") for fp in paths)
    assert not any(fp.endswith("F_06_01_AP Board Report.txt") for fp in paths)
    assert any(fp.endswith("2026-06-09_meeting_transcript.txt") for fp in paths)


def test_skips_board_packet_metadata(repo):
    p = _paths(repo)
    folder = p["raw"] / "board_packets" / "2026-05-12"
    (folder / "meeting.json").write_text("{}")
    (folder / "agenda.md").write_text("# agenda")
    (folder / "MANIFEST.md").write_text("# manifest")
    (folder / "transcript.json").write_text("{}")  # real transcript -> kept
    rows = bdi.build_inventory(p["raw"], p["inventory"], p["manual"], repo, today="2026-06-06")
    by_path = {r["file_path"]: r for r in rows}
    assert not any(fp.endswith("meeting.json") for fp in by_path)
    assert not any(fp.endswith("agenda.md") for fp in by_path)
    assert not any(fp.endswith("MANIFEST.md") for fp in by_path)
    tj = next((r for fp, r in by_path.items() if fp.endswith("transcript.json")), None)
    assert tj is not None and tj["document_type"] == "transcript"


def test_build_inventory_infers_date_and_classifies(repo):
    p = _paths(repo)
    rows = bdi.build_inventory(p["raw"], p["inventory"], p["manual"], repo, today="2026-06-06")
    by_path = {r["file_path"]: r for r in rows}
    fr = by_path["data/raw/board_packets/2026-05-12/fy26_q3_financial_report_2026-05-12.pdf"]
    assert fr["meeting_date"] == "2026-05-12"
    assert fr["document_type"] == "quarterly_financial_report"
    assert fr["status"] == "new"
    assert fr["processed"] == "false"
    assert fr["date_added"] == "2026-06-06"


def test_manual_override_takes_precedence_and_is_noted(repo):
    p = _paths(repo)
    target = "data/raw/board_packets/2026-06-09/section_l_action_items.pdf"
    with open(p["manual"], "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["document_id", "file_path", "document_type", "reason", "date_entered", "editor", "notes"]
        )
        writer.writerow(["", target, "board_packet", "manual review", "2026-06-06", "tester", ""])
    rows = bdi.build_inventory(p["raw"], p["inventory"], p["manual"], repo, today="2026-06-06")
    row = next(r for r in rows if r["file_path"] == target)
    assert row["document_type"] == "board_packet"
    assert "manually set" in row["notes"]


def test_build_inventory_is_idempotent_and_preserves_progress(repo):
    p = _paths(repo)
    bdi.build_inventory(p["raw"], p["inventory"], p["manual"], repo, today="2026-06-06")
    # Simulate a later stage marking one document processed.
    rows = _read(p["inventory"])
    rows[0]["processed"] = "true"
    rows[0]["status"] = "extracted"
    rows[0]["source_url"] = "https://example.org/doc"
    bdi.write_inventory(p["inventory"], rows)
    target_id = rows[0]["document_id"]

    # Re-run on a later date; progress fields must survive.
    again = bdi.build_inventory(p["raw"], p["inventory"], p["manual"], repo, today="2026-07-01")
    updated = next(r for r in again if r["document_id"] == target_id)
    assert updated["processed"] == "true"
    assert updated["status"] == "extracted"
    assert updated["source_url"] == "https://example.org/doc"
    assert updated["date_added"] == "2026-06-06"  # not overwritten with the new date


def test_summary_reports_counts(repo):
    p = _paths(repo)
    rows = bdi.build_inventory(p["raw"], p["inventory"], p["manual"], repo, today="2026-06-06")
    text = bdi.write_summary(p["summary"], rows)
    assert "Total documents:** 6" in text
    assert "Duplicate file groups:** 1" in text
    assert p["summary"].exists()


# --------------------------------------------------------------------------- #
# detect_duplicates
# --------------------------------------------------------------------------- #
def test_detects_duplicate_group(repo):
    p = _paths(repo)
    rows = bdi.build_inventory(p["raw"], p["inventory"], p["manual"], repo, today="2026-06-06")
    groups = dd.find_duplicate_groups(rows)
    assert len(groups) == 1
    assert len(groups[0]) == 2
    dup_paths = {r["file_path"] for r in groups[0]}
    assert dup_paths == {
        "data/raw/board_packets/2026-05-12/fy26_q3_financial_report_2026-05-12.pdf",
        "data/raw/board_packets/2026-06-09/q3_financial_report_resend.pdf",
    }


def test_detect_issues_flags_expected_types(repo):
    p = _paths(repo)
    rows = bdi.build_inventory(p["raw"], p["inventory"], p["manual"], repo, today="2026-06-06")
    issues = dd.detect_issues(rows, run_date="2026-06-06")
    types = {i["issue_type"] for i in issues}
    assert "duplicate_document" in types
    assert "missing_source_url" in types  # fixtures have no source_url
    # All 6 fixtures lack a source_url.
    assert sum(1 for i in issues if i["issue_type"] == "missing_source_url") == 6


def test_write_issues_preserves_other_stages(repo):
    p = _paths(repo)
    # Pre-seed an issue from a hypothetical later stage.
    with open(p["issues"], "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=dd.ISSUE_FIELDS)
        writer.writeheader()
        writer.writerow(
            {
                "run_date": "2026-06-01",
                "severity": "critical",
                "issue_type": "negative_cash_balance",
                "fund_code": "10",
                "document_id": "",
                "description": "from another stage",
                "recommended_action": "keep me",
                "status": "open",
            }
        )
    rows = bdi.build_inventory(p["raw"], p["inventory"], p["manual"], repo, today="2026-06-06")
    issues = dd.detect_issues(rows, run_date="2026-06-06")
    dd.write_issues(p["issues"], issues)

    on_disk = _read(p["issues"])
    issue_types = {r["issue_type"] for r in on_disk}
    assert "negative_cash_balance" in issue_types  # preserved
    assert "duplicate_document" in issue_types  # added

    # Running again should not duplicate the managed rows.
    dd.write_issues(p["issues"], dd.detect_issues(rows, run_date="2026-06-07"))
    second = _read(p["issues"])
    assert sum(1 for r in second if r["issue_type"] == "negative_cash_balance") == 1
    assert sum(1 for r in second if r["issue_type"] == "duplicate_document") == 1
