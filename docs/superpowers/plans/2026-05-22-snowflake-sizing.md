# Snowflake Sizing Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Cortex Code plugin (`/snowflake-sizing`) that takes a customer context file, researches them via Glean, and generates a single self-contained interactive HTML pricing proposal with live JS sliders for every Snowflake consumption variable.

**Architecture:** Single-command plugin dispatching to a 6-phase skill. All business logic lives in two reference documents (`sizing-methodology.md` and `html-spec.md`) that Claude reads during execution. The HTML output embeds a full pricing JSON and sizing spec as JS constants, with a vanilla JS calculation engine — no server needed.

**Tech Stack:** Markdown skill documents, JSON (pricing data), vanilla JS + Chart.js 4.4.1 (via CDN), Snowflake Texta/Lato fonts (from `snowflake-branding/snowflake.com/fonts/`), inline SVG logo.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `plugins/snowflake-sizing/.claude-plugin/plugin.json` | Create | Plugin registration |
| `plugins/snowflake-sizing/commands/snowflake-sizing.md` | Create | Entry point, argument parsing, tool allowlist |
| `plugins/snowflake-sizing/skills/snowflake-sizing/SKILL.md` | Create | 6-phase orchestration workflow |
| `plugins/snowflake-sizing/skills/snowflake-sizing/references/sizing-methodology.md` | Create | All sizing rules, warehouse/serverless/AI benchmarks, ramp curves |
| `plugins/snowflake-sizing/skills/snowflake-sizing/references/html-spec.md` | Create | Complete HTML/CSS/JS template spec for output generation |
| `plugins/snowflake-sizing/assets/snowflake_pricing_master.json` | Create | Updated pricing data for May 2026 PDF — all 7 tables |
| `plugins/snowflake-sizing/.gitignore` | Modify | Add `temp/` to ignored paths |
| `plugins/snowflake-sizing/README.md` | Create | Usage guide for SEs |

---

## Task 1: Plugin scaffold and `.gitignore`

**Files:**
- Create: `plugins/snowflake-sizing/.claude-plugin/plugin.json`
- Create: `plugins/snowflake-sizing/commands/snowflake-sizing.md`
- Modify: `plugins/snowflake-sizing/.gitignore`

- [ ] **Step 1: Create `.claude-plugin/plugin.json`**

```bash
mkdir -p plugins/snowflake-sizing/.claude-plugin
```

Write `plugins/snowflake-sizing/.claude-plugin/plugin.json`:
```json
{
  "name": "snowflake-sizing",
  "version": "0.1.0",
  "description": "Generate accurate, interactive Snowflake consumption estimates and customer-facing HTML pricing proposals from discovery notes and Glean research.",
  "author": { "name": "Alex Ross" },
  "commands": "commands",
  "skills": "skills"
}
```

- [ ] **Step 2: Create the command entry point**

```bash
mkdir -p plugins/snowflake-sizing/commands
```

Write `plugins/snowflake-sizing/commands/snowflake-sizing.md`:
```markdown
---
description: Generate an interactive Snowflake consumption estimate and customer-facing HTML proposal from a discovery context file.
argument-hint: "<context-file> [--customer \"Name\"] [--years 3] [--edition Enterprise] [--region \"AWS US East (Northern Virginia)\"]"
allowed-tools: [Read, Write, Bash, WebFetch, snowflake_sql_execute, mcp__glean_default__search, mcp__glean_default__read_document, mcp__glean_default__chat, mcp__glean_default__employee_search]
skill: snowflake-sizing
---

Generate a Snowflake sizing estimate and interactive HTML proposal. Pass `$ARGUMENTS` to the skill.
```

- [ ] **Step 3: Update `.gitignore` to exclude `temp/`**

Edit `plugins/snowflake-sizing/.gitignore` — current content is `examples/`. New content:
```
examples/
temp/
```

- [ ] **Step 4: Create the skills directory structure**

```bash
mkdir -p plugins/snowflake-sizing/skills/snowflake-sizing/references
mkdir -p plugins/snowflake-sizing/assets
mkdir -p plugins/snowflake-sizing/temp
```

- [ ] **Step 5: Verify structure**

```bash
find plugins/snowflake-sizing -not -path "*/\.*" -not -path "*/temp/*" -not -path "*/examples/*" | sort
```

Expected output:
```
plugins/snowflake-sizing/
plugins/snowflake-sizing/.claude-plugin/plugin.json
plugins/snowflake-sizing/.gitignore
plugins/snowflake-sizing/assets/
plugins/snowflake-sizing/commands/snowflake-sizing.md
plugins/snowflake-sizing/skills/snowflake-sizing/references/
plugins/snowflake-sizing/temp/
```

- [ ] **Step 6: Commit**

```bash
git add plugins/snowflake-sizing/.claude-plugin/plugin.json \
        plugins/snowflake-sizing/commands/snowflake-sizing.md \
        plugins/snowflake-sizing/.gitignore
git commit -m "feat(snowflake-sizing): scaffold plugin structure and command entry point"
```

---

## Task 2: Update pricing JSON to May 2026

**Files:**
- Create: `plugins/snowflake-sizing/assets/snowflake_pricing_master.json`

The v1 JSON at `../../../ldeleyritz-demos-main/consumption-estimator/snowflake_pricing_master.json` covers the Jan 2026 PDF. This task creates an updated copy covering the May 12, 2026 PDF changes.

- [ ] **Step 1: Copy v1 JSON as starting point**

```bash
cp /Users/axross/Snowflake/Repos/ldeleyritz-demos-main/consumption-estimator/snowflake_pricing_master.json \
   plugins/snowflake-sizing/assets/snowflake_pricing_master.json
```

- [ ] **Step 2: Update metadata**

Edit `plugins/snowflake-sizing/assets/snowflake_pricing_master.json` — update the `metadata` block:
```json
"metadata": {
  "effective_date": "2026-05-12",
  "source": "Snowflake Service Consumption Table",
  "description": "Complete Snowflake Pricing Reference - All Components",
  "version": "2.0",
  "last_updated": "2026-05-22"
}
```

- [ ] **Step 3: Add Table 1(e) — Adaptive Compute Services**

Add after the `"interactive"` key in `"warehouses"`:
```json
"adaptive": {
  "description": "Table 1(e) - Adaptive Compute Services. Credit consumption scales dynamically based on compute usage, software optimizations, and active queries.",
  "note": "Cannot be pre-sized; modelled as a standard warehouse with auto-scaling behaviour. Use standard warehouse rates as upper bound."
}
```

- [ ] **Step 4: Add Table 1(g) — Gen 2 SPCS instances**

Add a `"spcs_gen2"` key inside `"spcs"`:
```json
"spcs_gen2": {
  "description": "Table 1(g) - Gen 2 SPCS Compute Credits/Hour by Cloud Provider",
  "data": [
    {"family": "GEN_ARM_G1_2",   "aws": 0.084,  "azure": null,  "gcp": null},
    {"family": "GEN_ARM_G1_4",   "aws": 0.168,  "azure": null,  "gcp": null},
    {"family": "GEN_ARM_G1_8",   "aws": 0.336,  "azure": null,  "gcp": null},
    {"family": "GEN_ARM_G1_16",  "aws": 0.672,  "azure": null,  "gcp": null},
    {"family": "GEN_ARM_G1_32",  "aws": 1.344,  "azure": null,  "gcp": null},
    {"family": "GEN_X64_G2_2",   "aws": 0.092,  "azure": 0.086, "gcp": null},
    {"family": "GEN_X64_G2_4",   "aws": 0.184,  "azure": 0.172, "gcp": null},
    {"family": "GEN_X64_G2_8",   "aws": 0.368,  "azure": 0.344, "gcp": null},
    {"family": "GEN_X64_G2_16",  "aws": null,   "azure": 0.688, "gcp": null},
    {"family": "GEN_X64_G2_32",  "aws": 1.472,  "azure": 1.376, "gcp": null},
    {"family": "GPU_L40S_G1_8",  "aws": 1.580,  "azure": null,  "gcp": null},
    {"family": "GPU_L40S_G1_16", "aws": 3.160,  "azure": null,  "gcp": null},
    {"family": "GPU_L40S_G1_48", "aws": 9.480,  "azure": null,  "gcp": null},
    {"family": "GPU_L40S_G1_192","aws": 37.920, "azure": null,  "gcp": null},
    {"family": "GPU_R6K_G1_8",   "aws": 2.537,  "azure": null,  "gcp": null},
    {"family": "GPU_R6K_G1_16",  "aws": 5.074,  "azure": null,  "gcp": null},
    {"family": "GPU_R6K_G1_32",  "aws": 10.148, "azure": null,  "gcp": null},
    {"family": "GPU_R6K_G1_48",  "aws": 15.222, "azure": null,  "gcp": null},
    {"family": "GPU_R6K_G1_96",  "aws": 30.444, "azure": null,  "gcp": null},
    {"family": "GPU_R6K_G1_192", "aws": 60.888, "azure": null,  "gcp": null},
    {"family": "GPU_A100_G1_12", "aws": null,   "azure": null,  "gcp": 5.051},
    {"family": "GPU_A100_G1_48", "aws": null,   "azure": null,  "gcp": 20.204},
    {"family": "MEM_X64_G2_8",   "aws": 0.392,  "azure": 0.311, "gcp": null},
    {"family": "MEM_X64_G2_32",  "aws": 1.568,  "azure": 1.244, "gcp": null},
    {"family": "MEM_X64_G2_64",  "aws": 3.136,  "azure": 2.486, "gcp": null},
    {"family": "MEM_X64_G2_96",  "aws": null,   "azure": 3.732, "gcp": null},
    {"family": "MEM_X64_G2_192", "aws": 9.408,  "azure": null,  "gcp": null}
  ]
}
```

- [ ] **Step 5: Add Table 2(b) — AI Credit Pricing**

Add an `"ai_credit_pricing"` key at the top level, after `"credit_pricing"`:
```json
"ai_credit_pricing": {
  "description": "Table 2(b) - AI Credit Pricing. Separate from Snowflake Compute Credits.",
  "on_demand": {
    "global": 2.00,
    "regional": 2.20
  },
  "capacity_tiers": [
    {"tier": 1, "acv_range": "$0-$1,199,999",     "global": 2.00, "regional": 2.20},
    {"tier": 2, "acv_range": "$1,200,000-$2,999,999", "global": 1.96, "regional": 2.16},
    {"tier": 3, "acv_range": "$3,000,000-$4,999,999", "global": 1.96, "regional": 2.16},
    {"tier": 4, "acv_range": "$5,000,000-$9,999,999", "global": 1.94, "regional": 2.13},
    {"tier": 5, "acv_range": "$10,000,000-$19,999,999","global": 1.92, "regional": 2.11},
    {"tier": 6, "acv_range": "$20,000,000-$39,999,999","global": 1.90, "regional": 2.09},
    {"tier": 7, "acv_range": "$40,000,000+",           "global": 1.88, "regional": 2.07}
  ]
}
```

- [ ] **Step 6: Add new AWS regions from May 2026 PDF**

In the `"credit_pricing"` → `"data"` array, add these new entries (after the existing AWS entries):
```json
{"cloud": "AWS", "region": "Africa (Cape Town)",         "standard": 2.80, "enterprise": 4.20, "business_critical": 5.60, "vps": 8.40},
{"cloud": "AWS", "region": "Middle East (UAE)",          "standard": 2.70, "enterprise": 4.00, "business_critical": 5.40, "vps": 8.10},
{"cloud": "AWS", "region": "Asia Pacific (Malaysia)",    "standard": 2.40, "enterprise": 3.60, "business_critical": 4.80, "vps": 7.20},
{"cloud": "AWS", "region": "Asia Pacific (Thailand)",    "standard": 2.40, "enterprise": 3.60, "business_critical": 4.80, "vps": 7.20},
{"cloud": "AWS", "region": "Europe (Stockholm)",         "standard": 2.40, "enterprise": 3.60, "business_critical": 4.80, "vps": 7.20},
{"cloud": "AWS", "region": "Asia Pacific (Osaka)",       "standard": 2.85, "enterprise": 4.30, "business_critical": 5.70, "vps": 8.55},
{"cloud": "AWS", "region": "South America East 1 (São Paulo)", "standard": 3.10, "enterprise": 4.65, "business_critical": 6.20, "vps": 9.30},
{"cloud": "AWS", "region": "EU (Paris)",                 "standard": 2.60, "enterprise": 3.90, "business_critical": 5.20, "vps": 7.80},
{"cloud": "AWS", "region": "Asia Pacific (Jakarta)",     "standard": 2.50, "enterprise": 3.70, "business_critical": 5.00, "vps": 7.50},
{"cloud": "AWS", "region": "EU (Zurich)",                "standard": 3.10, "enterprise": 4.65, "business_critical": 6.20, "vps": 9.30},
{"cloud": "GCP", "region": "Middle East Central 2 (Dammam)", "standard": 3.25, "enterprise": 4.90, "business_critical": 6.50, "vps": 9.75},
{"cloud": "GCP", "region": "Australia Southeast 2 (Melbourne)", "standard": 2.75, "enterprise": 4.05, "business_critical": 5.50, "vps": 8.25},
{"cloud": "Azure", "region": "East US (Virginia)",       "standard": 2.00, "enterprise": 3.00, "business_critical": 4.00, "vps": 6.00},
{"cloud": "Azure", "region": "Korea Central",            "standard": 2.75, "enterprise": 4.05, "business_critical": 5.50, "vps": 8.25},
{"cloud": "Azure", "region": "Sweden Central",           "standard": 2.40, "enterprise": 3.60, "business_critical": 4.80, "vps": 7.20},
{"cloud": "Azure", "region": "Mexico Central",           "standard": 2.00, "enterprise": 3.00, "business_critical": 4.00, "vps": 6.00}
```

- [ ] **Step 7: Validate JSON is parseable**

```bash
python3 -c "import json; d=json.load(open('plugins/snowflake-sizing/assets/snowflake_pricing_master.json')); print('Keys:', list(d.keys())); print('Gen2 instances:', len(d['spcs']['spcs_gen2']['data'])); print('AI credit on-demand global: $', d['ai_credit_pricing']['on_demand']['global'])"
```

Expected output:
```
Keys: ['metadata', 'credit_pricing', 'ai_credit_pricing', 'warehouses', 'snowpark_optimized', 'spcs', 'serverless', 'openflow', 'postgres', 'ai_features', 'storage', 'data_transfer', 'formulas', 'reference_values']
Gen2 instances: 27
AI credit on-demand global: $ 2.0
```

- [ ] **Step 8: Commit**

```bash
git add plugins/snowflake-sizing/assets/snowflake_pricing_master.json
git commit -m "feat(snowflake-sizing): add pricing master JSON updated to May 2026 PDF"
```

---

## Task 3: `sizing-methodology.md` — sizing rules reference

**Files:**
- Create: `plugins/snowflake-sizing/skills/snowflake-sizing/references/sizing-methodology.md`

This document is read by Claude during Phase 3. It must be prescriptive enough that Claude makes consistent, defensible sizing decisions without hallucinating numbers.

- [ ] **Step 1: Write the file**

Write `plugins/snowflake-sizing/skills/snowflake-sizing/references/sizing-methodology.md`:

```markdown
# Snowflake Sizing Methodology

## The Prime Directive: SOURCE OR ASSUMPTION

Every number in the estimate MUST be one of:
- **SOURCED**: Directly from context file or Glean research — cite it. E.g. `SOURCED: questionnaire Q4 — "50GB daily batch load"`
- **ASSUMPTION**: Explicitly labelled with rationale. E.g. `ASSUMPTION: weekday-only operation (22 days/month) — no evidence of weekend processing`
- **REQUIRES_CONFIRMATION**: Flag when missing info significantly impacts cost. Quantify the impact.

Never guess silently. Never omit a category. Never fabricate data.

---

## Warehouse Sizing Rules

### Size Selection

| Size | Credits/hr | Choose When |
|------|-----------|-------------|
| XS   | 1         | Dev/test only; <10 concurrent users; query latency not critical |
| S    | 2         | Light BI (<20 users); simple daily transforms <100GB |
| M    | 4         | Standard BI (20–50 users); moderate ELT; daily loads 100GB–1TB |
| L    | 8         | Heavy ELT; complex queries; 50–100 concurrent users; >1TB daily |
| XL   | 16        | Large-scale ML prep; 100+ users; multi-TB daily processing |
| 2XL+ | 32+       | Specialised high-throughput; rarely needed for standard workloads |

**Warehouse sizing is for LATENCY, not throughput.** A query taking 4 min on XS takes ~1 min on M — same credits, different latency. Size for the SLA.

### Multi-Cluster Warehouse (MCW) Rules

**MCW is REQUIRED when ANY of:**
- Power BI DirectQuery with >15 concurrent users
- Any BI tool with >30 concurrent users
- Mixed Import/DirectQuery patterns at scale
- SLA requires <30s response under peak load

**MCW Credit Formula:**
```
Monthly Credits = size_credits/hr × hours/day × days/month × avg_clusters
avg_clusters = (clusters_min + clusters_max) / 2
```

### Auto-suspend Defaults

| Workload Type | Recommended Auto-suspend |
|---|---|
| BI / Interactive | 1–2 minutes |
| Batch / ELT | 10 seconds |
| Dev / Ad-hoc | 5 minutes |

### Warehouse Credit Rates (Standard)

XS=1, S=2, M=4, L=8, XL=16, 2XL=32, 3XL=64, 4XL=128, 5XL=256, 6XL=512

### Gen 2 Warehouse Rates (per hour)

AWS/GCP: XS=1.35, S=2.70, M=5.40, L=10.80, XL=21.60, 2XL=43.20
Azure: XS=1.25, S=2.50, M=5.00, L=10.00, XL=20.00, 2XL=40.00

### Interactive Warehouse Rates (60-second minimum)

XS=0.60, S=1.20, M=2.40, L=4.80, XL=9.60, 2XL=19.20

### Snowpark Optimized Rates

MEMORY_1X: XS=1, S=2, M=4, L=8, XL=16, 2XL=32, 3XL=64, 4XL=128
MEMORY_16X: M=6, L=12, XL=24, 2XL=48, 3XL=96, 4XL=192
MEMORY_64X (Preview): L=15, XL=30, 2XL=60

---

## Operating Days

**Always explicitly confirm:**
- **Weekday-only**: 22 days/month (264/year) — most BI, business ops
- **7-day operation**: 30 days/month (365/year) — streaming, customer-facing apps, 24/7 pipelines

Default to weekday-only if no evidence of weekend processing.

---

## Workload Category Benchmarks

### Data Ingestion

| Pattern | Size | Hours/Day | Notes |
|---|---|---|---|
| Batch daily <100GB | S–M | 1–2 | Single daily load |
| Batch daily 100GB–1TB | M–L | 2–4 | Consider parallel loading |
| Batch daily >1TB | L–XL | 4–8 | Use parallel loading |
| Hourly micro-batch | XS–S | 24 | Use auto-suspend aggressively |
| Near real-time | S–M | 24 | Consider Snowpipe Streaming instead |

**Credit benchmark**: 10–30 credits/TB ingested (varies by complexity)

### Transformation / ELT

| Pattern | Size | Frequency | Credits/Run |
|---|---|---|---|
| Light SQL transforms | S | Daily | 2–5 |
| Standard dbt (50–200 models) | M | Daily | 10–30 |
| Complex joins/aggregations | L | Daily | 30–100 |
| ML feature engineering | L–XL | Daily | 50–200 |

**Credit benchmark**: Simple=10–20 cr/TB; Complex=30–50 cr/TB; ML=50–100 cr/TB

**Dynamic Tables** run on a customer-managed warehouse. Model as a warehouse workload with hours = sum of daily refresh durations.

### BI & Analytics

| User Profile | Queries/Day | Credits/User/Month |
|---|---|---|
| Executive (light) | 5–10 | 5–15 |
| Analyst (medium) | 20–50 | 20–50 |
| Power user (heavy) | 50–100 | 50–150 |
| Data scientist | 20–40 heavy | 100–300 |

**BI Formula**: `Users × Queries/Day × Avg_Query_Runtime_hrs × Size_Credits × Days/Month`

---

## Serverless Feature Formulas

All serverless features charge: `Compute_Hours × Multiplier × 1 credit/hr`
Plus any unit charges listed below.

| Feature | Compute Multiplier | Cloud Services | Unit Charge |
|---|---|---|---|
| Snowpipe | — | — | 0.0037 credits/GB |
| Snowpipe Streaming | — | — | 0.0037 credits/uncompressed GB |
| Snowpipe Streaming Classic | 1.0 | — | 0.01 credits/client instance/hr |
| Serverless Tasks | 0.9 | 1.0 | — |
| Serverless Tasks Flex | 0.5 | 1.0 | — |
| Serverless Alerts | 0.9 | 1.0 | — |
| Clustered Tables | 2.0 | 1.0 | — |
| Materialized Views | 2.0 | 1.0 | — |
| Dynamic Tables | warehouse-based | — | — |
| Search Optimization | 2.0 | 1.0 | — |
| Query Acceleration | 1.0 | — | — |
| Replication | 2.0 | 0.35 | — |
| Backup | 2.0 | 1.0 | — |
| Failsafe Recovery | 0.9 | 1.0 | — |
| Data Quality Monitoring | 2.0 | 1.0 | — |
| Trust Center | 1.0 | 1.0 | — |
| Table Optimization | 0.75 | 1.0 | — |
| Storage Lifecycle Policy | 0.50 | 1.0 | — |
| Hybrid Tables Requests | 1.0 | 1.0 | 1 cr/30GB read, 1 cr/7.5GB write |
| Copy Files | 2.0 | — | — |
| Automated Refresh | 1.25 | — | 0.06 cr/1000 files |
| Organization Usage | 1.0 | 1.0 | — |
| Sensitive Data Classification | 0.9 | 1.0 | — |
| Open Catalog | — | — | 0.5 cr/million requests |
| Logging | 1.25 | — | 0.28 cr/1000 file batches |
| Telemetry Data Ingest | — | — | 0.0212 cr/GB |
| Archive Storage Retrieval | — | — | 0.05 cr/1000 files |
| Archive Storage Write | — | — | 0.05 cr/1000 files |

---

## AI / Cortex Credits (Table 6 — uses separate AI credit pool)

AI credits are priced separately from compute credits. Default on-demand rate: **$2.00/credit global, $2.20/credit regional**.

### Cortex Complete key models (credits per 1M tokens)

| Model | Input | Output |
|---|---|---|
| claude-4-sonnet | 1.50 | 7.50 |
| claude-4-opus | 7.50 | 37.50 |
| claude-haiku-4-5 | 0.55 | 2.75 |
| llama4-maverick | 0.12 | 0.49 |
| llama4-scout | 0.09 | 0.33 |
| openai-gpt-4.1 | 1.00 | 4.00 |
| snowflake-arctic | 0.84 | 0.84 |

### Snowflake Intelligence / Cortex Agents (credits per 1M tokens)

| Model | Input | Output |
|---|---|---|
| claude-4-sonnet | 2.51 | 12.55 |
| claude-haiku-4-5 | 0.92 | 4.60 |
| openai-gpt-4.1 | 1.84 | 7.36 |

### Cortex Analyst
67 credits per 1,000 messages (= 0.067 cr/message)

### Cortex Search
6.3 credits per GB/month of indexed data

### Document AI
8 credits per hour of compute

### Cortex Code (Snowflake Intelligence billing)
Estimate: `developers × queries/day × avg_tokens_per_query / 1,000,000 × intelligence_rate × working_days`
Default: 20 queries/dev/day, 2,000 tokens/query = 0.04M tokens/dev/day

---

## Storage Formulas

### Standard storage overhead

```
compressed_tb = raw_tb / compression_ratio
time_travel_overhead_tb = compressed_tb × churn_rate_pct/100 × time_travel_days / 30
failsafe_overhead_tb     = compressed_tb × churn_rate_pct/100 × 7 / 30
total_storage_tb         = compressed_tb + time_travel_overhead_tb + failsafe_overhead_tb
monthly_storage_cost     = total_storage_tb × storage_rate_per_tb
```

### Compression benchmarks

| Data Type | Typical Compression |
|---|---|
| CSV/JSON logs | 5–10x |
| Structured relational | 3–5x |
| Semi-structured | 3–7x |
| Already compressed (Parquet/ORC) | 1–2x |

Default: 3x compression if unknown.

---

## Ramp-Up Curves (Year 1 multiplier)

New workloads don't hit full consumption on day one.

| Curve | Year 1 Multiplier | Use When |
|---|---|---|
| Slowest | 55% | Heavy migration; >12 month rollout |
| Slow | 65% | Phased migration; 6–12 month rollout |
| Linear | 70% | Standard new deployment (default) |
| Fast | 80% | Replacing existing system; team ready |
| Fastest | 90% | Lift-and-shift; immediate full usage |

### Multi-year `growth_rates` array

Generated as: `[ramp_year1, 1.0, (1+g), (1+g)², ...]` where `g` = annual growth rate (default 0.20).

Examples:
- 3 years, 20% growth, linear ramp: `[0.70, 1.00, 1.20]`
- 5 years, 20% growth, fast ramp:   `[0.80, 1.00, 1.20, 1.44, 1.73]`
- 3 years, 30% growth, slow ramp:   `[0.65, 1.00, 1.30]`

---

## The Three-Scenario Rule

Always present three TCV scenarios in the HTML:

| Scenario | Growth Rate | Ramp | Intent |
|---|---|---|---|
| Conservative | 10%/yr | Slowest (55%) | Minimum commitment anchor |
| Expected | 20%/yr | Linear (70%) | Recommended contract value |
| Aggressive | 35%/yr | Fast (80%) | Innovation + full adoption |

---

## Defending the Estimate

| Customer Pushback | Response |
|---|---|
| "This seems expensive" | Show TCO vs legacy (hardware, DBAs, maintenance). Snowflake typically 30–50% lower TCO. |
| "Why this warehouse size?" | Cite concurrency requirement + query complexity. Offer to demo different sizes. |
| "What if we grow faster?" | "Credits are fungible — reallocate between workloads. Can add capacity mid-contract." |
| "Why serverless vs compute?" | Serverless for sporadic/unpredictable; compute for sustained, predictable workloads. |

---

## Questions Requiring Customer Confirmation

Flag any of these as `REQUIRES_CONFIRMATION` with quantified impact:

- Number of concurrent users (impacts MCW sizing — can be ±50% of compute cost)
- Weekend/7-day operation vs weekday-only (±36% of compute cost)
- Are OpenFlow databases on same server instance? (1 vs N connections)
- Compression ratio if unknown (±40% of storage cost)
- Growth rate assumption (±50% of Year 3 cost)
```

- [ ] **Step 2: Verify file was written**

```bash
wc -l plugins/snowflake-sizing/skills/snowflake-sizing/references/sizing-methodology.md
```

Expected: ~220 lines

- [ ] **Step 3: Commit**

```bash
git add plugins/snowflake-sizing/skills/snowflake-sizing/references/sizing-methodology.md
git commit -m "feat(snowflake-sizing): add sizing-methodology reference document"
```

---

## Task 4: `html-spec.md` — HTML generation contract

**Files:**
- Create: `plugins/snowflake-sizing/skills/snowflake-sizing/references/html-spec.md`

This document tells Claude exactly how to generate the HTML. It is a contract, not a suggestion.

- [ ] **Step 1: Write the file**

Write `plugins/snowflake-sizing/skills/snowflake-sizing/references/html-spec.md`:

```markdown
# Snowflake Sizing HTML Specification

## Output File

`temp/<customer-slug>-<N>year-sizing.html`

Customer slug: lowercase, hyphens only. E.g. `acme-corp-3year-sizing.html`.

The file MUST be completely self-contained. No external files. No server required. Send directly to customer.

---

## Required CDN Scripts (in `<head>`)

```html
<link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
```

---

## CSS Variables (`:root`)

```css
:root {
  --sf-blue: #29B5E8;
  --sf-blue-dark: #1398C9;
  --sf-navy: #11567F;
  --sf-navy-deep: #043C5C;
  --sf-teal: #00C8D7;
  --sf-orange: #FF9F36;
  --gray-800: #2d3748;
  --gray-700: #4a5568;
  --gray-600: #718096;
  --gray-200: #e2e8f0;
  --gray-100: #f7fafc;
  --white: #ffffff;
  --success: #38a169;
  --warning: #ED7D31;
}
```

---

## Snowflake Logo (inline SVG — use in header)

```html
<svg width="140" height="32" viewBox="0 0 140 32" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M16 0C7.163 0 0 7.163 0 16s7.163 16 16 16 16-7.163 16-16S24.837 0 16 0zm0 28.8C8.941 28.8 3.2 23.059 3.2 16S8.941 3.2 16 3.2 28.8 8.941 28.8 16 23.059 28.8 16 28.8z" fill="white"/>
  <text x="38" y="22" font-family="Open Sans, sans-serif" font-size="18" font-weight="700" fill="white">snowflake</text>
</svg>
```

Note: For a more accurate logo, read and inline the SVG from `snowflake-branding/snowflake.com/images/logo-white.svg` if accessible.

---

## Page Structure (top to bottom)

### 1. Header

```html
<div class="header">
  <div class="header-top">
    <div><!-- Snowflake logo SVG --></div>
    <div class="doc-meta">
      <div>CONSUMPTION ESTIMATE</div>
      <div>Prepared: [DATE]</div>
      <div>[EDITION] · [CLOUD] [REGION]</div>
    </div>
  </div>
  <h1>[CUSTOMER NAME]</h1>
  <div class="header-subtitle">[N]-Year Snowflake Consumption Estimate</div>
</div>
```

CSS: `background: linear-gradient(135deg, var(--sf-navy-deep) 0%, #0d3a5f 100%); border-radius: 8px; padding: 32px; color: white;`

### 2. Executive Summary KPI Tiles

Four tiles in a `grid-template-columns: repeat(4, 1fr)` grid. Each tile:
- Label (small, muted)
- Large value (bold, white)
- Left border `3px solid var(--sf-blue)`

Tiles:
1. **Total TCV** — sum of all years, formatted `$X,XXX,XXX`
2. **Year 1 Cost** — year 1 total
3. **Total Credits** — sum of all years' compute+serverless+AI credits (not dollar)
4. **Recommended Commitment** — same as TCV (SE adjusts manually)

All tiles update live via `id="kpi-tcv"` etc.

### 3. Year-by-Year Chart + Table

**Chart**: Stacked bar chart (Chart.js). One bar per year. Segments (bottom to top):
- Compute Warehouses (var(--sf-blue))
- Serverless (var(--sf-teal))
- AI/Cortex (#8B5CF6)
- Storage (#F59E0B)
- Other (var(--gray-600))

Chart dataset IDs: `chartCompute`, `chartServerless`, `chartAI`, `chartStorage`, `chartOther`

**Table below chart** — columns: Year | Credits | Compute $ | Serverless $ | AI $ | Storage $ | Other $ | **Total $**

### 4. Workload Breakdown Donut

Chart.js doughnut showing credit % by workload. Labels show workload name + percentage. Colours cycle through Snowflake palette.

### 5. Configuration Panel (Accordion Tabs)

Tabs rendered as pill buttons. Active tab shows its section. Default active: **Warehouses**.

Tabs (in order): Warehouses | Serverless | AI / Cortex | SPCS | Openflow | Storage | Collaboration | Global Settings

#### Warehouses Tab

For each workload in `SIZING_SPEC.workloads`, render a card:

```html
<div class="workload-card" data-id="[workload.id]">
  <div class="workload-header">
    <span class="workload-label">[workload.label]</span>
    <span class="workload-calc" id="calc-[id]"><!-- live calculation --></span>
  </div>
  <div class="controls-grid">
    <label>Warehouse Size
      <select id="size-[id]" onchange="updateWorkload('[id]', 'size', this.value)">
        <option value="XS">XS — 1 cr/hr</option>
        <option value="S">S — 2 cr/hr</option>
        <option value="M" selected>M — 4 cr/hr</option>
        <option value="L">L — 8 cr/hr</option>
        <option value="XL">XL — 16 cr/hr</option>
        <option value="2XL">2XL — 32 cr/hr</option>
        <option value="3XL">3XL — 64 cr/hr</option>
        <option value="4XL">4XL — 128 cr/hr</option>
      </select>
    </label>
    <label>Hours/Day
      <input type="range" id="hrs-[id]" min="0" max="24" step="0.5" value="[hours_per_day]"
             oninput="updateWorkload('[id]', 'hours_per_day', +this.value)">
      <span id="hrs-val-[id]">[hours_per_day]</span>
    </label>
    <label>Days/Month
      <input type="range" id="days-[id]" min="1" max="31" step="1" value="[days_per_month]"
             oninput="updateWorkload('[id]', 'days_per_month', +this.value)">
      <span id="days-val-[id]">[days_per_month]</span>
    </label>
    <label>Clusters (min / max)
      <input type="number" id="cmin-[id]" min="1" max="10" value="[clusters_min]"
             onchange="updateWorkload('[id]', 'clusters_min', +this.value)"> /
      <input type="number" id="cmax-[id]" min="1" max="10" value="[clusters_max]"
             onchange="updateWorkload('[id]', 'clusters_max', +this.value)">
    </label>
  </div>
  <div class="justification">[workload.source]: [workload.justification]</div>
</div>
```

Live calculation shown in `.workload-calc`:
`4 cr/hr × 2.0 hrs × 22 days × 1.0 avg clusters = 176 cr/mo → 2,112 cr/yr`

#### Serverless Tab

For each feature in `SIZING_SPEC.serverless`, render a row:
```html
<div class="serverless-row">
  <label class="toggle">
    <input type="checkbox" id="sl-[key]" [checked if enabled]
           onchange="updateServerless('[key]', 'enabled', this.checked)">
    <span class="feature-name">[label]</span>
    <span class="unit-hint">[unit, e.g. "GB/month"]</span>
  </label>
  <input type="number" id="sl-vol-[key]" value="[volume]" min="0"
         oninput="updateServerless('[key]', '[volume_field]', +this.value)"
         [disabled if not enabled]>
  <span class="serverless-cost" id="sl-cost-[key]">$0</span>
</div>
```

#### AI / Cortex Tab

Group by sub-category: Cortex Complete | Cortex Agents | Snowflake Intelligence | Cortex Code | Analyst & Search | Functions | Fine-tuning | Other

Each feature: toggle + model selector (where applicable) + token/message/GB input + live cost.

#### SPCS Tab

Table of SPCS instances from `SIZING_SPEC.spcs.instances`. Each row: label, generation (gen1/gen2), instance type selector, count, hours/month, live credit cost. "+ Add instance" button clones the last row.

#### Openflow Tab

Deployment selector (BYOC / SPCS), source connections, vCPU/connection, hours/month, live cost. Plus Oracle Connector toggle with licensed cores.

#### Storage Tab

- Raw TB (year 1): range slider 0–1000
- Compression ratio: select (1x / 2x / 3x / 5x / 7x / 10x)
- Annual growth %: range slider 0–100
- Time-travel days: select (0 / 1 / 7 / 14 / 30 / 90)
- Churn rate %: range slider 0–100
- Live storage breakdown table: compressed TB | time-travel TB | failsafe TB | total TB | monthly $ | annual $

#### Collaboration Tab

Reader accounts toggle + warehouse size + hours/day + days/month.
Native Apps toggle + monthly subscription fee.
Marketplace toggle + monthly subscription fee.

#### Global Settings Tab

- Edition: select (Standard / Enterprise / Business Critical / VPS) — updates credit_rate live
- Cloud: select (AWS / Azure / GCP)
- Region: grouped select populated from PRICING_DATA — updates credit_rate live
- Contract years: select (1 / 2 / 3 / 4 / 5) — adds/removes year bars from chart
- Ramp curve: select (Slowest 55% / Slow 65% / Linear 70% / Fast 80% / Fastest 90%)
- Annual growth %: number input (overrides computed growth_rates)

### 6. Scenario Comparison

Three side-by-side columns rendered as cards:

| | Conservative | Expected | Aggressive |
|---|---|---|---|
| Growth | 10%/yr | 20%/yr | 35%/yr |
| Ramp | Slowest (55%) | Linear (70%) | Fast (80%) |

Each column shows: Year 1 / Year 2 / Year 3 / TCV. The "Expected" column is highlighted with `border: 2px solid var(--sf-blue)`.

Each column has editable growth % and ramp selector so the SE can customise.

### 7. Assumptions & Open Questions

Two sections rendered from `SIZING_SPEC.assumptions` and `SIZING_SPEC.confirm_required`:

```html
<div class="assumptions-section">
  <h3>Stated Assumptions</h3>
  <ul id="assumptions-list"><!-- rendered from SIZING_SPEC.assumptions --></ul>
</div>
<div class="confirm-section">
  <h3>⚠️ Requires Customer Confirmation</h3>
  <ul id="confirm-list"><!-- rendered from SIZING_SPEC.confirm_required --></ul>
</div>
```

Each `confirm_required` item renders with an orange warning badge and the quantified impact.

### 8. Footer

```html
<div class="footer">
  <p>Prepared by Snowflake · This estimate is based on stated requirements and industry benchmarks.
  Actual consumption may vary. All prices are list price on-demand rates.
  Credit rates effective [PDF_VERSION].</p>
  <p>Generated [DATE]</p>
</div>
```

---

## JS Calculation Engine

### Constants (at top of `<script>`)

```javascript
const PRICING_DATA = /* paste full snowflake_pricing_master.json here */;
const SIZING_SPEC  = /* paste generated spec JSON here */;
```

### Core Functions

```javascript
const WH_CREDITS = { XS:1, S:2, M:4, L:8, XL:16, '2XL':32, '3XL':64, '4XL':128 };

function whMonthlyCredits(w) {
  const rate = WH_CREDITS[w.size] || 1;
  const avgClusters = (w.clusters_min + w.clusters_max) / 2;
  return rate * w.hours_per_day * w.days_per_month * avgClusters;
}

function storageForYear(year) {
  const s = SIZING_SPEC.storage.standard;
  const base = s.raw_tb_year1 / s.compression_ratio;
  const grown = base * Math.pow(1 + s.annual_growth_pct / 100, year - 1);
  const ttOH  = grown * (s.churn_rate_pct / 100) * (s.time_travel_days / 30);
  const fsOH  = grown * (s.churn_rate_pct / 100) * (7 / 30);
  return grown + ttOH + fsOH;
}

function recalculate() {
  const years = SIZING_SPEC.meta.contract_years;
  const cr    = SIZING_SPEC.meta.credit_rate;
  const aiCr  = SIZING_SPEC.meta.ai_credit_rate;
  const sr    = SIZING_SPEC.meta.storage_rate_per_tb;
  const ramps = SIZING_SPEC.growth_rates;

  const yearData = [];

  for (let y = 1; y <= years; y++) {
    const ramp = ramps[y - 1] || ramps[ramps.length - 1];

    // Warehouse credits (annual)
    const whCredits = SIZING_SPEC.workloads
      .reduce((sum, w) => sum + whMonthlyCredits(w) * 12, 0) * ramp;

    // Serverless credits (annual) — each feature uses its own formula
    const slCredits = calcServerlessCredits() * 12 * ramp;

    // AI credits (annual)
    const aiCredits = calcAICredits() * 12 * ramp;

    // Storage cost (annual)
    const storageCost = storageForYear(y) * sr * 12;

    // SPCS cost (annual)
    const spcsCost = calcSPCSCost() * 12 * ramp;

    // Openflow cost (annual)
    const of = SIZING_SPEC.openflow;
    const ofCost = of.enabled
      ? of.source_connections * of.vcpu_per_connection * of.hours_monthly * 0.0225 * cr * 12 * ramp
      : 0;

    // Oracle Openflow (annual, not credit-based)
    const oracleCost = SIZING_SPEC.openflow_oracle.enabled
      ? SIZING_SPEC.openflow_oracle.licensed_cores * (70 + 40) * 12
      : 0;

    // Data transfer & Privatelink (annual)
    const transferCost = calcTransferCost() * 12;

    // Collaboration costs (annual)
    const collabCost = calcCollabCost() * 12 * ramp;

    const computeCost  = whCredits  * cr;
    const serverlessCost = slCredits * cr;
    const aiCost       = aiCredits  * aiCr;
    const otherCost    = spcsCost + ofCost + oracleCost + transferCost + collabCost;
    const yearTotal    = computeCost + serverlessCost + aiCost + storageCost + otherCost;

    yearData.push({ y, whCredits, slCredits, aiCredits, computeCost, serverlessCost, aiCost, storageCost, otherCost, yearTotal });
  }

  updateKPIs(yearData);
  updateCharts(yearData);
  updateWorkloadCalcs();
  updateScenarios();
}
```

### `calcServerlessCredits()` — returns monthly credits

```javascript
function calcServerlessCredits() {
  const sl = SIZING_SPEC.serverless;
  let total = 0;
  // Unit-charge features
  if (sl.snowpipe.enabled)
    total += sl.snowpipe.files_per_month / 1000 * 0.0037 * 1000; // approx via GB
  if (sl.snowpipe_streaming.enabled)
    total += sl.snowpipe_streaming.uncompressed_gb_per_month * 0.0037;
  if (sl.snowpipe_streaming_classic.enabled)
    total += sl.snowpipe_streaming_classic.client_instances * 0.01 * 730;
  if (sl.open_catalog.enabled)
    total += sl.open_catalog.requests_per_month_M * 0.5;
  if (sl.telemetry_data_ingest.enabled)
    total += sl.telemetry_data_ingest.gb_per_month * 0.0212;
  if (sl.archive_storage_retrieval.enabled)
    total += sl.archive_storage_retrieval.files_per_month / 1000 * 0.05;
  if (sl.archive_storage_write.enabled)
    total += sl.archive_storage_write.files_per_month / 1000 * 0.05;
  if (sl.logging.enabled)
    total += sl.logging.file_batches_per_month / 1000 * 0.28;
  if (sl.automated_refresh.enabled)
    total += sl.automated_refresh.files_per_month / 1000 * 0.06;
  if (sl.hybrid_tables_requests.enabled)
    total += (sl.hybrid_tables_requests.reads_gb_monthly / 30) +
             (sl.hybrid_tables_requests.writes_gb_monthly / 7.5);
  // Compute-multiplier features (multiplier × 1 cr/hr)
  const computeMultipliers = {
    serverless_tasks: 0.9, serverless_tasks_flex: 0.5, serverless_alerts: 0.9,
    clustered_tables: 2.0, materialized_views: 2.0, search_optimization: 2.0,
    query_acceleration: 1.0, replication: 2.0, backup: 2.0, failsafe_recovery: 0.9,
    data_quality_monitoring: 2.0, trust_center: 1.0, table_optimization: 0.75,
    storage_lifecycle_policy: 0.5, copy_files: 2.0, organization_usage: 1.0,
    sensitive_data_classification: 0.9
  };
  for (const [key, mult] of Object.entries(computeMultipliers)) {
    const f = sl[key];
    if (f && f.enabled) total += f.compute_hours_monthly * mult;
  }
  return total;
}
```

### `calcAICredits()` — returns monthly AI credits

```javascript
function calcAICredits() {
  const ai = SIZING_SPEC.ai_cortex;
  let total = 0;
  const aiModels = PRICING_DATA.ai_features.cortex_complete.data;
  const getRate = (model, type) => {
    const m = aiModels.find(x => x.model === model);
    return m ? (m[type] || 0) : 0;
  };
  if (ai.cortex_complete.enabled)
    total += ai.cortex_complete.monthly_input_tokens_M  * getRate(ai.cortex_complete.model, 'input') +
             ai.cortex_complete.monthly_output_tokens_M * getRate(ai.cortex_complete.model, 'output');
  if (ai.cortex_agents.enabled)
    total += (ai.cortex_agents.monthly_input_tokens_M  * 1.88 +
              ai.cortex_agents.monthly_output_tokens_M * 9.41);
  if (ai.snowflake_intelligence.enabled)
    total += (ai.snowflake_intelligence.monthly_input_tokens_M  * 2.51 +
              ai.snowflake_intelligence.monthly_output_tokens_M * 12.55);
  if (ai.cortex_code.enabled) {
    const tokensM = ai.cortex_code.developers * ai.cortex_code.queries_per_dev_per_day *
                    ai.cortex_code.avg_tokens_per_query / 1_000_000 * 22;
    total += tokensM * 2.51; // via Snowflake Intelligence
  }
  if (ai.cortex_analyst.enabled)
    total += ai.cortex_analyst.monthly_messages / 1000 * 67;
  if (ai.cortex_search.enabled)
    total += ai.cortex_search.indexed_data_gb * 6.3;
  if (ai.document_ai.enabled)
    total += ai.document_ai.compute_hours_monthly * 8;
  if (ai.ai_parse_document_layout.enabled)
    total += ai.ai_parse_document_layout.pages_per_month / 1000 * 3.33;
  if (ai.ai_parse_document_ocr.enabled)
    total += ai.ai_parse_document_ocr.pages_per_month / 1000 * 0.5;
  if (ai.cortex_fine_tuning.enabled)
    total += ai.cortex_fine_tuning.training_tokens_M * 3.40; // llama3.1-70b default
  const funcRates = { ai_classify: 1.39, ai_sentiment: 1.60, ai_summarize: 0.10, ai_translate: 1.50, ai_extract: 5.00, ai_transcribe: 1.30 };
  for (const [key, rate] of Object.entries(funcRates)) {
    const f = ai.cortex_functions[key];
    if (f && f.enabled) total += f.tokens_M_monthly * rate;
  }
  if (ai.embeddings.enabled) total += ai.embeddings.tokens_M_monthly * 0.05;
  return total;
}
```

### `updateKPIs(yearData)`

```javascript
function updateKPIs(yearData) {
  const tcv = yearData.reduce((s, y) => s + y.yearTotal, 0);
  const yr1 = yearData[0].yearTotal;
  const totalCredits = yearData.reduce((s, y) => s + y.whCredits + y.slCredits + y.aiCredits, 0);
  document.getElementById('kpi-tcv').textContent       = '$' + fmt(tcv);
  document.getElementById('kpi-yr1').textContent       = '$' + fmt(yr1);
  document.getElementById('kpi-credits').textContent   = fmt(totalCredits) + ' cr';
  document.getElementById('kpi-commit').textContent    = '$' + fmt(tcv);
}
function fmt(n) { return Math.round(n).toLocaleString('en-US'); }
```

### `updateWorkload(id, field, value)` and `updateServerless(key, field, value)`

```javascript
function updateWorkload(id, field, value) {
  const w = SIZING_SPEC.workloads.find(x => x.id === id);
  if (w) { w[field] = value; recalculate(); }
}
function updateServerless(key, field, value) {
  if (SIZING_SPEC.serverless[key]) {
    SIZING_SPEC.serverless[key][field] = value;
    recalculate();
  }
}
```

---

## Formatting Rules

- Dollar amounts: `$X,XXX` (no cents unless <$10)
- Credit amounts: `X,XXX cr` (integer)
- Percentages: `XX%`
- Large numbers use `toLocaleString('en-US')`

---

## What-if Slider Behaviour

- All sliders fire `oninput` (not `onchange`) for live updates
- Every slider has a visible value display (a `<span>` next to it updated in `oninput`)
- Disabled inputs (feature not enabled) are `opacity: 0.4; pointer-events: none`
- Enabling a feature via toggle immediately enables its inputs and re-runs `recalculate()`

---

## On Page Load

```javascript
document.addEventListener('DOMContentLoaded', () => {
  populateGlobalSettings();
  populateWorkloadCards();
  populateServerlessPanel();
  populateAIPanel();
  populateSPCSPanel();
  populateOpenflowPanel();
  populateStoragePanel();
  populateCollabPanel();
  renderAssumptions();
  recalculate();
});
```
```

- [ ] **Step 2: Verify**

```bash
wc -l plugins/snowflake-sizing/skills/snowflake-sizing/references/html-spec.md
```

Expected: ~350+ lines

- [ ] **Step 3: Commit**

```bash
git add plugins/snowflake-sizing/skills/snowflake-sizing/references/html-spec.md
git commit -m "feat(snowflake-sizing): add html-spec reference document"
```

---

## Task 5: `SKILL.md` — core orchestration skill

**Files:**
- Create: `plugins/snowflake-sizing/skills/snowflake-sizing/SKILL.md`

- [ ] **Step 1: Write SKILL.md**

Write `plugins/snowflake-sizing/skills/snowflake-sizing/SKILL.md`:

```markdown
---
name: snowflake-sizing
description: Generate a defensible Snowflake consumption estimate and interactive HTML pricing proposal from a customer context file and Glean research.
argument-hint: "<context-file> [--customer \"Name\"] [--years 3] [--edition Enterprise] [--region \"AWS US East (Northern Virginia)\"]"
allowed-tools: [Read, Write, Bash, WebFetch, snowflake_sql_execute, mcp__glean_default__search, mcp__glean_default__read_document, mcp__glean_default__chat, mcp__glean_default__employee_search]
---

# Snowflake Sizing Skill

Generate a complete, defensible Snowflake consumption estimate and a single self-contained interactive HTML proposal.

---

## Phase 1 — Parse arguments & bootstrap

Parse `$ARGUMENTS`:
- `context_file` — required. Path to customer transcript, questionnaire, or notes.
- `--customer "Name"` — customer name override. If omitted, extract from context file.
- `--years N` — contract length in years. Default: **3**.
- `--edition X` — Standard / Enterprise / Business Critical / VPS. Default: **Enterprise**.
- `--region "X"` — full region string, e.g. `"AWS US East (Northern Virginia)"`. If omitted, infer from context file; default to `"AWS US East (Northern Virginia)"`.

Load pricing data:
```bash
cat skills/snowflake-sizing/assets/../../../assets/snowflake_pricing_master.json
```
(Note: command must resolve relative to the plugin root. Use Read tool on `assets/snowflake_pricing_master.json`.)

Derive from pricing data:
- `credit_rate` — from `credit_pricing.data` matching cloud + region + edition
- `ai_credit_rate` — from `ai_credit_pricing.on_demand.global` ($2.00 default)
- `storage_rate_per_tb` — from `storage.on_demand` for the region

Build initial `meta` object:
```json
{
  "customer": "[extracted name]",
  "edition": "[edition]",
  "cloud": "[AWS|Azure|GCP]",
  "region": "[region]",
  "credit_rate": [number],
  "ai_credit_rate": 2.00,
  "storage_rate_per_tb": [number],
  "hybrid_tables_storage_rate_per_gb": 0.34,
  "contract_years": [N],
  "generated_date": "[today YYYY-MM-DD]",
  "ramp_curve": "linear",
  "pdf_version": "2026-05-12"
}
```

Read reference documents now (run in parallel):
1. Read `skills/snowflake-sizing/references/sizing-methodology.md`
2. Read `skills/snowflake-sizing/references/html-spec.md`

---

## Phase 2 — Research in parallel

Run these THREE operations simultaneously:

**A. Read context file**
Read the file at `context_file`. Extract every piece of information relevant to sizing:
- Company name, industry, size
- Existing data stack and tools
- Stated workloads (ingestion, transformation, BI, ML, apps)
- Data volumes (daily, monthly, total)
- User counts and concurrency
- Operating hours and days
- Growth projections
- Specific Snowflake features mentioned
- Any budget or target spend mentioned

**B. Glean research** (run all 3 searches in parallel)
```
search: "[customer name] snowflake data platform workloads"   → Salesforce/Drive
search: "[customer name]" app:gong                            → Gong call summaries
search: "[customer name]" app:salescloud                      → opportunity context
```

From Glean results extract: industry vertical, company scale, tech stack signals, stated pain points, growth indicators.

**C. Gong transcript SQL** (use SNOWHOUSE connection)

Phase 1 — Find calls:
```sql
SELECT CONVERSATION_KEY, CONVERSATION_ID, TITLE,
       PLANNED_START_DATETIME::DATE AS call_date,
       CALL_SPOTLIGHT_BRIEF, CALL_URL
FROM GONG_SHARE.GONG_DATA_CLOUD.CALLS
WHERE LOWER(TITLE) LIKE LOWER('%[customer name]%')
ORDER BY PLANNED_START_DATETIME DESC
LIMIT 3;
```

If no results, retry with a shorter substring (first word only) or known abbreviations.

Phase 2 — Load transcripts (top 2 calls from Phase 1):
```sql
SELECT p.NAME AS speaker, p.AFFILIATION,
       t.value:topic::STRING AS topic,
       t.INDEX AS turn_index,
       t.value:sentences AS sentences
FROM GONG_SHARE.GONG_DATA_CLOUD.CALL_TRANSCRIPTS ct,
     LATERAL FLATTEN(input => ct.TRANSCRIPT) t
JOIN GONG_SHARE.GONG_DATA_CLOUD.CONVERSATION_PARTICIPANTS p
    ON ct.CONVERSATION_KEY = p.CONVERSATION_KEY
    AND t.value:speakerId::STRING = p.SPEAKER_ID::STRING
WHERE ct.CONVERSATION_KEY IN ('[key_1]', '[key_2]')
ORDER BY ct.CONVERSATION_KEY, t.INDEX;
```

Extract from transcripts: stated data volumes, tech stack, workload descriptions, pain points, growth plans, pricing signals. Use `AFFILIATION` to distinguish Internal (Snowflake) vs External (customer) speakers. If `TRANSCRIPT` is NULL, fall back to `CALL_SPOTLIGHT_BRIEF`.

If SNOWHOUSE is unavailable or `GONG_SHARE` is not accessible, skip this operation and continue with A + B only.

**Merge all sources.** Context file takes precedence. Glean fills account-level gaps. Gong transcripts provide verbatim customer statements. Note the source for every number used in Phase 3.

---

## Phase 3 — Build the sizing spec

Using `sizing-methodology.md` as your rulebook, reason through EVERY consumption category.

**For each workload category, decide:**
1. Is this relevant to this customer? (enabled: true / false)
2. If enabled: what are the sizing parameters? (SIZE from evidence, not guessing)
3. Label every number: SOURCED (cite it) or ASSUMPTION (explain it)
4. Add anything unclear to `confirm_required` with quantified impact

**Work through categories in this order:**

### Warehouses
Identify all distinct workload patterns and create one warehouse entry per pattern:
- Data Ingestion (if batch/ELT loading)
- Transformation / ELT (if transformation occurs in Snowflake)
- BI / Analytics (one per BI tool or user group if different patterns)
- Ad-hoc / Data Science (if mentioned)
- Development (always include: 1 × XS, 4 hrs/day, 22 days)
- Any other specific workloads mentioned

Apply warehouse sizing rules from `sizing-methodology.md`. Apply MCW when concurrency rules trigger.

### Serverless Features
For each of the 27 features in the spec template, set enabled=true only if there is EVIDENCE or a strong ASSUMPTION for that customer. Set all others to enabled=false with `ASSUMPTION: not required for this use case`.

Key patterns to check:
- Snowpipe / Snowpipe Streaming → any real-time or event-driven ingestion?
- Serverless Tasks → any orchestration/scheduling?
- Dynamic Tables → any declarative pipeline?
- Clustered Tables → large tables with selective filtering?
- Replication → multi-region or DR requirements?
- Search Optimization → point lookups on large tables?

### AI / Cortex Features
Enable only what the customer has explicitly mentioned or where there is clear use case evidence. Do NOT default-enable AI features.

If the customer is in a data science or AI-forward industry, flag relevant features in `confirm_required`.

### SPCS, Openflow, Postgres
Enable only if explicitly mentioned. For Openflow, always ask about source database server count.

### Storage
Use stated data volumes from context. Apply compression defaults from `sizing-methodology.md`. Set time_travel_days=1 (default) and churn_rate=10% unless stated otherwise.

### Growth rates
Build `growth_rates` array:
```
growth_rates[0] = ramp_year1  (default 0.70 for linear)
growth_rates[y] = 1.0 × (1 + annual_growth)^(y-1)  for y >= 1
```
Use growth rate from context file if stated, otherwise 0.20 (20%/yr).
Extend array to `contract_years` length.

### Compile spec
Produce the complete JSON spec matching the structure in the design spec. Include:
- All enabled workloads with SOURCED/ASSUMPTION labels
- All disabled features set to enabled:false
- `assumptions` array (20+ items expected for a thorough estimate)
- `confirm_required` array with quantified impact statements

---

## Phase 4 — Apply multi-year growth

For each year 1 to N, compute year-level totals:

| Component | Formula |
|---|---|
| Warehouse credits/yr | Σ(size_cr/hr × hrs/day × days/mo × avg_clusters) × 12 × ramp[y] |
| Serverless credits/yr | monthly_serverless_credits × 12 × ramp[y] |
| AI credits/yr | monthly_ai_credits × 12 × ramp[y] |
| Storage cost/yr | storage_tb(y) × storage_rate × 12 |
| SPCS cost/yr | Σ(instance_cr/hr × hrs/mo × count) × credit_rate × 12 × ramp[y] |
| Openflow cost/yr | connections × vcpu × hours × 0.0225 × credit_rate × 12 × ramp[y] |
| Transfer + Privatelink | tb × rate × 12 |

Print a summary table to the terminal (for SE reference):

```
Year | Credits | Compute $ | Serverless $ | AI $ | Storage $ | Total $
  1  |  XX,XXX | $XX,XXX   | $X,XXX       | $X   | $X,XXX    | $XX,XXX
  2  |  XX,XXX | $XX,XXX   | $X,XXX       | $X   | $X,XXX    | $XX,XXX
  3  |  XX,XXX | $XX,XXX   | $X,XXX       | $X   | $X,XXX    | $XX,XXX
TCV: $XXX,XXX
```

---

## Phase 5 — Generate interactive HTML

Using `html-spec.md` as the exact specification, write the complete HTML file to:
`temp/<customer-slug>-<N>year-sizing.html`

Where `customer-slug` = customer name lowercased, spaces replaced with hyphens.

The file MUST:
1. Be completely self-contained (no external file dependencies beyond CDN scripts)
2. Embed `PRICING_DATA` as the full parsed pricing JSON constant (all keys)
3. Embed `SIZING_SPEC` as the complete spec JSON constant
4. Implement all functions from `html-spec.md` verbatim (exact names matter for the HTML event handlers)
5. Call `recalculate()` on page load
6. Use Snowflake brand colours from `html-spec.md` CSS variables
7. Include all 8 configuration tabs (Warehouses, Serverless, AI/Cortex, SPCS, Openflow, Storage, Collaboration, Global Settings)
8. Include the 3-scenario comparison panel
9. Show assumptions and confirm_required items

**Quality check before writing the file:**
- Count workload cards in the JS → must match number of workloads in SIZING_SPEC
- Verify `growth_rates` array length = `contract_years`
- Verify `credit_rate` in spec matches the region in the header

---

## Phase 6 — Output summary

Print to terminal:

```
✅ Generated: temp/[filename]

📊 [CUSTOMER] — [N]-Year Consumption Estimate
  Edition: [EDITION] · [CLOUD] [REGION] · $[CREDIT_RATE]/credit

  Year 1:  $[XX,XXX]  ([XX,XXX] credits)
  Year 2:  $[XX,XXX]
  Year 3:  $[XX,XXX]
  ──────────────────
  TCV:     $[XXX,XXX]

📈 Top 3 workloads by credit volume:
  1. [Workload label] — [XX,XXX] cr/yr ([XX]%)
  2. [Workload label] — [XX,XXX] cr/yr ([XX]%)
  3. [Workload label] — [XX,XXX] cr/yr ([XX]%)

⚠️  Requires customer confirmation:
  • [confirm_required item 1]
  • [confirm_required item 2]
  ...

Open in browser: open temp/[filename]
```
```

- [ ] **Step 2: Verify**

```bash
wc -l plugins/snowflake-sizing/skills/snowflake-sizing/SKILL.md
```

Expected: ~250+ lines

- [ ] **Step 3: Commit**

```bash
git add plugins/snowflake-sizing/skills/snowflake-sizing/SKILL.md
git commit -m "feat(snowflake-sizing): add main SKILL.md with 6-phase workflow"
```

---

## Task 6: README.md

**Files:**
- Create: `plugins/snowflake-sizing/README.md`

- [ ] **Step 1: Write README**

Write `plugins/snowflake-sizing/README.md`:

```markdown
# snowflake-sizing

Generate accurate, defensible Snowflake consumption estimates and interactive customer-facing HTML proposals.

## Usage

```bash
/snowflake-sizing <context-file> [options]
```

**Options:**

| Option | Default | Description |
|---|---|---|
| `--customer "Name"` | (from context file) | Customer name for proposal |
| `--years N` | `3` | Contract length in years |
| `--edition X` | `Enterprise` | Standard / Enterprise / Business Critical / VPS |
| `--region "X"` | `"AWS US East (Northern Virginia)"` | Full region string |

## Example

```bash
/snowflake-sizing temp/acme-discovery-notes.txt --customer "ACME Corp" --years 3 --edition Enterprise --region "AWS Europe (London)"
```

## Output

A single self-contained HTML file at `temp/<customer-slug>-<N>year-sizing.html`.

Open it in any browser. The proposal includes:
- Executive summary with live TCV, Year 1 cost, and total credits
- Year-by-year bar chart and workload breakdown donut
- Interactive sliders for every variable (warehouse size, hours, clusters, serverless features, AI tokens, storage, etc.)
- 3-scenario comparison (Conservative / Expected / Aggressive)
- All assumptions listed with source citations
- Items requiring customer confirmation with quantified impact

## Context File Format

Any combination of:
- Call transcripts (plain text or copied from Gong)
- Completed sizing questionnaire (Word, PDF, or plain text)
- Discovery notes
- Company background

The more detail the better. Missing information will be flagged as assumptions or confirmed requirements.

## Pricing Data

Bundled in `assets/snowflake_pricing_master.json` — based on the Snowflake Service Consumption Table effective **2026-05-12**.

To update: edit `assets/snowflake_pricing_master.json` and update `metadata.effective_date`.

## Branding

Snowflake brand colours (`#29B5E8`, `#11567F`) and Open Sans font (via Google Fonts CDN). The Snowflake logo is rendered as inline SVG.
```

- [ ] **Step 2: Commit**

```bash
git add plugins/snowflake-sizing/README.md
git commit -m "docs(snowflake-sizing): add README"
```

---

## Task 7: Smoke test with sample context

**Files:**
- None created (test only)

- [ ] **Step 1: Create a minimal test context file**

Write `temp/test-context.txt`:
```
Customer: Acme Financial Services
Industry: Financial Services / Banking
Region: UK, planning to use AWS Europe (London)
Snowflake Edition: Enterprise

Discovery Notes:
- 50GB daily batch loads from 3 SQL Server databases via Fivetran
- dbt Cloud for transformations (~200 models, runs nightly, ~45 min)
- Power BI DirectQuery with 40 concurrent users during business hours (8am–6pm weekdays)
- 5 data scientists using Python notebooks + Snowpark, running 2–3 hours/day
- Dev team of 8 engineers
- Current data warehouse: ~5TB raw data, expecting 30% annual growth
- Real-time fraud detection pipeline mentioned as Year 2 initiative
- No Snowflake AI features planned initially
- Budget target: £2M over 3 years
```

- [ ] **Step 2: Run the plugin**

```bash
# From the plugin root (plugins/snowflake-sizing/)
# In Cortex Code / Claude Code, run:
/snowflake-sizing temp/test-context.txt --customer "Acme Financial" --years 3 --edition Enterprise --region "AWS Europe (London)"
```

- [ ] **Step 3: Verify HTML output exists**

```bash
ls -la temp/ | grep acme
```

Expected: `acme-financial-3year-sizing.html` exists and is >50KB.

- [ ] **Step 4: Open and verify the HTML**

```bash
open temp/acme-financial-3year-sizing.html
```

Manually verify:
- [ ] Page loads without JS errors (check browser console)
- [ ] Header shows "Acme Financial" with Enterprise + AWS Europe (London) + credit rate $4.00
- [ ] Executive Summary KPI tiles show non-zero TCV
- [ ] Year-by-year bar chart renders with 3 bars
- [ ] Workload cards show calculation annotations (e.g. `4 cr/hr × X hrs × 22 days = N cr/mo`)
- [ ] Moving a warehouse size slider updates the KPI tiles
- [ ] Serverless section shows Snowpipe toggle (disabled by default, since Fivetran handles ingestion)
- [ ] Assumptions section has at least 10 items
- [ ] Confirm required shows at least 1 item (SQL Server same instance question)
- [ ] Scenario comparison shows 3 columns with different TCV values

- [ ] **Step 5: Verify credit rate calculation**

In the browser console:
```javascript
console.log(SIZING_SPEC.meta.credit_rate);  // Expected: 4.00 (Enterprise, AWS London)
console.log(SIZING_SPEC.workloads.length);  // Expected: ≥4 (ingest, transform, BI, dev)
console.log(SIZING_SPEC.growth_rates);      // Expected: [0.70, 1.00, 1.20]
```

- [ ] **Step 6: Final commit**

```bash
# temp/ is gitignored — only commit if you've added anything to track
git status  # confirm temp/ files are not staged
```

---

## Self-Review Against Spec

**Spec coverage check:**

| Spec Requirement | Task |
|---|---|
| Plugin scaffold (plugin.json, command, skill dirs) | Task 1 |
| Default years=3 | Task 1 (command) + Task 5 (SKILL.md Phase 1) |
| Glean research of customer | Task 5 (SKILL.md Phase 2) |
| All May 2026 PDF tables in pricing JSON | Task 2 |
| Full sizing spec JSON structure | Task 5 (SKILL.md Phase 3) + Task 3 (methodology) |
| Multi-year growth_rates formula | Task 3 (methodology) + Task 4 (html-spec JS) |
| Interactive HTML sliders for all variables | Task 4 (html-spec.md) |
| JS calculation engine (recalculate, calcServerlessCredits, etc.) | Task 4 (html-spec.md) |
| Chart.js year-by-year + donut charts | Task 4 (html-spec.md) |
| 3-scenario comparison panel | Task 4 (html-spec.md) + Task 5 (SKILL.md Phase 5) |
| Assumptions + confirm_required rendering | Task 4 (html-spec.md) |
| Snowflake branding (colours, fonts, logo) | Task 4 (html-spec.md) |
| Time-travel + failsafe storage overhead | Task 3 (methodology) + Task 4 (storageForYear) |
| Cortex Code via Snowflake Intelligence | Task 3 (methodology) + Task 4 (calcAICredits) |
| Openflow Oracle connector ($70+$40/core/mo) | Task 5 (SKILL.md) + Task 4 (html-spec) |
| AI Credit Pricing (separate $2.00/credit pool) | Task 2 (pricing JSON) + Task 4 (JS engine) |
| Gen 2 SPCS instances | Task 2 (pricing JSON) + Task 4 (SPCS panel) |
| Phase 6 summary output | Task 5 (SKILL.md Phase 6) |
| Smoke test | Task 7 |

All spec requirements are covered.
