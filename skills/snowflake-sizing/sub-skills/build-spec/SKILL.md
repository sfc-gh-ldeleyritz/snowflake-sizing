---
name: snowflake-sizing-build-spec
description: Phase 3 + 4 of snowflake-sizing - assemble a customer-specific patch dict and run scripts/spec-prepare.py to produce a validated, ramp-aware SIZING_SPEC with authoritative computed_totals.
---

# Build-Spec sub-skill (snowflake-sizing)

Loaded by the parent `snowflake-sizing` skill after the research sub-skill
returns. Inputs available: bootstrapped `meta` object, evidence file path,
context file content, top-3 findings summary.

Load these references on demand from `${CLAUDE_PLUGIN_ROOT}/skills/snowflake-sizing/references/`:

- `sizing-methodology.md` - the rulebook (always loaded for Phase 3)
- `field-names.md` - the wrong-vs-correct field-name reference (most cases
  are now auto-corrected by spec-prepare; reference is for the few that
  still require manual attention)
- `ai-feature-defaults.md` - cortex_code 3-surface form, cortex_complete
  default model, optional Document AI placeholder shape
- `content-hygiene.md` - rules for what may NEVER appear in customer-facing fields

---

## Phase 3 - Build the SIZING_SPEC patch and run spec-prepare

In v1.8 the agent no longer constructs the full SIZING_SPEC dict by hand.
Instead, build a small **patch dict** containing only the customer-specific
deltas; everything else (the 9 ai_cortex placeholders, 27 serverless
placeholders, structurally complete meta) is supplied by
`framework/sizing_spec_skeleton.json` and merged in by spec-prepare.

### Content hygiene (MANDATORY)

Before writing any visible-text field (`label`, `justification`, `note`,
`description`, `assumptions[]`, `confirm_required[].item`), apply the rules
in `references/content-hygiene.md`:

- No personal names from Gong transcripts.
- No internal artefact filenames.
- No citation prefixes (`SOURCED:`, `ASSUMPTION:`, `REQUIRES_CONFIRMATION:`)
  in customer-facing prose - those go only in the bare `source` enum field.

### Patch dict shape

The patch is a partial SIZING_SPEC tree with only the keys you intend to
override or fill in. spec-prepare deep-merges it over the skeleton.
Minimum patch covers `meta`, `workloads`, `storage.standard`, evidence-
backed AI / serverless features, `assumptions`, `confirm_required`.

Example patch:

```json
{
  "meta": {
    "customer": "Test Corp",
    "edition": "Enterprise",
    "cloud": "AWS",
    "region": "us-east-1",
    "credit_rate": 2.0,
    "ai_credit_rate": 2.0,
    "storage_rate_per_tb": 23.0,
    "hybrid_tables_storage_rate_per_gb": 0.04,
    "contract_years": 3,
    "annual_growth_rate": 0.20,
    "default_dev_start_month": 2,
    "default_go_live_month": 11,
    "list_credit_rate": 4.0,
    "version_number": 1
  },
  "workloads": [
    {
      "id": "wh-elt", "label": "ELT / Transformation",
      "size": "S", "hours_per_day": 3.0, "days_per_month": 22,
      "clusters_min": 1, "clusters_max": 1, "auto_suspend_seconds": 60,
      "dev_start_month": 1, "go_live_month": 3,
      "ramp_curve": "linear",
      "source": "SOURCED",
      "justification": "<plain customer-facing prose - no citation prefix>"
    }
  ],
  "storage": {
    "standard": {
      "raw_tb_year1": 50,
      "compression_ratio": 3,
      "annual_growth_pct": 25,
      "time_travel_days": 1,
      "churn_rate_pct": 10
    }
  },
  "ai_cortex": {
    "cortex_complete": {
      "enabled": true, "model": "claude-sonnet-4-6",
      "monthly_input_tokens_M": 100,
      "monthly_output_tokens_M": 30
    }
  },
  "serverless": {
    "snowpipe": { "enabled": true, "gb_per_month": 1000 }
  },
  "assumptions": ["Annual growth applied year-over-year from year 2 onwards."],
  "confirm_required": [
    { "item": "Confirm 25%/yr storage growth rate", "impact_pct": 10 }
  ]
}
```

### What you don't need to do (handled by spec-prepare)

- Don't write the 12 ai_cortex disabled placeholders - the skeleton has
  them (the 9 schema-required keys plus the 3 optional Document AI
  siblings - `document_ai`, `ai_parse_document_layout`,
  `ai_parse_document_ocr` - which the skeleton seeds disabled so the
  template's `populateAIPanel()` and `calcAICost` paths never have to
  dereference an undefined node).
- Don't write the 27 serverless disabled placeholders - the skeleton has them.
- Don't worry about legacy field names - spec-prepare auto-renames
  `storage_growth_pct` -> `annual_growth_pct`, `monthly_tokens_input` ->
  `monthly_input_tokens_M`, `indexed_gb` -> `indexed_data_gb`,
  `monthly_credits` -> `compute_hours_monthly`, and splits `avg_clusters`
  into `clusters_min`/`clusters_max` automatically. The PreToolUse hook
  will block any spec that still contains these legacy names.
- Don't compute `computed_totals` manually - spec-prepare does it via
  `framework/compute_totals.py`, ported from the JS recalculate() so the
  values match the rendered HTML to the cent for the core categories.

### Workloads guidance

Apply the warehouse sizing rules from `sizing-methodology.md`. Apply MCW
(`clusters_min`/`clusters_max`) when concurrency rules trigger. Always
include a Development workload (XS, ~4 hrs/day, 22 days). Label every
numeric input: `source = SOURCED` (cite in `justification`), `source =
ASSUMPTION` (explain in `justification` AND add to `confirm_required`
with quantified impact), or `source = ESTIMATED` (range-bounded but not pinned).

### Serverless / AI / SPCS / OpenFlow / Replication

Set `enabled=true` only with evidence. Use `references/ai-feature-defaults.md`
for AI defaults. For OpenFlow, `warehouse_size` MUST be the full name
(`X-Small`, `Small`, `Medium`), NOT abbreviated. For Replication, see
`references/research-protocol.md` Section 7 for the populated-fields list.

### Storage

Set `time_travel_days=1` and `churn_rate_pct=10` unless evidence states
otherwise. Apply compression defaults from `sizing-methodology.md`. The
field is `annual_growth_pct` (a percentage 0-100, not a fraction).

### Run spec-prepare

Write the patch dict to a temp file under `temp/` and call:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/spec-prepare.py \
  --patch temp/<slug>-patch.json \
  --out sizings/<slug>-<N>year-sizing-v<version>-<YYYY-MM-DD>.json
```

The script:

1. Deep-merges the patch over the skeleton.
2. Auto-renames legacy field names (with warnings logged so you can fix
   the source patch on the next iteration).
3. Strips internal markers (`_skeleton_marker`, `_comment`, etc.).
4. Computes authoritative core TCV via `framework/compute_totals.py` and
   stamps `computed_totals` into the spec.
5. Runs schema validation.
6. Writes the output. Prints the core TCV summary on stdout.

If spec-prepare exits non-zero, fix the patch and re-run. The script's
errors include the schema path of the offending field.

---

## Phase 4 - Inspect computed_totals (replaces the old hand-computed math)

`computed_totals` is now the single source of truth for the build-time
core TCV. Inspect the values and confirm they match expectations:

```
core TCV: $XXX,XXX  (per-year ['$YY', '$YY', '$YY'])
```

If the core TCV is dramatically off (e.g., $0, or 5x customer's stated
budget), the patch likely has a structural error not caught by validation.
Common causes:

- All workloads have `dev_start_month` and `go_live_month` outside year 1
  (no ramp = no compute).
- `meta.credit_rate` was left at 0.
- `workloads` is empty.

Phase 4 used to apply ramp + growth math by hand. spec-prepare does this
now, in lockstep with the JS template. Print the per-year breakdown to
the terminal:

```
Year | Compute $ | Serverless $ | AI $ | Storage $ | Core $
  1  |    ...    |     ...      |  ... |    ...    |  ...
  2  |    ...    |     ...      |  ... |    ...    |  ...
  3  |    ...    |     ...      |  ... |    ...    |  ...
Core TCV: $XXX,XXX (warehouse + serverless + ai + storage)
Note: SPCS, OpenFlow, Replication, Transfer, Collab are computed JS-side
at render time and add to the customer-visible TCV.
```

The render-html sub-skill will pick up `computed_totals` from the spec and
the JS will display the full TCV at first load.

---

Hand control back to the parent skill, which will invoke the `render-html`
sub-skill next.