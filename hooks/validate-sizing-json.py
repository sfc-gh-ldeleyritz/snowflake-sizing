#!/usr/bin/env python3
"""
PostToolUse hook: validates SIZING_SPEC JSON files written to sizings/*.json.

Fires on Write tool calls. Skips Edit (partial content) and all non-sizing files.
Blocks on hard structural errors - the same class of mistakes that cause the
HTML renderer to produce a $0 proposal. Approves silently if all checks pass.

Field lists and enum sets are loaded from framework/sizing_spec_schema.json
via _schema_loader.SCHEMA - a single source of truth shared with
scripts/spec-validate.py.

Decision protocol (CoCo PostToolUse hook):
  - {"decision": "block", "reason": "..."}  ->  agent sees error, must fix and retry
  - (no output / exit 0)                     ->  approved
"""

import json
import os
import pathlib
import sys

_PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PLUGIN_ROOT / "scripts"))
from _schema_loader import SCHEMA  # noqa: E402


def is_sizing_json(path: str) -> bool:
    if not path or not path.lower().endswith(".json"):
        return False
    normalized = path.replace("\\", "/")
    return "/sizings/" in normalized or os.path.basename(os.path.dirname(path)) == "sizings"


def validate(spec: dict, file_path: str) -> list:
    errors = []

    if "warehouses" in spec:
        errors.append(
            "'warehouses' key found at top level - must be 'workloads'. "
            "The JS renderer reads SIZING_SPEC.workloads; 'warehouses' silently renders as $0."
        )
    for key in SCHEMA.required_top_level():
        if key not in spec:
            errors.append(f"Missing required top-level key '{key}'.")

    if errors:
        return errors

    meta = spec.get("meta", {})
    for field in SCHEMA.required_meta():
        if field not in meta:
            errors.append(f"meta.{field} is required.")

    valid_editions = SCHEMA.valid_editions()
    edition = meta.get("edition")
    if edition and edition not in valid_editions:
        errors.append(
            f"meta.edition '{edition}' is not valid - "
            f"must be one of: {', '.join(sorted(valid_editions))}."
        )

    valid_clouds = SCHEMA.valid_clouds()
    cloud = meta.get("cloud")
    if cloud and cloud not in valid_clouds:
        errors.append(
            f"meta.cloud '{cloud}' is not valid - "
            f"must be one of: {', '.join(sorted(valid_clouds))}."
        )

    valid_ramp_curves = SCHEMA.valid_ramp_curves()
    ramp = meta.get("default_ramp_curve")
    if ramp and ramp not in valid_ramp_curves:
        errors.append(
            f"meta.default_ramp_curve '{ramp}' is not valid - "
            f"must be one of: {', '.join(sorted(valid_ramp_curves))}."
        )

    required_workload = SCHEMA.required_workload()
    valid_wh_sizes = SCHEMA.valid_wh_sizes()
    valid_sources = SCHEMA.valid_sources()
    workloads = spec.get("workloads", [])
    if not isinstance(workloads, list):
        errors.append("'workloads' must be an array.")
    else:
        if len(workloads) == 0:
            errors.append("'workloads' array is empty - TCV will render as $0.")
        for i, w in enumerate(workloads):
            label = w.get("label") or w.get("id") or f"workloads[{i}]"
            for field in required_workload:
                if field not in w:
                    errors.append(f"workload '{label}': missing required field '{field}'.")
            size = w.get("size")
            if size and size not in valid_wh_sizes:
                errors.append(
                    f"workload '{label}': size '{size}' is not valid - "
                    f"must be one of: {', '.join(sorted(valid_wh_sizes))}."
                )
            source = w.get("source")
            if source and source not in valid_sources:
                errors.append(
                    f"workload '{label}': source '{source}' is not valid - "
                    f"must be one of: {', '.join(sorted(valid_sources))}."
                )
            wl_ramp = w.get("ramp_curve")
            if wl_ramp and wl_ramp != "manual" and wl_ramp not in valid_ramp_curves:
                errors.append(
                    f"workload '{label}': ramp_curve '{wl_ramp}' is not valid - "
                    f"must be one of: {', '.join(sorted(valid_ramp_curves))}, manual."
                )
            if "avg_clusters" in w:
                errors.append(
                    f"workload '{label}': 'avg_clusters' is deprecated - "
                    "replace with 'clusters_min' and 'clusters_max'."
                )

    storage = spec.get("storage", {})
    if "raw_tb" in storage and "standard" not in storage:
        errors.append(
            "storage.raw_tb found at top level - "
            "expected path is storage.standard.raw_tb_year1."
        )
    if "standard" in storage and "raw_tb_year1" not in storage["standard"]:
        errors.append("storage.standard present but missing 'raw_tb_year1'.")

    ai = spec.get("ai_cortex", {})

    for key in SCHEMA.required_ai_cortex():
        if key not in ai:
            errors.append(
                f"ai_cortex.{key} is missing - required by populateAIPanel() "
                "in the HTML template (it dereferences the key without "
                "optional chaining; omission throws TypeError at boot and "
                "the page silently renders as $0). Set 'enabled: false' if "
                "the feature is not used. See framework/sizing_spec_schema.json."
            )

    if "cortex_functions" in ai:
        cf_obj = ai.get("cortex_functions") or {}
        if isinstance(cf_obj, dict):
            for fn in SCHEMA.required_cortex_functions():
                if fn not in cf_obj:
                    errors.append(
                        f"ai_cortex.cortex_functions.{fn} is missing - "
                        "required by populateAIPanel() (the renderer iterates "
                        "all 6 ai_* SQL functions and reads .enabled / "
                        ".tokens_M_monthly without a presence guard). Set "
                        "'enabled: false' if unused."
                    )

    cc = ai.get("cortex_complete", {})
    if cc.get("enabled"):
        if "monthly_tokens_input" in cc:
            errors.append(
                "ai_cortex.cortex_complete uses 'monthly_tokens_input' - "
                "must be 'monthly_input_tokens_M' (value in millions)."
            )
        if "monthly_input_tokens_M" not in cc:
            errors.append(
                "ai_cortex.cortex_complete is enabled but missing 'monthly_input_tokens_M'."
            )

    cs = ai.get("cortex_search", {})
    if cs.get("enabled") and "indexed_gb" in cs:
        errors.append(
            "ai_cortex.cortex_search uses 'indexed_gb' - must be 'indexed_data_gb'."
        )

    if "ai_extract" in ai:
        errors.append(
            "'ai_extract' found directly under ai_cortex - "
            "must be at ai_cortex.cortex_functions.ai_extract "
            "(cortex_functions groups all AI_ SQL functions)."
        )

    cf = ai.get("cortex_functions", {})
    ae = cf.get("ai_extract", {})
    if ae.get("enabled") and "tokens_M_monthly" not in ae:
        errors.append(
            "ai_cortex.cortex_functions.ai_extract is enabled but missing 'tokens_M_monthly'."
        )

    sl = spec.get("serverless", {})
    if isinstance(sl, dict):
        for feat_key, feat_val in sl.items():
            if isinstance(feat_val, dict) and feat_val.get("enabled") and "monthly_credits" in feat_val:
                errors.append(
                    f"serverless.{feat_key} uses 'monthly_credits' - "
                    "must be 'compute_hours_monthly'."
                )

    wrong_of_wh_sizes = SCHEMA.valid_wh_sizes() - SCHEMA.valid_wh_sizes_full()
    of = spec.get("openflow", {})
    for inst in of.get("instances", []):
        wh = inst.get("warehouse_size")
        if wh in wrong_of_wh_sizes:
            errors.append(
                f"openflow instance '{inst.get('id', '?')}': "
                f"warehouse_size='{wh}' uses abbreviation - "
                "use full name e.g. 'X-Small', 'Small', 'Medium' "
                "(the JS billing lookup requires the full string)."
            )

    required_cr_item = SCHEMA.required_confirm_required_item()
    for i, item in enumerate(spec.get("confirm_required", [])):
        if not isinstance(item, dict):
            errors.append(
                f"confirm_required[{i}] must be an object with "
                f"{', '.join(repr(f) for f in required_cr_item)}."
            )
        else:
            for f in required_cr_item:
                if f not in item:
                    errors.append(f"confirm_required[{i}] is missing '{f}'.")

    return errors


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name != "Write":
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    content = tool_input.get("content", "")

    if not is_sizing_json(file_path):
        sys.exit(0)

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
            f"BLOCKED: SIZING_SPEC validation failed - {len(errors)} error(s) in {file_path}\n\n"
            "ERRORS (must fix before the HTML will render correctly):\n"
            + "\n".join(f"  - {e}" for e in errors)
            + "\n\nFix all errors above, then re-issue the Write tool call."
            "\nSchema reference: framework/sizing_spec_schema.json (relative to plugin root)"
        )
        print(json.dumps({"decision": "block", "reason": reason}))

    sys.exit(0)


if __name__ == "__main__":
    main()
