# Data Dictionary

This document defines every canonical table in the ICCashForecast pipeline. It is
the authoritative reference for column names, meanings, and allowed values.

All tables are CSV with a header row. Conventions used throughout:

- **Dates** use ISO `YYYY-MM-DD`. Month-granularity values use `YYYY-MM`.
- **Money** is stored as plain numbers (no `$`, commas, or parentheses).
  Negatives use a leading `-`. See
  [NAMING_CONVENTIONS.md](NAMING_CONVENTIONS.md) for number normalization rules.
- **`confidence`** is one of `high`, `medium`, `low`.
- **`fund_code`** must exist in `funds.csv`.
- Every extracted row carries a source reference (`source_file`, `source_page`,
  and where relevant `document_id` / `extraction_method`).

Stage ownership:

| Directory | Tables | Written by |
|-----------|--------|------------|
| `data/extracted/` | `document_inventory.csv` | inventory stage |
| `data/normalized/` | canonical tables (forecast input) | normalize stage |
| `data/manual/` | manual overrides + corrections log | humans |
| `data/forecast/` | forecast output, risk scores | forecast stage |

---

## Inventory

### `data/extracted/document_inventory.csv`
Registry of every source file in `data/raw/`.

| Column | Description |
|--------|-------------|
| `document_id` | Stable unique id for the document |
| `file_hash` | Content hash (e.g. SHA-256) used for duplicate detection |
| `file_path` | Path relative to repo root |
| `meeting_date` | Board meeting / report date (`YYYY-MM-DD`) |
| `agenda_item` | Agenda item label, if applicable |
| `document_type` | One of the recognized document types (see below) |
| `title` | Human-readable document title |
| `source_url` | Public URL the file was obtained from |
| `date_added` | When the file was added to the repo (`YYYY-MM-DD`) |
| `processed` | Whether extraction has run (`true`/`false`) |
| `status` | Processing status (e.g. `new`, `extracted`, `error`, `skipped`) |
| `notes` | Free-text notes |

**Recognized `document_type` values:** `quarterly_financial_report`,
`monthly_financial_report`, `accounts_payable_report`, `cfo_update`,
`board_financial_update`, `board_minutes`, `board_packet`, `budget_amendment`,
`certified_budget`, `annual_financial_report`, `audit`, `debt_schedule`,
`interfund_loan_document`, `property_sale_document`, `capital_project_update`,
`transcript`, `generic_pdf`, `generic_excel`.

---

## Canonical / normalized tables (`data/normalized/`)

### `funds.csv`
Canonical fund list. Seeded in Phase 0.

| Column | Description |
|--------|-------------|
| `fund_code` | Numeric ICCSD fund code (e.g. `10`) |
| `fund_name` | Canonical fund name |
| `fund_group` | Grouping: `Operating`, `Capital`, `Debt Service`, etc. |
| `restricted_flag` | `true` if the fund is legally restricted |
| `notes` | Free-text notes |

### `cash_balances.csv`
Cash and investments by fund and date.

`as_of_date, fund_code, fund_name, cash_in_bank, investments,
total_cash_investments, source_file, source_page, extraction_method,
confidence, notes`

`total_cash_investments` should equal `cash_in_bank + investments`; mismatches
are flagged by validation.

### `receipts_disbursements.csv`
Cash-basis receipts and disbursements by fund.

`period_end, fund_code, fund_name, beginning_balance, budgeted_receipts,
receipts_to_date, budgeted_disbursements, disbursements_to_date, ending_balance,
source_file, source_page, confidence`

### `monthly_actuals.csv`
Monthly revenue and expenditure activity, one row per line item.

`month, fund_code, fund_name, line_item, type, amount, source_file, source_page,
confidence, notes`

**Valid `type` values:** `receipt`, `disbursement`, `transfer_in`,
`transfer_out`, `debt_service`, `interfund_loan_in`, `interfund_loan_out`,
`adjustment`.

### `accounts_payable.csv`
Board-approved or proposed AP batches.

`board_date, fund_code, fund_name, vendor, description, amount, source_file,
source_page, confidence, notes`

### `budget_authority.csv`
Certified / amended budget authority by fund and fiscal year.

`fiscal_year, fund_code, fund_name, budgeted_revenue, budgeted_expenditure,
budget_type, source_file, source_page, confidence, notes`

`budget_type` examples: `certified`, `amendment`, `proposed`.

### `debt_service.csv`
Debt-service obligations.

`due_date, fund_code, debt_issue, principal, interest, total_payment,
source_file, source_page, confidence, notes`

### `interfund_loans.csv`
Interfund loans and repayments.

`date_authorized, date_expected, date_actual, fund_from, fund_to, amount,
purpose, repayment_due, status, source_file, source_page, confidence, notes`

**Recommended `status` values:** `authorized`, `outstanding`,
`partially_repaid`, `repaid`, `unclear`, `cancelled`.

### `property_tax_receipts.csv`
Property-tax receipt timing by fund.

`receipt_date, fund_code, fund_name, levy_year, installment, amount,
source_file, source_page, confidence, notes`

### `state_aid_receipts.csv`
State foundation aid and related receipts.

`receipt_date, fund_code, fund_name, aid_type, fiscal_year, amount, source_file,
source_page, confidence, notes`

### `known_events.csv`
One-time or unusual inflows/outflows.

`event_date, fund_code, event_type, direction, amount, description, status,
source_file, source_page, confidence, notes`

`direction` is `inflow` or `outflow`. **Example `event_type` values:**
`property_sale_proceeds`, `bond_payment`, `capital_project_payment`,
`insurance_renewal`, `audit_cost`, `legal_cost`, `consulting_contract`,
`interfund_transfer`, `state_aid_timing_change`, `short_term_borrowing`,
`budget_cut`, `grant_reimbursement`.

### `assumptions.csv`
Forecast assumptions.

`assumption_id, scenario, fund_code, description, value, method, source,
confidence, active, notes`

`scenario` is `base`, `conservative`, or `stress` (or `all`). `active` is
`true`/`false`.

### `source_links.csv`
Normalized row → source provenance index.

`document_id, source_file, source_page, source_table, source_url,
extraction_method, confidence, notes`

### `data_quality_issues.csv`
Validation warnings and unresolved issues.

`run_date, severity, issue_type, fund_code, document_id, description,
recommended_action, status`

**`severity` values:** `info`, `warning`, `critical`.

---

## Manual override tables (`data/manual/`)

Manual files mirror their canonical counterparts and add override metadata
(`reason`, `date_entered`, `editor`). Overrides never silently replace extracted
values; the site discloses manually entered/corrected values.

| File | Notes |
|------|-------|
| `document_classification_manual.csv` | `document_id, file_path, document_type, reason, date_entered, editor, notes` |
| `cash_balances_manual.csv` | cash-balance schema + `reason, date_entered, editor` |
| `monthly_actuals_manual.csv` | monthly-actuals schema + `reason, date_entered, editor` |
| `known_events_manual.csv` | known-events schema + `reason, date_entered, editor` |
| `interfund_loans_manual.csv` | interfund-loans schema + `reason, date_entered, editor` |
| `assumptions_manual.csv` | assumptions schema + `reason, date_entered, editor` |
| `corrections_log.csv` | `date, table_name, row_id, field, old_value, new_value, reason, source_file, source_page, edited_by` |

---

## Forecast output (`data/forecast/`)

### `forecast_by_fund_month.csv`
Main forecast output, one row per fund / month / scenario.

`month, fund_code, fund_name, scenario, beginning_cash, projected_receipts,
projected_disbursements, transfers_net, interfund_loans_net, known_events_net,
ending_cash, days_cash_on_hand, confidence, status, notes`

The forecast identity:
`ending_cash = beginning_cash + projected_receipts − projected_disbursements
+ transfers_net + interfund_loans_net + known_events_net`.

### `risk_scores.csv`
Fund-level risk result.

`run_date, fund_code, fund_name, scenario, status, lowest_projected_cash,
lowest_projected_month, year_end_cash, primary_risk_reason, confidence, notes`

**`status` values:** `Good`, `At Risk`, `Red Flag`. Suggested rules:
`Good` = projected low point > 30 days of average monthly disbursements;
`At Risk` = positive but < 15 days; `Red Flag` = projected ending cash < $0 in
any month.

### `scenario_comparison.csv`
Side-by-side ending cash across scenarios.

`month, fund_code, fund_name, base_ending_cash, conservative_ending_cash,
stress_ending_cash, notes`

### `forecast_warnings.csv`
Forecast-time warnings.

`run_date, fund_code, scenario, severity, warning_type, description,
recommended_action`
