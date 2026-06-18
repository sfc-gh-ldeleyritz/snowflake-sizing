"""html_builder — token-map construction and template substitution.

Public surface:
    build_token_map(spec, pricing, fonts_css, computed_totals) -> dict[str, str]
    substitute_tokens(template, tokens) -> str
    check_substitution_complete(html) -> None   raises ValueError on unresolved tokens
    fmt_credit_rate(val) -> str
"""
from __future__ import annotations

import datetime as _dt
import json
import re

# Tokens deliberately retained in rendered HTML — the in-page Save Version
# logic uses them as splice sentinels.
_SENTINELS = frozenset({"SIZING_SPEC_BEGIN", "SIZING_SPEC_END"})
_TOKEN_RE = re.compile(r"__([A-Z][A-Z0-9_]+)__")


def fmt_credit_rate(val) -> str:
    """Format a credit rate number as a plain string (no $ prefix).

    Produces integer notation when the value is whole (3.0 → '3'),
    two-decimal otherwise (2.75 → '2.75').
    """
    if val is None or val == "":
        return ""
    try:
        f = float(val)
    except (TypeError, ValueError):
        return str(val)
    if f == int(f):
        return f"{int(f)}"
    return f"{f:.2f}"


def build_token_map(
    spec: dict,
    pricing: dict,
    fonts_css: str,
    computed_totals: dict,
) -> dict[str, str]:
    """Build the full substitution map for the proposal template.

    The spec passed in should already have ``computed_totals`` injected by the
    caller (compiler.py does this before calling build_token_map). It is
    serialised as-is into ``__SIZING_SPEC__`` so that the in-page JS can read
    ``SIZING_SPEC.computed_totals`` without any extra work.
    """
    meta = spec.get("meta", {}) or {}
    today = _dt.date.today().isoformat()
    return {
        "__BRAND_FONTS_CSS__": fonts_css,
        "__PRICING_DATA__": json.dumps(pricing, separators=(",", ":")),
        "__SIZING_SPEC__": json.dumps(spec, separators=(",", ":")),
        "__COMPUTED_TOTALS__": json.dumps(computed_totals, separators=(",", ":")),
        "__CUSTOMER__": str(meta.get("customer") or ""),
        "__EDITION__": str(meta.get("edition") or ""),
        "__CLOUD__": str(meta.get("cloud") or ""),
        "__REGION__": str(meta.get("region") or ""),
        "__YEARS__": str(meta.get("contract_years") or ""),
        "__CREDIT_RATE__": fmt_credit_rate(meta.get("credit_rate")),
        "__DATE__": str(meta.get("generated_date") or today),
        "__PDF_VERSION__": str(meta.get("pdf_version") or today),
    }


def substitute_tokens(template: str, tokens: dict[str, str]) -> str:
    """Replace all tokens in template. Short tokens first to avoid re-scanning.

    Large blobs (PRICING_DATA, SIZING_SPEC, etc.) are replaced last so we
    don't accidentally re-scan their contents for further substitutions.
    ``str.replace`` runs serially; no rescanning occurs.
    """
    out = template
    for tok in sorted(tokens, key=lambda k: len(tokens[k])):
        out = out.replace(tok, tokens[tok])
    return out


def check_substitution_complete(html: str) -> None:
    """Assert that no unresolved ``__TOKEN__`` patterns remain.

    Raises ``ValueError`` listing leftover tokens. The two SIZING_SPEC
    sentinel tokens are intentionally preserved and are exempted.
    """
    leftovers = [
        f"__{m.group(1)}__ at offset {m.start()}"
        for m in _TOKEN_RE.finditer(html)
        if m.group(1) not in _SENTINELS
    ]
    if leftovers:
        raise ValueError(
            "Unresolved tokens after substitution:\n"
            + "".join(f"  - {t}\n" for t in leftovers)
        )
