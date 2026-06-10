"""Tests for the quarterly financial report extractor."""
from pathlib import Path

import pytest

import quarterly_financial_report as qfr

REPO = Path(__file__).resolve().parent.parent
Q2_SIDECAR = (
    REPO / "data/raw/board_packets/2026-02-10_Board_of_Directors/attachments/"
    "K_02_01_FY26 Quarter 2 Financial Report (1).txt"
)


# --------------------------------------------------------------------------- #
# Number / date helpers
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("$ 17,852,375", 17852375.0),
        ("$ 1 7,852,375", 17852375.0),     # stray intra-number space artifact
        ("$ 2 18,169,788", 218169788.0),
        ("$ (191,113)", -191113.0),        # parentheses = negative
        ("$ -", None),
        ("   ", None),
        ("$ 2,084,441.41", 2084441.41),    # decimals preserved
    ],
)
def test_clean_amount(raw, expected):
    assert qfr.clean_amount(raw) == expected


def test_parse_period_end():
    assert qfr.parse_period_end("Period Ending 12/31/2025") == "2025-12-31"
    assert qfr.parse_period_end("As of 3/31/2026") == "2026-03-31"
    assert qfr.parse_period_end("no date here") is None


# --------------------------------------------------------------------------- #
# Combined Statement of Receipts and Disbursements
# --------------------------------------------------------------------------- #
COMBINED = """2025-2026 Combined Statement of Receipts and Disbursements (Cash Basis)
Period Ending 12/31/2025
Fund # Fund Description Balance as of 7/1/2025 Budgeted Receipts Receipts to Date ...
10 General Fund $ 1 7,852,375 $ 221,745,164 $ 94,256,177 42.5% $ 215,222,547 $ 86,401,778 40.1% $ 25,706,774
21 Student Activity Fund $ 438,424 $ 3,520,061 $ 2,042,817 58.0% $ 3,800,000 $ 2,672,353 70.3% $ (191,113)
Total $ 48,784,438 $ 292,013,651 $ 136,866,427 46.9% $ 286,728,130 $ 126,836,671 44.2% $ 58,814,193
"""


def test_parse_combined_statement():
    rows, page, period_end = qfr.parse_combined_statement([COMBINED])
    assert page == 1 and period_end == "2025-12-31"
    gf = next(r for r in rows if r["fund_code"] == "10")
    assert gf["beginning_balance"] == 17852375.0     # artifact cleaned
    assert gf["receipts_to_date"] == 94256177.0       # percentage stripped
    assert gf["ending_balance"] == 25706774.0
    act = next(r for r in rows if r["fund_code"] == "21")
    assert act["ending_balance"] == -191113.0         # negative
    assert "Total" not in {r["fund_code"] for r in rows}  # total row not emitted


# --------------------------------------------------------------------------- #
# Cash & Investments Detail (side-by-side tables share a repeated label)
# --------------------------------------------------------------------------- #
CASH = """FY26 Q2 Cash and Investments Detail
As of 12/31/2025
General (10, 84) $ 8,609,013 $ 6,631,101 General (10, 84) $ 6,631,101 $ - $ 21,885,563 $ 28,516,664 71.5%
Activity (21) $ 980,794 $ 998,503 Activity (21) $ 998,503 $ - $ 998,503 2.5%
Total All Funds $ 23,901,573 $ 10,726,186 Total All Funds $10,726,186 $ - $ 29,172,202 $ 39,898,388 100.0%
"""


def test_parse_cash_detail():
    rows, page, as_of = qfr.parse_cash_detail([CASH])
    assert page == 1 and as_of == "2025-12-31"
    gen = next(r for r in rows if r["fund_code"] == "10")
    assert gen["cash_in_bank"] == 6631101.0
    assert gen["total_cash_investments"] == 28516664.0
    assert gen["investments"] == 28516664.0 - 6631101.0   # derived
    act = next(r for r in rows if r["fund_code"] == "21")
    assert act["investments"] == 0.0
    tot = next(r for r in rows if r["fund_code"] == "ALL")
    assert tot["total_cash_investments"] == 39898388.0


def test_can_handle():
    assert qfr.can_handle([COMBINED])
    assert not qfr.can_handle(["some unrelated text"])


# --------------------------------------------------------------------------- #
# Integration: real FY26 Q2 report (via committed text sidecar)
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not Q2_SIDECAR.exists(), reason="Q2 sidecar not present")
def test_real_q2_monthly_reconciles():
    pages = [Q2_SIDECAR.read_text(encoding="utf-8")]
    rows, page, fy = qfr.parse_monthly_gf(pages)
    assert fy == 2025  # prior-year table in the FY26 Q2 report is FY2025
    items = [r for r in rows if not r["is_total"]]
    rev = sum(r["amount"] for r in items if r["type"] == "revenue")
    exp = sum(r["amount"] for r in items if r["type"] == "expenditure")
    # Line items reconcile to the published FY2025 totals (within rounding).
    assert abs(rev - 208_583_924) < 10
    assert abs(exp - 208_850_928) < 10
    # Property tax drives the two big revenue months: October and April.
    by_month = {}
    for r in items:
        if r["type"] == "revenue":
            by_month[r["month"]] = by_month.get(r["month"], 0) + r["amount"]
    top2 = sorted(by_month, key=by_month.get, reverse=True)[:2]
    assert set(top2) == {"2024-10", "2025-04"}


@pytest.mark.skipif(not Q2_SIDECAR.exists(), reason="Q2 sidecar not present")
def test_real_q2_numbers():
    pages = [Q2_SIDECAR.read_text(encoding="utf-8")]
    result = qfr.extract(pages)
    assert result["period_end"] == "2025-12-31"
    rd = {r["fund_code"]: r for r in result["receipts_disbursements"]}
    assert len(rd) == 7
    assert rd["10"]["ending_balance"] == 25706774.0          # General Fund
    assert rd["61"]["ending_balance"] == 6596356.0            # Nutrition
    cash = {r["fund_code"]: r for r in result["cash_balances"]}
    assert cash["ALL"]["total_cash_investments"] == 39898388.0
    # The six fund groups reconcile to the all-funds total.
    parts = sum(r["total_cash_investments"] for r in result["cash_balances"]
                if r["fund_code"] != "ALL")
    assert abs(parts - 39898388.0) <= 2
