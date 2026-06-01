"""charts.py - Native python-pptx chart builders from computed_totals arrays.

Each helper returns a (chart, chart_frame) by mutating an existing slide.
All charts are NATIVE editable PowerPoint charts (CategoryChartData /
XL_CHART_TYPE) - not images.
"""
from __future__ import annotations

from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.util import Inches, Pt

from . import brand

# Per-slice palette for the doughnut chart (workload mode can have many slices,
# so this extends beyond the 4-series stacked-column palette).
_DONUT_PALETTE = [
    brand.rgb(brand.COLORS["snowflakeBlue"]),
    brand.rgb(brand.COLORS["starBlue"]),
    brand.rgb(brand.COLORS["valenciaOrange"]),
    brand.rgb(brand.COLORS["purpleMoon"]),
    brand.rgb(brand.COLORS["firstLight"]),
    brand.rgb(brand.COLORS["navy"]),
]


def _apply_series_colors(chart, colors: list) -> None:
    """Apply brand colors to each series fill."""
    for i, series in enumerate(chart.series):
        color = colors[i % len(colors)]
        fill = series.format.fill
        fill.solid()
        fill.fore_color.rgb = color


def _color_points(chart, colors: list) -> None:
    """Color each DATA POINT of the first series (for pie/doughnut charts).

    Pie and doughnut charts have a single series whose slices are colored
    per-POINT, not per-series - so _apply_series_colors does not work here.
    """
    try:
        points = chart.plots[0].series[0].points
    except (IndexError, AttributeError):
        return
    for i, point in enumerate(points):
        fill = point.format.fill
        fill.solid()
        fill.fore_color.rgb = colors[i % len(colors)]


def _style_chart(chart) -> None:
    """Apply common chart styling: remove legend border, set font."""
    plot = chart.plots[0]
    # Style value axis (Y axis)
    try:
        va = chart.value_axis
        va.tick_labels.font.size = Pt(9)
        va.tick_labels.font.color.rgb = brand.DGRAY
        va.has_major_gridlines = True
    except Exception:
        pass
    # Style category axis (X axis)
    try:
        ca = chart.category_axis
        ca.tick_labels.font.size = Pt(9)
        ca.tick_labels.font.color.rgb = brand.DGRAY
    except Exception:
        pass
    # Legend
    try:
        chart.has_legend = True
        chart.legend.font.size = Pt(9)
        chart.legend.font.color.rgb = brand.DGRAY
        chart.legend.include_in_layout = False
    except Exception:
        pass
    # Chart title
    try:
        chart.has_title = False
    except Exception:
        pass


def add_year_by_year_chart(
    slide,
    computed_totals: dict,
    left=None, top=None, width=None, height=None,
) -> object:
    """Add a stacked column chart of per-year costs to *slide*.

    Series: Compute, Serverless, AI, Storage, Other (from computed_totals arrays).
    Returns the Chart object.
    """
    years = len(computed_totals.get("core_year_total", []))
    categories = [f"Year {y}" for y in range(1, years + 1)]

    chart_data = CategoryChartData()
    chart_data.categories = categories

    series_defs = [
        ("Compute",    "compute_cost_per_year"),
        ("Serverless", "serverless_cost_per_year"),
        ("AI/Cortex",  "ai_cost_per_year"),
        ("Storage",    "storage_cost_per_year"),
        ("Other",      "other_cost_per_year"),
    ]
    for label, key in series_defs:
        values = computed_totals.get(key, [0] * years)
        chart_data.add_series(label, [round(v, 2) for v in values])

    # Default geometry if not specified (10.0" x 5.625" slide content area).
    l = left   if left   is not None else Inches(0.4)
    t = top    if top    is not None else Inches(0.7)
    w = width  if width  is not None else Inches(9.2)
    h = height if height is not None else Inches(4.3)

    chart_frame = slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_STACKED, l, t, w, h, chart_data
    )
    chart = chart_frame.chart
    _apply_series_colors(chart, brand.CHART_SERIES_COLORS)
    _style_chart(chart)
    return chart


def add_cost_line_chart(
    slide,
    computed_totals: dict,
    left=None, top=None, width=None, height=None,
) -> object:
    """Add a line chart of total core cost per year to *slide*.

    Single series: Total (core_year_total).
    Returns the Chart object.
    """
    years = len(computed_totals.get("core_year_total", []))
    categories = [f"Year {y}" for y in range(1, years + 1)]

    chart_data = CategoryChartData()
    chart_data.categories = categories
    totals = computed_totals.get("core_year_total", [0] * years)
    chart_data.add_series("Total Cost ($)", [round(v, 2) for v in totals])

    l = left   if left   is not None else Inches(9.2)
    t = top    if top    is not None else Inches(1.4)
    w = width  if width  is not None else Inches(3.8)
    h = height if height is not None else Inches(4.8)

    chart_frame = slide.shapes.add_chart(
        XL_CHART_TYPE.LINE_MARKERS, l, t, w, h, chart_data
    )
    chart = chart_frame.chart
    _apply_series_colors(chart, [brand.BLUE])
    _style_chart(chart)
    return chart


def _style_donut(chart) -> None:
    """Doughnut styling: no title, right-hand legend, percentage data labels."""
    try:
        chart.has_title = False
    except Exception:
        pass
    try:
        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.RIGHT
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(9)
        chart.legend.font.color.rgb = brand.DGRAY
    except Exception:
        pass
    try:
        dl = chart.plots[0].data_labels
        dl.number_format = "0%"
        dl.number_format_is_linked = False
        dl.show_percentage = True
        dl.show_value = False
        dl.show_category_name = False
        dl.font.size = Pt(9)
        dl.font.color.rgb = brand.DGRAY
    except Exception:
        pass


def _workload_donut_data(spec: dict, pricing: dict, computed_totals: dict):
    """Compute (labels, values, mode) for the cost-mix doughnut.

    Primary "workload" mode: each workload's Year-1 warehouse (compute) credits,
    so the slices show how compute is distributed across workloads.  Falls back to
    "category" mode - the Compute/Serverless/AI/Storage cost mix across the whole
    term - when there are fewer than two workloads with non-zero Year-1 credits
    (a single slice is meaningless).  Lazy-imports the math helpers so charts.py
    carries no import-order dependency on framework/.
    """
    from compute_totals import wh_monthly_credits, ramp_multiplier_for_year

    meta = spec.get("meta", {}) or {}
    cloud = meta.get("cloud")
    workloads = spec.get("workloads", []) or []

    labels: list[str] = []
    values: list[float] = []
    for i, w in enumerate(workloads):
        dev = int(w.get("dev_start_month", meta.get("default_dev_start_month", 2)) or 2)
        go = int(w.get("go_live_month", meta.get("default_go_live_month", 11)) or 11)
        curve = w.get("ramp_curve", meta.get("default_ramp_curve", "linear")) or "linear"
        credits = wh_monthly_credits(w, pricing, cloud) * 12 * ramp_multiplier_for_year(
            dev, go, curve, 1
        )
        if credits > 0:
            labels.append(w.get("label") or w.get("id") or f"Workload {i + 1}")
            values.append(round(credits, 2))

    if len(labels) >= 2:
        return labels, values, "workload"

    # Fallback: category cost mix across the term.
    cats = [
        ("Compute", "compute_cost_per_year"),
        ("Serverless", "serverless_cost_per_year"),
        ("AI/Cortex", "ai_cost_per_year"),
        ("Storage", "storage_cost_per_year"),
        ("Other", "other_cost_per_year"),
    ]
    labels, values = [], []
    for label, key in cats:
        total = sum(computed_totals.get(key, []) or [])
        if total > 0:
            labels.append(label)
            values.append(round(total, 2))
    if not values:
        labels, values = ["No cost data"], [1.0]
    return labels, values, "category"


def add_workload_donut(
    slide,
    spec: dict,
    pricing: dict,
    computed_totals: dict,
    left=None, top=None, width=None, height=None,
) -> tuple:
    """Add a cost-mix doughnut chart to *slide*.

    Returns ``(chart, mode)`` where *mode* is ``"workload"`` (slices are per-
    workload Year-1 compute credits) or ``"category"`` (slices are the
    Compute/Serverless/AI/Storage cost mix); the caller uses *mode* to set an
    accurate title (workload mode is compute-only).
    """
    labels, values, mode = _workload_donut_data(spec, pricing, computed_totals)

    chart_data = CategoryChartData()
    chart_data.categories = labels
    chart_data.add_series("Share", values)

    l = left   if left   is not None else Inches(1.7)
    t = top    if top    is not None else Inches(1.35)
    w = width  if width  is not None else Inches(6.6)
    h = height if height is not None else Inches(3.5)

    chart_frame = slide.shapes.add_chart(
        XL_CHART_TYPE.DOUGHNUT, l, t, w, h, chart_data
    )
    chart = chart_frame.chart
    # Category mode reuses the stacked-column palette so Compute/Serverless/AI/
    # Storage read the same color in both charts; workload mode uses the extended
    # per-slice palette.
    colors = brand.CHART_SERIES_COLORS if mode == "category" else _DONUT_PALETTE
    _color_points(chart, colors)
    _style_donut(chart)
    return chart, mode
