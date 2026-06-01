#!/usr/bin/env python3
"""framework/calc_access.py — native-shape readers for the live calculator block.

Single source of truth for rate lookups against ``pricing["calc"]`` (the
calculator-native data assembled by ``framework/live_pricing.py``). Both the
Python math (``compute_totals``) and the pricing validator read rates through
these helpers so there is exactly one place that understands the calculator's
nested JSON shapes.

All functions are pure: they never mutate inputs and tolerate missing/partial
data (returning ``None`` or a sensible default rather than raising).

Calculator-native shapes (under ``pricing["calc"]["pricing"]``, a list of
``{priceType, data}`` objects)::

    Credit On Demand / Storage / Data Transfer:
        [{cloud, data:[{region, data:[{productFamily2, listPrice, ...}]}]}]
    AI Credit:
        [{cloud:"All", data:[{region:"All", data:[{productFamily2, data:[{listPrice}]}]}]}]
    computeTypes:
        [{type, label, data}]   # STANDARD_GEN_1 (flat XS-6XL),
                                 # STANDARD_GEN_2 (per-cloud XS-4XL),
                                 # SNOWPARK (flat, memoryConfiguration qualifier),
                                 # SPCS ([{instanceType, data:[{instanceFamily, creditsPerHour}]}])
    AI / Cortex Code / Snowflake Intelligence:
        [{subTypeName, data:[{functionName, data:[{modelName, creditConversionRate,
                                                   conversionUnit, conversionType}]}]}]
"""
from __future__ import annotations

from typing import Optional

# ── Normalizers ───────────────────────────────────────────────────────────── #

_CLOUD_ALIASES = {
    "aws": "AWS", "amazon": "AWS", "amazon web services": "AWS",
    "azure": "Azure", "microsoft azure": "Azure", "ms azure": "Azure",
    "gcp": "GCP", "google": "GCP", "google cloud": "GCP",
    "google cloud platform": "GCP",
}

_EDITION_ALIASES = {
    "standard": "Standard",
    "enterprise": "Enterprise",
    "business critical": "Business Critical",
    "business_critical": "Business Critical",
    "business-critical": "Business Critical",
    "vps": "VPS",
    "virtual private snowflake": "VPS",
}

# Canonical warehouse sizes (calculator order). Both short ("XS") and long
# ("X-Small") spellings normalize to the short token.
_SIZE_ALIASES = {
    "x-small": "XS", "xsmall": "XS", "xs": "XS",
    "small": "S", "s": "S",
    "medium": "M", "m": "M",
    "large": "L", "l": "L",
    "x-large": "XL", "xlarge": "XL", "xl": "XL",
    "2x-large": "2XL", "2xlarge": "2XL", "2xl": "2XL",
    "3x-large": "3XL", "3xlarge": "3XL", "3xl": "3XL",
    "4x-large": "4XL", "4xlarge": "4XL", "4xl": "4XL",
    "5x-large": "5XL", "5xlarge": "5XL", "5xl": "5XL",
    "6x-large": "6XL", "6xlarge": "6XL", "6xl": "6XL",
}


def norm_cloud(cloud: Optional[str]) -> Optional[str]:
    if not cloud:
        return None
    return _CLOUD_ALIASES.get(cloud.strip().lower(), cloud.strip())


def norm_edition(edition: Optional[str]) -> Optional[str]:
    if not edition:
        return None
    return _EDITION_ALIASES.get(edition.strip().lower(), edition.strip())


def norm_size(size: Optional[str]) -> Optional[str]:
    if not size:
        return None
    return _SIZE_ALIASES.get(size.strip().lower(), size.strip().upper())


def _size_of(warehouse_label: str) -> str:
    """Extract the canonical size token from a calculator warehouse label.

    'XS - 1 credit/hour' -> 'XS';  'M - 5.4 credits/hour' -> 'M';  'XS' -> 'XS'.
    """
    head = (warehouse_label or "").split(" - ", 1)[0].split(" ", 1)[0]
    return norm_size(head) or head.upper()


# ── calc-block navigation ─────────────────────────────────────────────────── #

def has_calc(pricing: dict) -> bool:
    """True when a usable native calc block is present."""
    calc = (pricing or {}).get("calc") or {}
    return bool(calc.get("pricing"))


def _calc(pricing: dict) -> dict:
    return (pricing or {}).get("calc") or {}


def price_type(pricing: dict, name: str):
    """Return the ``data`` payload for a named priceType, or None."""
    for pt in _calc(pricing).get("pricing") or []:
        if pt.get("priceType") == name:
            return pt.get("data")
    return None


def _region_match(want: str, have: str) -> bool:
    if want is None or have is None:
        return False
    return want.strip().lower() == have.strip().lower()


def _cloud_region_rows(data, cloud: str, region: str):
    """Yield the innermost rows for a cloud+region in a cloud→region nested block."""
    cloud_n = norm_cloud(cloud)
    for c in data or []:
        if c.get("cloud") not in (cloud_n, cloud, "All"):
            continue
        for r in c.get("data") or []:
            if _region_match(region, r.get("region")) or r.get("region") == "All":
                return r.get("data") or []
    return []


# ── Credit / storage / AI-credit rates ────────────────────────────────────── #

def credit_rate(pricing: dict, cloud: str, region: str, edition: str) -> Optional[float]:
    """On-demand credit $/credit for cloud/region/edition (productFamily2)."""
    rows = _cloud_region_rows(price_type(pricing, "Credit On Demand"), cloud, region)
    ed = norm_edition(edition)
    for row in rows:
        if row.get("productFamily2") == ed:
            v = row.get("listPrice")
            return float(v) if v is not None else None
    return None


def storage_rate(pricing: dict, cloud: str, region: str) -> Optional[float]:
    """On-demand capacity storage $/TB/month for cloud/region."""
    rows = _cloud_region_rows(price_type(pricing, "Storage"), cloud, region)
    for row in rows:
        if row.get("productFamily2") == "Capacity Storage":
            v = row.get("listPrice")
            return float(v) if v is not None else None
    # Some regions list a single storage row without the family label.
    if rows:
        v = rows[0].get("listPrice")
        return float(v) if v is not None else None
    return None


def ai_credit_rates(pricing: dict) -> dict:
    """Return ``{"regional": <rate>, "global": <rate>}`` from the AI Credit type."""
    out = {"regional": None, "global": None}
    data = price_type(pricing, "AI Credit") or []
    for c in data:
        for r in c.get("data") or []:
            for fam in r.get("data") or []:
                name = (fam.get("productFamily2") or "").strip().lower()
                rows = fam.get("data") or []
                if name in out and rows:
                    v = rows[0].get("listPrice")
                    out[name] = float(v) if v is not None else None
    return out


def ai_credit_rate(pricing: dict, tier: str = "regional") -> Optional[float]:
    """Single AI-credit rate for ``tier`` ('regional' | 'global')."""
    return ai_credit_rates(pricing).get((tier or "regional").strip().lower())


# ── Warehouse credits/hour ─────────────────────────────────────────────────── #

def _flat_wh_credits(data, size: str) -> Optional[float]:
    want = norm_size(size)
    for w in data or []:
        if _size_of(w.get("warehouse", "")) == want:
            v = w.get("creditsPerHour")
            return float(v) if v is not None else None
    return None


def warehouse_credits(
    pricing: dict,
    size: str,
    gen: int = 1,
    warehouse_type: str = "standard",
    memory_config: Optional[str] = None,
    cloud: Optional[str] = None,
) -> Optional[float]:
    """Credits/hour for a warehouse of the given size and configuration.

    - ``warehouse_type='standard'``, ``gen=1``: STANDARD_GEN_1 (flat, XS–6XL).
    - ``warehouse_type='standard'``, ``gen=2``: STANDARD_GEN_2 (per-cloud, XS–4XL;
      ``cloud`` selects the price column, defaulting to AWS).
    - ``warehouse_type='snowpark'``: SNOWPARK (flat, XS–4XL; ``memory_config``
      selects the memoryConfiguration qualifier, defaulting to MEMORY_1X).

    Returns None if the size/config is unavailable.
    """
    ct = price_type(pricing, "computeTypes") or []
    wtype = (warehouse_type or "standard").strip().lower()

    def _by_type(t):
        for c in ct:
            if c.get("type") == t:
                return c.get("data")
        return None

    if wtype in ("snowpark", "snowpark_optimized", "snowpark-optimized"):
        data = _by_type("SNOWPARK") or []
        want = norm_size(size)
        mem = (memory_config or "MEMORY_1X").strip()
        for w in data:
            if _size_of(w.get("warehouse", "")) != want:
                continue
            quals = {q.get("label"): q.get("value") for q in w.get("additionalQualifiers") or []}
            if quals.get("memoryConfiguration", "MEMORY_1X") == mem:
                v = w.get("creditsPerHour")
                return float(v) if v is not None else None
        return None

    if int(gen) == 2:
        data = _by_type("STANDARD_GEN_2") or []
        cloud_n = norm_cloud(cloud) or "AWS"
        col = next((x for x in data if x.get("cloud") == cloud_n), None)
        if col is None and data:
            col = data[0]
        return _flat_wh_credits(col.get("data") if col else [], size)

    # default: Gen-1 standard (flat, cloud-agnostic)
    return _flat_wh_credits(_by_type("STANDARD_GEN_1"), size)


# ── SPCS compute ──────────────────────────────────────────────────────────── #

def _spcs_data(pricing: dict):
    for c in price_type(pricing, "computeTypes") or []:
        if c.get("type") == "SPCS":
            return c.get("data") or []
    return []


def spcs_families(pricing: dict) -> list:
    """Flat list of ``{instance_type, family, label, credits_per_hour}`` for SPCS."""
    out = []
    for grp in _spcs_data(pricing):
        itype = grp.get("instanceType")
        for fam in grp.get("data") or []:
            label = fam.get("instanceFamily", "")
            out.append({
                "instance_type": itype,
                "family": label.split(" - ", 1)[0].strip(),
                "label": label,
                "credits_per_hour": fam.get("creditsPerHour"),
            })
    return out


def spcs_credit(pricing: dict, family: str) -> Optional[float]:
    """Credits/hour for an SPCS instance family code (e.g. 'GPU_NV_S')."""
    if not family:
        return None
    want = family.strip().lower()
    for f in spcs_families(pricing):
        if f["family"].lower() == want:
            v = f["credits_per_hour"]
            return float(v) if v is not None else None
    return None


# ── AI / Cortex Code / Snowflake Intelligence token rates ──────────────────── #

def ai_token_rate(
    pricing: dict,
    price_type_name: str,
    function_name: str,
    model: Optional[str] = None,
    subtype: Optional[str] = None,
) -> Optional[float]:
    """creditConversionRate for a token line in an AI-style price type.

    Navigates ``priceType -> subTypeName -> functionName -> modelName``. ``model``
    matches ``modelName`` (use None to match a null-model function). ``subtype``
    optionally restricts to a single subTypeName.
    """
    data = price_type(pricing, price_type_name) or []
    for st in data:
        if subtype is not None and st.get("subTypeName") != subtype:
            continue
        for fn in st.get("data") or []:
            if fn.get("functionName") != function_name:
                continue
            for m in fn.get("data") or []:
                if m.get("modelName") == model:
                    v = m.get("creditConversionRate")
                    return float(v) if v is not None else None
    return None


def ai_models(
    pricing: dict,
    price_type_name: str,
    function_name: Optional[str] = None,
    subtype: Optional[str] = None,
) -> list:
    """Sorted unique non-null model names available for a price type/function."""
    seen = set()
    for st in price_type(pricing, price_type_name) or []:
        if subtype is not None and st.get("subTypeName") != subtype:
            continue
        for fn in st.get("data") or []:
            if function_name is not None and fn.get("functionName") != function_name:
                continue
            for m in fn.get("data") or []:
                name = m.get("modelName")
                if name:
                    seen.add(name)
    return sorted(seen)


# ── Regions (for dropdowns + edition availability) ─────────────────────────── #

def calc_regions(pricing: dict, cloud: Optional[str] = None) -> list:
    """List of region names from regions.json, optionally filtered to a cloud."""
    cloud_n = norm_cloud(cloud)
    out = []
    for c in _calc(pricing).get("regions") or []:
        if cloud_n and c.get("cloud") != cloud_n:
            continue
        for cont in c.get("data") or []:
            for r in cont.get("data") or []:
                name = r.get("region")
                if name:
                    out.append(name)
    return out


def region_product_families(pricing: dict, cloud: str, region: str) -> Optional[list]:
    """Editions (product_families) available for a cloud/region, or None if unknown."""
    cloud_n = norm_cloud(cloud)
    for c in _calc(pricing).get("regions") or []:
        if c.get("cloud") != cloud_n:
            continue
        for cont in c.get("data") or []:
            for r in cont.get("data") or []:
                if _region_match(region, r.get("region")):
                    return (r.get("data") or {}).get("product_families")
    return None
