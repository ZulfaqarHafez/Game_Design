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

from goldlab.webapi import MAX_BODY, route  # noqa: E402


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
        self._send(*route("GET", self._op()))

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        # Read at most one byte past the limit so oversized bodies get a 413 without being buffered.
        self._send(*route("POST", self._op(), self.rfile.read(min(n, MAX_BODY + 1)) if n > 0 else b""))
