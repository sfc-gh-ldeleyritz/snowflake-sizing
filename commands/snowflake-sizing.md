---
description: Generate an interactive Snowflake consumption estimate and customer-facing HTML proposal from a discovery context file.
argument-hint: "<context-file> [--customer \"Name\"] [--years 3] [--edition Enterprise] [--region \"AWS US East (Northern Virginia)\"]"
allowed-tools: [Read, Write, Bash, WebFetch, snowflake_sql_execute, mcp__glean__search, mcp__glean__read_document, mcp__glean__chat, mcp__glean__employee_search]
skill: snowflake-sizing
---

Generate a Snowflake sizing estimate and interactive HTML proposal. Pass `$ARGUMENTS` to the skill.

**Prerequisites (skill will hard-fail without these):**
- Glean MCP configured: `cortex mcp add glean https://snowflake-be.glean.com/mcp/default --transport http`
- Active SNOWHOUSE connection with `GONG_SHARE.GONG_DATA_CLOUD` access: `cortex connections set snowhouse`

The skill emits three artifacts: `sizings/<slug>-<N>year-sizing-v1-<date>.html` (the interactive proposal), `sizings/<slug>-<N>year-sizing-v1-<date>.json` (the portable sizing spec), and `temp/<slug>-research-evidence.md` (the Glean + Gong audit trail).

**Flags:**

| Flag | Default | Description |
|---|---|---|
| `--customer "Name"` | extracted from context | Override the customer name. |
| `--years N` | 3 | Contract length in years. |
| `--edition X` | Enterprise | Snowflake edition (Standard / Enterprise / Business Critical / VPS). |
| `--region "X"` | AWS Europe (London) | Full region string; inferred from context if omitted. |
| `--skip-glean` | off | Skip Glean research (requires user confirmation). |
| `--skip-gong` | off | Skip Gong research (requires user confirmation). |
| `--mode replication` | off | Activate the replication / DR research block. |

**PPTX output:** there is no automated PPTX flag. To produce a deck, open the generated HTML proposal and click the **Export to PPTX** button - it builds a Snowflake-branded deck entirely in the browser from the current (optionally edited) in-page spec. No server or Python step is involved.

