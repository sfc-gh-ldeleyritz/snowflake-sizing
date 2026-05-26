---
description: Generate an interactive Snowflake consumption estimate and customer-facing HTML proposal from a discovery context file.
argument-hint: "<context-file> [--customer \"Name\"] [--years 3] [--edition Enterprise] [--region \"AWS US East (Northern Virginia)\"]"
allowed-tools: [Read, Write, Bash, WebFetch, snowflake_sql_execute, mcp__glean_default__search, mcp__glean_default__read_document, mcp__glean_default__chat, mcp__glean_default__employee_search]
skill: snowflake-sizing
---

Generate a Snowflake sizing estimate and interactive HTML proposal. Pass `$ARGUMENTS` to the skill.

**Prerequisites (skill will hard-fail without these):**
- Glean MCP configured: `cortex mcp add glean https://snowflake-be.glean.com/mcp/default --transport http`
- Active SNOWHOUSE connection with `GONG_SHARE.GONG_DATA_CLOUD` access: `cortex connections set snowhouse`

The skill emits three artifacts: `sizings/<slug>-<N>year-sizing-v1-<date>.html` (the interactive proposal), `sizings/<slug>-<N>year-sizing-v1-<date>.json` (the portable sizing spec), and `temp/<slug>-research-evidence.md` (the Glean + Gong audit trail).
