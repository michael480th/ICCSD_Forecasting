# Board materials triage — gold mines vs. noise

The merged board-packet corpus (`data/raw/board_packets/`, 14 meetings Jan–Jun
2026) holds **~520 documents, but only ~84 feed the cash forecast.** The rest are
contracts, data-privacy agreements (DPAs), MOUs, policies, and committee charters
— important governance, irrelevant to cash.

This document is the **extraction target list**: every forecast-relevant board
document, grouped by the canonical table it feeds. The classifications here are
applied to the inventory via `data/manual/document_classification_manual.csv`
(63 overrides), so `document_inventory.csv` reflects this triage. Regenerate the
list by re-running the inventory after editing the manual file.

> ⚠️ Relevance is a judgment call on filenames (the PDFs aren't parsed yet).
> Treat this as a living shortlist — correct anything mis-bucketed, and confirm
> the actual contents during extraction (Phase 2).

---

## Priority 1 — Direct cash position

The closest thing to a monthly cash read. **Start extraction here.**

| meeting | document | type | → table |
|---|---|---|---|
| 2026-05-12 | Financials as of 3.31.26 Board Mtg 5.12.26.pdf | `monthly_financial_report` | cash_balances |
| 2026-04-28 | Financial ICCSD Monthly Close Schedule as of 4.17.26.pdf | `monthly_financial_report` | cash_balances / monthly_actuals |
| 2026-02-10 | FY26 Quarter 2 Financial Report (1).pdf | `quarterly_financial_report` | cash_balances / receipts_disbursements |
| 2026-04-28 | PFM_Presentation_ICCSD_YTD_GenFund_Fiscal_Progress.pdf | `board_financial_update` | cash_balances (GF YTD) |
| 2026-05-12 | PFM Presentation ICCSD YTD General Fund Fiscal Progress … | `board_financial_update` | cash_balances (GF YTD) |

## Priority 2 — Monthly financial / CFO updates

One **Board Financial Leadership Update** per meeting, plus Interim CFO reports
(ICCSD has an interim/contracted CFO — FGMK/PFM). These narrate receipts,
disbursements, and risks → `monthly_actuals` + assumptions.

| meeting | document | type |
|---|---|---|
| 2026-02-10 | Financial Update - Feb 10 Board Meeting.pdf | `board_financial_update` |
| 2026-02-24 | ICCSD FGMK Interim CFO.pdf | `cfo_update` |
| 2026-03-10 | Board Financial Leadership Update.pdf | `board_financial_update` |
| 2026-03-24 | Interim Chief Financial (Officer Report).pdf | `cfo_update` |
| 2026-04-14 | Interim Chief Financial Officer Report 4.10.26 / 4.3.26.pdf | `cfo_update` |
| 2026-04-14 | Board Financial Leadership Update.pdf | `board_financial_update` |
| 2026-04-28 | Interim Chief Financial Report 4.17.26 / 4.24.26.pdf | `cfo_update` |
| 2026-04-28 | Board Financial Leadership Update.pdf | `board_financial_update` |
| 2026-05-12 | (Exhibit 2m) Board Financial Leadership Update – May 12, 2026.pdf | `board_financial_update` |
| 2026-06-09 | Board Financial Leadership Update.pdf | `board_financial_update` |

## Priority 3 — Accounts payable (disbursement backbone)

**36 documents** → `accounts_payable.csv`. Two formats of (likely) the same data:
weekly `BoardReport10003` runs and `Accounts_Payable_Summaries`. **Pick one as
canonical** to avoid double-counting disbursements; one per meeting batch.

- `Accounts_Payable_Summaries - YYYYMMDD.pdf` — one per meeting (cleaner)
- `…BoardReport10003.pdf` / `AP Board Report …pdf` — weekly check runs

(Full per-meeting list is in the inventory: filter `document_type =
accounts_payable_report`.)

## Priority 4 — One-time inflows: property-sale proceeds

`known_events.csv`. Spring 2026 property sales with **"Deposit of Proceeds to
General Fund"** hearings — exactly the uncertain one-time inflows the project plan
flags. Properties: **1725 N. Dodge St., Hills Property, Scanlon Property**, plus
"Deposit of Funds" notices/affidavits.

| meeting | document | type |
|---|---|---|
| 2026-05-12 | 1725 N. Dodge Street – Notice of PH for Deposit of Proceeds to General | `property_sale_document` |
| 2026-05-12 | Hills Property – Notice of Public Hearing, Deposit of Proceeds to General | `property_sale_document` |
| 2026-05-12 | Scanlon Property – Conveyance of Real Property / Notice of Public Hearing | `property_sale_document` |
| 2026-04-28 | Affidavit and Resolution re Conveyance of Real Property | `property_sale_document` |
| 2026-05-26 | (Affidavits of Publication) Deposit of Funds | `property_sale_document` |

## Priority 5 — Interfund loans & short-term borrowing

`interfund_loans.csv` / `known_events.csv`. The **GF→SAVE interfund loan** and an
**Anticipated Borrowing Need memo** are material to liquidity.

| meeting | document | type |
|---|---|---|
| 2026-01-27 | Resolution Approving Interfund Loan ICCSD.pdf | `interfund_loan_document` |
| 2026-05-12 | Resolution Approving Interfund Loan GF to SAVE Iowa City CSD.pdf | `interfund_loan_document` |
| 2026-03-24 | Interfund correction.xlsx | `interfund_loan_document` |
| 2026-05-12 | Anticipated Borrowing Need Memo Update for 4_28.pdf | `board_financial_update` (short-term borrowing) |

## Priority 6 — Budget authority

`budget_authority.csv`. FY27 certified budget cycle + FY26 amendment.

| meeting | document | type |
|---|---|---|
| 2026-02-24 | FY27 Certified Budget Update / Proposed Budget Actions (2026-27) | `certified_budget` |
| 2026-03-24 | FY27 Certified Budget / Exhibit 2c – Budget | `certified_budget` |
| 2026-04-28 | FY27 Certified Budget Discussion / NOPA 2026-2027 Certified Budget | `certified_budget` |
| 2026-05-12 | FY26 Certified Budget Amendment Public Hearing Notice | `certified_budget` |
| 2026-06-09 | Iowa City CSD FY27 Amendment.pdf | `budget_amendment` |

## Priority 7 — Forecast drivers (no document_type yet)

Relevant context, but no matching recognized `document_type` — left as
`generic_pdf`, listed here so they aren't forgotten:

- **Property-tax levy:** `NOPA - 2026-2027 Property Tax Levy.pdf` (2026-04-28) →
  revenue timing (`property_tax_receipts`)
- **Enrollment:** `Enrollment Board Report 25-26.pdf` (2026-02-10),
  `RFP - Demographic Study & Enrollment Projection.pdf` (2026-06-09)
- **General Fund detail:** `Building Level General Fund Expenditure Review.pdf`

---

## Noise — safe to skip (~400 docs)

Not cash-relevant: vendor **contracts & invoices**, **data-privacy agreements
(DPAs)** (Clever, GearLocker, IssueBadge, HMH, VHL…), **MOUs** (iJAG),
**board policies & regulations** (700 Policies, 208.R1), **Financial Oversight
Committee charters** (these contain the word "financial" but are governance, not
numbers), affidavits unrelated to fund deposits, and recycling/facility items.

The inventory leaves these as `generic_pdf` and the data-quality report flags
them `unknown_document_type` — that's expected and correct.

---

## Caveats found during triage

1. **Truncated-name twins.** Some files appear both full and truncated
   (`Interim Chief Financ.pdf` vs `Interim Chief Financial Officer Report
   4.10.26.pdf`; `FY27 Certified Budge.pdf`; `Board Financial lead.pdf`). Several
   may be duplicate copies — the duplicate detector will catch identical content;
   confirm any that differ.
2. **AP double-representation.** `Accounts_Payable_Summaries` vs weekly
   `BoardReport10003` likely cover the same disbursements — choose one canonical
   source per period.
3. **Property-sale cluster.** Multiple `Affidavit of Publication` files repeat
   across the 05-12 and 05-26 meetings; dedupe before counting proceeds once.
