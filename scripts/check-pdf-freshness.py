#!/usr/bin/env python3
"""scripts/check-pdf-freshness.py — detect when the legal pricing PDF is newer.

DETECT-ONLY. This never edits the static master. It downloads the authoritative
Snowflake *Service Consumption Table* PDF, reads the ``Effective: <date>`` line
off page 1, and compares it to ``assets/snowflake_pricing_master.json`` ->
``metadata.effective_date``.

The static master (ai_features token rates, serverless, openflow, postgres,
org-usage, replication, ...) is hand-maintained from this PDF. When Snowflake
publishes a newer edition this script flags it so a human can refresh the master;
the scheduled CI job turns that signal into a GitHub issue.

Exit codes:
    0  In sync   — master effective_date >= PDF effective_date.
    1  STALE     — PDF effective_date is NEWER than the master (action needed).
    2  Unknown   — could not download / parse / locate pdftotext (check skipped).

Usage:
    python3 scripts/check-pdf-freshness.py
    python3 scripts/check-pdf-freshness.py --pdf path/to/local.pdf   # skip download
    python3 scripts/check-pdf-freshness.py --master assets/snowflake_pricing_master.json
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

_THIS_DIR = pathlib.Path(__file__).resolve().parent
_PLUGIN_ROOT = _THIS_DIR.parent
_DEFAULT_MASTER = _PLUGIN_ROOT / "assets" / "snowflake_pricing_master.json"

DEFAULT_PDF_URL = "https://www.snowflake.com/legal-files/CreditConsumptionTable.pdf"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
# The page-1 header reads e.g. "Effective: May 29, 2026". Anchor on the colon so
# we never catch the lowercase "effective size" prose later on the page.
_EFFECTIVE_RE = re.compile(r"Effective:\s*([A-Z][a-z]+\s+\d{1,2},?\s*\d{4})")
_DATE_FORMATS = ("%B %d, %Y", "%B %d %Y")


def parse_effective_date(text: str) -> _dt.date | None:
    """Extract the ``Effective: <Month DD, YYYY>`` date from PDF page-1 text."""
    m = _EFFECTIVE_RE.search(text or "")
    if not m:
        return None
    raw = re.sub(r"\s+", " ", m.group(1)).strip()
    for fmt in _DATE_FORMATS:
        try:
            return _dt.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def load_master_effective_date(master_path: pathlib.Path) -> _dt.date | None:
    """Read ``metadata.effective_date`` (ISO ``YYYY-MM-DD``) from the master."""
    meta = json.loads(master_path.read_text(encoding="utf-8")).get("metadata") or {}
    raw = meta.get("effective_date")
    if not raw:
        return None
    try:
        return _dt.date.fromisoformat(str(raw).strip())
    except ValueError:
        return None


def freshness_exit_code(master_date: _dt.date, pdf_date: _dt.date) -> int:
    """0 when the master is current (>= PDF), 1 when the PDF is newer (stale)."""
    return 1 if pdf_date > master_date else 0


def _download_pdf(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed host)
        return resp.read()


def pdf_page1_text(pdf_bytes: bytes) -> str | None:
    """Run pdftotext over page 1 of ``pdf_bytes``. None if pdftotext is missing."""
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as fh:
        fh.write(pdf_bytes)
        fh.flush()
        proc = subprocess.run(
            [exe, "-f", "1", "-l", "1", fh.name, "-"],
            capture_output=True, text=True,
        )
    return proc.stdout if proc.returncode == 0 else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdf-url", default=DEFAULT_PDF_URL, help="PDF URL to check.")
    ap.add_argument("--pdf", default=None, help="Use a local PDF file instead of downloading.")
    ap.add_argument("--master", default=str(_DEFAULT_MASTER), help="Path to the pricing master JSON.")
    ap.add_argument("--timeout", type=float, default=25.0, help="Download timeout in seconds.")
    args = ap.parse_args(argv)

    master_path = pathlib.Path(args.master)
    master_date = load_master_effective_date(master_path)
    if master_date is None:
        sys.stderr.write(f"check-pdf-freshness: no metadata.effective_date in {master_path}\n")
        return 2

    # Obtain page-1 text (local file or download).
    try:
        if args.pdf:
            pdf_bytes = pathlib.Path(args.pdf).read_bytes()
        else:
            pdf_bytes = _download_pdf(args.pdf_url, timeout=args.timeout)
    except Exception as exc:  # noqa: BLE001 — detection is best-effort
        sys.stderr.write(f"check-pdf-freshness: could not obtain PDF ({exc!r}); check skipped.\n")
        return 2

    text = pdf_page1_text(pdf_bytes)
    if text is None:
        sys.stderr.write(
            "check-pdf-freshness: pdftotext unavailable or failed; check skipped. "
            "Install poppler-utils (CI) / `brew install poppler` (macOS).\n"
        )
        return 2

    pdf_date = parse_effective_date(text)
    if pdf_date is None:
        sys.stderr.write("check-pdf-freshness: could not parse 'Effective:' date from page 1; check skipped.\n")
        return 2

    print(f"check-pdf-freshness: master={master_date.isoformat()}  pdf={pdf_date.isoformat()}  ({args.pdf_url})")
    if freshness_exit_code(master_date, pdf_date) == 1:
        days = (pdf_date - master_date).days
        print(
            f"  STALE  PDF is {days} day(s) NEWER than the master.\n"
            f"         Hand-update {master_path.name} (metadata.effective_date,\n"
            f"         ai_features token rates, serverless, etc.) from the new PDF,\n"
            f"         then re-run. (This script never edits the master.)"
        )
        return 1
    print("  OK  master is up to date with the legal PDF.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
