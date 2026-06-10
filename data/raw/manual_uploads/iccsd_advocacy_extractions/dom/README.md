# Iowa DOM state-data layer (state-computed, UNAUDITED)

Per-district data for the 15 benchmarked districts, extracted from the Iowa Department of
Management / Department of Education workbooks uploaded to the repo (UAB/, AEA/,
PropertyValuation/, PropertyTaxRateFiles/, FinalCashReserveLevies/, AtRiskFormula/,
AidandLevyTaxCertification/). Reproduce with `scripts/extract_dom.py`.

All tables join on district name (mapped from the 4-digit DOM `Dist` code; lookalikes
Louisa-Muscatine / West Burlington / Western Dubuque are excluded). These figures are
**state-computed and unaudited** — they exist independent of each district's audit, so
coverage includes districts whose audits are missing (Iowa City FY2024–FY2025).

| File | Coverage | Key fields | Framework use |
|---|---|---|---|
| `unspent-authorized-budget.csv` | FY20–25 | max_authorized_budget, **unspent_authorized_budget**, uab_pct_of_max | **A2 — Iowa's #1 health metric**; negative = unlawful (SBRC) |
| `aea-flowthrough.csv` | FY20–25 | aea_flowthrough ($) | Clean AEA pass-through → exact ISFIS solvency denominator |
| `certified-enrollment.csv` | FY20–25 | certified_enrollment (DOM x249, funding/budget enrollment) | Uniform per-pupil denominator; fills audit gaps |
| `cash-reserve-levy.csv` | FY20–25 | cash_reserve_levy, twenty_pct_cap, levying_maximum, crl_pct_of_cap | **A9 — solvency lever**; who taxes to stay liquid |
| `levy-rates-and-valuation.csv` | FY20–25 | ISL, management, voted/regular PPEL, debt-service, grand-total rate; net & taxable valuation | **B6 levy capacity**; property-wealth base |
| `assessed-valuation-latest.csv` | latest (FY26) | assessed_actual_with_ge (100% value) | **B5 — 5%-of-actual-value GO-debt limit** |
| `at-risk.csv` | FY20–25 | atrisk weighting + dollars_generated, district_cost_pp | Spending-authority driver (the Cedar Rapids SBRC story); poverty proxy |
| `aid-levy-summary.csv` | latest | budget_enrollment, district & state cost per pupil | Formula context |

**Note on enrollment:** DOM `x249` (funding/budget enrollment) differs ~1–3% from the audit
"certified enrollment" figures (definitional / one-year-lag). The state figure is used as the
canonical, uniform, complete denominator; the audit figure is retained in the master dataset.

Source: Iowa DOM school-resources reports (dom.iowa.gov) + DE Aid & Levy.
