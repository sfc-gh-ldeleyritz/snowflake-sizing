"""pricing_validator — cross-check a SIZING_SPEC's pricing rates against the master table.

Public surface:
    REGION_ALIASES: dict[str, str]
    lookup_credit_rate(pricing, cloud, region, edition) -> float | None
    lookup_storage_rate(pricing, cloud, region) -> float | None
    lookup_ai_credit_rate(pricing, cloud, region) -> float
    validate_pricing(spec, pricing) -> list[str]

All functions are pure; they never mutate their inputs and have no side effects.
"""
from __future__ import annotations

import pathlib
import sys

# calc_access lives in framework/; add to sys.path so the native-shape readers
# are importable whether this module is used via the renderer, the tests, or
# stand-alone. Falls back gracefully to the flattened tables if unavailable.
_FRAMEWORK_DIR = str(pathlib.Path(__file__).resolve().parent.parent / "framework")
if _FRAMEWORK_DIR not in sys.path:
    sys.path.insert(0, _FRAMEWORK_DIR)
try:
    import calc_access
except Exception:  # noqa: BLE001 (defensive: never block validation on import)
    calc_access = None  # type: ignore

# ── Region alias map ──────────────────────────────────────────────────────── #
# Maps spec region strings (which LLMs freely invent) to the canonical key
# used in snowflake_pricing_master.json.  Add new variants here as they appear.
REGION_ALIASES: dict[str, str] = {
    # AWS
    "US East1 (N. Virginia)":           "US East (Northern Virginia)",
    "US East 1 (N. Virginia)":          "US East (Northern Virginia)",
    "US East (N. Virginia)":            "US East (Northern Virginia)",
    "US East 1 (Northern Virginia)":    "US East (Northern Virginia)",
    "US West 2 (Oregon)":               "US West (Oregon)",
    "EU Frankfurt":                     "EU Frankfurt",          # exact — kept for explicitness
    "EU (Frankfurt)":                   "EU Frankfurt",
    "EU Dublin":                        "EU Dublin",
    "EU (Dublin)":                      "EU Dublin",
    "EU (Paris)":                       "EU (Paris)",
    # Azure
    "East US 2 (Virginia)":             "East US 2 (Virginia)",  # exact
    "East US (Virginia)":               "East US (Virginia)",
    # GCP
    "US Central1 (Iowa)":               "US Central 1 (Iowa)",
    "US Central 1 (Iowa)":              "US Central 1 (Iowa)",   # exact
    "US East4 (N. Virginia)":           "US East 4 (N. Virginia)",
    "Europe West4 (Netherlands)":       "Europe West 4 (Netherlands)",
    "Europe West 4 (Netherlands)":      "Europe West 4 (Netherlands)",
    "Europe West3 (Frankfurt)":         "Europe West 3 (Frankfurt)",
    "Europe West2 (London)":            "Europe West 2 (London)",
}

# Global enterprise credit rate (all US/standard regions). Used to classify
# regions as global-AI ($2.00) vs regional-AI ($2.20).
_GLOBAL_ENTERPRISE_RATE = 3.0


def _resolve_region(region: str) -> str:
    """Return the canonical pricing-table region string, or the original if unknown."""
    return REGION_ALIASES.get(region, region)


def _credit_row(pricing: dict, cloud: str, region: str) -> dict | None:
    """Return the credit_pricing row matching cloud+region, or None."""
    canon = _resolve_region(region)
    for row in (pricing.get("credit_pricing") or {}).get("data") or []:
        if row.get("cloud") == cloud and row.get("region") == canon:
            return row
    return None


def _storage_row(pricing: dict, cloud: str, region: str) -> dict | None:
    """Return the storage.standard row matching cloud+region, or None."""
    canon = _resolve_region(region)
    for row in ((pricing.get("storage") or {}).get("standard") or {}).get("data") or []:
        if row.get("cloud") == cloud and row.get("region") == canon:
            return row
    return None


def lookup_credit_rate(pricing: dict, cloud: str, region: str, edition: str) -> float | None:
    """Return the on-demand credit rate for cloud/region/edition, or None if unresolved.

    Prefers the live calculator block (pricing['calc']) when present, falling back
    to the flattened credit_pricing table. edition is case-insensitive and may use
    spaces or underscores (e.g. 'Business Critical', 'business_critical').
    """
    canon = _resolve_region(region)
    if calc_access is not None and calc_access.has_calc(pricing):
        rate = calc_access.credit_rate(pricing, cloud, canon, edition)
        if rate is not None:
            return rate
    row = _credit_row(pricing, cloud, region)
    if row is None:
        return None
    key = edition.lower().replace(" ", "_").replace("-", "_")
    val = row.get(key)
    return float(val) if val is not None else None


def lookup_storage_rate(pricing: dict, cloud: str, region: str) -> float | None:
    """Return the on-demand standard storage rate ($/TB/month), or None if unresolved."""
    canon = _resolve_region(region)
    if calc_access is not None and calc_access.has_calc(pricing):
        rate = calc_access.storage_rate(pricing, cloud, canon)
        if rate is not None:
            return rate
    row = _storage_row(pricing, cloud, region)
    if row is None:
        return None
    val = row.get("on_demand")
    return float(val) if val is not None else None


def lookup_ai_credit_rate(pricing: dict, cloud: str, region: str) -> float:
    """Return the on-demand AI credit rate for the given cloud/region.

    The two tiers (global $2.00, regional $2.20) are sourced from the live
    calculator's 'AI Credit' price type when present, else the flattened
    ai_credit_pricing table. The region is classified global vs regional by its
    enterprise credit rate (global base $3.00 => global AI rate).
    """
    if calc_access is not None and calc_access.has_calc(pricing):
        rates = calc_access.ai_credit_rates(pricing)
        global_rate = float(rates.get("global") or 2.0)
        regional_rate = float(rates.get("regional") or 2.2)
    else:
        on_demand = (pricing.get("ai_credit_pricing") or {}).get("on_demand") or {}
        global_rate = float(on_demand.get("global") or 2.0)
        regional_rate = float(on_demand.get("regional") or 2.2)

    row = _credit_row(pricing, cloud, region)
    if row is None:
        # Unknown region — default to global rate (conservative assumption)
        return global_rate

    enterprise_rate = row.get("enterprise")
    if enterprise_rate is None or float(enterprise_rate) <= _GLOBAL_ENTERPRISE_RATE:
        return global_rate
    return regional_rate


def validate_pricing(spec: dict, pricing: dict) -> list[str]:
    """Cross-check a spec's pricing meta fields against the master table.

    Returns a list of warning strings (empty = no issues found).
    Warnings are prefixed with '[pricing-check]' and include the field name,
    the spec value, the expected value, and the pricing-table source.

    Tolerates floating-point rounding up to 0.01.  Does NOT mutate spec or pricing.
    """
    meta = spec.get("meta") or {}
    cloud = meta.get("cloud") or ""
    region = meta.get("region") or ""
    edition = meta.get("edition") or ""

    warnings: list[str] = []
    _TOL = 0.01

    # Check whether the region can be resolved at all.
    canon = _resolve_region(region)
    row = _credit_row(pricing, cloud, region)
    if row is None:
        warnings.append(
            f"[pricing-check] UNRESOLVED_REGION: '{region}' not found in credit_pricing table "
            f"for cloud='{cloud}'. Add it to REGION_ALIASES or correct the spec. "
            f"Numeric rate checks skipped."
        )
        return warnings  # can't validate rates without a resolved region

    # ── edition availability (live regions.json product_families) ──────────── #
    # Only checks when the live calc block is present and the region is known to
    # regions.json; a missing region there is not an error (credit_pricing above
    # already gates resolvability).
    if calc_access is not None and calc_access.has_calc(pricing) and edition:
        fams = calc_access.region_product_families(pricing, cloud, canon)
        if fams:
            norm_ed = calc_access.norm_edition(edition)
            if norm_ed not in fams:
                warnings.append(
                    f"[pricing-check] EDITION_AVAILABILITY: '{edition}' is not offered in "
                    f"{cloud} / {canon} per the live calculator (available: {', '.join(fams)})"
                )

    # ── credit_rate ──────────────────────────────────────────────────────── #
    expected_cr = lookup_credit_rate(pricing, cloud, region, edition)
    actual_cr = meta.get("credit_rate")
    if expected_cr is not None and actual_cr is not None:
        # Skip the credit_rate check when a negotiated discount is active and the
        # pre-discount list_credit_rate matches the expected on-demand rate.
        discount = meta.get("discount") or {}
        list_cr = meta.get("list_credit_rate")
        discount_active = (
            discount.get("enabled")
            and list_cr is not None
            and abs(float(list_cr) - expected_cr) <= _TOL
        )
        if not discount_active and abs(float(actual_cr) - expected_cr) > _TOL:
            warnings.append(
                f"[pricing-check] credit_rate mismatch: spec={actual_cr}, "
                f"expected={expected_cr} "
                f"({cloud} / {canon} / {edition} on-demand)"
            )

    # ── storage_rate_per_tb ──────────────────────────────────────────────── #
    expected_st = lookup_storage_rate(pricing, cloud, region)
    actual_st = meta.get("storage_rate_per_tb")
    if expected_st is not None and actual_st is not None:
        if abs(float(actual_st) - expected_st) > _TOL:
            warnings.append(
                f"[pricing-check] storage_rate_per_tb mismatch: spec={actual_st}, "
                f"expected={expected_st} "
                f"({cloud} / {canon} standard on-demand)"
            )

    # ── ai_credit_rate ───────────────────────────────────────────────────── #
    # The pricing table has two on-demand tiers: global=$2.00, regional=$2.20.
    # SEs commonly use $2.00 for all standard regions including EU/APAC (all 5
    # real customer sizings do this). Accept any value in [2.00, 2.20] as valid
    # and only flag values clearly outside that range.
    ai_on_demand = (pricing.get("ai_credit_pricing") or {}).get("on_demand") or {}
    ai_lo = float(ai_on_demand.get("global") or 2.0)
    ai_hi = float(ai_on_demand.get("regional") or 2.2)
    actual_ai = meta.get("ai_credit_rate")
    if actual_ai is not None:
        if float(actual_ai) < ai_lo - _TOL or float(actual_ai) > ai_hi + _TOL:
            warnings.append(
                f"[pricing-check] ai_credit_rate out of range: spec={actual_ai}, "
                f"valid on-demand range=[${ai_lo}–${ai_hi}] "
                f"(AI Credit Pricing Table 2(b))"
            )

    return warnings
