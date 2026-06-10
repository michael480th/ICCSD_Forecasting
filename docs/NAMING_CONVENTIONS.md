# Naming & Formatting Conventions

These rules keep source files, document ids, and normalized values consistent so
the pipeline stays reproducible as new documents are added.

## Raw file organization

Store raw files by source type and date under `data/raw/`:

```text
data/raw/board_packets/YYYY-MM-DD/      Board meeting materials, by meeting date
data/raw/district_reports/              District financial reports
data/raw/state_reports/                 State filings (certified annual report, etc.)
data/raw/transcripts/                   Meeting transcripts
data/raw/manual_uploads/                Ad-hoc public records request responses
```

A board-meeting folder may contain (not all are required):

```text
agenda.pdf
minutes.pdf
packet.pdf
section_f_consent.pdf
section_j_discussion.pdf
section_l_action.pdf
financial_report.pdf
transcript.txt
source_urls.md          ← record where each file was obtained
```

### File naming rules

- Use lowercase, `snake_case`, ASCII only. No spaces.
- Be descriptive and date-stamped where the date isn't already in the folder,
  e.g. `fy26_q3_financial_report_2026-05-12.pdf`.
- Prefix fiscal-year documents with `fyNN` (e.g. `fy26`, `fy27`).
- Keep the original document's meaning obvious from the filename alone.
- Always add a `source_urls.md` next to downloaded files listing the public URL
  and retrieval date for each.

## Document ids

`document_id` should be stable and human-readable. Recommended pattern:

```text
{YYYY-MM-DD}_{document_type}_{short_slug}
e.g. 2026-05-12_quarterly_financial_report_fy26_q3
```

The id must remain stable across pipeline re-runs; duplicate detection relies on
`file_hash`, not the id.

## Dates

- Calendar dates: ISO `YYYY-MM-DD`.
- Monthly periods: `YYYY-MM`.
- Fiscal years: ICCSD fiscal year runs **July 1 → June 30**; `FY26` means the
  year ending June 30, 2026.

## Fund names

Normalize all variants to a single canonical `fund_code` + `fund_name` from
`data/normalized/funds.csv`. Examples that all map to fund `10` / `General Fund`:

```text
General
General Fund
Fund 10
10 General Fund
General (10, 84)
```

## Number normalization

When extracting numeric values, normalize to plain numbers before storing:

| Source form | Stored as |
|-------------|-----------|
| `$1,234,567` | `1234567` |
| `(45,000)` (parentheses = negative) | `-45000` |
| `3.5%` | `3.5` (document the unit in the column/notes) |
| blank / `—` / `n/a` | empty cell |
| `1,234 ` (stray whitespace) | `1234` |
| OCR artifacts (`l` for `1`, `O` for `0`) | corrected digits |

Strip `$`, thousands separators, and surrounding whitespace. Preserve the sign.

## Confidence levels

Use `high`, `medium`, `low` consistently (see DATA_DICTIONARY for the meaning of
each in the forecast-confidence context).

## Manual entries

Every manual entry or override must record `source_file`, `source_page` (or
section), `reason`, `date_entered`, and `editor`. Corrections are additionally
logged in `data/manual/corrections_log.csv`.
