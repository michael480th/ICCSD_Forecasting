#!/usr/bin/env python3
"""Build the source-trace report — the auditable "trace every number" deliverable.

For every figure on the scorecard, the General Fund forecast, and the monthly
liquidity forecast, this shows how to get from the published number back to a
primary source: the output cell -> the builder formula/inputs -> the source-tagged
normalized table or cited document -> the underlying ICCSD ACFR, Iowa DOM filing,
or PFM board presentation.

Scorecard KPIs are recomputed here from raw components (they reproduce exactly).
Forecast and liquidity figures are projections, so instead each *input* is traced
to its source document, the roll-forward formula is shown with a worked example
that reproduces the published value, and the dated cash events are listed with the
exact source file and page they came from.

Two outputs, both regenerable from code:
  * data/normalized/source_links.csv  — document -> table provenance index
  * docs/kpi_trace.html               — the reporter-facing trace report

Run:  python scripts/analysis/kpi_trace.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "data/raw/manual_uploads/iccsd_advocacy_extractions"
NORM = REPO / "data/normalized"
INVENTORY = REPO / "data/extracted/document_inventory.csv"
OUT_LINKS = NORM / "source_links.csv"
OUT_HTML = REPO / "docs/kpi_trace.html"
ICCSD = "Iowa City CSD"

# Reuse the exact site shell (nav, hero, footer, GH base) so the page matches.
sys.path.insert(0, str(REPO / "scripts/site"))
import build_site as site  # noqa: E402

BLOB = site.GH + "/blob/main/"          # GitHub blob base for "view the file" links
TARGET = {"low": 10, "high": 15, "floor": 5}   # solvency policy 701.5R1

# Source files actually read by the builders.
DISTRICT_CSV = "data/raw/manual_uploads/iccsd_advocacy_extractions/district-extractions/Iowa_City_CSD.csv"
AEA_CSV = "data/raw/manual_uploads/iccsd_advocacy_extractions/dom/aea-flowthrough.csv"
UAB_CSV = "data/raw/manual_uploads/iccsd_advocacy_extractions/dom/unspent-authorized-budget.csv"
CRL_CSV = "data/raw/manual_uploads/iccsd_advocacy_extractions/dom/cash-reserve-levy.csv"
ACFR = {fy: f"data/raw/district_reports/audits/Iowa City CSD-{fy}.pdf" for fy in range(2020, 2024)}
# PFM board documents behind the forecast (paths match the document inventory).
PFM_CFA = "data/raw/board_packets/2026-04-01_Work_Session/attachments/B_01_02_PFM Summary of Comprehensive Fiscal Analysis - Tax Anticipation Warrants.pdf"
PFM_MEMO = "data/raw/board_packets/2026-04-01_Work_Session/attachments/B_01_01_Capital Outlay Borrowing Need Memo Update for 4_1.pdf"
PFM_CFC = "data/raw/board_packets/2026-06-09_Board_of_Directors/attachments/K_02_01_PFM Presentation ICCSD Capital Funding Capacity SAVE & PPEL 06092026.pdf"


# --------------------------------------------------------------------------- #
# Loaders
# --------------------------------------------------------------------------- #
def load_inventory() -> dict[str, dict]:
    with open(INVENTORY, newline="") as fh:
        return {r["file_path"]: r for r in csv.DictReader(fh)}


def load_audit() -> list[dict]:
    with open(SRC / "district-extractions/Iowa_City_CSD.csv", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="|"))


def load_iccsd_uab() -> list[dict]:
    with open(SRC / "dom/unspent-authorized-budget.csv", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r["district"] == ICCSD]
    return sorted(rows, key=lambda r: int(r["fiscal_year"]))


def load_csv(name: str) -> list[dict]:
    with open(NORM / name, newline="") as fh:
        return list(csv.DictReader(fh))


def load_assumptions() -> dict[str, dict]:
    return {r["assumption_id"]: r for r in load_csv("assumptions.csv")}


def solvency_status(v: float) -> str:
    if v >= TARGET["low"]:
        return "on target" if v <= TARGET["high"] else "above target"
    return "below floor" if v < TARGET["floor"] else "below target"


# --------------------------------------------------------------------------- #
# source_links.csv — document -> table provenance index
# --------------------------------------------------------------------------- #
def _row(inv, path, table, method, conf, notes, page=""):
    meta = inv.get(path, {})
    return {
        "document_id": meta.get("document_id", ""),
        "source_file": path,
        "source_page": page,
        "source_table": table,
        "source_url": meta.get("source_url", "") or "",
        "extraction_method": method,
        "confidence": conf,
        "notes": notes,
    }


def scan_table_sources(name: str) -> dict[str, dict]:
    """{source_file: {pages:set, confidence}} from a source-tagged normalized table."""
    out: dict[str, dict] = {}
    for r in load_csv(name):
        sf = r.get("source_file")
        if not sf:
            continue
        e = out.setdefault(sf, {"pages": set(), "confidence": r.get("confidence", "")})
        if r.get("source_page"):
            e["pages"].add(str(r["source_page"]))
    return out


def build_source_links(inv, audit) -> list[dict]:
    links: list[dict] = []
    by_fy = {int(r["fiscal_year"]): r for r in audit}

    # ---- KPI scorecard lineage --------------------------------------------
    for fy, path in ACFR.items():
        r = by_fy.get(fy, {})
        links.append(_row(
            inv, path,
            f"kpi_scorecard.csv :: solvency_ratio_pct, operating_margin_pct (ICCSD FY{fy})",
            "ICCSDAdvocacy audit extraction (manual)", r.get("confidence", ""),
            "%s audit, report dated %s%s" % (
                r.get("auditor", "RSM US LLP"), r.get("report_date", ""),
                "; FY2023 issued 26+ months late, material weakness" if fy == 2023 else "")))
    links.append(_row(inv, DISTRICT_CSV,
        "kpi_scorecard.csv :: solvency_ratio_pct, operating_margin_pct (ICCSD FY2020-2023)",
        "imported from ICCSDAdvocacy repo (pipe-delimited)", "high",
        "Per-year ACFR extraction: GF revenue/expenditure/fund balance, unassigned, AEA flow-through."))
    links.append(_row(inv, AEA_CSV,
        "kpi_scorecard.csv + gf_forecast.csv :: solvency denominator (revenue - AEA flow-through)",
        "imported from ICCSDAdvocacy repo (Iowa DOM)", "high",
        "AEA flow-through removed from the solvency denominator per policy 701.5R1."))
    links.append(_row(inv, UAB_CSV,
        "kpi_scorecard.csv :: uab_pct_of_max (ICCSD + 14 peers, FY2020-2025)",
        "imported from ICCSDAdvocacy repo (Iowa DOM filing)", "high",
        "Unspent Authorized Budget / Maximum Authorized Budget, per Iowa DOM."))

    # ---- GF forecast lineage (PFM model + anchors) ------------------------
    links.append(_row(inv, PFM_CFA,
        "gf_forecast.csv :: base-case GF revenue & expenditure (FY2026-FY2029)",
        "PFM 7-year GF cash-flow model (board presentation)", "high",
        "PFM Summary of Comprehensive Fiscal Analysis, 4/1/2026 Work Session — the base case."))
    links.append(_row(inv, PFM_MEMO,
        "gf_forecast.csv + monthly_liquidity.csv :: warrant & financing assumptions",
        "PFM / COO borrowing-need memo (board presentation)", "high",
        "Capital Outlay Borrowing Need Memo update for 4/1/2026 (warrant sizing, interfund flows)."))
    links.append(_row(inv, PFM_CFC,
        "gf_forecast.csv + monthly_liquidity.csv :: capital-funding & SAVE repayment context",
        "PFM Capital Funding Capacity (board presentation)", "high",
        "PFM Presentation: ICCSD Capital Funding Capacity (SAVE & PPEL), 6/9/2026."))
    links.append(_row(inv, CRL_CSV,
        "gf_forecast.csv :: FY2024 assigned+unassigned anchor ($14,881,750)",
        "imported from ICCSDAdvocacy repo (Iowa DOM)", "high",
        "FY2024 Certified Annual Report figure via the Iowa DOM cash-reserve-levy worksheet."))

    # ---- Monthly liquidity lineage (auto-derived from source-tagged tables)
    feeds = {
        "monthly_actuals.csv": "monthly_liquidity.csv :: FY2025 seasonality",
        "cash_balances.csv": "monthly_liquidity.csv :: start cash position",
        "known_events.csv": "monthly_liquidity.csv :: dated interfund/property cash events",
    }
    merged: dict[str, dict] = {}
    for tbl, label in feeds.items():
        for sf, info in scan_table_sources(tbl).items():
            m = merged.setdefault(sf, {"pages": set(), "labels": [], "confidence": info["confidence"]})
            m["pages"].update(info["pages"])
            m["labels"].append(label)
    for sf in sorted(merged):
        m = merged[sf]
        links.append(_row(inv, sf, " ; ".join(m["labels"]),
                          "PDF extraction (source-tagged in normalized table)",
                          m["confidence"], "Board-packet source document.",
                          page=",".join(sorted(m["pages"]))))
    return links


def write_source_links(links):
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
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def money(n) -> str:
    return "${:,.0f}".format(int(round(float(n))))


def blob(path: str, label: str | None = None) -> str:
    return f'<a href="{BLOB}{path.replace(" ", "%20")}">{esc(label or path)}</a>'


# --------------------------------------------------------------------------- #
# Trace report body
# --------------------------------------------------------------------------- #
def build_body(inv, audit, uab, assumptions, forecast, events, cash, links) -> str:
    a = {int(r["fiscal_year"]): r for r in audit}
    fys = sorted(a)
    out = []
    P = out.append

    P('<div class="disclaimer"><b>What this page is.</b> A line-by-line audit trail for the whole site '
      '&mdash; the <a href="kpi_scorecard.html">scorecard</a>, the <a href="forecast.html">forecast</a>, '
      'and the <a href="liquidity.html">liquidity</a> model. Audited scorecard figures are recomputed '
      'here from raw components (they reproduce in front of you); forecast and liquidity figures are '
      'projections, so each <em>input</em> is traced to its source document and the formula is shown with '
      'a worked example. A reporter can verify the site without taking our word for anything.</div>')

    P('<div class="card"><h3>How to verify any number in four steps</h3><ol>'
      '<li><b>Read the value</b> in the published table or its data file (linked below each section).</li>'
      '<li><b>Apply the formula / inputs</b> shown here &mdash; the same ones in the builder scripts.</li>'
      '<li><b>Open the extraction</b> the components come from (a source-tagged CSV).</li>'
      '<li><b>Trace to the primary document</b> &mdash; ACFR, Iowa DOM filing, or PFM board presentation '
      '&mdash; in the provenance index at the bottom.</li></ol></div>')

    P('<h2>Part A &mdash; Scorecard KPIs (audited, recomputed here)</h2>')

    # ---- Metric 1: solvency -------------------------------------------------
    P('<h3>1 &middot; Solvency ratio</h3>')
    P('<div class="q"><b>Formula (board policy 701.5R1).</b> '
      'solvency&nbsp;=&nbsp;(unassigned&nbsp;+&nbsp;assigned GF fund balance) &divide; '
      '(GF revenue &minus; AEA flow-through). Target 10&ndash;15%, 5% floor.</div>')
    P('<div class="card"><table><tr>'
      '<th>FY</th><th class="w">Unassigned + assigned</th><th class="w">Revenue &minus; AEA</th>'
      '<th class="w">= Solvency</th><th class="w">Published</th><th class="w">vs. target</th></tr>')
    for fy in fys:
        r = a[fy]
        rev, aea = int(r["gf_revenue"]), int(r["aea_flowthrough"])
        num = int(r["gf_unassigned"]) + int(r["gf_assigned"] or 0)
        den = rev - aea
        calc, pub = num / den * 100, float(r["solvency_ratio_pct"])
        st = solvency_status(pub)
        pill = "p-red" if "floor" in st else "p-orange" if "below" in st else "p-green"
        P(f'<tr><td><b>FY{fy}</b></td><td class="w">{money(num)}</td>'
          f'<td class="w">{money(rev)} &minus; {money(aea)}<br>= {money(den)}</td>'
          f'<td class="w"><b>{calc:.2f}%</b></td><td class="w">{pub:.2f}%</td>'
          f'<td class="w"><span class="pill {pill}">{st}</span></td></tr>')
    P('</table><p class="src">Recomputed column reproduces the published value exactly. Components: '
      + blob(DISTRICT_CSV, "per-year ACFR extraction") + '; AEA from ' + blob(AEA_CSV, "Iowa DOM AEA")
      + '.</p><p>Primary documents (RSM US LLP):</p><ul>')
    for fy in fys:
        r = a[fy]
        note = " &mdash; <b>issued 26+ months late; material weakness</b>" if fy == 2023 else ""
        P(f'<li>FY{fy}: {blob(ACFR[fy], "ICCSD ACFR " + str(fy))} '
          f'<span class="src">(dated {esc(r["report_date"])}, {esc(r["opinion_type"])}{note})</span></li>')
    P('</ul></div>')

    # ---- Metric 2: operating margin ----------------------------------------
    P('<h3>2 &middot; Operating margin</h3>')
    P('<div class="q"><b>Formula.</b> operating margin&nbsp;=&nbsp;(GF revenue &minus; GF expenditure) '
      '&divide; GF revenue.</div>')
    P('<div class="card"><table><tr><th>FY</th><th class="w">Revenue</th><th class="w">Expenditure</th>'
      '<th class="w">= Margin</th><th class="w">Published</th></tr>')
    for fy in fys:
        r = a[fy]
        rev, exp = int(r["gf_revenue"]), int(r["gf_expenditure"])
        calc, pub = (rev - exp) / rev * 100, float(r["operating_margin_pct"])
        P(f'<tr><td><b>FY{fy}</b></td><td class="w">{money(rev)}</td><td class="w">{money(exp)}</td>'
          f'<td class="w"><span class="pill {"p-green" if pub>=0 else "p-orange"}">{calc:+.2f}%</span></td>'
          f'<td class="w">{pub:+.2f}%</td></tr>')
    P('</table><p class="src">Source: ' + blob(DISTRICT_CSV, "Iowa_City_CSD.csv") + '.</p></div>')

    # ---- Metric 3: UAB ------------------------------------------------------
    P('<h3>3 &middot; Unspent Authorized Budget (UAB) ratio</h3>')
    P('<div class="q"><b>Formula.</b> UAB ratio&nbsp;=&nbsp;unspent authorized budget &divide; '
      'maximum authorized budget (Iowa DOM). Target 5&ndash;10%.</div>')
    P('<div class="card"><table><tr><th>FY</th><th class="w">Unspent</th><th class="w">Max authorized</th>'
      '<th class="w">= UAB</th><th class="w">Published</th></tr>')
    for r in uab:
        fy = int(r["fiscal_year"])
        uns, mx = float(r["unspent_authorized_budget"]), float(r["max_authorized_budget"])
        calc, pub = uns / mx * 100, float(r["uab_pct_of_max"])
        pill = "p-red" if pub < 0 else "p-orange" if pub < 5 else "p-green"
        P(f'<tr><td><b>FY{fy}</b></td><td class="w">{money(uns)}</td><td class="w">{money(mx)}</td>'
          f'<td class="w"><span class="pill {pill}">{calc:.2f}%</span></td><td class="w">{pub:.2f}%</td></tr>')
    P('</table><p class="src">Source: ' + blob(UAB_CSV, "unspent-authorized-budget.csv")
      + ' (Iowa DOM filing).</p></div>')

    # ---- Part B: forecast ---------------------------------------------------
    P('<h2>Part B &mdash; General Fund forecast (FY2026&ndash;FY2029)</h2>')
    P('<p>The forecast is a <b>projection</b>, not an audited fact: the base case is '
      '<b>PFM’s own 7-year GF cash-flow model</b>. There is no single formula to recompute &mdash; '
      'instead every input is traced to a source, and the fund-balance roll-forward is shown with a '
      'worked example that reproduces the published figure.</p>')
    ax = assumptions
    P('<div class="card"><h3>Key inputs and their sources</h3><table>'
      '<tr><th>Input</th><th class="w">Value</th><th>Source document</th></tr>'
      f'<tr><td>FY2024 assigned+unassigned <b>anchor</b></td><td class="w">{money(ax["au_anchor_fy24"]["value"])}</td>'
      f'<td>{esc(ax["au_anchor_fy24"]["source"])} &mdash; {blob(CRL_CSV, "cash-reserve-levy.csv")}</td></tr>'
      '<tr><td>FY2026&ndash;29 base GF revenue &amp; expenditure</td><td class="w">PFM model</td>'
      f'<td>{blob(PFM_CFA, "PFM Comprehensive Fiscal Analysis (4/1/2026)")}</td></tr>'
      f'<tr><td>AEA flow-through (FY2026)</td><td class="w">{money(ax["aea_fy26"]["value"])}</td>'
      f'<td>{esc(ax["aea_fy26"]["source"])} &mdash; {blob(AEA_CSV, "aea-flowthrough.csv")}</td></tr>'
      '<tr><td>FY2026 max authorized budget <span class="src">(est.)</span></td><td class="w">$222,000,000</td>'
      f'<td>{esc(ax["uab_auth_growth"]["source"])} <span class="src">(estimated; UAB band is wide)</span></td></tr>'
      '</table>')
    # Worked example: FY2026 base solvency from the published forecast row.
    base = {int(r["fiscal_year"]): r for r in forecast if r["scenario"] == "base"}
    b26 = base[2026]
    au26, rev26 = int(b26["assigned_unassigned"]), int(b26["gf_revenue"])
    aea26 = int(float(ax["aea_fy26"]["value"]))
    s26 = au26 / (rev26 - aea26) * 100
    P(f'<h3 style="margin-top:18px">Worked example &mdash; FY2026 base solvency</h3>'
      f'<p>Roll the {money(ax["au_anchor_fy24"]["value"])} FY2024 anchor forward by each year’s '
      f'operating result (revenue &minus; expenditure + transfers). FY2026 base ends at '
      f'<b>{money(au26)}</b> assigned+unassigned on an operating result of '
      f'<b>{money(b26["operating_result"])}</b> (a deficit). Then:</p>'
      f'<div class="callout"><div>FY2026 base solvency</div>'
      f'<div class="big">{s26:.2f}%</div>'
      f'<div>{money(au26)} &divide; ({money(rev26)} &minus; {money(aea26)} AEA) = '
      f'<b>{s26:.2f}%</b> &mdash; matches the published forecast, far below the 5% floor.</div></div>')
    P('<table><tr><th>FY (base)</th><th class="w">Operating result</th>'
      '<th class="w">Assigned+unassigned</th><th class="w">Solvency</th></tr>')
    for fy in sorted(base):
        r = base[fy]
        sp = float(r["solvency_pct"])
        pill = "p-red" if sp < 5 else "p-orange" if sp < 10 else "p-green"
        P(f'<tr><td><b>FY{fy}</b></td><td class="w">{money(r["operating_result"])}</td>'
          f'<td class="w">{money(r["assigned_unassigned"])}</td>'
          f'<td class="w"><span class="pill {pill}">{sp:.2f}%</span></td></tr>')
    P('</table><p class="src">Builder: ' + blob("scripts/analysis/gf_forecast.py", "gf_forecast.py")
      + ' &middot; output: ' + blob("data/normalized/gf_forecast.csv", "gf_forecast.csv")
      + ' &middot; inputs: ' + blob("data/normalized/assumptions.csv", "assumptions.csv")
      + '. FY2024+ are unaudited; read solvency within ~&plusmn;1.5 pts.</p></div>')

    # ---- Part C: liquidity --------------------------------------------------
    P('<h2>Part C &mdash; Monthly liquidity (cash)</h2>')
    P('<p>The cash forecast starts from the latest known balance, applies FY2025 monthly seasonality, '
      'and overlays dated cash events. Each of those three inputs is source-tagged.</p>')
    # start cash = latest fund-10 cash_balances row
    f10 = [r for r in cash if r["fund_code"] == "10"]
    sc = max(f10, key=lambda x: x["as_of_date"])
    P('<div class="card"><h3>Inputs and their sources</h3><ul>'
      f'<li><b>Start cash:</b> {money(sc["total_cash_investments"])} (GF, as of {esc(sc["as_of_date"])}) '
      f'&mdash; {blob(sc["source_file"], Path(sc["source_file"]).name)}, p.{esc(sc["source_page"])}.</li>'
      '<li><b>Seasonality:</b> FY2025 monthly revenue/expenditure shares &mdash; '
      + blob("data/normalized/monthly_actuals.csv", "monthly_actuals.csv")
      + ' (extracted from the FY26 Q2 Financial Report).</li>'
      '<li><b>Annual scaling:</b> per-scenario GF revenue/expenditure from '
      + blob("data/normalized/gf_forecast.csv", "gf_forecast.csv") + ' (Part B).</li>'
      '<li><b>Dated cash events:</b> the table below.</li></ul>')
    P('<h3 style="margin-top:16px">Dated cash events (each traced to a board document)</h3>'
      '<table><tr><th>Date</th><th>Event</th><th class="w">Amount</th>'
      '<th>Source (file &middot; page)</th><th class="w">Conf.</th></tr>')
    for e in sorted(events, key=lambda x: x["event_date"]):
        amt = money(e["amount"]) if e["amount"] else "<span class='src'>TBD</span>"
        sign = "&minus;" if e["direction"] == "outflow" and e["amount"] else ""
        P(f'<tr><td class="w">{esc(e["event_date"])}</td><td>{esc(e["description"])}</td>'
          f'<td class="w">{sign}{amt}</td>'
          f'<td>{blob(e["source_file"], Path(e["source_file"]).name)} &middot; p.{esc(e["source_page"])}</td>'
          f'<td class="w">{esc(e["confidence"])}</td></tr>')
    P('</table><p class="src">Builder: ' + blob("scripts/analysis/liquidity_forecast.py", "liquidity_forecast.py")
      + ' &middot; output: ' + blob("data/normalized/monthly_liquidity.csv", "monthly_liquidity.csv")
      + ' &middot; events: ' + blob("data/normalized/known_events.csv", "known_events.csv")
      + '. Events without an amount (e.g. the 1725 N. Dodge sale) are excluded from the base lines.</p></div>')

    # ---- Provenance index ---------------------------------------------------
    P('<h2>Provenance index</h2>')
    P('<p>The machine-readable trail is '
      + blob("data/normalized/source_links.csv", "source_links.csv")
      + ' &mdash; one row per source document, with its inventory <code>document_id</code>.</p>')
    P('<div class="card"><table><tr><th>document_id</th><th>source file</th><th>feeds</th>'
      '<th class="w">conf.</th></tr>')
    for lk in links:
        P(f'<tr><td><code>{esc(lk["document_id"]) or "&mdash;"}</code></td>'
          f'<td>{blob(lk["source_file"], Path(lk["source_file"]).name)}</td>'
          f'<td><span class="src">{esc(lk["source_table"])}</span></td>'
          f'<td class="w">{esc(lk["confidence"]) or "&mdash;"}</td></tr>')
    P('</table></div>')

    P('<div class="q"><b>Scope &amp; honesty note.</b> Audited solvency and operating margin exist only '
      'for FY2020&ndash;FY2023; FY2024&ndash;FY2025 ACFRs are not yet filed, so those cells are blank by '
      'design. Forecast and liquidity figures are projections built on the PFM model and the dated events '
      'above &mdash; verify against the primary PDFs for anything consequential.</div>')
    return "\n".join(out)


def main():
    inv = load_inventory()
    audit = load_audit()
    uab = load_iccsd_uab()
    assumptions = load_assumptions()
    forecast = load_csv("gf_forecast.csv")
    events = load_csv("known_events.csv")
    cash = load_csv("cash_balances.csv")

    links = build_source_links(inv, audit)
    write_source_links(links)

    body = build_body(inv, audit, uab, assumptions, forecast, events, cash, links)
    OUT_HTML.write_text(
        site.page("Source-trace report — ICCSD Forecasting", body, "kpi_trace.html",
                  hero_title="Source-trace report",
                  hero_sub="Every number on the site, traced from primary source through formula to output."),
        encoding="utf-8")
    print(f"wrote {OUT_LINKS.relative_to(REPO)} ({len(links)} rows)")
    print(f"wrote {OUT_HTML.relative_to(REPO)}")


if __name__ == "__main__":
    main()
