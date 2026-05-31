"""slides.py - Individual slide builders for the Snowflake sizing PPTX.

Each builder receives (prs, spec, computed_totals) and appends one slide
to *prs*, returning the new slide.

Slide order:
   1. Title slide
   2. Exec summary / TCV
   3. Workloads detail table
   4. Year-by-year costs (native chart)
   5. Serverless / AI breakdown
   6. Assumptions
   7. Confirm-required items (conditional — only when spec["confirm_required"] non-empty)
   8. Closer / thank-you

All coordinates are sized for a 10.0" x 5.625" slide.
"""
from __future__ import annotations

import datetime
from typing import Any

from pptx import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

from . import brand
from .charts import add_year_by_year_chart


# ── Slide layout helpers ──────────────────────────────────────────────────── #

def _get_layout(prs: Presentation, name: str):
    """Return the first slide layout matching *name*, or None if not found."""
    for master in prs.slide_masters:
        for layout in master.slide_layouts:
            if layout.name == name:
                return layout
    return None


def _blank_slide(prs: Presentation):
    """Add a blank slide using the cleanest available layout.

    Tries the named 'One Column Layout' from the base template first, then
    searches all masters for a layout with no shapes, then falls back to
    an index-based search.
    """
    layout = _get_layout(prs, "One Column Layout")
    if layout:
        return prs.slides.add_slide(layout)
    # Fallback: layout with no shapes (no inherited chrome).
    for master in reversed(list(prs.slide_masters)):
        for lo in master.slide_layouts:
            if not list(lo.shapes):
                return prs.slides.add_slide(lo)
    # Last resort: index-based blank layout.
    layouts = prs.slide_layouts
    for idx in (6, 5, 11, 0):
        try:
            lo = layouts[idx]
            if not lo.placeholders:
                return prs.slides.add_slide(lo)
        except IndexError:
            pass
    return prs.slides.add_slide(layouts[-1])


def _cover_slide(prs: Presentation):
    """Add a cover slide using the '1_Data Cloud_1_1_2' layout (blue bg)."""
    layout = _get_layout(prs, "1_Data Cloud_1_1_2")
    if layout:
        return prs.slides.add_slide(layout)
    return _blank_slide(prs)


def _closer_slide_blank(prs: Presentation):
    """Add a closer slide using the 'Thank You_1' layout (blue bg + bottom chrome)."""
    layout = _get_layout(prs, "Thank You_1")
    if layout:
        return prs.slides.add_slide(layout)
    return _blank_slide(prs)


def _set_slide_bg(slide, color: RGBColor) -> None:
    """Fill slide background with a solid color."""
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_rect(slide, left, top, width, height, fill_color: RGBColor, line_color=None):
    """Add a filled rectangle shape."""
    shape = slide.shapes.add_shape(
        1,  # MSO_SHAPE_TYPE.RECTANGLE = 1
        left, top, width, height,
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if line_color is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line_color
    return shape


def _add_textbox(slide, left, top, width, height, text: str,
                 font_name: str = None, font_size: Pt = None,
                 bold: bool = False, color: RGBColor = None,
                 align=PP_ALIGN.LEFT, word_wrap: bool = True) -> Any:
    """Add a text box and return the shape."""
    txb = slide.shapes.add_textbox(left, top, width, height)
    tf = txb.text_frame
    tf.word_wrap = word_wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = font_name or brand.FONTS["body"]
    if font_size:
        run.font.size = font_size
    run.font.bold = bold
    if color:
        run.font.color.rgb = color
    return txb


def _add_logo(slide) -> None:
    """Add the Snowflake logo to the top-right if available."""
    logo = brand.logo_path()
    if logo:
        slide.shapes.add_picture(
            str(logo),
            brand.LOGO_X, brand.LOGO_Y,
            brand.LOGO_W, brand.LOGO_H,
        )


def _add_accent_bar(slide) -> None:
    """Add the bottom blue accent bar."""
    _add_rect(
        slide,
        brand.BAR_X, brand.BAR_Y,
        brand.BAR_W, brand.BAR_H,
        brand.BLUE,
    )


def _chrome(slide) -> None:
    """Apply content-slide chrome: accent bar and logo. Background set by layout."""
    _add_accent_bar(slide)
    _add_logo(slide)


def _slide_heading(slide, text: str) -> None:
    """Add the standard slide heading + blue divider line."""
    _add_textbox(
        slide,
        Inches(0.4), Inches(0.15),
        Inches(7.0), Inches(0.45),
        text,
        font_name=brand.FONTS["heading"],
        font_size=brand.SIZE_HEADING,
        bold=True,
        color=brand.NAVY,
    )
    _add_rect(slide, Inches(0.4), Inches(0.63), Inches(9.2), Inches(0.03), brand.BLUE)


# ── Dollar formatting ─────────────────────────────────────────────────────── #

def _fmt_dollar(value: float, abbreviated: bool = False) -> str:
    if value is None:
        return "$0"
    if abbreviated:
        if abs(value) >= 1_000_000:
            return f"${value / 1_000_000:.1f}M"
        if abs(value) >= 1_000:
            return f"${value / 1_000:.0f}k"
    return f"${value:,.0f}"


# ── Slide 1: Title ────────────────────────────────────────────────────────── #

def build_title_slide(prs: Presentation, spec: dict, computed_totals: dict):
    """Slide 1: Snowflake-branded cover.  Blue background from layout, white text."""
    slide = _cover_slide(prs)
    # Layout provides the blue background and the Snowflake freeform mark.
    # Add accent bar at the bottom to cover the layout copyright text.
    _add_accent_bar(slide)

    meta = spec.get("meta", {}) or {}
    customer = meta.get("customer") or "Customer"
    edition = meta.get("edition") or ""
    cloud = meta.get("cloud") or ""
    region = meta.get("region") or ""
    date = meta.get("generated_date") or datetime.date.today().isoformat()
    presenter = meta.get("presenter") or ""
    years = meta.get("contract_years", 3)

    # Customer name (large, top-left).
    _add_textbox(
        slide,
        Inches(0.45), Inches(0.7),
        Inches(8.6), Inches(0.9),
        customer,
        font_name=brand.FONTS["heading"],
        font_size=brand.SIZE_TITLE,
        bold=True,
        color=brand.WHITE,
        align=PP_ALIGN.LEFT,
    )

    # Proposal title.
    _add_textbox(
        slide,
        Inches(0.45), Inches(1.8),
        Inches(6.8), Inches(0.6),
        "Snowflake Sizing Proposal",
        font_name=brand.FONTS["heading"],
        font_size=brand.SIZE_SUBTITLE,
        bold=False,
        color=brand.WHITE,
        align=PP_ALIGN.LEFT,
    )

    # Sub-details: edition | cloud | region | N-Year.
    details_parts = []
    if edition:
        details_parts.append(edition)
    if cloud:
        details_parts.append(cloud)
    if region:
        details_parts.append(region)
    if years:
        details_parts.append(f"{years}-Year Contract")
    details = "  |  ".join(details_parts)
    _add_textbox(
        slide,
        Inches(0.45), Inches(2.55),
        Inches(6.8), Inches(0.4),
        details,
        font_size=brand.SIZE_BODY,
        color=brand.LGRAY,
        align=PP_ALIGN.LEFT,
    )

    # Date + presenter footer (above accent bar).
    footer_parts = [date]
    if presenter:
        footer_parts.append(f"Prepared by: {presenter}")
    _add_textbox(
        slide,
        Inches(0.45), Inches(4.8),
        Inches(5.0), Inches(0.3),
        "  |  ".join(footer_parts),
        font_size=brand.SIZE_SMALL,
        color=brand.LGRAY,
        align=PP_ALIGN.LEFT,
    )

    return slide


# ── Slide 2: Exec Summary / TCV ───────────────────────────────────────────── #

def build_exec_summary_slide(prs: Presentation, spec: dict, computed_totals: dict):
    """Slide 2: Stat grid with headline TCV, years, edition, region."""
    slide = _blank_slide(prs)
    _chrome(slide)

    meta = spec.get("meta", {}) or {}
    years = int(meta.get("contract_years", 3) or 3)
    edition = meta.get("edition") or "N/A"
    cloud = meta.get("cloud") or "N/A"
    region = meta.get("region") or "N/A"
    credit_rate = float(meta.get("credit_rate", 0) or 0)
    core_tcv = computed_totals.get("core_tcv", 0) or 0
    core_year_total = computed_totals.get("core_year_total") or []

    _slide_heading(slide, "Executive Summary")

    # Stat cards — 4 across the top row.
    stats = [
        ("Core TCV",     _fmt_dollar(core_tcv, abbreviated=True)),
        ("Contract Term", f"{years} Years"),
        ("Edition",       f"{edition}"),
        ("Cloud / Region", f"{cloud}\n{region}"),
    ]
    card_w   = Inches(2.2)
    card_h   = Inches(1.2)
    card_gap = Inches(0.12)
    card_top = Inches(0.72)
    for i, (label, value) in enumerate(stats):
        cx = Inches(0.4) + i * (card_w + card_gap)
        _add_rect(slide, cx, card_top, card_w, card_h, brand.LGRAY)
        _add_textbox(
            slide, cx + Inches(0.1), card_top + Inches(0.08),
            card_w - Inches(0.2), Inches(0.65),
            value,
            font_name=brand.FONTS["heading"],
            font_size=brand.SIZE_STAT_VALUE,
            bold=True,
            color=brand.NAVY,
            align=PP_ALIGN.CENTER,
        )
        _add_textbox(
            slide, cx + Inches(0.08), card_top + card_h - Inches(0.37),
            card_w - Inches(0.16), Inches(0.35),
            label,
            font_size=brand.SIZE_STAT_LABEL,
            color=brand.DGRAY,
            align=PP_ALIGN.CENTER,
        )

    # Credit rate.
    _add_textbox(
        slide,
        Inches(0.4), Inches(1.97),
        Inches(5.0), Inches(0.3),
        f"Credit Rate: ${credit_rate:.2f}/credit",
        font_size=brand.SIZE_SMALL,
        color=brand.DGRAY,
    )

    # Per-year cost section label (includes full TCV for reference).
    _add_textbox(
        slide,
        Inches(0.4), Inches(2.32),
        Inches(9.0), Inches(0.38),
        f"Core Costs by Year  (Compute + Serverless + AI/Cortex + Storage)  |  TCV: {_fmt_dollar(core_tcv)}",
        font_name=brand.FONTS["body"],
        font_size=brand.SIZE_BODY,
        bold=True,
        color=brand.NAVY,
    )

    # Per-year cost table.
    row_top = Inches(2.72)
    col_w   = Inches(1.3)
    col_gap = Inches(0.04)
    row_h   = Inches(0.38)
    table_w = col_w + years * (col_w + col_gap)

    row_defs = [
        ("Compute",    "compute_cost_per_year"),
        ("Serverless", "serverless_cost_per_year"),
        ("AI/Cortex",  "ai_cost_per_year"),
        ("Storage",    "storage_cost_per_year"),
        ("Total",      "core_year_total"),
    ]

    # Header row.
    _add_rect(slide, Inches(0.4), row_top, table_w, row_h, brand.NAVY)
    _add_textbox(
        slide, Inches(0.45), row_top + Inches(0.08),
        col_w - Inches(0.1), row_h - Inches(0.08),
        "Category",
        font_size=brand.SIZE_SMALL, bold=True, color=brand.WHITE,
    )
    for y in range(years):
        cx = Inches(0.4) + col_w + Inches(0.06) + y * (col_w + col_gap)
        _add_textbox(
            slide, cx, row_top + Inches(0.08),
            col_w - Inches(0.06), row_h - Inches(0.08),
            f"Year {y + 1}",
            font_size=brand.SIZE_SMALL, bold=True, color=brand.WHITE,
            align=PP_ALIGN.RIGHT,
        )

    # Data rows.
    for ri, (row_label, key) in enumerate(row_defs):
        is_total = row_label == "Total"
        ry = row_top + (ri + 1) * row_h
        row_bg = brand.BLUE if is_total else (brand.LGRAY if ri % 2 == 0 else brand.WHITE)
        txt_color = brand.WHITE if is_total else brand.NAVY
        _add_rect(slide, Inches(0.4), ry, table_w, row_h, row_bg)
        _add_textbox(
            slide, Inches(0.45), ry + Inches(0.08),
            col_w - Inches(0.1), row_h - Inches(0.08),
            row_label,
            font_size=brand.SIZE_SMALL, bold=is_total, color=txt_color,
        )
        values = computed_totals.get(key, []) or []
        for y in range(years):
            v = values[y] if y < len(values) else 0
            cx = Inches(0.4) + col_w + Inches(0.06) + y * (col_w + col_gap)
            _add_textbox(
                slide, cx, ry + Inches(0.08),
                col_w - Inches(0.06), row_h - Inches(0.08),
                _fmt_dollar(v),
                font_size=brand.SIZE_SMALL, bold=is_total, color=txt_color,
                align=PP_ALIGN.RIGHT,
            )

    return slide


# ── Slide 3: Workloads detail ─────────────────────────────────────────────── #

def build_workloads_slide(prs: Presentation, spec: dict, computed_totals: dict):
    """Slide 3: Table of workloads with key parameters."""
    slide = _blank_slide(prs)
    _chrome(slide)

    workloads = spec.get("workloads", []) or []

    _slide_heading(slide, "Warehouse Workloads")

    col_defs = [
        ("Workload",   Inches(2.4)),
        ("Size",       Inches(0.55)),
        ("Hrs/Day",    Inches(0.6)),
        ("Days/Mo",    Inches(0.6)),
        ("Min Cl",     Inches(0.55)),
        ("Max Cl",     Inches(0.55)),
        ("Ramp",       Inches(0.85)),
        ("Dev Start",  Inches(0.7)),
        ("Go Live",    Inches(0.6)),
    ]
    total_w  = sum(w for _, w in col_defs)
    table_top = Inches(0.7)
    row_h    = Inches(0.33)

    # Header.
    _add_rect(slide, Inches(0.4), table_top, total_w, row_h, brand.NAVY)
    x = Inches(0.4)
    for hdr, cw in col_defs:
        _add_textbox(
            slide, x + Inches(0.04), table_top + Inches(0.07),
            cw - Inches(0.08), row_h - Inches(0.07),
            hdr,
            font_size=brand.SIZE_SMALL, bold=True, color=brand.WHITE,
        )
        x += cw

    # Data rows.
    max_visible = 12
    for ri, w in enumerate(workloads[:max_visible]):
        ry = table_top + (ri + 1) * row_h
        bg = brand.LGRAY if ri % 2 == 0 else brand.WHITE
        _add_rect(slide, Inches(0.4), ry, total_w, row_h, bg)
        row_vals = [
            w.get("label") or w.get("id") or f"Workload {ri + 1}",
            w.get("size") or "N/A",
            str(w.get("hours_per_day", 0)),
            str(w.get("days_per_month", 0)),
            str(w.get("clusters_min", 1)),
            str(w.get("clusters_max", 1)),
            w.get("ramp_curve") or "N/A",
            f"M{w.get('dev_start_month', 1)}",
            f"M{w.get('go_live_month', 12)}",
        ]
        x = Inches(0.4)
        for (_, cw), val in zip(col_defs, row_vals):
            _add_textbox(
                slide, x + Inches(0.04), ry + Inches(0.07),
                cw - Inches(0.08), row_h - Inches(0.07),
                val,
                font_size=brand.SIZE_SMALL, color=brand.NAVY,
            )
            x += cw

    if len(workloads) > max_visible:
        overflow_y = table_top + (max_visible + 1) * row_h + Inches(0.05)
        _add_textbox(
            slide, Inches(0.4), overflow_y,
            Inches(8.0), Inches(0.28),
            f"... and {len(workloads) - max_visible} more workloads (see full spec JSON)",
            font_size=brand.SIZE_SMALL, color=brand.DGRAY,
        )

    return slide


# ── Slide 4: Year-by-year costs chart ────────────────────────────────────── #

def build_year_chart_slide(prs: Presentation, spec: dict, computed_totals: dict):
    """Slide 4: Native stacked-column chart of per-year costs."""
    slide = _blank_slide(prs)
    _chrome(slide)

    meta = spec.get("meta", {}) or {}
    core_tcv = computed_totals.get("core_tcv", 0) or 0

    _slide_heading(slide, "Year-by-Year Cost Breakdown")

    # TCV callout (top-right).
    _add_textbox(
        slide,
        Inches(6.8), Inches(0.15),
        Inches(2.8), Inches(0.45),
        f"Core TCV: {_fmt_dollar(core_tcv)}",
        font_size=brand.SIZE_BODY,
        bold=True,
        color=brand.BLUE,
        align=PP_ALIGN.RIGHT,
    )

    # Main stacked-column chart spanning the content area.
    add_year_by_year_chart(
        slide, computed_totals,
        left=Inches(0.4), top=Inches(0.7),
        width=Inches(9.2), height=Inches(4.45),
    )

    return slide


# ── Slide 5: Serverless / AI breakdown ───────────────────────────────────── #

def build_serverless_ai_slide(prs: Presentation, spec: dict, computed_totals: dict):
    """Slide 5: Enabled serverless features and AI/Cortex spend summary."""
    slide = _blank_slide(prs)
    _chrome(slide)

    serverless = spec.get("serverless", {}) or {}
    ai_cortex  = spec.get("ai_cortex", {}) or {}

    _slide_heading(slide, "Serverless & AI/Cortex")

    # ── Left column: serverless ──────────────────────────────────────────── #
    _add_textbox(
        slide, Inches(0.4), Inches(0.7), Inches(4.1), Inches(0.38),
        "Enabled Serverless Features",
        font_size=brand.SIZE_BODY, bold=True, color=brand.NAVY,
    )

    enabled_sl = [
        (k, v) for k, v in serverless.items()
        if isinstance(v, dict) and v.get("enabled")
    ]

    row_h     = Inches(0.32)
    table_top = Inches(1.12)

    if enabled_sl:
        for ri, (key, val) in enumerate(enabled_sl):
            ry = table_top + ri * row_h
            bg = brand.LGRAY if ri % 2 == 0 else brand.WHITE
            _add_rect(slide, Inches(0.4), ry, Inches(4.1), row_h, bg)
            label = key.replace("_", " ").title()
            _add_textbox(
                slide, Inches(0.44), ry + Inches(0.05),
                Inches(2.7), row_h,
                label,
                font_size=brand.SIZE_SMALL, color=brand.NAVY,
            )
            volume_keys = [
                "gb_per_month", "compute_hours_monthly",
                "uncompressed_gb_per_month", "client_instances",
                "requests_per_month_M",
            ]
            vol_str = ""
            for vk in volume_keys:
                v2 = val.get(vk)
                if v2:
                    vol_str = f"{v2} {vk.replace('_', ' ')}"
                    break
            if vol_str:
                _add_textbox(
                    slide, Inches(3.1), ry + Inches(0.05),
                    Inches(1.5), row_h,
                    vol_str,
                    font_size=brand.SIZE_SMALL, color=brand.DGRAY,
                    align=PP_ALIGN.RIGHT,
                )
    else:
        _add_textbox(
            slide, Inches(0.4), table_top, Inches(4.1), Inches(0.38),
            "No serverless features enabled.",
            font_size=brand.SIZE_SMALL, color=brand.DGRAY,
        )

    # Serverless total.
    sl_costs = computed_totals.get("serverless_cost_per_year") or []
    sl_total = sum(sl_costs)
    _add_textbox(
        slide, Inches(0.4), Inches(4.5), Inches(4.1), Inches(0.38),
        f"Total Serverless Cost (all years): {_fmt_dollar(sl_total)}",
        font_size=brand.SIZE_SMALL, bold=True, color=brand.NAVY,
    )

    # ── Right column: AI/Cortex ──────────────────────────────────────────── #
    _add_textbox(
        slide, Inches(5.0), Inches(0.7), Inches(4.6), Inches(0.38),
        "AI / Cortex Features",
        font_size=brand.SIZE_BODY, bold=True, color=brand.NAVY,
    )

    ai_feature_map = {
        "cortex_complete":        "Cortex Complete",
        "cortex_agents":          "Cortex Agents",
        "snowflake_intelligence":  "Snowflake Intelligence",
        "cortex_code":            "Cortex Code",
        "cortex_analyst":         "Cortex Analyst",
        "cortex_search":          "Cortex Search",
        "document_ai":            "Document AI",
        "cortex_fine_tuning":     "Fine Tuning",
        "embeddings":             "Embeddings",
    }
    enabled_ai = [
        (ai_feature_map.get(k, k.replace("_", " ").title()), v)
        for k, v in ai_cortex.items()
        if isinstance(v, dict) and v.get("enabled")
    ]

    if enabled_ai:
        for ri, (label, val) in enumerate(enabled_ai):
            ry = table_top + ri * row_h
            bg = brand.LGRAY if ri % 2 == 0 else brand.WHITE
            _add_rect(slide, Inches(5.0), ry, Inches(4.6), row_h, bg)
            _add_textbox(
                slide, Inches(5.04), ry + Inches(0.05),
                Inches(4.5), row_h,
                label,
                font_size=brand.SIZE_SMALL, color=brand.NAVY,
            )
    else:
        _add_textbox(
            slide, Inches(5.0), table_top, Inches(4.6), Inches(0.38),
            "No AI/Cortex features enabled.",
            font_size=brand.SIZE_SMALL, color=brand.DGRAY,
        )

    # AI total.
    ai_costs = computed_totals.get("ai_cost_per_year") or []
    ai_total = sum(ai_costs)
    _add_textbox(
        slide, Inches(5.0), Inches(4.5), Inches(4.6), Inches(0.38),
        f"Total AI/Cortex Cost (all years): {_fmt_dollar(ai_total)}",
        font_size=brand.SIZE_SMALL, bold=True, color=brand.NAVY,
    )

    return slide


# ── Slide 6: Assumptions ─────────────────────────────────────────────────── #

def build_assumptions_slide(prs: Presentation, spec: dict, computed_totals: dict):
    """Slide 6: Key pricing & sizing assumptions (full-width)."""
    slide = _blank_slide(prs)
    _chrome(slide)

    assumptions = spec.get("assumptions") or []

    _slide_heading(slide, "Key Assumptions")

    _add_textbox(
        slide, Inches(0.4), Inches(0.72), Inches(9.2), Inches(0.38),
        "Pricing & Sizing Assumptions",
        font_size=brand.SIZE_BODY, bold=True, color=brand.NAVY,
    )

    max_visible = 22
    assume_text = "\n".join(f"• {a}" for a in assumptions[:max_visible])
    if len(assumptions) > max_visible:
        assume_text += f"\n• ... and {len(assumptions) - max_visible} more"
    _add_textbox(
        slide, Inches(0.4), Inches(1.13),
        Inches(9.2), Inches(3.95),
        assume_text,
        font_size=brand.SIZE_SMALL, color=brand.NAVY,
    )

    return slide


# ── Slide 7 (conditional): Confirm Required ───────────────────────────────── #

def build_confirm_required_slide(prs: Presentation, spec: dict, computed_totals: dict):
    """Slide 7 (conditional): Open items that must be confirmed before signing."""
    slide = _blank_slide(prs)
    _chrome(slide)

    confirm_required = spec.get("confirm_required") or []

    _slide_heading(slide, "Open Items to Confirm")

    col_item_w   = Inches(7.1)
    col_impact_w = Inches(1.9)
    total_w      = col_item_w + col_impact_w   # 9.0"
    table_top    = Inches(0.7)
    row_h        = Inches(0.38)

    # Header row.
    _add_rect(slide, Inches(0.4), table_top, total_w, row_h, brand.NAVY)
    _add_textbox(
        slide, Inches(0.45), table_top + Inches(0.08),
        col_item_w - Inches(0.1), row_h - Inches(0.08),
        "Item",
        font_size=brand.SIZE_SMALL, bold=True, color=brand.WHITE,
    )
    _add_textbox(
        slide, Inches(0.4) + col_item_w + Inches(0.05),
        table_top + Inches(0.08),
        col_impact_w - Inches(0.05), row_h - Inches(0.08),
        "Impact",
        font_size=brand.SIZE_SMALL, bold=True, color=brand.WHITE,
        align=PP_ALIGN.RIGHT,
    )

    # Data rows.
    max_visible = 12
    for ri, c in enumerate(confirm_required[:max_visible]):
        ry = table_top + (ri + 1) * row_h
        bg = brand.LGRAY if ri % 2 == 0 else brand.WHITE
        _add_rect(slide, Inches(0.4), ry, total_w, row_h, bg)

        if isinstance(c, dict):
            item_text  = c.get("item") or str(c)
            pct        = c.get("impact_pct")
            impact_str = f"~{pct * 100:.0f}%" if pct else ""
        else:
            item_text  = str(c)
            impact_str = ""

        _add_textbox(
            slide, Inches(0.45), ry + Inches(0.07),
            col_item_w - Inches(0.1), row_h - Inches(0.07),
            item_text,
            font_size=brand.SIZE_SMALL, color=brand.NAVY,
        )
        if impact_str:
            _add_textbox(
                slide, Inches(0.4) + col_item_w + Inches(0.05),
                ry + Inches(0.07),
                col_impact_w - Inches(0.05), row_h - Inches(0.07),
                impact_str,
                font_size=brand.SIZE_SMALL, color=brand.NAVY,
                align=PP_ALIGN.RIGHT,
            )

    if len(confirm_required) > max_visible:
        overflow_y = table_top + (max_visible + 1) * row_h + Inches(0.05)
        _add_textbox(
            slide, Inches(0.4), overflow_y,
            Inches(8.0), Inches(0.28),
            f"... and {len(confirm_required) - max_visible} more items",
            font_size=brand.SIZE_SMALL, color=brand.DGRAY,
        )

    return slide


# ── Slide 7 or 8: Closer ─────────────────────────────────────────────────── #

def build_closer_slide(prs: Presentation, spec: dict, computed_totals: dict):
    """Final slide: Thank-you / next-steps closer.  Blue background from layout."""
    slide = _closer_slide_blank(prs)
    # Layout provides blue background and the full Snowflake bottom chrome
    # (GROUP shape: 10"x1.5" blue bar with white wordmark at bottom edge).
    # Do NOT add accent bar or logo — layout GROUP already provides both.

    meta = spec.get("meta", {}) or {}
    customer = meta.get("customer") or "Customer"

    _add_textbox(
        slide,
        Inches(1.0), Inches(1.3),
        Inches(8.0), Inches(0.9),
        "Thank You",
        font_name=brand.FONTS["heading"],
        font_size=brand.SIZE_TITLE,
        bold=True,
        color=brand.WHITE,
        align=PP_ALIGN.CENTER,
    )
    _add_textbox(
        slide,
        Inches(1.0), Inches(2.4),
        Inches(8.0), Inches(0.5),
        f"We look forward to partnering with {customer} on Snowflake.",
        font_size=brand.SIZE_SUBTITLE,
        color=brand.WHITE,
        align=PP_ALIGN.CENTER,
    )

    next_steps = [
        "1. Review assumptions and confirm open items",
        "2. Align on contract term and commercial structure",
        "3. Schedule technical deep-dive / proof of concept",
    ]
    _add_textbox(
        slide,
        Inches(1.0), Inches(3.1),
        Inches(8.0), Inches(1.6),
        "\n".join(next_steps),
        font_size=brand.SIZE_BODY,
        color=brand.WHITE,
        align=PP_ALIGN.CENTER,
    )

    return slide
