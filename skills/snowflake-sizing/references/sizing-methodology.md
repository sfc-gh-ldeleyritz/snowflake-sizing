# Snowflake Sizing Methodology

## The Prime Directive: SOURCE OR ASSUMPTION

Every number in the estimate MUST be one of:
- **SOURCED**: Directly from context file or Glean research — cite it. E.g. `SOURCED: questionnaire Q4 — "50GB daily batch load"`
- **ASSUMPTION**: Explicitly labelled with rationale. E.g. `ASSUMPTION: weekday-only operation (22 days/month) — no evidence of weekend processing`
- **REQUIRES_CONFIRMATION**: Flag when missing info significantly impacts cost. Quantify the impact.

Never guess silently. Never omit a category. Never fabricate data.

## Currency: USD only, never convert

Every figure in a sizing is in **US dollars (USD)**. Snowflake credit and storage rates are USD; do not convert any number into GBP, EUR, JPY, or any other currency, and do not include a non-USD currency symbol (£, €, ¥) or an FX/"exchange rate" calculation anywhere in the spec or HTML. If the customer requires billing in another currency, capture that as a `confirm_required` item (e.g. "Confirm GBP billing currency and FX handling with deal desk") — phrased in USD with no converted figure. The pre-write guard blocks non-USD symbols, conversion phrasing, and non-USD figures (a bare currency name in a confirm note is allowed).

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

| Model | Input | Output | Notes |
|---|---|---|---|
| claude-sonnet-4-6 | 1.65 | 8.25 | **← DEFAULT for cortex_complete** |
| claude-4-sonnet | 1.50 | 7.50 | Legacy — prefer claude-sonnet-4-6 |
| claude-4-opus | 7.50 | 37.50 | Complex reasoning only |
| claude-haiku-4-5 | 0.55 | 2.75 | High-volume / low-cost |
| llama4-maverick | 0.12 | 0.49 | |
| llama4-scout | 0.09 | 0.33 | |
| openai-gpt-4.1 | 1.00 | 4.00 | |
| snowflake-arctic | 0.84 | 0.84 | |

### Cortex Agents — Table 6(b) (credits per 1M tokens)

| Model | Input | Output |
|---|---|---|
| claude-4-sonnet | 1.88 | 9.41 |
| claude-haiku-4-5 | 0.75 | 3.76 |
| openai-gpt-4.1 | 1.50 | 6.00 |

### Snowflake Intelligence — Table 6(d) (credits per 1M tokens)

Used for Cortex Code, Snowflake Intelligence agentic features.

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

**DEPRECATED (2026-05-26)** — Superseded by `AI_EXTRACT`. Do NOT include `document_ai`, `ai_parse_document_layout`, or `ai_parse_document_ocr` in new sizing specs. For document processing workloads, use `ai_extract` with appropriate token volumes (default 70M tokens/month when document extraction is a primary use case).

### Cortex Code (per-surface billing)

Cortex Code bills at the Table 6(e) rate (~$2.51/M tokens blended) regardless of surface, but per-developer usage differs significantly by surface. Estimate each surface independently and sum:

```
surface_credits/mo = developers × queries/dev/day × tokens/query / 1,000,000 × 22 × 2.51
total = sum(cli, snowsight, desktop)
```

| Surface | Typical queries/dev/day | Typical tokens/query | Notes |
|---|---|---|---|
| CLI | 5–20 | 800–1,500 | Power users in terminal; lightweight prompts. |
| Snowsight | 10–40 | 1,000–1,800 | SQL assist inside worksheets; medium per-dev usage. |
| Cortex Code Desktop | 30–80 | 1,200–2,500 | IDE assistant with inline suggestions + chat; heaviest per-dev usage. |

Default if surface is uncertain: enable CLI only at 20 queries/dev/day × 1,200 tokens/query (conservative). Flag the other two surfaces in `confirm_required` so the SE can validate with the customer.

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

## Ramp-Up Curves (Birdbox per-workload model)

Each workload row carries three ramp inputs that determine its month-by-month consumption:

- `dev_start_month` — first month of any consumption (typically 0; billing ramp begins from month 1 of the contract)
- `go_live_month` — month at which consumption reaches 100% of steady-state (typically 3)
- `ramp_curve` — one of `slowest | slow | linear | fast | fastest | manual`

### The factor formula

```
factor(m) = clamp(((m − dev_start + 1) / (go_live − dev_start + 1)) ^ exponent, 0, 1)
```

Where `exponent` comes from `pricing.ramp_curves.exponents`:

| Curve | Exponent | Shape | Typical Use |
|---|---|---|---|
| Slowest | 4.0 | Slow start, gradual acceleration | Heavy migration, >12 month rollout |
| Slow | 2.0 | Quadratic ramp | Phased migration, 6–12 month rollout |
| Linear | 1.0 | Steady straight line | Standard new deployment (default) |
| Fast | 0.5 | Square-root: quick early gains | Replacing existing system; team ready |
| Fastest | 0.25 | Sharp early ramp, tail to 100% | Lift-and-shift; immediate full usage |
| Manual | 0 | All months = 0 | Caller overrides per-month values |

For `m < dev_start` factor is 0; for `m > go_live` factor is 1. After go-live, the existing annual `growth_rate` applies to subsequent years.

### Choosing a curve

The agent should default to `pricing.ramp_curves.recommended_by_workload_type[<workload kind>]`, e.g.:

- migration → slow
- new_BI_dashboard, new_data_pipeline, new_ELT → linear
- ML_training → slow ; ML_inference → fast
- Cortex_pilot → fastest ; Cortex_production → fast
- DR_replication → fastest
- lift_and_shift → fast

### Year 1 effective multiplier examples

For the default window (`dev_start=0`, `go_live=3`), the average of factor(1..12) is roughly:

| Curve | Avg factor across 12 months |
|---|---|
| Slowest | 0.86 |
| Slow | 0.90 |
| Linear | 0.94 |
| Fast | 0.96 |
| Fastest | 0.98 |

These are **derived**, not configured — Phase 4 sums per-month factors directly rather than using a single multiplier.

### Multi-year monthly model

Phase 4 produces a per-month credit array, not a per-year multiplier. Year totals come from `sum(factor(m) × monthly_credits × growth_factor(year(m)))` where `growth_factor` applies the annual `growth_rate` from year 2 onwards.

### Annual growth (per-workload, AI, and parity)

Growth is applied as `(1 + growth) ^ (year − 1)`, layered on top of the ramp factor. Three knobs control which rate a category uses:

- `meta.annual_growth_rate` — the base case for every warehouse, serverless, SPCS, OpenFlow, and collaboration line. Defaults to `0.20` when unset (matching the interactive render).
- `workloads[].growth_rate` (optional) — overrides `annual_growth_rate` for a single warehouse row, so a fast-growing ML workload and a flat ELT workload can diverge in the same model.
- `meta.ai_growth_rate` (optional, may be `null`) — growth for the AI/Cortex category. When `null`/absent it falls back to `annual_growth_rate`.

Precedence in the interactive render is **scenario `growthOverride` > `workloads[].growth_rate` > `meta.annual_growth_rate`**; a scenario band replaces every per-workload rate so the Conservative/Expected/Aggressive cards stay clean.

**Python/JS parity:** `framework/compute_totals.py` and the JS in `proposal-template.html` apply growth identically (year 1 = averaged ramp, years 2+ = full capacity × cumulative growth). The build-time `computed_totals` therefore equals the rendered headline TCV to the cent — there is no separate "static vs interactive" number. If you change one growth path, change the other and re-run the parity test.

---

## The Three-Scenario Rule

Always present three TCV scenarios in the HTML. Scenarios shift `ramp_curve` and `go_live_month` together so they remain physically meaningful:

| Scenario | Growth Rate | Ramp Curve | Go-live shift | Intent |
|---|---|---|---|---|
| Conservative | 10%/yr | slow | +1 month later | Minimum commitment anchor |
| Expected | 20%/yr | linear | unchanged | Recommended contract value |
| Aggressive | 35%/yr | fast | −1 month earlier | Innovation + full adoption |

---

## Replication Sizing

Activate this section when the context mentions BCDR / DR / replication / data sharing / migration. Pricing data lives in `pricing.replication`.

### Inputs (per replication relationship)

| Field | Source |
|---|---|
| `source_region` | Customer Snowflake account region (Source Deployment) |
| `target_region` | Replica region OR `Egress Cost Optimizer (ECO) Cache` |
| `initial_TB` | Active bytes at start. Measure with `SYSTEM$ESTIMATE_REPLICATION_COST` or sum `STAT_ACTIVE_BYTES` (see research-protocol.md) |
| `monthly_change_TB` | Monthly bytes replicated. Measure via `FIFTEEN_MINS_TB / ONE_HOUR_TB / ONE_DAY_TB` from `SYSTEM$ESTIMATE_REPLICATION_COST` |
| `storage_growth_pct` | Yearly. Use `account_usage.database_storage_usage_history` query in research-protocol.md. Default: 15%. |
| `yoy_pct` | Year-over-year increase in changes + storage. Default: 10%. |
| `compute_credits_per_TB` | Default 4 from `pricing.replication.compute_credits_per_TB.default`. Range 3–5. Use 4–5 for small payloads with high object count (metadata scan dominates). |
| `replica_storage_$_per_TB_per_month` | Target deployment's storage rate from `pricing.storage` |

### Formulas (3-year)

```
year_1_active_TB     = initial_TB
year_n_active_TB     = year_(n−1)_active_TB + year_(n−1)_growth_TB
year_1_growth_TB     = initial_TB × storage_growth_pct
year_n_growth_TB     = year_(n−1)_growth_TB × (1 + yoy_pct)
year_1_change_TB     = monthly_change_TB × 12
year_n_change_TB     = year_(n−1)_change_TB × (1 + yoy_pct)

# Compute and egress have a year-1 special case to account for the initial seed transfer:
year_1_basis_TB      = active_TB + growth_TB + change_TB    (= end-of-year storage + annual change)
year_n>1_basis_TB    = growth_TB + change_TB                 (= incremental delta only)

annual_compute_credits  = basis_TB × compute_credits_per_TB
annual_compute_cost     = annual_compute_credits × $/credit
annual_egress_cost      = basis_TB × egress_matrix[source_region][target_region]
annual_replica_storage  = avg_TB × replica_storage_$/TB/mo × 12
                        where avg_TB = active_TB + (growth_TB / 2)

annual_total            = annual_compute_cost + annual_egress_cost + annual_replica_storage
```

Year-1 special case (`active + growth + change` basis) reflects that replication needs to seed the entire primary state into the target. From year 2 onwards, only the incremental delta crosses the wire. This matches the Apr 2026 Replication Cost Calculator output exactly (verified against the documented $160,444.54 example for Thailand → ECO Cache, 100 TB initial, 8 TB/month change, 15% growth, 10% YoY).

### Egress matrix lookup

The matrix `pricing.replication.egress_matrix[source][target]` returns `$/TB`. Diagonal entries (same region) are 0. Convention: rows = source, cols = target.

If `target_region == "Egress Cost Optimizer (ECO) Cache"`, additional ECO Cache update-frequency multipliers apply — see `pricing.replication.eco_cache.update_frequency_factors`.

### Compute credits/TB selection

| Payload Profile | Credits/TB |
|---|---|
| Large databases, few objects (e.g., wide fact tables) | 3 |
| Mixed (default) | 4 |
| Many small objects, high DDL churn (metadata-heavy) | 5 |

When in doubt, use 4 and flag `REQUIRES_CONFIRMATION` so the SE can validate against `SYSTEM$ESTIMATE_REPLICATION_COST` output.

---

## Migration Scenario

A migration is replication used as a one-way bulk transfer from a source deployment (or external system) into Snowflake. Use the same replication formulas with these adjustments:

- `monthly_change_TB` ≈ `initial_TB / migration_window_months` for the migration window, then drops to ongoing change rate (often near 0 if the source is decommissioned).
- `ramp_curve` defaults to `slow` (matches the gradual cutover most enterprise migrations follow).
- After cutover, `replica_storage_*` becomes primary storage cost — fold it into the standard storage line, not the replication line.
- Egress only applies if data leaves a paid region. Same-region or in-cloud migrations may have $0 egress.

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
- How many tables per OpenFlow source database? (600-table limit per runtime — can force more nodes)
- Expected monthly data volume through OpenFlow? (±30% of cost via Snowpipe)
- Is there an existing warehouse that can be reused for CDC MERGE? (can avoid 60–70% of CDC cost)
- For Oracle CDC: processor type — Intel/AMD x86 counts at 0.5 factor; SPARC/POWER at 1.0

---

## OpenFlow Sizing

### Runtime Size Selection by Connector Type

**CDC (JDBC/database):**
- Dedicated 1 runtime node per distinct JDBC source server (not per table/schema)
- `runtime_nodes = max(source_server_count, ceil(total_tables / 600))` — 600-table limit per runtime
- Runtime size: Medium if ≤100,000 events/day/connection; Large if >100,000 events/day
- Always confirm: "Are all databases on the same physical server/cluster?" — determines 1 vs N nodes

**Streaming (Kafka, Kinesis, etc.):**
- Compute effective throughput: `messages_per_second × avg_message_size_kb / 1000` MB/s
- Small if throughput < 10 MB/s; Medium if 10–50 MB/s; Large if ≥ 50 MB/s
- Runtime nodes: start at 1; add nodes if throughput requires horizontal scale or high availability

**Files (S3, SFTP, etc.):**
- Small for most workloads (infrequent batch, low transform complexity)
- Medium/Large for high-volume continuous ingestion with heavy transformations

**SaaS / REST API:**
- Small unless high polling frequency + complex transforms → Medium

**Oracle CDC:**
- Same node rules as CDC; additionally has licensing cost ($110/core/mo yr 1–3, $40/core/mo yr 4+)
- Licensed cores = physical processor cores × processor_factor (x86=0.5, SPARC/POWER=1.0)

### Platform Limits

| Constraint | Value |
|---|---|
| Max tables per runtime | 600 |
| Runtime packing ratio (SPCS) | 3 runtime nodes per compute pool node |
| Runtime packing ratio (BYOC) | 3 runtime nodes per EC2 node |
| EBS per EC2 compute pool node | 200 GB |
| SPCS control pool | 1 per deployment (not per instance) |
| BYOC fixed infra | 1 set per deployment (not per instance) |

### SPCS Credit Rates (Credit Consumption Table 1d)

| Runtime size | cr/hr per compute pool node |
|---|---|
| Small | 0.11 |
| Medium | 0.41 |
| Large | 0.83 |
| Control pool (CPU_X64_S) | 0.11 (always-on, 1 per deployment) |

### BYOC Regional Pricing

| AWS Region | Fixed infra/mo | EC2 Small/hr | EC2 Medium/hr | EC2 Large/hr | EBS/GB-mo |
|---|---|---|---|---|---|
| us-east-1 | $463.39 | $0.2016 | $0.8064 | $1.6128 | $0.080 |
| us-west-2 | $463.39 | $0.2016 | $0.8064 | $1.6128 | $0.080 |
| eu-west-1 | $505.79 | $0.2247 | $0.8988 | $1.7976 | $0.088 |
| eu-west-2 | $522.57 | $0.2331 | $0.9324 | $1.8648 | $0.0928 |
| eu-central-1 | $537.74 | $0.2415 | $0.9660 | $1.9320 | $0.0952 |
| ap-southeast-1 | $560.53 | $0.2520 | $1.0080 | $2.0160 | $0.096 |
| ap-northeast-1 | $575.49 | $0.2604 | $1.0416 | $2.0832 | $0.096 |

### BYOC vCPU Snowflake Credits (Credit Consumption Table 1g)

0.0225 credits/vCPU/hour. vCPU counts: Small = 1, Medium = 4, Large = 8.

### Snowpipe Streaming Rate

0.0037 credits/GB uncompressed. Applied to all connector types on the `monthly_data_gb` volume.

### Warehouse MERGE (CDC)

MERGE warehouse is often the dominant cost for CDC workloads (60–70% of total). Key guidance:
- X-Small (1 cr/hr) sufficient for most CDC workloads with <10M events/day
- Warehouse hours ≈ 24 × days_per_month for continuous CDC; lower for scheduled batch
- Always ask if customer already has a shared warehouse — avoids duplicating this cost in the estimate
