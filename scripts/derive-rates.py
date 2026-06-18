#!/usr/bin/env python3
"""Derive credit / AI-credit / storage rates for a cloud-region-edition.

Phase 1 helper for the snowflake-sizing build flow. Wraps framework/live_pricing
(live calculator fetch with cache -> committed seed -> static master fallback)
and framework/calc_access (native-shape readers), so the agent no longer hand-reads
the pricing JSON. Region aliases resolve through renderer.pricing_validator.

Usage:
    python3 scripts/derive-rates.py --cloud AWS --region "us-east-1" --edition Enterprise
    python3 scripts/derive-rates.py --cloud GCP --region "Netherlands" --edition Enterprise --offline
    python3 scripts/derive-rates.py --cloud AWS --region "London" --edition Enterprise --json

Exit codes:
    0  rates resolved and printed.
    1  region/edition could not be resolved (available regions are listed).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

_THIS_DIR = pathlib.Path(__file__).resolve().parent
_PLUGIN_ROOT = _THIS_DIR.parent
for _d in (str(_PLUGIN_ROOT), str(_PLUGIN_ROOT / "framework")):
    if _d not in sys.path:
        sys.path.insert(0, _d)

import calc_access  # noqa: E402
import live_pricing  # noqa: E402
from renderer.pricing_validator import _resolve_region, lookup_ai_credit_rate  # noqa: E402


def derive(cloud: str, region: str, edition: str, offline: bool = False, timeout: float = 10.0) -> dict:
    pricing = live_pricing.load_pricing(prefer_live=not offline, offline=offline, timeout=timeout)
    canon = _resolve_region(region)
    credit = calc_access.credit_rate(pricing, cloud, canon, edition)
    storage = calc_access.storage_rate(pricing, cloud, canon)
    ai_credit = lookup_ai_credit_rate(pricing, cloud, canon)
    editions = calc_access.region_product_families(pricing, cloud, canon)
    calc = pricing.get("calc") or {}
    return {
        "ok": credit is not None and storage is not None,
        "cloud": cloud,
        "region_input": region,
        "region_resolved": canon,
        "edition": edition,
        "credit_rate": credit,
        "ai_credit_rate": ai_credit,
        "storage_rate_per_tb": storage,
        "available_editions": editions,
        "source": {
            "fetched_at": calc.get("fetched_at"),
            "container_id": (calc.get("source") or {}).get("container_id"),
            "offline": offline,
        },
        "_pricing": pricing,  # internal, popped before JSON output
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cloud", required=True, help="AWS | Azure | GCP")
    ap.add_argument("--region", required=True, help="Region string (alias-resolved before lookup).")
    ap.add_argument("--edition", default="Enterprise", help="Standard | Enterprise | Business Critical | VPS")
    ap.add_argument("--offline", action="store_true", help="Skip live fetch; use cache/seed/master.")
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--json", action="store_true", help="Emit a JSON object instead of a human summary.")
    args = ap.parse_args(argv)

    res = derive(args.cloud, args.region, args.edition, offline=args.offline, timeout=args.timeout)
    pricing = res.pop("_pricing")

    if not res["ok"]:
        sys.stderr.write(
            f"derive-rates: could not resolve {args.cloud} / '{args.region}' "
            f"(-> '{res['region_resolved']}') / {args.edition}.\n"
        )
        regions = calc_access.calc_regions(pricing, args.cloud)
        if regions:
            sys.stderr.write(f"  Available {args.cloud} regions ({len(regions)}):\n")
            for r in regions:
                sys.stderr.write(f"    - {r}\n")
        if args.json:
            print(json.dumps(res, indent=2))
        return 1

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        src = "offline" if args.offline else f"live @ {res['source']['fetched_at']}"
        eds = ", ".join(res["available_editions"] or []) or "n/a"
        print(f"Region: {res['region_resolved']} ({args.cloud})  [{src}]")
        print(f"  credit_rate         : ${res['credit_rate']:.2f}/credit ({args.edition})")
        print(f"  ai_credit_rate      : ${res['ai_credit_rate']:.2f}/credit")
        print(f"  storage_rate_per_tb : ${res['storage_rate_per_tb']:.2f}/TB/month")
        print(f"  editions available  : {eds}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
