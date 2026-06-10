#!/usr/bin/env python3
"""Build the ICCashForecast GitHub Pages site into docs/.

Converts the markdown analysis reports to styled, self-contained HTML pages
(shared docs/site.css), generates the landing page (index.html), and drops a
.nojekyll marker so GitHub Pages serves the files as-is. The hand-built
bond_rating_assessment.html is linked from the nav (it shares site.css).

Serve GitHub Pages from the `docs/` folder. Regenerate with:
    python scripts/site/build_site.py
"""
from __future__ import annotations
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "docs"
GH = "https://github.com/michael480th/ICCashForecast"

# Markdown reports to convert -> (output html, nav label, hero subtitle)
REPORTS = {
    "kpi_scorecard.md": ("kpi_scorecard.html", "KPI Scorecard",
                         "ICCSD vs. its own board targets and large Iowa peers"),
    "forecast.md": ("forecast.html", "Forecast",
                    "General Fund & solvency, reconciled to PFM's projection"),
    "liquidity.md": ("liquidity.html", "Liquidity",
                     "Month-by-month General Fund cash, with the warrant package"),
    "board_materials_triage.md": ("board_materials_triage.html", "Board Materials",
                                  "Which board documents feed the forecast — and which are noise"),
}
NAV_ITEMS = [
    ("index.html", "Home"),
    ("kpi_scorecard.html", "KPI Scorecard"),
    ("forecast.html", "Forecast"),
    ("liquidity.html", "Liquidity"),
    ("bond_rating_assessment.html", "Bond Rating"),
    ("board_materials_triage.html", "Board Materials"),
    (GH, "GitHub ↗"),
]

# --------------------------------------------------------------------------- #
# Minimal Markdown -> HTML
# --------------------------------------------------------------------------- #
_REPORT_MD = {k: v[0] for k, v in REPORTS.items()}


def inline(t: str) -> str:
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    def _link(m):
        text, url = m.group(1), m.group(2)
        url = _REPORT_MD.get(url, url)            # rewrite report .md links to .html
        return f'<a href="{url}">{text}</a>'
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _link, t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", t)
    return t


def _split_row(row: str) -> list[str]:
    row = row.strip().strip("|").replace("\\|", "\x00")
    return [c.strip().replace("\x00", "|") for c in row.split("|")]


def _table(rows: list[str]) -> str:
    header = _split_row(rows[0])
    sep_ok = len(rows) > 1 and set(rows[1].replace("|", "").strip()) <= set("-: ")
    body = rows[2:] if sep_ok else rows[1:]
    h = "<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in header) + "</tr></thead><tbody>"
    for r in body:
        h += "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in _split_row(r)) + "</tr>"
    return h + "</tbody></table>"


def _quote(lines: list[str]) -> str:
    parts, cur = [], []
    for ln in lines:
        if ln.strip() == "":
            if cur: parts.append(" ".join(cur)); cur = []
        else:
            cur.append(ln.strip())
    if cur: parts.append(" ".join(cur))
    return "<blockquote>" + "".join(f"<p>{inline(p)}</p>" for p in parts) + "</blockquote>"


def md_to_html(md: str) -> tuple[str, str]:
    """Return (hero_title, body_html). The leading '# Title' becomes the hero."""
    lines = md.split("\n")
    title = ""
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        lines = lines[1:]
    out, para, i, n = [], [], 0, len(lines)

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para).strip()) + "</p>")
            para.clear()

    while i < n:
        s = lines[i].strip()
        if not s:
            flush(); i += 1; continue
        m = re.match(r"(#{1,4})\s+(.*)", s)
        if m:
            flush(); lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>"); i += 1; continue
        if re.match(r"^(-{3,}|\*{3,})$", s):
            flush(); out.append("<hr>"); i += 1; continue
        if s.startswith("|"):
            flush(); tbl = []
            while i < n and lines[i].strip().startswith("|"):
                tbl.append(lines[i].strip()); i += 1
            out.append(_table(tbl)); continue
        if s.startswith(">"):
            flush(); bq = []
            while i < n and lines[i].strip().startswith(">"):
                bq.append(re.sub(r"^\s*>\s?", "", lines[i])); i += 1
            out.append(_quote(bq)); continue
        if re.match(r"^([-*]|\d+\.)\s+", s):
            flush(); items, ordered = [], bool(re.match(r"^\d+\.\s", s))
            while i < n:
                st = lines[i].strip()
                mm = re.match(r"^([-*]|\d+\.)\s+(.*)", st)
                if mm:
                    items.append(inline(mm.group(2))); i += 1
                elif st and lines[i].startswith(" ") and not st.startswith(("|", "#")):
                    if items: items[-1] += " " + inline(st)
                    i += 1
                else:
                    break
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{it}</li>" for it in items) + f"</{tag}>")
            continue
        para.append(s); i += 1
    flush()
    return title, "\n".join(out)


# --------------------------------------------------------------------------- #
# Page shell
# --------------------------------------------------------------------------- #
def nav(active: str) -> str:
    links = "".join(
        f'<a href="{href}"{" aria-current=page" if href == active else ""}>{label}</a>'
        for href, label in NAV_ITEMS)
    return ('<nav class="topnav"><a class="brand" href="index.html">ICCashForecast</a>'
            f'<div class="links">{links}</div></nav>')


FOOTER = (
    '<footer><p><b>About.</b> ICCashForecast is an <b>unofficial</b> analysis project that '
    'extracts Iowa City Community School District financial data from public records and builds '
    'a transparent General Fund cash forecast. It is <b>not affiliated</b> with ICCSD, Moody&rsquo;s, '
    'S&amp;P, or PFM. Figures are estimates carrying material uncertainty; nothing here is investment '
    f'advice.</p><p class="src">Sources: ICCSD audited ACFRs, Iowa DOM filings, and PFM board '
    f'presentations. Built from the <a href="{GH}">ICCashForecast repository</a>. '
    'Last generated 2026-06-10.</p></footer>')


def page(title: str, body: str, active: str, hero_title: str = "", hero_sub: str = "",
         wrap_content: bool = True) -> str:
    hero = ""
    if hero_title:
        hero = ('<header class="hero"><div class="wrap">'
                '<p class="kicker">ICCashForecast &middot; unofficial analysis</p>'
                f"<h1>{hero_title}</h1>" + (f"<p>{hero_sub}</p>" if hero_sub else "") +
                "</div></header>")
    inner = f'<main class="content">{body}</main>' if wrap_content else body
    return ("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
            '<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{title}</title>\n<link rel=\"stylesheet\" href=\"site.css\">\n</head>\n<body>\n"
            f"{nav(active)}{hero}<div class=\"wrap\">{inner}{FOOTER}</div>\n</body>\n</html>\n")


# --------------------------------------------------------------------------- #
# Landing page
# --------------------------------------------------------------------------- #
LANDING_BODY = f"""
<div class="ribbon-band"><div class="ribbon">
  <a class="tile accent" href="bond_rating_assessment.html">
    <div class="eyebrow">Featured assessment</div>
    <div class="h">Hypothetical 2028 Moody&rsquo;s GO rating</div>
    <p class="sub">Most likely <b>Baa1/Baa2</b> &middot; ~72% investment grade &middot; ~20% chance of
    no rating. How a GO rating is built, ICCSD scored factor-by-factor, and the probability spread.</p>
    <span class="go">Open the rating assessment &rarr;</span>
  </a>
  <a class="tile" href="#contents">
    <div class="eyebrow">What&rsquo;s inside</div>
    <div class="h">Repository contents</div>
    <p class="sub">~660 source documents, the extraction pipeline, the canonical data tables, and the
    analysis reports behind this forecast — all reproducible from code.</p>
    <span class="go">Jump to contents &rarr;</span>
  </a>
</div></div>

<div class="disclaimer"><b>Unofficial project.</b> An independent analysis built from public records —
not affiliated with ICCSD, Moody&rsquo;s, S&amp;P, or PFM, and not investment advice. All figures are
estimates with material uncertainty.</div>

<p>This is a transparent, source-traced cash forecast for the <b>Iowa City Community School
District</b> General Fund, built by extracting figures from the district&rsquo;s own board packets,
audited financial reports, and Iowa state filings. The picture: ICCSD is <b>solvent but structurally
tight</b> — running operating deficits, holding razor-thin reserves, and rolling short-term debt to
stay liquid.</p>

<h2>General Fund solvency</h2>
<p>Solvency ratio = unrestricted (assigned + unassigned) GF fund balance &divide; (revenue &minus; AEA
flow-through), the metric in board policy 701.5R1. Base case below is reconciled to <b>PFM&rsquo;s own
7-year cash-flow model</b>.</p>
<table>
  <tr><th>Fiscal year</th><th>Solvency (base)</th><th>vs. board target</th></tr>
  <tr><td>FY2024 (CAR)</td><td class="w">7.49%</td><td>below 10&ndash;15% target</td></tr>
  <tr><td>FY2025 (est.)</td><td class="w">4.09%</td><td>below 5% floor</td></tr>
  <tr><td><b>FY2026</b></td><td class="w"><b>0.50%</b></td><td><span class="pill p-red">far below floor</span></td></tr>
  <tr><td>FY2027</td><td class="w">1.18%</td><td>below floor</td></tr>
  <tr><td>FY2028</td><td class="w">2.41%</td><td>below floor</td></tr>
  <tr><td>FY2029</td><td class="w">3.52%</td><td>below floor</td></tr>
</table>
<p>PFM projects ~$225M of FY2026 spending (vs. the $212M budget) — a <b>~$6M operating deficit</b> —
so solvency sits near zero in FY2026 and stays <b>below the 5% floor every year through FY2029</b>.
<a href="forecast.html"><b>Full forecast &amp; scenario bands &rarr;</b></a></p>

<h2>Spending authority &amp; peers</h2>
<p>The Unspent Authorized Budget (UAB) ratio is how much legal spending room is left at year end.
ICCSD&rsquo;s is the thinnest of any large Iowa district.</p>
<table>
  <tr><th>Metric</th><th>Value</th><th></th></tr>
  <tr><td>FY2025 UAB ratio</td><td class="w">2.31%</td><td><b>last of 15</b> large Iowa districts (peer median ~16%)</td></tr>
  <tr><td>FY2026 UAB (est.)</td><td class="w">~&minus;1.4%</td><td>at or beyond the legal spending limit</td></tr>
  <tr><td>Board target</td><td class="w">5&ndash;10%</td><td>missed every year since FY2020</td></tr>
</table>
<p><a href="kpi_scorecard.html"><b>KPI scorecard &amp; peer benchmarking &rarr;</b></a></p>

<h2>Cash &amp; the warrant treadmill</h2>
<p>The district collects property tax in two waves (October, April), so cash draws down in between.
On operating cash alone the General Fund <b>goes negative in September 2026</b>. A <b>$25M revenue
anticipation warrant</b> bridges that trough — but it is repaid ~$26.5M in spring 2027, leaving cash
at only <b>~$0.4M by June 2027</b> (insufficient for July payroll), which is why a <b>second ~$10M
warrant</b> is already planned for FY2027. The warrants manage <em>liquidity</em>; they do not fix the
<em>solvency</em> gap. <a href="liquidity.html"><b>Monthly liquidity forecast &rarr;</b></a></p>

<h2 id="contents">Repository contents</h2>
<p>Everything here is reproducible from the <a href="{GH}">ICCashForecast repository</a>. An auditable
pipeline turns source PDFs into canonical data and forecasts:</p>
<div class="card">
<ul>
  <li><b>Source documents</b> (<code>data/raw/</code>) — ~660 public records: 14 board-meeting packets
  (Jan&ndash;Jun 2026), audited ACFRs (FY2020&ndash;2023), Iowa DOM filings, and peer-district audits.</li>
  <li><b>Inventory</b> (<code>data/extracted/</code>) — every document hashed, classified, and
  deduplicated, with data-quality flags.</li>
  <li><b>Canonical data</b> (<code>data/normalized/</code>) — cash balances, receipts &amp;
  disbursements, monthly actuals, the GF forecast, KPI scorecard, interfund loans, and known events.</li>
  <li><b>Pipeline</b> (<code>scripts/</code>) — inventory &rarr; extractors &rarr; analysis &rarr; this
  site, covered by an automated test suite.</li>
  <li><b>Reports</b> (<code>docs/</code>) — the analyses below, also published as this site.</li>
</ul>
</div>
<h3>The analysis reports</h3>
<div class="card"><ul>
  <li><a href="kpi_scorecard.html">Financial-KPI scorecard</a> &mdash; metrics vs. targets &amp; peers</li>
  <li><a href="forecast.html">General Fund forecast (FY2026&ndash;FY2029)</a> &mdash; solvency &amp; UAB, PFM-reconciled</li>
  <li><a href="liquidity.html">Monthly liquidity forecast</a> &mdash; cash through June 2027 with the warrant package</li>
  <li><a href="bond_rating_assessment.html">Hypothetical 2028 Moody&rsquo;s GO rating</a> &mdash; methodology, scoring &amp; probabilities</li>
  <li><a href="board_materials_triage.html">Board-materials triage</a> &mdash; which board documents feed the forecast</li>
</ul></div>
"""


def main():
    DOCS.mkdir(exist_ok=True)
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")

    (DOCS / "index.html").write_text(
        page("ICCSD General Fund Financial Forecast — ICCashForecast", LANDING_BODY, "index.html",
             hero_title="ICCSD General Fund Financial Forecast",
             hero_sub="A transparent, source-traced cash forecast for the Iowa City Community "
                      "School District."),
        encoding="utf-8")
    print("wrote docs/index.html, docs/.nojekyll")

    for md_name, (html_name, _label, sub) in REPORTS.items():
        src = DOCS / md_name
        if not src.exists():
            print(f"  ! missing {md_name}, skipped"); continue
        title, body = md_to_html(src.read_text(encoding="utf-8"))
        (DOCS / html_name).write_text(
            page(f"{title} — ICCashForecast", body, html_name,
                 hero_title=title, hero_sub=sub),
            encoding="utf-8")
        print(f"  {md_name} -> docs/{html_name}")


if __name__ == "__main__":
    main()
