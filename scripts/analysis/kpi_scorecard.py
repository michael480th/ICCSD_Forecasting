#!/usr/bin/env python3
"""ICCSD financial-KPI scorecard vs. board targets and large-Iowa-district peers.

Builds the district's key financial indicators — the metrics board policy 701.5R1
requires — and scores them against (a) the board's own adopted target ranges and
(b) the large Iowa district peer set. Source data is the ICCSDAdvocacy benchmarking
already imported under data/raw/manual_uploads/iccsd_advocacy_extractions/:

- district-extractions/Iowa_City_CSD.csv  — ICCSD audited KPIs FY2020-2023
  (solvency ratio, operating margin, fund balance, unassigned, revenue, AEA).
- dom/unspent-authorized-budget.csv       — UAB ratio, all peers, FY2020-2025.

Policy 701.5R1 targets:
  * Solvency ratio (unassigned+assigned GF FB / (revenue - AEA flow-through)):
    10-15% target, 5% minimum.
  * Unspent Authorized Budget ratio: 5-10% target.
  * UAB net of restricted (categorical): 0-5% target.

Outputs:
  data/normalized/kpi_scorecard.csv  — tidy metric/year/scope/value/target/status
  docs/kpi_scorecard.md              — readable scorecard

Note: FY2024 and FY2025 ICCSD ACFRs are not yet issued, so audited solvency for
those years is unavailable; UAB (a state filing) is available through FY2025.
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

# Board policy 701.5R1 target ranges.
TARGETS = {
    "solvency_ratio_pct": {"low": 10, "high": 15, "floor": 5},
    "uab_pct_of_max": {"low": 5, "high": 10, "floor": None},
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
            }
    return out


def load_uab() -> dict[int, dict[str, float]]:
    out: dict[int, dict[str, float]] = {}
    with open(SRC / "dom/unspent-authorized-budget.csv", newline="") as fh:
        for r in csv.DictReader(fh):
            out.setdefault(int(r["fiscal_year"]), {})[r["district"]] = float(r["uab_pct_of_max"])
    return out


def build_rows(audit, uab) -> list[dict]:
    rows = []
    years = sorted(set(audit) | set(uab))
    for fy in years:
        # ICCSD solvency (audited only)
        if fy in audit:
            v = audit[fy]["solvency_ratio_pct"]
            rows.append(dict(metric="solvency_ratio_pct", fiscal_year=fy, scope="ICCSD",
                             value=v, status=_status("solvency_ratio_pct", v),
                             source="ICCSD ACFR (RSM US LLP) via ICCSDAdvocacy"))
            o = audit[fy]["operating_margin_pct"]
            rows.append(dict(metric="operating_margin_pct", fiscal_year=fy, scope="ICCSD",
                             value=o, status="", source="ICCSD ACFR via ICCSDAdvocacy"))
        # ICCSD UAB + peer distribution
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


def write_md(audit, uab):
    lines = []
    A = lines.append
    A("# ICCSD financial-KPI scorecard\n")
    A("Key indicators required by board policy **701.5R1 – Financial Metrics**, scored "
      "against the board's own target ranges and the large-Iowa-district peer set. "
      "Source: ICCSDAdvocacy benchmarking (audited ACFRs + Iowa DOM filings).\n")
    A("> FY2024–FY2025 ICCSD ACFRs are not yet issued, so audited **solvency** for those "
      "years is unavailable. **UAB** (a state filing) runs through FY2025.\n")

    A("\n## ICCSD trend vs. board targets\n")
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
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    audit, uab = load_iccsd_audit(), load_uab()
    rows = build_rows(audit, uab)
    write_csv(rows)
    write_md(audit, uab)
    print(f"KPI scorecard: {len(rows)} rows -> {OUT_CSV.relative_to(REPO)}")
    print(f"  -> {OUT_MD.relative_to(REPO)}")


if __name__ == "__main__":
    main()
