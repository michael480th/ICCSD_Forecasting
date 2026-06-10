# scripts/extractors

Document-type-specific extractors that turn source PDFs into canonical tables.

## Implemented

### `quarterly_financial_report.py`
Parses ICCSD quarterly "Financial Report" PDFs (FY26 Q2, Q3, …) into:

| Output | From | Per |
|--------|------|-----|
| `data/normalized/receipts_disbursements.csv` | Combined Statement of Receipts & Disbursements (Cash Basis) | fund (10,21,22,33,36,40,61) |
| `data/normalized/cash_balances.csv` | Cash and Investments Detail | fund group, with cash-in-bank vs. investments |

Reports are matched by **content** (the Combined-Statement marker), not just the
inventory `document_type`, so the Q3 report (filed as "Financials as of 3.31.26")
is handled too. Text comes from `scripts/extract/extract_pdf_text.py` (pdfplumber,
with a `.txt`-sidecar fallback).

**Robustness:** amounts in these PDFs extract with stray intra-number spaces
(`$ 1 7,852,375` → 17,852,375); the parser isolates amounts by splitting each row
on `$` then stripping spaces. Parentheses = negative. Values are tagged
`confidence = medium` (unaudited internal records). The six cash groups reconcile
to "Total All Funds" within rounding — a built-in correctness check.

```bash
python scripts/extractors/quarterly_financial_report.py
```

## Planned
`accounts_payable_report.py`, `cfo_update.py`, `board_minutes.py`,
`certified_budget.py`, `annual_report.py`, `debt_schedule.py`,
`generic_pdf_text.py`, `generic_excel.py` — see the project plan.
