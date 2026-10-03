"""One-shot public-source deployment test. No document API or proxy is exposed."""
import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

state = {'status': 'starting', 'complete_packet_test': False}
lock = threading.Lock()
LISTING = 'https://simbli.eboardsolutions.com/SB_Meetings/SB_MeetingListing.aspx?S=36031992'
MEETING = 'https://simbli.eboardsolutions.com/SB_Meetings/ViewMeeting.aspx?S=36031992&MID=33526'
# Real public attachment ID observed in the selected meeting's CFO item.
ATTACHMENT = 'https://simbli.eboardsolutions.com/Meetings/Attachment.aspx?S=36031992&AID=616212&MID=33526&raw=1'


def blocked(text):
    text = text.lower()
    return any(s in text for s in ['pardon our interruption', 'trouble connecting to simbli',
                                   'verify you are human', 'request was blocked by our security'])


def update(**values):
    with lock:
        state.update(values)
        print(json.dumps(state), flush=True)


def probe():
    stage = 'browser_start'
    try:
        from playwright.sync_api import sync_playwright
        from pypdf import PdfReader
        from io import BytesIO
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context()
            page = context.new_page()
            for stage, url in [('listing', LISTING), ('meeting', MEETING)]:
                response = page.goto(url, wait_until='networkidle', timeout=45000)
                body = '\n'.join(frame.inner_text('body') for frame in page.frames)
                if blocked(body):
                    update(status='source_blocked', stage=stage,
                           explanation='Source security page returned. No retries or alternate routes attempted.')
                    return
                if not response or response.status != 200:
                    update(status='source_error', stage=stage, http_status=response.status if response else None)
                    return
                if stage == 'listing' and 'Meetings Listing' not in body:
                    raise ValueError('Expected listing content missing')
                if stage == 'meeting' and 'Regular Meeting' not in body:
                    raise ValueError('Expected meeting content missing')
                update(status='testing', stage=stage, page_text_chars=len(body))
            stage = 'document'
            response = context.request.get(ATTACHMENT, headers={'Cache-Control':'no-cache'}, timeout=45000)
            data = response.body()
            if blocked(data[:10000].decode('utf-8', 'ignore')):
                update(status='source_blocked', stage=stage)
                return
            if response.status != 200 or not data.startswith(b'%PDF-'):
                update(status='document_unverified', stage=stage, http_status=response.status,
                       bytes_received=len(data))
                return
            pdf = PdfReader(BytesIO(data))
            text = '\n'.join(page.extract_text() or '' for page in pdf.pages)
            update(status='sample_document_downloaded', stage=stage, bytes_received=len(data),
                   sha256=hashlib.sha256(data).hexdigest(), pages=len(pdf.pages), extracted_characters=len(text),
                   checked_at=datetime.now(timezone.utc).isoformat(),
                   complete_packet_test=False)
            browser.close()
    except Exception as e:
        # Avoid exposing page HTML, cookies, request tokens, or full stack traces.
        update(status='test_failed', stage=stage, error_type=type(e).__name__,
               runtime_detail=str(e)[:1600] if stage == 'browser_start' else 'See failure stage; no source content logged')


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ['/', '/health', '/status']:
            self.send_error(404)
            return
        with lock:
            payload = {'service':'icc-sd-retrieval-test', **state}
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    # Explicit opt-in avoids accidentally hitting Simbli during local validation.
    if os.environ.get('RUN_SOURCE_TEST') == '1':
        threading.Thread(target=probe, daemon=True).start()
    else:
        update(status='source_test_not_requested')
    ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('PORT','10000'))), Handler).serve_forever()
