#!/usr/bin/env python3
"""Structural + range sanity checks for the merged Snowflake pricing data.

Replaces the previous ~1000-line exact-value spot-check that pinned every rate
to the May 2026 Service Consumption Table PDF. Warehouse / credit / storage / AI
rates now come from the LIVE calculator (framework/live_pricing.py), so exact
values drift legitimately. This validates SHAPE and plausible RANGES instead:

  - calc block present with all expected price types + regions
  - static-only sections still present (serverless, openflow, replication, ...)
  - credit rates within [1, 10] $/credit across cloud/region/edition
  - capacity storage within [15, 60] $/TB/month
  - AI credit tiers within [1.5, 2.5]
  - Gen1 standard warehouse credits double per size step (XS=1 ... 6XL=512)
  - Gen2 (per-cloud), Snowpark, and SPCS present with positive credit rates

Usage:
  python3 scripts/verify-pricing-json.py            # live fetch (fallback: seed/master)
  python3 scripts/verify-pricing-json.py --offline  # committed seed/master only
  python3 scripts/verify-pricing-json.py --pricing assets/live_pricing_seed.json

Exit code: 0 if all checks pass, 1 if any fail.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "framework"))

import calc_access as ca  # noqa: E402
import live_pricing as lp  # noqa: E402

errors: list[str] = []
warnings: list[str] = []


def fail(section: str, desc: str) -> None:
    errors.append(f"[{section}] {desc}")


def warn(section: str, desc: str) -> None:
    warnings.append(f"[{section}] {desc}")


def in_range(section: str, desc: str, val, lo: float, hi: float) -> None:
    if val is None:
        fail(section, f"{desc}: missing")
    elif not (lo <= float(val) <= hi):
        fail(section, f"{desc}: {val} outside [{lo}, {hi}]")


# Expected Gen1 standard credits/hour (doubles per size step).
_GEN1_EXPECTED = {
    "XS": 1, "S": 2, "M": 4, "L": 8, "XL": 16,
    "2XL": 32, "3XL": 64, "4XL": 128, "5XL": 256, "6XL": 512,
}
_CALC_PRICE_TYPES = {
    "Credit On Demand", "Storage", "computeTypes",
    "Cortex Code", "Snowflake Intelligence", "AI Credit",
}
_STATIC_SECTIONS = ["serverless", "openflow", "replication", "ramp_curves",
                    "reference_values", "formulas", "data_transfer"]


def check_structural(pricing: dict, check_static: bool = True) -> None:
    if not ca.has_calc(pricing):
        fail("calc", "no live calc block present (calc.pricing missing)")
        return
    calc = pricing["calc"]
    present = {pt.get("priceType") for pt in calc.get("pricing") or []}
    for pt in sorted(_CALC_PRICE_TYPES):
        if pt not in present:
            fail("calc", f"missing price type '{pt}'")
    if not calc.get("regions"):
        fail("calc", "regions list is empty")
    if check_static:
        for sec in _STATIC_SECTIONS:
            if sec not in pricing:
                fail("static", f"missing static section '{sec}'")


def check_credit_and_storage(pricing: dict) -> None:
    cod = ca.price_type(pricing, "Credit On Demand") or []
    n_credit = 0
    for cloud_blk in cod:
        for region_blk in cloud_blk.get("data") or []:
            for row in region_blk.get("data") or []:
                in_range("credit", f"{cloud_blk.get('cloud')}/{region_blk.get('region')}/"
                         f"{row.get('productFamily2')}", row.get("listPrice"), 1.0, 10.0)
                n_credit += 1
    if n_credit == 0:
        fail("credit", "no credit-rate rows found")

    storage = ca.price_type(pricing, "Storage") or []
    n_storage = 0
    for cloud_blk in storage:
        for region_blk in cloud_blk.get("data") or []:
            for row in region_blk.get("data") or []:
                in_range("storage", f"{cloud_blk.get('cloud')}/{region_blk.get('region')}",
                         row.get("listPrice"), 15.0, 60.0)
                n_storage += 1
    if n_storage == 0:
        fail("storage", "no storage-rate rows found")


def check_ai_credit(pricing: dict) -> None:
    rates = ca.ai_credit_rates(pricing)
    in_range("ai_credit", "regional", rates.get("regional"), 1.5, 2.5)
    in_range("ai_credit", "global", rates.get("global"), 1.5, 2.5)


def check_warehouses(pricing: dict) -> None:
    # Gen1 doubles per size step.
    for size, expected in _GEN1_EXPECTED.items():
        got = ca.warehouse_credits(pricing, size, gen=1)
        if got is None:
            fail("gen1", f"{size}: missing")
        elif abs(got - expected) > 1e-6:
            fail("gen1", f"{size}: {got} != {expected}")
    # Gen2 present (per-cloud) and positive for each cloud.
    for cloud in ("AWS", "Azure", "GCP"):
        r = ca.warehouse_credits(pricing, "M", gen=2, cloud=cloud)
        if r is None or r <= 0:
            fail("gen2", f"{cloud} M: {r}")
    # Snowpark present and positive.
    sp = ca.warehouse_credits(pricing, "M", warehouse_type="snowpark")
    if sp is None or sp <= 0:
        fail("snowpark", f"M MEMORY_1X: {sp}")


def check_spcs(pricing: dict) -> None:
    fams = ca.spcs_families(pricing)
    if not fams:
        fail("spcs", "no SPCS families found")
        return
    itypes = {f["instance_type"] for f in fams}
    for want in ("HIGHMEM_X64", "CPU_X64", "GPU"):
        if want not in itypes:
            warn("spcs", f"instance type '{want}' not present")
    for f in fams:
        if f["credits_per_hour"] is None or f["credits_per_hour"] <= 0:
            fail("spcs", f"{f['family']}: non-positive rate {f['credits_per_hour']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--offline", action="store_true", help="Use committed seed/master only.")
    ap.add_argument("--pricing", default=None, help="Validate a specific pricing JSON file verbatim.")
    args = ap.parse_args(argv)

    check_static = True
    if args.pricing:
        obj = json.loads(pathlib.Path(args.pricing).read_text(encoding="utf-8"))
        # Accept either a full pricing dict (has 'calc') or a bare calc/seed/cache
        # block (has top-level 'pricing' list); wrap the latter and skip the
        # static-section checks that only apply to the merged master.
        if "calc" in obj:
            pricing = obj
        elif isinstance(obj.get("pricing"), list):
            pricing = {"calc": obj}
            check_static = False
        else:
            pricing = obj
        src = args.pricing
    else:
        pricing = lp.load_pricing(prefer_live=not args.offline, offline=args.offline)
        calc = pricing.get("calc") or {}
        src = f"{'offline' if args.offline else 'live'} (fetched_at={calc.get('fetched_at')})"

    check_structural(pricing, check_static=check_static)
    if ca.has_calc(pricing):
        check_credit_and_storage(pricing)
        check_ai_credit(pricing)
        check_warehouses(pricing)
        check_spcs(pricing)

    print(f"verify-pricing-json: source = {src}")
    for w in warnings:
        print(f"  WARN  {w}")
    if errors:
        print(f"\nFAILED with {len(errors)} error(s):")
        for e in errors:
            print(f"  FAIL  {e}")
        return 1
    print(f"  OK  all structural + range checks passed ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
