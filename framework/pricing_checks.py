#!/usr/bin/env python3
"""framework/pricing_checks.py — structural + range guards for merged pricing.

Single importable source of truth for the "is this pricing data plausible?"
checks. Both the ``scripts/verify-pricing-json.py`` CLI and the
``scripts/refresh-seed.py`` auto-refresh gate call :func:`check_pricing` so the
seed is never auto-committed unless it passes the very same guards the CLI
enforces.

Validates SHAPE and plausible RANGES (not exact values — warehouse / credit /
storage / AI rates come from the LIVE calculator and drift legitimately):

  - calc block present with all expected price types + non-empty regions
  - static-only sections still present (serverless, openflow, replication, ...)
  - credit rates within [1, 10] $/credit across cloud/region/edition
  - capacity storage within [15, 60] $/TB/month
  - AI credit tiers within [1.5, 2.5]
  - Gen1 standard warehouse credits double per size step (XS=1 ... 6XL=512)
  - Gen2 (per-cloud), Snowpark, and SPCS present with positive credit rates

Public surface:
    check_pricing(pricing, *, check_static=True) -> (errors, warnings)
"""
from __future__ import annotations

import calc_access as ca  # native-shape rate accessors (framework/)

# Expected Gen1 standard credits/hour (doubles per size step).
GEN1_EXPECTED = {
    "XS": 1, "S": 2, "M": 4, "L": 8, "XL": 16,
    "2XL": 32, "3XL": 64, "4XL": 128, "5XL": 256, "6XL": 512,
}
CALC_PRICE_TYPES = {
    "Credit On Demand", "Storage", "computeTypes",
    "Cortex Code", "Snowflake Intelligence", "AI Credit",
}
STATIC_SECTIONS = ["serverless", "openflow", "replication", "ramp_curves",
                   "reference_values", "formulas", "data_transfer"]


class _Report:
    """Accumulates ``errors`` / ``warnings`` with the small helpers the checks use."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def fail(self, section: str, desc: str) -> None:
        self.errors.append(f"[{section}] {desc}")

    def warn(self, section: str, desc: str) -> None:
        self.warnings.append(f"[{section}] {desc}")

    def in_range(self, section: str, desc: str, val, lo: float, hi: float) -> None:
        if val is None:
            self.fail(section, f"{desc}: missing")
        elif not (lo <= float(val) <= hi):
            self.fail(section, f"{desc}: {val} outside [{lo}, {hi}]")


def _check_structural(pricing: dict, rep: _Report, check_static: bool) -> None:
    if not ca.has_calc(pricing):
        rep.fail("calc", "no live calc block present (calc.pricing missing)")
        return
    calc = pricing["calc"]
    present = {pt.get("priceType") for pt in calc.get("pricing") or []}
    for pt in sorted(CALC_PRICE_TYPES):
        if pt not in present:
            rep.fail("calc", f"missing price type '{pt}'")
    if not calc.get("regions"):
        rep.fail("calc", "regions list is empty")
    if check_static:
        for sec in STATIC_SECTIONS:
            if sec not in pricing:
                rep.fail("static", f"missing static section '{sec}'")


def _check_credit_and_storage(pricing: dict, rep: _Report) -> None:
    cod = ca.price_type(pricing, "Credit On Demand") or []
    n_credit = 0
    for cloud_blk in cod:
        for region_blk in cloud_blk.get("data") or []:
            for row in region_blk.get("data") or []:
                rep.in_range("credit", f"{cloud_blk.get('cloud')}/{region_blk.get('region')}/"
                             f"{row.get('productFamily2')}", row.get("listPrice"), 1.0, 10.0)
                n_credit += 1
    if n_credit == 0:
        rep.fail("credit", "no credit-rate rows found")

    storage = ca.price_type(pricing, "Storage") or []
    n_storage = 0
    for cloud_blk in storage:
        for region_blk in cloud_blk.get("data") or []:
            for row in region_blk.get("data") or []:
                rep.in_range("storage", f"{cloud_blk.get('cloud')}/{region_blk.get('region')}",
                             row.get("listPrice"), 15.0, 60.0)
                n_storage += 1
    if n_storage == 0:
        rep.fail("storage", "no storage-rate rows found")


def _check_ai_credit(pricing: dict, rep: _Report) -> None:
    rates = ca.ai_credit_rates(pricing)
    rep.in_range("ai_credit", "regional", rates.get("regional"), 1.5, 2.5)
    rep.in_range("ai_credit", "global", rates.get("global"), 1.5, 2.5)


def _check_warehouses(pricing: dict, rep: _Report) -> None:
    # Gen1 doubles per size step.
    for size, expected in GEN1_EXPECTED.items():
        got = ca.warehouse_credits(pricing, size, gen=1)
        if got is None:
            rep.fail("gen1", f"{size}: missing")
        elif abs(got - expected) > 1e-6:
            rep.fail("gen1", f"{size}: {got} != {expected}")
    # Gen2 present (per-cloud) and positive for each cloud.
    for cloud in ("AWS", "Azure", "GCP"):
        r = ca.warehouse_credits(pricing, "M", gen=2, cloud=cloud)
        if r is None or r <= 0:
            rep.fail("gen2", f"{cloud} M: {r}")
    # Snowpark present and positive.
    sp = ca.warehouse_credits(pricing, "M", warehouse_type="snowpark")
    if sp is None or sp <= 0:
        rep.fail("snowpark", f"M MEMORY_1X: {sp}")


def _check_spcs(pricing: dict, rep: _Report) -> None:
    fams = ca.spcs_families(pricing)
    if not fams:
        rep.fail("spcs", "no SPCS families found")
        return
    itypes = {f["instance_type"] for f in fams}
    for want in ("HIGHMEM_X64", "CPU_X64", "GPU"):
        if want not in itypes:
            rep.warn("spcs", f"instance type '{want}' not present")
    for f in fams:
        if f["credits_per_hour"] is None or f["credits_per_hour"] <= 0:
            rep.fail("spcs", f"{f['family']}: non-positive rate {f['credits_per_hour']}")


def check_pricing(pricing: dict, *, check_static: bool = True) -> tuple[list[str], list[str]]:
    """Run all structural + range guards on a merged pricing dict.

    Args:
        pricing:      Merged pricing dict (static master + native ``calc`` block),
                      or a bare calc block wrapped as ``{"calc": <block>}``.
        check_static: When True, also require the static-only sections. Set False
                      when validating a bare calc/seed block that has no master.

    Returns:
        ``(errors, warnings)`` — two lists of ``"[section] message"`` strings.
        ``errors`` empty means the data passed every guard.
    """
    rep = _Report()
    _check_structural(pricing, rep, check_static)
    if ca.has_calc(pricing):
        _check_credit_and_storage(pricing, rep)
        _check_ai_credit(pricing, rep)
        _check_warehouses(pricing, rep)
        _check_spcs(pricing, rep)
    return rep.errors, rep.warnings
