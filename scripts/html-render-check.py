#!/usr/bin/env python3
"""Verify that a generated sizing HTML will render non-zero dollar values.

Extracts the embedded SIZING_SPEC JSON from the HTML, then runs a Python
replica of the JS recalculate() engine to compute Year 1 / Year 2 / Year 3
compute + storage costs and the overall TCV.

Exit 0 if TCV > 0 and Year 1 total > 0 for every input file.
Exit 1 if any file computes $0 or cannot be parsed, with reasons printed.

Usage:
    python3 html-render-check.py path1.html [path2.html ...]
"""
import json
import pathlib
import re
import sys

# ── JS-replica constants ───────────────────────────────────────────────────── #

WH_CREDITS = {
    "XS": 1, "S": 2, "M": 4, "L": 8, "XL": 16,
    "2XL": 32, "3XL": 64, "4XL": 128,
    # Full-name aliases used in the template
    "X-Small": 1, "Small": 2, "Medium": 4, "Large": 8, "X-Large": 16,
    "2X-Large": 32, "3X-Large": 64, "4X-Large": 128,
}

RAMP_EXPONENTS = {
    "slowest": 4.0, "slow": 2.0, "linear": 1.0,
    "fast": 0.5, "fastest": 0.25, "manual": 0.0,
}

# ── Core math replicas ─────────────────────────────────────────────────────── #

def ramp_factor_for_month(dev_start, go_live, curve, m):
    """Replica of JS rampFactorForMonth()."""
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


def ramp_multiplier_for_year(dev_start, go_live, curve, year):
    """Replica of JS rampMultiplierForYear() — average factor over 12 months."""
    offset = (year - 1) * 12
    total = sum(
        ramp_factor_for_month(dev_start, go_live, curve, offset + m)
        for m in range(1, 13)
    )
    return total / 12.0


def wh_monthly_credits(w):
    """Replica of JS whMonthlyCredits(w)."""
    rate = WH_CREDITS.get(w.get("size", "XS"), 1)
    clusters_min = w.get("clusters_min", 1)
    clusters_max = w.get("clusters_max", 1)
    avg_clusters = (clusters_min + clusters_max) / 2.0
    return rate * w.get("hours_per_day", 0) * w.get("days_per_month", 0) * avg_clusters


def storage_for_year(spec, year):
    """Simplified replica of JS storageForYear() — returns active TB."""
    st = spec.get("storage", {}).get("standard", {})
    if not st:
        return 0.0
    raw_tb = st.get("raw_tb_year1", 0)
    comp = st.get("compression_ratio", 3) or 3
    growth = (st.get("annual_growth_pct", 0) or 0) / 100.0
    tt = st.get("time_travel_days", 1) or 1
    active_tb = (raw_tb / comp) * (1 + tt / 7) * ((1 + growth) ** (year - 1))
    return active_tb


def compute_year_totals(spec):
    """
    Compute per-year cost breakdown, mirroring JS recalculate().

    Returns list of dicts: { year, wh_credits, compute_cost, storage_cost, year_total }
    Only warehouse compute and storage are replicated here — serverless, AI,
    SPCS, and OpenFlow are not included (they are often zero or small).
    """
    meta = spec.get("meta", {})
    years = int(meta.get("contract_years", 3))
    cr = float(meta.get("credit_rate", 0))
    sr = float(meta.get("storage_rate_per_tb", 0))

    # Default ramp for storage growth
    default_dev = int(meta.get("default_dev_start_month", 2))
    default_go  = int(meta.get("default_go_live_month", 11))

    workloads = spec.get("workloads", [])
    year_data = []

    for y in range(1, years + 1):
        wh_credits = 0.0
        for w in workloads:
            monthly = wh_monthly_credits(w)
            dev_start = int(w.get("dev_start_month", default_dev))
            go_live   = int(w.get("go_live_month",   default_go))
            curve     = w.get("ramp_curve", "linear")
            ramp      = ramp_multiplier_for_year(dev_start, go_live, curve, y)
            wh_credits += monthly * 12 * ramp

        compute_cost  = wh_credits * cr
        storage_cost  = storage_for_year(spec, y) * sr * 12
        year_total    = compute_cost + storage_cost

        year_data.append({
            "year":         y,
            "wh_credits":   wh_credits,
            "compute_cost": compute_cost,
            "storage_cost": storage_cost,
            "year_total":   year_total,
        })

    return year_data


# ── HTML parsing ───────────────────────────────────────────────────────────── #

_SPEC_RE = re.compile(
    r'/\* __SIZING_SPEC_BEGIN__ \*/\s*const SIZING_SPEC\s*=\s*(\{.*?\});\s*'
    r'/\* __SIZING_SPEC_END__ \*/',
    re.DOTALL,
)


def extract_spec(html):
    """Return parsed SIZING_SPEC dict, or raise ValueError."""
    m = _SPEC_RE.search(html)
    if not m:
        raise ValueError(
            "__SIZING_SPEC_BEGIN__ / __SIZING_SPEC_END__ markers not found — "
            "the __SIZING_SPEC__ token was probably not substituted during HTML generation"
        )
    return json.loads(m.group(1))


def fmt(n):
    return f"${n:,.0f}"


# ── Main ───────────────────────────────────────────────────────────────────── #

def check_file(path_str):
    """Return (passed: bool, lines: list[str])."""
    lines = []
    p = pathlib.Path(path_str)

    if not p.exists() or not p.is_file():
        return False, [f"{path_str}: file not found"]

    try:
        html = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return False, [f"{path_str}: read error — {exc}"]

    try:
        spec = extract_spec(html)
    except (ValueError, json.JSONDecodeError) as exc:
        return False, [f"{path_str}: FAILED — {exc}"]

    # Validate workloads key exists (spec-validate.py catches this too, but
    # we give a clear message here so the render-check is self-contained)
    if "workloads" not in spec:
        return False, [
            f"{path_str}: FAILED — SIZING_SPEC.workloads missing "
            "(check for 'warehouses' key instead)"
        ]

    year_data = compute_year_totals(spec)
    years = len(year_data)

    tcv          = sum(y["year_total"]   for y in year_data)
    total_cr     = sum(y["wh_credits"]   for y in year_data)
    yr1_compute  = year_data[0]["compute_cost"]  if year_data else 0
    yr1_total    = year_data[0]["year_total"]    if year_data else 0

    # Diagnosis helpers
    meta         = spec.get("meta", {})
    cr           = float(meta.get("credit_rate", 0))
    workloads    = spec.get("workloads", [])
    enabled_wls  = [w for w in workloads if w.get("hours_per_day", 0) > 0]

    if tcv == 0 or yr1_total == 0:
        reasons = []
        if cr == 0:
            reasons.append("meta.credit_rate = 0 — pricing lookup may have failed")
        if len(workloads) == 0:
            reasons.append("workloads array is empty")
        elif len(enabled_wls) == 0:
            reasons.append("all workloads have hours_per_day = 0")
        if total_cr == 0 and workloads:
            reasons.append(
                "all workloads computed 0 credits — check ramp dates "
                "(dev_start_month / go_live_month) and hours_per_day"
            )
        reason_str = "; ".join(reasons) if reasons else "unknown cause"
        return False, [
            f"{path_str}: FAILED",
            f"  TCV = $0 — {reason_str}",
        ]

    # Success — print the cost summary
    summary_lines = [f"{path_str}: PASS"]
    year_parts = "  ".join(
        f"Year {y['year']}: {fmt(y['year_total'])}" for y in year_data
    )
    summary_lines.append(f"  {year_parts}  TCV: {fmt(tcv)}")
    summary_lines.append(
        f"  ({fmt(total_cr).replace('$','')} total warehouse credits, "
        f"cr=${cr:.2f}/credit)"
    )
    return True, summary_lines


def main():
    args = sys.argv[1:]
    if not args:
        print("usage: html-render-check.py path1.html [path2.html ...]",
              file=sys.stderr)
        sys.exit(2)

    any_failed = False
    for path in args:
        passed, lines = check_file(path)
        label = "html-render-check: PASS" if passed else "html-render-check: FAILED"
        print(label)
        for line in lines:
            print(line)
        if not passed:
            any_failed = True

    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
