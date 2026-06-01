---
description: Generate an interactive Snowflake consumption estimate and customer-facing HTML proposal from a discovery context file.
argument-hint: "<context-file> [--customer \"Name\"] [--years 3] [--edition Enterprise] [--region \"AWS US East (Northern Virginia)\"] [--pptx]"
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
| `--pptx` | off | After generating the HTML, also produce a Snowflake-branded PowerPoint (`.pptx`) from the same sizing JSON. Runs the render-pptx sub-skill with a full visual QA loop. Requires `python-pptx` (`pip install python-pptx`) and LibreOffice for QA image export. |

**PPTX output** (only with `--pptx`):
`sizings/<slug>-<N>year-sizing-v1-<date>.pptx` - 6-slide Snowflake-branded deck (Title, Exec Summary/TCV, Workloads Detail, Year-by-Year Costs, Serverless/AI Breakdown, Assumptions + Closer). Numbers are Python-authoritative: `render-pptx.py` re-runs `compute_core_totals()` on the spec before building slides.

The HTML "Export for PPTX" button downloads the current in-browser spec as JSON; pass it to `scripts/render-pptx.py --spec <file.json> --out <file.pptx>` to pick up browser-side edits without re-running the full pipeline.
