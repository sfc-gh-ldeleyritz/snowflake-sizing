# SIZING_SPEC field-name reference

> The HTML renderer reads specific field paths without optional chaining.
> Wrong field names silently compute $0. Always use the exact paths below.

Loaded by: `sub-skills/build-spec/SKILL.md`. The full canonical contract is in
`framework/sizing_spec_schema.json`; this document is the human-readable lookup
for the most common footguns.

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

No `avg_clusters` - replaced by `clusters_min` + `clusters_max`. The JS engine
computes `avg = (clusters_min + clusters_max) / 2`.

## AI / Cortex field names

| Feature | Correct path | Wrong (never use) |
|---|---|---|
| Cortex Complete tokens | `ai_cortex.cortex_complete.monthly_input_tokens_M` + `monthly_output_tokens_M` (millions) | `monthly_tokens_input` |
| Cortex Search index | `ai_cortex.cortex_search.indexed_data_gb` | `indexed_gb` |
| AI Extract | `ai_cortex.cortex_functions.ai_extract.tokens_M_monthly` | top-level `ai_cortex.ai_extract` |
| Serverless compute features | `compute_hours_monthly` on each serverless item | `monthly_credits` |
| Storage volume | `storage.standard.raw_tb_year1` | `storage.raw_tb` |
| OpenFlow MERGE warehouse | `warehouse_size: "X-Small"` (full name) | `"XS"` (abbreviation) |

## Required ai_cortex sub-keys (12)

All of these MUST be present in `ai_cortex` even if disabled. `populateAIPanel()`
dereferences each one without optional chaining; missing any one throws a
TypeError at boot and the page silently renders as $0.

```
cortex_complete, cortex_agents, snowflake_intelligence,
cortex_code, cortex_analyst, cortex_search,
document_ai, ai_parse_document_layout, ai_parse_document_ocr,
cortex_fine_tuning, cortex_functions, embeddings
```

## Required cortex_functions sub-keys (6)

The renderer iterates these unconditionally:

```
ai_classify, ai_sentiment, ai_summarize,
ai_translate, ai_extract, ai_transcribe
```

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
