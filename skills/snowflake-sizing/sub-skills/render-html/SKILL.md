---
name: snowflake-sizing-render-html
description: Phase 5 + 6 of snowflake-sizing - run scripts/render-html.py to substitute the proposal template, write the HTML (the PreToolUse sizing-guard hook validates pre-write), print the final summary.
---

# Render-HTML sub-skill (snowflake-sizing)

Loaded by the parent `snowflake-sizing` skill after the build-spec sub-skill
returns. Inputs available: complete `SIZING_SPEC` JSON written by
spec-prepare.py to `sizings/<slug>-<N>year-sizing-v<version>-<date>.json`,
including the `computed_totals` block.

Load this reference on demand from `${CLAUDE_PLUGIN_ROOT}/skills/snowflake-sizing/references/`:

- `html-spec.md` - the full template token + DOM-shape reference (1000+ lines, only loaded HERE)

---

## Phase 5 - Generate HTML

Output paths (both go to the git-tracked `sizings/` directory):

```
Spec:  sizings/<customer-slug>-<N>year-sizing-v<version>-<YYYY-MM-DD>.json   (already written by spec-prepare in Phase 3)
HTML:  sizings/<customer-slug>-<N>year-sizing-v<version>-<YYYY-MM-DD>.html
```

The single PreToolUse hook `hooks/sizing-guard.py` runs automatically on
both Writes:

- **JSON Write** (handled by spec-prepare in Phase 3): the hook re-checks
  schema validity, legacy field names, and leakage fields. spec-prepare's
  output is built to pass; the hook is a belt-and-braces guard.
- **HTML Write** (this phase): the hook scans for em-dashes, content-hygiene
  tokens, unsubstituted template tokens, and runs the Node sidecar render
  check. Block on any failure - retry the HTML write after fixing the
  underlying SIZING_SPEC.

### Step 1 - Run scripts/render-html.py

Do NOT hand-roll the token substitution and do NOT use bash redirects /
`python -c ...open(...).write()` heredocs to drop the HTML on disk -
those code paths bypass the PreToolUse hook entirely. Use the plugin
script, which performs the substitution AND invokes the same
`hooks/sizing-guard.py` gate the real `Write` tool would trigger:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render-html.py \
  --spec sizings/<customer-slug>-<N>year-sizing-v<version>-<YYYY-MM-DD>.json \
  --out  sizings/<customer-slug>-<N>year-sizing-v<version>-<YYYY-MM-DD>.html
```

The script reads
`${CLAUDE_PLUGIN_ROOT}/assets/templates/proposal-template.html`,
`${CLAUDE_PLUGIN_ROOT}/assets/branding/_brand_fonts.css`, and
`${CLAUDE_PLUGIN_ROOT}/assets/snowflake_pricing_master.json` (deep-stripping
`utility_queries_reference` blocks before the JSON reaches the HTML),
substitutes every token below, and writes the result atomically only
after the sizing-guard hook returns PASS. If the hook blocks, the script
exits non-zero with the hook's reason - fix the underlying SIZING_SPEC
and re-run; do NOT try to write the HTML through `Write` to "skip" the
script. Load `${CLAUDE_PLUGIN_ROOT}/skills/snowflake-sizing/references/html-spec.md`
on demand for the full DOM contract.

| Token | Value (handled by render-html.py) |
|---|---|
| `__BRAND_FONTS_CSS__` | full contents of `_brand_fonts.css` |
| `__PRICING_DATA__` | `assets/snowflake_pricing_master.json` with `utility_queries_reference` blocks deep-stripped |
| `__SIZING_SPEC__` | the complete SIZING_SPEC JSON |
| `__CUSTOMER__` | `meta.customer` |
| `__EDITION__` | `meta.edition` |
| `__CLOUD__` | `meta.cloud` |
| `__REGION__` | `meta.region` |
| `__YEARS__` | `meta.contract_years` |
| `__CREDIT_RATE__` | `meta.credit_rate` |
| `__DATE__` | `meta.generated_date` (or today) |
| `__PDF_VERSION__` | `meta.pdf_version` |

The two `__SIZING_SPEC_BEGIN__` / `__SIZING_SPEC_END__` sentinels are
deliberately preserved by the script - the in-page Save Version code
uses them as splice markers.

### Step 2 - Confirm hook approval

The script prints `sizing-guard hook: PASS` on success. That single line
covers all four checks the hook runs against the rendered HTML:

- Em-dash scan
- Content-hygiene scan (forbidden tokens / internal artefact filenames)
- Substitution-completeness (no `__TOKEN__` left except the sentinels)
- Node sidecar render check (DOM parses, kpi-tcv resolves to non-zero)

The legacy standalone scripts (`scripts/emdash-check.py`,
`scripts/content-hygiene-check.py`, `scripts/html-render-check.py`) remain
available for manual / verbose runs but the agent does not need to
invoke them in the normal path.

---

## Phase 6 - Output summary

Print to terminal:

```
Generated:
   sizings/<slug>-<N>year-sizing-v<version>-<date>.html   (interactive sizing proposal)
   sizings/<slug>-<N>year-sizing-v<version>-<date>.json   (portable sizing spec)
   temp/<slug>-research-evidence.md                       (Glean + Gong audit trail)

   sizing-guard hook: PASS  (schema, hygiene, em-dash, render)

<CUSTOMER> - <N>-Year Consumption Estimate
  Edition: <EDITION> | <CLOUD> <REGION> | $<CREDIT_RATE>/credit

  Year 1:  $<XX,XXX>  (<XX,XXX> credits)
  Year 2:  $<XX,XXX>
  Year 3:  $<XX,XXX>
  --------------------
  Core TCV (build-time, spec-prepare): $<XXX,XXX>
  Full TCV (render-time, JS): $<XXX,XXX>
  (Delta = SPCS + OpenFlow + Replication + Transfer + Collab, computed JS-side)

Top 3 workloads by credit volume:
  1. <Workload label> - <XX,XXX> cr/yr (<XX>%)
  2. <Workload label> - <XX,XXX> cr/yr (<XX>%)
  3. <Workload label> - <XX,XXX> cr/yr (<XX>%)

Requires Confirmation:
  - <confirm_required item 1>
  - <confirm_required item 2>
  ...

Open in browser: open sizings/<slug>-<N>year-sizing-v<version>-<date>.html
Save as PDF: click the "Print / Save as PDF" button, then choose Save as PDF as the
  destination (expand More Settings and uncheck Headers and footers for a clean output).
Save HTML: click "Save HTML" to download a self-contained HTML with the SE's
  current edits embedded; the version number auto-increments each save.
```
