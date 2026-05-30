"""charts.py - Native python-pptx chart builders from computed_totals arrays.

Each helper returns a (chart, chart_frame) by mutating an existing slide.
All charts are NATIVE editable PowerPoint charts (CategoryChartData /
XL_CHART_TYPE) - not images.
"""
from __future__ import annotations

from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches, Pt

from . import brand


def _apply_series_colors(chart, colors: list) -> None:
    """Apply brand colors to each series fill."""
    for i, series in enumerate(chart.series):
        color = colors[i % len(colors)]
        fill = series.format.fill
        fill.solid()
        fill.fore_color.rgb = color


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

    Series: Compute, Serverless, AI, Storage (from computed_totals arrays).
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
    ]
    for label, key in series_defs:
        values = computed_totals.get(key, [0] * years)
        chart_data.add_series(label, [round(v, 2) for v in values])

    # Default geometry if not specified.
    l = left   if left   is not None else Inches(0.5)
    t = top    if top    is not None else Inches(1.4)
    w = width  if width  is not None else Inches(8.5)
    h = height if height is not None else Inches(4.8)

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
