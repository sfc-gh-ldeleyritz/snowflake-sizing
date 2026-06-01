"""slides.py - Slide builders for the Snowflake sizing PPTX generator.

Each builder duplicates a pre-baked designer "donor" slide (cloned into the base
template by scripts/create-sizing-template.py) and injects real content into it,
so the committed on-brand design - styled a:tbl tables, big-number stat columns,
branded covers/closers - is reused verbatim instead of hand-drawn.

Builder contract:
    build_*_slide(prs, donor, spec, computed_totals) -> Slide
        *donor* is the pristine donor slide for this builder's template kind,
        captured once by build_pptx BEFORE any duplication.  The builder
        duplicates it in-package (clone.duplicate_slide_inpackage), injects
        content via the placeholder/position-targeting helpers in inject.py
        (set_title / set_subtitle / body_placeholders / number_shapes /
        caption_shapes / fill_table), and returns the new slide.  build_pptx
        deletes the donors afterwards.

Injection targets shapes by placeholder ROLE + POSITION, never by donor sample
text, so it survives the default scaffolding baked into the donors.

Deck order (up to 10 slides; safe-harbor, agenda, and the cost-mix doughnut are
toggleable - all default ON):
    1.  Title                        (donor: title)
    2.  Safe Harbor                  (donor: safe_harbor)      [meta.include_safe_harbor]
    3.  Agenda                       (donor: agenda)            [meta.include_agenda]
    4.  Understanding Your Snowflake Costs (donor: understanding_costs)
    5.  Cost detail by year          (donor: table_styled)
    6.  Year-by-year chart           (donor: content + native chart; per-year ACV totals)
    7.  Cost mix doughnut            (donor: content + native chart) [include_workload_donut]
    8.  Warehouse workloads          (donor: table_styled)
    9.  Serverless & AI              (donor: table_styled)
    10. Closer / thank-you           (donor: thank_you)

Key assumptions, open items to confirm, and next steps are no longer their own
slides; build_closer_slide folds them into the thank-you slide's speaker notes.
"""
from __future__ import annotations

import datetime

from pptx.util import Inches

from . import clone, inject
from .charts import add_workload_donut, add_year_by_year_chart


# ── Formatting helpers ─────────────────────────────────────────────────────── #

def _fmt_dollar(value: float | None, abbreviated: bool = False) -> str:
    if value is None:
        return "$0"
    if abbreviated:
        if abs(value) >= 1_000_000:
            return f"${value / 1_000_000:.1f}M"
        if abs(value) >= 1_000:
            return f"${value / 1_000:.0f}k"
    return f"${value:,.0f}"


def _meta(spec: dict) -> dict:
    return spec.get("meta", {}) or {}


# Data-row fill for the styled tables: the slide-19 donor ships all-blue rows;
# overriding data rows to white (header keeps its navy fill, cells keep their
# light-gray bottom-border gridlines) gives a cleaner, more legible table.
_DATA_ROW_FILL = "FFFFFF"


# ── Slide 1: Title ─────────────────────────────────────────────────────────── #

def build_title_slide(prs, donor, spec, computed_totals):
    slide = clone.duplicate_slide_inpackage(prs, donor)

    # The donor cover may carry sample decorations / a presenter block on the
    # right (x >= ~6"); drop it so the customer title owns the slide (the bake
    # already removes these, so this is defensive / a no-op on a fresh base).
    inject.remove_shapes(slide, lambda sh: (sh.left or 0) > 5_500_000)

    meta = _meta(spec)
    customer = meta.get("customer") or "Customer"
    edition = meta.get("edition") or ""
    cloud = meta.get("cloud") or ""
    region = meta.get("region") or ""
    years = meta.get("contract_years", 3)
    date = meta.get("generated_date") or datetime.date.today().isoformat()

    sub_parts = [p for p in (edition, cloud, region) if p]
    if years:
        sub_parts.append(f"{years}-Year Contract")

    # The cover's three text placeholders, top-to-bottom: main title (two-line),
    # subtitle, date.
    shapes = inject.text_shapes_by_position(slide)
    if len(shapes) >= 1:
        inject.set_paragraph_texts(shapes[0], [customer, "Snowflake Sizing Proposal"])
    if len(shapes) >= 2:
        inject.set_shape_text(shapes[1], "  |  ".join(sub_parts))
    if len(shapes) >= 3:
        inject.set_shape_text(shapes[2], date)
    return slide


# ── Slide: Safe Harbor (static legal disclaimer) ───────────────────────────── #

def build_safe_harbor_slide(prs, donor, spec, computed_totals):
    # The donor carries Snowflake's verbatim safe-harbor text + copyright; just
    # duplicate it into the deck unchanged.
    return clone.duplicate_slide_inpackage(prs, donor)


# ── Slide: Agenda ──────────────────────────────────────────────────────────── #

_AGENDA_SECTIONS = [
    "Cost Detail by Year",
    "Year-by-Year Costs & Cost Mix",
    "Warehouse Workloads",
    "Serverless & AI / Cortex",
]


def build_agenda_slide(prs, donor, spec, computed_totals):
    slide = clone.duplicate_slide_inpackage(prs, donor)
    inject.set_title(slide, "Agenda")

    body = inject.find_largest_body(slide)
    if body is not None:
        inject.set_body_paragraphs(body, list(_AGENDA_SECTIONS), tight=True)
    return slide


# ── Slide: Understanding Your Snowflake Costs (hand-authored content slide) ──── #

def build_understanding_costs_slide(prs, donor, spec, computed_totals):
    # The donor is the hand-authored "Understanding Your Snowflake Costs" content
    # slide (One Column Layout, with the Compute / Storage / Data-Transfer cost
    # cards) committed in the base template; duplicate it into the deck verbatim.
    return clone.duplicate_slide_inpackage(prs, donor)


# ── Slide 5: Cost detail by year (styled table) ────────────────────────────── #

_COST_ROWS = [
    ("Compute", "compute_cost_per_year"),
    ("Serverless", "serverless_cost_per_year"),
    ("AI / Cortex", "ai_cost_per_year"),
    ("Storage", "storage_cost_per_year"),
    ("Other (SPCS/OpenFlow/Transfer/Collab/Repl.)", "other_cost_per_year"),
    ("Snowflake Services Delivery", None),
    ("Educational Services", None),
    ("Total", "core_year_total"),
]


def build_cost_detail_slide(prs, donor, spec, computed_totals):
    slide = clone.duplicate_slide_inpackage(prs, donor)
    years = len(computed_totals.get("core_year_total", []) or [])

    inject.set_title(slide, "Cost Detail by Year")
    inject.set_subtitle(slide, "Core costs by category (USD)")

    headers = ["Category"] + [f"Year {y}" for y in range(1, years + 1)]
    rows = []
    for label, key in _COST_ROWS:
        if key is None:
            rows.append([label] + [""] * years)
        else:
            values = computed_totals.get(key, []) or []
            rows.append([label] + [_fmt_dollar(values[y] if y < len(values) else 0)
                                   for y in range(years)])
    ratios = [1.6] + [1.0] * years
    inject.fill_table(slide, headers, rows, col_ratios=ratios, bold_last_row=True,
                      data_row_fill=_DATA_ROW_FILL)
    return slide


# ── Slide 5: Year-by-year chart (content donor + native chart) ─────────────── #

def _acv_subtitle(computed_totals: dict) -> str:
    """One-line per-year ACV (annual contract value = core_year_total) summary.

    Uses exact dollars for short terms and abbreviates (>3 years) so the line
    stays on one line and never wraps into the chart below the subtitle."""
    yt = computed_totals.get("core_year_total", []) or []
    if not yt:
        return "ACV by year: n/a"
    abbreviated = len(yt) > 3
    parts = [f"Y{i + 1} {_fmt_dollar(v, abbreviated)}" for i, v in enumerate(yt)]
    return "ACV by year:  " + "   |   ".join(parts)


def build_year_chart_slide(prs, donor, spec, computed_totals):
    slide = clone.duplicate_slide_inpackage(prs, donor)

    inject.set_title(slide, "Year-by-Year Cost Breakdown")
    inject.set_subtitle(slide, _acv_subtitle(computed_totals))

    # Clear the donor body text so it doesn't show behind the chart.
    bodies = inject.body_placeholders(slide)
    if bodies:
        inject.set_body_paragraphs(bodies[0], [""])

    add_year_by_year_chart(
        slide, computed_totals,
        left=Inches(0.45), top=Inches(1.45),
        width=Inches(9.1), height=Inches(3.35),
    )
    return slide


# ── Slide 6: Cost mix doughnut (content donor + native chart) ──────────────── #

def build_workload_donut_slide(prs, donor, spec, pricing, computed_totals):
    """Doughnut of the cost mix.

    Unlike the other builders this also takes *pricing*, because the primary
    "workload" mode derives each slice from a workload's warehouse credits via
    the live calculator.  add_workload_donut returns the chart plus a *mode*
    ("workload" or "category") so the title stays accurate - workload mode is
    compute-only, category mode spans all core cost categories.
    """
    slide = clone.duplicate_slide_inpackage(prs, donor)

    # Clear the donor body text so it doesn't show behind the chart.
    bodies = inject.body_placeholders(slide)
    if bodies:
        inject.set_body_paragraphs(bodies[0], [""])

    chart, mode = add_workload_donut(
        slide, spec, pricing, computed_totals,
        left=Inches(1.7), top=Inches(1.4),
        width=Inches(6.6), height=Inches(3.45),
    )

    if mode == "workload":
        inject.set_title(slide, "Compute Mix by Workload")
        inject.set_subtitle(slide, "Year-1 warehouse credits by workload")
    else:
        inject.set_title(slide, "Cost Mix by Category")
        inject.set_subtitle(slide, "Share of core spend across the contract term")
    return slide


# ── Slide 7: Warehouse workloads (styled table) ────────────────────────────── #

_WORKLOAD_HEADERS = [
    "Workload", "Size", "Hrs/Day", "Days/Mo", "Min Cl", "Max Cl", "Ramp", "Dev", "Go-Live",
]
_WORKLOAD_RATIOS = [2.5, 0.8, 0.85, 0.85, 0.75, 0.75, 1.05, 0.7, 0.8]
_MAX_WORKLOAD_ROWS = 12


def build_workloads_slide(prs, donor, spec, computed_totals):
    slide = clone.duplicate_slide_inpackage(prs, donor)
    workloads = spec.get("workloads", []) or []
    visible = workloads[:_MAX_WORKLOAD_ROWS]

    subtitle = f"{len(workloads)} workload(s)"
    if len(workloads) > _MAX_WORKLOAD_ROWS:
        subtitle += f"  (showing first {_MAX_WORKLOAD_ROWS})"
    inject.set_title(slide, "Warehouse Workloads")
    inject.set_subtitle(slide, subtitle)

    rows = []
    for i, w in enumerate(visible):
        rows.append([
            w.get("label") or w.get("id") or f"Workload {i + 1}",
            w.get("size") or "N/A",
            str(w.get("hours_per_day", 0)),
            str(w.get("days_per_month", 0)),
            str(w.get("clusters_min", 1)),
            str(w.get("clusters_max", 1)),
            w.get("ramp_curve") or "N/A",
            f"M{w.get('dev_start_month', 1)}",
            f"M{w.get('go_live_month', 12)}",
        ])
    if not rows:
        rows = [["(no workloads defined)"] + [""] * (len(_WORKLOAD_HEADERS) - 1)]

    inject.fill_table(slide, _WORKLOAD_HEADERS, rows, col_ratios=_WORKLOAD_RATIOS,
                      data_row_fill=_DATA_ROW_FILL)
    return slide


# ── Slide 8: Serverless, AI & Other Compute (styled table, by year) ────────── #

# Full non-warehouse compute stack. Rows with all-zero spend are dropped so lean
# specs keep a tight table (only Serverless / AI typically show). Keys map to the
# per-year dollar arrays in framework/compute_totals.compute_core_totals().
_SERVERLESS_AI_ROWS = [
    ("Serverless", "serverless_cost_per_year"),
    ("AI / Cortex", "ai_cost_per_year"),
    ("SPCS", "spcs_cost_per_year"),
    ("OpenFlow", "openflow_cost_per_year"),
    ("Data Transfer", "data_transfer_cost_per_year"),
    ("Collaboration", "collaboration_cost_per_year"),
    ("Replication / DR", "replication_cost_per_year"),
]


def build_serverless_ai_slide(prs, donor, spec, computed_totals):
    slide = clone.duplicate_slide_inpackage(prs, donor)
    years = len(computed_totals.get("core_year_total", []) or [])

    inject.set_title(slide, "Serverless, AI & Other Compute")
    inject.set_subtitle(slide, "Projected spend by year (USD)")

    headers = ["Category"] + [f"Year {y}" for y in range(1, years + 1)]
    totals = [0.0] * years
    rows = []
    for label, key in _SERVERLESS_AI_ROWS:
        values = computed_totals.get(key, []) or []
        row_vals = [values[y] if y < len(values) else 0 for y in range(years)]
        # Skip categories with no spend in any year (keeps lean decks tight).
        if not any(round(v, 2) for v in row_vals):
            continue
        for y in range(years):
            totals[y] += row_vals[y]
        rows.append([label] + [_fmt_dollar(v) for v in row_vals])
    rows.append(["Total"] + [_fmt_dollar(v) for v in totals])

    ratios = [1.6] + [1.0] * years
    inject.fill_table(slide, headers, rows, col_ratios=ratios, bold_last_row=True,
                      data_row_fill=_DATA_ROW_FILL)
    return slide


# ── Slide 10: Closer / thank-you (thank_you donor) ─────────────────────────── #

_NEXT_STEPS = [
    "Review assumptions and confirm open items",
    "Align on contract term and commercial structure",
    "Schedule technical deep-dive / proof of concept",
]


def _confirm_note_line(c) -> str:
    """Render a confirm_required entry as a notes bullet with optional impact %."""
    if isinstance(c, dict):
        item = c.get("item") or ""
        pct = c.get("impact_pct")
        return f"- {item} (~{pct * 100:.0f}% impact)" if pct else f"- {item}"
    return f"- {c}"


def build_closer_slide(prs, donor, spec, computed_totals):
    slide = clone.duplicate_slide_inpackage(prs, donor)

    # The donor's iconic "THANK / YOU" headline + blue background + wordmark are
    # kept verbatim; the supporting detail (assumptions, open items, next steps)
    # now lives in the speaker notes instead of crowding the closing slide.
    assumptions = spec.get("assumptions") or []
    confirm_required = spec.get("confirm_required") or []

    notes = ["Key Assumptions"]
    notes += [f"- {a}" for a in assumptions] if assumptions else ["- (none recorded)"]
    notes += ["", "Open Items to Confirm"]
    notes += ([_confirm_note_line(c) for c in confirm_required]
              if confirm_required else ["- (none)"])
    notes += ["", "Next Steps"]
    notes += [f"{i}. {s}" for i, s in enumerate(_NEXT_STEPS, start=1)]

    inject.set_speaker_notes(slide, "\n".join(notes))
    return slide
