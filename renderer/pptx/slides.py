"""slides.py - Slide builder functions for the Snowflake sizing PPTX.

Each builder receives (prs, spec, computed_totals) and appends one slide
(or two for the closer) to *prs*, returning the new slide(s).

Slide order:
   1. Title slide
   2. Exec summary / TCV
   3. Workloads detail table
   4. Year-by-year costs (native chart)
   5. Serverless / AI breakdown
   6. Assumptions
   7. Closer / thank-you
"""
from __future__ import annotations

import datetime
from typing import Any

from pptx import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

from . import brand
from .charts import add_year_by_year_chart, add_cost_line_chart


# ── Slide layout helpers ──────────────────────────────────────────────────── #

def _blank_slide(prs: Presentation):
    """Add a blank slide (layout index 6 or the last available blank)."""
    layouts = prs.slide_layouts
    # Try index 6 (Blank in most built-in themes).
    for idx in (6, 5, 11, 0):
        try:
            layout = layouts[idx]
            if not layout.placeholders:
                return prs.slides.add_slide(layout)
        except IndexError:
            pass
    # Fallback: use whatever the last layout is.
    return prs.slides.add_slide(layouts[-1])


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


def _chrome(slide, bg_color: RGBColor = None) -> None:
    """Apply standard chrome: background, accent bar, logo."""
    _set_slide_bg(slide, bg_color or brand.WHITE)
    _add_accent_bar(slide)
    _add_logo(slide)


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
    """Slide 1: Snowflake-branded title.  Customer name as text (no logo)."""
    slide = _blank_slide(prs)
    _set_slide_bg(slide, brand.NAVY)
    _add_accent_bar(slide)
    _add_logo(slide)

    meta = spec.get("meta", {}) or {}
    customer = meta.get("customer") or "Customer"
    edition = meta.get("edition") or ""
    cloud = meta.get("cloud") or ""
    region = meta.get("region") or ""
    date = meta.get("generated_date") or datetime.date.today().isoformat()
    presenter = meta.get("presenter") or ""
    years = meta.get("contract_years", 3)

    # Customer name (large, top).
    _add_textbox(
        slide,
        Inches(0.6), Inches(0.9),
        Inches(11.5), Inches(1.2),
        customer,
        font_name=brand.FONTS["heading"],
        font_size=brand.SIZE_TITLE,
        bold=True,
        color=brand.WHITE,
        align=PP_ALIGN.LEFT,
    )

    # Title.
    _add_textbox(
        slide,
        Inches(0.6), Inches(2.0),
        Inches(9.0), Inches(0.8),
        "Snowflake Sizing Proposal",
        font_name=brand.FONTS["heading"],
        font_size=brand.SIZE_SUBTITLE,
        bold=False,
        color=brand.BLUE,
        align=PP_ALIGN.LEFT,
    )

    # Sub-details.
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
        Inches(0.6), Inches(2.85),
        Inches(9.0), Inches(0.5),
        details,
        font_size=brand.SIZE_BODY,
        color=brand.LGRAY,
        align=PP_ALIGN.LEFT,
    )

    # Date + presenter.
    footer_parts = [date]
    if presenter:
        footer_parts.append(f"Prepared by: {presenter}")
    _add_textbox(
        slide,
        Inches(0.6), Inches(6.5),
        Inches(6.0), Inches(0.4),
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

    # Slide heading.
    _add_textbox(
        slide,
        Inches(0.5), Inches(0.2),
        Inches(9.0), Inches(0.55),
        "Executive Summary",
        font_name=brand.FONTS["heading"],
        font_size=brand.SIZE_HEADING,
        bold=True,
        color=brand.NAVY,
    )

    # Divider line (thin blue rect).
    _add_rect(slide, Inches(0.5), Inches(0.78), Inches(12.3), Inches(0.04), brand.BLUE)

    # Stat cards - 4 across the top row.
    stats = [
        ("Core TCV", _fmt_dollar(core_tcv)),
        ("Contract Term", f"{years} Years"),
        ("Edition", f"{edition}"),
        (f"Cloud / Region", f"{cloud}\n{region}"),
    ]
    card_w = Inches(3.0)
    card_h = Inches(1.6)
    card_gap = Inches(0.2)
    card_top = Inches(0.9)
    for i, (label, value) in enumerate(stats):
        cx = Inches(0.5) + i * (card_w + card_gap)
        # Card background.
        _add_rect(slide, cx, card_top, card_w, card_h, brand.LGRAY)
        # Value text.
        _add_textbox(
            slide, cx + Inches(0.15), card_top + Inches(0.1),
            card_w - Inches(0.3), Inches(0.9),
            value,
            font_name=brand.FONTS["heading"],
            font_size=brand.SIZE_STAT_VALUE,
            bold=True,
            color=brand.NAVY,
            align=PP_ALIGN.CENTER,
        )
        # Label text.
        _add_textbox(
            slide, cx + Inches(0.1), card_top + card_h - Inches(0.45),
            card_w - Inches(0.2), Inches(0.4),
            label,
            font_size=brand.SIZE_STAT_LABEL,
            color=brand.DGRAY,
            align=PP_ALIGN.CENTER,
        )

    # Credit rate info.
    _add_textbox(
        slide,
        Inches(0.5), Inches(2.62),
        Inches(6.0), Inches(0.35),
        f"Credit Rate: ${credit_rate:.2f}/credit",
        font_size=brand.SIZE_SMALL,
        color=brand.DGRAY,
    )

    # Per-year cost table header.
    _add_textbox(
        slide,
        Inches(0.5), Inches(3.05),
        Inches(12.0), Inches(0.4),
        "Core Costs by Year  (Compute + Serverless + AI/Cortex + Storage)",
        font_name=brand.FONTS["body"],
        font_size=brand.SIZE_BODY,
        bold=True,
        color=brand.NAVY,
    )

    # Per-year cost rows.
    row_top = Inches(3.5)
    col_w = Inches(1.7)
    col_gap = Inches(0.05)
    row_h = Inches(0.5)

    col_labels = [
        ("Category", brand.NAVY, True),
    ] + [(f"Year {y + 1}", brand.NAVY, True) for y in range(years)]
    row_defs = [
        ("Compute",    "compute_cost_per_year"),
        ("Serverless", "serverless_cost_per_year"),
        ("AI/Cortex",  "ai_cost_per_year"),
        ("Storage",    "storage_cost_per_year"),
        ("Total",      "core_year_total"),
    ]

    # Header row bg.
    _add_rect(
        slide, Inches(0.5), row_top,
        Inches(0.5) + col_w + years * (col_w + col_gap),
        row_h, brand.NAVY
    )
    # Header cells.
    _add_textbox(
        slide, Inches(0.55), row_top + Inches(0.1),
        col_w - Inches(0.1), row_h - Inches(0.1),
        "Category",
        font_size=brand.SIZE_SMALL, bold=True, color=brand.WHITE,
    )
    for y in range(years):
        cx = Inches(0.5) + col_w + Inches(0.1) + y * (col_w + col_gap)
        _add_textbox(
            slide, cx, row_top + Inches(0.1),
            col_w - Inches(0.1), row_h - Inches(0.1),
            f"Year {y + 1}",
            font_size=brand.SIZE_SMALL, bold=True, color=brand.WHITE,
            align=PP_ALIGN.RIGHT,
        )

    for ri, (row_label, key) in enumerate(row_defs):
        is_total = row_label == "Total"
        ry = row_top + (ri + 1) * row_h
        row_bg = brand.BLUE if is_total else (brand.LGRAY if ri % 2 == 0 else brand.WHITE)
        txt_color = brand.WHITE if is_total else brand.NAVY
        _add_rect(
            slide, Inches(0.5), ry,
            col_w + years * (col_w + col_gap),
            row_h, row_bg
        )
        _add_textbox(
            slide, Inches(0.55), ry + Inches(0.1),
            col_w - Inches(0.1), row_h - Inches(0.1),
            row_label,
            font_size=brand.SIZE_SMALL, bold=is_total, color=txt_color,
        )
        values = computed_totals.get(key, []) or []
        for y in range(years):
            v = values[y] if y < len(values) else 0
            cx = Inches(0.5) + col_w + Inches(0.1) + y * (col_w + col_gap)
            _add_textbox(
                slide, cx, ry + Inches(0.1),
                col_w - Inches(0.1), row_h - Inches(0.1),
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

    _add_textbox(
        slide,
        Inches(0.5), Inches(0.2),
        Inches(9.0), Inches(0.55),
        "Warehouse Workloads",
        font_name=brand.FONTS["heading"],
        font_size=brand.SIZE_HEADING,
        bold=True,
        color=brand.NAVY,
    )
    _add_rect(slide, Inches(0.5), Inches(0.78), Inches(12.3), Inches(0.04), brand.BLUE)

    # Table columns.
    col_defs = [
        ("Workload",    Inches(3.2)),
        ("Size",        Inches(0.7)),
        ("Hrs/Day",     Inches(0.8)),
        ("Days/Mo",     Inches(0.8)),
        ("Min Cl",      Inches(0.7)),
        ("Max Cl",      Inches(0.7)),
        ("Ramp",        Inches(1.1)),
        ("Dev Start",   Inches(0.9)),
        ("Go Live",     Inches(0.8)),
    ]
    total_w = sum(w for _, w in col_defs)
    row_h = Inches(0.42)
    table_top = Inches(0.9)

    # Header.
    _add_rect(slide, Inches(0.5), table_top, total_w, row_h, brand.NAVY)
    x = Inches(0.5)
    for hdr, cw in col_defs:
        _add_textbox(
            slide, x + Inches(0.05), table_top + Inches(0.08),
            cw - Inches(0.1), row_h - Inches(0.08),
            hdr,
            font_size=brand.SIZE_SMALL, bold=True, color=brand.WHITE,
        )
        x += cw

    # Data rows.
    for ri, w in enumerate(workloads):
        ry = table_top + (ri + 1) * row_h
        bg = brand.LGRAY if ri % 2 == 0 else brand.WHITE
        _add_rect(slide, Inches(0.5), ry, total_w, row_h, bg)
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
        x = Inches(0.5)
        for (_, cw), val in zip(col_defs, row_vals):
            _add_textbox(
                slide, x + Inches(0.05), ry + Inches(0.08),
                cw - Inches(0.1), row_h - Inches(0.08),
                val,
                font_size=brand.SIZE_SMALL, color=brand.NAVY,
            )
            x += cw

    # Overflow note if too many workloads.
    max_visible = int((Inches(5.8) / row_h))
    if len(workloads) > max_visible:
        _add_textbox(
            slide, Inches(0.5), table_top + (max_visible + 1) * row_h + Inches(0.1),
            Inches(8.0), Inches(0.3),
            f"… and {len(workloads) - max_visible} more workloads (see full spec JSON)",
            font_size=brand.SIZE_SMALL, color=brand.DGRAY,
        )

    return slide


# ── Slide 4: Year-by-year costs chart ────────────────────────────────────── #

def build_year_chart_slide(prs: Presentation, spec: dict, computed_totals: dict):
    """Slide 4: Native stacked-column chart + line overlay of per-year costs."""
    slide = _blank_slide(prs)
    _chrome(slide)

    meta = spec.get("meta", {}) or {}
    years = int(meta.get("contract_years", 3) or 3)
    core_tcv = computed_totals.get("core_tcv", 0) or 0

    _add_textbox(
        slide,
        Inches(0.5), Inches(0.2),
        Inches(9.0), Inches(0.55),
        "Year-by-Year Cost Breakdown",
        font_name=brand.FONTS["heading"],
        font_size=brand.SIZE_HEADING,
        bold=True,
        color=brand.NAVY,
    )
    _add_rect(slide, Inches(0.5), Inches(0.78), Inches(12.3), Inches(0.04), brand.BLUE)

    # TCV callout.
    _add_textbox(
        slide,
        Inches(9.5), Inches(0.2),
        Inches(3.3), Inches(0.55),
        f"Core TCV: {_fmt_dollar(core_tcv)}",
        font_size=brand.SIZE_BODY,
        bold=True,
        color=brand.BLUE,
        align=PP_ALIGN.RIGHT,
    )

    # Main stacked column chart.
    add_year_by_year_chart(
        slide, computed_totals,
        left=Inches(0.5), top=Inches(0.9),
        width=Inches(12.3), height=Inches(5.6),
    )

    return slide


# ── Slide 5: Serverless / AI breakdown ───────────────────────────────────── #

def build_serverless_ai_slide(prs: Presentation, spec: dict, computed_totals: dict):
    """Slide 5: Enabled serverless features and AI/Cortex spend summary."""
    slide = _blank_slide(prs)
    _chrome(slide)

    serverless = spec.get("serverless", {}) or {}
    ai_cortex = spec.get("ai_cortex", {}) or {}
    years = int((spec.get("meta") or {}).get("contract_years", 3) or 3)

    _add_textbox(
        slide,
        Inches(0.5), Inches(0.2),
        Inches(9.0), Inches(0.55),
        "Serverless & AI/Cortex",
        font_name=brand.FONTS["heading"],
        font_size=brand.SIZE_HEADING,
        bold=True,
        color=brand.NAVY,
    )
    _add_rect(slide, Inches(0.5), Inches(0.78), Inches(12.3), Inches(0.04), brand.BLUE)

    # Serverless section.
    _add_textbox(
        slide, Inches(0.5), Inches(0.9), Inches(5.5), Inches(0.4),
        "Enabled Serverless Features",
        font_size=brand.SIZE_BODY, bold=True, color=brand.NAVY,
    )

    enabled_sl = [
        (k, v) for k, v in serverless.items()
        if isinstance(v, dict) and v.get("enabled")
    ]

    if enabled_sl:
        row_h = Inches(0.4)
        table_top = Inches(1.35)
        for ri, (key, val) in enumerate(enabled_sl):
            ry = table_top + ri * row_h
            bg = brand.LGRAY if ri % 2 == 0 else brand.WHITE
            _add_rect(slide, Inches(0.5), ry, Inches(5.5), row_h, bg)
            label = key.replace("_", " ").title()
            _add_textbox(
                slide, Inches(0.55), ry + Inches(0.07),
                Inches(3.5), row_h,
                label,
                font_size=brand.SIZE_SMALL, color=brand.NAVY,
            )
            # Show key volume metric if present.
            volume_keys = [
                "gb_per_month", "compute_hours_monthly", "uncompressed_gb_per_month",
                "client_instances", "requests_per_month_M",
            ]
            vol_str = ""
            for vk in volume_keys:
                v2 = val.get(vk)
                if v2:
                    vol_str = f"{v2} {vk.replace('_', ' ')}"
                    break
            if vol_str:
                _add_textbox(
                    slide, Inches(4.1), ry + Inches(0.07),
                    Inches(2.0), row_h,
                    vol_str,
                    font_size=brand.SIZE_SMALL, color=brand.DGRAY,
                    align=PP_ALIGN.RIGHT,
                )
    else:
        _add_textbox(
            slide, Inches(0.5), Inches(1.35), Inches(5.5), Inches(0.4),
            "No serverless features enabled.",
            font_size=brand.SIZE_SMALL, color=brand.DGRAY,
        )

    # Serverless cost summary.
    sl_costs = computed_totals.get("serverless_cost_per_year") or []
    sl_total = sum(sl_costs)
    _add_textbox(
        slide, Inches(0.5), Inches(5.8), Inches(5.5), Inches(0.4),
        f"Total Serverless Cost (all years): {_fmt_dollar(sl_total)}",
        font_size=brand.SIZE_SMALL, bold=True, color=brand.NAVY,
    )

    # AI/Cortex section.
    _add_textbox(
        slide, Inches(6.5), Inches(0.9), Inches(6.0), Inches(0.4),
        "AI / Cortex Features",
        font_size=brand.SIZE_BODY, bold=True, color=brand.NAVY,
    )

    ai_feature_map = {
        "cortex_complete":         "Cortex Complete",
        "cortex_agents":           "Cortex Agents",
        "snowflake_intelligence":  "Snowflake Intelligence",
        "cortex_code":             "Cortex Code",
        "cortex_analyst":          "Cortex Analyst",
        "cortex_search":           "Cortex Search",
        "document_ai":             "Document AI",
        "cortex_fine_tuning":      "Fine Tuning",
        "embeddings":              "Embeddings",
    }
    enabled_ai = [
        (ai_feature_map.get(k, k.replace("_", " ").title()), v)
        for k, v in ai_cortex.items()
        if isinstance(v, dict) and v.get("enabled")
    ]

    if enabled_ai:
        row_h = Inches(0.4)
        table_top = Inches(1.35)
        for ri, (label, val) in enumerate(enabled_ai):
            ry = table_top + ri * row_h
            bg = brand.LGRAY if ri % 2 == 0 else brand.WHITE
            _add_rect(slide, Inches(6.5), ry, Inches(6.0), row_h, bg)
            _add_textbox(
                slide, Inches(6.55), ry + Inches(0.07),
                Inches(5.9), row_h,
                label,
                font_size=brand.SIZE_SMALL, color=brand.NAVY,
            )
    else:
        _add_textbox(
            slide, Inches(6.5), Inches(1.35), Inches(6.0), Inches(0.4),
            "No AI/Cortex features enabled.",
            font_size=brand.SIZE_SMALL, color=brand.DGRAY,
        )

    # AI cost summary.
    ai_costs = computed_totals.get("ai_cost_per_year") or []
    ai_total = sum(ai_costs)
    _add_textbox(
        slide, Inches(6.5), Inches(5.8), Inches(6.0), Inches(0.4),
        f"Total AI/Cortex Cost (all years): {_fmt_dollar(ai_total)}",
        font_size=brand.SIZE_SMALL, bold=True, color=brand.NAVY,
    )

    return slide


# ── Slide 6: Assumptions + Closer ────────────────────────────────────────── #

def build_assumptions_slide(prs: Presentation, spec: dict, computed_totals: dict):
    """Slide 6: Key assumptions + confirm-required items."""
    slide = _blank_slide(prs)
    _chrome(slide)

    assumptions = spec.get("assumptions") or []
    confirm_required = spec.get("confirm_required") or []

    _add_textbox(
        slide,
        Inches(0.5), Inches(0.2),
        Inches(9.0), Inches(0.55),
        "Key Assumptions",
        font_name=brand.FONTS["heading"],
        font_size=brand.SIZE_HEADING,
        bold=True,
        color=brand.NAVY,
    )
    _add_rect(slide, Inches(0.5), Inches(0.78), Inches(12.3), Inches(0.04), brand.BLUE)

    # Left column: assumptions.
    _add_textbox(
        slide, Inches(0.5), Inches(0.88), Inches(6.2), Inches(0.38),
        "Pricing & Sizing Assumptions",
        font_size=brand.SIZE_BODY, bold=True, color=brand.NAVY,
    )
    assume_text = "\n".join(f"• {a}" for a in assumptions[:18])
    if len(assumptions) > 18:
        assume_text += f"\n• … and {len(assumptions) - 18} more"
    _add_textbox(
        slide, Inches(0.5), Inches(1.3), Inches(6.2), Inches(5.3),
        assume_text,
        font_size=brand.SIZE_SMALL, color=brand.NAVY,
    )

    # Right column: confirm-required.
    _add_textbox(
        slide, Inches(6.9), Inches(0.88), Inches(6.0), Inches(0.38),
        "Items to Confirm Before Signing",
        font_size=brand.SIZE_BODY, bold=True, color=brand.NAVY,
    )
    if confirm_required:
        items = []
        for c in confirm_required[:10]:
            if isinstance(c, dict):
                item_text = c.get("item") or str(c)
                pct = c.get("impact_pct")
                impact = f"  (~{pct*100:.0f}% impact)" if pct else ""
                items.append(f"• {item_text}{impact}")
            else:
                items.append(f"• {c}")
        confirm_text = "\n".join(items)
    else:
        confirm_text = "No open items."
    _add_textbox(
        slide, Inches(6.9), Inches(1.3), Inches(6.0), Inches(5.3),
        confirm_text,
        font_size=brand.SIZE_SMALL, color=brand.NAVY,
    )

    return slide


def build_closer_slide(prs: Presentation, spec: dict, computed_totals: dict):
    """Slide 7: Thank-you / next-steps closer."""
    slide = _blank_slide(prs)
    _set_slide_bg(slide, brand.NAVY)
    _add_accent_bar(slide)
    _add_logo(slide)

    meta = spec.get("meta", {}) or {}
    customer = meta.get("customer") or "Customer"

    _add_textbox(
        slide,
        Inches(1.5), Inches(2.0),
        Inches(10.0), Inches(1.2),
        "Thank You",
        font_name=brand.FONTS["heading"],
        font_size=brand.SIZE_TITLE,
        bold=True,
        color=brand.WHITE,
        align=PP_ALIGN.CENTER,
    )
    _add_textbox(
        slide,
        Inches(1.5), Inches(3.3),
        Inches(10.0), Inches(0.7),
        f"We look forward to partnering with {customer} on Snowflake.",
        font_size=brand.SIZE_SUBTITLE,
        color=brand.BLUE,
        align=PP_ALIGN.CENTER,
    )

    next_steps = [
        "1. Review assumptions and confirm open items",
        "2. Align on contract term and commercial structure",
        "3. Schedule technical deep-dive / proof of concept",
    ]
    _add_textbox(
        slide,
        Inches(2.5), Inches(4.2),
        Inches(8.0), Inches(1.8),
        "\n".join(next_steps),
        font_size=brand.SIZE_BODY,
        color=brand.LGRAY,
        align=PP_ALIGN.CENTER,
    )

    return slide
