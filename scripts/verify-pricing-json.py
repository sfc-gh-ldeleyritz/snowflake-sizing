#!/usr/bin/env python3
"""Structural + range sanity checks for the merged Snowflake pricing data.

Thin CLI over ``framework/pricing_checks.check_pricing`` — the same guard module
that gates the auto-refreshed seed in ``scripts/refresh-seed.py``, so the CLI and
the seed gate can never disagree on what "plausible" means.

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

import live_pricing as lp  # noqa: E402
from pricing_checks import check_pricing  # noqa: E402


def _load_pricing_arg(path: str) -> tuple[dict, bool]:
    """Load an explicit pricing file. Returns (pricing, check_static).

    Accepts either a full pricing dict (has ``calc``) or a bare calc/seed/cache
    block (has a top-level ``pricing`` list); wraps the latter and skips the
    static-section checks that only apply to the merged master.
    """
    obj = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if "calc" in obj:
        return obj, True
    if isinstance(obj.get("pricing"), list):
        return {"calc": obj}, False
    return obj, True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--offline", action="store_true", help="Use committed seed/master only.")
    ap.add_argument("--pricing", default=None, help="Validate a specific pricing JSON file verbatim.")
    args = ap.parse_args(argv)

    check_static = True
    if args.pricing:
        pricing, check_static = _load_pricing_arg(args.pricing)
        src = args.pricing
    else:
        pricing = lp.load_pricing(prefer_live=not args.offline, offline=args.offline)
        calc = pricing.get("calc") or {}
        src = f"{'offline' if args.offline else 'live'} (fetched_at={calc.get('fetched_at')})"

    errors, warnings = check_pricing(pricing, check_static=check_static)

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
