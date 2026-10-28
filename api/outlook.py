"""Vercel Python function: the gold outlook written by the analyst.

GET  /api/outlook              latest outlook, score and refresh policy (made on the spot if none exists)
POST /api/outlook?refresh=1    a new outlook, allowed once an hour, or any time with a bearer secret
GET  /api/outlook (cron)       Vercel's daily cron sends Authorization: Bearer $CRON_SECRET, which forces a refresh
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gold-backtester"))

from goldlab.analyst import http as outlook_http  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def _run(self):
        u = urlparse(self.path)
        query = {k: v[0] for k, v in parse_qs(u.query).items()}
        code, body = outlook_http(self.command, query, {k.lower(): v for k, v in self.headers.items()})
        data = json.dumps(body, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    do_GET = _run
    do_POST = _run
