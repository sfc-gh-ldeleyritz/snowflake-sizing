"""embed-pptx-assets.py — Re-embed sizing-base-template.pptx into proposal-template.html.

Run after modifying assets/templates/sizing-base-template.pptx to keep the
in-browser PPTX export in sync.

Usage:
    cd plugins/snowflake-sizing
    python3 scripts/embed-pptx-assets.py

Commit both files afterwards.
"""
import base64
import pathlib
import sys

_SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent

PPTX_PATH = _PLUGIN_ROOT / "assets" / "templates" / "sizing-base-template.pptx"
HTML_PATH = _PLUGIN_ROOT / "assets" / "templates" / "proposal-template.html"
_PREFIX = "const SIZING_BASE_TEMPLATE_B64 = '"


def main() -> None:
    for p in (PPTX_PATH, HTML_PATH):
        if not p.is_file():
            print(f"ERROR: not found: {p}", file=sys.stderr)
            sys.exit(1)

    b64 = base64.b64encode(PPTX_PATH.read_bytes()).decode("ascii")
    print(f"PPTX: {PPTX_PATH.stat().st_size // 1024} KB → {len(b64)} base64 chars")

    lines = HTML_PATH.read_text(encoding="utf-8").splitlines(keepends=True)
    hits = [i for i, ln in enumerate(lines) if ln.startswith(_PREFIX)]
    if len(hits) != 1:
        print(
            f"ERROR: expected 1 match for SIZING_BASE_TEMPLATE_B64, got {len(hits)}",
            file=sys.stderr,
        )
        sys.exit(1)

    lines[hits[0]] = f"{_PREFIX}{b64}';\n"
    HTML_PATH.write_text("".join(lines), encoding="utf-8")
    print(f"Updated: {HTML_PATH}")
    print("Done. Commit assets/templates/sizing-base-template.pptx and proposal-template.html.")


if __name__ == "__main__":
    main()
