# Snowflake Sizing Plugin — Design Spec

**Date:** 2026-05-22
**Status:** Approved
**Pricing PDF:** Snowflake Service Consumption Table, effective 2026-05-12

---

## Overview

A Cortex Code plugin that produces accurate, defensible Snowflake consumption estimates. The SE provides a freeform context file (transcript, questionnaire, notes); the plugin researches the customer via Glean, builds a complete sizing spec covering every billable Snowflake service, and generates a single self-contained interactive HTML proposal with live JS-powered what-if sliders.

Replaces the v1 prompt-only approach in `ldeleyritz-demos-main/consumption-estimator` with a structured plugin that covers the full May 2026 credit consumption table, multi-year projections, and interactive scenario modelling.

---

## Plugin Architecture

```
plugins/snowflake-sizing/
├── .claude-plugin/
│   └── plugin.json
├── commands/
│   └── snowflake-sizing.md          ← single entry point
├── skills/
│   └── snowflake-sizing/
│       ├── SKILL.md                 ← 6-phase workflow
│       └── references/
│           ├── sizing-methodology.md    ← warehouse/serverless/AI sizing rules
│           └── html-spec.md             ← HTML structure + JS engine contract
├── assets/
│   └── snowflake_pricing_master.json   ← all pricing data, PDF version 2026-05-12
├── examples/
│   └── MTM-sizing-3year.html
└── README.md
```

### Command invocation

```
/snowflake-sizing <context-file> [--customer "Name"] [--years 3] [--edition Enterprise] [--region "AWS US East (Northern Virginia)"]
```

**Defaults:** years=3, edition=Enterprise, region derived from context file if not specified.

**Allowed tools:** `Read`, `Write`, `Bash`, `WebFetch`, `snowflake_sql_execute`, `mcp__glean_default__search`, `mcp__glean_default__read_document`, `mcp__glean_default__chat`, `mcp__glean_default__employee_search`

---

## Workflow — 6 Phases

### Phase 1 — Parse & bootstrap

Extract customer name, context file path, years, edition, region, and credit rate from arguments. Load `assets/snowflake_pricing_master.json`. Derive `credit_rate`, `ai_credit_rate`, and `storage_rate_per_tb` for the specified edition + region.

### Phase 2 — Research in parallel

Three operations run simultaneously:

- **A. Read context file** — transcript, questionnaire, discovery notes
- **B. Glean research** — search for customer across Salesforce, Google Drive, Slack, and Gong summaries (run 3 searches in parallel: `"[customer] snowflake workloads"`, `app:gong "[customer]"`, `app:salescloud "[customer]"`). Extract: industry, company scale, existing tech stack, stated workloads, data volumes, growth signals. Same pattern as `se-comments` and `rfp-wizard` plugins.
- **C. Gong transcript SQL** — query `GONG_SHARE.GONG_DATA_CLOUD` via the **SNOWHOUSE** connection using the two-phase pattern from the `gong-transcripts` plugin: (1) find the 3 most recent calls matching the customer name via `WHERE LOWER(TITLE) LIKE LOWER('%<customer>%')`; (2) load full transcripts for the top 2 calls by joining `CALL_TRANSCRIPTS` + `CONVERSATION_PARTICIPANTS` on `CONVERSATION_KEY`. Extract: stated data volumes, tech stack signals, workload descriptions, pain points, growth plans, and pricing signals. If SNOWHOUSE is unavailable, skip silently.

### Phase 3 — Build the sizing spec

Reason through all billable categories using `sizing-methodology.md`. For every category in the consumption table, either size it from evidence or set it to zero/disabled with an explicit `ASSUMPTION` label. Apply the SOURCE-OR-ASSUMPTION rule throughout — every number is either cited or labelled. Apply the appropriate ramp-up curve for Year 1.

### Phase 4 — Apply multi-year growth

For each year 1→N: apply growth rate from context (default 20%/yr), compute per-year credits and costs. Produce a year-by-year summary.

### Phase 5 — Generate interactive HTML

Write a single self-contained file to `temp/<customer-slug>-<N>year-sizing.html`. All pricing data and the sizing spec are embedded as JS constants. The HTML contains a live JS calculation engine — every slider/toggle updates all totals and charts in real time without any server or Claude re-run. Apply Snowflake branding to html based on assets in '/Users/axross/Snowflake/Repos/aross-se-superpowers/snowflake-branding'

### Phase 6 — Output summary

Print file path, Total TCV, Year 1 cost, top 3 workloads by credit volume, and any `confirm_required` items.

---

## Sizing Spec — Full JSON Structure

The spec is the data layer for the HTML, embedded as `const SIZING_SPEC = {...}`. It also drives the initial slider values and inline calculation annotations.

```json
{
  "meta": {
    "customer": "ACME Corp",
    "edition": "Enterprise",
    "cloud": "AWS",
    "region": "US East (Northern Virginia)",
    "credit_rate": 3.00,
    "ai_credit_rate": 2.00,
    "storage_rate_per_tb": 23.00,
    "hybrid_tables_storage_rate_per_gb": 0.34,
    "contract_years": 3,
    "generated_date": "2026-05-22",
    "ramp_curve": "linear",
    "pdf_version": "2026-05-12"
  },

  "workloads": [
    {
      "id": "wh_ingest",
      "label": "Data Ingestion",
      "warehouse_type": "standard",
      "size": "M",
      "hours_per_day": 2,
      "days_per_month": 22,
      "clusters_min": 1,
      "clusters_max": 1,
      "justification": "...",
      "source": "SOURCED: questionnaire Q4"
    }
  ],

  "serverless": {
    "snowpipe":                         { "enabled": false, "files_per_month": 0 },
    "snowpipe_streaming":               { "enabled": false, "uncompressed_gb_per_month": 0 },
    "snowpipe_streaming_classic":       { "enabled": false, "client_instances": 0 },
    "serverless_tasks":                 { "enabled": false, "compute_hours_monthly": 0 },
    "serverless_tasks_flex":            { "enabled": false, "compute_hours_monthly": 0 },
    "serverless_alerts":                { "enabled": false, "compute_hours_monthly": 0 },
    "clustered_tables":                 { "enabled": false, "compute_hours_monthly": 0 },
    "materialized_views":               { "enabled": false, "compute_hours_monthly": 0 },
    "search_optimization":              { "enabled": false, "compute_hours_monthly": 0 },
    "query_acceleration":               { "enabled": false, "compute_hours_monthly": 0 },
    "replication":                      { "enabled": false, "compute_hours_monthly": 0 },
    "backup":                           { "enabled": false, "compute_hours_monthly": 0 },
    "failsafe_recovery":                { "enabled": false, "compute_hours_monthly": 0 },
    "data_quality_monitoring":          { "enabled": false, "compute_hours_monthly": 0 },
    "trust_center":                     { "enabled": false, "compute_hours_monthly": 0 },
    "table_optimization":               { "enabled": false, "compute_hours_monthly": 0 },
    "storage_lifecycle_policy":         { "enabled": false, "compute_hours_monthly": 0 },
    "hybrid_tables_requests":           { "enabled": false, "reads_gb_monthly": 0, "writes_gb_monthly": 0 },
    "copy_files":                       { "enabled": false, "compute_hours_monthly": 0 },
    "automated_refresh":                { "enabled": false, "files_per_month": 0 },
    "organization_usage":               { "enabled": false, "compute_hours_monthly": 0 },
    "sensitive_data_classification":    { "enabled": false, "compute_hours_monthly": 0 },
    "open_catalog":                     { "enabled": false, "requests_per_month_M": 0 },
    "logging":                          { "enabled": false, "file_batches_per_month": 0 },
    "telemetry_data_ingest":            { "enabled": false, "gb_per_month": 0 },
    "archive_storage_retrieval":        { "enabled": false, "files_per_month": 0 },
    "archive_storage_write":            { "enabled": false, "files_per_month": 0 }
  },

  "ai_cortex": {
    "cortex_complete": {
      "enabled": false,
      "model": "claude-sonnet-4-6",
      "monthly_input_tokens_M": 0,
      "monthly_output_tokens_M": 0
    },
    "cortex_agents": {
      "enabled": false,
      "model": "claude-sonnet-4-6",
      "monthly_input_tokens_M": 0,
      "monthly_output_tokens_M": 0
    },
    "snowflake_intelligence": {
      "enabled": false,
      "model": "claude-sonnet-4-6",
      "monthly_input_tokens_M": 0,
      "monthly_output_tokens_M": 0
    },
    "cortex_code": {
      "enabled": false,
      "note": "Billed via Snowflake Intelligence (Table 6d)",
      "developers": 0,
      "queries_per_dev_per_day": 20,
      "avg_tokens_per_query": 2000
    },
    "cortex_analyst": {
      "enabled": false,
      "monthly_messages": 0
    },
    "cortex_search": {
      "enabled": false,
      "indexed_data_gb": 0
    },
    "document_ai": {
      "enabled": false,
      "compute_hours_monthly": 0
    },
    "ai_parse_document_layout": { "enabled": false, "pages_per_month": 0 },
    "ai_parse_document_ocr":    { "enabled": false, "pages_per_month": 0 },
    "cortex_fine_tuning": {
      "enabled": false,
      "model": "llama3.1-70b",
      "training_tokens_M": 0
    },
    "cortex_functions": {
      "ai_classify":    { "enabled": false, "tokens_M_monthly": 0 },
      "ai_sentiment":   { "enabled": false, "tokens_M_monthly": 0 },
      "ai_summarize":   { "enabled": false, "tokens_M_monthly": 0 },
      "ai_translate":   { "enabled": false, "tokens_M_monthly": 0 },
      "ai_extract":     { "enabled": false, "tokens_M_monthly": 0 },
      "ai_transcribe":  { "enabled": false, "tokens_M_monthly": 0 }
    },
    "embeddings": {
      "enabled": false,
      "model": "snowflake-arctic-embed-l-v2.0",
      "tokens_M_monthly": 0
    },
    "provisioned_throughput": {
      "enabled": false,
      "ptus": 0,
      "hours_monthly": 0
    }
  },

  "spcs": {
    "enabled": false,
    "instances": [
      {
        "id": "spcs_1",
        "label": "App Compute",
        "generation": "gen2",
        "instance_type": "GEN_X64_G2_8",
        "hours_monthly": 0,
        "count": 1
      }
    ]
  },

  "openflow": {
    "enabled": false,
    "deployment": "BYOC",
    "source_connections": 0,
    "vcpu_per_connection": 4,
    "hours_monthly": 0
  },

  "openflow_oracle": {
    "enabled": false,
    "licensed_cores": 0
  },

  "postgres": {
    "enabled": false,
    "instance_family": "STANDARD_L",
    "high_availability": false,
    "instances": 1,
    "storage_tb": 0
  },

  "storage": {
    "standard": {
      "raw_tb_year1": 5,
      "compression_ratio": 3,
      "annual_growth_pct": 20,
      "time_travel_days": 1,
      "failsafe_days": 7,
      "churn_rate_pct": 10
    },
    "hybrid_tables_gb": 0,
    "archive": {
      "enabled": false,
      "tier": "cool",
      "tb": 0
    },
    "eco_cache": {
      "enabled": false,
      "tb": 0
    },
    "spcs_block": {
      "enabled": false,
      "volume_tb": 0,
      "iops_thousands": 0,
      "throughput_gb_per_sec": 0,
      "snapshot_tb": 0
    }
  },

  "data_transfer": {
    "enabled": false,
    "tb_per_month": 0,
    "pattern": "same_region"
  },

  "privatelink": {
    "enabled": false,
    "endpoints": 0,
    "tb_processed_monthly": 0
  },

  "collaboration": {
    "reader_accounts": {
      "enabled": false,
      "warehouse_size": "XS",
      "hours_per_day": 2,
      "days_per_month": 22
    },
    "native_apps": {
      "enabled": false,
      "monthly_subscription_fee": 0
    },
    "marketplace": {
      "enabled": false,
      "monthly_subscription_fee": 0
    }
  },

  "cloud_services": {
    "expected_above_threshold": false,
    "note": "Only billed when daily serverless compute exceeds 10% of daily VW credits. Calculated automatically from workload profile."
  },

  "growth_rates": [0.70, 1.00, 1.20, 1.44, 1.73],
  "assumptions": [],
  "confirm_required": []
}
```

---

## Interactive HTML Design

### File output

`temp/<customer-slug>-<N>year-sizing.html` — single self-contained file, no server required. Shareable directly with the customer.

### Embedded JS constants

```js
const PRICING_DATA = { /* full pricing JSON pruned to selected cloud/region */ };
const SIZING_SPEC  = { /* full spec as above */ };
```

### Page sections

| Section                      | Description                                                                                                                           |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Header                       | Snowflake inline SVG logo, customer name, edition/cloud/region badge, date                                                            |
| Executive Summary            | 4 KPI tiles: Total TCV, Year 1 cost, Total credits (N yrs), Recommended commitment. Live-updating.                                    |
| Year-by-year chart           | Grouped bar chart (Chart.js). Bars split: Compute / Serverless / AI / Storage / Other. Summary table below.                           |
| Workload breakdown           | Donut chart, credit % by category. Live-updating.                                                                                     |
| Configuration panel          | Tabbed accordion: Warehouses, Serverless, AI/Cortex, SPCS, Openflow, Postgres, Storage, Collaboration, Data Transfer, Global Settings |
| Scenario comparison          | 3 columns: Conservative / Expected / Aggressive. Growth multiplier adjustable per column.                                             |
| Assumptions & open questions | Rendered from `spec.assumptions` and `spec.confirm_required`. Warning badges on unconfirmed items.                                |
| Footer                       | "Prepared by Snowflake" + disclaimer + generated date                                                                                 |

### Configuration panel — control types

- **Warehouse size:** dropdown (XS / S / M / L / XL / 2XL / 3XL / 4XL), shows credits/hr inline
- **Hours/day:** slider 0–24, step 0.5
- **Days/month:** slider 1–31, step 1
- **Clusters min/max:** number inputs 1–10
- **Serverless features:** toggle + volume input (units shown per feature)
- **AI features:** toggle, model selector, token/message/GB inputs
- **SPCS instances:** instance type selector, hours/month, count; add/remove rows
- **Edition/region:** dropdowns that update `credit_rate` live from `PRICING_DATA`
- **Ramp curve:** selector (Slowest 55% / Slow 65% / Linear 70% / Fast 80% / Fastest 90%)
- **Contract years:** selector (1 / 2 / 3 / 4 / 5)

### JS calculation engine

```
onAnyControlChange → updateSpec(field, value) → recalculate()

recalculate():
  for year in 1..N:
    ramp = SPEC.growth_rates[year-1]
    credits.warehouses  = Σ (size_credits/hr × hrs/day × days/mo × avg_clusters) × 12 × ramp
    credits.serverless  = Σ feature_credits(f) × 12 × ramp  [for each enabled serverless feature]
    credits.ai          = Σ ai_credits(f) × 12 × ramp       [for each enabled AI feature]
    cost.storage        = storage_tb(year) × storage_rate × 12
    cost.spcs           = Σ (instance_credits/hr × hrs/mo × count) × credit_rate × 12 × ramp
    cost.openflow       = (openflow.source_connections × openflow.vcpu_per_connection × openflow.hours_monthly) × 0.0225 × credit_rate × 12 × ramp
    cost.postgres       = postgres_credits/hr × hrs × credit_rate × 12 × ramp
    cost.transfer       = tb_transferred × transfer_rate × 12
    yearTotal[year]     = (credits.all × credit_rate) + cost.storage + non-credit costs

  TCV = Σ yearTotal
  updateKPIs(); updateCharts(); updateScenarioColumns()
```

Each workload card displays its own inline calculation: `4 cr/hr × 2 hrs × 22 days = 176 cr/mo → 2,112 cr/yr`.

### Snowflake branding

- Colors: `--sf-blue: #29B5E8`, `--sf-navy: #043C5C`, `--sf-teal: #00C8D7`
- Font: Open Sans (Google Fonts CDN)
- Snowflake logo: inline SVG
- Header: navy gradient background
- Charts: Snowflake blue palette

---

## Pricing Coverage — Full Table Map

| PDF Table | Content                                            | Spec Section                                           |
| --------- | -------------------------------------------------- | ------------------------------------------------------ |
| 1(a)      | Standard Warehouse (XS–6XL)                       | `workloads[].warehouse_type: standard`               |
| 1(b)      | Gen 2 Warehouse                                    | `workloads[].warehouse_type: gen2`                   |
| 1(c)      | Snowpark Optimized Warehouse                       | `workloads[].warehouse_type: snowpark`               |
| 1(d)      | Interactive Warehouse                              | `workloads[].warehouse_type: interactive`            |
| 1(e)      | Adaptive Compute Services                          | `workloads[].warehouse_type: adaptive`               |
| 1(f)      | First Gen SPCS (CPU/HIGHMEM/GPU)                   | `spcs.instances[].generation: gen1`                  |
| 1(g)      | Gen 2 SPCS (ARM/X64/GPU/MEM)                       | `spcs.instances[].generation: gen2`                  |
| 1(h)      | Openflow (BYOC + SPCS)                             | `openflow`                                           |
| 1(i)      | Postgres Compute                                   | `postgres`                                           |
| 2(a)      | On-demand credit pricing (all regions)             | `meta.credit_rate` (from PRICING_DATA)               |
| 2(b)      | AI Credit Pricing                                  | `meta.ai_credit_rate`                                |
| 3(a)      | Standard Storage                                   | `storage.standard`                                   |
| 3(b)      | Hybrid Tables Storage                              | `storage.hybrid_tables_gb`                           |
| 3(c)      | SPCS Block Storage                                 | `storage.spcs_block`                                 |
| 3(d)      | ECO Cache                                          | `storage.eco_cache`                                  |
| 3(e)      | Archive Storage                                    | `storage.archive`                                    |
| 3(f)      | Postgres Storage                                   | `postgres.storage_tb`                                |
| 4(a–c)   | Data Transfer (AWS/Azure/GCP)                      | `data_transfer`                                      |
| 4(d)      | API Gateway Private Endpoints                      | `data_transfer.pattern: private_endpoint`            |
| 4(e)      | Outbound Privatelink                               | `privatelink`                                        |
| 5         | All 27 Serverless Features                         | `serverless.*`                                       |
| 6(a)      | Cortex AI Functions (40+ models)                   | `ai_cortex.cortex_complete` + `cortex_functions`   |
| 6(b)      | REST API with Prompt Caching                       | `ai_cortex.cortex_complete` (rest_api mode)          |
| 6(c)      | REST API                                           | `ai_cortex.cortex_complete` (rest_api mode)          |
| 6(d)      | Snowflake Intelligence                             | `ai_cortex.snowflake_intelligence` + `cortex_code` |
| 6(e)      | Cortex Agents                                      | `ai_cortex.cortex_agents`                            |
| 6(f)      | Cortex Analyst via Intelligence/Agents             | `ai_cortex.cortex_analyst`                           |
| 6(g)      | Fine-tuning                                        | `ai_cortex.cortex_fine_tuning`                       |
| 6(h)      | Other AI (Parse, Analyst API, Search, Document AI) | `ai_cortex.*`                                        |
| 6(i)      | Provisioned Throughput                             | `ai_cortex.provisioned_throughput`                   |
| 7         | Openflow Oracle Connector                          | `openflow_oracle`                                    |

---

## Glean Research Strategy

On Phase 2, search Glean in parallel with reading the context file:

```
search: "<customer name> snowflake consumption credits"
search: "<customer name> <domain> data platform workloads"
search: "<customer name>" app:gong          ← call transcripts
search: "<customer name>" app:salescloud    ← opportunity details
```

Extract: company size, industry vertical, existing data stack (Databricks, Oracle, SQL Server, etc.), stated use cases, data volumes, growth projections. Use to fill in sizing assumptions and surface relevant industry benchmarks.

---

## Sizing Methodology — Key Rules (from v1 prompt + Google Doc)

1. **SOURCE OR ASSUMPTION** — every number is cited or explicitly labelled
2. **Warehouse sizing validation** — XS: dev/<10 users; S: light BI <20 users; M: 20–50 users; L: heavy/50–100; XL: 100+
3. **Multi-cluster required when** — DirectQuery >15 concurrent; any BI tool >30 concurrent; SLA <30s under load
4. **Conservative by default** — when uncertain, use the higher estimate
5. **Weekday vs 7-day** — explicitly verify operating days (22 vs 30/month)
6. **Dynamic Tables** — modelled as warehouse workloads (not serverless); cost = warehouse size × refresh duration
7. **Ramp-up curves** — Linear (70%) is default for Year 1 unless evidence suggests faster/slower adoption. `growth_rates` is always sized to `contract_years`: `[ramp_yr1, 1.0, 1+g, (1+g)², ...]` where `g` = annual growth rate (default 20%). Example for 3yr at 20%: `[0.70, 1.00, 1.20]`; for 5yr: `[0.70, 1.00, 1.20, 1.44, 1.73]`.
8. **Time-Travel + Fail-safe overhead** — calculated as `compressed_tb × churn_rate × (time_travel_days + 7) / 30`
9. **Cloud Services** — only flag when serverless-heavy (>10% threshold); typically not a direct cost
10. **Cortex Code** — modelled via Snowflake Intelligence credits: `developers × queries/day × avg_tokens × working_days`

---

## File Naming

Output: `temp/<customer-slug>-<N>year-sizing.html`

Customer slug: lowercase, hyphens, no spaces. E.g. `acme-corp-3year-sizing.html`.
