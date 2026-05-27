#!/usr/bin/env python3
"""Verify that a generated sizing HTML will render non-zero dollar values.

Two-stage gate:

  1. Real-JS execution — invokes the sidecar `html-render-check.mjs` under
     Node, which extracts the inline <script> block, runs it inside a
     stubbed-DOM `vm` context, fires the DOMContentLoaded handler, and reports
     whether boot succeeded and what `kpi-tcv` textContent ended up. This is
     the source-of-truth gate: it exercises populate*Panel() / recalculate()
     exactly as the browser does, so a missing-but-template-required key
     (e.g. ai_cortex.document_ai) that throws a TypeError at boot is caught.

  2. Python TCV math — re-implements the warehouse-credit + storage portion
     of recalculate() in Python and confirms the math produces a non-zero
     TCV. This is a secondary sanity check that detects credit_rate=0,
     empty workloads, and ramps that schedule everything outside year 1.

Both gates must pass. The python math is also reported alongside the JS
result so divergence (>5%) is flagged.

Exit 0 if all input files pass both gates. Exit 1 if any fails, with the
reason printed.

Usage:
    python3 html-render-check.py path1.html [path2.html ...]
"""
import json
import pathlib
import re
import shutil
import subprocess
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


# ── Node sidecar invocation ────────────────────────────────────────────────── #

_THIS_DIR = pathlib.Path(__file__).resolve().parent
_NODE_SIDECAR = _THIS_DIR / "html-render-check.mjs"


def run_node_render_check(html_path):
    """Invoke html-render-check.mjs under Node for the given HTML file.

    Returns a dict with keys: ok, kpi_tcv, error, stack. If Node is missing
    or the sidecar fails to launch, returns a dict with ok=False and a
    descriptive error.
    """
    node_bin = shutil.which("node")
    if node_bin is None:
        return {
            "ok": False,
            "kpi_tcv": "$0",
            "error": (
                "Node.js is not on PATH — the JS render gate cannot run. "
                "Install Node 18+ (`brew install node`) and re-run."
            ),
            "stack": None,
        }

    if not _NODE_SIDECAR.exists():
        return {
            "ok": False,
            "kpi_tcv": "$0",
            "error": f"Sidecar missing: {_NODE_SIDECAR}",
            "stack": None,
        }

    try:
        proc = subprocess.run(
            [node_bin, str(_NODE_SIDECAR), str(html_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "kpi_tcv": "$0",
            "error": "Node sidecar timed out after 30s",
            "stack": None,
        }
    except OSError as exc:
        return {
            "ok": False,
            "kpi_tcv": "$0",
            "error": f"Failed to launch Node sidecar — {exc}",
            "stack": None,
        }

    if proc.returncode != 0:
        return {
            "ok": False,
            "kpi_tcv": "$0",
            "error": (
                f"Node sidecar exited {proc.returncode}: {proc.stderr.strip()}"
            ),
            "stack": None,
        }

    try:
        return json.loads(proc.stdout.strip())
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "kpi_tcv": "$0",
            "error": f"Sidecar produced invalid JSON: {exc}\n--stdout--\n{proc.stdout}",
            "stack": None,
        }


def parse_dollar(s):
    """Parse '$1,234,567' → 1234567.0, defensively. Empty / '$0' → 0.0."""
    if not s:
        return 0.0
    cleaned = s.replace("$", "").replace(",", "").strip()
    if not cleaned:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


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

    # ── Gate 1: Real-JS execution via Node sidecar ──────────────────────── #
    js_result = run_node_render_check(p)
    js_tcv = parse_dollar(js_result.get("kpi_tcv", "$0"))

    # ── Gate 2: Python TCV math ─────────────────────────────────────────── #
    year_data = compute_year_totals(spec)

    py_tcv       = sum(y["year_total"]   for y in year_data)
    total_cr     = sum(y["wh_credits"]   for y in year_data)
    yr1_total    = year_data[0]["year_total"]    if year_data else 0

    # Diagnosis helpers
    meta         = spec.get("meta", {})
    cr           = float(meta.get("credit_rate", 0))
    workloads    = spec.get("workloads", [])
    enabled_wls  = [w for w in workloads if w.get("hours_per_day", 0) > 0]

    # ── Failure paths ───────────────────────────────────────────────────── #

    if not js_result.get("ok", False):
        # The browser-equivalent JS execution either threw or produced $0.
        # This is the source-of-truth failure: the page will render as $0
        # in a real browser, regardless of what the Python math says.
        out = [f"{path_str}: FAILED"]
        err = js_result.get("error") or "unknown JS render failure"
        out.append(f"  JS render gate: {err}")
        stack = js_result.get("stack")
        if stack:
            # Trim to the first 3 frames — enough to locate the offending function.
            stack_lines = [ln for ln in stack.splitlines() if ln.strip()][:4]
            for ln in stack_lines:
                out.append(f"    {ln.strip()}")
        out.append(
            f"  → The page will render as $0 in a real browser. "
            f"Python TCV math computed {fmt(py_tcv)} but is not the "
            f"source of truth for what the user sees."
        )
        return False, out

    if py_tcv == 0 or yr1_total == 0:
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
            f"  Python TCV math: $0 — {reason_str}",
            f"  (JS render gate reported {js_result.get('kpi_tcv', '$0')})",
        ]

    # ── Divergence check (JS < Python) ──────────────────────────────────── #
    summary_lines = [f"{path_str}: PASS"]
    year_parts = "  ".join(
        f"Year {y['year']}: {fmt(y['year_total'])}" for y in year_data
    )
    summary_lines.append(f"  {year_parts}  Python TCV: {fmt(py_tcv)}")
    summary_lines.append(f"  JS render TCV: {js_result.get('kpi_tcv', '$0')}")

    if py_tcv > 0 and js_tcv > 0:
        # Python TCV models warehouse compute + storage only. JS TCV adds
        # serverless / AI / SPCS / OpenFlow / collaboration / data transfer.
        # JS is therefore expected to run higher; the only divergence worth
        # flagging is JS < Python (something that the Python math counted is
        # missing from the JS rendered total) — this should never happen
        # unless the renderer fails partway through.
        if js_tcv < py_tcv * 0.95:
            summary_lines.append(
                f"  [warn] JS render TCV ({fmt(js_tcv)}) is lower than "
                f"the Python warehouse-only TCV ({fmt(py_tcv)}) — the "
                "renderer may be omitting workload cost. Verify the page "
                "in a real browser."
            )

    summary_lines.append(
        f"  ({fmt(total_cr).replace('$','')} warehouse credits, "
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
