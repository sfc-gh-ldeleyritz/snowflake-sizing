---
name: snowflake-sizing-render-html
description: Phase 5 + 6 of snowflake-sizing - serialize SIZING_SPEC, substitute template tokens, run the parallel quality gates, and print the final summary.
---

# Render-HTML sub-skill (snowflake-sizing)

Loaded by the parent `snowflake-sizing` skill after the build-spec sub-skill
returns. Inputs available: complete `SIZING_SPEC` dict, `meta` object,
year-by-year totals from Phase 4.

Load these references on demand from `${CLAUDE_PLUGIN_ROOT}/skills/snowflake-sizing/references/`:

- `html-spec.md` - the full template token + DOM-shape reference (1000+ lines, only loaded HERE)
- `content-hygiene.md` - the visible-text rules (also referenced by the gate)

---

## Phase 5 - Generate spec + HTML, run parallel gates

Output paths (both go to the git-tracked `sizings/` directory):

```
Spec:  sizings/<customer-slug>-<N>year-sizing-v<version>-<YYYY-MM-DD>.json
HTML:  sizings/<customer-slug>-<N>year-sizing-v<version>-<YYYY-MM-DD>.html
```

Where `customer-slug` is the customer name lowercased with spaces -> hyphens
and non-alphanumerics stripped, `version` is `SIZING_SPEC.meta.version_number`
(set to 1 in Phase 1), and `YYYY-MM-DD` is today's date.

### Step 1 - Write the spec JSON FIRST

Serialize the complete `SIZING_SPEC` as pretty-printed JSON and Write to
`sizings/<slug>-<N>year-sizing-v<version>-<date>.json`. The PostToolUse hook
`hooks/validate-sizing-json.py` runs automatically and BLOCKS on any
structural error. If blocked, fix the spec and re-Write.

The JSON write must succeed before touching the template - if HTML
generation fails downstream, the spec is already saved.

### Step 2 - Run spec-validate (BLOCKING)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/spec-validate.py sizings/<slug>-<N>year-sizing-v<version>-<date>.json
```

If exit code is non-zero, fix the field-name errors flagged and re-Write the
JSON before continuing. Both the script and the PostToolUse hook share the
schema-driven validation in `framework/sizing_spec_schema.json` via
`scripts/_schema_loader.py`.

### Step 3 - Generate the HTML

1. Read `${CLAUDE_PLUGIN_ROOT}/assets/templates/proposal-template.html`
2. Read `${CLAUDE_PLUGIN_ROOT}/assets/branding/_brand_fonts.css`
3. Substitute every token below (NOW load `references/html-spec.md` if you
   need detail on the DOM contract):

| Token | Value |
|---|---|
| `__BRAND_FONTS_CSS__` | full contents of `_brand_fonts.css` |
| `__PRICING_DATA__` | full contents of `assets/snowflake_pricing_master.json` |
| `__SIZING_SPEC__` | the complete SIZING_SPEC JSON (from Phase 4) |
| `__CUSTOMER__` | customer display name |
| `__EDITION__` | Snowflake edition |
| `__CLOUD__` | `AWS` / `Azure` / `GCP` |
| `__REGION__` | deployment region |
| `__YEARS__` | contract length as integer |
| `__CREDIT_RATE__` | per-credit dollar rate |
| `__DATE__` | today's date (YYYY-MM-DD) |
| `__PDF_VERSION__` | `meta.pdf_version` |

4. Write the result to `sizings/<slug>-<N>year-sizing-v<version>-<date>.html`.
   The `hooks/content-hygiene.py` PostToolUse hook runs automatically and
   BLOCKS on forbidden patterns (citation prefixes / internal artefact
   filenames / etc. in customer-facing text). If blocked, fix the SIZING_SPEC
   visible-text fields, regenerate the HTML, and re-Write.

Do NOT modify any other part of the template.

### Step 4 - Run the three independent quality gates IN PARALLEL

In a single Bash invocation, run all three checks simultaneously using
background jobs and `wait`. They are independent and read-only on the
artifacts.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/html-render-check.py    sizings/<slug>-...html > /tmp/render.txt 2>&1 &
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/emdash-check.py         sizings/<slug>-...html temp/<slug>-research-evidence.md > /tmp/emdash.txt 2>&1 &
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/content-hygiene-check.py sizings/<slug>-...html > /tmp/hygiene.txt 2>&1 &
wait
cat /tmp/render.txt /tmp/emdash.txt /tmp/hygiene.txt
```

All three must exit 0. If any one failed:

- `html-render-check` failure - the page would render as $0 in a real browser.
  Read the JS stack trace, fix the root cause in the SIZING_SPEC, and re-do
  steps 1-4. Common causes: zero `credit_rate`, missing AI key, all ramps
  outside year 1.
- `emdash-check` failure - replace each U+2014 occurrence with ` - ` (space
  hyphen space) in the source artifact (likely the SIZING_SPEC) and re-do
  steps 1-4.
- `content-hygiene-check` failure - rewrite the offending fields in the
  SIZING_SPEC as plain customer-facing prose (no citation prefixes, no file
  names, no personal names) and re-do steps 1-4.

---

## Phase 6 - Output summary

Print to terminal:

```
Generated:
   sizings/<slug>-<N>year-sizing-v<version>-<date>.html   (interactive sizing proposal)
   sizings/<slug>-<N>year-sizing-v<version>-<date>.json   (portable sizing spec)
   temp/<slug>-research-evidence.md                       (Glean + Gong audit trail)

   spec-validate: PASS
   html-render-check: PASS
   emdash check: PASS
   content hygiene: PASS

<CUSTOMER> - <N>-Year Consumption Estimate
  Edition: <EDITION> | <CLOUD> <REGION> | $<CREDIT_RATE>/credit

  Year 1:  $<XX,XXX>  (<XX,XXX> credits)
  Year 2:  $<XX,XXX>
  Year 3:  $<XX,XXX>
  --------------------
  TCV:     $<XXX,XXX>

Top 3 workloads by credit volume:
  1. <Workload label> - <XX,XXX> cr/yr (<XX>%)
  2. <Workload label> - <XX,XXX> cr/yr (<XX>%)
  3. <Workload label> - <XX,XXX> cr/yr (<XX>%)

Requires Confirmation:
  - <confirm_required item 1>
  - <confirm_required item 2>
  ...

Open in browser: open sizings/<slug>-<N>year-sizing-v<version>-<date>.html
Print / Save as PDF: click the "Print / Save as PDF" button in the proposal
  (Cmd-P; in the print dialog expand More Settings and uncheck Headers and footers).
Save Version: click "Save Version" to download a self-contained HTML with the SE's
  current edits embedded; the version number auto-increments each save.
Export JSON: click "Export JSON" to download the current SIZING_SPEC as a portable
  .json file (round-trip browser edits, or feed future export skills).
```
