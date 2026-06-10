#!/usr/bin/env python3
"""Extractor: ICCSD quarterly financial report.

Parses the district's quarterly "Financial Report" PDFs (FY26 Q2, Q3, …) into
two canonical tables:

- ``receipts_disbursements.csv`` — the **Combined Statement of Receipts and
  Disbursements (Cash Basis)**: per-fund beginning balance, budgeted/actual
  receipts and disbursements, and ending balance. This is the cleanest per-fund
  cash position in the deck and the forecast's main "beginning cash" source.
- ``cash_balances.csv`` — the **Cash and Investments Detail**: cash-in-bank vs.
  investments by fund group, as of the reporting date.

The same layout appears in every quarter, so one parser handles them all.
Documents are matched by content (the Combined-Statement marker), not just by
their inventory ``document_type``, so the Q3 report — filed under the title
"Financials as of 3.31.26" — is picked up too.

Robustness notes:
- Amounts in these PDFs extract with stray intra-number spaces (``$ 1 7,852,375``
  meaning 17,852,375). Amounts are isolated by splitting each row on ``$`` and
  then stripping spaces, so the artifact is handled regardless of text source.
- Parentheses denote negatives; ``-`` / blank denote zero/empty.

Run:  python scripts/extractors/quarterly_financial_report.py
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "extract"))
import extract_pdf_text as ept  # noqa: E402

INVENTORY_PATH = REPO_ROOT / "data" / "extracted" / "document_inventory.csv"
RD_PATH = REPO_ROOT / "data" / "normalized" / "receipts_disbursements.csv"
CASH_PATH = REPO_ROOT / "data" / "normalized" / "cash_balances.csv"
MONTHLY_PATH = REPO_ROOT / "data" / "normalized" / "monthly_actuals.csv"

COMBINED_MARKER = "Combined Statement of Receipts and Disbursements"

# Fiscal-year months in order (July .. June).
MONTHS = ["July", "August", "September", "October", "November", "December",
          "January", "February", "March", "April", "May", "June"]

# Canonical fund names for the per-fund Combined Statement (keyed by fund code).
FUND_NAMES = {
    "10": "General Fund",
    "21": "Student Activity Fund",
    "22": "Management Fund",
    "33": "SAVE",
    "36": "PPEL",
    "40": "Debt Service Fund",
    "61": "School Nutrition Fund",
}

# Cash & Investments Detail groups: (source label, representative fund_code, name).
CASH_GROUPS = [
    ("General (10, 84)", "10", "General Fund (incl. 84)"),
    ("Activity (21)", "21", "Student Activity Fund"),
    ("Capital Projects and Bonds (33, 36)", "33", "Capital Projects & Bonds (SAVE 33, PPEL 36)"),
    ("Nutrition (61)", "61", "School Nutrition Fund"),
    ("Insurance (71, 74)", "71", "Insurance (71, 74)"),
    ("Children's Aid (82)", "82", "Children's Aid (82)"),
    ("Total All Funds", "ALL", "Total All Funds"),
]

RD_FIELDS = [
    "period_end", "fund_code", "fund_name", "beginning_balance",
    "budgeted_receipts", "receipts_to_date", "budgeted_disbursements",
    "disbursements_to_date", "ending_balance", "source_file", "source_page",
    "confidence",
]
CASH_FIELDS = [
    "as_of_date", "fund_code", "fund_name", "cash_in_bank", "investments",
    "total_cash_investments", "source_file", "source_page", "extraction_method",
    "confidence", "notes",
]
MONTHLY_FIELDS = [
    "month", "fund_code", "fund_name", "line_item", "type", "amount",
    "source_file", "source_page", "confidence", "notes",
]


# --------------------------------------------------------------------------- #
# Number / date helpers
# --------------------------------------------------------------------------- #
def clean_amount(chunk: str) -> float | None:
    """Parse one money value, tolerating ``$``, commas, parens, and the stray
    intra-number spaces these PDFs produce (``1 7,852,375`` -> 17852375)."""
    s = chunk.replace("$", "").strip()
    if not s or s in {"-", "–", "—"}:
        return None
    neg = "(" in s and ")" in s
    s = re.sub(r"[(),]", "", s)
    s = s.replace(" ", "")
    if s in {"", "-"}:
        return None
    try:
        val = float(s)
    except ValueError:
        return None
    return -val if neg else val


def _strip_trailing_percent(chunk: str) -> str:
    """Drop a trailing percentage (and anything after it) from a $-chunk."""
    return re.sub(r"[\d.]+\s*%.*$", "", chunk)


def fmt(val: float | None) -> str:
    if val is None:
        return ""
    return str(int(val)) if float(val).is_integer() else str(val)


def parse_period_end(text: str) -> str | None:
    """ISO date from 'Period Ending M/D/YYYY' (or 'As of M/D/YYYY')."""
    m = re.search(r"(?:Period Ending|As of)\s+(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if not m:
        return None
    mo, da, yr = (int(g) for g in m.groups())
    return f"{yr:04d}-{mo:02d}-{da:02d}"


# --------------------------------------------------------------------------- #
# Table parsers (operate on a list of per-page text strings)
# --------------------------------------------------------------------------- #
def _amounts_from_row(line: str, after: str) -> list[float | None]:
    """Split the part of ``line`` after the prefix ``after`` on '$' and parse
    each chunk as a money value (stripping any trailing percentage)."""
    tail = line.split(after, 1)[1] if after in line else line
    return [clean_amount(_strip_trailing_percent(c)) for c in tail.split("$")[1:]]


def parse_combined_statement(pages: list[str]):
    """Return (rows, source_page, period_end) for the Combined Statement."""
    for idx, text in enumerate(pages):
        if COMBINED_MARKER not in text:
            continue
        period_end = parse_period_end(text)
        rows = []
        for line in text.splitlines():
            m = re.match(r"\s*(10|21|22|33|36|40|61)\s", line)
            if not m or "$" in line[: m.start()] or "$" not in line:
                continue
            code = m.group(1)
            head = f"{code} "
            vals = _amounts_from_row(line, head)
            if len(vals) < 6:
                continue
            bal, bud_rec, rec_td, bud_dis, dis_td, ending = vals[:6]
            rows.append(
                {
                    "fund_code": code,
                    "fund_name": FUND_NAMES[code],
                    "beginning_balance": bal,
                    "budgeted_receipts": bud_rec,
                    "receipts_to_date": rec_td,
                    "budgeted_disbursements": bud_dis,
                    "disbursements_to_date": dis_td,
                    "ending_balance": ending,
                }
            )
        if rows:
            return rows, idx + 1, period_end
    return [], None, None


def _label_regex(label: str) -> re.Pattern:
    rx = re.escape(label).replace(r"\ ", r"\s+").replace("'", "['’]")
    return re.compile(rx)


def parse_cash_detail(pages: list[str]):
    """Return (rows, source_page, as_of_date) for the Cash & Investments Detail.

    Each detail line also carries a side-by-side "Cash Totals by Quarter" table
    with the same repeated label; we take the text after the *last* label
    occurrence (the detail portion, which ends in a weighted-portion %), then
    read cash-in-bank as the first amount and total as the last, deriving
    investments = total - cash."""
    target = next((i for i, t in enumerate(pages)
                   if "Cash and Investments Detail" in t or "Cash and Investment Totals" in t), None)
    if target is None:
        return [], None, None
    text = pages[target]
    as_of = parse_period_end(text)
    rows = []
    for label, code, name in CASH_GROUPS:
        rx = _label_regex(label)
        line = next((ln for ln in text.splitlines()
                     if rx.search(ln) and ln.rstrip().endswith("%") and "$" in ln), None)
        if not line:
            continue
        last = list(rx.finditer(line))[-1]
        nums = [clean_amount(_strip_trailing_percent(c))
                for c in line[last.end():].split("$")[1:]]
        nums = [n for n in nums if n is not None] or [None]
        cash, total = nums[0], nums[-1]
        if cash is None or total is None or total < cash:
            continue  # don't emit a row we can't trust
        rows.append(
            {
                "fund_code": code,
                "fund_name": name,
                "cash_in_bank": cash,
                "investments": total - cash,
                "total_cash_investments": total,
                "notes": "grouped per source; investments = total - cash_in_bank",
            }
        )
    return rows, target + 1, as_of


# --------------------------------------------------------------------------- #
# General Fund revenue / expenditure by month (seasonality)
# --------------------------------------------------------------------------- #
def _fy_month_isos(fy: int) -> list[str]:
    """ISO YYYY-MM for each fiscal-year month (July fy-1 .. June fy)."""
    out = []
    for i in range(12):
        out.append(f"{fy - 1}-{7 + i:02d}" if i < 6 else f"{fy}-{i - 5:02d}")
    return out


def parse_monthly_gf(pages: list[str]):
    """Parse the prior-year (complete FY) General Fund revenue & expenditure
    by-month tables. Returns (rows, source_page, fiscal_year).

    These tables show 12 months (July..June) then Accruals and Total; we keep the
    first 12 amounts as the monthly series. The "Prior Year" table is the complete
    fiscal year, so it's the seasonality source. Aggregate ("Total Monthly …")
    rows are returned with line_item flagged so callers can validate or skip them.
    """
    text = "\n".join(pages)
    lines = text.splitlines()
    rows: list[dict] = []
    section = None
    fy = None
    capture = False
    page_no = next((i + 1 for i, p in enumerate(pages)
                    if "Revenue by Month" in p), None)
    for ln in lines:
        s = ln.strip()
        if s.startswith("General Fund Revenue by Month"):
            section, capture = "revenue", False
            continue
        if s.startswith("General Fund Expenditures by Month"):
            section, capture = "expenditure", False
            continue
        m = re.search(r"Prior Year \(Period Ending 6/30/(\d{4})\)", ln)
        if m and section:
            fy, capture = int(m.group(1)), True
            continue
        if "Current Year (Period Ending" in ln or s.startswith(("Total YTD", "Prior Year vs")):
            capture = False
            continue
        if not capture or section is None or "$" not in ln:
            continue
        label = ln.split("$")[0].strip()
        if not label or label.lower().startswith(("current year", "fund")):
            continue
        chunks = ln.split("$")[1:]
        if len(chunks) < 12:  # a monthly row has 12 months (+ accruals + total)
            continue
        # In these tables a "$ -" / blank month means $0, not a missing value.
        months = [clean_amount(_strip_trailing_percent(c)) or 0.0 for c in chunks][:12]
        is_total = label.lower().startswith("total monthly")
        for iso, amt in zip(_fy_month_isos(fy), months):
            rows.append({
                "month": iso, "line_item": label, "type": section,
                "amount": amt, "is_total": is_total,
            })
    return rows, page_no, fy


# --------------------------------------------------------------------------- #
# Public extractor interface
# --------------------------------------------------------------------------- #
def can_handle(pages: list[str]) -> bool:
    return any(COMBINED_MARKER in p for p in pages)


def extract(pages: list[str]) -> dict:
    rd_rows, rd_page, period_end = parse_combined_statement(pages)
    cash_rows, cash_page, as_of = parse_cash_detail(pages)
    monthly_rows, monthly_page, monthly_fy = parse_monthly_gf(pages)
    return {
        "period_end": period_end,
        "as_of_date": as_of or period_end,
        "receipts_disbursements": rd_rows,
        "rd_page": rd_page,
        "cash_balances": cash_rows,
        "cash_page": cash_page,
        "monthly_gf": monthly_rows,
        "monthly_page": monthly_page,
        "monthly_fy": monthly_fy,
    }


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #
def _candidate_docs(inventory_path: Path) -> list[dict]:
    if not inventory_path.exists():
        return []
    types = {"quarterly_financial_report", "monthly_financial_report"}
    with open(inventory_path, newline="", encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh) if r["document_type"] in types]


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def main() -> None:
    docs = _candidate_docs(INVENTORY_PATH)
    rd_all, cash_all, monthly_all = [], [], []
    seen_monthly_fy = set()  # the prior-year monthly table repeats across reports
    handled = 0
    for doc in docs:
        pdf = REPO_ROOT / doc["file_path"]
        if not pdf.exists():
            continue
        pages = ept.page_texts(pdf)
        if not can_handle(pages):
            continue
        handled += 1
        method = ept.extraction_method(pdf)
        result = extract(pages)
        src = doc["file_path"]
        for r in result["receipts_disbursements"]:
            rd_all.append({
                "period_end": result["period_end"] or "",
                **{k: fmt(r[k]) if isinstance(r.get(k), float) else r[k] for k in r},
                "source_file": src,
                "source_page": result["rd_page"] or "",
                "confidence": "medium",
            })
        for r in result["cash_balances"]:
            cash_all.append({
                "as_of_date": result["as_of_date"] or "",
                **{k: fmt(r[k]) if isinstance(r.get(k), float) else r[k] for k in r},
                "source_file": src,
                "source_page": result["cash_page"] or "",
                "extraction_method": f"{method}+quarterly_financial_report",
                "confidence": "medium",
            })
        mfy = result["monthly_fy"]
        if mfy is not None and mfy not in seen_monthly_fy:
            seen_monthly_fy.add(mfy)
            for r in result["monthly_gf"]:
                if r["is_total"]:
                    continue  # aggregate row; line items are written individually
                monthly_all.append({
                    "month": r["month"], "fund_code": "10", "fund_name": "General Fund",
                    "line_item": r["line_item"], "type": r["type"], "amount": fmt(r["amount"]),
                    "source_file": src, "source_page": result["monthly_page"] or "",
                    "confidence": "medium",
                    "notes": f"FY{mfy} actual (prior-year table)",
                })

    _write(RD_PATH, RD_FIELDS, rd_all)
    _write(CASH_PATH, CASH_FIELDS, cash_all)
    _write(MONTHLY_PATH, MONTHLY_FIELDS, monthly_all)
    print(f"Quarterly financial report extractor: handled {handled} document(s).")
    print(f"  receipts_disbursements rows: {len(rd_all)} -> {RD_PATH.relative_to(REPO_ROOT)}")
    print(f"  cash_balances rows:          {len(cash_all)} -> {CASH_PATH.relative_to(REPO_ROOT)}")
    print(f"  monthly_actuals rows:        {len(monthly_all)} -> {MONTHLY_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
