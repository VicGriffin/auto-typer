from __future__ import annotations

import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from shared_scraper import (
    PRESET_SITES,
    DependencyError,
    ScrapeError,
    calculate_metrics,
    extract_text_from_url,
)


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

DEFAULT_TEXT = (
    "This web version keeps the project's text workspace, scraping flow, and timed typing "
    "preview inside the browser. Paste your own text or scrape a supported typing site, then "
    "play it back on the typing pad to simulate the original desktop experience in a website."
)

APP_CONFIG = {
    "presets": PRESET_SITES,
    "defaultText": DEFAULT_TEXT,
}


def load_index_page() -> bytes:
    template = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
    rendered = template.replace("__APP_CONFIG__", json.dumps(APP_CONFIG))
    return rendered.encode("utf-8")


class OverlayTyperWebHandler(BaseHTTPRequestHandler):
    server_version = "OverlayTyperWeb/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path in {"/", "/index.html"}:
            self._send_bytes(load_index_page(), content_type="text/html; charset=utf-8")
            return

        if path == "/health":
            self._send_json({"status": "ok"})
            return

        if path.startswith("/static/"):
            self._serve_static_file(path)
            return

        self._send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/scrape":
            self._send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send_json({"error": "Request body must be valid JSON."}, status=HTTPStatus.BAD_REQUEST)
            return

        url = str(payload.get("url", "")).strip()
        duration = payload.get("duration", 1.0)

        if not url:
            self._send_json({"error": "Provide a URL to scrape."}, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            result = extract_text_from_url(url)
            metrics = calculate_metrics(result.text, duration)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except DependencyError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        except ScrapeError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
            return
        except Exception as exc:
            self._send_json({"error": f"Unexpected scraping error: {exc}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self._send_json(
            {
                "url": result.url,
                "source": result.source,
                "text": result.text,
                "used_selenium": result.used_selenium,
                "metrics": metrics,
            }
        )

    def _serve_static_file(self, request_path: str) -> None:
        relative_path = request_path.removeprefix("/static/")
        target = (STATIC_DIR / relative_path).resolve()

        try:
            target.relative_to(STATIC_DIR.resolve())
        except ValueError:
            self._send_json({"error": "Forbidden."}, status=HTTPStatus.FORBIDDEN)
            return

        if not target.is_file():
            self._send_json({"error": "Static asset not found."}, status=HTTPStatus.NOT_FOUND)
            return

        mime_type, _ = mimetypes.guess_type(target.name)
        content = target.read_bytes()
        self._send_bytes(content, content_type=mime_type or "application/octet-stream")

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self._send_bytes(body, status=status, content_type="application/json; charset=utf-8")

    def _send_bytes(
        self,
        body: bytes,
        status: HTTPStatus = HTTPStatus.OK,
        content_type: str = "application/octet-stream",
    ) -> None:
        self.send_response(status.value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def run() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))

    with ThreadingHTTPServer((host, port), OverlayTyperWebHandler) as server:
        print(f"Overlay Typer Bot Web running at http://127.0.0.1:{port}")
        server.serve_forever()


if __name__ == "__main__":
    run()
