# Test fixtures

`sample_raw/` contains **synthetic, throwaway** files used only by the test
suite. They are NOT real ICCSD documents and contain no real financial data.
The `.pdf`/`.xlsx` files are plain text with fake content — they exercise
hashing, filename/folder classification, and duplicate detection without
requiring real document parsing.

Notable cases:
- `board_packets/2026-05-12/fy26_q3_financial_report_2026-05-12.pdf` and
  `board_packets/2026-06-09/q3_financial_report_resend.pdf` have **identical
  content** to exercise duplicate detection (same document, different name).
- Filenames are chosen to exercise the auto-classifier (financial report,
  minutes, section action items, accounts payable, transcript).
