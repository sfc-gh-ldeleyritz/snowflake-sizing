#!/usr/bin/env python3
"""Python port of the JS sizing math used by proposal-template.html.

This is the authoritative source for the drift-prone TCV components. It covers
the full compute stack: warehouse compute, serverless, AI/Cortex, storage, and
the "other" categories (SPCS, OpenFlow + OpenFlow-Oracle, data-transfer +
PrivateLink, collaboration, and replication/DR). The HTML live-recalc JS is kept
field-for-field and formula-for-formula in sync with this module so the
Python-injected first-load totals never drift from JS recalculation.

Note: SPCS/OpenFlow/collaboration are keyed to the schema field names
(instance_family/num_instances, warehouse_size/rows_per_day_M,
reader_accounts/native_apps/marketplace) and apply the credit rate, fixing an
earlier divergence where the JS read non-schema fields and added raw credits to
dollar totals.

Public surface:

    compute_core_totals(spec, pricing) -> dict

The returned dict has shape:

    {
      "schema_version": 1,
      "computed_at": "<UTC ISO-8601>",
      "computed_by": "framework/compute_totals.py",
      "scope": "warehouse | serverless | ai | storage | spcs | openflow | transfer | collab | replication (full compute stack)",
      "warehouse_credits_per_year": [Y1, Y2, Y3, ...],
      "serverless_credits_per_year": [...],
      "ai_credits_per_year":         [...],
      "storage_active_tb_per_year":  [...],
      "compute_cost_per_year":       [...],   # warehouse_credits * credit_rate
      "serverless_cost_per_year":    [...],   # serverless_credits * credit_rate
      "ai_cost_per_year":            [...],   # ai_credits * ai_credit_rate
      "storage_cost_per_year":       [...],   # active_tb * storage_rate * 12
      "spcs_cost_per_year":          [...],   # spcs_credits * credit_rate (ramped)
      "openflow_cost_per_year":      [...],   # connector credits*cr (ramped) + Oracle licensing
      "data_transfer_cost_per_year": [...],   # transfer + PrivateLink dollars
      "collaboration_cost_per_year": [...],   # reader credits*cr + subscriptions (ramped)
      "replication_cost_per_year":   [...],   # compute + egress + replica storage
      "other_cost_per_year":         [...],   # sum of the five categories above
      "core_year_total":             [...],   # sum of all cost arrays
      "core_tcv":                    <float>  # sum across years
    }

The HTML template reads these values to render the headline KPIs on first
load instead of recomputing them in JS. Live recalculate() still runs JS
math for slider deltas; the per-year arrays stop the first-load drift.
"""
from __future__ import annotations

import datetime as _dt
import json
import pathlib
from typing import Optional

import calc_access  # native-shape rate accessors (framework/)

# ── JS-replica constants (must match proposal-template.html) ──────────────── #

# Gen-1 standard fallback table. Authoritative rates now come from the live
# calculator via calc_access.warehouse_credits(); this dict is the offline
# fallback used only when the merged pricing has no `calc` block (e.g. bare
# unit-test fixtures). Note it stops at 4XL: the calc accessor is what fixes
# the historical 5XL/6XL = 1-credit bug.
WH_CREDITS = {
    "XS": 1, "S": 2, "M": 4, "L": 8, "XL": 16,
    "2XL": 32, "3XL": 64, "4XL": 128,
    "X-Small": 1, "Small": 2, "Medium": 4, "Large": 8, "X-Large": 16,
    "2X-Large": 32, "3X-Large": 64, "4X-Large": 128,
}

RAMP_EXPONENTS = {
    "slowest": 4.0, "slow": 2.0, "linear": 1.0,
    "fast": 0.5, "fastest": 0.25, "manual": 0.0,
}

# Mirrors JS computeMultipliers map in calcServerlessCredits().
_SERVERLESS_COMPUTE_MULTIPLIERS = {
    "serverless_tasks": 0.9, "serverless_tasks_flex": 0.5, "serverless_alerts": 0.9,
    "clustered_tables": 2.0, "materialized_views": 2.0, "search_optimization": 2.0,
    "query_acceleration": 1.0, "replication": 2.0, "backup": 2.0,
    "failsafe_recovery": 0.9, "data_quality_monitoring": 2.0, "trust_center": 1.0,
    "table_optimization": 0.75, "storage_lifecycle_policy": 0.5, "copy_files": 2.0,
    "organization_usage": 1.0, "sensitive_data_classification": 0.9,
}

# Cortex_functions key -> pricing-data feature name (mirrors JS funcMap).
_CORTEX_FN_TO_FEATURE = {
    "ai_classify":   "AI_CLASSIFY",
    "ai_sentiment":  "AI Sentiment",
    "ai_summarize":  "Summarize",
    "ai_translate":  "AI_TRANSLATE",
    "ai_extract":    "AI_EXTRACT (arctic-extract)",
    "ai_transcribe": "AI_TRANSCRIBE",
}


# ── Core math ─────────────────────────────────────────────────────────────── #

def ramp_factor_for_month(dev_start: int, go_live: int, curve: str, m: int) -> float:
    if curve == "manual":
        return 1.0 if (dev_start == 1 and go_live == 1) else 0.0
    if m < dev_start:
        return 0.0
    if m >= go_live:
        return 1.0
    denom = go_live - dev_start + 1
    if denom <= 0:
        return 1.0
    exp = RAMP_EXPONENTS.get(curve, 1.0)
    f = ((m - dev_start + 1) / denom) ** exp
    return min(1.0, max(0.0, f))


def ramp_multiplier_for_year(dev_start: int, go_live: int, curve: str, year: int, growth: float = 0.0) -> float:
    """Average ramp factor across the 12 months in `year` (1-indexed), scaled by
    the cumulative annual-growth factor for years 2+.

    Mirrors the JS rampMultiplierForYear in assets/templates/proposal-template.html:
    year 1 averages the 12 monthly ramp factors; years 2+ are treated as at full
    capacity (avg = 1.0) and the result is multiplied by (1 + growth)**(year - 1).
    Keeping this in lockstep with the JS guarantees the build-time computed_totals
    equals the interactive render to the cent.
    """
    if year == 1:
        avg = sum(
            ramp_factor_for_month(dev_start, go_live, curve, m)
            for m in range(1, 13)
        ) / 12.0
    else:
        avg = 1.0
    return avg * ((1.0 + growth) ** (year - 1))


def default_ramp_multiplier_for_year(meta: dict, year: int, growth: Optional[float] = None) -> float:
    dev, go, curve = _resolve_ramp_window({}, meta)
    if growth is None:
        growth = _annual_growth(meta)
    return ramp_multiplier_for_year(dev, go, curve, year, growth)


def _resolve_ramp_window(w: dict, meta: dict) -> tuple:
    """Resolve (dev_start, go_live, curve) with the exact `!= null` precedence the
    JS rampMultiplierForYear uses: row value, then meta default, then 0 / 3 / linear.
    A literal 0 for dev_start is honoured (not treated as falsy), which is why this
    uses `is not None` rather than `or`."""
    dev = w.get("dev_start_month")
    if dev is None:
        dev = meta.get("default_dev_start_month")
    if dev is None:
        dev = 0
    go = w.get("go_live_month")
    if go is None:
        go = meta.get("default_go_live_month")
    if go is None:
        go = 3
    curve = w.get("ramp_curve") or meta.get("default_ramp_curve") or "linear"
    return int(dev), int(go), curve


def _annual_growth(meta: dict) -> float:
    """Resolve meta.annual_growth_rate, defaulting to 0.20 when absent (matches the
    JS default in proposal-template.html: `m.annual_growth_rate != null ? ... : 0.20`)."""
    g = meta.get("annual_growth_rate")
    return float(g) if g is not None else 0.20


def _ai_growth(meta: dict) -> float:
    """AI growth: meta.ai_growth_rate when set, else falls back to annual growth."""
    g = meta.get("ai_growth_rate")
    return float(g) if g is not None else _annual_growth(meta)


def wh_credits_per_hour(w: dict, pricing: Optional[dict] = None, cloud: Optional[str] = None) -> float:
    """Credits/hour for a workload's warehouse.

    Uses the live calculator (via calc_access) when ``pricing`` carries a ``calc``
    block (honouring gen 1/2, warehouse_type standard/snowpark and memory_config)
    and falls back to the static WH_CREDITS table otherwise.
    """
    size = w.get("size", "XS")
    if pricing is not None and calc_access.has_calc(pricing):
        rate = calc_access.warehouse_credits(
            pricing, size,
            gen=int(w.get("gen", 1) or 1),
            warehouse_type=(w.get("warehouse_type") or "standard"),
            memory_config=w.get("memory_config"),
            cloud=cloud,
        )
        if rate is not None:
            return rate
    return WH_CREDITS.get(size, 1)


def wh_monthly_credits(w: dict, pricing: Optional[dict] = None, cloud: Optional[str] = None) -> float:
    rate = wh_credits_per_hour(w, pricing, cloud)
    cmin = w.get("clusters_min", 1) or 0
    cmax = w.get("clusters_max", 1) or 0
    avg_clusters = (cmin + cmax) / 2.0
    return (
        rate
        * (w.get("hours_per_day", 0) or 0)
        * (w.get("days_per_month", 0) or 0)
        * avg_clusters
    )


def storage_active_tb(spec: dict, year: int) -> float:
    """Replicates JS storageForYear() exactly: base + time-travel + fail-safe."""
    st = spec.get("storage", {}).get("standard", {}) or {}
    raw = st.get("raw_tb_year1", 0) or 0
    comp = (st.get("compression_ratio") or 1) or 1
    growth = (st.get("annual_growth_pct", 0) or 0) / 100.0
    tt = st.get("time_travel_days", 1) or 1
    churn = (st.get("churn_rate_pct", 0) or 0) / 100.0
    base = raw / comp
    grown = base * ((1 + growth) ** (year - 1))
    tt_oh = grown * churn * (tt / 30.0)
    fs_oh = grown * churn * (7.0 / 30.0)
    return grown + tt_oh + fs_oh


# ── Serverless ────────────────────────────────────────────────────────────── #

def serverless_monthly_credits(spec: dict) -> float:
    sl = spec.get("serverless", {}) or {}
    total = 0.0

    def _on(key):
        f = sl.get(key)
        return isinstance(f, dict) and f.get("enabled")

    # Per-feature volume-priced rules (mirror JS lines 941-961).
    if _on("snowpipe"):
        total += (sl["snowpipe"].get("gb_per_month", 0) or 0) * 0.0037
    if _on("snowpipe_streaming"):
        total += (sl["snowpipe_streaming"].get("uncompressed_gb_per_month", 0) or 0) * 0.0037
    if _on("snowpipe_streaming_classic"):
        total += (sl["snowpipe_streaming_classic"].get("client_instances", 0) or 0) * 0.01 * 730
    if _on("open_catalog"):
        total += (sl["open_catalog"].get("requests_per_month_M", 0) or 0) * 0.5
    if _on("telemetry_data_ingest"):
        total += (sl["telemetry_data_ingest"].get("gb_per_month", 0) or 0) * 0.0212
    if _on("archive_storage_retrieval"):
        total += (sl["archive_storage_retrieval"].get("files_per_month", 0) or 0) / 1000 * 0.05
    if _on("archive_storage_write"):
        total += (sl["archive_storage_write"].get("files_per_month", 0) or 0) / 1000 * 0.05
    if _on("logging"):
        total += (sl["logging"].get("file_batches_per_month", 0) or 0) / 1000 * 0.28
    if _on("automated_refresh"):
        total += (sl["automated_refresh"].get("files_per_month", 0) or 0) / 1000 * 0.06
    if _on("hybrid_tables_requests"):
        f = sl["hybrid_tables_requests"]
        total += ((f.get("reads_gb_monthly", 0) or 0) / 30.0) + ((f.get("writes_gb_monthly", 0) or 0) / 7.5)

    # Compute-hour features.
    for key, mult in _SERVERLESS_COMPUTE_MULTIPLIERS.items():
        if _on(key):
            total += (sl[key].get("compute_hours_monthly", 0) or 0) * mult
    return total


# ── AI / Cortex ───────────────────────────────────────────────────────────── #

def _by_key(rows, key, value):
    for r in rows or []:
        if r.get(key) == value:
            return r
    return None


def ai_monthly_credits(spec: dict, pricing: dict) -> float:
    ai = spec.get("ai_cortex", {}) or {}
    feats = (pricing.get("ai_features") or {})
    cc_models = ((feats.get("cortex_complete") or {}).get("data") or [])
    si_models = ((feats.get("intelligence_agents_analyst") or {}).get("data") or [])
    other_feats = ((feats.get("other_ai_features") or {}).get("data") or [])
    ft_models = ((feats.get("fine_tuning") or {}).get("data") or [])
    util_funcs = ((feats.get("utility_functions") or {}).get("data") or [])

    def cc_rate(model, t):
        m = _by_key(cc_models, "model", model) or {}
        return m.get(t, 0) or 0

    def si_rate(model, t):
        m = _by_key(si_models, "model", model) or {}
        return m.get(t, 0) or 0

    def feat_rate(name):
        m = _by_key(other_feats, "feature", name) or {}
        return m.get("rate", 0) or 0

    def ft_rate(model, t):
        m = _by_key(ft_models, "model", model) or {}
        return m.get(t, 0) or 0

    def util_rate(name):
        m = _by_key(util_funcs, "function", name) or {}
        return m.get("rate", 0) or 0

    total = 0.0

    cc = ai.get("cortex_complete") or {}
    if cc.get("enabled"):
        total += (cc.get("monthly_input_tokens_M", 0) or 0) * cc_rate(cc.get("model"), "input")
        total += (cc.get("monthly_output_tokens_M", 0) or 0) * cc_rate(cc.get("model"), "output")

    for feat_key in ("cortex_agents", "snowflake_intelligence"):
        f = ai.get(feat_key) or {}
        if f.get("enabled"):
            model = f.get("model") or "claude-4-sonnet"
            total += (f.get("monthly_input_tokens_M", 0) or 0) * si_rate(model, "input")
            total += (f.get("monthly_output_tokens_M", 0) or 0) * si_rate(model, "output")
            total += (f.get("monthly_cache_write_tokens_M", 0) or 0) * si_rate(model, "cache_write")
            total += (f.get("monthly_cache_read_tokens_M", 0) or 0) * si_rate(model, "cache_read")

    cco = ai.get("cortex_code") or {}
    if cco:
        cc_model = cco.get("model") or "claude-4-sonnet"
        cc_in_rate = si_rate(cc_model, "input")
        surface_hit = False
        for surface in ("cli", "snowsight", "desktop"):
            s = cco.get(surface)
            if isinstance(s, dict) and s.get("enabled"):
                surface_hit = True
                tokens_M = (
                    (s.get("developers", 0) or 0)
                    * (s.get("queries_per_dev_per_day", 0) or 0)
                    * (s.get("avg_tokens_per_query", 0) or 0)
                    / 1_000_000
                    * 22
                )
                total += tokens_M * cc_in_rate
        # Flat format (schema-canonical per sizing_spec_schema.json additionalProperties:false)
        if not surface_hit and cco.get("enabled"):
            tokens_M = (
                (cco.get("developers", 0) or 0)
                * (cco.get("queries_per_dev_per_day", 0) or 0)
                * (cco.get("avg_tokens_per_query", 0) or 0)
                / 1_000_000
                * 22
            )
            total += tokens_M * cc_in_rate

    ca = ai.get("cortex_analyst") or {}
    if ca.get("enabled"):
        total += (ca.get("monthly_messages", 0) or 0) / 1000.0 * feat_rate("Cortex Analyst (API)")

    cs = ai.get("cortex_search") or {}
    if cs.get("enabled"):
        total += (cs.get("indexed_data_gb", 0) or 0) * feat_rate("Cortex Search")

    da = ai.get("document_ai") or {}
    if da.get("enabled"):
        total += (da.get("compute_hours_monthly", 0) or 0) * feat_rate("Document AI")

    apl = ai.get("ai_parse_document_layout") or {}
    if apl.get("enabled"):
        total += (apl.get("pages_per_month", 0) or 0) / 1000.0 * feat_rate("AI Parse Document - Layout")

    apo = ai.get("ai_parse_document_ocr") or {}
    if apo.get("enabled"):
        total += (apo.get("pages_per_month", 0) or 0) / 1000.0 * feat_rate("AI Parse Document - OCR")

    cft = ai.get("cortex_fine_tuning") or {}
    if cft.get("enabled"):
        model = cft.get("model") or "llama3.1-70b"
        total += (cft.get("training_tokens_M", 0) or 0) * ft_rate(model, "training")

    cf = ai.get("cortex_functions") or {}
    if isinstance(cf, dict):
        for key, feat_name in _CORTEX_FN_TO_FEATURE.items():
            f = cf.get(key)
            if isinstance(f, dict) and f.get("enabled"):
                total += (f.get("tokens_M_monthly", 0) or 0) * util_rate(feat_name)

    em = ai.get("embeddings") or {}
    if em.get("enabled"):
        # Hard-coded JS rate for embeddings (line 1068) - intentionally
        # not in pricing JSON; kept as constant to mirror exactly.
        total += (em.get("tokens_M_monthly", 0) or 0) * 0.05

    return total


# ── Other compute categories (SPCS / OpenFlow / transfer / collab / replication) ── #

# OpenFlow connector ingest sizing assumption: average uncompressed bytes per
# changed row for Snowpipe-Streaming volume. The schema carries rows/day, not GB,
# so this documented constant converts rows -> uncompressed GB. Mirrors the JS
# _OF_AVG_ROW_BYTES in proposal-template.html.
_OF_AVG_ROW_BYTES = 1024
_OF_SNOWPIPE_CREDITS_PER_GB = 0.0037  # mirrors serverless snowpipe_streaming rate


def _wh_credits_for_size(size: str, pricing: Optional[dict] = None, cloud: Optional[str] = None) -> float:
    """Gen-1 standard credits/hour for a warehouse size label (calc block or fallback)."""
    if pricing is not None and calc_access.has_calc(pricing):
        rate = calc_access.warehouse_credits(pricing, size, cloud=cloud)
        if rate is not None:
            return rate
    return WH_CREDITS.get(size, 1)


def spcs_monthly_credits(spec: dict, pricing: dict) -> float:
    """SPCS compute pool credits/month, summed across instances (schema-keyed)."""
    s = spec.get("spcs") or {}
    if not s.get("enabled"):
        return 0.0
    total = 0.0
    for inst in s.get("instances") or []:
        fam = inst.get("instance_family")
        rate = calc_access.spcs_credit(pricing, fam)
        if rate is None:
            rate = _spcs_credit_fallback(pricing, fam)
        total += (
            (rate or 0.0)
            * (inst.get("num_instances", 0) or 0)
            * (inst.get("hours_per_day", 0) or 0)
            * (inst.get("days_per_month", 0) or 0)
        )
    return total


def _spcs_credit_fallback(pricing: dict, family: str) -> Optional[float]:
    """Look up SPCS credits/hour from the static master tables when no calc block.

    Mirrors the JS fallback to PRICING_DATA.spcs (cpu/highmem/gpu/spcs_gen2),
    keyed by the same family codes the schema uses (e.g. 'CPU_X64_M').
    """
    if not family:
        return None
    want = family.strip().lower()
    spcs = pricing.get("spcs") or {}
    for group in ("cpu", "highmem", "gpu", "spcs_gen2"):
        for row in ((spcs.get(group) or {}).get("data") or []):
            if (row.get("family") or "").strip().lower() == want:
                v = row.get("credits_per_hour")
                return float(v) if v is not None else None
    return None


def openflow_connector_monthly_credits(spec: dict, pricing: dict, cloud: Optional[str] = None) -> float:
    """OpenFlow connector credits/month: warehouse MERGE + Snowpipe-Streaming ingest + runtime vCPU-hours.

    Warehouse MERGE = wh_credits(size) * warehouse_hours_monthly. Ingest converts
    rows_per_day_M -> uncompressed GB/month via _OF_AVG_ROW_BYTES, priced at the
    Snowpipe-Streaming rate. Runtime billing: vcpus * nodes * hours_monthly * 0.0225
    credits/vCPU-hr (Table 1(h)), read from pricing["openflow"].
    """
    of = spec.get("openflow") or {}
    if not of.get("enabled"):
        return 0.0

    of_pricing = pricing.get("openflow") or {}
    size_map = {s["name"]: s["vcpus"] for s in of_pricing.get("sizes") or []}
    if not size_map:
        size_map = {"Small": 1, "Medium": 4, "Large": 8}
    byoc_entry = next((d for d in (of_pricing.get("data") or []) if d.get("deployment") == "BYOC"), {})
    runtime_rate = float(byoc_entry.get("rate") or 0.0225)

    total = 0.0
    for inst in of.get("instances") or []:
        wh_size = inst.get("warehouse_size")
        wh_hours = inst.get("warehouse_hours_monthly", 0) or 0
        if wh_size and wh_hours:
            total += _wh_credits_for_size(wh_size, pricing, cloud) * wh_hours
        rows_m = inst.get("rows_per_day_M", 0) or 0
        monthly_data_gb = inst.get("monthly_data_gb", 0) or 0
        ingest_gb = monthly_data_gb if monthly_data_gb > 0 else (
            rows_m * 1_000_000 * 30 * _OF_AVG_ROW_BYTES / 1e9 if rows_m > 0 else 0
        )
        if ingest_gb:
            total += ingest_gb * _OF_SNOWPIPE_CREDITS_PER_GB
        # Runtime vCPU-hour billing (credits/vCPU-hr per Table 1(h))
        vcpus = size_map.get(inst.get("runtime_size") or "Medium", 4)
        nodes = inst.get("runtime_nodes", 1) or 1
        hours_m = inst.get("hours_monthly", 730) or 730
        total += vcpus * nodes * hours_m * runtime_rate
    return total


def openflow_oracle_cost_for_year(spec: dict, year: int) -> float:
    """OpenFlow-Oracle connector licensing $/year ($110/core/mo yrs 1-3, $40 after)."""
    oo = spec.get("openflow_oracle") or {}
    if not oo.get("enabled"):
        return 0.0
    cores = oo.get("licensed_cores", 0) or 0
    rate = 110 if year <= 3 else 40
    return cores * rate * 12


def transfer_monthly_cost(spec: dict) -> float:
    """Data-transfer + PrivateLink $/month (already dollars; mirrors calcTransferCost)."""
    dt = spec.get("data_transfer") or {}
    pl = spec.get("privatelink") or {}
    total = 0.0
    if dt.get("enabled"):
        pattern = dt.get("pattern")
        rate = 0.0 if pattern == "same_region" else (0.08 if pattern == "cross_region" else 0.154)
        total += (dt.get("tb_per_month", 0) or 0) * 1024 * rate
    if pl.get("enabled"):
        total += (pl.get("endpoints", 0) or 0) * 7.30
        total += (pl.get("tb_processed_monthly", 0) or 0) * 1024 * 0.01
    return total


def collaboration_monthly_cost(spec: dict, pricing: dict, cr: float, cloud: Optional[str] = None) -> float:
    """Collaboration $/month: reader-account credits*cr + native-app/marketplace subscriptions."""
    c = spec.get("collaboration") or {}
    total = 0.0
    ra = c.get("reader_accounts") or {}
    if ra.get("enabled"):
        rate = _wh_credits_for_size(ra.get("warehouse_size", "XS"), pricing, cloud)
        total += rate * (ra.get("hours_per_day", 0) or 0) * (ra.get("days_per_month", 0) or 0) * cr
    na = c.get("native_apps") or {}
    if na.get("enabled"):
        total += na.get("monthly_subscription", 0) or 0
    mp = c.get("marketplace") or {}
    if mp.get("enabled"):
        total += mp.get("monthly_subscription", 0) or 0
    return total


def replication_for_year(spec: dict, pricing: dict, year: int) -> dict:
    """Per-year replication cost (compute + egress + replica storage); ports calcReplicationForYear."""
    zero = {"compute_credits": 0.0, "compute_cost": 0.0, "egress_cost": 0.0,
            "storage_cost": 0.0, "total_cost": 0.0}
    rep = spec.get("replication") or {}
    if not rep or rep.get("enabled") is False:
        return zero
    cr = float((spec.get("meta") or {}).get("credit_rate", 0) or 0)
    yoy = (rep.get("yoy_pct") if rep.get("yoy_pct") is not None else 10) / 100.0
    growth = (rep.get("storage_growth_pct") if rep.get("storage_growth_pct") is not None else 15) / 100.0
    cred_per_tb = rep.get("compute_credits_per_TB") if rep.get("compute_credits_per_TB") is not None else 4
    storage_rate = rep.get("replica_storage_per_tb_per_month") if rep.get("replica_storage_per_tb_per_month") is not None else 23

    active_tb = rep.get("initial_TB", 0) or 0
    growth_tb = active_tb * growth
    change_tb = (rep.get("monthly_change_TB", 0) or 0) * 12
    for _y in range(2, year + 1):
        active_tb = active_tb + growth_tb
        growth_tb = growth_tb * (1 + yoy)
        change_tb = change_tb * (1 + yoy)
    avg_tb = active_tb + (growth_tb / 2)

    matrix = (pricing.get("replication") or {}).get("egress_matrix") or {}
    egress_rate = 0.0
    src, tgt = rep.get("source_region"), rep.get("target_region")
    if src and tgt and isinstance(matrix.get(src), dict) and isinstance(matrix[src].get(tgt), (int, float)):
        egress_rate = matrix[src][tgt]

    basis_tb = (active_tb + growth_tb + change_tb) if year == 1 else (growth_tb + change_tb)
    compute_credits = basis_tb * cred_per_tb
    compute_cost = compute_credits * cr
    egress_cost = basis_tb * egress_rate
    storage_cost = avg_tb * storage_rate * 12
    return {
        "compute_credits": compute_credits,
        "compute_cost": compute_cost,
        "egress_cost": egress_cost,
        "storage_cost": storage_cost,
        "total_cost": compute_cost + egress_cost + storage_cost,
    }


# ── Public entry point ────────────────────────────────────────────────────── #

def compute_core_totals(spec: dict, pricing: dict) -> dict:
    meta = spec.get("meta", {}) or {}
    years = int(meta.get("contract_years", 3) or 3)
    cr = float(meta.get("credit_rate", 0) or 0)
    ai_cr = float(meta.get("ai_credit_rate", cr) or cr)
    sr = float(meta.get("storage_rate_per_tb", 0) or 0)
    workloads = spec.get("workloads", []) or []
    ag = _annual_growth(meta)
    ai_g = _ai_growth(meta)

    sl_monthly = serverless_monthly_credits(spec)
    ai_monthly = ai_monthly_credits(spec, pricing)
    cloud = meta.get("cloud")
    spcs_monthly = spcs_monthly_credits(spec, pricing)
    of_conn_monthly = openflow_connector_monthly_credits(spec, pricing, cloud)
    transfer_monthly = transfer_monthly_cost(spec)
    collab_monthly = collaboration_monthly_cost(spec, pricing, cr, cloud)

    wh_credits_yr = []
    sl_credits_yr = []
    ai_credits_yr = []
    st_tb_yr = []
    compute_cost_yr = []
    sl_cost_yr = []
    ai_cost_yr = []
    st_cost_yr = []
    spcs_cost_yr = []
    of_cost_yr = []
    transfer_cost_yr = []
    collab_cost_yr = []
    repl_cost_yr = []
    other_cost_yr = []
    core_total_yr = []

    for y in range(1, years + 1):
        wh_credits = 0.0
        for w in workloads:
            dev, go, curve = _resolve_ramp_window(w, meta)
            g = float(w["growth_rate"]) if w.get("growth_rate") is not None else ag
            wh_credits += (
                wh_monthly_credits(w, pricing, meta.get("cloud")) * 12
                * ramp_multiplier_for_year(dev, go, curve, y, g)
            )
        # Default-window ramp for the non-workload categories. Serverless / SPCS /
        # OpenFlow / collaboration grow on meta.annual_growth_rate; AI grows on its
        # own ai_growth_rate (falling back to annual when unset). Mirrors the JS
        # defRamp / aiRamp split in computeYearData.
        def_ramp = default_ramp_multiplier_for_year(meta, y, ag)
        ai_ramp = default_ramp_multiplier_for_year(meta, y, ai_g)
        sl_credits = sl_monthly * 12 * def_ramp
        ai_credits = ai_monthly * 12 * ai_ramp
        st_tb = storage_active_tb(spec, y)

        compute_cost = wh_credits * cr
        sl_cost = sl_credits * cr
        ai_cost = ai_credits * ai_cr
        st_cost = st_tb * sr * 12

        # Other compute categories (ramped on the meta-default window where
        # adoption-sensitive; transfer + Oracle licensing are not ramped).
        spcs_cost = spcs_monthly * 12 * def_ramp * cr
        of_cost = of_conn_monthly * 12 * def_ramp * cr + openflow_oracle_cost_for_year(spec, y)
        transfer_cost = transfer_monthly * 12
        collab_cost = collab_monthly * 12 * def_ramp
        repl_cost = replication_for_year(spec, pricing, y)["total_cost"]
        other_cost = spcs_cost + of_cost + transfer_cost + collab_cost + repl_cost

        core_total = compute_cost + sl_cost + ai_cost + st_cost + other_cost

        wh_credits_yr.append(round(wh_credits, 2))
        sl_credits_yr.append(round(sl_credits, 2))
        ai_credits_yr.append(round(ai_credits, 2))
        st_tb_yr.append(round(st_tb, 4))
        compute_cost_yr.append(round(compute_cost, 2))
        sl_cost_yr.append(round(sl_cost, 2))
        ai_cost_yr.append(round(ai_cost, 2))
        st_cost_yr.append(round(st_cost, 2))
        spcs_cost_yr.append(round(spcs_cost, 2))
        of_cost_yr.append(round(of_cost, 2))
        transfer_cost_yr.append(round(transfer_cost, 2))
        collab_cost_yr.append(round(collab_cost, 2))
        repl_cost_yr.append(round(repl_cost, 2))
        other_cost_yr.append(round(other_cost, 2))
        core_total_yr.append(round(core_total, 2))

    return {
        "schema_version": 1,
        "computed_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "computed_by": "framework/compute_totals.py",
        "scope": "warehouse | serverless | ai | storage | spcs | openflow | transfer | collab | replication (full compute stack)",
        "warehouse_credits_per_year": wh_credits_yr,
        "serverless_credits_per_year": sl_credits_yr,
        "ai_credits_per_year": ai_credits_yr,
        "storage_active_tb_per_year": st_tb_yr,
        "compute_cost_per_year": compute_cost_yr,
        "serverless_cost_per_year": sl_cost_yr,
        "ai_cost_per_year": ai_cost_yr,
        "storage_cost_per_year": st_cost_yr,
        "spcs_cost_per_year": spcs_cost_yr,
        "openflow_cost_per_year": of_cost_yr,
        "data_transfer_cost_per_year": transfer_cost_yr,
        "collaboration_cost_per_year": collab_cost_yr,
        "replication_cost_per_year": repl_cost_yr,
        "other_cost_per_year": other_cost_yr,
        "core_year_total": core_total_yr,
        "core_tcv": round(sum(core_total_yr), 2),
    }


def load_pricing(plugin_root: Optional[pathlib.Path] = None) -> dict:
    """Load assets/snowflake_pricing_master.json. Helper for CLI use."""
    if plugin_root is None:
        plugin_root = pathlib.Path(__file__).resolve().parent.parent
    path = plugin_root / "assets" / "snowflake_pricing_master.json"
    return json.loads(path.read_text(encoding="utf-8"))
