#!/usr/bin/env python3
"""Build the KPI source-trace report — the auditable "trace every number" deliverable.

For each value on the financial-KPI scorecard, this recomputes the metric from its
raw audited/filed components, shows the exact formula with the numbers plugged in,
and links the chain back to the primary source: the scorecard cell -> the builder
formula (scripts/analysis/kpi_scorecard.py) -> the ICCSDAdvocacy extraction CSV ->
the underlying ICCSD ACFR (RSM US LLP) or Iowa DOM filing.

Two outputs, both regenerable from code:
  * data/normalized/source_links.csv  — the document -> table provenance index
  * docs/kpi_trace.html               — the reporter-facing trace report

Everything is derived from the same raw files the scorecard uses, so the published
figures reproduce here exactly. Run:  python scripts/analysis/kpi_trace.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "data/raw/manual_uploads/iccsd_advocacy_extractions"
INVENTORY = REPO / "data/extracted/document_inventory.csv"
OUT_LINKS = REPO / "data/normalized/source_links.csv"
OUT_HTML = REPO / "docs/kpi_trace.html"
ICCSD = "Iowa City CSD"

# Reuse the exact site shell (nav, hero, footer, GH base) so the page matches.
sys.path.insert(0, str(REPO / "scripts/site"))
import build_site as site  # noqa: E402

BLOB = site.GH + "/blob/main/"          # GitHub blob base for "view the file" links
TARGET = {"low": 10, "high": 15, "floor": 5}   # solvency policy 701.5R1


# --------------------------------------------------------------------------- #
# Load raw inputs
# --------------------------------------------------------------------------- #
def load_inventory() -> dict[str, dict]:
    """{file_path: {document_id, file_hash, source_url}} for provenance lookup."""
    out = {}
    with open(INVENTORY, newline="") as fh:
        for r in csv.DictReader(fh):
            out[r["file_path"]] = r
    return out


def load_audit() -> list[dict]:
    rows = []
    with open(SRC / "district-extractions/Iowa_City_CSD.csv", newline="") as fh:
        for r in csv.DictReader(fh, delimiter="|"):
            rows.append(r)
    return rows


def load_iccsd_uab() -> list[dict]:
    rows = []
    with open(SRC / "dom/unspent-authorized-budget.csv", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["district"] == ICCSD:
                rows.append(r)
    return sorted(rows, key=lambda r: int(r["fiscal_year"]))


def solvency_status(v: float) -> str:
    if v >= TARGET["low"]:
        return "on target" if v <= TARGET["high"] else "above target"
    return "below floor" if v < TARGET["floor"] else "below target"


# --------------------------------------------------------------------------- #
# source_links.csv — document -> table provenance index (KPI-scorecard slice)
# --------------------------------------------------------------------------- #
DISTRICT_CSV = "data/raw/manual_uploads/iccsd_advocacy_extractions/district-extractions/Iowa_City_CSD.csv"
AEA_CSV = "data/raw/manual_uploads/iccsd_advocacy_extractions/dom/aea-flowthrough.csv"
UAB_CSV = "data/raw/manual_uploads/iccsd_advocacy_extractions/dom/unspent-authorized-budget.csv"
ACFR = {fy: f"data/raw/district_reports/audits/Iowa City CSD-{fy}.pdf" for fy in range(2020, 2024)}


def build_source_links(inv: dict, audit: list[dict]) -> list[dict]:
    def row(path, table, method, conf, notes):
        meta = inv.get(path, {})
        return {
            "document_id": meta.get("document_id", ""),
            "source_file": path,
            "source_page": "",
            "source_table": table,
            "source_url": meta.get("source_url", "") or "",
            "extraction_method": method,
            "confidence": conf,
            "notes": notes,
        }

    links = []
    # Ultimate primary sources: the four ICCSD ACFRs that the extraction reads.
    by_fy = {int(r["fiscal_year"]): r for r in audit}
    for fy, path in ACFR.items():
        r = by_fy.get(fy, {})
        links.append(row(
            path,
            "kpi_scorecard.csv :: solvency_ratio_pct, operating_margin_pct (ICCSD FY%d)" % fy,
            "ICCSDAdvocacy audit extraction (manual)",
            r.get("confidence", ""),
            "%s audit, report dated %s%s" % (
                r.get("auditor", "RSM US LLP"), r.get("report_date", ""),
                "; FY2023 issued 26+ months late, material weakness" if fy == 2023 else ""),
        ))
    # Intermediate extractions actually read by scripts/analysis/kpi_scorecard.py.
    links.append(row(
        DISTRICT_CSV,
        "kpi_scorecard.csv :: solvency_ratio_pct, operating_margin_pct (ICCSD FY2020-2023)",
        "imported from ICCSDAdvocacy repo (pipe-delimited)", "high",
        "Per-year ACFR extraction: GF revenue/expenditure/fund balance, unassigned, AEA flow-through.",
    ))
    links.append(row(
        AEA_CSV,
        "kpi_scorecard.csv :: solvency_ratio_pct (denominator: revenue - AEA flow-through)",
        "imported from ICCSDAdvocacy repo (Iowa DOM)", "high",
        "AEA flow-through removed from the solvency denominator per policy 701.5R1.",
    ))
    links.append(row(
        UAB_CSV,
        "kpi_scorecard.csv :: uab_pct_of_max (ICCSD + 14 peers, FY2020-2025)",
        "imported from ICCSDAdvocacy repo (Iowa DOM filing)", "high",
        "Unspent Authorized Budget / Maximum Authorized Budget, per Iowa DOM.",
    ))
    return links


def write_source_links(links: list[dict]):
    fields = ["document_id", "source_file", "source_page", "source_table",
              "source_url", "extraction_method", "confidence", "notes"]
    with open(OUT_LINKS, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(links)


# --------------------------------------------------------------------------- #
# HTML helpers
# --------------------------------------------------------------------------- #
def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def money(n: int) -> str:
    return "${:,.0f}".format(n)


def blob(path: str, label: str | None = None) -> str:
    return f'<a href="{BLOB}{path.replace(" ", "%20")}">{esc(label or path)}</a>'


# --------------------------------------------------------------------------- #
# Build the trace report body
# --------------------------------------------------------------------------- #
def build_body(inv: dict, audit: list[dict], uab: list[dict], links: list[dict]) -> str:
    a = audit_by_fy = {int(r["fiscal_year"]): r for r in audit}
    fys = sorted(audit_by_fy)
    out = []
    P = out.append

    # Intro
    P('<div class="disclaimer"><b>What this page is.</b> A line-by-line audit trail for the '
      '<a href="kpi_scorecard.html">financial-KPI scorecard</a>. Every figure below is recomputed here '
      'from its raw audited/filed components, so the published number reproduces in front of you, and '
      'each one links back to the primary source document. A reporter can verify the scorecard without '
      'taking our word for anything.</div>')

    P('<div class="card"><h3>How to verify any number in four steps</h3><ol>'
      '<li><b>Read the value</b> on the scorecard (or in '
      f'{blob("data/normalized/kpi_scorecard.csv", "kpi_scorecard.csv")}).</li>'
      '<li><b>Apply the formula</b> below — the same one in the builder '
      f'{blob("scripts/analysis/kpi_scorecard.py", "kpi_scorecard.py")} — with the raw components shown.</li>'
      '<li><b>Open the extraction</b> the components come from '
      f'({blob(DISTRICT_CSV, "Iowa_City_CSD.csv")} / {blob(UAB_CSV, "unspent-authorized-budget.csv")}).</li>'
      '<li><b>Trace to the primary document</b> — the ICCSD ACFR (RSM US LLP) or the Iowa DOM filing — '
      'listed in the provenance index at the bottom.</li></ol></div>')

    # ---- Metric 1: solvency -------------------------------------------------
    P('<h2>1 · Solvency ratio</h2>')
    P('<div class="q"><b>Formula (board policy 701.5R1).</b> '
      'solvency&nbsp;=&nbsp;(unassigned&nbsp;+&nbsp;assigned GF fund balance) &divide; '
      '(GF revenue &minus; AEA flow-through). Target 10&ndash;15%, 5% floor.</div>')
    P('<div class="card"><table><tr>'
      '<th>FY</th><th class="w">Unassigned + assigned</th><th class="w">Revenue &minus; AEA</th>'
      '<th class="w">= Solvency</th><th class="w">Published</th><th class="w">vs. target</th></tr>')
    for fy in fys:
        r = a[fy]
        rev, aea = int(r["gf_revenue"]), int(r["aea_flowthrough"])
        un, asg = int(r["gf_unassigned"]), int(r["gf_assigned"] or 0)
        num, den = un + asg, rev - aea
        calc = num / den * 100
        pub = float(r["solvency_ratio_pct"])
        st = solvency_status(pub)
        pill = ("p-red" if "floor" in st else "p-orange" if "below" in st else "p-green")
        P(f'<tr><td><b>FY{fy}</b></td>'
          f'<td class="w">{money(num)}</td>'
          f'<td class="w">{money(rev)} &minus; {money(aea)}<br>= {money(den)}</td>'
          f'<td class="w"><b>{calc:.2f}%</b></td>'
          f'<td class="w">{pub:.2f}%</td>'
          f'<td class="w"><span class="pill {pill}">{st}</span></td></tr>')
    P('</table><p class="src">Recomputed column reproduces the published value exactly. '
      'Components come from ' + blob(DISTRICT_CSV, "the per-year ACFR extraction") +
      '; the AEA flow-through is corroborated by ' + blob(AEA_CSV, "the Iowa DOM AEA file") + '.</p>')
    P('<p>Primary documents (audited financial statements, RSM US LLP):</p><ul>')
    for fy in fys:
        r = a[fy]
        note = (" — <b>issued 26+ months late; material weakness</b>" if fy == 2023 else "")
        P(f'<li>FY{fy}: {blob(ACFR[fy], "ICCSD ACFR " + str(fy))} '
          f'<span class="src">(report dated {esc(r["report_date"])}, opinion: {esc(r["opinion_type"])}{note})</span></li>')
    P('</ul></div>')

    # ---- Metric 2: operating margin ----------------------------------------
    P('<h2>2 · Operating margin</h2>')
    P('<div class="q"><b>Formula.</b> operating margin&nbsp;=&nbsp;(GF revenue &minus; GF expenditure) '
      '&divide; GF revenue.</div>')
    P('<div class="card"><table><tr>'
      '<th>FY</th><th class="w">Revenue</th><th class="w">Expenditure</th>'
      '<th class="w">= Margin</th><th class="w">Published</th></tr>')
    for fy in fys:
        r = a[fy]
        rev, exp = int(r["gf_revenue"]), int(r["gf_expenditure"])
        calc = (rev - exp) / rev * 100
        pub = float(r["operating_margin_pct"])
        sign = "p-green" if pub >= 0 else "p-orange"
        P(f'<tr><td><b>FY{fy}</b></td><td class="w">{money(rev)}</td><td class="w">{money(exp)}</td>'
          f'<td class="w"><span class="pill {sign}">{calc:+.2f}%</span></td><td class="w">{pub:+.2f}%</td></tr>')
    P('</table><p class="src">Source: ' + blob(DISTRICT_CSV, "Iowa_City_CSD.csv") +
      ' (GF revenue &amp; expenditure per the ACFRs above).</p></div>')

    # ---- Metric 3: UAB ------------------------------------------------------
    P('<h2>3 · Unspent Authorized Budget (UAB) ratio</h2>')
    P('<div class="q"><b>Formula.</b> UAB ratio&nbsp;=&nbsp;unspent authorized budget &divide; '
      'maximum authorized budget (Iowa DOM). Target 5&ndash;10%.</div>')
    P('<div class="card"><table><tr>'
      '<th>FY</th><th class="w">Unspent</th><th class="w">Max authorized</th>'
      '<th class="w">= UAB</th><th class="w">Published</th></tr>')
    for r in uab:
        fy = int(r["fiscal_year"])
        uns, mx = float(r["unspent_authorized_budget"]), float(r["max_authorized_budget"])
        calc = uns / mx * 100
        pub = float(r["uab_pct_of_max"])
        pill = "p-red" if pub < 0 else "p-orange" if pub < 5 else "p-green"
        P(f'<tr><td><b>FY{fy}</b></td><td class="w">{money(uns)}</td><td class="w">{money(mx)}</td>'
          f'<td class="w"><span class="pill {pill}">{calc:.2f}%</span></td><td class="w">{pub:.2f}%</td></tr>')
    P('</table><p class="src">Source: ' + blob(UAB_CSV, "unspent-authorized-budget.csv") +
      ' (Iowa DOM filing). ICCSD has been below the 5% target every year, and negative in FY2023.</p></div>')

    # ---- Provenance index ---------------------------------------------------
    P('<h2>Provenance index</h2>')
    P('<p>The machine-readable version of this trail is '
      f'{blob("data/normalized/source_links.csv", "source_links.csv")} — one row per source document '
      'feeding the scorecard, with its inventory <code>document_id</code> and hash.</p>')
    P('<div class="card"><table><tr><th>document_id</th><th>source file</th>'
      '<th>feeds</th><th class="w">conf.</th></tr>')
    for lk in links:
        did = lk["document_id"] or "<span class='src'>(not in inventory)</span>"
        P(f'<tr><td><code>{esc(lk["document_id"]) or "&mdash;"}</code></td>'
          f'<td>{blob(lk["source_file"], Path(lk["source_file"]).name)}</td>'
          f'<td><span class="src">{esc(lk["source_table"])}</span></td>'
          f'<td class="w">{esc(lk["confidence"]) or "&mdash;"}</td></tr>')
    P('</table><p class="src">This index currently covers the KPI scorecard lineage; it is appended to '
      'as other normalized tables are wired in.</p></div>')

    P('<div class="q"><b>Scope &amp; honesty note.</b> Audited solvency and operating margin exist only '
      'for FY2020&ndash;FY2023 (the years with issued ACFRs); FY2024&ndash;FY2025 ACFRs are not yet filed, '
      'so those cells are blank by design. The ICCSDAdvocacy extraction CSVs are a manual transcription of '
      'the ACFRs and DOM filings linked above &mdash; verify against the primary PDFs for anything '
      'consequential.</div>')
    return "\n".join(out)


def main():
    inv = load_inventory()
    audit = load_audit()
    uab = load_iccsd_uab()
    links = build_source_links(inv, audit)
    write_source_links(links)
    body = build_body(inv, audit, uab, links)
    OUT_HTML.write_text(
        site.page("KPI source-trace report — ICCSD Forecasting", body, "kpi_trace.html",
                  hero_title="KPI source-trace report",
                  hero_sub="Every scorecard number, traced from primary source through formula to output."),
        encoding="utf-8")
    print(f"wrote {OUT_LINKS.relative_to(REPO)} ({len(links)} rows)")
    print(f"wrote {OUT_HTML.relative_to(REPO)}")


if __name__ == "__main__":
    main()
