#!/usr/bin/env python3
"""framework/live_pricing.py — live Snowflake pricing-calculator fetch + hybrid merge.

The public Snowflake pricing calculator publishes its rate tables as three AEM
JSON resources under one version-specific container path, e.g.::

    https://www.snowflake.com/content/snowflake-site/global/en/pricing-options/
      calculator/_jcr_content/root/responsivegrid/container_397110202_/container/
      pricing_calculator.pricing.json   (9 price types)
      pricing_calculator.regions.json   (cloud -> region -> product_families)
      pricing_calculator.assumptions.json   (currently 404s; reserved)

The ``container_<digits>_`` id changes when the page is re-authored, so we
discover the live paths by scraping the public calculator page and regexing the
embedded resource paths, falling back to pinned URLs captured from the page.

This module never participates in the render *core* (``renderer.compile_spec`` is
pure and takes ``pricing`` as an argument). It only assembles the ``pricing``
dict that callers feed in, so rendering stays deterministic and unit-testable.

Hybrid merge
------------
The live calculator only covers warehouse / storage / credit / AI rate tables.
Serverless, OpenFlow, Postgres, replication, ramp curves, formulas, reference
values, organization-usage and the detailed ai_features blocks have no
calculator equivalent and stay in the committed static master. ``merge_pricing``
therefore attaches the native live blocks under a single ``calc`` namespace and
leaves every static section untouched::

    pricing["calc"] = {
        "schema": "snowflake-calculator-native/1",
        "fetched_at": "<UTC ISO-8601>",
        "source": {...},
        "pricing":  [ ...9 priceType objects... ],
        "regions":  [ ...cloud list... ],
        "assumptions": {},
    }

Resolution order (``load_pricing``): live fetch → on-disk cache
(``live_pricing_cache.json``, gitignored) → committed seed
(``live_pricing_seed.json``) → static master (no ``calc``). The committed seed
ships a native snapshot so a fresh clone renders correctly fully offline; a
successful live fetch refreshes the runtime cache.

Public surface
--------------
    discover_endpoints(timeout=...) -> dict
    fetch_live(timeout=..., endpoints=None) -> dict
    build_calc_block(live) -> dict
    merge_pricing(static_base, calc_block) -> dict
    load_pricing(plugin_root=None, prefer_live=True, offline=False, timeout=...) -> dict
    write_seed(calc_block, plugin_root=None) -> None
    pricing_sha256(pricing) -> str
    build_pricing_snapshot(pricing) -> dict
"""
from __future__ import annotations

import copy
import datetime as _dt
import hashlib
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request
from typing import Optional

# ── Paths ─────────────────────────────────────────────────────────────────── #

_PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent.parent
_MASTER_REL = ("assets", "snowflake_pricing_master.json")
_SEED_REL = ("assets", "live_pricing_seed.json")
_CACHE_REL = ("assets", "live_pricing_cache.json")

# ── Live endpoint discovery ───────────────────────────────────────────────── #

CALCULATOR_PAGE_URL = "https://www.snowflake.com/en/pricing-options/calculator/"
_HOST = "https://www.snowflake.com"
CALC_SCHEMA = "snowflake-calculator-native/1"

# Pinned fallbacks (captured 2026-05-30) — used only if page-scrape discovery
# fails to surface a given endpoint. The container id is version-specific and is
# expected to drift; discovery is the primary path.
_PINNED_BASE = (
    _HOST
    + "/content/snowflake-site/global/en/pricing-options/calculator/_jcr_content"
    + "/root/responsivegrid/container_397110202_/container"
)
_PINNED = {
    "pricing": f"{_PINNED_BASE}/pricing_calculator.pricing.json",
    "regions": f"{_PINNED_BASE}/pricing_calculator.regions.json",
}

# Matches the embedded AEM resource paths in the calculator page HTML, e.g.
#   /content/snowflake-site/.../container_397110202_/container/pricing_calculator.pricing.json
_ENDPOINT_RE = re.compile(
    r"/content/snowflake-site/[^\s\"'<>]*?pricing_calculator\.(pricing|regions)\.json"
)
_CONTAINER_RE = re.compile(r"container_\d+_")

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_DEFAULT_TIMEOUT = 10.0


def _http_get(url: str, timeout: float = _DEFAULT_TIMEOUT) -> str:
    """GET a URL and return the decoded body. Raises on any HTTP/network error."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed host)
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def discover_endpoints(timeout: float = _DEFAULT_TIMEOUT) -> dict:
    """Scrape the calculator page for the version-specific JSON endpoint paths.

    Returns ``{"pricing": url, "regions": url}``. Any endpoint not found in the
    page HTML falls back to the pinned URL. Never raises — a scrape failure just
    yields the pinned URLs (logged to stderr).
    """
    found: dict[str, str] = {}
    try:
        html = _http_get(CALCULATOR_PAGE_URL, timeout=timeout)
        for m in _ENDPOINT_RE.finditer(html):
            found[m.group(1)] = _HOST + m.group(0)
    except Exception as exc:  # noqa: BLE001 — discovery is best-effort
        sys.stderr.write(
            f"live_pricing: endpoint discovery failed ({exc!r}); using pinned URLs\n"
        )
    return {
        "pricing": found.get("pricing", _PINNED["pricing"]),
        "regions": found.get("regions", _PINNED["regions"]),
    }


def fetch_live(timeout: float = _DEFAULT_TIMEOUT, endpoints: Optional[dict] = None) -> dict:
    """Fetch + parse the live calculator JSON.

    Returns ``{"pricing": <list>, "regions": <list>, "endpoints": <dict>}``.
    Raises ``urllib.error.URLError`` / ``json.JSONDecodeError`` / ``OSError`` on
    failure so the caller (``load_pricing``) can decide on a fallback.
    """
    eps = endpoints or discover_endpoints(timeout=timeout)
    pricing = json.loads(_http_get(eps["pricing"], timeout=timeout))
    regions = json.loads(_http_get(eps["regions"], timeout=timeout))
    return {"pricing": pricing, "regions": regions, "endpoints": eps}


def build_calc_block(live: dict) -> dict:
    """Assemble the native ``calc`` namespace from a ``fetch_live`` result."""
    eps = live.get("endpoints", {}) or {}
    cm = _CONTAINER_RE.search(eps.get("pricing", "") or "")
    return {
        "schema": CALC_SCHEMA,
        "fetched_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "source": {
            "calculator_page": CALCULATOR_PAGE_URL,
            "pricing_url": eps.get("pricing"),
            "regions_url": eps.get("regions"),
            "container_id": cm.group(0) if cm else "",
        },
        "pricing": live["pricing"],
        "regions": live["regions"],
        "assumptions": {},  # pricing_calculator.assumptions.json currently 404s; reserved
    }


def merge_pricing(static_base: dict, calc_block: dict) -> dict:
    """Return a deep copy of ``static_base`` with ``calc_block`` attached as ``calc``.

    Every static section is retained verbatim; only the ``calc`` namespace is
    (re)written. This is the hybrid-merge contract.
    """
    out = copy.deepcopy(static_base)
    out["calc"] = copy.deepcopy(calc_block)
    return out


# ── Disk helpers ──────────────────────────────────────────────────────────── #

def _root(plugin_root: Optional[pathlib.Path]) -> pathlib.Path:
    return pathlib.Path(plugin_root) if plugin_root else _PLUGIN_ROOT


def _master_path(plugin_root: Optional[pathlib.Path] = None) -> pathlib.Path:
    return _root(plugin_root).joinpath(*_MASTER_REL)


def _seed_path(plugin_root: Optional[pathlib.Path] = None) -> pathlib.Path:
    return _root(plugin_root).joinpath(*_SEED_REL)


def _cache_path(plugin_root: Optional[pathlib.Path] = None) -> pathlib.Path:
    return _root(plugin_root).joinpath(*_CACHE_REL)


def _load_master(plugin_root: Optional[pathlib.Path] = None) -> dict:
    return json.loads(_master_path(plugin_root).read_text(encoding="utf-8"))


def _read_calc_file(path: pathlib.Path) -> Optional[dict]:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _read_cache(plugin_root: Optional[pathlib.Path] = None) -> Optional[dict]:
    return _read_calc_file(_cache_path(plugin_root))


def _read_seed(plugin_root: Optional[pathlib.Path] = None) -> Optional[dict]:
    return _read_calc_file(_seed_path(plugin_root))


def _write_cache(calc_block: dict, plugin_root: Optional[pathlib.Path] = None) -> None:
    try:
        _cache_path(plugin_root).write_text(
            json.dumps(calc_block, separators=(",", ":")), encoding="utf-8"
        )
    except OSError as exc:
        sys.stderr.write(f"live_pricing: cache write failed ({exc!r})\n")


def load_pricing(
    plugin_root: Optional[pathlib.Path] = None,
    prefer_live: bool = True,
    offline: bool = False,
    timeout: float = _DEFAULT_TIMEOUT,
) -> dict:
    """Load the merged pricing dict (static master + native ``calc`` block).

    Resolution order:
      1. Live fetch (skipped when ``offline`` or ``prefer_live=False``).
      2. Runtime cache (``assets/live_pricing_cache.json``, gitignored).
      3. Committed seed (``assets/live_pricing_seed.json``).
      4. Static master alone (no ``calc`` — only if the seed is also missing).

    A successful live fetch refreshes the cache. Returns a dict that has a
    ``calc`` key whenever a live fetch, cache, or committed seed is available.
    """
    base = _load_master(plugin_root)

    def _fallback() -> dict:
        cached = _read_cache(plugin_root)
        if cached:
            return merge_pricing(base, cached)
        seed = _read_seed(plugin_root)
        if seed:
            return merge_pricing(base, seed)
        return base

    if offline or not prefer_live:
        return _fallback()

    try:
        live = fetch_live(timeout=timeout)
        calc = build_calc_block(live)
        _write_cache(calc, plugin_root)
        return merge_pricing(base, calc)
    except Exception as exc:  # noqa: BLE001 — any failure → graceful fallback
        sys.stderr.write(
            f"live_pricing: live fetch failed ({exc!r}); "
            "falling back to cache, then committed seed, then static master\n"
        )
        return _fallback()


def write_seed(calc_block: dict, plugin_root: Optional[pathlib.Path] = None) -> None:
    """Write ``calc_block`` to the committed seed file (pretty-printed, diffable).

    The seed is the offline fallback shipped in the repo; a maintainer refreshes
    it by committing a new live fetch.
    """
    _seed_path(plugin_root).write_text(
        json.dumps(calc_block, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


# ── Pricing snapshot / pinning ────────────────────────────────────────────── #

def pricing_sha256(pricing: dict) -> str:
    """Stable hash of a merged pricing dict (canonical JSON, key-sorted)."""
    payload = json.dumps(pricing or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_pricing_snapshot(pricing: dict) -> dict:
    """Capture the provenance of the pricing used to build a sizing.

    Stamped into a spec as the optional top-level ``pricing_snapshot`` block so a
    delivered sizing records exactly which rates it was built against. The full
    rates live in a sidecar (``<slug>.pricing.json``); this block is the metadata
    + an integrity hash that lets a re-render confirm it loaded the same data.
    ``pinned_pricing_file`` is filled by the caller once the sidecar path is known.
    """
    meta = (pricing or {}).get("metadata") or {}
    calc = (pricing or {}).get("calc") or {}
    src = calc.get("source") or {}
    return {
        "schema_version": 1,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "master_effective_date": meta.get("effective_date"),
        "master_version": meta.get("version"),
        "calc_schema": calc.get("schema"),
        "calc_fetched_at": calc.get("fetched_at"),
        "calc_container_id": src.get("container_id"),
        "calc_source_urls": {
            "calculator_page": src.get("calculator_page"),
            "pricing_url": src.get("pricing_url"),
            "regions_url": src.get("regions_url"),
        },
        "pricing_sha256": pricing_sha256(pricing),
        "pinned_pricing_file": None,
    }


# ── CLI ───────────────────────────────────────────────────────────────────── #

def _summary(calc: dict) -> str:
    pricing = calc.get("pricing") or []
    types = [pt.get("priceType") for pt in pricing if isinstance(pt, dict)]
    regions = calc.get("regions") or []
    return (
        f"schema={calc.get('schema')} fetched_at={calc.get('fetched_at')}\n"
        f"  container={calc.get('source', {}).get('container_id')}\n"
        f"  price types ({len(types)}): {', '.join(t for t in types if t)}\n"
        f"  region clouds: {', '.join(c.get('cloud', '?') for c in regions)}"
    )


def main(argv: Optional[list] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Live Snowflake pricing-calculator fetch / merge / cache.")
    ap.add_argument("--refresh", action="store_true", help="Fetch live, refresh cache, print summary.")
    ap.add_argument("--print-endpoints", action="store_true", help="Discover + print live endpoint URLs.")
    ap.add_argument("--write-seed", action="store_true",
                    help="Fetch live (or use cache) and write the committed offline seed file.")
    ap.add_argument("--offline", action="store_true", help="Never hit the network (use cache/committed seed).")
    ap.add_argument("--timeout", type=float, default=_DEFAULT_TIMEOUT)
    args = ap.parse_args(argv)

    if args.print_endpoints:
        eps = discover_endpoints(timeout=args.timeout)
        print(json.dumps(eps, indent=2))
        return 0

    if args.write_seed:
        if args.offline:
            calc = _read_cache() or _read_seed()
            if not calc:
                sys.stderr.write("live_pricing: --offline --write-seed needs a cache or existing seed\n")
                return 1
        else:
            calc = build_calc_block(fetch_live(timeout=args.timeout))
        write_seed(calc)
        print(f"live_pricing: wrote committed seed -> {_seed_path()}")
        print(_summary(calc))
        return 0

    # default / --refresh
    merged = load_pricing(prefer_live=not args.offline, offline=args.offline, timeout=args.timeout)
    calc = merged.get("calc") or {}
    print(_summary(calc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
