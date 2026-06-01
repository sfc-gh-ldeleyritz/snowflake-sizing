#!/usr/bin/env python3
"""Build-time normalizer for SIZING_SPEC JSON.

Replaces the old "agent constructs the dict by hand" workflow. The build-spec
sub-skill now produces a small `patch` dict containing only the customer
specifics (workloads, AI usage, storage TB, growth rate, ...). spec-prepare:

    1. Loads framework/sizing_spec_skeleton.json (every required key, neutral
       defaults, 12 ai_cortex placeholders, 27 serverless placeholders).
    2. Deep-merges the patch over the skeleton.
    3. Renames known legacy field names (storage_growth_pct ->
       annual_growth_pct, monthly_tokens_input -> monthly_input_tokens_M,
       indexed_gb -> indexed_data_gb, monthly_credits ->
       compute_hours_monthly, avg_clusters -> clusters_min/max).
    4. Strips internal leakage fields (utility_queries_reference, _comment,
       __doc__, the skeleton self-marker).
    5. Computes authoritative "core" TCV totals via framework/compute_totals
       and injects them into a `computed_totals` block.
    6. Validates against the schema (top-level required keys, meta required,
       ai_cortex completeness, workload required, enum sanity).
    7. Writes the normalized spec to --out.

Failures are reported as a single grouped error report. The agent fixes the
patch dict and re-runs; the same script is the fast PreToolUse path that
hooks/sizing-guard.py uses for ad-hoc checks of an already-written spec.

Usage:
    python3 scripts/spec-prepare.py --patch <patch.json> --out <spec.json>
    python3 scripts/spec-prepare.py --patch - --out <spec.json>     # patch on stdin
    python3 scripts/spec-prepare.py --validate-only <spec.json>     # check existing
"""
from __future__ import annotations

import argparse
import copy
import datetime as _dt
import json
import pathlib
import sys
from typing import Any

_THIS_DIR = pathlib.Path(__file__).resolve().parent
_PLUGIN_ROOT = _THIS_DIR.parent
_SKELETON_PATH = _PLUGIN_ROOT / "framework" / "sizing_spec_skeleton.json"

sys.path.insert(0, str(_PLUGIN_ROOT / "scripts"))
sys.path.insert(0, str(_PLUGIN_ROOT / "framework"))
from _schema_loader import SCHEMA  # noqa: E402
from compute_totals import compute_core_totals  # noqa: E402
import live_pricing as lp  # noqa: E402  (merged static + live calc, for pinning)


# ── Legacy field rename map ───────────────────────────────────────────────── #
#
# Drives auto-correction inside _rename_legacy_fields(). Each entry is keyed
# by a deterministic locator (path-tuple plus old field name) so we never
# mis-rename a field that legitimately uses the old name in a different
# context. Adding a new rename: just add an entry; the test harness covers
# every one.
_LEGACY_RENAMES = [
    # path_prefix (subpath under spec root), old, new
    (("storage", "standard"),                       "storage_growth_pct",     "annual_growth_pct"),
    (("ai_cortex", "cortex_complete"),              "monthly_tokens_input",   "monthly_input_tokens_M"),
    (("ai_cortex", "cortex_complete"),              "monthly_tokens_output",  "monthly_output_tokens_M"),
    (("ai_cortex", "cortex_agents"),                "monthly_tokens_input",   "monthly_input_tokens_M"),
    (("ai_cortex", "cortex_agents"),                "monthly_tokens_output",  "monthly_output_tokens_M"),
    (("ai_cortex", "snowflake_intelligence"),       "monthly_tokens_input",   "monthly_input_tokens_M"),
    (("ai_cortex", "snowflake_intelligence"),       "monthly_tokens_output",  "monthly_output_tokens_M"),
    (("ai_cortex", "cortex_search"),                "indexed_gb",             "indexed_data_gb"),
]

# Path prefixes whose every dict child has a `monthly_credits` -> `compute_hours_monthly`
# rename. The schema renamed this field for the entire serverless tree.
_SERVERLESS_FIELD_RENAME = ("monthly_credits", "compute_hours_monthly")

# Fields stripped before write. Internal markers and known leakage tokens.
_LEAKAGE_FIELD_NAMES = {
    "utility_queries_reference",   # internal research artefact (memory rule c4962f74)
    "_skeleton_marker",            # injected by regen_skeleton.py
    "_comment",
    "__doc__",
    "__notes__",
}


# ── Helpers ───────────────────────────────────────────────────────────────── #

def _deep_merge(dst: Any, src: Any) -> Any:
    """Patch `src` over `dst`, recursively for dicts. Lists in src REPLACE
    lists in dst (this is the right behaviour for workloads / instances /
    confirm_required - patches supply the intended final list)."""
    if isinstance(dst, dict) and isinstance(src, dict):
        out = dict(dst)
        for k, v in src.items():
            if k in out:
                out[k] = _deep_merge(out[k], v)
            else:
                out[k] = copy.deepcopy(v)
        return out
    return copy.deepcopy(src)


def _walk_node(node: Any, path: tuple) -> list[tuple[tuple, dict]]:
    """Yield (path, dict_node) pairs for every dict in the tree."""
    out = []
    if isinstance(node, dict):
        out.append((path, node))
        for k, v in node.items():
            out.extend(_walk_node(v, path + (k,)))
    elif isinstance(node, list):
        for i, item in enumerate(node):
            out.extend(_walk_node(item, path + (i,)))
    return out


def _rename_legacy_fields(spec: dict, warnings: list[str]) -> None:
    for path_prefix, old, new in _LEGACY_RENAMES:
        node = spec
        for p in path_prefix:
            node = node.get(p) if isinstance(node, dict) else None
            if not isinstance(node, dict):
                node = None
                break
        if isinstance(node, dict) and old in node:
            # Always prefer the legacy value over the skeleton default. The
            # skeleton ships with neutral zeros; if the patch supplies the
            # legacy field name it means the agent intended to set that
            # value, and the skeleton's placeholder must yield.
            node[new] = node[old]
            del node[old]
            warnings.append(
                f"renamed legacy field {'.'.join(path_prefix)}.{old} -> {new}"
            )

    # Serverless: monthly_credits -> compute_hours_monthly across all features.
    sl = spec.get("serverless")
    if isinstance(sl, dict):
        old, new = _SERVERLESS_FIELD_RENAME
        for feat_key, feat in sl.items():
            if isinstance(feat, dict) and old in feat:
                feat[new] = feat[old]
                del feat[old]
                warnings.append(
                    f"renamed legacy field serverless.{feat_key}.{old} -> {new}"
                )

    # Workload-level avg_clusters -> clusters_min/clusters_max split.
    for w in spec.get("workloads", []) or []:
        if isinstance(w, dict) and "avg_clusters" in w:
            avg = w.get("avg_clusters") or 1
            # Patch values win over skeleton defaults (clusters_min/max
            # default to 0 in the schema-derived skeleton).
            if not w.get("clusters_min"):
                w["clusters_min"] = avg
            if not w.get("clusters_max"):
                w["clusters_max"] = avg
            del w["avg_clusters"]
            warnings.append(
                f"workload '{w.get('id') or w.get('label') or '?'}': "
                f"split avg_clusters -> clusters_min/clusters_max"
            )


def _strip_leakage(spec: dict) -> int:
    """Remove forbidden internal/marker fields anywhere in the tree. Returns count."""
    count = 0
    for _, node in _walk_node(spec, ()):
        for fname in list(node.keys()):
            if fname in _LEAKAGE_FIELD_NAMES:
                del node[fname]
                count += 1
    return count


def _stamp_meta_defaults(spec: dict) -> None:
    """Fill in `generated_date` if missing - the agent often forgets."""
    meta = spec.setdefault("meta", {})
    if not meta.get("generated_date"):
        meta["generated_date"] = _dt.date.today().isoformat()


# Pricing-snapshot helpers live in framework/live_pricing.py (the single home for
# pricing provenance); re-exported here as lp.build_pricing_snapshot / lp.pricing_sha256.


# ── Validation ────────────────────────────────────────────────────────────── #

def validate_spec(spec: dict) -> list[str]:
    """Mirror the validation logic in hooks/validate-sizing-json.py.

    Kept in lockstep with that hook so spec-prepare and the hook never
    disagree on what passes.
    """
    errors: list[str] = []

    if "warehouses" in spec:
        errors.append(
            "'warehouses' key found at top level - must be 'workloads' "
            "(JS renderer reads SIZING_SPEC.workloads; 'warehouses' renders as $0)."
        )

    for key in SCHEMA.required_top_level():
        if key not in spec:
            errors.append(f"Missing required top-level key '{key}'.")
    if errors:
        return errors

    meta = spec.get("meta", {}) or {}
    for f in SCHEMA.required_meta():
        if f not in meta:
            errors.append(f"meta.{f} is required.")
    if meta.get("edition") and meta["edition"] not in SCHEMA.valid_editions():
        errors.append(
            f"meta.edition '{meta['edition']}' invalid - must be one of "
            f"{', '.join(sorted(SCHEMA.valid_editions()))}."
        )
    if meta.get("cloud") and meta["cloud"] not in SCHEMA.valid_clouds():
        errors.append(
            f"meta.cloud '{meta['cloud']}' invalid - must be one of "
            f"{', '.join(sorted(SCHEMA.valid_clouds()))}."
        )
    if meta.get("default_ramp_curve") and meta["default_ramp_curve"] not in SCHEMA.valid_ramp_curves():
        errors.append(
            f"meta.default_ramp_curve '{meta['default_ramp_curve']}' invalid."
        )

    workloads = spec.get("workloads", [])
    if not isinstance(workloads, list):
        errors.append("'workloads' must be an array.")
    else:
        if not workloads:
            errors.append("'workloads' array is empty - TCV will render as $0.")
        for i, w in enumerate(workloads):
            label = w.get("label") or w.get("id") or f"workloads[{i}]"
            for f in SCHEMA.required_workload():
                if f not in w:
                    errors.append(f"workload '{label}': missing required field '{f}'.")
            if w.get("size") and w["size"] not in SCHEMA.valid_wh_sizes():
                errors.append(
                    f"workload '{label}': size '{w['size']}' invalid - "
                    f"must be one of {', '.join(sorted(SCHEMA.valid_wh_sizes()))}."
                )
            if w.get("source") and w["source"] not in SCHEMA.valid_sources():
                errors.append(
                    f"workload '{label}': source '{w['source']}' invalid."
                )

    ai = spec.get("ai_cortex", {}) or {}
    for k in SCHEMA.required_ai_cortex():
        if k not in ai:
            errors.append(f"ai_cortex.{k} is missing (required by populateAIPanel()).")
    cf = ai.get("cortex_functions", {}) or {}
    if isinstance(cf, dict):
        for fn in SCHEMA.required_cortex_functions():
            if fn not in cf:
                errors.append(f"ai_cortex.cortex_functions.{fn} is missing.")

    storage = spec.get("storage", {}) or {}
    if "raw_tb" in storage and "standard" not in storage:
        errors.append("storage.raw_tb at top level - expected storage.standard.raw_tb_year1.")
    if "standard" in storage and "raw_tb_year1" not in storage["standard"]:
        errors.append("storage.standard present but missing 'raw_tb_year1'.")

    return errors


# ── Driver ────────────────────────────────────────────────────────────────── #

def prepare(
    patch: dict,
    *,
    pricing: dict | None = None,
    skeleton: dict | None = None,
    prefer_live: bool = False,
) -> tuple[dict, list[str], dict]:
    """Build a normalized SIZING_SPEC from a patch dict.

    Returns ``(spec, warnings, pricing)`` where ``pricing`` is the merged dict
    (static master + native ``calc`` block) the totals were computed against and
    that the caller pins as the sidecar. ``prefer_live`` controls the loader: the
    CLI passes True to pin the freshest live calculator data (graceful fallback to
    cache → committed seed → static master); the default False keeps library/test
    callers network-free and deterministic.
    """
    if skeleton is None:
        skeleton = json.loads(_SKELETON_PATH.read_text(encoding="utf-8"))
    if pricing is None:
        pricing = lp.load_pricing(_PLUGIN_ROOT, prefer_live=prefer_live, offline=not prefer_live)
    warnings: list[str] = []

    spec = _deep_merge(skeleton, patch or {})
    _rename_legacy_fields(spec, warnings)
    stripped = _strip_leakage(spec)
    if stripped:
        warnings.append(f"stripped {stripped} internal/leakage field(s)")

    _stamp_meta_defaults(spec)

    spec["computed_totals"] = compute_core_totals(spec, pricing)
    spec["pricing_snapshot"] = lp.build_pricing_snapshot(pricing)
    return spec, warnings, pricing


def _read_patch(path: str) -> dict:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--patch", help="Path to patch JSON, or '-' for stdin.")
    parser.add_argument("--out", help="Path to write the normalized spec.")
    parser.add_argument(
        "--validate-only",
        metavar="SPEC_PATH",
        help="Validate an existing spec; do not normalize. Exits non-zero on errors.",
    )
    parser.add_argument(
        "--offline", action="store_true",
        help="Pin the committed seed / static master instead of fetching the live "
             "calculator (deterministic, network-free).",
    )
    args = parser.parse_args()

    if args.validate_only:
        spec = json.loads(pathlib.Path(args.validate_only).read_text(encoding="utf-8"))
        errors = validate_spec(spec)
        if errors:
            print(f"spec-prepare: validation failed ({len(errors)} error(s))", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
            return 1
        print(f"spec-prepare: {args.validate_only} is valid.")
        return 0

    if not args.patch or not args.out:
        parser.error("--patch and --out are required (or use --validate-only).")

    patch = _read_patch(args.patch)
    spec, warnings, pricing = prepare(patch, prefer_live=not args.offline)
    errors = validate_spec(spec)

    if errors:
        print(
            f"spec-prepare: prepared spec failed validation ({len(errors)} error(s)).",
            file=sys.stderr,
        )
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Pin the exact merged pricing as a sidecar next to the spec so a re-render
    # reproduces identical numbers (render-html auto-loads it). sizings/* is
    # gitignored, so this is a local artifact to archive alongside the proposal.
    sidecar = out_path.parent / (out_path.stem + ".pricing.json")
    spec["pricing_snapshot"]["pinned_pricing_file"] = sidecar.name
    sidecar.write_text(json.dumps(pricing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    out_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    print(f"spec-prepare: wrote {args.out}")
    if warnings:
        print(f"  Auto-corrections ({len(warnings)}):")
        for w in warnings:
            print(f"    - {w}")
    ct = spec["computed_totals"]
    print(
        f"  core TCV: ${ct['core_tcv']:,.0f}  "
        f"(per-year {[f'${y:,.0f}' for y in ct['core_year_total']]})"
    )
    snap = spec["pricing_snapshot"]
    print(
        f"  pinned pricing -> {sidecar.name}  "
        f"(master {snap['master_effective_date']} v{snap['master_version']}, "
        f"calc {snap['calc_fetched_at']}, sha {snap['pricing_sha256'][:12]})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
