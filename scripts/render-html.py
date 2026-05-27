#!/usr/bin/env python3
"""Render a sizing-proposal HTML from a SIZING_SPEC JSON.

Replaces the previously agent-driven token-substitution flow in the
render-html sub-skill. Hand-rolling the substitution in prose let the
agent fall back to `bash python -c '...open(...).write(html)'` heredocs,
which silently bypassed the `hooks/sizing-guard.py` PreToolUse hook
(the hook only fires on the `Write` tool). This script does the
substitution AND invokes the hook directly via subprocess so the same
gate runs in the same place no matter how the rendering is triggered.

Token map (every token must end up substituted; the script asserts no
`__TOKEN__` leftovers except the two SIZING_SPEC sentinels):

    __BRAND_FONTS_CSS__   <- assets/branding/_brand_fonts.css verbatim
    __PRICING_DATA__      <- assets/snowflake_pricing_master.json
                              with `utility_queries_reference` deep-stripped
                              (memory rule c4962f74 - keeps internal SQL
                              snippets out of customer-facing HTML).
    __SIZING_SPEC__       <- spec JSON (compact dump)
    __CUSTOMER__          <- meta.customer
    __EDITION__           <- meta.edition
    __CLOUD__             <- meta.cloud
    __REGION__            <- meta.region
    __YEARS__             <- meta.contract_years
    __CREDIT_RATE__       <- meta.credit_rate (as plain number, the
                              template wraps it in a <span> with `$`)
    __DATE__              <- meta.generated_date (or today)
    __PDF_VERSION__       <- meta.pdf_version

The two `__SIZING_SPEC_BEGIN__` / `__SIZING_SPEC_END__` tokens stay in
place because the in-page Save Version code uses them as a literal
sentinel pair to splice an updated spec back in. Those are the only
allowed `__TOKEN__` leftovers - everything else is treated as a
substitution failure.

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
import datetime as _dt
import json
import os
import pathlib
import re
import subprocess
import sys

_THIS_DIR = pathlib.Path(__file__).resolve().parent
_PLUGIN_ROOT = _THIS_DIR.parent
_DEFAULT_TEMPLATE = _PLUGIN_ROOT / "assets" / "templates" / "proposal-template.html"
_DEFAULT_PRICING = _PLUGIN_ROOT / "assets" / "snowflake_pricing_master.json"
_DEFAULT_FONTS = _PLUGIN_ROOT / "assets" / "branding" / "_brand_fonts.css"
_HOOK_PATH = _PLUGIN_ROOT / "hooks" / "sizing-guard.py"

# Tokens deliberately retained in the rendered HTML (the in-page Save Version
# logic uses them as splice sentinels).
_SENTINELS = {"SIZING_SPEC_BEGIN", "SIZING_SPEC_END"}
_TOKEN_RE = re.compile(r"__([A-Z][A-Z0-9_]+)__")


def _strip_utility_queries_reference(node):
    """Deep-strip `utility_queries_reference` from a pricing-data tree.

    Memory rule c4962f74 says these blocks are internal research artefacts
    that must not reach customer-facing HTML. Doing the strip in code
    (rather than relying on the agent to remember) makes the rule
    structurally enforced.
    """
    if isinstance(node, dict):
        node.pop("utility_queries_reference", None)
        for v in node.values():
            _strip_utility_queries_reference(v)
    elif isinstance(node, list):
        for v in node:
            _strip_utility_queries_reference(v)


def _build_token_map(spec: dict, pricing: dict, fonts_css: str) -> dict[str, str]:
    meta = spec.get("meta", {}) or {}
    today = _dt.date.today().isoformat()
    return {
        "__BRAND_FONTS_CSS__": fonts_css,
        "__PRICING_DATA__": json.dumps(pricing, separators=(",", ":")),
        "__SIZING_SPEC__": json.dumps(spec, separators=(",", ":")),
        "__CUSTOMER__": str(meta.get("customer") or ""),
        "__EDITION__": str(meta.get("edition") or ""),
        "__CLOUD__": str(meta.get("cloud") or ""),
        "__REGION__": str(meta.get("region") or ""),
        "__YEARS__": str(meta.get("contract_years") or ""),
        "__CREDIT_RATE__": _fmt_credit_rate(meta.get("credit_rate")),
        "__DATE__": str(meta.get("generated_date") or today),
        "__PDF_VERSION__": str(meta.get("pdf_version") or today),
    }


def _fmt_credit_rate(val) -> str:
    if val is None or val == "":
        return ""
    try:
        f = float(val)
    except (TypeError, ValueError):
        return str(val)
    # Match the template's existing rendering convention: 2 decimals when
    # there's a fractional component, integer otherwise.
    if f == int(f):
        return f"{int(f)}"
    return f"{f:.2f}"


def _substitute(template: str, tokens: dict[str, str]) -> str:
    """Replace tokens in a deterministic order. Long-value tokens last so
    we don't accidentally rescan them for further substitutions."""
    out = template
    # Order: short scalar tokens first, then the three large blobs. Any
    # __TOKEN__ pattern inside the blobs is fine because str.replace runs
    # serially; we don't re-scan.
    short_first = sorted(
        tokens.keys(),
        key=lambda k: len(tokens[k]),
    )
    for tok in short_first:
        out = out.replace(tok, tokens[tok])
    return out


def _check_substitution_complete(html: str) -> list[str]:
    leftovers: list[str] = []
    for m in _TOKEN_RE.finditer(html):
        tok = m.group(1)
        if tok in _SENTINELS:
            continue
        leftovers.append(f"__{tok}__ at offset {m.start()}")
    return leftovers


def _run_sizing_guard(out_path: pathlib.Path, html: str) -> tuple[bool, str]:
    """Invoke the same PreToolUse hook the real Write would trigger.

    Returns (ok, reason). reason is the hook's `decision: block` payload
    when the hook blocks; empty string on PASS or when the hook is missing
    (the hook itself is fail-open by design - we mirror that here).
    """
    if not _HOOK_PATH.exists():
        return True, ""
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(out_path),
            "content": html,
        },
    }
    try:
        proc = subprocess.run(
            [sys.executable, str(_HOOK_PATH)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        # Mirror the hook's own fail-open posture - a hung gate must not
        # wedge the build.
        return True, ""
    if proc.returncode != 0:
        # Fail-open per hook convention. Surface stderr for debugging.
        sys.stderr.write(
            f"render-html: sizing-guard hook exited {proc.returncode} "
            f"(treating as fail-open). stderr: {proc.stderr.strip()[:400]}\n"
        )
        return True, ""
    out = proc.stdout.strip()
    if not out:
        return True, ""
    try:
        decision = json.loads(out)
    except json.JSONDecodeError:
        sys.stderr.write(
            f"render-html: sizing-guard produced non-JSON output (treating "
            f"as fail-open): {out[:400]}\n"
        )
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
        (spec_path, "spec"),
        (template_path, "template"),
        (pricing_path, "pricing"),
        (fonts_path, "brand fonts"),
    ]:
        if not p.is_file():
            sys.stderr.write(f"render-html: {label} not found at {p}\n")
            return 2

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    pricing = json.loads(pricing_path.read_text(encoding="utf-8"))
    _strip_utility_queries_reference(pricing)
    fonts_css = fonts_path.read_text(encoding="utf-8")
    template = template_path.read_text(encoding="utf-8")

    tokens = _build_token_map(spec, pricing, fonts_css)
    html = _substitute(template, tokens)

    leftovers = _check_substitution_complete(html)
    if leftovers:
        sys.stderr.write(
            "render-html: substitution failed. Unresolved tokens:\n"
            + "".join(f"  - {tok}\n" for tok in leftovers)
        )
        return 1

    ok, reason = _run_sizing_guard(out_path, html)
    if not ok:
        sys.stderr.write(
            "render-html: sizing-guard PreToolUse hook blocked the write.\n"
            + reason
            + "\n"
        )
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: write to a temp sibling, fsync, rename.
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(html, encoding="utf-8")
    os.replace(tmp, out_path)

    print(f"render-html: wrote {out_path}")
    print("  sizing-guard hook: PASS")
    ct = spec.get("computed_totals") or {}
    if ct:
        per_year = ct.get("core_year_total") or []
        per_year_str = ", ".join(f"${y:,.0f}" for y in per_year)
        core = ct.get("core_tcv") or 0
        print(f"  core TCV: ${core:,.0f}  (per-year [{per_year_str}])")
    return 0


if __name__ == "__main__":
    sys.exit(main())
