#!/usr/bin/env python3
"""Consolidated PreToolUse hook for snowflake-sizing.

Replaces three previously separate post-write hooks/gate-scripts:
  - hooks/validate-sizing-json.py    (PostToolUse: spec validation)
  - hooks/content-hygiene.py         (PostToolUse: forbidden-token scan)
  - scripts/emdash-check.py          (manual gate)
  - scripts/html-render-check.py     (manual gate, kept for verbose runs)
  - scripts/content-hygiene-check.py (manual gate)

Firing pre-write means the agent sees the error before the file lands on
disk - the retry loop is one Write attempt instead of write-validate-edit-rewrite.

Scope (paths matched, by glob over the absolute path):
  - sizings/*.json   -> schema validate, legacy-field rename suggestions,
                        leakage-field rejection.
  - sizings/*.html   -> substitution completeness, em-dash, content hygiene,
                        DOM render check via Node sidecar (skipped if
                        SNOWFLAKE_SIZING_SKIP_NODE=1 in env).
  - temp/*-evidence*.md -> em-dash check only (the previous-session bug had
                        em-dashes leak through evidence files into customer
                        text via copy-paste during build-spec).

Decision protocol (CoCo PreToolUse hook):
  - exit 0 with no output                           -> approved
  - print {"decision": "block", "reason": "..."}    -> agent retries
  - exit non-zero (any other reason)                -> approved (fail-open
                                                       so a hook bug never
                                                       wedges the session)
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

_PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PLUGIN_ROOT / "scripts"))
sys.path.insert(0, str(_PLUGIN_ROOT / "framework"))

# spec-prepare is the single source of truth for validation logic and the
# legacy-field-name table. Importing it keeps the hook in lockstep so the
# agent never sees one set of error messages from spec-prepare and a
# different set from the hook.
import importlib.util
_SP_PATH = _PLUGIN_ROOT / "scripts" / "spec-prepare.py"
_spec_module_spec = importlib.util.spec_from_file_location("spec_prepare", _SP_PATH)
spec_prepare = importlib.util.module_from_spec(_spec_module_spec)
_spec_module_spec.loader.exec_module(spec_prepare)


EM_DASH = chr(0x2014)

# ── Currency enforcement (USD only, never convert) ────────────────────────── #
# Sizings are always quoted in USD. We block (a) non-USD currency symbols, which
# only appear when a figure has been converted/quoted in another currency, (b)
# explicit conversion phrasing, and (c) a non-USD ISO code sitting next to a
# number (e.g. "GBP 450,000", "450k EUR"). A bare currency name with no adjacent
# figure is NOT blocked, so an SE can still record "customer requires GBP billing"
# as a confirm_required item - in USD - without tripping the gate.
_NON_USD_SYMBOLS = ("\u00a3", "\u20ac", "\u00a5")  # £ € ¥
_CONVERSION_PHRASES = (
    "convert to", "converted at", "converted to", "conversion rate",
    "exchange rate", "fx rate", "indicative @", "indicative rate",
)
_NON_USD_CODES = "GBP|EUR|JPY|AUD|CAD|CHF|INR|SGD|CNY|HKD|NZD|SEK|NOK|DKK|ZAR|BRL|MXN|AED"
# A non-USD ISO code immediately before or after a number = a figure in that currency.
# The numeric side must contain a real digit (so a sentence-ending "GBP." does not match).
_NON_USD_AMOUNT_RE = re.compile(
    rf"(?:\b(?:{_NON_USD_CODES})\b\s*[\$£€¥]?\s*\d[\d.,]*)"
    rf"|(?:\d[\d.,]*\s*[kKmMbB]?\s*\b(?:{_NON_USD_CODES})\b)"
)
_USD_GUIDANCE = (
    "All figures must be in USD - never convert currency. Quote in USD and, if the "
    "customer requires another billing currency, record that as a confirm_required "
    "item (e.g. \"Confirm GBP billing currency with deal desk\") rather than "
    "converting any figure."
)


def _currency_findings(content: str) -> list[str]:
    out: list[str] = []
    for sym in _NON_USD_SYMBOLS:
        if sym in content:
            out.append(
                f"Non-USD currency symbol '{sym}' at line {_line_of(content, sym)}. {_USD_GUIDANCE}"
            )
    low = content.lower()
    for phrase in _CONVERSION_PHRASES:
        if phrase in low:
            out.append(
                f"Currency-conversion phrase '{phrase}' present. {_USD_GUIDANCE}"
            )
    m = _NON_USD_AMOUNT_RE.search(content)
    if m:
        line = content.count("\n", 0, m.start()) + 1
        out.append(
            f"Non-USD monetary figure '{m.group(0).strip()}' at line {line}. {_USD_GUIDANCE}"
        )
    return out


# Forbidden tokens in customer-facing HTML (mirrors scripts/content-hygiene-check.py).
# Citation prefixes are allowed in JSON `source` metadata; they're scanned only in HTML.
_HYGIENE_TOKENS_HTML = (
    "SOURCED:", "ASSUMPTION:", "REQUIRES_CONFIRMATION:",
    "sizing-methodology.md", "customer-context.md",
    "research-evidence.md", "html-spec.md", "research-protocol.md",
)

# Substitution leftovers (template tokens that should have been replaced).
_TOKEN_LEFTOVER_RE = re.compile(r"__([A-Z][A-Z0-9_]+)__")
# Tokens deliberately left in the rendered HTML (e.g. SIZING_SPEC begin/end markers).
_TOKEN_ALLOWLIST = {"SIZING_SPEC_BEGIN", "SIZING_SPEC_END"}


# ── Path classification ───────────────────────────────────────────────────── #

def _path_kind(path: str) -> str:
    """Return 'sizing-json', 'sizing-html', 'evidence-md', or 'other'."""
    if not path:
        return "other"
    p = path.replace("\\", "/")
    # Match both absolute (/.../sizings/foo.json) and relative
    # (sizings/foo.json) paths. The hook receives whatever the agent
    # passed to Write, which may be either.
    in_sizings = "/sizings/" in p or p.startswith("sizings/")
    in_temp = "/temp/" in p or p.startswith("temp/")
    if p.endswith(".json") and in_sizings:
        return "sizing-json"
    if p.endswith(".html") and in_sizings:
        return "sizing-html"
    if in_temp and re.search(r"-evidence(?:-[a-z]+)?\.md$", p):
        return "evidence-md"
    return "other"


# ── JSON path ─────────────────────────────────────────────────────────────── #

def _check_json(content: str, file_path: str) -> list[str]:
    errors: list[str] = []
    try:
        spec = json.loads(content)
    except json.JSONDecodeError as exc:
        return [f"Invalid JSON: {exc}"]

    # Legacy field detection (separate from validation so we can emit the
    # auto-fix command suggestion as the error message).
    legacy_hits = _scan_legacy_fields(spec)
    if legacy_hits:
        for hit in legacy_hits:
            errors.append(
                f"Legacy field '{hit['old']}' at {hit['path']} "
                f"(should be '{hit['new']}'). "
                f"Run scripts/spec-prepare.py --patch <patch.json> --out <spec.json> "
                "to auto-rename."
            )

    # Leakage fields: any of the known internal markers should never reach
    # a sizing JSON.
    leak_hits = _scan_leakage_fields(spec)
    for hit in leak_hits:
        errors.append(f"Internal-marker field '{hit}' must not appear in sizing JSON.")

    # Currency enforcement: no non-USD figures/conversions in narrative fields.
    errors.extend(_currency_findings(content))

    # Schema validation last (other diagnostics are more actionable).
    errors.extend(spec_prepare.validate_spec(spec))
    return errors


def _scan_legacy_fields(spec: dict) -> list[dict]:
    out = []
    # Reuse spec-prepare's table of renames.
    for path_prefix, old, new in spec_prepare._LEGACY_RENAMES:
        node = spec
        for p in path_prefix:
            node = node.get(p) if isinstance(node, dict) else None
            if not isinstance(node, dict):
                node = None
                break
        if isinstance(node, dict) and old in node:
            out.append({"path": ".".join(path_prefix) + "." + old, "old": old, "new": new})
    sl = spec.get("serverless")
    if isinstance(sl, dict):
        old, new = spec_prepare._SERVERLESS_FIELD_RENAME
        for feat_key, feat in sl.items():
            if isinstance(feat, dict) and old in feat:
                out.append({
                    "path": f"serverless.{feat_key}.{old}", "old": old, "new": new,
                })
    for i, w in enumerate(spec.get("workloads", []) or []):
        if isinstance(w, dict) and "avg_clusters" in w:
            label = w.get("id") or w.get("label") or f"workloads[{i}]"
            out.append({
                "path": f"workloads[{label}].avg_clusters",
                "old": "avg_clusters", "new": "clusters_min/clusters_max",
            })
    return out


def _scan_leakage_fields(spec: dict) -> list[str]:
    found: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            for k in node.keys():
                if k in spec_prepare._LEAKAGE_FIELD_NAMES:
                    found.add(k)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(spec)
    return sorted(found)


# ── HTML path ─────────────────────────────────────────────────────────────── #

def _check_html(content: str, file_path: str) -> list[str]:
    errors: list[str] = []

    # 1. Em-dash scan (cheap).
    errors.extend(_emdash_findings(content))

    # 1b. Currency enforcement (USD only).
    errors.extend(_currency_findings(content))

    # 2. Content-hygiene tokens.
    for tok in _HYGIENE_TOKENS_HTML:
        if tok in content:
            line = _line_of(content, tok)
            errors.append(
                f"Forbidden token '{tok}' present at line {line}. "
                "Citation prefixes / internal artefact filenames must not "
                "appear in customer-facing HTML."
            )

    # 3. Substitution leftovers.
    for m in _TOKEN_LEFTOVER_RE.finditer(content):
        tok = m.group(1)
        if tok in _TOKEN_ALLOWLIST:
            continue
        line = content.count("\n", 0, m.start()) + 1
        errors.append(
            f"Unsubstituted template token '__{tok}__' at line {line}. "
            "Either provide the substitution value in render-html step 3, or "
            "add the token to the allowlist in hooks/sizing-guard.py."
        )

    # 4. Node render check (most expensive). Skip on opt-out env var.
    if not os.environ.get("SNOWFLAKE_SIZING_SKIP_NODE"):
        node_err = _node_render_check(content)
        if node_err:
            errors.append(node_err)

    return errors


def _emdash_findings(content: str) -> list[str]:
    out = []
    if EM_DASH not in content:
        return out
    for lineno, line in enumerate(content.splitlines(), start=1):
        idx = line.find(EM_DASH)
        while idx != -1:
            out.append(f"Em-dash (U+2014) at line {lineno} col {idx + 1} - replace with ' - '.")
            idx = line.find(EM_DASH, idx + 1)
    return out


def _line_of(content: str, tok: str) -> int:
    idx = content.find(tok)
    return content.count("\n", 0, idx) + 1 if idx >= 0 else 0


def _node_render_check(content: str) -> str | None:
    sidecar = _PLUGIN_ROOT / "scripts" / "html-render-check.mjs"
    if not sidecar.exists():
        return None  # Sidecar missing - fail-open.
    try:
        node = subprocess.check_output(["which", "node"], text=True).strip()
    except subprocess.CalledProcessError:
        return None  # Node not on PATH - fail-open.
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        proc = subprocess.run(
            [node, str(sidecar), tmp_path],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode != 0:
            return (
                f"Node render gate failed (exit {proc.returncode}): "
                f"{(proc.stderr or '').strip()[:400]}"
            )
        try:
            res = json.loads(proc.stdout.strip())
        except json.JSONDecodeError:
            return f"Node render gate produced invalid JSON: {proc.stdout[:400]}"
        if not res.get("ok"):
            err = res.get("error") or "unknown JS render failure"
            return (
                f"JS render gate: {err} - the page will render as $0 in a "
                "real browser. Inspect the inline script with the embedded "
                "SIZING_SPEC: a missing key in ai_cortex / serverless / "
                "workloads usually causes a TypeError at boot."
            )
        kpi = res.get("kpi_tcv", "$0")
        if kpi in ("$0", "0", ""):
            return "JS render gate: kpi-tcv resolved to $0 - check credit_rate, workloads, ramp curve."
        return None
    except subprocess.TimeoutExpired:
        return "Node render gate timed out after 30s - skipping (fail-open)."
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ── Evidence-md path (em-dash only) ───────────────────────────────────────── #

def _check_evidence_md(content: str) -> list[str]:
    return _emdash_findings(content)


# ── Hook driver ───────────────────────────────────────────────────────────── #

def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if data.get("tool_name") != "Write":
        sys.exit(0)

    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    content = tool_input.get("content") or ""

    kind = _path_kind(file_path)
    if kind == "other":
        sys.exit(0)

    if kind == "sizing-json":
        errors = _check_json(content, file_path)
        label = "SIZING_SPEC validation"
    elif kind == "sizing-html":
        errors = _check_html(content, file_path)
        label = "Sizing HTML pre-write checks"
    else:  # evidence-md
        errors = _check_evidence_md(content)
        label = "Research evidence pre-write checks"

    if errors:
        reason = (
            f"BLOCKED: {label} failed for {file_path} ({len(errors)} issue(s)).\n\n"
            + "\n".join(f"  - {e}" for e in errors)
            + "\n\nFix the issues above and re-issue Write. "
            "spec-prepare.py auto-corrects most JSON issues; for HTML, regenerate "
            "from a corrected SIZING_SPEC."
        )
        print(json.dumps({"decision": "block", "reason": reason}))

    sys.exit(0)


if __name__ == "__main__":
    main()
