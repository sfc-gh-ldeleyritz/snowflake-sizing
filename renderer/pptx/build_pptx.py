"""build_pptx.py - Public entry point for the Snowflake sizing PPTX generator.

Public surface:
    build(spec, pricing) -> bytes
    build(spec, pricing, out_path=<path>) -> bytes  (also writes file)

The function:
  1. Strips internal pricing data (utility_queries_reference).
  2. Re-runs compute_core_totals() for authoritative numbers - does NOT trust
     spec['computed_totals'] which may be stale from an HTML edit.
  3. Sanitizes em-dashes (U+2014) and en-dashes (U+2013) in all string fields
     to ' - ' (mirrors sizing-guard hygiene).
  4. Builds a 13.333" x 7.5" widescreen Presentation with 7 slides.
  5. Returns raw PPTX bytes (and writes to out_path if provided).

Slide order:
  1. Title
  2. Exec summary / TCV
  3. Workloads detail table
  4. Year-by-year costs (native chart)
  5. Serverless / AI breakdown
  6. Assumptions
  7. Closer / thank-you
"""
from __future__ import annotations

import copy
import io
import pathlib
import sys

from pptx import Presentation
from pptx.util import Emu

# Ensure framework/ is importable when called from arbitrary CWDs.
_THIS_DIR = pathlib.Path(__file__).resolve().parent
_PLUGIN_ROOT = _THIS_DIR.parent.parent
_FRAMEWORK_DIR = str(_PLUGIN_ROOT / "framework")
if _FRAMEWORK_DIR not in sys.path:
    sys.path.insert(0, _FRAMEWORK_DIR)
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from compute_totals import compute_core_totals  # noqa: E402
from renderer.spec_invariants import strip_internal_pricing_data  # noqa: E402

from . import brand
from .slides import (  # noqa: E402
    build_title_slide,
    build_exec_summary_slide,
    build_workloads_slide,
    build_year_chart_slide,
    build_serverless_ai_slide,
    build_assumptions_slide,
    build_closer_slide,
)


# ── Em/en-dash sanitizer ─────────────────────────────────────────────────── #

_DASH_TABLE = str.maketrans({
    "\u2014": " - ",   # em-dash
    "\u2013": " - ",   # en-dash
    "\u2012": " - ",   # figure dash
    "\u2015": " - ",   # horizontal bar
})


def _sanitize_dashes(obj):
    """Recursively replace em/en-dashes in all string fields with ' - '.

    Operates on dicts, lists, and strings.  Other types are returned as-is.
    The input object is mutated (caller should pass a deep copy).
    """
    if isinstance(obj, str):
        return obj.translate(_DASH_TABLE)
    if isinstance(obj, dict):
        for k in list(obj.keys()):
            obj[k] = _sanitize_dashes(obj[k])
        return obj
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            obj[i] = _sanitize_dashes(v)
        return obj
    return obj


# ── PPTX builder ─────────────────────────────────────────────────────────── #

def build(
    spec: dict,
    pricing: dict,
    out_path: str | pathlib.Path | None = None,
) -> bytes:
    """Build a Snowflake-branded PPTX from *spec* and *pricing*.

    Args:
        spec:     Parsed SIZING_SPEC dict (from sizings/<slug>.json).
        pricing:  Parsed snowflake_pricing_master.json dict.
        out_path: Optional filesystem path to write the .pptx file.

    Returns:
        Raw PPTX bytes (valid ZIP / Office Open XML).
    """
    # 1. Strip internal pricing artefacts.
    pricing = strip_internal_pricing_data(pricing)

    # 2. Deep-copy spec and re-compute authoritative totals.
    spec = copy.deepcopy(spec)
    computed_totals = compute_core_totals(spec, pricing)
    spec["computed_totals"] = computed_totals

    # 3. Sanitize em/en-dashes throughout.
    spec = _sanitize_dashes(spec)

    # 4. Create presentation with widescreen dimensions.
    prs = Presentation()
    prs.slide_width  = brand.SLIDE_W   # 13.333"
    prs.slide_height = brand.SLIDE_H   # 7.5"

    # 5. Build slides.
    build_title_slide(prs, spec, computed_totals)
    build_exec_summary_slide(prs, spec, computed_totals)
    build_workloads_slide(prs, spec, computed_totals)
    build_year_chart_slide(prs, spec, computed_totals)
    build_serverless_ai_slide(prs, spec, computed_totals)
    build_assumptions_slide(prs, spec, computed_totals)
    build_closer_slide(prs, spec, computed_totals)

    # 6. Serialise to bytes.
    buf = io.BytesIO()
    prs.save(buf)
    pptx_bytes = buf.getvalue()

    # 7. Write to disk if requested.
    if out_path is not None:
        p = pathlib.Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(pptx_bytes)

    return pptx_bytes
