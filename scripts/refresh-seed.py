#!/usr/bin/env python3
"""scripts/refresh-seed.py — guarded auto-refresh of the committed pricing seed.

The committed offline seed (``assets/live_pricing_seed.json``) is the fallback a
fresh clone renders from when the live calculator is unreachable. This script
keeps it fresh *safely*:

    1. Fetch the live calculator (framework/live_pricing.fetch_live →
       build_calc_block).
    2. Merge the fresh calc block onto the static master and run the SAME
       structural + range guards the verify-pricing-json CLI uses
       (framework/pricing_checks.check_pricing).
    3. If the guards FAIL  -> do NOT write; exit non-zero. The last-good seed is
       kept (callers fall back to it automatically).
       If the guards PASS and the calc *content* differs from the committed seed
       -> write the new seed.
       If the guards PASS and content is unchanged -> no-op (exit 0).

``--dry-run`` performs the fetch + guard + diff and reports what it WOULD do
without writing. The scheduled CI job (``.github/workflows/pricing-refresh.yml``)
runs this script and commits the seed only when it actually changed.

Exit codes:
    0  Seed written, or already current (with --dry-run: would-write / current).
    1  Guards failed (seed untouched), or the live fetch failed.
    2  Argument / IO error.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import sys

_THIS_DIR = pathlib.Path(__file__).resolve().parent
_PLUGIN_ROOT = _THIS_DIR.parent
sys.path.insert(0, str(_PLUGIN_ROOT / "framework"))

import live_pricing as lp  # noqa: E402
from pricing_checks import check_pricing  # noqa: E402

_MASTER_PATH = _PLUGIN_ROOT / "assets" / "snowflake_pricing_master.json"


def _load_master(plugin_root: pathlib.Path | None = None) -> dict:
    root = plugin_root or _PLUGIN_ROOT
    return json.loads((root / "assets" / "snowflake_pricing_master.json").read_text(encoding="utf-8"))


def _content_key(calc: dict | None) -> str:
    """Canonical JSON of the rate-bearing content, ignoring volatile metadata.

    ``fetched_at`` changes on every fetch and the container id can drift without
    any rate change, so the "did anything actually change?" comparison is over
    the ``pricing`` + ``regions`` payloads only.
    """
    calc = calc or {}
    return json.dumps(
        {"pricing": calc.get("pricing"), "regions": calc.get("regions")},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )


def content_differs(new_calc: dict, old_seed: dict | None) -> bool:
    """True when the new calc block's rate content differs from the committed seed."""
    return _content_key(new_calc) != _content_key(old_seed)


def gate(new_calc: dict, master: dict) -> tuple[list[str], list[str]]:
    """Run the seed guards on the merged (master + fresh calc) pricing.

    Returns ``(errors, warnings)``; an empty ``errors`` list means the candidate
    is safe to commit.
    """
    merged = lp.merge_pricing(master, new_calc)
    return check_pricing(merged, check_static=True)


def _summarize(calc: dict) -> str:
    pricing = calc.get("pricing") or []
    types = [pt.get("priceType") for pt in pricing if isinstance(pt, dict)]
    regions = calc.get("regions") or []
    src = calc.get("source") or {}
    return (
        f"    fetched_at={calc.get('fetched_at')} container={src.get('container_id')}\n"
        f"    price types ({len(types)}): {', '.join(t for t in types if t)}\n"
        f"    region clouds: {', '.join(c.get('cloud', '?') for c in regions)}"
    )


def refresh_seed(
    *,
    dry_run: bool = False,
    timeout: float = lp._DEFAULT_TIMEOUT,
    plugin_root: pathlib.Path | None = None,
    new_calc: dict | None = None,
) -> int:
    """Fetch → guard → diff → (maybe) write. Returns a process exit code.

    ``new_calc`` lets callers/tests inject a candidate calc block instead of
    hitting the network; when None the live calculator is fetched.
    """
    root = plugin_root or _PLUGIN_ROOT
    stamp = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    print(f"refresh-seed: {stamp}  (dry-run={dry_run})")

    if new_calc is None:
        try:
            new_calc = lp.build_calc_block(lp.fetch_live(timeout=timeout))
        except Exception as exc:  # noqa: BLE001 — any fetch failure keeps last-good seed
            sys.stderr.write(
                f"refresh-seed: live fetch failed ({exc!r}); seed left unchanged.\n"
            )
            return 1

    master = _load_master(root)
    errors, warnings = gate(new_calc, master)
    for w in warnings:
        print(f"  WARN  {w}")
    if errors:
        sys.stderr.write(
            f"refresh-seed: candidate FAILED {len(errors)} guard check(s); "
            "seed left unchanged (last-good kept).\n"
        )
        for e in errors:
            sys.stderr.write(f"  FAIL  {e}\n")
        return 1

    old_seed = lp._read_seed(root)
    if not content_differs(new_calc, old_seed):
        print("refresh-seed: guards PASS; content unchanged — seed already current.")
        print(_summarize(new_calc))
        return 0

    print("refresh-seed: guards PASS; content CHANGED vs committed seed.")
    if old_seed:
        print("  old:")
        print(_summarize(old_seed))
    print("  new:")
    print(_summarize(new_calc))

    if dry_run:
        print("refresh-seed: --dry-run, not writing. (Seed WOULD be updated.)")
        return 0

    lp.write_seed(new_calc, root)
    print(f"refresh-seed: wrote updated seed -> {lp._seed_path(root)}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="Fetch + guard + diff but do not write the seed.")
    ap.add_argument("--timeout", type=float, default=lp._DEFAULT_TIMEOUT,
                    help="Live-fetch timeout in seconds.")
    args = ap.parse_args(argv)
    return refresh_seed(dry_run=args.dry_run, timeout=args.timeout)


if __name__ == "__main__":
    sys.exit(main())
