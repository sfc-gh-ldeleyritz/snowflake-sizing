#!/usr/bin/env python3
"""Local one-click PPTX render bridge for the proposal template.

The proposal HTML's "Export JSON for PPTX" button POSTs its in-browser
SIZING_SPEC to this server, which calls renderer/pptx/build_pptx.build() and
streams the resulting .pptx back as the HTTP response so the browser downloads
a real PowerPoint. If this server is not running, the button falls back to
downloading the spec JSON (the legacy behavior), which an SE can feed to
scripts/render-pptx.py by hand.

Usage:
    python3 scripts/serve-pptx.py
    python3 scripts/serve-pptx.py --port 8765
    python3 scripts/serve-pptx.py --open sizings/<proposal>.html
    python3 scripts/serve-pptx.py --pricing assets/snowflake_pricing_master.json

Endpoints:
    GET  /health       -> {"ok": true}
    POST /render-pptx  -> body = SIZING_SPEC JSON; returns .pptx bytes

Authoritative totals and internal-pricing stripping are handled inside build()
exactly as the CLI path does, so a browser-edited (and possibly stale)
computed_totals block cannot affect the rendered deck.

Security: binds to 127.0.0.1 only. Responses set Access-Control-Allow-Origin: *
so a proposal opened from file:// (Origin: null) can read the binary response;
the server only renders a deck from the posted spec and never writes to disk.

Exit codes:
    0  Clean shutdown (Ctrl-C).
    2  Argument / pricing-load error.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_THIS_DIR = pathlib.Path(__file__).resolve().parent
_PLUGIN_ROOT = _THIS_DIR.parent
_DEFAULT_PRICING = _PLUGIN_ROOT / "assets" / "snowflake_pricing_master.json"

# Ensure renderer/ and framework/ are importable (mirrors render-pptx.py).
sys.path.insert(0, str(_PLUGIN_ROOT))
sys.path.insert(0, str(_PLUGIN_ROOT / "framework"))

from renderer.pptx.build_pptx import build  # noqa: E402

PPTX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)

# Parsed snowflake_pricing_master.json, loaded once at startup in main().
# build() deep-copies before stripping, so this dict is never mutated.
_PRICING: dict = {}


class PptxBridgeHandler(BaseHTTPRequestHandler):
    """Handles /health (GET), /render-pptx (POST) and CORS preflight (OPTIONS)."""

    server_version = "SizingPptxBridge/1.0"
    protocol_version = "HTTP/1.1"

    # ---- response helpers ---------------------------------------------- #
    def _set_cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send(self, status: int, body: bytes, content_type: str,
              extra_headers: "dict | None" = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._set_cors()
        for key, val in (extra_headers or {}).items():
            self.send_header(key, val)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _send_text(self, status: int, text: str) -> None:
        self._send(status, text.encode("utf-8"), "text/plain;charset=utf-8")

    def _send_json(self, status: int, obj: dict) -> None:
        self._send(status, json.dumps(obj).encode("utf-8"),
                   "application/json;charset=utf-8")

    # ---- verb handlers ------------------------------------------------- #
    def do_OPTIONS(self) -> None:  # noqa: N802
        # CORS preflight. The button uses a safelisted Content-Type so no
        # preflight is normally sent, but answer it anyway for robustness.
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self._set_cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] == "/health":
            self._send_json(200, {"ok": True})
        else:
            self._send_text(404, "Not found. Try GET /health or POST /render-pptx.")

    def do_POST(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] != "/render-pptx":
            self._send_text(404, "Not found. POST the SIZING_SPEC JSON to /render-pptx.")
            return

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            self._send_text(400, "Empty request body; expected SIZING_SPEC JSON.")
            return
        raw = self.rfile.read(length)

        try:
            spec = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._send_text(400, f"Invalid JSON in request body: {exc}")
            return

        t0 = time.perf_counter()
        try:
            pptx_bytes = build(spec, _PRICING)  # no out_path => bytes only, no disk write
        except Exception as exc:  # noqa: BLE001
            self._send_text(500, f"PPTX build failed: {exc}\n\n{traceback.format_exc()}")
            return

        if pptx_bytes[:2] != b"PK":
            self._send_text(500, "Build produced invalid output (missing PK ZIP magic).")
            return

        self._send(200, pptx_bytes, PPTX_CONTENT_TYPE,
                   {"Content-Disposition": 'attachment; filename="sizing.pptx"'})
        ms = (time.perf_counter() - t0) * 1000.0
        self.log_message("rendered PPTX (%d bytes, %.0f ms)", len(pptx_bytes), ms)

    # ---- logging ------------------------------------------------------- #
    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        sys.stderr.write("serve-pptx: %s %s\n" % (self.command or "-", fmt % args))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1",
                        help="Bind host (default: 127.0.0.1, loopback only).")
    parser.add_argument("--port", type=int, default=8765,
                        help="Bind port (default: 8765).")
    parser.add_argument("--pricing", default=str(_DEFAULT_PRICING),
                        help="Path to snowflake_pricing_master.json.")
    parser.add_argument("--open", dest="open_path", default=None, metavar="HTML",
                        help="Open this proposal HTML in the browser after start.")
    parser.add_argument("--no-open", action="store_true",
                        help="Do not open a browser even if --open is given.")
    args = parser.parse_args()

    pricing_path = pathlib.Path(args.pricing)
    if not pricing_path.is_file():
        sys.stderr.write(f"serve-pptx: pricing not found at {pricing_path}\n")
        return 2
    try:
        global _PRICING
        _PRICING = json.loads(pricing_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        sys.stderr.write(f"serve-pptx: failed to load pricing JSON - {exc}\n")
        return 2

    httpd = ThreadingHTTPServer((args.host, args.port), PptxBridgeHandler)
    base = f"http://{args.host}:{args.port}"
    print(f"serve-pptx: PPTX render bridge listening on {base}")
    print(f"  health : {base}/health")
    print(f"  render : POST {base}/render-pptx  (body = SIZING_SPEC JSON)")
    print(f"  pricing: {pricing_path}")
    print("  In the proposal, click 'Export JSON for PPTX' to download a .pptx.")
    print("  Press Ctrl-C to stop.")

    if args.open_path and not args.no_open:
        html_path = pathlib.Path(args.open_path).resolve()
        if html_path.is_file():
            webbrowser.open(html_path.as_uri())
            print(f"  opened : {html_path}")
        else:
            sys.stderr.write(f"serve-pptx: --open file not found: {html_path}\n")

    # Flush the banner so the URL is visible even when stdout is piped to a log.
    sys.stdout.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nserve-pptx: shutting down.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
