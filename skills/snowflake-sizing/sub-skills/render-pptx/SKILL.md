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
   bytes (7 slides: Title, Exec Summary/TCV, Workloads Detail, Year-by-Year
   Costs, Serverless/AI Breakdown, Assumptions, Closer).
4. Writes the result to `--out`.

If the script exits non-zero, inspect stderr for the error, fix the underlying
spec if needed, and re-run. Do NOT write the PPTX manually.

**Live export path.** The HTML proposal has an "Export for PPTX" button next to
"Save HTML". Clicking it syncs the SE's in-browser edits back into `SIZING_SPEC`
and downloads a `<slug>-...-v<n>-<date>.json` file. Pass that downloaded JSON
as `--spec` to pick up browser-side edits without re-running the full pipeline.

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

- Slide count matches expected (7 slides).
- Title slide: customer name present, Snowflake branding visible, no truncated text.
- Exec summary/TCV slide: TCV figure matches `computed_totals.core_tcv` from the spec.
- Workloads slide: all workloads from `spec.workloads` appear; no row overflow.
- Year-by-year slide: chart series match `computed_totals.core_year_total` array.
- Serverless/AI slide: figures consistent with spec values.
- Assumptions slide: no em-dashes (U+2014 / U+2013), no unsubstituted tokens.
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
Export for PPTX:    click the "Export for PPTX" button in the HTML proposal to
  download an updated JSON; pass it as --spec to render-pptx.py to pick up
  any browser-side edits.
```
