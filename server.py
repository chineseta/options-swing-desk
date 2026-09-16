#!/usr/bin/env python3
"""Local proxy + static server for the US options-chain swing web app."""
from __future__ import annotations
import json, os, sys, urllib.error, urllib.parse, urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
ROOT = os.path.dirname(os.path.abspath(__file__))
CBOE = "https://cdn.cboe.com/api/global/delayed_quotes/options/{}.json"
UA = "Mozilla/5.0 (compatible; OptionsSwingDesk/1.0)"
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)
    def log_message(self, fmt, *args):
        sys.stderr.write("[desk] " + (fmt % args) + "\n")
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/chain":
            qs = urllib.parse.parse_qs(parsed.query)
            symbol = (qs.get("symbol") or ["SPY"])[0].strip().upper()
            symbol = "".join(c for c in symbol if c.isalnum() or c in ".-")[:12]
            if not symbol:
                return self._json(400, {"error": "missing symbol"})
            url = CBOE.format(symbol)
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    body = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            except urllib.error.HTTPError as e:
                self._json(e.code, {"error": f"CBOE {e.code}", "symbol": symbol})
            except Exception as e:
                self._json(502, {"error": str(e), "symbol": symbol})
            return
        if parsed.path in ("/", "/index.html"):
            self.path = "/index.html"
        return super().do_GET()
    def _json(self, code, obj):
        raw = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)
def main():
    port = int(os.environ.get("PORT", "8765"))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Options swing desk  http://127.0.0.1:{port}", flush=True)
    httpd.serve_forever()
if __name__ == "__main__":
    main()
