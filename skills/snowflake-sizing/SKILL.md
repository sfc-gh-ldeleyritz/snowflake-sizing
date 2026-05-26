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
- `--region "X"` — full region string, e.g. `"AWS Europe (London)"`. If omitted, infer from context file; default to `"AWS Europe (London)`".

Read pricing data using the absolute path (works regardless of working directory):

```
~/Snowflake/Repos/aross-se-superpowers/plugins/snowflake-sizing/assets/snowflake_pricing_master.json
```

Derive from pricing data:

- `credit_rate` — from `credit_pricing.data` matching cloud + region + edition (see Region name resolution below)
- `ai_credit_rate` — from `ai_credit_pricing.on_demand.global` ($2.00 default)
- `storage_rate_per_tb` — from `storage.standard` for the region (use `row["on_demand"]` for the no-commit rate)

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
  "default_ramp_curve": "linear",
  "default_dev_start_month": 0,
  "default_go_live_month": 3,
  "pdf_version": "2026-05-12",
  "version_number": 1
}
```

The `default_*` fields seed per-workload defaults during Phase 3. They are not used directly in Phase 4 — every workload row carries its own `ramp_curve`, `dev_start_month`, `go_live_month`.

**Optional discount block.** If the context mentions a negotiated capacity discount, an Order Form rate, or the SE asks for a what-if, add a `discount` block to `meta` (and seed `list_credit_rate` to the same value as `credit_rate`):

```json
"list_credit_rate": [same as credit_rate above],
"discount": {
  "enabled": true,
  "mode": "percent",          // or "rate"
  "percent": 25,              // 0..100
  "rate": null                // or e.g. 3.00; null derives from percent
}
```

`meta.credit_rate` should be written as the **effective** (post-discount) rate; `meta.list_credit_rate` preserves the pricing-JSON value for badge math. The HTML's `applyDiscount()` helper recomputes both on Edition / Cloud / Region changes. Omit the `discount` block entirely if no discount applies — the template will seed `enabled: false` automatically.

**Scope reminder.** Per the AI Pricing Sales GTM FAQ, negotiated capacity discounts apply to Platform Credits only. AI Credits ($2.00 global / $2.20 regional) keep the on-demand rate; the discount block does **not** modify `meta.ai_credit_rate`.

Read all four files in a single parallel batch (absolute paths — works regardless of working directory):

1. `~/Snowflake/Repos/aross-se-superpowers/plugins/snowflake-sizing/skills/snowflake-sizing/references/sizing-methodology.md`
2. `~/Snowflake/Repos/aross-se-superpowers/plugins/snowflake-sizing/skills/snowflake-sizing/references/html-spec.md`
3. `~/Snowflake/Repos/aross-se-superpowers/plugins/snowflake-sizing/skills/snowflake-sizing/references/research-protocol.md`

**Region name resolution (MANDATORY before pricing lookup)**

Before looking up `credit_rate`, resolve the user-supplied region string against the following alias table. Use the canonical key as the exact string to match in `credit_pricing.data[].region`.

| User input (examples) | Canonical key in `credit_pricing.data` |
|---|---|
| `North Europe`, `Azure North Europe`, `Ireland` | `North Europe (Ireland)` |
| `London`, `UK South`, `Azure London`, `UK` | `UK South (London)` |
| `AWS US East`, `Virginia`, `N. Virginia`, `us-east-1` | `AWS US East (Northern Virginia)` |
| `AWS US West`, `Oregon`, `us-west-2` | `AWS US West (Oregon)` |
| `Frankfurt`, `AWS Frankfurt`, `eu-central-1` | `AWS EU (Frankfurt)` |
| `Sydney`, `AWS Sydney`, `ap-southeast-2` | `AWS Asia Pacific (Sydney)` |
| `Singapore`, `AWS Singapore`, `ap-southeast-1` | `AWS Asia Pacific (Singapore)` |
| `Tokyo`, `AWS Tokyo`, `ap-northeast-1` | `AWS Asia Pacific (Tokyo)` |
| `Netherlands`, `West Europe`, `Azure Netherlands` | `West Europe (Netherlands)` |
| `Sweden Central` | `Sweden Central` |

If the supplied string matches no alias and no exact key, print:
```
⚠️  Region '<input>' not matched. Available keys: <list from credit_pricing.data>
Closest match found: '<key>' — continue? (or correct --region before proceeding)
```

After resolving, always print to the terminal before proceeding:
```
Region: <resolved key> | Credit rate: $X.XX/credit (<Edition>)
```

---

## Phase 1.5 — Preflight (BLOCKING)

Before ANY research, verify both research surfaces are available. This is a hard gate — if either check fails, abort with the exact setup instructions below. Do NOT continue with partial research.

**1. Glean MCP availability**

Run a no-op `mcp__glean_default__search` with `query: "*"` and `num_results: 1`.

If the call errors with `tool not found`, `MCP not configured`, or similar, ABORT with this exact message and stop:

```
⛔ Glean MCP is not configured. Run:
   cortex mcp add glean https://snowflake-be.glean.com/mcp/default --transport http
Then re-invoke this skill. Do NOT proceed with sizing — Glean evidence is required.
```

**2. SNOWHOUSE / Gong access**

Run via `snowflake_sql_execute` on the active connection:

```sql
SELECT COUNT(*) FROM GONG_SHARE.GONG_DATA_CLOUD.CALLS LIMIT 1;
```

If the call errors (connection not configured, table not accessible, permission denied), ABORT with this exact message and stop:

```
⛔ SNOWHOUSE Gong access unavailable. Set the active connection:
   cortex connections set snowhouse
Confirm `cortex connections list` shows snowhouse, then re-invoke.
```

Only proceed to Phase 2 after BOTH checks pass. The narrow EXCEPTIONS clause at the end of Phase 2 is the only legitimate way to bypass either check.

---

## Phase 2 — Research (MANDATORY CHECKPOINT)

CRITICAL: All three research operations (A, B, C) MUST execute. There is no "skip if dossier exists" branch. A pre-existing customer-context.md or pre-fetched dossier is useful but NOT a substitute for live Glean + Gong research.

**DO NOT PROCEED to Phase 3 until you have completed Phase 2.5 (research findings report).**

Read `skills/snowflake-sizing/references/research-protocol.md` before executing the matrix below — it contains the exact query strings, SQL templates, retry rules, and evidence file template.

**PARALLELISM RULE**: Run A, B1, B2, B3, and C1 simultaneously in a single parallel batch. Do NOT wait for any one call to complete before launching the others. C2 requires CONVERSATION_KEY values from C1 — launch C2 the moment C1 returns; do NOT wait for A/B to finish before starting C2.

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

**B. Glean research** (run all 3 searches in parallel — see `references/research-protocol.md` §1)

| Call | Tool                           | Query                                              | Filter             | num_results | Purpose               |
| ---- | ------------------------------ | -------------------------------------------------- | ------------------ | ----------- | --------------------- |
| B1   | `mcp__glean_default__search` | `"<customer> snowflake data platform workloads"` | _none_           | 8           | Account-level signals |
| B2   | `mcp__glean_default__search` | `"<customer>"`                                   | `app:gong`       | 8           | Recent customer calls |
| B3   | `mcp__glean_default__search` | `"<customer>"`                                   | `app:salescloud` | 5           | Opp size, ARR, stage  |

From Glean results extract: industry vertical, company scale, tech stack signals, stated pain points, growth indicators, opportunity stage and ARR.

**C. Gong transcript SQL** (use SNOWHOUSE via `snowflake_sql_execute` — see `references/research-protocol.md` §2)

C1 — Find calls (limit 3, verbatim SQL in research-protocol.md).

**MANDATORY retry-on-empty (research-protocol.md §3).** If C1 returns 0 rows, you MUST retry before recording "No Gong calls found":

- Try the first word only (e.g. `"GSMAi"` → `"GSMA"`).
- Try dropping parentheticals (e.g. `"GSMA Intelligence (GSMAi)"` → `"GSMA Intelligence"`).
- Try a known abbreviation or parent-account name (e.g. `"Light and Wonder"` → `"LnW"`; `"Marks and Spencer"` → `"M&S"`).
- Document each retry attempt verbatim in the evidence file.
- Only after **two** retry queries also return 0 rows may you record `No Gong calls found` and continue to Phase 2.5.

C2 — Load transcripts for the top 2 CONVERSATION_KEY values from C1 (verbatim SQL in research-protocol.md). Use `CONVERSATION_KEY` (hash), NOT `CONVERSATION_ID` (numeric). Use `AFFILIATION` to distinguish Internal (Snowflake) vs External (customer) speakers. If `TRANSCRIPT` is NULL, fall back to `CALL_SPOTLIGHT_BRIEF` and note the fallback in the evidence file.

Extract from transcripts: stated data volumes, tech stack, workload descriptions, pain points, growth plans, pricing signals, and verbatim quotes you will cite in Phase 3.

**Merge all sources.** Context file takes precedence. Glean fills account-level gaps. Gong transcripts provide verbatim customer statements. Note the source for every number you will use in Phase 3.

---

### Phase 2 EXCEPTIONS — when research may be reduced

Research is REQUIRED in all standard runs. Reduced research is permitted ONLY when:

- Flag `--skip-glean` is explicitly passed AND user confirms in chat.
- Flag `--skip-gong` is explicitly passed AND user confirms in chat.
- Customer name is `internal-test`, `demo`, or `POC-template`.

In any of these cases, write that fact verbatim to the evidence file under `## Research scope reduction` before proceeding to Phase 2.5.

---

## Phase 2.5 — Report Research Findings (BLOCKING)

DO NOT PROCEED to Phase 3 until you have written the research evidence file AND reported a short summary to the user.

**1. Write `temp/<customer-slug>-research-evidence.md`** using the template in `references/research-protocol.md` §4. The slug matches the slug used for the sizing HTML output. Required sections:

- Glean — account signals (B1) with title, datasource, snippet, URL per hit
- Glean — Gong-indexed calls (B2)
- Glean — Salesforce (B3)
- Gong — call inventory (C1) with retry log
- Gong — transcript verbatim (C2) — for each of the top 2 calls, list every turn that mentions data volume, user count, workload type, operating hours, unstructured/AI use, migration phase, or pricing/budget signals, with `[turn N] <speaker> (<affiliation>): "<verbatim quote>"`
- Sizing-impacting findings — numbered list mapping each finding to the workload/serverless/AI item it changes

**2. Print this summary to the terminal** (≤ 15 lines) before continuing:

```
📋 Research complete
   Glean hits: B1=N, B2=N, B3=N
   Gong calls reviewed: <call1 title> (<call_date>), <call2 title> (<call_date>)
   Top 3 sizing-impacting findings:
   1. ...
   2. ...
   3. ...
   Evidence file: temp/<slug>-research-evidence.md

Proceeding to Phase 3 (build sizing spec).
```

---

## Phase 3 — Build the sizing spec

### § Content Hygiene (MANDATORY)

The following MUST NEVER appear in any customer-facing field (`label`, `justification`, `note`, `description` — any field that renders as visible text in the HTML):

- **Personal names** from Gong transcripts or internal contacts (first or last names of any individuals)
- **Internal file names** (`sizing-methodology.md`, `customer-context.md`, `research-evidence.md`, `html-spec.md`, `research-protocol.md`, or any other internal artefact)
- **Citation prefixes in visible text**: `SOURCED:`, `ASSUMPTION:`, `REQUIRES_CONFIRMATION:`
- **References to internal tools, systems, or methodology artefacts**

Citation labels (`SOURCED:`, `ASSUMPTION:`) are ONLY permitted inside the JSON `source` metadata field (used as JS flags, never rendered). Justification text must be plain customer-facing prose: *"Based on stated 50 TB daily ingestion volume"* — never *"SOURCED: Gong turn 14 — Jay: …"*.

### § AI Feature Defaults (MANDATORY)

1. **Document AI is removed.** Do NOT include `document_ai`, `ai_parse_document_layout`, or `ai_parse_document_ocr` in any spec. These features are superseded by `ai_extract`. For document processing workloads, use `ai_extract` with appropriate token volumes (default 70M tokens/month when document extraction is a primary use case).

2. **Default model for `cortex_complete`**: Always specify `claude-sonnet-4-6` (input: 1.65 AI cr/M, output: 8.25 AI cr/M). Do not use unlisted, older, or smaller models as defaults.

---

Using `sizing-methodology.md` as your rulebook, reason through EVERY consumption category.

**For each workload category, decide:**

1. Is this relevant to this customer? (enabled: true / false)
2. If enabled: what are the sizing parameters? (SIZE from evidence, not guessing)
3. Label every number: SOURCED (cite it) or ASSUMPTION (explain it)
4. Add anything unclear to `confirm_required` with quantified impact

**SOURCED label format (mandatory).** Every SOURCED tag must cite a concrete artifact:

| Source       | Citation format                                                                         |
| ------------ | --------------------------------------------------------------------------------------- |
| Context file | `SOURCED: customer-context.md L<line>`                                                |
| Glean doc    | `SOURCED: Glean — <title> (<datasource>) — <url>`                                   |
| Gong         | `SOURCED: Gong <conversation_key[:10]> turn <N> — <speaker>: "<≤15 word verbatim>"` |

ASSUMPTION labels are still allowed but ONLY when all three of A (context file), B (Glean), C (Gong) are silent on that data point. Every ASSUMPTION must also appear in `confirm_required` with quantified impact.

**Work through categories in this order:**

### Workloads (SIZING_SPEC.workloads array)

> **CRITICAL: The top-level array key MUST be `workloads`. Do NOT use `warehouses`. The JS engine reads `SIZING_SPEC.workloads` — any other key renders as $0.**

**Required shape for every workload row:**

```json
{
  "id": "wh-elt",
  "label": "ELT / Transformation",
  "size": "S",
  "hours_per_day": 3.0,
  "days_per_month": 22,
  "clusters_min": 1,
  "clusters_max": 1,
  "auto_suspend_seconds": 10,
  "dev_start_month": 2,
  "go_live_month": 9,
  "ramp_curve": "linear",
  "justification": "...",
  "source": "..."
}
```

Use `clusters_min` and `clusters_max` (both required). Do NOT use `avg_clusters` — that field is not read by the JS engine.

Identify all distinct workload patterns and create one workload entry per pattern:

- Data Ingestion (if batch/ELT loading)
- Transformation / ELT (if transformation occurs in Snowflake)
- BI / Analytics (one per BI tool or user group if different patterns)
- Ad-hoc / Data Science (if mentioned)
- Development (always include: 1 × XS, 4 hrs/day, 22 days)
- Any other specific workloads mentioned

Apply warehouse sizing rules from `sizing-methodology.md`. Apply MCW when concurrency rules trigger.

**Per-workload ramp fields (REQUIRED on every workload row).** Each warehouse, serverless feature, AI feature, SPCS instance, OpenFlow instance, and collaboration account must carry:

| Field | Default | Source |
|---|---|---|
| `dev_start_month` | 0 | `meta.default_dev_start_month` (override per workload if context indicates a later kickoff) |
| `go_live_month` | 3 | `meta.default_go_live_month` (shorten if customer states a faster deadline; lengthen for complex migrations) |
| `ramp_curve` | from `pricing.ramp_curves.recommended_by_workload_type[<workload kind>]` | See sizing-methodology.md "Choosing a curve" |

When a workload is genuinely steady-state from month 1 (e.g., an ongoing production system being lifted), set `dev_start_month=1`, `go_live_month=1`, `ramp_curve="manual"` and the per-month factor stays at 1.0 throughout (the JS engine treats `manual` with `dev_start==go_live==1` as full ramp).

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

**Field name reference (MANDATORY — wrong names silently compute $0):**

| Feature | Correct field path | Wrong (never use) |
|---|---|---|
| Cortex Complete tokens | `ai_cortex.cortex_complete.monthly_input_tokens_M` + `monthly_output_tokens_M` (values in millions) | `monthly_tokens_input` |
| Cortex Search index | `ai_cortex.cortex_search.indexed_data_gb` | `indexed_gb` |
| AI Extract | `ai_cortex.cortex_functions.ai_extract.tokens_M_monthly` | `ai_cortex.ai_extract` (top-level) |
| Serverless compute features | `compute_hours_monthly` on each serverless item | `monthly_credits` |
| Storage volume | `storage.standard.raw_tb_year1` | `storage.raw_tb` |
| OpenFlow MERGE warehouse | `warehouse_size: "X-Small"` (full name) | `"XS"` (abbreviation) |

`ai_cortex.cortex_functions` is a **required sub-object** even when all AI_ SQL functions are disabled — omitting it causes the AI section to error silently.

**Cortex Code shape:** `ai_cortex.cortex_code = { cli, snowsight, desktop }`, each entry `{ enabled, developers, queries_per_dev_per_day, avg_tokens_per_query }`. The three surfaces (CLI / Snowsight / Cortex Code Desktop) bill at the same Table 6(e) rate but reflect different per-developer usage patterns. Enable each surface independently. Defaults:

| Surface | Typical queries/dev/day | Typical tokens/query | Notes |
|---|---|---|---|
| CLI | 5 - 20 | 800 - 1,500 | Power users in terminal; lightweight prompts. |
| Snowsight | 10 - 40 | 1,000 - 1,800 | SQL assist inside worksheets; medium usage. |
| Cortex Code Desktop | 30 - 80 | 1,200 - 2,500 | IDE assistant with inline suggestions + chat; heaviest usage. |

The legacy single-object shape (`cortex_code.{enabled, developers, queries_per_dev_per_day, avg_tokens_per_query}`) is auto-normalized by the template (legacy values land on `cli`), but new specs MUST emit the three-surface form.

### SPCS, Openflow, Postgres

Enable only if explicitly mentioned. For Openflow, always ask about source database server count.

**SPCS shape:** `spcs.instances[]`, each entry `{ id, label, generation, instance_type, count, hours_monthly }`. Set `spcs.enabled=true` whenever the array is non-empty.

**OpenFlow shape:** `openflow.instances[]`, each entry:
```json
{
  "id": "of-1",
  "label": "Postgres CDC",
  "connector_type": "CDC",
  "deployment": "SPCS",
  "runtime_size": "Medium",
  "runtime_nodes": 3,
  "byoc_region": null,
  "monthly_data_gb": 90,
  "warehouse_size": "X-Small",
  "warehouse_hours_monthly": 180,
  "hours_monthly": 730
}
```

Fields:
- `connector_type`: `"CDC"` / `"Streaming"` / `"Files"` / `"SaaS"` / `"Oracle CDC"` — display label and determines applicable cost components
- `deployment`: `"SPCS"` (Snowflake-managed, credit-based) or `"BYOC"` (AWS-hosted, dual billing)
- `runtime_size`: `"Small"` (1 vCPU, light), `"Medium"` (4 vCPU, standard), `"Large"` (8 vCPU, high-volume)
- `runtime_nodes`: number of runtime nodes required. For CDC: 1 per distinct JDBC source server; if total tables > 600, use `max(source_servers, ceil(total_tables/600))`. For Streaming/Files: throughput-driven (see sizing-methodology.md)
- `byoc_region`: AWS region code, required when `deployment === "BYOC"`. One of: `"us-east-1"`, `"us-west-2"`, `"eu-west-1"`, `"eu-west-2"`, `"eu-central-1"`, `"ap-southeast-1"`, `"ap-northeast-1"`
- `monthly_data_gb`: estimated GB/month through Snowpipe Streaming. For CDC: `connections × events_per_day × avg_row_bytes / 1e9 × 30`. For Streaming: `MB/s × active_hours × 3600 × 30 / 1000`
- `warehouse_size` + `warehouse_hours_monthly`: MERGE warehouse for CDC/Oracle CDC workloads. Often 60–70% of total CDC cost — always confirm if customer has an existing warehouse that can be reused. Set `warehouse_size: null` if no dedicated warehouse.

Create one instance per distinct connector deployment (e.g. one for "Salesforce CDC", one for "Postgres replication"). Set `openflow.enabled=true` whenever the array is non-empty.

### Collaboration: Reader / Managed accounts

`collaboration.accounts[]`, each entry `{ id, type, label, warehouse_size, hours_per_day, days_per_month }`. `type` is either `"reader"` or `"managed"` and is display-only (same compute cost model). Create one entry per distinct account the customer plans to provision. Native Apps and Marketplace remain on `collaboration.native_apps` / `collaboration.marketplace` as subscription objects.

### Replication / DR / Migration block

**Activation trigger.** Add a `replication` object to the SIZING_SPEC if any of A / B / C / context-file mentions: BCDR, DR, disaster recovery, failover, replication, secondary region, data sharing provider, multi-region, migration to Snowflake. Also activate when `--mode replication` or `--mode dr` is on the command line.

When triggered, run the D1 / D2 / D3 queries documented in `references/research-protocol.md` §7 and populate:

```json
"replication": {
  "enabled": true,
  "source_region": "AWS-Asia Pacific (Sydney)",
  "target_region": "AWS-US East1 (N. Virginia)",
  "initial_TB": 100,
  "monthly_change_TB": 8,
  "replication_frequency": "ONE_HOUR",
  "storage_growth_pct": 0.15,
  "yoy_pct": 0.10,
  "compute_credits_per_TB": 4,
  "replica_storage_per_tb_per_month": 23.0,
  "ramp_curve": "fastest",
  "dev_start_month": 1,
  "go_live_month": 2,
  "notes": "SOURCED: D2 SYSTEM$ESTIMATE_REPLICATION_COST ONE_HOUR_TB=8.0"
}
```

If the trigger does not fire, omit the `replication` key entirely (the HTML template only renders the section when `__REPLICATION_JSON__ != null`).

Region names MUST match keys in `pricing.replication.egress_matrix` exactly (e.g. `"AWS-Asia Pacific (Sydney)"` — including capitalization and parenthetical). Do NOT normalize to `"AWS Sydney"` or other shortenings.

### Storage

Use stated data volumes from context. Apply compression defaults from `sizing-methodology.md`. Set time_travel_days=1 (default) and churn_rate=10% unless stated otherwise.

### Growth rate

Set `meta.annual_growth_rate` from context (default 0.20 = 20%/yr). This applies to every workload from year 2 onwards. Year 1 ramp is handled per-workload by the Birdbox curve model — there is no `growth_rates` array anymore.

If different workloads have different growth rates, override per-workload via `growth_rate_override` on the row.

### Compile spec

Produce the complete JSON spec. Include:

- All enabled workloads with SOURCED/ASSUMPTION labels
- All disabled features set to enabled:false
- `assumptions` array (20+ items expected for a thorough estimate)
- `confirm_required` array with quantified impact statements

---

## Phase 4 — Apply multi-year growth (per-workload monthly model)

Switch from the legacy `growth_rates[]` array to a per-month / per-workload model that integrates Birdbox ramp curves with the annual growth rate.

### Per-month factor

For each workload row and each absolute month `m` (1-indexed across the full contract horizon):

```
relative_month = ((m - 1) MOD 12) + 1                  # month within the year, 1..12
year_index     = ((m - 1) DIV 12)                      # 0 = year 1, 1 = year 2, ...

ramp_factor    = clamp(((m_in_y1 - dev_start + 1) / (go_live - dev_start + 1)) ^ exponent, 0, 1)
                 where m_in_y1 = m for year 1; for year 2+, ramp_factor = 1.0

growth_factor  = (1 + annual_growth_rate) ^ year_index   # year 1 = 1.0, year 2 = 1+g, ...

month_factor   = ramp_factor × growth_factor
```

`exponent` comes from `pricing.ramp_curves.exponents[ramp_curve]`.

### Year totals

```
warehouse_credits_year_y    = Σ_workloads (cr_per_hr(size) × hrs/day × days/mo × avg_clusters) × Σ_months_in_y (month_factor)
serverless_credits_year_y   = Σ_workloads (monthly_serverless_credits × Σ_months_in_y month_factor)
ai_credits_year_y           = Σ_workloads (monthly_ai_credits × Σ_months_in_y month_factor)
storage_cost_year_y         = active_TB(y) × storage_rate × 12     (already grows via storage growth model)
spcs_cost_year_y            = Σ_instances  (instance_cr/hr × hrs/mo × count × credit_rate × Σ_months_in_y month_factor)
openflow_cost_year_y        = per-instance sum × Σ_months_in_y month_factor, where per-instance:
  SPCS runtimes:  ceil(nodes/3) × SPCS_rate[size] × 730 × cr   (Small=0.11, Medium=0.41, Large=0.83 cr/hr)
  SPCS ctrl pool: 0.11 × 730 × cr  (once per deployment with any SPCS instance)
  BYOC fixed:     region_fixed × 1  (no ramp — always-on; once per deployment; $463–575/mo by region)
  BYOC EC2+EBS:   ceil(nodes/3) × (ec2_hourly[region][size] × 730 + 200 × ebs_gb[region])
  BYOC credits:   nodes × vcpu[size] × 730 × 0.0225 × cr   (Small=1, Medium=4, Large=8 vCPU)
  Snowpipe:       monthly_data_gb × 0.0037 × cr
  Warehouse MERGE: wh_credits[wh_size] × wh_hours_monthly × cr  (CDC only; X-Small=1,S=2,M=4,L=8 cr/hr)
transfer + privatelink      = tb × rate × 12
replication_cost_year_y     = (active_TB(y) + monthly_change_TB(y) × 12) × cr_per_TB × credit_rate
                            + monthly_change_TB(y) × 12 × egress_matrix[source][target]
                            + avg_TB(y) × replica_storage_per_TB_per_month × 12
                              (only if SIZING_SPEC.replication is present)
```

The legacy `× ramp[y]` shorthand is replaced by `× Σ_months_in_y month_factor` — i.e., the sum of 12 per-month factors instead of one annualized number. This makes each workload's ramp shape visible in the year-1 total.

Print a summary table to the terminal (for SE reference):

```
Year | Credits | Compute $ | Serverless $ | AI $ | Storage $ | Replication $ | Total $
  1  |  XX,XXX | $XX,XXX   | $X,XXX       | $X   | $X,XXX    | $X,XXX        | $XX,XXX
  2  |  XX,XXX | $XX,XXX   | $X,XXX       | $X   | $X,XXX    | $X,XXX        | $XX,XXX
  3  |  XX,XXX | $XX,XXX   | $X,XXX       | $X   | $X,XXX    | $X,XXX        | $XX,XXX
TCV: $XXX,XXX
```

If `replication` is not present in SIZING_SPEC, omit the Replication column.

---

## Phase 5 — Generate sizing spec and interactive HTML

The `.json` spec is the primary artifact and is written **first**. The HTML is then derived from it.

**Output paths** (both go to the git-tracked `sizings/` directory):

```
Spec:  sizings/<customer-slug>-<N>year-sizing-v<version_number>-<YYYY-MM-DD>.json
HTML:  sizings/<customer-slug>-<N>year-sizing-v<version_number>-<YYYY-MM-DD>.html
```

Where:
- `customer-slug` = customer name lowercased, spaces replaced with hyphens, special chars stripped
- `version_number` = `SIZING_SPEC.meta.version_number` (set to `1` in Phase 1)
- `YYYY-MM-DD` = today's date

**Steps:**

1. **Write the spec file first.** Serialize the complete `SIZING_SPEC` object as pretty-printed JSON and write to `sizings/<customer-slug>-<N>year-sizing-v1-<date>.json`. This step must complete before touching the template — if HTML generation fails, the spec is already saved.

2. Read `skills/snowflake-sizing/references/_template.html`

3. Read `assets/branding/_brand_fonts.css`

4. Substitute every token below — replace the exact token string with its value:

| Token | Value |
|---|---|
| `__BRAND_FONTS_CSS__` | full contents of `assets/branding/_brand_fonts.css` |
| `__PRICING_DATA__` | full contents of `assets/snowflake_pricing_master.json` (now includes `ramp_curves` and `replication.egress_matrix`) |
| `__SIZING_SPEC__` | complete SIZING_SPEC JSON object (from Phase 4) — includes per-workload `dev_start_month`/`go_live_month`/`ramp_curve` and optional `replication` block |
| `__CUSTOMER__` | customer display name |
| `__EDITION__` | Snowflake edition (`Enterprise` / `Business Critical`) |
| `__CLOUD__` | cloud provider (`AWS` / `Azure` / `GCP`) |
| `__REGION__` | deployment region (e.g. `us-east-1`) |
| `__YEARS__` | contract length as integer |
| `__CREDIT_RATE__` | per-credit dollar rate |
| `__DATE__` | today's date (YYYY-MM-DD) |
| `__PDF_VERSION__` | version string from SIZING_SPEC metadata |

5. Write the result to `sizings/<customer-slug>-<N>year-sizing-v1-<date>.html`

Do **not** modify any other part of the template. The template already contains official Snowflake branding (wordmark, fonts, favicon, crystal mark footer) — do not regenerate or alter those sections.

**Quality check before reporting success (BLOCKING):**

1. Confirm no `__TOKEN__` strings remain in the HTML output (all 11 substituted).
2. Verify the per-month factor model is wired through (not the legacy `growth_rates` array). `grep growth_rates sizings/<slug>-<N>year-sizing-v1-<date>.html` should return zero hits.
3. Verify `credit_rate` in spec matches the region in the header.
4. If `SIZING_SPEC.replication` was populated, confirm both `source_region` and `target_region` are valid keys in `pricing.replication.egress_matrix` (`source_region` exists, and `target_region` exists in `egress_matrix[source_region]`).
5. **Spec structure gate (BLOCKING).** Run:

   ```bash
   python3 assets/spec-validate.py sizings/<slug>-<N>year-sizing-v1-<date>.json
   ```

   If exit code is non-zero, fix the field-name errors flagged by the script before continuing. The most common failures: `warehouses` → `workloads`, `avg_clusters` → `clusters_min`/`clusters_max`, `storage.raw_tb` → `storage.standard.raw_tb_year1`.

   The canonical JSON Schema for the full SIZING_SPEC (all fields, types, and enums) is at `${CORTEX_PLUGIN_ROOT}/framework/sizing_spec_schema.json`. The `hooks/validate-sizing-json.py` PostToolUse hook enforces the same rules automatically on every `Write` to `sizings/*.json`.

6. **HTML render check gate (BLOCKING).** Run:

   ```bash
   python3 assets/html-render-check.py sizings/<slug>-<N>year-sizing-v1-<date>.html
   ```

   If exit code is non-zero, the script prints the $0 diagnosis (missing `workloads`, zero `credit_rate`, all ramps outside year 1, etc.). Fix the root cause in the JSON spec and re-run Phase 5 steps 4–6 until the gate passes. A passing gate prints the computed Year 1 / Year 2 / Year 3 / TCV summary — record these numbers in the Phase 6 output.

7. **Em-dash gate.** Run:

   ```bash
   python3 assets/emdash-check.py sizings/<slug>-<N>year-sizing-v1-<date>.html temp/<slug>-research-evidence.md
   ```

   If exit code is non-zero, the script prints `file:line:col` for each U+2014 occurrence. Replace each em-dash with ` - ` (space hyphen space) in the source artifact and re-run the gate until it exits 0. Do NOT proceed to Phase 6 until the gate passes.

8. **Content hygiene gate.** Run:

   ```bash
   python3 -c "
   import sys
   with open('sizings/<slug>-<N>year-sizing-v1-<date>.html') as f:
       html = f.read()
   patterns = ['SOURCED:', 'ASSUMPTION:', 'sizing-methodology.md',
               'customer-context.md', 'research-evidence.md', 'html-spec.md',
               'research-protocol.md']
   fails = [p for p in patterns if p in html]
   if fails:
       print('CONTENT HYGIENE FAIL:', fails)
       sys.exit(1)
   print('CONTENT HYGIENE PASS')
   "
   ```

   If exit non-zero, locate the offending fields in the SIZING_SPEC, rewrite their visible text as plain customer-facing prose (no citation prefixes, no file names, no personal names), and re-run Phase 5 steps 4–8 until all gates pass.

---

## Phase 6 — Output summary

Print to terminal:

```
✅ Generated:
   sizings/[slug]-[N]year-sizing-v1-[date].html   (interactive sizing proposal)
   sizings/[slug]-[N]year-sizing-v1-[date].json   (portable sizing spec)
   temp/[slug]-research-evidence.md               (Glean + Gong audit trail)

🛡  spec-validate: PASS
🛡  html-render-check: PASS
🛡  emdash check: PASS
🛡  content hygiene: PASS

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

⚠️  Requires Confirmation:
  • [confirm_required item 1]
  • [confirm_required item 2]
  ...

Open in browser: open sizings/[slug]-[N]year-sizing-v1-[date].html
Print / Save as PDF: click the "Print / Save as PDF" button in the top-right of the proposal,
or in the SE's terminal: open sizings/[slug]-[N]year-sizing-v1-[date].html (then Cmd-P → "Save as PDF").
Tip: Chrome adds a date/title header and file:// URL footer by default — expand "More settings"
in the print dialog and uncheck "Headers and footers" for a clean PDF. (Hover the ⓘ next to the
Print button in the proposal for the same hint.)
Save versioned snapshots: click "Save Version" (next to Print) to download a self-contained HTML
with the SE's current edits embedded. Filename is auto-generated as
<slug>-<years>year-sizing-v<N>-<YYYY-MM-DD>.html and the version number auto-increments each save.
Export portable spec: click "Export JSON" (next to Save Version) to download the current
SIZING_SPEC as a .json file — useful for round-tripping browser edits back to disk, or passing
to future export skills (/export-pptx, /export-xlsx) to generate other format deliverables.
```
