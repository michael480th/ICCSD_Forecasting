# ICCSD hosted retrieval test

Small deployment probe for the public ICCSD meeting guide. This is not the production guide or a complete packet downloader.

Render native Python web service, free plan:
- Build: `pip install -r requirements.txt && python -m playwright install chromium`
- Start: `python app.py`
- Set `RUN_SOURCE_TEST=1` for the explicitly requested one-shot source test.
- Endpoints: `/health`, `/status`.

The browser checks the official listing, selected meeting, and one known PDF attachment. It validates the PDF signature, parses all pages, records a content hash and check timestamp, and reports readable character count. It stops on a source security block. No stealth settings, alternate IPs, challenge bypasses, or credential access are used.

A successful sample test does not establish complete packet coverage. An unsuccessful browser launch may indicate missing native libraries; evaluate the deployment logs before changing configuration. No public endpoint triggers downloads or accepts arbitrary URLs.

The free host can sleep after inactivity and is only for this test, not the final speed target. Set RUN_SOURCE_TEST=0 after the test so future restarts do not repeat it.
