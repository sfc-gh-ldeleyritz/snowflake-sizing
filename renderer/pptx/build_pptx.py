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
  4. Builds a 10.0" x 5.625" Presentation with 8 slides (6 if both the safe
     harbor and agenda are disabled) by duplicating pre-baked designer "donor"
     slides and injecting content into them (clone.py + inject.py).  Donors are
     located by bake-order index (clone.donors_by_order), not by sample text.
  5. Returns raw PPTX bytes (and writes to out_path if provided).

Slide order:
  1.  Title
  2.  Safe Harbor              (skip with meta.include_safe_harbor = false)
  3.  Agenda                   (skip with meta.include_agenda = false)
  4.  Cost detail by year (styled table)
  5.  Year-by-year costs (native chart)
  6.  Workloads detail table
  7.  Serverless / AI by year (styled table)
  8.  Closer / thank-you       (assumptions, open items + next steps in notes)
"""
from __future__ import annotations

import copy
import io
import pathlib
import sys

from pptx import Presentation

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

from . import brand, clone
from .slides import (  # noqa: E402
    build_title_slide,
    build_safe_harbor_slide,
    build_agenda_slide,
    build_cost_detail_slide,
    build_year_chart_slide,
    build_workloads_slide,
    build_serverless_ai_slide,
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

def _load_base_presentation():
    """Open the committed base template containing the baked donor slides.

    Requires the sizing base (8 designer donors baked in BAKED_DONOR_ORDER by
    scripts/create-sizing-template.py); the donors are located by slide index, so
    the full master template is no longer a valid fallback.  Raises if the base is
    unavailable, since the clone-based builders require donor slides.
    """
    tpath = brand.BASE_TEMPLATE_PATH
    if tpath.is_file():
        return Presentation(str(tpath))
    raise FileNotFoundError(
        f"No sizing base PPTX template found at:\n  {tpath}\n"
        "Run scripts/create-sizing-template.py to generate the donor base."
    )


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

    # 4. Open the donor base template.
    prs = _load_base_presentation()

    # 5. Capture the donor slides by bake-order index BEFORE any duplication, and
    #    remember every pre-existing slide so they can be removed afterwards.
    donors = clone.donors_by_order(prs)
    donor_ids = {id(s._element) for s in prs.slides}

    meta = spec.get("meta", {}) or {}
    include_safe_harbor = meta.get("include_safe_harbor", True)
    include_agenda = meta.get("include_agenda", True)

    # 6. Build slides in order by duplicating donors + injecting content.
    build_title_slide(prs, donors["title"], spec, computed_totals)
    if include_safe_harbor:
        build_safe_harbor_slide(prs, donors["safe_harbor"], spec, computed_totals)
    if include_agenda:
        build_agenda_slide(prs, donors["agenda"], spec, computed_totals)
    build_cost_detail_slide(prs, donors["table_styled"], spec, computed_totals)
    build_year_chart_slide(prs, donors["content"], spec, computed_totals)
    build_workloads_slide(prs, donors["table_styled"], spec, computed_totals)
    build_serverless_ai_slide(prs, donors["table_styled"], spec, computed_totals)
    build_closer_slide(prs, donors["thank_you"], spec, computed_totals)

    # 7. Remove the original donor slides, leaving only the generated deck.
    clone.delete_slides(prs, lambda s: id(s._element) in donor_ids)

    # 8. Serialise to bytes.
    buf = io.BytesIO()
    prs.save(buf)
    pptx_bytes = buf.getvalue()

    # 9. Write to disk if requested.
    if out_path is not None:
        p = pathlib.Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(pptx_bytes)

    return pptx_bytes
