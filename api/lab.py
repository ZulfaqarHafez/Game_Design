"""Vercel Python function: the backtester API used by the website.

GET  /api/lab?op=strategies
POST /api/lab?op=backtest|validate|pine   (JSON body)
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gold-backtester"))

from goldlab.webapi import handle  # noqa: E402

MAX_BODY = 64_000


class handler(BaseHTTPRequestHandler):
    def _send(self, code, body):
        data = json.dumps(body, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store" if code != 200 or self.command == "POST" else "public, max-age=300")
        self.end_headers()
        self.wfile.write(data)

    def _op(self):
        return (parse_qs(urlparse(self.path).query).get("op") or [""])[0]

    def do_GET(self):
        op = self._op()
        if op != "strategies":
            return self._send(405, {"error": "Use POST for this operation"})
        self._send(*handle(op, None))

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            return self._send(413, {"error": "Request too large"})
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self._send(400, {"error": "Body must be JSON"})
        if not isinstance(req, dict):
            return self._send(400, {"error": "Body must be a JSON object"})
        self._send(*handle(self._op(), req))
