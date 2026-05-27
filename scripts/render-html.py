#!/usr/bin/env python3
"""Render a sizing-proposal HTML from a SIZING_SPEC JSON.

Thin CLI wrapper around renderer.compiler.compile_spec(). All pipeline logic
(spec validation, compute_totals, token substitution) lives in renderer/.

Usage:
    python3 scripts/render-html.py --spec sizings/<slug>.json \
                                    --out  sizings/<slug>.html
    # Optional overrides; sane defaults are derived from the plugin layout.
    python3 scripts/render-html.py --spec ... --out ... \
        --template assets/templates/proposal-template.html \
        --pricing  assets/snowflake_pricing_master.json \
        --brand-fonts assets/branding/_brand_fonts.css

Exit codes:
    0  HTML written, sizing-guard hook PASS.
    1  Validation, substitution, or hook block - file NOT written.
    2  Argument / IO error.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

_THIS_DIR = pathlib.Path(__file__).resolve().parent
_PLUGIN_ROOT = _THIS_DIR.parent
_DEFAULT_TEMPLATE = _PLUGIN_ROOT / "assets" / "templates" / "proposal-template.html"
_DEFAULT_PRICING = _PLUGIN_ROOT / "assets" / "snowflake_pricing_master.json"
_DEFAULT_FONTS = _PLUGIN_ROOT / "assets" / "branding" / "_brand_fonts.css"
_HOOK_PATH = _PLUGIN_ROOT / "hooks" / "sizing-guard.py"

# Ensure renderer/ is importable.
sys.path.insert(0, str(_PLUGIN_ROOT))
from renderer import compile_spec  # noqa: E402
from renderer.spec_invariants import SpecValidationError  # noqa: E402


def _run_sizing_guard(out_path: pathlib.Path, html: str) -> tuple[bool, str]:
    """Invoke the PreToolUse hook that Write would trigger.

    Returns (ok, reason). Fail-open: a hung or absent hook never blocks the write.
    """
    if not _HOOK_PATH.exists():
        return True, ""
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(out_path), "content": html}}
    try:
        proc = subprocess.run(
            [sys.executable, str(_HOOK_PATH)],
            input=json.dumps(payload),
            capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        return True, ""
    if proc.returncode != 0:
        sys.stderr.write(
            f"render-html: sizing-guard hook exited {proc.returncode} "
            f"(fail-open). stderr: {proc.stderr.strip()[:400]}\n"
        )
        return True, ""
    out = proc.stdout.strip()
    if not out:
        return True, ""
    try:
        decision = json.loads(out)
    except json.JSONDecodeError:
        sys.stderr.write(f"render-html: sizing-guard non-JSON (fail-open): {out[:400]}\n")
        return True, ""
    if decision.get("decision") == "block":
        return False, decision.get("reason") or "sizing-guard blocked the write"
    return True, ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--spec", required=True, help="Path to sizing spec JSON.")
    parser.add_argument("--out", required=True, help="Path to write the rendered HTML.")
    parser.add_argument("--template", default=str(_DEFAULT_TEMPLATE))
    parser.add_argument("--pricing", default=str(_DEFAULT_PRICING))
    parser.add_argument("--brand-fonts", default=str(_DEFAULT_FONTS))
    args = parser.parse_args()

    spec_path = pathlib.Path(args.spec)
    out_path = pathlib.Path(args.out)
    template_path = pathlib.Path(args.template)
    pricing_path = pathlib.Path(args.pricing)
    fonts_path = pathlib.Path(args.brand_fonts)

    for p, label in [
        (spec_path, "spec"), (template_path, "template"),
        (pricing_path, "pricing"), (fonts_path, "brand fonts"),
    ]:
        if not p.is_file():
            sys.stderr.write(f"render-html: {label} not found at {p}\n")
            return 2

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    pricing = json.loads(pricing_path.read_text(encoding="utf-8"))
    template = template_path.read_text(encoding="utf-8")
    fonts_css = fonts_path.read_text(encoding="utf-8")

    try:
        result = compile_spec(spec, pricing, template, fonts_css)
    except SpecValidationError as exc:
        sys.stderr.write("render-html: spec validation failed.\n")
        for err in exc.errors:
            sys.stderr.write(f"  - {err}\n")
        return 1
    except ValueError as exc:
        sys.stderr.write(f"render-html: {exc}\n")
        return 1

    ok, reason = _run_sizing_guard(out_path, result.html)
    if not ok:
        sys.stderr.write(f"render-html: sizing-guard blocked the write.\n{reason}\n")
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(result.html, encoding="utf-8")
    os.replace(tmp, out_path)

    print(f"render-html: wrote {out_path}")
    print("  sizing-guard hook: PASS")
    ct = result.computed_totals
    if ct:
        per_year = ct.get("core_year_total") or []
        per_year_str = ", ".join(f"${y:,.0f}" for y in per_year)
        core = ct.get("core_tcv") or 0
        print(f"  core TCV: ${core:,.0f}  (per-year [{per_year_str}])")
    return 0


if __name__ == "__main__":
    sys.exit(main())
