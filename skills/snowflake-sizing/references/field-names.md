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
cortex_fine_tuning, cortex_functions, ai_embed
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

## New fields (v3.0.0 / SF-01..SF-11)

| Field | Feature | Notes |
|---|---|---|
| `workloads[].kind` | SF-01 | `"standard"` (default) \| `"unit_based"`. When `"unit_based"`, warehouse-hour fields are ignored; use the unit fields below instead. |
| `workloads[].cost_per_unit`, `unit_count_start`, `unit_count_end`, `unit_ramp_months`, `growth_rate` | SF-01 | Per-unit (e.g. per-tenant) monthly cost model. Ramps linearly from `unit_count_start` to `unit_count_end` over `unit_ramp_months`, then grows at `growth_rate` (falls back to `meta.annual_growth_rate`). |
| `workloads[].rollout_kind` | SF-02 | `"phased_multi_tenant"` pushes `go_live_month` to at least 12 and defaults `ramp_curve` to `"slow"` unless explicitly set. |
| `workloads[].avg_clusters_override` | SF-03 | Explicit average-cluster count; takes priority over the peak-fraction formula and the naive `(clusters_min + clusters_max)/2` midpoint. |
| `workloads[].peak_hours_per_day` | SF-03 | Hours/day running at `clusters_max`; used to derive an average-cluster estimate via peak fraction when `avg_clusters_override` is absent. |
| `workloads[].active_fraction` | SF-04 | 0-1 multiplier on `hours_per_day` modeling auto-suspend idle time. `null`/absent = `1.0` (no change). |
| `workloads[].zero_copy_source` | SF-09 | `true` = workload contributes $0 to warehouse credits/storage/ingest (e.g. zero-copy share). Listed in `computed_totals.zero_copy_sources`. |
| `workloads[].interactive.{enabled, min_clusters, max_clusters, fallback_warehouse_size, fallback_hours_per_day}` | SF-10 | App-serving warehouse billed 24h/day at the interactive-warehouse rate; optional fallback warehouse adds its own hours/day contribution. |
| `openflow.instances[].runtime_mode` | SF-05 | `"always_on"` (default, 730 hrs/mo) \| `"scheduled"` (uses `refresh_hours_per_run × runs_per_month`). |
| `openflow.instances[].refresh_hours_per_run`, `runs_per_month` | SF-05 | Only read when `runtime_mode = "scheduled"`. |
| `openflow.instances[].deployment` | SF-11 | `"BYOC"` \| `"SPCS"`. Defaults to `BYOC` on AWS, `SPCS` elsewhere. `SPCS` bills SPCS CPU-family rates plus an always-on control-pool node. |
| `ai_cortex.cortex_complete.{active_entities, summaries_per_entity_per_mo, avg_input_tokens_per_call, avg_output_tokens_per_call, caching_reduction_pct}` | SF-06 | Usage-model inputs; derive `monthly_input_tokens_M`/`monthly_output_tokens_M` when the raw token fields are absent. Explicit raw tokens always win if both are present. |
| `meta.target_budget` | SF-07 | SE-supplied budget anchor (USD TCV). When Year-1 cost exceeds 2x this value, a non-blocking warning fires in Python, JS, and the guard hook. |
| `meta.per_unit_benchmark` | SF-07 | Optional per-unit cost benchmark (USD/unit/month); reserved for future per-unit reasonableness checks (not yet wired into JS). |
| `scenarios.<tier>.intensity_factor` | SF-08 | Multiplier (default `1.0`) on warehouse + AI credits for that scenario tier. Serverless credits are intentionally NOT scaled by intensity. |

### Guided prompts (Phase 3 discovery)

Ask the SE:
- Is this a phased / multi-tenant SaaS rollout? (triggers SF-02 defaults)
- Is Salesforce or other data arriving via zero-copy share? (SF-09)
- Is this a high-concurrency app-serving workload? (SF-10 interactive)
- What is the customer's stated budget or per-tenant cost target? (SF-07)

