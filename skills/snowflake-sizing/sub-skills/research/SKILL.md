---
name: snowflake-sizing-research
description: Phase 2 of snowflake-sizing - run preflight checks and dispatch the research subagent for Glean + Gong evidence.
---

# Research sub-skill (snowflake-sizing)

Loaded by the parent `snowflake-sizing` skill once `meta` is bootstrapped.
This sub-skill is a thin launcher: the protocol detail lives in
`references/research-protocol.md` and the heavy lifting is delegated to
`agents/research-agent.md` so the main agent's context stays slim.

---

## Phase 1.5 - Preflight (BLOCKING)

Verify both research surfaces before anything else. Hard gate - if either
fails, abort with the exact setup instructions and stop.

### 1. Glean MCP availability

Run a no-op `mcp__glean_default__search` with `query: "*"` and `num_results: 1`.
If the call errors with `tool not found`, `MCP not configured`, or similar, ABORT with:

```
Glean MCP is not configured. Run:
   cortex mcp add glean https://snowflake-be.glean.com/mcp/default --transport http
Then re-invoke this skill.
```

### 2. SNOWHOUSE / Gong access

Run via `snowflake_sql_execute`:

```sql
SELECT COUNT(*) FROM GONG_SHARE.GONG_DATA_CLOUD.CALLS LIMIT 1;
```

If the call errors (connection not configured, table not accessible, permission denied), ABORT with:

```
SNOWHOUSE Gong access unavailable. Set the active connection:
   cortex connections set snowhouse
Confirm `cortex connections list` shows snowhouse, then re-invoke.
```

The narrow EXCEPTIONS clause below is the only legitimate way to bypass either check.

### EXCEPTIONS - when research may be reduced

Reduced research is permitted ONLY when:

- `--skip-glean` is explicitly passed AND user confirms in chat.
- `--skip-gong` is explicitly passed AND user confirms in chat.
- Customer name is `internal-test`, `demo`, or `POC-template`.

In any of these cases, write the fact verbatim to the evidence file under
`## Research scope reduction` before proceeding.

---

## Phase 2 - Dispatch the research-agent (MANDATORY CHECKPOINT)

Launch `research-agent` (under `agents/research-agent.md`) with:

- `customer` - the parsed customer name (full and short form if both exist)
- `context_file` - the path passed to `/snowflake-sizing`
- Flags: `--skip-glean`, `--skip-gong`, `--mode replication`, `--mode dr`
  (forward whatever the parent skill received)
- `slug` - lowercased customer name with spaces -> hyphens, non-alphanumerics stripped
- `evidence_path` - `temp/<slug>-research-evidence.md`

The research-agent reads `references/research-protocol.md`, runs B1/B2/B3 +
C1/C2 (and D1/D2/D3 when triggered) in parallel, writes the evidence file,
and returns ONLY a structured summary - never raw transcripts or Glean blobs.

## Phase 2.5 - Verify and proceed

When the research-agent returns:

1. Confirm the evidence file exists at `temp/<slug>-research-evidence.md`. If
   not, abort and surface the agent's last message to the user.
2. Print this summary verbatim to the terminal (the agent's return string is
   already in this shape):

   ```
   Research complete
      Glean hits: B1=N, B2=N, B3=N
      Gong calls reviewed: <call1> (<date>), <call2> (<date>)
      Top 3 sizing-impacting findings:
      1. ...
      2. ...
      3. ...
      Evidence file: temp/<slug>-research-evidence.md
   Proceeding to build-spec.
   ```

3. Hand control back to the parent `snowflake-sizing` skill, which will
   invoke the `build-spec` sub-skill next.

## Pre-fetched batch mode

If the parent invocation passed `Pre-fetched Glean Results:` and `Pre-fetched
Gong Results:` blobs in the prompt, pass these forward to the research-agent
in its prompt. The agent will skip the live B/C calls and still write the
evidence file from the pre-fetched data - the audit trail is required
regardless of how the data was fetched.
