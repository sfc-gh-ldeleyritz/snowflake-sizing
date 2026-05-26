#!/usr/bin/env python3
"""
PostToolUse hook: validates SIZING_SPEC JSON files written to sizings/*.json.

Fires on Write tool calls. Skips Edit (partial content) and all non-sizing files.
Blocks on hard structural errors — the same class of mistakes that cause the
HTML renderer to produce a $0 proposal. Approves silently if all checks pass.

Decision protocol (CoCo PostToolUse hook):
  - {"decision": "block", "reason": "..."}  →  agent sees error, must fix and retry
  - (no output / exit 0)                    →  approved
"""

import json
import os
import sys

# ---------------------------------------------------------------------------
# Constants matching framework/sizing_spec_schema.json
# ---------------------------------------------------------------------------

REQUIRED_TOP_LEVEL = [
    "meta", "workloads", "serverless", "ai_cortex",
    "storage", "assumptions", "confirm_required",
]

REQUIRED_META = [
    "customer", "edition", "cloud", "region",
    "credit_rate", "ai_credit_rate",
    "storage_rate_per_tb", "hybrid_tables_storage_rate_per_gb",
    "contract_years", "generated_date",
    "default_ramp_curve", "annual_growth_rate",
]

REQUIRED_WORKLOAD = [
    "id", "label", "size",
    "hours_per_day", "days_per_month",
    "clusters_min", "clusters_max", "auto_suspend_seconds",
    "source", "ramp_curve",
    "dev_start_month", "go_live_month",
]

VALID_EDITIONS = {"Standard", "Enterprise", "Business Critical", "VPS"}
VALID_CLOUDS = {"AWS", "Azure", "GCP"}
VALID_WH_SIZES = {"XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL", "6XL"}
VALID_SOURCES = {"SOURCED", "ASSUMPTION", "ESTIMATED"}
VALID_RAMP_CURVES = {"fastest", "fast", "linear", "slow", "slowest"}

# OpenFlow instances require full names, not abbreviations
OPENFLOW_WH_FULL = {"X-Small", "Small", "Medium", "Large", "X-Large", "2X-Large", "3X-Large", "4X-Large"}
OPENFLOW_WH_ABBREVS = {"XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL"}


# ---------------------------------------------------------------------------
# File path filter
# ---------------------------------------------------------------------------

def is_sizing_json(path: str) -> bool:
    if not path or not path.lower().endswith(".json"):
        return False
    normalized = path.replace("\\", "/")
    # Match sizings/ anywhere in the path
    return "/sizings/" in normalized or os.path.basename(os.path.dirname(path)) == "sizings"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(spec: dict, file_path: str) -> list:
    errors = []

    # 1. Guard: top-level shape
    if "warehouses" in spec:
        errors.append(
            "'warehouses' key found at top level — must be 'workloads'. "
            "The JS renderer reads SIZING_SPEC.workloads; 'warehouses' silently renders as $0."
        )
    for key in REQUIRED_TOP_LEVEL:
        if key not in spec:
            errors.append(f"Missing required top-level key '{key}'.")

    if errors:
        # Can't safely validate sub-sections without the core keys
        return errors

    # 2. meta
    meta = spec.get("meta", {})
    for field in REQUIRED_META:
        if field not in meta:
            errors.append(f"meta.{field} is required.")

    edition = meta.get("edition")
    if edition and edition not in VALID_EDITIONS:
        errors.append(
            f"meta.edition '{edition}' is not valid — "
            f"must be one of: {', '.join(sorted(VALID_EDITIONS))}."
        )

    cloud = meta.get("cloud")
    if cloud and cloud not in VALID_CLOUDS:
        errors.append(
            f"meta.cloud '{cloud}' is not valid — "
            f"must be one of: {', '.join(sorted(VALID_CLOUDS))}."
        )

    ramp = meta.get("default_ramp_curve")
    if ramp and ramp not in VALID_RAMP_CURVES:
        errors.append(
            f"meta.default_ramp_curve '{ramp}' is not valid — "
            f"must be one of: {', '.join(sorted(VALID_RAMP_CURVES))}."
        )

    # 3. workloads
    workloads = spec.get("workloads", [])
    if not isinstance(workloads, list):
        errors.append("'workloads' must be an array.")
    else:
        if len(workloads) == 0:
            errors.append("'workloads' array is empty — TCV will render as $0.")
        for i, w in enumerate(workloads):
            label = w.get("label") or w.get("id") or f"workloads[{i}]"
            for field in REQUIRED_WORKLOAD:
                if field not in w:
                    errors.append(f"workload '{label}': missing required field '{field}'.")
            size = w.get("size")
            if size and size not in VALID_WH_SIZES:
                errors.append(
                    f"workload '{label}': size '{size}' is not valid — "
                    f"must be one of: {', '.join(sorted(VALID_WH_SIZES))}."
                )
            source = w.get("source")
            if source and source not in VALID_SOURCES:
                errors.append(
                    f"workload '{label}': source '{source}' is not valid — "
                    f"must be one of: {', '.join(sorted(VALID_SOURCES))}."
                )
            wl_ramp = w.get("ramp_curve")
            if wl_ramp and wl_ramp not in VALID_RAMP_CURVES:
                errors.append(
                    f"workload '{label}': ramp_curve '{wl_ramp}' is not valid — "
                    f"must be one of: {', '.join(sorted(VALID_RAMP_CURVES))}."
                )
            if "avg_clusters" in w:
                errors.append(
                    f"workload '{label}': 'avg_clusters' is deprecated — "
                    "replace with 'clusters_min' and 'clusters_max'."
                )

    # 4. storage path
    storage = spec.get("storage", {})
    if "raw_tb" in storage and "standard" not in storage:
        errors.append(
            "storage.raw_tb found at top level — "
            "expected path is storage.standard.raw_tb_year1."
        )
    if "standard" in storage and "raw_tb_year1" not in storage["standard"]:
        errors.append("storage.standard present but missing 'raw_tb_year1'.")

    # 5. AI field names
    ai = spec.get("ai_cortex", {})

    cc = ai.get("cortex_complete", {})
    if cc.get("enabled"):
        if "monthly_tokens_input" in cc:
            errors.append(
                "ai_cortex.cortex_complete uses 'monthly_tokens_input' — "
                "must be 'monthly_input_tokens_M' (value in millions)."
            )
        if "monthly_input_tokens_M" not in cc:
            errors.append(
                "ai_cortex.cortex_complete is enabled but missing 'monthly_input_tokens_M'."
            )

    cs = ai.get("cortex_search", {})
    if cs.get("enabled") and "indexed_gb" in cs:
        errors.append(
            "ai_cortex.cortex_search uses 'indexed_gb' — must be 'indexed_data_gb'."
        )

    if "ai_extract" in ai:
        errors.append(
            "'ai_extract' found directly under ai_cortex — "
            "must be at ai_cortex.cortex_functions.ai_extract "
            "(cortex_functions groups all AI_ SQL functions)."
        )

    cf = ai.get("cortex_functions", {})
    ae = cf.get("ai_extract", {})
    if ae.get("enabled") and "tokens_M_monthly" not in ae:
        errors.append(
            "ai_cortex.cortex_functions.ai_extract is enabled but missing 'tokens_M_monthly'."
        )

    # 6. serverless: wrong field name
    sl = spec.get("serverless", {})
    if isinstance(sl, dict):
        for feat_key, feat_val in sl.items():
            if isinstance(feat_val, dict) and feat_val.get("enabled") and "monthly_credits" in feat_val:
                errors.append(
                    f"serverless.{feat_key} uses 'monthly_credits' — "
                    "must be 'compute_hours_monthly'."
                )

    # 7. OpenFlow warehouse_size must be full name
    of = spec.get("openflow", {})
    for inst in of.get("instances", []):
        wh = inst.get("warehouse_size")
        if wh in OPENFLOW_WH_ABBREVS:
            errors.append(
                f"openflow instance '{inst.get('id', '?')}': "
                f"warehouse_size='{wh}' uses abbreviation — "
                "use full name e.g. 'X-Small', 'Small', 'Medium' "
                "(the JS billing lookup requires the full string)."
            )

    # 8. confirm_required items
    for i, item in enumerate(spec.get("confirm_required", [])):
        if not isinstance(item, dict):
            errors.append(f"confirm_required[{i}] must be an object with 'item' and 'impact_pct'.")
        elif "item" not in item or "impact_pct" not in item:
            errors.append(f"confirm_required[{i}] is missing 'item' or 'impact_pct'.")

    return errors


# ---------------------------------------------------------------------------
# Hook entry point
# ---------------------------------------------------------------------------

def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name != "Write":
        # Edit calls deliver only the new_string fragment, not the full file.
        # Full structural validation requires complete file content — skip.
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    content = tool_input.get("content", "")

    if not is_sizing_json(file_path):
        sys.exit(0)

    # Parse JSON content
    try:
        spec = json.loads(content)
    except json.JSONDecodeError as exc:
        reason = (
            f"BLOCKED: Invalid JSON written to {file_path}\n\n"
            f"  {exc}\n\n"
            "Fix the JSON syntax error, then re-issue the Write tool call."
        )
        print(json.dumps({"decision": "block", "reason": reason}))
        sys.exit(0)

    errors = validate(spec, file_path)

    if errors:
        reason = (
            f"BLOCKED: SIZING_SPEC validation failed — {len(errors)} error(s) in {file_path}\n\n"
            "ERRORS (must fix before the HTML will render correctly):\n"
            + "\n".join(f"  - {e}" for e in errors)
            + "\n\nFix all errors above, then re-issue the Write tool call."
            "\nSchema reference: ${CORTEX_PLUGIN_ROOT}/framework/sizing_spec_schema.json"
        )
        print(json.dumps({"decision": "block", "reason": reason}))

    sys.exit(0)


if __name__ == "__main__":
    main()
