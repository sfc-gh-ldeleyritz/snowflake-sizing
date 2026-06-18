"""spec_invariants — spec validation and pricing-data sanitization.

Public surface:
    strip_internal_pricing_data(pricing) -> dict   deep-copy, strips utility_queries_reference
    validate_spec(spec) -> None                    raises SpecValidationError on failure
    SpecValidationError                            ValueError subclass carrying error list
"""
from __future__ import annotations

import copy
import pathlib
import sys

_THIS_DIR = pathlib.Path(__file__).resolve().parent
_PLUGIN_ROOT = _THIS_DIR.parent

# _schema_loader lives in scripts/; add to sys.path once.
_SCRIPTS_DIR = str(_PLUGIN_ROOT / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


# ── Pricing sanitization ─────────────────────────────────────────────────── #

def strip_internal_pricing_data(pricing: dict) -> dict:
    """Return a deep copy of pricing with utility_queries_reference stripped.

    Memory rule c4962f74 — these blocks are internal research artefacts that
    must not reach customer-facing HTML.
    """
    out = copy.deepcopy(pricing)
    _strip_key_recursive(out, "utility_queries_reference")
    return out


def _strip_key_recursive(node, key: str) -> None:
    if isinstance(node, dict):
        node.pop(key, None)
        for v in node.values():
            _strip_key_recursive(v, key)
    elif isinstance(node, list):
        for v in node:
            _strip_key_recursive(v, key)


# ── Validation ───────────────────────────────────────────────────────────── #

class SpecValidationError(ValueError):
    """Raised by validate_spec when the spec fails one or more checks."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        summary = "; ".join(self.errors[:3])
        if len(self.errors) > 3:
            summary += f" (…and {len(self.errors) - 3} more)"
        super().__init__(f"{len(self.errors)} validation error(s): {summary}")


def validate_spec(spec: dict) -> None:
    """Validate spec for renderer correctness — fields needed for cost calculation.

    This is intentionally lighter than spec-prepare.py's validate_spec(). It only
    checks what the renderer and compute_totals.py actually need to produce correct
    output. It does NOT enforce display-only fields (auto_suspend_seconds, source,
    justification) or additionalProperties — real-world specs can have extra fields
    added in different schema versions.

    Raises SpecValidationError on failure. Does not mutate the spec.
    """
    from _schema_loader import SCHEMA  # in scripts/ (added to sys.path above)

    errors: list[str] = []

    if "warehouses" in spec:
        errors.append(
            "'warehouses' key found at top level — must be 'workloads' "
            "(JS renderer reads SIZING_SPEC.workloads; 'warehouses' renders as $0)"
        )

    for key in SCHEMA.required_top_level():
        if key not in spec:
            errors.append(f"Missing required top-level key '{key}'.")
    if errors:
        raise SpecValidationError(errors)

    meta = spec.get("meta", {}) or {}
    for field in SCHEMA.required_meta():
        if field not in meta:
            errors.append(f"meta.{field} is required.")
    if meta.get("edition") and meta["edition"] not in SCHEMA.valid_editions():
        errors.append(
            f"meta.edition '{meta['edition']}' invalid — must be one of "
            f"{', '.join(sorted(SCHEMA.valid_editions()))}."
        )
    if meta.get("cloud") and meta["cloud"] not in SCHEMA.valid_clouds():
        errors.append(
            f"meta.cloud '{meta['cloud']}' invalid — must be one of "
            f"{', '.join(sorted(SCHEMA.valid_clouds()))}."
        )

    workloads = spec.get("workloads", [])
    if not isinstance(workloads, list):
        errors.append("'workloads' must be an array.")
    elif not workloads:
        errors.append("'workloads' array is empty — TCV will render as $0")
    else:
        # Only check fields that affect cost calculation (not display-only fields).
        _CALC_FIELDS = ("id", "label", "size", "hours_per_day", "days_per_month",
                        "clusters_min", "clusters_max", "ramp_curve",
                        "dev_start_month", "go_live_month")
        for i, w in enumerate(workloads):
            label = w.get("label") or w.get("id") or f"workloads[{i}]"
            for f in _CALC_FIELDS:
                if f not in w:
                    errors.append(f"workload '{label}': missing field '{f}'.")
            if w.get("size") and w["size"] not in SCHEMA.valid_wh_sizes():
                errors.append(
                    f"workload '{label}': size '{w['size']}' invalid — "
                    f"must be one of {', '.join(sorted(SCHEMA.valid_wh_sizes()))}."
                )

    ai = spec.get("ai_cortex", {}) or {}
    for k in SCHEMA.required_ai_cortex():
        if k not in ai:
            errors.append(f"ai_cortex.{k} is missing.")

    if errors:
        raise SpecValidationError(errors)
