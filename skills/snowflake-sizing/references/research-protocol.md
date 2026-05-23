# Research Protocol — snowflake-sizing

This is the operational reference for Phase 2 of `SKILL.md`. Read it once at the start of Phase 2 and execute the matrix verbatim. Phase 2 is a **MANDATORY CHECKPOINT** — there is no skip-if-dossier-exists branch.

---

## 1. Glean MCP queries (B1, B2, B3)

Tool: `mcp__glean_default__search` (also commonly named `mcp__glean__search` on some hosts — try the alias if the default is missing).

| Call | `query` | `app` filter | `num_results` | Purpose |
|------|---------|--------------|---------------|---------|
| B1 | `"<customer> snowflake data platform workloads"` | _none_ | 8 | Account-level signals across Drive, Slack, Confluence, etc. |
| B2 | `"<customer>"` | `gong` | 8 | Recent customer calls indexed by Glean |
| B3 | `"<customer>"` | `salescloud` | 5 | Salesforce: opp size, ARR, stage, close date |

Substitute `<customer>` with the parsed customer name. If the customer name has a parenthetical short form (e.g. `"GSMA Intelligence (GSMAi)"`), run B1 with the full name and B2/B3 with the short form.

For each Glean result, record: title, datasource, snippet (first 200 chars), URL, date.

---

## 2. Gong SQL (C1, C2)

Connection: **SNOWHOUSE** via `snowflake_sql_execute`.

### C1 — Find calls

```sql
SELECT CONVERSATION_KEY, CONVERSATION_ID, TITLE,
       PLANNED_START_DATETIME::DATE AS call_date,
       CALL_SPOTLIGHT_BRIEF, CALL_URL
FROM GONG_SHARE.GONG_DATA_CLOUD.CALLS
WHERE LOWER(TITLE) LIKE LOWER('%<customer_substring>%')
ORDER BY PLANNED_START_DATETIME DESC
LIMIT 3;
```

Use the customer name (or first word) as `<customer_substring>`.

### C2 — Load transcripts (top 2 calls from C1)

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
WHERE ct.CONVERSATION_KEY IN ('<key_1>', '<key_2>')
ORDER BY ct.CONVERSATION_KEY, t.INDEX;
```

Critical join rules:
- Use `CONVERSATION_KEY` (hash). Do NOT use `CONVERSATION_ID` (numeric) for joins.
- If `TRANSCRIPT` is NULL, fall back to `CALL_SPOTLIGHT_BRIEF` from C1 for that call.
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

Write to `temp/<customer-slug>-research-evidence.md`. The customer slug is the customer name lowercased with spaces → hyphens and non-alphanumerics removed (matches the slug used in `temp/<customer-slug>-<N>year-sizing.html`).

```markdown
# Research Evidence — <Customer> sizing v<N>

Generated: <YYYY-MM-DD>
Sizing artifact: temp/<customer-slug>-<N>year-sizing.html

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

## 6. Pre-fetched batch mode

If the parent invocation passed `Pre-fetched Glean Results:` and `Pre-fetched Gong Results:` blobs in the prompt, parse those blobs and skip the live B/C calls. Still write the evidence file from the pre-fetched data — the audit trail is required regardless of how the data was fetched.
