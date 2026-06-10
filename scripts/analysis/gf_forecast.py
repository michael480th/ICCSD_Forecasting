#!/usr/bin/env python3
"""Forward-looking General Fund forecast for ICCSD: FY2026-FY2029.

Projects the General Fund operating result, assigned+unassigned fund balance, and
the two board-policy KPIs (solvency ratio, Unspent Authorized Budget ratio) under
conservative / base / optimistic scenarios.

The **base case is PFM's own 7-year GF cash-flow model** (PFM Comprehensive Fiscal
Analysis, 4/1/2026 Work Session) — the district financial advisor's authoritative
projection — rather than the printed budget. This matters: PFM projects FY2026 GF
expenditures of ~$225.1M (vs. the $212.1M budget), i.e. a ~$6.0M operating
*deficit* where the budget showed a surplus. Conservative/optimistic flex revenue
and expenditure around PFM's path.

KPI definitions follow board policy 701.5R1:
  solvency_ratio = (assigned + unassigned GF fund balance) / (GF revenue - AEA)
  uab_ratio      = (max authorized budget - GF expenditures) / max authorized budget

Fund-balance roll-forward: assigned+unassigned is anchored at the FY2024 Certified
Annual Report figure ($14,881,750) and rolled by each year's fund-balance change
(revenues - expenditures + transfers + other), which EXCLUDES warrant proceeds/
repayments and interfund-loan principal (those are balance-sheet financing, not
fund balance). FY2025 uses PFM's reported fiscal-year change (-$6.55M, incl. a
-$6.07M accrual adjustment).

CAVEATS: FY2024-2029 are unaudited (no ACFR issued for FY2024+). The anchor-vs-
audited roll has ~$3M of slack (the FY2024 CAR assigned+unassigned is ~$3M above a
straight roll of the FY2023 audited figure), so treat solvency within ~±1.5 pts.
The FY2026 max authorized budget is estimated (not yet final), so the UAB band is
wide — but every plausible authority is below PFM's $225M spend, so the sign holds.
"""
from __future__ import annotations
import csv
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_CSV = REPO / "data/normalized/gf_forecast.csv"
OUT_MD = REPO / "docs/forecast.md"

TARGET_SOLV = (10.0, 15.0, 5.0)   # low, high, floor
TARGET_UAB = (5.0, 10.0, None)

# ---- Audited / actual history ------------------------------------------- #
SOLV_AUDITED = {2020: 4.21, 2021: 6.35, 2022: 2.82, 2023: 2.45}  # ICCSD ACFRs
AU_FY24 = 14_881_750            # assigned+unassigned, FY2024 Certified Annual Report
FY25_FB_CHANGE = -6_549_172    # PFM FY2025 fiscal-year surplus/(deficit) (no financing)
REV25, EXP25 = 211_774_151, 211_982_184          # PFM FY2025
REV24, EXP24 = 206_530_216, 198_158_230          # PFM FY2024
AEA = {2024: 7_937_307, 2025: 8_064_107, 2026: 8_225_000,
       2027: 8_400_000, 2028: 8_568_000, 2029: 8_740_000}

# ---- PFM base-case GF cash-flow (FY2026-FY2029) -------------------------- #
# rev, exp, transfers in/(out), other rev/(exp) — financing (warrants, interfund
# loans) is intentionally excluded from the fund-balance roll.
PFM = {
    2026: dict(rev=219_082_029, exp=225_081_295, transfers=-1_259_191, other=-10_000),
    2027: dict(rev=224_333_277, exp=222_843_509, transfers=0, other=0),
    2028: dict(rev=230_078_712, exp=227_300_379, transfers=0, other=0),
    2029: dict(rev=234_457_719, exp=231_846_387, transfers=0, other=0),
}
FYS = [2026, 2027, 2028, 2029]

# Estimated FY2026 maximum authorized budget (spending authority). FY2025 actual
# was $217.88M; grown modestly given declining enrollment + budget guarantee.
MAX_AUTH_26 = 222_000_000

# ---- Scenario levers (multipliers on PFM revenue / expenditure) ---------- #
SCEN = {
    "conservative": dict(rev=0.985, exp=1.010),   # soft revenue, sticky costs
    "base":         dict(rev=1.000, exp=1.000),   # PFM as-is
    "optimistic":   dict(rev=1.005, exp=0.970),   # cost reductions land toward budget
}


def status(v, tgt):
    lo, hi, fl = tgt
    if v >= lo:
        return "on_target" if v <= hi else "above_target"
    if fl is not None and v < fl:
        return "below_floor"
    return "below_target"


def project():
    rows = []
    au25 = AU_FY24 + FY25_FB_CHANGE        # FY2025 assigned+unassigned (history)
    for name, s in SCEN.items():
        au = au25
        for fy in FYS:
            p = PFM[fy]
            rev, exp = p["rev"] * s["rev"], p["exp"] * s["exp"]
            au += (rev - exp) + p["transfers"] + p["other"]
            sv = round(au / (rev - AEA[fy]) * 100, 2)
            ub = MAX_AUTH_26 - exp if fy == 2026 else None
            rows.append(dict(
                fiscal_year=fy, scenario=name,
                gf_revenue=round(rev), gf_expenditure=round(exp),
                operating_result=round(rev - exp), assigned_unassigned=round(au),
                solvency_pct=sv, solvency_status=status(sv, TARGET_SOLV),
                uab_pct=(round(ub / MAX_AUTH_26 * 100, 2) if ub is not None else ""),
                uab_status=(status(ub / MAX_AUTH_26 * 100, TARGET_UAB) if ub is not None else "")))
    return rows, au25


def write_csv(rows):
    fields = ["fiscal_year", "scenario", "gf_revenue", "gf_expenditure",
              "operating_result", "assigned_unassigned", "solvency_pct",
              "solvency_status", "uab_pct", "uab_status"]
    with open(OUT_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader(); w.writerows(rows)


def band(rows, fy, key):
    vals = [r[key] for r in rows if r["fiscal_year"] == fy and r[key] != ""]
    base = next(r[key] for r in rows if r["fiscal_year"] == fy and r["scenario"] == "base")
    return min(vals), base, max(vals)


def write_md(rows, au25):
    L, A = [], None
    out = []
    def A(s): out.append(s)
    A("# ICCSD General Fund forward forecast (FY2026–FY2029)\n")
    A("Forecast of the General Fund and its two board-policy (701.5R1) KPIs. The "
      "**base case is PFM's own 7-year GF cash-flow model** (the district advisor's "
      "authoritative projection); conservative/optimistic flex revenue and "
      "expenditure around it. Uncertain quantities are shown as a band.\n")
    A("> **This supersedes the earlier budget-based forecast.** The printed FY2026 "
      "budget showed a ~+$6M surplus; PFM projects ~$225.1M of FY2026 spending (vs. "
      "the $212.1M budget) — a **~$6M operating deficit**. That single change pulls "
      "the whole solvency path down.\n")
    A("> **Caveats.** FY2024+ are unaudited. The assigned+unassigned roll is anchored "
      "on the FY2024 Certified Annual Report ($14.88M) with ~±$3M slack; read solvency "
      "within ~±1.5 pts. FY2026 max authorized budget (for UAB) is estimated.\n")

    A("## Solvency ratio — trajectory vs. board target (10–15%, 5% floor)\n")
    A("| Fiscal year | Conservative | Base | Optimistic |")
    A("|---|---|---|---|")
    for fy in (2020, 2021, 2022, 2023):
        A(f"| FY{fy} (audited) | — | {SOLV_AUDITED[fy]:.2f}% | — |")
    s24 = AU_FY24 / (REV24 - AEA[2024]) * 100
    s25 = au25 / (REV25 - AEA[2025]) * 100
    A(f"| FY2024 (CAR) | — | {s24:.2f}% | — |")
    A(f"| FY2025 (est.) | — | {s25:.2f}% | — |")
    for fy in FYS:
        lo, b, hi = band(rows, fy, "solvency_pct")
        A(f"| **FY{fy} (PFM proj.)** | {lo:.2f}% | **{b:.2f}%** | {hi:.2f}% |")

    A("\n## Unspent Authorized Budget ratio — vs. board target (5–10%)\n")
    A("| Fiscal year | Conservative | Base | Optimistic |")
    A("|---|---|---|---|")
    A("| FY2025 (actual) | — | 2.31% | — |")
    lo, b, hi = band(rows, 2026, "uab_pct")
    A(f"| **FY2026 (est.)** | {lo:.2f}% | **{b:.2f}%** | {hi:.2f}% |")
    A(f"\nWith PFM's ~$225M spend against ~$222M of estimated authority, the FY2026 "
      f"UAB is **roughly zero to negative** — i.e. ICCSD is spending at or beyond its "
      f"legal authority, as it did in FY2023 (−1.21%). Far below the 5–10% target and "
      f"still last among large Iowa peers.\n")

    A("## How the year ends — the bottom line\n")
    lo, sb, hi = band(rows, 2026, "solvency_pct")
    ob = next(r["operating_result"] for r in rows if r["fiscal_year"] == 2026 and r["scenario"] == "base")
    aub = next(r["assigned_unassigned"] for r in rows if r["fiscal_year"] == 2026 and r["scenario"] == "base")
    A(f"- **FY2026 operating result (base/PFM):** **−${abs(ob)/1e6:.1f}M** — a deficit, "
      f"not the surplus the printed budget implied.")
    A(f"- **FY2026 assigned+unassigned fund balance:** ~${aub/1e6:.1f}M (base) — a thin "
      f"sliver, down from ~$14.9M at FY2024.")
    A(f"- **FY2026 solvency ratio:** base **{sb:.2f}%** (band {lo:.2f}–{hi:.2f}%) — "
      f"**far below the 5% floor**, let alone the 10–15% target.")
    A(f"- **FY2026 UAB:** roughly **zero to negative** — at/over the legal spending limit.\n")
    A("**Read:** the FY2024 fund-balance rebuild (to ~$14.9M, solvency ~7.5%) was "
      "temporary — driven by an unusually low FY2024 spend ($198M). As spending "
      "snapped back ($212M FY2025, $225M FY2026), the cushion eroded. On PFM's "
      "numbers the General Fund ends FY2026 essentially at zero unassigned balance "
      "and stays **below its 5% solvency floor every year through FY2029**, only "
      "crawling back toward ~3.5%. The district does not return to its target band "
      "within the forecast horizon. This is a structural operating-margin problem "
      "layered on top of the cash-timing crunch — the warrants and interfund loans "
      "manage *liquidity*, but they do not fix the *solvency* gap.\n")
    OUT_MD.write_text("\n".join(out) + "\n", encoding="utf-8")


rows, au25 = project()
write_csv(rows)
write_md(rows, au25)
print(f"GF forecast (PFM-reconciled): {len(rows)} rows -> {OUT_CSV.relative_to(REPO)}")
for fy in FYS:
    lo, b, hi = band(rows, fy, "solvency_pct")
    print(f"  FY{fy} solvency: base {b:.2f}%  band {lo:.2f}-{hi:.2f}%")
lo, b, hi = band(rows, 2026, "uab_pct")
print(f"  FY2026 UAB: base {b:.2f}%  band {lo:.2f}-{hi:.2f}%")
