# Research Protocol — snowflake-sizing

This is the operational reference for Phase 2 of `SKILL.md`. Read it once at the start of Phase 2 and execute the matrix verbatim. Phase 2 is a **MANDATORY CHECKPOINT** — there is no skip-if-dossier-exists branch.

---

## 1. Glean MCP queries (B1, B2, B3)

**Executor: main agent** (Phase 1.7 of `SKILL.md`). Glean MCP OAuth is
session-bound and does not propagate to subagents, so B1/B2/B3 must run
in the main-agent context. The research-coordinator does not call Glean
directly - it receives a `pre_fetched_glean` blob from the parent and
transforms it into the Glean section of the evidence file using the
markdown template at the bottom of this section.

Tool: `mcp__glean__search` (the host exposes the Glean MCP server registered as `glean`; the legacy `mcp__glean_default__search` alias is no longer used).

| Call | `query` | `app` filter | `num_results` | Purpose |
|------|---------|--------------|---------------|---------|
| B1 | `"<customer> snowflake data platform workloads"` | _none_ | 8 | Account-level signals across Drive, Slack, Confluence, etc. |
| B2 | `"<customer>"` | `gong` | 8 | Recent customer calls indexed by Glean |
| B3 | `"<customer>"` | `salescloud` | 5 | Salesforce: opp size, ARR, stage, close date |

Substitute `<customer>` with the parsed customer name. If the customer name has a parenthetical short form (e.g. `"GSMA Intelligence (GSMAi)"`), run B1 with the full name and B2/B3 with the short form.

For each Glean result, record: title, datasource, snippet (first 200 chars), URL, date.

### Glean evidence section template (emitted by research-coordinator)

```markdown
## Glean evidence (B1 / B2 / B3)

### B1 - Account-level
Query: "<verbatim B1.query>"
Hits: <B1.hits>

| # | Title | Datasource | Date | URL |
|---|---|---|---|---|
| 1 | ... | drive | YYYY-MM-DD | ... |

Snippet highlights:
- <title>: <snippet first ~200 chars>
- ...

### B2 - Gong-indexed
Query: "<verbatim B2.query>" (app=gong)
Hits: <B2.hits>

[same table + snippet structure]

### B3 - Salesforce
Query: "<verbatim B3.query>" (app=salescloud)
Hits: <B3.hits>

[same table + snippet structure]
```

---

## 2. Gong SQL (C1, C2)

Connection: **SNOWHOUSE** via `snowflake_sql_execute`.

### C1 — Find calls

```sql
SELECT c.CONVERSATION_KEY,
       c.CONVERSATION_ID,
       c.TITLE,
       c.PLANNED_START_DATETIME::DATE AS call_date,
       c.CALL_SPOTLIGHT_BRIEF,
       c.CALL_URL,
       EXISTS (
           SELECT 1
           FROM GONG_SHARE.GONG_DATA_CLOUD.CALL_TRANSCRIPTS sub
           WHERE sub.CONVERSATION_KEY = c.CONVERSATION_KEY
             AND sub.TRANSCRIPT IS NOT NULL
       ) AS has_transcript
FROM GONG_SHARE.GONG_DATA_CLOUD.CALLS c
WHERE LOWER(c.TITLE) LIKE LOWER('%<customer_substring>%')
  AND c.PLANNED_START_DATETIME <= CURRENT_TIMESTAMP()
ORDER BY c.PLANNED_START_DATETIME DESC
LIMIT 5;
```

Use the customer name (or first word) as `<customer_substring>`. The
`PLANNED_START_DATETIME <= CURRENT_TIMESTAMP()` clause filters out
not-yet-happened scheduled calls (which have no transcript and waste a C2
slot). Pick the top 2 calls **where `has_transcript = TRUE`** for C2; if
fewer than 2 such calls exist, run C2 against whatever is available and
record the rest with the CALL_SPOTLIGHT_BRIEF fallback noted below.

### C2 — Load transcripts (top 2 calls from C1 with `has_transcript = TRUE`)

```sql
WITH turns AS (
    SELECT ct.CONVERSATION_KEY,
           t.INDEX                          AS turn_index,
           t.value:topic::STRING            AS topic,
           t.value:speakerId::STRING        AS speaker_id,
           t.value:sentences                AS sentences
    FROM GONG_SHARE.GONG_DATA_CLOUD.CALL_TRANSCRIPTS ct,
         LATERAL FLATTEN(input => ct.TRANSCRIPT) t
    WHERE ct.CONVERSATION_KEY IN ('<key_1>', '<key_2>')
      AND ct.TRANSCRIPT IS NOT NULL
)
SELECT p.NAME            AS speaker,
       p.AFFILIATION,
       turns.topic,
       turns.turn_index,
       turns.sentences
FROM turns
JOIN GONG_SHARE.GONG_DATA_CLOUD.CONVERSATION_PARTICIPANTS p
    ON  p.CONVERSATION_KEY = turns.CONVERSATION_KEY
    AND p.SPEAKER_ID::STRING = turns.speaker_id
ORDER BY turns.CONVERSATION_KEY, turns.turn_index;
```

Critical join rules:
- Use `CONVERSATION_KEY` (hash). Do NOT use `CONVERSATION_ID` (numeric) for joins.
- The `LATERAL FLATTEN` lives inside a CTE and uses the implicit
  comma-join form (no `ON TRUE` predicate). Snowflake rejects
  `JOIN LATERAL FLATTEN(...) ON TRUE` together with a downstream join
  predicate (`Unsupported feature 'lateral table function called with
  OUTER JOIN syntax or a join predicate (ON clause)'`); the CTE form
  sidesteps that limitation cleanly.
- **NULL fallback**: If C1 reports `has_transcript = FALSE` for a chosen
  call, retrieve that call's `CALL_SPOTLIGHT_BRIEF` from the C1 result set
  and record `[FALLBACK: CALL_SPOTLIGHT_BRIEF — TRANSCRIPT NULL]` in the
  evidence file for that call.
- Distinguish customer vs Snowflake speakers using `p.AFFILIATION` (`External` vs `Internal`).

---

## 3. Retry-on-empty rules (MANDATORY for C1)

If C1 returns 0 rows, you **must** retry before recording "No Gong calls found". Walk this table top-down and stop at the first hit.

| Pattern | Example transformation |
|---------|------------------------|
| First word only | `"GSMAi"` → `"GSMA"` |
| Drop parenthetical | `"GSMA Intelligence (GSMAi)"` → `"GSMA Intelligence"` |
| Strip suffix tokens | `"Light and Wonder Inc"` → `"Light and Wonder"` |
| Known abbreviation | `"Light and Wonder"` → `"LnW"`; `"Marks and Spencer"` → `"M&S"`; `"GSMA Intelligence"` → `"GSMAi"` |
| Parent-account fallback | `"Cap1 Operational Intelligence"` → `"Capital One"` |
| Domain-derived stem | `"acme.com"` → `"acme"` |

You may execute up to **two** retry queries. Document each attempted substring in the evidence file (Section "Gong — call inventory (C1) — retries"). Only after two empty results may you record `No Gong calls found` and continue to Phase 2.5.

---

## 4. Evidence file template

Write to `temp/<customer-slug>-research-evidence.md`. The customer slug is the customer name lowercased with spaces → hyphens and non-alphanumerics removed.

```markdown
# Research Evidence — <Customer> sizing v<N>

Generated: <YYYY-MM-DD>
Sizing artifact: sizings/<customer-slug>-<N>year-sizing-v1-<YYYY-MM-DD>.html

## Glean — account signals (B1)
Query: "<customer> snowflake data platform workloads"  num_results=8  hits=<N>
- [<datasource>] <title> — <snippet 200 chars> — <url>
- ...

## Glean — Gong-indexed calls (B2)
Query: "<customer>" app=gong  num_results=8  hits=<N>
- [<datasource>] <title> — <snippet> — <url>
- ...

## Glean — Salesforce (B3)
Query: "<customer>" app=salescloud  num_results=5  hits=<N>
- [<datasource>] <title> — ARR/Stage/CloseDate signals — <url>
- ...

## Gong — call inventory (C1)
Substring tried: `<customer>`  rows=<N>
| call_date | title | conversation_key (first 10) | spotlight_brief (first 200 chars) |
|-----------|-------|------------------------------|------------------------------------|
| ... |

### Gong — C1 retries (only if first attempt empty)
- Attempt 2: substring `<retry>` → rows=<N>
- Attempt 3: substring `<retry>` → rows=<N>

## Gong — transcript verbatim (C2)
For each of the top 2 calls:

### <title> (<call_date>, <conversation_key prefix 10>)
URL: <CALL_URL>

#### Key sizing-relevant turns
- **[turn N] <speaker> (<affiliation>):** "<verbatim quote>"
- **[turn N] <speaker> (<affiliation>):** "<verbatim quote>"

(Capture every turn that mentions: data volume, user count, workload type,
operating hours, unstructured/AI use, migration phase, pricing/budget signals.)

## Sizing-impacting findings
1. <finding> → <which workload / serverless / AI item it changes> — SOURCED: <citation>
2. ...

## Research scope reduction (only if exceptions clause invoked)
- (only present when --skip-glean / --skip-gong was confirmed by the user, or
  customer is internal-test / demo / POC-template)
```

---

## 5. Citation format used in the sizing JSON spec

Phase 3 of SKILL.md must label every numeric input. Use these exact prefixes:

| Source | Citation format |
|--------|-----------------|
| Context file | `SOURCED: customer-context.md L<line>` |
| Glean doc | `SOURCED: Glean — <title> (<datasource>) — <url>` |
| Gong | `SOURCED: Gong <conversation_key[:10]> turn <N> — <speaker>: "<≤15 word verbatim>"` |
| No source | `ASSUMPTION: <reason>` (must also appear in `confirm_required` with quantified impact) |

ASSUMPTION is only allowed when **all three** of A (context file), B (Glean), and C (Gong) are silent on the data point.

---

## 6. Pre-fetched mode (standard for Glean; optional for Gong)

**Glean is always pre-fetched.** The main agent runs B1/B2/B3 inline in
Phase 1.7 of `SKILL.md` and forwards the results to the
research-coordinator as a `Pre-fetched Glean Results:` blob in the
coordinator's prompt. The coordinator emits the Glean evidence section
into the final audit file using the template in Section 1 of this
document - there is no live Glean call inside any subagent.

**Gong may be pre-fetched** by a higher-level batch orchestrator (e.g. a
sizing-batch wrapper). When `Pre-fetched Gong Results:` is present in the
coordinator's prompt, the coordinator forwards it to the gong specialist,
which parses the blob and skips the live C1/C2 SQL. The audit trail in
`temp/<slug>-research-evidence.md` is required regardless of how the data
was fetched.

---

## 7. Replication research block (D1, D2, D3)

**Activation trigger.** Run this block when the customer context, Glean, or Gong results mention any of: `BCDR`, `DR`, `disaster recovery`, `failover`, `replication`, `secondary region`, `data sharing provider`, `migration to Snowflake`, `multi-region`. Also run if `--mode replication` or `--mode dr` is passed on the command line.

When triggered, populate a `replication` block on the SIZING_SPEC. See sizing-methodology.md "Replication Sizing" for the field list.

### D1 — Top databases by replicated TB (SNOWHOUSE)

Execute on **SNOWHOUSE**, not the customer account. Substitute the customer's deployment (PROD2, AZEASTUS2PROD, etc.) into the `set` lines.

```sql
-- Set deployment-specific views (substitute deployment from C11 of customer's account locator)
set accounting_etl = 'SNOWHOUSE_IMPORT.<DEPLOYMENT>.ACCOUNTING_ETL_V';
set table_etl      = 'SNOWHOUSE_IMPORT.<DEPLOYMENT>.TABLE_ETL_V';
set schema_etl     = 'SNOWHOUSE_IMPORT.<DEPLOYMENT>.SCHEMA_ETL_V';
set database_etl   = 'SNOWHOUSE_IMPORT.<DEPLOYMENT>.DATABASE_ETL_V';
set account_id     = (SELECT id FROM SNOWHOUSE_IMPORT.<DEPLOYMENT>.account_etl_v
                      WHERE name = '<CUSTOMER_ACCOUNT_NAME>');

-- Top databases by Replicated TB
SELECT
    database_etl.name AS database,
    ROUND(SUM(STAT_ACTIVE_BYTES) / POWER(2, 40), 2)   AS active_bytes_TB,
    ROUND(SUM(STAT_BYTES)        / POWER(2, 40), 2)   AS replicated_bytes_TB,
    SUM(STAT_ACTIVE_ROWS)                              AS active_rows
FROM IDENTIFIER($accounting_etl) accounting_etl
JOIN IDENTIFIER($table_etl)    AS table_etl    ON accounting_etl.table_id = table_etl.id
JOIN IDENTIFIER($schema_etl)   AS schema_etl   ON table_etl.parent_id = schema_etl.id
JOIN IDENTIFIER($database_etl) AS database_etl ON schema_etl.parent_id = database_etl.id
WHERE accounting_etl.ACCOUNT_ID = $account_id
  AND table_etl.deleted_on IS NULL
  AND schema_etl.deleted_on IS NULL
  AND database_etl.deleted_on IS NULL
GROUP BY 1
ORDER BY 2 DESC
LIMIT 50;

-- Total Active and Replicated TB + clone factor
SELECT
    ROUND(SUM(STAT_ACTIVE_BYTES) / POWER(2, 40))   AS total_active_TB,
    ROUND(SUM(STAT_BYTES)        / POWER(2, 40))   AS total_replicated_TB,
    ROUND(total_replicated_TB / total_active_TB, 2) AS clone_factor
FROM IDENTIFIER($accounting_etl) accounting_etl
JOIN IDENTIFIER($table_etl)    AS table_etl    ON accounting_etl.table_id = table_etl.id
JOIN IDENTIFIER($schema_etl)   AS schema_etl   ON table_etl.parent_id = schema_etl.id
JOIN IDENTIFIER($database_etl) AS database_etl ON schema_etl.parent_id = database_etl.id
WHERE accounting_etl.ACCOUNT_ID = $account_id
  AND table_etl.deleted_on IS NULL
  AND schema_etl.deleted_on IS NULL
  AND database_etl.deleted_on IS NULL;
```

**Populates:**
- `replication.initial_TB` ← `total_active_TB` (or per-DB selection if only some DBs replicate)
- `replication.clone_factor` ← `clone_factor` (logical/active ratio; surfaced for SE awareness, not used in cost math)

### D2 — `SYSTEM$ESTIMATE_REPLICATION_COST` (customer account)

Run as a customer-account user on the **primary deployment**. This is the most authoritative source for `monthly_change_TB`.

```sql
-- Replace <DB1>, <DB2>, ... with the databases scoped for replication
SELECT SYSTEM$ESTIMATE_REPLICATION_COST(
    OBJECT_CONSTRUCT('databases', ARRAY_CONSTRUCT('<DB1>', '<DB2>'))
) AS replication_estimate;
```

The function returns a JSON document with monthly change estimates broken down by replication frequency:

```
FIFTEEN_MINS_TB = ...   -- if customer needs 15-min RPO
ONE_HOUR_TB     = ...   -- typical default
ONE_DAY_TB      = ...   -- low-frequency / data sharing
```

**Populates:**
- `replication.monthly_change_TB` ← appropriate row based on customer's `replication_frequency`
- `replication.replication_frequency` ← matches the chosen row (`FIFTEEN_MINS` | `ONE_HOUR` | `ONE_DAY`)

If `SYSTEM$ESTIMATE_REPLICATION_COST` access is unavailable (preview gating), fall back to D3 + an empirical 28% monthly change rate as `ASSUMPTION`.

### D3 — Storage growth (customer account)

```sql
-- Year-over-year storage growth per database (customer's primary account)
SELECT
    database_name,
    ROUND(MAX(average_database_bytes) / POW(2, 30))                  AS high_GB,
    ROUND(MIN(average_database_bytes) / POW(2, 30))                  AS low_GB,
    ROUND(100 * (high_GB - low_GB) / IFF(low_GB::INT = 0, 1, low_GB)) AS pct_growth
FROM snowflake.account_usage.database_storage_usage_history
WHERE deleted IS NULL
  AND average_database_bytes > 10 * POWER(2, 30)
  AND usage_date > DATEADD('days', -365, CURRENT_DATE())
GROUP BY 1
ORDER BY 2 DESC;
```

**Populates:**
- `replication.storage_growth_pct` ← weighted average of `pct_growth` across replicated databases (default 15% if no signal)

If the customer's databases are <12 months old, narrow the date range and document the change in the evidence file.

### Evidence file additions

Append a new section to `temp/<customer-slug>-research-evidence.md`:

```markdown
## Replication signals (D1/D2/D3) — only when triggered
Trigger source: <"context file mentions DR" | "Gong call: BCDR discussion" | "--mode dr flag">

### D1 SNOWHOUSE — top databases by replicated TB
Deployment: <DEPLOYMENT>  Account: <ACCOUNT>
Total active TB: <N>  Total replicated TB: <N>  Clone factor: <N>
| database | active_TB | replicated_TB | rows |
|---|---|---|---|

### D2 SYSTEM$ESTIMATE_REPLICATION_COST
Databases scoped: <list>
FIFTEEN_MINS_TB: <N>  ONE_HOUR_TB: <N>  ONE_DAY_TB: <N>
Chosen frequency: <FIFTEEN_MINS|ONE_HOUR|ONE_DAY>  → monthly_change_TB = <N>

### D3 — Storage growth (account_usage)
Weighted growth pct: <N>%  Window: <date range>
| database | low_GB | high_GB | pct_growth |
|---|---|---|---|
```
