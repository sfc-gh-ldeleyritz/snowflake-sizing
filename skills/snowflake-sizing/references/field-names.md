# SIZING_SPEC field-name reference

> The HTML renderer reads specific field paths without optional chaining.
> Wrong field names silently compute $0. Always use the exact paths below.

Loaded by: `sub-skills/build-spec/SKILL.md`. The full canonical contract is in
`framework/sizing_spec_schema.json`; this document is the human-readable lookup
for the most common footguns.

> **In v1.8 spec-prepare.py auto-corrects the most common legacy field names**
> (marked **[auto-fixed]** below). The patch dict you write is allowed to
> use the legacy name; spec-prepare logs a rename warning and writes the
> corrected name to the final spec. The PreToolUse hook still blocks legacy
> names that escape spec-prepare so the JS renderer never sees them.

---

## Top-level structure

| Wrong | Correct | Why |
|---|---|---|
| `warehouses` | `workloads` | The JS engine reads `SIZING_SPEC.workloads`. Any other key renders as $0. |
| `storage.raw_tb` | `storage.standard.raw_tb_year1` | Storage tier shape; `raw_tb` at the top of `storage` is unread. |
| `ai_cortex.ai_extract` | `ai_cortex.cortex_functions.ai_extract` | All AI_ SQL functions live under `cortex_functions`. |

## Required workload row fields

Every entry in `workloads[]` must have:

```
id, label, size, hours_per_day, days_per_month,
clusters_min, clusters_max, auto_suspend_seconds,
source, ramp_curve, dev_start_month, go_live_month
```

`avg_clusters` is **[auto-fixed]** by spec-prepare into `clusters_min` +
`clusters_max` (both equal to the original avg). The JS engine then
computes `avg = (clusters_min + clusters_max) / 2`.

## Optional growth fields

| Field | Scope | Default when absent | Use |
|---|---|---|---|
| `meta.annual_growth_rate` | base for all categories | `0.20` | Account-wide YoY consumption growth. |
| `workloads[].growth_rate` | one warehouse row | falls back to `meta.annual_growth_rate` | Per-workload growth (e.g. ML grows faster than ELT). |
| `meta.ai_growth_rate` | AI / Cortex category | `null` -> falls back to `meta.annual_growth_rate` | Separate growth for AI consumption. |

All three are optional numbers (0-5). Growth is applied as `(1 + growth) ^ (year - 1)` on top of the ramp factor, identically in `compute_totals.py` and the HTML JS, so the build-time TCV matches the rendered TCV.

## AI / Cortex field names

| Feature | Correct path | Wrong (never use) | Auto-fixed? |
|---|---|---|---|
| Cortex Complete tokens | `ai_cortex.cortex_complete.monthly_input_tokens_M` + `monthly_output_tokens_M` (millions) | `monthly_tokens_input` | **yes** |
| Cortex Search index | `ai_cortex.cortex_search.indexed_data_gb` | `indexed_gb` | **yes** |
| AI Extract | `ai_cortex.cortex_functions.ai_extract.tokens_M_monthly` | top-level `ai_cortex.ai_extract` | no - hook blocks |
| Serverless compute features | `compute_hours_monthly` on each serverless item | `monthly_credits` | **yes** |
| Storage growth (Standard) | `storage.standard.annual_growth_pct` | `storage_growth_pct` | **yes** |
| Storage volume | `storage.standard.raw_tb_year1` | `storage.raw_tb` | no - hook blocks |
| OpenFlow MERGE warehouse | `warehouse_size: "X-Small"` (full name) | `"XS"` (abbreviation) | no - hook blocks |

## Required ai_cortex sub-keys (9 in v1.8, down from 12)

All of these MUST be present in `ai_cortex` even if disabled. The skeleton
ships them; spec-prepare deep-merges your patch over them. Missing any
one trips the schema validator and the PreToolUse hook.

```
cortex_complete, cortex_agents, snowflake_intelligence,
cortex_code, cortex_analyst, cortex_search,
cortex_fine_tuning, cortex_functions, embeddings
```

The previously-required `document_ai`, `ai_parse_document_layout`, and
`ai_parse_document_ocr` are now optional. The HTML template uses optional
chaining for the only on-render dereference, so a sizing without those
keys renders correctly. Supply them in the patch only when the customer
actively uses Document AI.

## Required cortex_functions sub-keys (6)

The renderer iterates these unconditionally:

```
ai_classify, ai_sentiment, ai_summarize,
ai_translate, ai_extract, ai_transcribe
```

## Cortex Code shape (two accepted forms)

The schema accepts both shapes; the renderer and `compute_totals.py` read the
three surfaces first and fall back to the flat fields.

- **Three-surface (canonical — emit this for new specs):**
  `cortex_code.{cli, snowsight, desktop}`, each
  `{ enabled, developers, queries_per_dev_per_day, avg_tokens_per_query }`,
  plus an optional top-level `cortex_code.model`.
- **Legacy flat (still valid):** `cortex_code.{ enabled, developers,
  queries_per_dev_per_day, avg_tokens_per_query }`. The template migrates these
  onto `cli` at render time. Existing fixtures use this form.

Both are closed objects (`additionalProperties: false`) — no other keys allowed.
See `references/ai-feature-defaults.md` for the per-surface usage defaults.

## Warehouse size enums

Workloads / collaboration accounts use abbreviations: `XS, S, M, L, XL, 2XL,
3XL, 4XL, 5XL, 6XL`.

OpenFlow `warehouse_size` MUST use full names: `X-Small, Small, Medium, Large,
X-Large, 2X-Large, 3X-Large, 4X-Large`.

## Ramp curve enum

Five named curves plus the manual flat-line:

```
fastest, fast, linear, slow, slowest, manual
```

Use `manual` with `dev_start=1, go_live=1` to pin a workload at full ramp from
month 1 onwards (e.g. ongoing production system being lifted).

## Source label enum

The `source` metadata field on each workload is one of:

```
SOURCED, ASSUMPTION, ESTIMATED
```

The full citation string (e.g. `"SOURCED: Gong abc123def turn 14 - ..."`) is
recorded inside `justification`, NOT inside `source`. The validator enforces
the enum strictly.
