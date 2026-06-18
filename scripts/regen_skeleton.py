#!/usr/bin/env python3
"""Regenerate framework/sizing_spec_skeleton.json from sizing_spec_schema.json.

The skeleton is a structurally complete, schema-valid SIZING_SPEC with
sensible neutral defaults (every toggle disabled, empty workloads, every
required key present). Build-spec phase clones this and applies a small
patch dict instead of constructing the whole spec from scratch - that
removes the entire class of "missing required key" / "wrong field name"
errors the agent kept making.

Usage:
    python3 scripts/regen_skeleton.py             # regenerate (writes file)
    python3 scripts/regen_skeleton.py --check     # exit non-zero if drifted

Skeleton placement defaults: framework/sizing_spec_skeleton.json. The path
can be overridden with --out for tests.

Why a generator rather than a hand-edited skeleton: the schema is the single
source of truth for required-key lists. Letting the skeleton drift away from
schema is exactly the failure mode this whole change is trying to eliminate,
so we rebuild the skeleton mechanically every time the schema changes.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

_THIS_DIR = pathlib.Path(__file__).resolve().parent
_PLUGIN_ROOT = _THIS_DIR.parent
_SCHEMA_PATH = _PLUGIN_ROOT / "framework" / "sizing_spec_schema.json"
_SKELETON_PATH = _PLUGIN_ROOT / "framework" / "sizing_spec_skeleton.json"

# Per-path neutral defaults that produce a more useful starting point than
# raw-zero. The schema doesn't carry "default" annotations, but a skeleton
# of all zeros makes downstream sanity-checks noisy. Compression ratio of 1
# is the lowest schema-valid value (minimum: 1) and a reasonable neutral.
# Time-travel days defaults to 1 (the documented default for Standard).
_OVERRIDES: dict[tuple, object] = {
    ("storage", "standard", "compression_ratio"): 1,
    ("storage", "standard", "time_travel_days"): 1,
    ("meta", "default_ramp_curve"): "linear",
    ("meta", "edition"): "Enterprise",
    ("meta", "cloud"): "AWS",
    # Annual growth is a fraction (0.20 = 20%/yr). Skeleton ships with 0
    # so the patch must explicitly set growth - prevents accidental
    # compounding when the agent forgets to fill it in.
}


def _resolve(node: dict, schema_root: dict) -> dict:
    """Inline $ref pointers (one level - schema doesn't nest them deeply)."""
    if "$ref" in node:
        path = node["$ref"].lstrip("#/").split("/")
        cur = schema_root
        for p in path:
            cur = cur[p]
        # Recurse to handle nested $ref (defensive; current schema is flat).
        return _resolve(cur, schema_root)
    return node


def default_for(prop_schema: dict, schema_root: dict, path: tuple = ()) -> object:
    prop_schema = _resolve(prop_schema, schema_root)
    override_key = path
    if override_key in _OVERRIDES:
        return _OVERRIDES[override_key]
    t = prop_schema.get("type")
    if isinstance(t, list):
        # Pick the first non-null type for a stable default.
        t = next((x for x in t if x != "null"), t[0])
    if t == "object":
        out: dict = {}
        req = prop_schema.get("required", [])
        props = prop_schema.get("properties", {})
        for k in req:
            if k in props:
                out[k] = default_for(props[k], schema_root, path + (k,))
        return out
    if t == "array":
        return []
    if t == "boolean":
        return False
    if t in ("number", "integer"):
        # Use the explicit minimum where schema declares one (e.g.
        # compression_ratio minimum: 1). Otherwise 0 - schema-valid for
        # all minimum: 0 / no-minimum cases.
        return prop_schema.get("minimum", 0)
    if t == "string":
        enum = prop_schema.get("enum")
        if enum:
            # Pick the first enum value for a deterministic, schema-valid default.
            return enum[0]
        return ""
    return None


def build_skeleton() -> dict:
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    skeleton = default_for(schema, schema)
    # Optional-but-JS-required blocks. The schema marks these as not
    # required at the top level (a sizing without SPCS is structurally
    # valid), but the JS template's calcSPCSCost / calcOpenflowCost /
    # calcReplicationForYear / calcTransferCost / calcCollabCost
    # dereference `SIZING_SPEC.<key>.enabled` (and friends) without
    # optional chaining, so a missing key throws a TypeError at boot and
    # the page renders as $0. Seed disabled placeholders here so that
    # spec-prepare's deep-merge output ALWAYS satisfies the JS contract,
    # whether or not the agent's patch supplies them.
    skeleton.setdefault("spcs", {"enabled": False, "instances": []})
    skeleton.setdefault("openflow", {"enabled": False, "instances": []})
    skeleton.setdefault("openflow_oracle", {"enabled": False, "licensed_cores": 0})
    skeleton.setdefault("postgres", {"enabled": False, "instances": []})
    skeleton.setdefault("data_transfer", {"enabled": False, "pattern": "same_region", "tb_per_month": 0})
    skeleton.setdefault("privatelink", {"enabled": False, "endpoints": 0, "tb_processed_monthly": 0})
    skeleton.setdefault("collaboration", {"accounts": []})
    skeleton.setdefault("replication", {"enabled": False})

    # Document-AI placeholders. Schema marks these as OPTIONAL siblings of
    # `ai_cortex.cortex_complete` etc., but the proposal-template JS uses
    # short-circuit `&&` guards to read `compute_hours_monthly` /
    # `pages_per_month` (calcAICost path), and the `populateAIPanel()` row
    # for `document_ai` historically blew up before optional chaining was
    # added. Baking neutral disabled placeholders into the skeleton
    # eliminates the entire class of "agent forgot to include the doc-AI
    # keys -> JS dereferences undefined -> page renders $0" failure mode
    # without forcing the agent to remember a separate rule.
    ai_cortex = skeleton.setdefault("ai_cortex", {})
    ai_cortex.setdefault("document_ai", {"enabled": False, "compute_hours_monthly": 0})
    ai_cortex.setdefault("ai_parse_document_layout", {"enabled": False, "pages_per_month": 0})
    ai_cortex.setdefault("ai_parse_document_ocr", {"enabled": False, "pages_per_month": 0})

    # Inject a one-liner self-describing marker. This is preserved through
    # the spec-prepare merge so a stray skeleton file is identifiable in
    # logs - but we strip it before final write in spec-prepare, so it
    # never reaches customer-facing JSON.
    skeleton["_skeleton_marker"] = (
        "Generated from framework/sizing_spec_schema.json by "
        "scripts/regen_skeleton.py. Do not edit by hand; rerun the script."
    )
    return skeleton


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if the on-disk skeleton differs from a fresh regeneration.",
    )
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=_SKELETON_PATH,
        help="Override output path (default: framework/sizing_spec_skeleton.json).",
    )
    args = parser.parse_args()

    fresh = build_skeleton()
    fresh_text = json.dumps(fresh, indent=2, sort_keys=False) + "\n"

    if args.check:
        if not args.out.exists():
            print(f"Skeleton missing at {args.out}. Run without --check to create it.", file=sys.stderr)
            return 1
        on_disk = args.out.read_text(encoding="utf-8")
        if on_disk != fresh_text:
            print(
                f"DRIFT: {args.out} is out of sync with the schema.\n"
                f"Run: python3 scripts/regen_skeleton.py",
                file=sys.stderr,
            )
            return 1
        print(f"OK: {args.out} matches the schema.")
        return 0

    args.out.write_text(fresh_text, encoding="utf-8")
    print(f"Wrote {args.out} ({len(fresh_text)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
