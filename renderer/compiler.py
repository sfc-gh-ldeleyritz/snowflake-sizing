"""compiler — single entry point from SIZING_SPEC JSON to rendered HTML.

Bundles the four pipeline stages:
  1. Strip internal fields from pricing data (spec_invariants)
  2. Validate spec (spec_invariants)
  3. Compute core totals; inject into spec (framework/compute_totals)
  4. Build token map + substitute into template (html_builder)

Public API:
    compile_spec(spec, pricing, template, fonts_css) -> CompileResult

The input spec is not mutated; a copy is made before computed_totals
are injected.
"""
from __future__ import annotations

import copy
import pathlib
import sys
from dataclasses import dataclass, field

_THIS_DIR = pathlib.Path(__file__).resolve().parent
_PLUGIN_ROOT = _THIS_DIR.parent

_FRAMEWORK_DIR = str(_PLUGIN_ROOT / "framework")
if _FRAMEWORK_DIR not in sys.path:
    sys.path.insert(0, _FRAMEWORK_DIR)

from compute_totals import compute_core_totals  # noqa: E402

from .spec_invariants import strip_internal_pricing_data, validate_spec  # noqa: E402
from .html_builder import build_token_map, check_substitution_complete, substitute_tokens  # noqa: E402


@dataclass
class CompileResult:
    """Outcome of compiling a SIZING_SPEC to an HTML proposal."""

    html: str
    spec: dict       # normalized spec with computed_totals injected
    computed_totals: dict = field(default_factory=dict)


def compile_spec(
    spec: dict,
    pricing: dict,
    template: str,
    fonts_css: str,
) -> CompileResult:
    """Render a SIZING_SPEC JSON to the HTML proposal template.

    Steps:
      1. Strip utility_queries_reference from pricing (keeps internal SQL out
         of customer-facing HTML per memory rule c4962f74).
      2. Validate spec. Raises SpecValidationError on schema/domain failures.
      3. Compute core totals via framework/compute_totals and inject them as
         spec['computed_totals'] so the in-page JS can read
         SIZING_SPEC.computed_totals directly (Python is authoritative).
      4. Build token map and substitute into template.
      5. Assert all tokens resolved (raises ValueError on any leftover).

    Args:
        spec:      Parsed SIZING_SPEC dict.
        pricing:   Parsed snowflake_pricing_master.json dict.
        template:  Raw HTML template string (proposal-template.html).
        fonts_css: Raw CSS string for brand fonts.

    Returns:
        CompileResult with the final HTML, the normalized spec, and the
        Python-computed totals.

    Raises:
        SpecValidationError: spec fails schema or domain validation.
        ValueError:          an unresolved __TOKEN__ pattern remains.
    """
    pricing = strip_internal_pricing_data(pricing)
    spec = copy.deepcopy(spec)
    validate_spec(spec)
    # Pricing rate check — warning only, never blocks rendering.
    from .pricing_validator import validate_pricing as _validate_pricing
    for w in _validate_pricing(spec, pricing):
        sys.stderr.write(w + "\n")
    totals = compute_core_totals(spec, pricing)
    spec["computed_totals"] = totals
    tokens = build_token_map(spec, pricing, fonts_css, totals)
    html = substitute_tokens(template, tokens)
    check_substitution_complete(html)
    return CompileResult(html=html, spec=spec, computed_totals=totals)
