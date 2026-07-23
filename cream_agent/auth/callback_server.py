"""A tiny loopback HTTP server that catches a single OAuth redirect.

Native/CLI OAuth clients can't register a hosted redirect URI, so per the
MCP authorization spec (and OAuth 2.1 for public clients) we use
``http://localhost:<port>/callback`` and run a short-lived local server to
catch the one redirect the browser makes after the user approves access.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional
from urllib.parse import parse_qs, urlsplit


@dataclass
class CallbackResult:
    code: Optional[str] = None
    state: Optional[str] = None
    error: Optional[str] = None
    error_description: Optional[str] = None


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (stdlib method name)
        query = parse_qs(urlsplit(self.path).query)
        result = CallbackResult(
            code=query.get("code", [None])[0],
            state=query.get("state", [None])[0],
            error=query.get("error", [None])[0],
            error_description=query.get("error_description", [None])[0],
        )
        self.server.callback_result = result  # type: ignore[attr-defined]

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        if result.error:
            body = (
                f"<html><body><h2>Cream Agent</h2>"
                f"<p>Robinhood authorization failed: {result.error_description or result.error}. "
                f"You can close this tab and return to the terminal.</p></body></html>"
            )
        else:
            body = (
                "<html><body><h2>Cream Agent</h2>"
                "<p>Robinhood connected. You can close this tab and return to the terminal.</p>"
                "</body></html>"
            )
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass  # silence default stderr request logging


def wait_for_callback(port: int, timeout: float = 300.0) -> CallbackResult:
    """Start a loopback server on ``port``, block until the OAuth redirect
    arrives (or ``timeout`` seconds elapse), and return what it received.
    """
    server = HTTPServer(("127.0.0.1", port), _Handler)
    server.callback_result = None  # type: ignore[attr-defined]
    server.timeout = timeout

    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    result = getattr(server, "callback_result", None)
    server.server_close()
    if result is None:
        return CallbackResult(error="timeout", error_description="No redirect received in time")
    return result
