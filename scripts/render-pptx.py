#!/usr/bin/env python3
"""Render a Snowflake-branded PPTX from a SIZING_SPEC JSON.

Mirrors scripts/render-html.py in structure and exit codes.

Usage:
    python3 scripts/render-pptx.py --spec sizings/<slug>.json
    python3 scripts/render-pptx.py --spec sizings/<slug>.json --out /tmp/out.pptx
    python3 scripts/render-pptx.py --spec sizings/<slug>.json \
        --pricing assets/snowflake_pricing_master.json

Output path (when --out is omitted) is derived from spec meta:
    sizings/<slug>-<N>year-sizing-v<version>-<date>.pptx

Exit codes:
    0  PPTX written successfully.
    1  Spec load / build error.
    2  Argument / IO error.
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import sys

_THIS_DIR = pathlib.Path(__file__).resolve().parent
_PLUGIN_ROOT = _THIS_DIR.parent
_DEFAULT_PRICING = _PLUGIN_ROOT / "assets" / "snowflake_pricing_master.json"

# Ensure renderer/ and framework/ are importable.
sys.path.insert(0, str(_PLUGIN_ROOT))
sys.path.insert(0, str(_PLUGIN_ROOT / "framework"))

from renderer.pptx.build_pptx import build  # noqa: E402


def _slugify(text: str) -> str:
    """Convert a customer name / string to a filesystem-safe slug."""
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def _derive_out_path(spec: dict, spec_path: pathlib.Path) -> pathlib.Path:
    """Derive a default output path from spec metadata."""
    meta = spec.get("meta", {}) or {}
    customer = _slugify(meta.get("customer") or spec_path.stem)
    years = int(meta.get("contract_years", 3) or 3)
    version = meta.get("spec_version") or meta.get("pdf_version") or "1"
    # Strip non-numeric prefix from version string.
    version_clean = re.sub(r"[^0-9.]", "", str(version)) or "1"
    date = datetime.date.today().isoformat()
    filename = f"{customer}-{years}year-sizing-v{version_clean}-{date}.pptx"
    return _PLUGIN_ROOT / "sizings" / filename


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--spec",    required=True, help="Path to sizing spec JSON.")
    parser.add_argument("--out",     default=None,  help="Output .pptx path (auto-derived if omitted).")
    parser.add_argument("--pricing", default=str(_DEFAULT_PRICING),
                        help="Path to snowflake_pricing_master.json.")
    args = parser.parse_args()

    spec_path    = pathlib.Path(args.spec)
    pricing_path = pathlib.Path(args.pricing)

    for p, label in [(spec_path, "spec"), (pricing_path, "pricing")]:
        if not p.is_file():
            sys.stderr.write(f"render-pptx: {label} not found at {p}\n")
            return 2

    try:
        spec    = json.loads(spec_path.read_text(encoding="utf-8"))
        pricing = json.loads(pricing_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        sys.stderr.write(f"render-pptx: failed to load JSON - {exc}\n")
        return 2

    out_path = pathlib.Path(args.out) if args.out else _derive_out_path(spec, spec_path)

    try:
        pptx_bytes = build(spec, pricing, out_path=out_path)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"render-pptx: build failed - {exc}\n")
        import traceback
        traceback.print_exc()
        return 1

    print(f"render-pptx: wrote {out_path}  ({len(pptx_bytes):,} bytes)")

    # Quick sanity: PPTX is a ZIP - check magic bytes.
    if pptx_bytes[:2] != b"PK":
        sys.stderr.write("render-pptx: WARNING - output does not start with PK (not a valid ZIP/PPTX)\n")
        return 1

    # Print headline numbers.
    from compute_totals import compute_core_totals  # noqa: E402
    from renderer.spec_invariants import strip_internal_pricing_data  # noqa: E402
    pricing_clean = strip_internal_pricing_data(pricing)
    ct = compute_core_totals(spec, pricing_clean)
    per_year = ct.get("core_year_total") or []
    per_year_str = ", ".join(f"${y:,.0f}" for y in per_year)
    print(f"  core TCV : ${ct.get('core_tcv', 0):,.0f}")
    print(f"  per-year : [{per_year_str}]")
    import io as _io
    import zipfile as _zip
    _n = len([n for n in _zip.ZipFile(_io.BytesIO(pptx_bytes)).namelist()
              if n.startswith("ppt/slides/slide") and n.endswith(".xml")])
    print(f"  slides   : {_n}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
