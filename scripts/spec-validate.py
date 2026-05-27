#!/usr/bin/env python3
"""Validate a SIZING_SPEC JSON file against the snowflake-sizing schema.

Catches the most common agent errors that produce a $0 HTML render:
  - Using 'warehouses' instead of 'workloads' as the top-level array key
  - Missing per-workload required fields (clusters_min, clusters_max, etc.)
  - Wrong AI field names (monthly_tokens_input vs monthly_input_tokens_M, etc.)
  - Wrong storage path (storage.raw_tb vs storage.standard.raw_tb_year1)
  - Wrong OpenFlow warehouse_size abbreviation (XS vs X-Small)

Field lists and enum sets are derived from framework/sizing_spec_schema.json
via _schema_loader.SCHEMA - a single source of truth shared with
hooks/validate-sizing-json.py. The human-readable error messages and the
footgun explanations are this script's value-add over a generic JSON Schema
validator.

Exit 0 if every checked file passes.
Exit 1 if any hard error is found, with locations printed.
Warnings are printed but do not change the exit code.

Usage:
    python3 spec-validate.py path1.json [path2.json ...]
"""
import json
import pathlib
import sys

# Allow `python3 scripts/spec-validate.py ...` from plugin root by inserting
# this file's directory onto sys.path so `_schema_loader` resolves.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _schema_loader import SCHEMA  # noqa: E402

# Optional top-level keys the validator wants to see (set enabled:false if unused).
KNOWN_OPTIONAL_TOP_LEVEL = [
    "openflow_oracle", "data_transfer", "privatelink",
]

# Subset of meta fields the validator surfaces as warnings (they are required
# by the schema, but the warning message highlights why each one matters for
# cost math). The full required_meta list comes from the schema.
META_FIELDS_FOR_COST_MATH = [
    "credit_rate", "ai_credit_rate", "contract_years", "annual_growth_rate",
]


def _dig(obj, *keys):
    """Return (value, True) if the key path exists, else (None, False)."""
    cur = obj
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return None, False
        cur = cur[k]
    return cur, True


def validate(path_str):
    errors = []
    warnings = []
    p = pathlib.Path(path_str)

    if not p.exists() or not p.is_file():
        errors.append(f"{path_str}: file not found")
        return errors, warnings

    try:
        text = p.read_text(encoding="utf-8")
        spec = json.loads(text)
    except json.JSONDecodeError as exc:
        errors.append(f"{path_str}: invalid JSON - {exc}")
        return errors, warnings
    except OSError as exc:
        errors.append(f"{path_str}: read error - {exc}")
        return errors, warnings

    # Hard checks - exit 1 on any failure ----------------------------------- #

    # 1. Top-level array must be 'workloads', not 'warehouses'
    if "warehouses" in spec:
        errors.append(
            f"{path_str}: top-level key 'warehouses' found - "
            "must be 'workloads'. The JS engine reads SIZING_SPEC.workloads; "
            "any other key renders as $0."
        )
    if "workloads" not in spec:
        errors.append(
            f"{path_str}: 'workloads' key missing - "
            "add a top-level 'workloads' array."
        )

    # 2. Per-workload required fields
    required_workload = SCHEMA.required_workload()
    valid_wh_sizes = SCHEMA.valid_wh_sizes()
    valid_sources = SCHEMA.valid_sources()
    valid_ramp_curves = SCHEMA.valid_ramp_curves()
    workloads = spec.get("workloads", [])
    if isinstance(workloads, list):
        for i, w in enumerate(workloads):
            label = w.get("label") or w.get("id") or f"workload[{i}]"
            for field in required_workload:
                if field not in w:
                    errors.append(
                        f"{path_str}: workload '{label}' missing required field '{field}'"
                    )
            size = w.get("size")
            if size and size not in valid_wh_sizes:
                errors.append(
                    f"{path_str}: workload '{label}' size '{size}' is not valid - "
                    f"must be one of: {', '.join(sorted(valid_wh_sizes))}"
                )
            source = w.get("source")
            if source and source not in valid_sources:
                errors.append(
                    f"{path_str}: workload '{label}' source '{source}' is not valid - "
                    f"must be one of: {', '.join(sorted(valid_sources))}"
                )
            wl_ramp = w.get("ramp_curve")
            # Validators tolerate 'manual' as a sixth ramp curve (Birdbox
            # flat-line signal); the schema enum covers the five named curves.
            if wl_ramp and wl_ramp != "manual" and wl_ramp not in valid_ramp_curves:
                errors.append(
                    f"{path_str}: workload '{label}' ramp_curve '{wl_ramp}' is not valid - "
                    f"must be one of: {', '.join(sorted(valid_ramp_curves))}, manual"
                )
            # Detect legacy avg_clusters usage
            if "avg_clusters" in w:
                errors.append(
                    f"{path_str}: workload '{label}' uses 'avg_clusters' - "
                    "replace with 'clusters_min' and 'clusters_max'"
                )

    # 3. Storage path
    if "storage" in spec:
        st = spec["storage"]
        if "raw_tb" in st and "standard" not in st:
            errors.append(
                f"{path_str}: storage.raw_tb found at top level - "
                "expected storage.standard.raw_tb_year1"
            )
        _, has_raw_tb_year1 = _dig(st, "standard", "raw_tb_year1")
        if not has_raw_tb_year1 and "standard" in st:
            errors.append(
                f"{path_str}: storage.standard exists but missing 'raw_tb_year1' key"
            )

    # 4. AI field names
    ai = spec.get("ai_cortex", {})

    # 4a. Template-required AI keys (presence check).
    # populateAIPanel() in proposal-template.html dereferences these without
    # optional chaining; missing any one throws a TypeError at boot and the
    # whole page silently renders as $0.
    if "ai_cortex" not in spec:
        errors.append(
            f"{path_str}: top-level 'ai_cortex' object is missing - "
            "required by populateAIPanel() in the HTML template. "
            "See framework/sizing_spec_schema.json properties.ai_cortex.required "
            "for the full list of required sub-keys (set enabled:false on each "
            "feature not in scope)."
        )
    else:
        for key in SCHEMA.required_ai_cortex():
            if key not in ai:
                errors.append(
                    f"{path_str}: ai_cortex.{key} is missing - required by "
                    "populateAIPanel() in the HTML template (it dereferences "
                    "the key without optional chaining; omission throws "
                    "TypeError and the page silently renders as $0). Set "
                    "'enabled: false' if the feature is not used. See "
                    "framework/sizing_spec_schema.json."
                )

        # 4b. cortex_functions sub-keys must all be present - populateAIPanel
        #     iterates them with no presence guard.
        if "cortex_functions" in ai:
            cf_obj = ai.get("cortex_functions") or {}
            if isinstance(cf_obj, dict):
                for fn in SCHEMA.required_cortex_functions():
                    if fn not in cf_obj:
                        errors.append(
                            f"{path_str}: ai_cortex.cortex_functions.{fn} is "
                            "missing - required by populateAIPanel() (the "
                            "renderer iterates all 6 ai_* SQL functions and "
                            "reads .enabled / .tokens_M_monthly without a "
                            "presence guard). Set 'enabled: false' if unused."
                        )

    # cortex_complete: wrong field name
    cc = ai.get("cortex_complete", {})
    if cc.get("enabled") and "monthly_tokens_input" in cc:
        errors.append(
            f"{path_str}: ai_cortex.cortex_complete uses 'monthly_tokens_input' - "
            "must be 'monthly_input_tokens_M' (value in millions)"
        )
    if cc.get("enabled") and "monthly_input_tokens_M" not in cc:
        errors.append(
            f"{path_str}: ai_cortex.cortex_complete enabled but missing "
            "'monthly_input_tokens_M'"
        )

    # cortex_search: wrong field name
    cs = ai.get("cortex_search", {})
    if cs.get("enabled") and "indexed_gb" in cs:
        errors.append(
            f"{path_str}: ai_cortex.cortex_search uses 'indexed_gb' - "
            "must be 'indexed_data_gb'"
        )

    # AI Extract: must be under cortex_functions, not top-level ai_cortex
    if "ai_extract" in ai:
        errors.append(
            f"{path_str}: 'ai_extract' found directly under ai_cortex - "
            "must be at ai_cortex.cortex_functions.ai_extract "
            "(the cortex_functions sub-object groups all AI_ SQL functions)"
        )
    cf = ai.get("cortex_functions", {})
    ae = cf.get("ai_extract", {})
    if ae.get("enabled") and "tokens_M_monthly" not in ae:
        errors.append(
            f"{path_str}: ai_cortex.cortex_functions.ai_extract enabled "
            "but missing 'tokens_M_monthly'"
        )

    # 5. Serverless: wrong compute field name
    sl = spec.get("serverless", {})
    if isinstance(sl, dict):
        for feat_key, feat_val in sl.items():
            if not isinstance(feat_val, dict):
                continue
            if feat_val.get("enabled") and "monthly_credits" in feat_val:
                errors.append(
                    f"{path_str}: serverless.{feat_key} uses 'monthly_credits' - "
                    "must be 'compute_hours_monthly'"
                )

    # 6. OpenFlow warehouse_size abbreviations
    # "Wrong" = abbreviated form that isn't a valid full name. Computed from
    # the schema enums rather than hard-coded.
    wrong_of_wh_sizes = SCHEMA.valid_wh_sizes() - SCHEMA.valid_wh_sizes_full()
    of = spec.get("openflow", {})
    for inst in of.get("instances", []):
        wh_size = inst.get("warehouse_size")
        if wh_size in wrong_of_wh_sizes:
            errors.append(
                f"{path_str}: openflow instance '{inst.get('id', '?')}' "
                f"warehouse_size='{wh_size}' - use full name e.g. 'X-Small', "
                "'Small', 'Medium' (the JS billing lookup uses the full string)"
            )

    # Warnings - printed but do not change exit code ------------------------ #

    meta = spec.get("meta", {})
    for field in META_FIELDS_FOR_COST_MATH:
        if field not in meta:
            warnings.append(
                f"{path_str}: meta.{field} missing - required for cost calculation"
            )

    if isinstance(workloads, list) and len(workloads) == 0:
        warnings.append(
            f"{path_str}: workloads array is empty - TCV will render as $0"
        )

    for key in KNOWN_OPTIONAL_TOP_LEVEL:
        if key not in spec:
            warnings.append(
                f"{path_str}: top-level key '{key}' missing (set enabled:false if not used)"
            )

    return errors, warnings


def main():
    args = sys.argv[1:]
    if not args:
        print("usage: spec-validate.py path1.json [path2.json ...]", file=sys.stderr)
        sys.exit(2)

    all_errors = []
    all_warnings = []
    checked = 0
    for path in args:
        errs, warns = validate(path)
        all_errors.extend(errs)
        all_warnings.extend(warns)
        checked += 1

    if all_warnings:
        print("spec-validate: WARNINGS")
        for w in all_warnings:
            print("  [warn]", w)

    if all_errors:
        print("spec-validate: FAILED")
        for e in all_errors:
            print(" ", e)
        print(f"  ({len(all_errors)} error(s) across {checked} file(s))")
        sys.exit(1)

    if not all_warnings:
        print(f"spec-validate: OK ({checked} file(s), 0 errors)")
    else:
        print(f"spec-validate: OK with warnings ({checked} file(s), 0 hard errors)")


if __name__ == "__main__":
    main()
