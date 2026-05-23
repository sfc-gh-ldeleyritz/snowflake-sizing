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

Read pricing data (use Read tool on `assets/snowflake_pricing_master.json`).

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

Read reference documents in parallel:
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
mcp__glean_default__search: "[customer name] snowflake data platform workloads"
mcp__glean_default__search: "[customer name]" app:gong
mcp__glean_default__search: "[customer name]" app:salescloud
```

From Glean results extract: industry vertical, company scale, tech stack signals, stated pain points, growth indicators.

**C. Gong transcript SQL** (use SNOWHOUSE connection via `snowflake_sql_execute`)

Phase C1 — Find calls:
```sql
SELECT CONVERSATION_KEY, CONVERSATION_ID, TITLE,
       PLANNED_START_DATETIME::DATE AS call_date,
       CALL_SPOTLIGHT_BRIEF, CALL_URL
FROM GONG_SHARE.GONG_DATA_CLOUD.CALLS
WHERE LOWER(TITLE) LIKE LOWER('%[customer_name]%')
ORDER BY PLANNED_START_DATETIME DESC
LIMIT 3;
```

If no results, retry with a shorter substring (first word only) or known abbreviations.

Phase C2 — Load transcripts (top 2 calls from C1):
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

Replace `[key_1]`, `[key_2]` with CONVERSATION_KEY values from C1. Use `CONVERSATION_KEY` (hash), NOT `CONVERSATION_ID` (numeric).

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
Produce the complete JSON spec. Include:
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
