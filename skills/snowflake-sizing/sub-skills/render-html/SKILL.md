---
name: snowflake-sizing-render-html
description: Phase 5 + 6 of snowflake-sizing - substitute template tokens, write the HTML (the PreToolUse sizing-guard hook validates pre-write), print the final summary.
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

### Step 1 - Generate the HTML

1. Read `${CLAUDE_PLUGIN_ROOT}/assets/templates/proposal-template.html`
2. Read `${CLAUDE_PLUGIN_ROOT}/assets/branding/_brand_fonts.css`
3. Read the spec JSON written in Phase 3.
4. Substitute every token below (NOW load `references/html-spec.md` if you
   need detail on the DOM contract):

| Token | Value |
|---|---|
| `__BRAND_FONTS_CSS__` | full contents of `_brand_fonts.css` |
| `__PRICING_DATA__` | full contents of `assets/snowflake_pricing_master.json` |
| `__SIZING_SPEC__` | the complete SIZING_SPEC JSON (read from the file) |
| `__CUSTOMER__` | customer display name |
| `__EDITION__` | Snowflake edition |
| `__CLOUD__` | `AWS` / `Azure` / `GCP` |
| `__REGION__` | deployment region |
| `__YEARS__` | contract length as integer |
| `__CREDIT_RATE__` | per-credit dollar rate |
| `__DATE__` | today's date (YYYY-MM-DD) |
| `__PDF_VERSION__` | `meta.pdf_version` |

5. Write the result to `sizings/<slug>-<N>year-sizing-v<version>-<date>.html`.
   The PreToolUse hook will scan and either approve or block. If blocked,
   the agent sees the specific failures (em-dash location, forbidden-token
   line number, unsubstituted token, or JS render trace) and must fix the
   underlying SIZING_SPEC and re-Write.

Do NOT modify any other part of the template.

### Step 2 - Confirm hook approval

After the Write succeeds (no `decision: block` from the hook), the HTML
is on disk and structurally validated. No additional manual gate scripts
need to be run; `hooks/sizing-guard.py` already covered:

- Em-dash scan
- Content-hygiene scan (forbidden tokens / internal artefact filenames)
- Substitution-completeness (no `__TOKEN__` left)
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
Print / Save as PDF: click the "Print / Save as PDF" button in the proposal
  (Cmd-P; in the print dialog expand More Settings and uncheck Headers and footers).
Save Version: click "Save Version" to download a self-contained HTML with the SE's
  current edits embedded; the version number auto-increments each save.
Export JSON: click "Export JSON" to download the current SIZING_SPEC as a portable
  .json file (round-trip browser edits, or feed future export skills).
```