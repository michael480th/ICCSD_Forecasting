#!/usr/bin/env python3
"""ICCSD financial-KPI scorecard vs. board targets and large-Iowa-district peers.

Builds the indicators board policy 701.5R1 requires and scores them against the
board's adopted targets and the large Iowa peer set. Source data is the
ICCSDAdvocacy benchmarking under data/raw/manual_uploads/iccsd_advocacy_extractions/:

- district-extractions/Iowa_City_CSD.csv  — ICCSD audited figures FY2020-2023
  (solvency, operating margin, fund balance, unassigned, GO debt outstanding).
- dom/unspent-authorized-budget.csv       — UAB ratio + dollars, peers, FY2020-2025.
- dom/certified-enrollment.csv            — certified enrollment, FY2020-2025.
- dom/assessed-valuation-latest.csv       — actual property valuation (for debt limit).

Board policy 701.5R1 metrics with explicit targets:
  * Solvency ratio: 10-15% target, 5% minimum.
  * Unspent Authorized Budget ratio: 5-10% target.
  * UAB net of restricted (categorical): 0-5% target (categorical data not yet wired).
  * Total GF balance >= unspent authority (metric #4) — so the district can
    cash-flow its full legal spending limit.
Reported indicator: enrollment trend. Statutory cap: GO debt <= 5% of actual value.

Outputs:
  data/normalized/kpi_scorecard.csv  — tidy metric/year/scope/value/target/status
  docs/kpi_scorecard.md              — readable scorecard

Note: FY2024 and FY2025 ICCSD ACFRs are not yet issued, so audited solvency, fund
balance, and GO debt for those years are unavailable; UAB and enrollment (state
filings) run through FY2025.
"""
from __future__ import annotations

import csv
import statistics as st
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "data/raw/manual_uploads/iccsd_advocacy_extractions"
OUT_CSV = REPO / "data/normalized/kpi_scorecard.csv"
OUT_MD = REPO / "docs/kpi_scorecard.md"
ICCSD = "Iowa City CSD"
GO_DEBT_LIMIT_PCT = 5.0   # Iowa Constitution: GO debt <= 5% of actual valuation

# Board policy 701.5R1 target ranges (and the statutory debt cap).
TARGETS = {
    "solvency_ratio_pct": {"low": 10, "high": 15, "floor": 5},
    "uab_pct_of_max": {"low": 5, "high": 10, "floor": None},
    "go_debt_pct_actual_value": {"high": GO_DEBT_LIMIT_PCT},
    "gf_balance_ge_authority_x": {"floor": 1.0},
}


def _status(metric: str, v: float | None) -> str:
    if v is None:
        return ""
    t = TARGETS.get(metric)
    if not t:
        return ""
    if v >= t["low"]:
        return "on_target" if v <= t["high"] else "above_target"
    if t["floor"] is not None and v < t["floor"]:
        return "below_floor"
    return "below_target"


def load_iccsd_audit() -> dict[int, dict]:
    out = {}
    with open(SRC / "district-extractions/Iowa_City_CSD.csv", newline="") as fh:
        for r in csv.DictReader(fh, delimiter="|"):
            fy = int(r["fiscal_year"])
            out[fy] = {
                "solvency_ratio_pct": float(r["solvency_ratio_pct"]),
                "operating_margin_pct": float(r["operating_margin_pct"]),
                "gf_total_fund_balance": int(r["gf_total_fund_balance"]),
                "gf_unassigned": int(r["gf_unassigned"]),
                "go_debt_outstanding": int(r["go_debt_outstanding"]),
            }
    return out


def load_uab() -> dict[int, dict[str, float]]:
    out: dict[int, dict[str, float]] = {}
    with open(SRC / "dom/unspent-authorized-budget.csv", newline="") as fh:
        for r in csv.DictReader(fh):
            out.setdefault(int(r["fiscal_year"]), {})[r["district"]] = float(r["uab_pct_of_max"])
    return out


def load_iccsd_uab_dollars() -> dict[int, float]:
    """ICCSD unspent authorized budget in dollars, by fiscal year."""
    out = {}
    with open(SRC / "dom/unspent-authorized-budget.csv", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["district"] == ICCSD:
                out[int(r["fiscal_year"])] = float(r["unspent_authorized_budget"])
    return out


def load_enrollment() -> dict[int, float]:
    out = {}
    with open(SRC / "dom/certified-enrollment.csv", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["district"] == ICCSD:
                out[int(r["fiscal_year"])] = float(r["certified_enrollment"])
    return out


def load_actual_valuation() -> tuple[int, float]:
    """Latest (fiscal_year, actual property valuation incl. gas & electric)."""
    rows = []
    with open(SRC / "dom/assessed-valuation-latest.csv", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r["district"] == ICCSD]
    r = max(rows, key=lambda x: int(x["fiscal_year"]))
    return int(r["fiscal_year"]), float(r["assessed_actual_with_ge"])


def build_rows(audit, uab, uab_d, enroll, val_fy, val_actual) -> list[dict]:
    rows = []
    years = sorted(set(audit) | set(uab))
    for fy in years:
        if fy in audit:
            v = audit[fy]["solvency_ratio_pct"]
            rows.append(dict(metric="solvency_ratio_pct", fiscal_year=fy, scope="ICCSD",
                             value=v, status=_status("solvency_ratio_pct", v),
                             source="ICCSD ACFR (RSM US LLP) via ICCSDAdvocacy"))
            o = audit[fy]["operating_margin_pct"]
            rows.append(dict(metric="operating_margin_pct", fiscal_year=fy, scope="ICCSD",
                             value=o, status="", source="ICCSD ACFR via ICCSDAdvocacy"))
        if fy in uab:
            ic = uab[fy].get(ICCSD)
            rows.append(dict(metric="uab_pct_of_max", fiscal_year=fy, scope="ICCSD",
                             value=ic, status=_status("uab_pct_of_max", ic),
                             source="Iowa DOM Unspent Authorized Budget"))
            peers = [v for d, v in uab[fy].items() if d != ICCSD]
            for scope, val in (("peer_median", st.median(peers)),
                               ("peer_min", min(peers)), ("peer_max", max(peers))):
                rows.append(dict(metric="uab_pct_of_max", fiscal_year=fy, scope=scope,
                                 value=round(val, 2), status="",
                                 source="Iowa DOM UAB (14 large Iowa districts)"))

    # --- Metric #4: total GF balance vs. unspent authority --------------------
    for fy in sorted(audit):
        fb = audit[fy]["gf_total_fund_balance"]
        rows.append(dict(metric="gf_total_fund_balance", fiscal_year=fy, scope="ICCSD",
                         value=fb, status="", source="ICCSD ACFR via ICCSDAdvocacy"))
        if fy in uab_d:
            auth = uab_d[fy]
            meets = fb >= auth
            ratio = round(fb / auth, 2) if auth > 0 else ""
            status = "met" if meets else "below_target"
            if auth <= 0:
                status = "met (authority ≤ 0)"
            rows.append(dict(metric="gf_balance_ge_authority_x", fiscal_year=fy, scope="ICCSD",
                             value=ratio, status=status,
                             source="GF balance (ACFR) vs. unspent authority (Iowa DOM)"))
    for fy in sorted(uab_d):
        rows.append(dict(metric="unspent_authority_dollars", fiscal_year=fy, scope="ICCSD",
                         value=round(uab_d[fy]), status="",
                         source="Iowa DOM Unspent Authorized Budget"))

    # --- Reported indicator: enrollment trend ---------------------------------
    for fy in sorted(enroll):
        rows.append(dict(metric="certified_enrollment", fiscal_year=fy, scope="ICCSD",
                         value=enroll[fy], status="",
                         source="Iowa DOM certified enrollment"))

    # --- Statutory cap: GO debt vs. 5% of actual valuation --------------------
    debt_fy = max(audit)
    go_debt = audit[debt_fy]["go_debt_outstanding"]
    pct = round(go_debt / val_actual * 100, 2)
    rows.append(dict(metric="go_debt_outstanding", fiscal_year=debt_fy, scope="ICCSD",
                     value=go_debt, status="",
                     source="ICCSD ACFR via ICCSDAdvocacy"))
    rows.append(dict(metric="go_debt_pct_actual_value", fiscal_year=debt_fy, scope="ICCSD",
                     value=pct, status=("within_limit" if pct <= GO_DEBT_LIMIT_PCT else "over_limit"),
                     source=f"GO debt FY{debt_fy} (ACFR) vs. FY{val_fy} actual valuation (Iowa DOM)"))
    return rows


def write_csv(rows):
    fields = ["metric", "fiscal_year", "scope", "value", "target_low",
              "target_high", "target_floor", "status", "source"]
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            t = TARGETS.get(r["metric"], {})
            w.writerow({**r, "target_low": t.get("low", ""),
                        "target_high": t.get("high", ""), "target_floor": t.get("floor", "")})


def write_md(audit, uab, uab_d, enroll, val_fy, val_actual):
    lines = []
    A = lines.append
    A("# ICCSD financial-KPI scorecard\n")
    A("Key indicators required by board policy **701.5R1 – Financial Metrics** (adopted 12/12/2023), "
      "scored against the board's own target ranges and the large-Iowa-district peer set. "
      "Source: ICCSDAdvocacy benchmarking (audited ACFRs + Iowa DOM filings).\n")
    A("> FY2024–FY2025 ICCSD ACFRs are not yet issued, so audited **solvency**, **fund balance**, and "
      "**GO debt** for those years are unavailable. **UAB** and **enrollment** (state filings) run through FY2025.\n")
    A("> **Want to check the math?** The [source-trace report](kpi_trace.html) recomputes every "
      "number below from its raw audited components and links each one to the primary source document "
      "(ICCSD ACFR / Iowa DOM filing).\n")

    A("\n## ICCSD trend vs. board targets\n")
    A("Policy 701.5R1 sets explicit targets for **solvency** and **UAB** (below); two further targeted "
      "commitments — total GF balance vs. unspent authority, and the categorical-net UAB — plus the "
      "reported enrollment indicator and the statutory debt limit follow in the next sections.\n")
    A("| Fiscal year | Solvency ratio % | UAB ratio % | Operating margin % |")
    A("|---|---|---|---|")
    A("| **Board target (701.5R1)** | **10–15% (≥5% floor)** | **5–10%** | — |")
    for fy in sorted(set(audit) | set(uab)):
        s = audit.get(fy, {}).get("solvency_ratio_pct")
        u = uab.get(fy, {}).get(ICCSD)
        o = audit.get(fy, {}).get("operating_margin_pct")
        def f(x): return "—" if x is None else f"{x:.2f}"
        A(f"| FY{fy} | {f(s)} | {f(u)} | {f(o)} |")

    A("\n## FY2025 UAB ratio — ICCSD vs. large Iowa peers\n")
    ranked = sorted(uab[2025].items(), key=lambda kv: kv[1], reverse=True)
    peers = [v for d, v in uab[2025].items() if d != ICCSD]
    A("| Rank | District | UAB % |")
    A("|---|---|---|")
    for i, (d, v) in enumerate(ranked, 1):
        bold = "**" if d == ICCSD else ""
        A(f"| {i} | {bold}{d}{bold} | {bold}{v:.2f}%{bold} |")
    A(f"\n**Peer median {st.median(peers):.2f}%** vs. **ICCSD {uab[2025][ICCSD]:.2f}%** "
      f"(target 5–10%). ICCSD ranks last of {len(uab[2025])} and was negative "
      f"({uab[2023][ICCSD]:.2f}%) in FY2023.\n")

    # --- Metric #4 -----------------------------------------------------------
    A("\n## Total GF balance vs. unspent authority — policy metric #4\n")
    A("Policy 701.5R1 commits the District to *\"a total general fund balance at least equal to its "
      "unspent authority\"* so it can cash-flow its full legal spending limit.\n")
    A("| Fiscal year | Total GF balance | Unspent authority | Balance ≥ authority? |")
    A("|---|---|---|---|")
    for fy in sorted(audit):
        fb = audit[fy]["gf_total_fund_balance"]
        if fy in uab_d:
            auth = uab_d[fy]
            mark = "✅ yes" if fb >= auth else "🔴 no"
            if auth <= 0:
                mark = "✅ (authority ≤ 0)"
            A(f"| FY{fy} | ${fb/1e6:.1f}M | ${auth/1e6:.1f}M | {mark} |")
    A("\n> **Read with care.** ICCSD has technically *met* #4 — but mostly because its **unspent "
      "authority is near zero or negative** (the very problem the UAB metric flags). It is easy to hold "
      "more fund balance than authority when you have almost no authority left. As the forecast shows the "
      "GF balance falling toward ~$1M (FY2026), this cushion is effectively gone.\n")

    # --- Enrollment ----------------------------------------------------------
    A("## Enrollment trend — reported indicator (no target)\n")
    A("Policy 701.5R1 requires reporting the enrollment trend because *funding follows the student*.\n")
    A("| Fiscal year | Certified enrollment | Year-over-year |")
    A("|---|---|---|")
    prev = None
    for fy in sorted(enroll):
        e = enroll[fy]
        yoy = "—" if prev is None else f"{(e/prev-1)*100:+.1f}%"
        A(f"| FY{fy} | {e:,.1f} | {yoy} |")
        prev = e
    A(f"\nEnrollment has been **roughly flat** — about {enroll[max(enroll)]:,.0f} in FY{max(enroll)} vs. "
      f"a {max(enroll.values()):,.0f} peak — sturdier than the statewide decline, but with no growth to "
      "lift per-pupil revenue.\n")

    # --- Debt limit ----------------------------------------------------------
    debt_fy = max(audit)
    go_debt = audit[debt_fy]["go_debt_outstanding"]
    limit = GO_DEBT_LIMIT_PCT / 100 * val_actual
    A("## General-obligation debt vs. the 5% statutory limit\n")
    A("Iowa caps a district's outstanding GO debt at **5% of the actual value** of taxable property.\n")
    A(f"- **GO debt outstanding:** ${go_debt/1e6:.1f}M (FY{debt_fy} ACFR)")
    A(f"- **Actual valuation:** ${val_actual/1e9:.2f}B (FY{val_fy}, Iowa DOM) → **5% limit ≈ ${limit/1e6:.0f}M**")
    A(f"- **Utilization:** GO debt is **{go_debt/val_actual*100:.2f}% of actual value** "
      f"(~{go_debt/limit*100:.0f}% of the limit) — **comfortably within** the cap, and falling "
      f"(${audit[min(audit)]['go_debt_outstanding']/1e6:.0f}M in FY{min(audit)}). Debt capacity is not "
      "the District's constraint.\n")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    audit = load_iccsd_audit()
    uab = load_uab()
    uab_d = load_iccsd_uab_dollars()
    enroll = load_enrollment()
    val_fy, val_actual = load_actual_valuation()
    rows = build_rows(audit, uab, uab_d, enroll, val_fy, val_actual)
    write_csv(rows)
    write_md(audit, uab, uab_d, enroll, val_fy, val_actual)
    print(f"KPI scorecard: {len(rows)} rows -> {OUT_CSV.relative_to(REPO)}")
    print(f"  -> {OUT_MD.relative_to(REPO)}")


if __name__ == "__main__":
    main()
