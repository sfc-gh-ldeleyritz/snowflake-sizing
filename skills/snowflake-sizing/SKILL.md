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

Read pricing data (use Read tool on `assets/snowflake_pricing_master.json`).

Derive from pricing data:

- `credit_rate` — from `credit_pricing.data` matching cloud + region + edition
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
  "ramp_curve": "linear",
  "pdf_version": "2026-05-12",
  "version_number": 1
}
```

Read reference documents in parallel:

1. Read `skills/snowflake-sizing/references/sizing-methodology.md`
2. Read `skills/snowflake-sizing/references/html-spec.md`
3. Read `skills/snowflake-sizing/references/research-protocol.md`

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

Run the full research matrix in parallel:

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

**OpenFlow shape:** `openflow.instances[]`, each entry `{ id, label, deployment, source_connections, vcpu_per_connection, hours_monthly }`. Create one instance per distinct connector (e.g. one for "Salesforce CDC", one for "Postgres logical replication"). Set `openflow.enabled=true` whenever the array is non-empty. The legacy single-object shape (`source_connections` / `vcpu_per_connection` / `hours_monthly` directly on `openflow`) is auto-normalized by the template — but new specs MUST emit the array form.

### Collaboration: Reader / Managed accounts

`collaboration.accounts[]`, each entry `{ id, type, label, warehouse_size, hours_per_day, days_per_month }`. `type` is either `"reader"` or `"managed"` and is display-only (same compute cost model). Create one entry per distinct account the customer plans to provision. Native Apps and Marketplace remain on `collaboration.native_apps` / `collaboration.marketplace` as subscription objects.

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

| Component              | Formula                                                                |
| ---------------------- | ---------------------------------------------------------------------- |
| Warehouse credits/yr   | Σ(size_cr/hr × hrs/day × days/mo × avg_clusters) × 12 × ramp[y]  |
| Serverless credits/yr  | monthly_serverless_credits × 12 × ramp[y]                            |
| AI credits/yr          | monthly_ai_credits × 12 × ramp[y]                                    |
| Storage cost/yr        | storage_tb(y) × storage_rate × 12                                    |
| SPCS cost/yr           | Σ(instance_cr/hr × hrs/mo × count) × credit_rate × 12 × ramp[y]  |
| Openflow cost/yr       | connections × vcpu × hours × 0.0225 × credit_rate × 12 × ramp[y] |
| Transfer + Privatelink | tb × rate × 12                                                       |

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

Read the committed template and substitute all placeholder tokens to produce the output file:

```
Input:   skills/snowflake-sizing/references/_template.html
Output:  temp/<customer-slug>-<N>year-sizing.html
```

Where `customer-slug` = customer name lowercased, spaces replaced with hyphens.

**Steps:**

1. Read `skills/snowflake-sizing/references/_template.html`
2. Read `assets/branding/_brand_fonts.css`
3. Substitute every token below — replace the exact token string with its value:

| Token | Value |
|---|---|
| `__BRAND_FONTS_CSS__` | full contents of `assets/branding/_brand_fonts.css` |
| `__PRICING_DATA__` | JSON object of credit/storage rates (from Phase 2) |
| `__SIZING_SPEC__` | complete SIZING_SPEC JSON object (from Phase 4) |
| `__CUSTOMER__` | customer display name |
| `__EDITION__` | Snowflake edition (`Enterprise` / `Business Critical`) |
| `__CLOUD__` | cloud provider (`AWS` / `Azure` / `GCP`) |
| `__REGION__` | deployment region (e.g. `us-east-1`) |
| `__YEARS__` | contract length as integer |
| `__CREDIT_RATE__` | per-credit dollar rate |
| `__DATE__` | today's date (YYYY-MM-DD) |
| `__PDF_VERSION__` | version string from SIZING_SPEC metadata |

4. Write the result to `temp/<customer-slug>-<N>year-sizing.html`

Do **not** modify any other part of the template. The template already contains official Snowflake branding (wordmark, fonts, favicon, crystal mark footer) — do not regenerate or alter those sections.

**Quality check before reporting success (BLOCKING):**

1. Confirm no `__TOKEN__` strings remain in the output (all 11 substituted).
2. Verify `growth_rates` array length = `contract_years`.
3. Verify `credit_rate` in spec matches the region in the header.
4. **Em-dash gate.** Run:

   ```bash
   python3 assets/emdash-check.py temp/<slug>-<N>year-sizing.html temp/<slug>-research-evidence.md
   ```

   If exit code is non-zero, the script prints `file:line:col` for each U+2014 occurrence. Replace each em-dash with ` - ` (space hyphen space) in the source artifact and re-run the gate until it exits 0. Do NOT proceed to Phase 6 until the gate passes.

---

## Phase 6 — Output summary

Print to terminal:

```
✅ Generated:
   temp/[filename].html              (interactive sizing proposal)
   temp/[slug]-research-evidence.md  (Glean + Gong audit trail)

🛡  emdash check: PASS

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
Print / Save as PDF: click the "Print / Save as PDF" button in the top-right of the proposal,
or in the SE's terminal: open temp/[filename] (then Cmd-P → "Save as PDF").
Tip: Chrome adds a date/title header and file:// URL footer by default — expand "More settings"
in the print dialog and uncheck "Headers and footers" for a clean PDF. (Hover the ⓘ next to the
Print button in the proposal for the same hint.)
Save versioned snapshots: click "Save Version" (next to Print) to download a self-contained HTML
with the SE's current edits embedded. Filename is auto-generated as
<slug>-<years>year-sizing-v<N>-<YYYY-MM-DD>.html and the version number auto-increments each save.
```
