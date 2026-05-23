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
