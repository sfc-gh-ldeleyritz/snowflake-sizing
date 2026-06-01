#!/usr/bin/env python3
"""Render a sizing-proposal HTML from a SIZING_SPEC JSON.

Thin CLI wrapper around renderer.compiler.compile_spec(). All pipeline logic
(spec validation, compute_totals, token substitution) lives in renderer/.

Usage:
    python3 scripts/render-html.py --spec sizings/<slug>.json \
                                    --out  sizings/<slug>.html
    # Pricing precedence: --pricing PATH (explicit) > --latest/--repin (fresh
    # live fetch) > a pinned <slug>.pricing.json sidecar written by spec-prepare
    # (reproducible re-render) > live fetch with cache → seed → master fallback.
    # --offline skips the network; --repin refreshes the pin to fresh pricing.
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
_DEFAULT_FONTS = _PLUGIN_ROOT / "assets" / "branding" / "_brand_fonts.css"
_HOOK_PATH = _PLUGIN_ROOT / "hooks" / "sizing-guard.py"

# Ensure renderer/ and framework/ are importable.
sys.path.insert(0, str(_PLUGIN_ROOT))
sys.path.insert(0, str(_PLUGIN_ROOT / "framework"))
from renderer import compile_spec  # noqa: E402
from renderer.spec_invariants import SpecValidationError  # noqa: E402
from live_pricing import load_pricing, build_pricing_snapshot, pricing_sha256  # noqa: E402


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
    parser.add_argument(
        "--pricing", default=None,
        help="Explicit pricing JSON to use verbatim (deterministic; for tests / "
             "reproducing a past sizing). Default: live calculator fetch with "
             "cache → committed seed → static master fallback.",
    )
    parser.add_argument(
        "--offline", action="store_true",
        help="Skip the live calculator fetch; use the cache, then the committed "
             "seed, then the static master.",
    )
    parser.add_argument(
        "--latest", action="store_true",
        help="Ignore any pinned sidecar and render against fresh live pricing "
             "(one-off; does not change the pin).",
    )
    parser.add_argument(
        "--repin", action="store_true",
        help="Fetch fresh live pricing, render against it, and re-pin: rewrite the "
             "<slug>.pricing.json sidecar and the spec's pricing_snapshot.",
    )
    parser.add_argument("--brand-fonts", default=str(_DEFAULT_FONTS))
    args = parser.parse_args()

    spec_path = pathlib.Path(args.spec)
    out_path = pathlib.Path(args.out)
    template_path = pathlib.Path(args.template)
    fonts_path = pathlib.Path(args.brand_fonts)

    for p, label in [
        (spec_path, "spec"), (template_path, "template"),
        (fonts_path, "brand fonts"),
    ]:
        if not p.is_file():
            sys.stderr.write(f"render-html: {label} not found at {p}\n")
            return 2

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    template = template_path.read_text(encoding="utf-8")
    fonts_css = fonts_path.read_text(encoding="utf-8")

    # Pricing resolution (precedence): explicit --pricing > --latest/--repin fresh
    # fetch > pinned sidecar (reproducible) > live/seed fallback.
    sidecar = spec_path.parent / (spec_path.stem + ".pricing.json")
    snapshot = spec.get("pricing_snapshot") or {}
    want_fresh = args.latest or args.repin

    if args.pricing is not None:
        pricing_path = pathlib.Path(args.pricing)
        if not pricing_path.is_file():
            sys.stderr.write(f"render-html: pricing not found at {pricing_path}\n")
            return 2
        pricing = json.loads(pricing_path.read_text(encoding="utf-8"))
        print(f"render-html: pricing = explicit {pricing_path}")
    elif want_fresh:
        pricing = load_pricing(prefer_live=not args.offline, offline=args.offline)
        print(f"render-html: pricing = fresh fetch ({'--repin' if args.repin else '--latest'})")
    elif snapshot and sidecar.is_file():
        pricing = json.loads(sidecar.read_text(encoding="utf-8"))
        expected = snapshot.get("pricing_sha256")
        if expected and pricing_sha256(pricing) != expected:
            sys.stderr.write(
                f"render-html: WARNING pinned-pricing sha mismatch for {sidecar.name} "
                "(sidecar edited since spec-prepare); rendering with it anyway.\n"
            )
        print(
            f"render-html: pricing = pinned {sidecar.name} "
            f"(calc {snapshot.get('calc_fetched_at')}, master {snapshot.get('master_effective_date')})"
        )
    else:
        if snapshot and not sidecar.is_file():
            sys.stderr.write(
                f"render-html: spec has pricing_snapshot but sidecar {sidecar.name} is missing; "
                "loading live/seed pricing instead — numbers may differ from the original. "
                "Re-run with --repin to refresh the pin.\n"
            )
        pricing = load_pricing(prefer_live=not args.offline, offline=args.offline)

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

    # Re-pin: persist the freshly fetched pricing as the new sidecar + snapshot so
    # subsequent renders reproduce these numbers.
    if args.repin:
        new_snapshot = build_pricing_snapshot(pricing)
        new_snapshot["pinned_pricing_file"] = sidecar.name
        sidecar.write_text(json.dumps(pricing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        new_spec = result.spec
        new_spec["pricing_snapshot"] = new_snapshot
        spec_path.write_text(json.dumps(new_spec, indent=2) + "\n", encoding="utf-8")
        print(f"render-html: re-pinned pricing -> {sidecar.name} (sha {new_snapshot['pricing_sha256'][:12]})")

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
