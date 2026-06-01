---
name: snowflake-sizing-render-pptx
description: Phase 7 + 8 of snowflake-sizing - run scripts/render-pptx.py to build a Snowflake-branded PPTX from the sizing JSON spec, export slide images for visual QA, iterate until clean, print the final summary.
---

# Render-PPTX sub-skill (snowflake-sizing)

Loaded by the parent `snowflake-sizing` skill when `--pptx` is passed, after
the render-html sub-skill returns. Inputs available: complete `SIZING_SPEC`
JSON written by spec-prepare.py to
`sizings/<slug>-<N>year-sizing-v<version>-<date>.json` (the single source of
truth for both HTML and PPTX), plus the `computed_totals` block inside it.

Prerequisites (if not already installed):

```
pip install python-pptx
```

LibreOffice is required for the QA image export step:

```
# macOS: brew install libreoffice
# Linux: apt-get install libreoffice
```

---

## Phase 7 - Generate PPTX

Output path (goes to the git-tracked `sizings/` directory):

```
PPTX: sizings/<customer-slug>-<N>year-sizing-v<version>-<YYYY-MM-DD>.pptx
```

The `sizings/*.pptx` path is allowed through the PreToolUse
`hooks/sizing-guard.py` hook (binary file - the hook skips text scans and
passes it directly).

### Authoritative-numbers invariant

`scripts/render-pptx.py` re-runs `framework/compute_totals.py:compute_core_totals()`
on the loaded JSON before building slides. This means the PPTX always reflects
fresh Python-authoritative numbers even if the JSON's `computed_totals` block
was edited or is stale - the same guarantee the HTML compiler already enforces.

### Step 1 - Run scripts/render-pptx.py

Do NOT hand-roll the PPTX generation or bypass the script. Use the plugin
script, which re-computes totals AND invokes the same authoritative
`framework/compute_totals.py` path that the HTML render does:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render-pptx.py \
  --spec sizings/<customer-slug>-<N>year-sizing-v<version>-<YYYY-MM-DD>.json \
  --out  sizings/<customer-slug>-<N>year-sizing-v<version>-<YYYY-MM-DD>.pptx
```

The script:

1. Reads the spec JSON from `--spec`.
2. Re-runs `compute_core_totals()` on the loaded spec for authoritative numbers.
3. Calls `renderer/pptx/build_pptx.build(spec, pricing)` to generate the PPTX
   bytes (up to **10 slides**, all toggles on - see the deck map below).
4. Writes the result to `--out`.

### Deck map (up to 10 slides)

Six slides are mandatory; four are toggleable via `meta` flags (all default
`true`), so the count ranges from 6 (everything off) to 10 (everything on):

| # | Slide | Donor | Toggle (`meta.*`, default true) |
|---|-------|-------|---------------------------------|
| 1 | Title | title | - |
| 2 | Safe Harbor | safe_harbor | `include_safe_harbor` |
| 3 | Agenda | agenda | `include_agenda` |
| 4 | Cost Detail by Year (table) | table_styled | - |
| 5 | Year-by-Year Costs (stacked-column chart; per-year ACV totals in subtitle) | content | - |
| 6 | Cost Mix doughnut (chart) | content | `include_workload_donut` |
| 7 | Warehouse Workloads (table) | table_styled | - |
| 8 | Serverless & AI / Cortex (table) | table_styled | - |
| 9 | Scenario Comparison (table) | table_styled | `include_scenarios` |
| 10 | Closer / Thank-you | thank_you | - |

Key assumptions, open items to confirm, and next steps live in the **closer's
speaker notes**, not on their own slides.

**Year-by-Year slide (slide 5):** the subtitle lists each year's ACV (annual
contract value = `core_year_total[y]`) in dollars; exact dollars for terms up to
3 years, abbreviated beyond that so the line stays on one line and does not wrap
into the chart.

**Doughnut (slide 6):** primary mode plots each workload's Year-1 warehouse
credits ("Compute Mix by Workload"); with fewer than two workloads it falls
back to the Compute/Serverless/AI/Storage cost mix ("Cost Mix by Category").

**Scenario engine (slide 9) - consistency invariant:** the Conservative /
Expected / Aggressive rows re-run the SAME `compute_core_totals()` engine on a
deep-copied spec. Levers are a go-live month shift plus a RELATIVE ramp-curve
step along `fastest < fast < linear < slow < slowest`. Both push credits the
same direction, so TCV is always monotone **Conservative <= Expected <=
Aggressive**. The Expected row applies no change and reuses the authoritative
`computed_totals`, so its TCV equals the deck headline exactly. (Never force an
absolute curve like `slow`: it is faster than a `slowest` baseline and would
flip Conservative above Expected.) Override the defaults with an optional
`spec.scenarios` list of `{label, go_live_delta, curve_steps}`.

If the script exits non-zero, inspect stderr for the error, fix the underlying
spec if needed, and re-run. Do NOT write the PPTX manually.

**Live export path (one-click bridge).** The HTML proposal has an "Export JSON
for PPTX" button next to "Save HTML". To make that button produce a real `.pptx`
in one click, start the local render bridge first:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/serve-pptx.py
```

With the bridge running, clicking the button POSTs the in-browser `SIZING_SPEC`
to `http://127.0.0.1:8765/render-pptx`, which runs the same `build_pptx.build()`
path as this CLI - authoritative `computed_totals` are recomputed server-side and
internal pricing is stripped - and the browser downloads
`<slug>-...-v<n>-<date>.pptx` directly. No server-side file is written.

If the bridge is **not** running, the button silently falls back to downloading
the `<slug>-...-v<n>-<date>.json` spec (the legacy behavior); pass that JSON as
`--spec` to `render-pptx.py` to pick up browser-side edits without re-running the
full pipeline. Emailed/standalone proposals always use this JSON fallback.

### Step 2 - Confirm output

The script prints the output path on success:

```
PPTX written: sizings/<slug>-<N>year-sizing-v<version>-<date>.pptx
```

---

## Phase 8 - Visual QA loop

### Step 1 - Export slides to images

Run `scripts/pptx-qa-export.sh` with the PPTX path. The script uses headless
LibreOffice to convert each slide to a PNG under `temp/`:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/pptx-qa-export.sh \
  sizings/<customer-slug>-<N>year-sizing-v<version>-<YYYY-MM-DD>.pptx
```

On success the script prints each slide path:

```
temp/<slug>-slide-01.png
temp/<slug>-slide-02.png
...
temp/<slug>-slide-NN.png
```

If `soffice` / `libreoffice` is not found, the script exits with a clear
error. Install LibreOffice and retry. LibreOffice is the only supported
export backend - no alternative path is attempted.

### Step 2 - Visual QA subagent

Delegate to a visual-QA subagent (Task tool, foreground) with the slide image
paths returned in Step 1. The subagent reads each PNG and reports:

- Slide count matches expected (10 with every toggle on; subtract one per
  disabled toggle, down to a 6-slide floor).
- Title slide: customer name present, Snowflake branding visible, no truncated text.
- Cost Detail slide: per-year category figures match `computed_totals`; Total row bold.
- Year-by-year slide: chart series match `computed_totals.core_year_total`; the
  subtitle lists each year's ACV total in dollars and does not wrap into the chart.
- Cost Mix doughnut: slices render with a legend; title reads "Compute Mix by
  Workload" (multi-workload) or "Cost Mix by Category" (single-workload fallback).
- Workloads slide: all workloads from `spec.workloads` appear; no row overflow.
- Serverless/AI slide: figures consistent with spec values.
- Scenario Comparison: three rows, TCV monotone Conservative <= Expected <=
  Aggressive, the Expected row bold and its TCV equal to the deck headline.
- No em-dashes (U+2014 / U+2013) and no unsubstituted tokens on any slide.
- Any layout issue: text overflow, white boxes, missing chart, blank slide.

The subagent returns a structured report:

```
VISUAL QA RESULT: PASS | FAIL
Issues found:
  - <issue description, slide N>
```

### Step 3 - Fix loop

If the subagent returns FAIL:

1. Identify the root cause in `renderer/pptx/` (slides.py, charts.py, brand.py,
   build_pptx.py) or in the spec JSON itself.
2. Fix the underlying source (do NOT edit the `.pptx` file directly).
3. Re-run `scripts/render-pptx.py --spec ... --out ...` to regenerate.
4. Re-run `scripts/pptx-qa-export.sh` to refresh slide images.
5. Re-delegate to the visual-QA subagent.
6. Repeat until PASS (max 3 iterations before escalating to the SE for guidance).

On PASS: proceed to Phase 8 output summary.

---

## Phase 8 output summary

Print to terminal:

```
Generated:
   sizings/<slug>-<N>year-sizing-v<version>-<date>.pptx  (Snowflake-branded PPTX)
   sizings/<slug>-<N>year-sizing-v<version>-<date>.html  (interactive sizing proposal)
   sizings/<slug>-<N>year-sizing-v<version>-<date>.json  (portable sizing spec)
   temp/<slug>-research-evidence.md                      (Glean + Gong audit trail)
   temp/<slug>-slide-01.png ... temp/<slug>-slide-NN.png (QA slide images)

   Visual QA: PASS  (<N> slides checked)

<CUSTOMER> - <N>-Year Consumption Estimate
  Edition: <EDITION> | <CLOUD> <REGION> | $<CREDIT_RATE>/credit

  Year 1:  $<XX,XXX>  (<XX,XXX> credits)
  Year 2:  $<XX,XXX>
  Year 3:  $<XX,XXX>
  --------------------
  Core TCV (Python-authoritative): $<XXX,XXX>

Open in PowerPoint: open sizings/<slug>-<N>year-sizing-v<version>-<date>.pptx
One-click export:   run scripts/serve-pptx.py, then click "Export JSON for PPTX"
  in the HTML proposal to download a .pptx directly (totals recomputed
  server-side). If the bridge is down, the button downloads JSON instead; pass
  it as --spec to render-pptx.py to pick up browser-side edits.
```
