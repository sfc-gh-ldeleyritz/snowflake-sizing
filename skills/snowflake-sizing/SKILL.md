---
name: snowflake-sizing
description: Generate a defensible Snowflake consumption estimate and interactive HTML pricing proposal from a customer context file and Glean research.
---

# Snowflake Sizing Skill (router)

Generate a complete, defensible Snowflake consumption estimate and a single
self-contained interactive HTML proposal. This top-level skill handles
argument parsing and pricing-data bootstrap, then routes through three
sub-skills loaded on demand.

---

## Phase 1 - Parse arguments and bootstrap

Parse `$ARGUMENTS`:

- `context_file` - required by default. Path to customer transcript,
  questionnaire, or notes. **If the value passed in `$ARGUMENTS` does not
  resolve to an existing file**, treat the entire `$ARGUMENTS` string as
  inline scenario context: keep it in memory as `inline_scenario`, and pass
  it to the research-coordinator in place of a file path. This unblocks
  ad-hoc invocations like `/snowflake-sizing Marks and Spencer wants to
  migrate 50TB...` without forcing the SE to first dump the prompt into a
  file. The audit trail in `temp/<slug>-research-evidence.md` records
  `Source: inline scenario (no context file)` so the provenance is
  preserved.
- `--customer "Name"` - customer name override. If omitted, extract from context.
- `--years N` - contract length. Default: **3**.
- `--edition X` - Standard / Enterprise / Business Critical / VPS. Default: **Enterprise**.
- `--region "X"` - full region string. If omitted, infer from context; default `"AWS Europe (London)"`.
- `--skip-glean`, `--skip-gong` - reduce research (requires user confirmation; see EXCEPTIONS in research sub-skill).
- `--mode replication` or `--mode dr` - activate the replication research block (D1/D2/D3).
- `--pptx` - after render-html completes, also run the render-pptx sub-skill to generate a Snowflake-branded PPTX from the same sizing JSON.

Read pricing data using the plugin-relative path:

```
${CLAUDE_PLUGIN_ROOT}/assets/snowflake_pricing_master.json
```

Derive from pricing data:

- `credit_rate` - from `credit_pricing.data` matching cloud + region + edition
- `ai_credit_rate` - from `ai_credit_pricing.on_demand.global` ($2.00 default)
- `storage_rate_per_tb` - from `storage.standard` for the region (`row["on_demand"]`)

### Region name resolution (MANDATORY before pricing lookup)

Resolve user-supplied region against the alias table below. Use the canonical
key as the exact string to match in `credit_pricing.data[].region`.

| User input | Canonical key |
|---|---|
| `North Europe`, `Ireland`, `Azure North Europe` | `North Europe (Ireland)` |
| `London`, `UK South`, `Azure London`, `UK` | `UK South (London)` |
| `AWS US East`, `Virginia`, `N. Virginia`, `us-east-1` | `AWS US East (Northern Virginia)` |
| `AWS US West`, `Oregon`, `us-west-2` | `AWS US West (Oregon)` |
| `Frankfurt`, `AWS Frankfurt`, `eu-central-1` | `AWS EU (Frankfurt)` |
| `Sydney`, `AWS Sydney`, `ap-southeast-2` | `AWS Asia Pacific (Sydney)` |
| `Singapore`, `AWS Singapore`, `ap-southeast-1` | `AWS Asia Pacific (Singapore)` |
| `Tokyo`, `AWS Tokyo`, `ap-northeast-1` | `AWS Asia Pacific (Tokyo)` |
| `Netherlands`, `West Europe`, `Azure Netherlands` | `West Europe (Netherlands)` |
| `Sweden Central` | `Sweden Central` |

If no alias matches and no exact key matches, print available keys from
`credit_pricing.data` and ask the SE to correct `--region` before proceeding.

After resolving, print:

```
Region: <resolved key> | Credit rate: $X.XX/credit (<Edition>)
```

### Bootstrap meta object

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

**Optional discount block.** If the context mentions a negotiated capacity
discount, an Order Form rate, or the SE asks for a what-if, add a `discount`
block (see `references/ai-feature-defaults.md` for scope rules - AI credits
are not discounted) and seed `list_credit_rate` to the same value as
`credit_rate`. Effective rate goes in `meta.credit_rate`.

---

## Phase 1.7 - Glean pre-fetch (main agent)

Glean MCP OAuth is session-bound and does not propagate to subagents - so
B1/B2/B3 must run in **this** main-agent context, not inside the
research-coordinator. The results are then forwarded to the coordinator
in-memory (no JSON sidecar on disk).

**Skip path.** If `--skip-glean` was passed AND the user has confirmed in
chat (per the EXCEPTIONS clause in the research sub-skill), set
`glean_skipped = true` and proceed to Routing without running queries.

**Standard path.** Run B1, B2, B3 in a single parallel `mcp__glean__search`
batch using the verbatim `query` / `app` / `num_results` matrix in
`references/research-protocol.md` Section 1. If the customer name has a
parenthetical short form (e.g. `"GSMA Intelligence (GSMAi)"`), use the full
name for B1 and the short form for B2/B3.

For each result, capture `{ title, datasource, snippet (<=200 chars), url,
date }`. Build the in-memory `pre_fetched_glean` object:

```json
{
  "B1": {"query": "<verbatim>", "app": null,         "hits": <n>, "results": [ {title, datasource, snippet, url, date}, ... ]},
  "B2": {"query": "<verbatim>", "app": "gong",       "hits": <n>, "results": [ ... ]},
  "B3": {"query": "<verbatim>", "app": "salescloud", "hits": <n>, "results": [ ... ]}
}
```

If the parallel batch errors out (Glean MCP not configured, OAuth expired,
etc.), abort with the setup instructions:

```
Glean MCP is not configured or its session expired. Run:
   cortex mcp add glean https://snowflake-be.glean.com/mcp/default --transport http
Then re-invoke this skill.
```

This replaces the Glean preflight that the coordinator used to run.

---

## Routing

Invoke the three sub-skills in sequence. Each one reads only the references
it needs - main-agent context stays slim.

1. **research** - `sub-skills/research/SKILL.md`
   Phase 1.5 preflight (SNOWHOUSE only - Glean preflight is implicit in
   Phase 1.7 above) and Phase 2 research. Delegated to
   `agents/research-coordinator.md` which fans out two-or-three specialist
   agents (Gong / optional Replication) in parallel. The coordinator
   receives the `pre_fetched_glean` object (or `glean_skipped: true`) and
   transforms it into the Glean section of the evidence file directly -
   there is no Glean specialist subagent. Returns top 3 findings +
   evidence file path.

2. **build-spec** - `sub-skills/build-spec/SKILL.md`
   Phases 3 + 4. Assembles SIZING_SPEC from evidence; applies per-month ramp
   and multi-year growth math. Loads `references/sizing-methodology.md`,
   `references/field-names.md`, `references/ai-feature-defaults.md`,
   `references/content-hygiene.md` as needed.

3. **render-html** - `sub-skills/render-html/SKILL.md`
    Phases 5 + 6. Writes spec JSON, substitutes template tokens, writes HTML,
    runs the three quality gates in parallel, prints the final summary.
    Loads `references/html-spec.md` (only here - 1000+ lines) and
    `references/content-hygiene.md`.

4. **render-pptx** - `sub-skills/render-pptx/SKILL.md` *(only when `--pptx` is present)*
    Phases 7 + 8. Runs `scripts/render-pptx.py` against the same
    `sizings/<slug>.json` written in Phase 3, exports slide images for visual
    QA, iterates until clean, prints the PPTX summary. Requires `python-pptx`
    and LibreOffice (see sub-skill prerequisites). The `--pptx` flag is parsed
    in Phase 1; the sub-skill is invoked only after render-html returns
    successfully.

## Hooks active during this skill

- `hooks/preflight.py` (UserPromptSubmit) - injects setup reminders before
  the skill even starts running.
- `hooks/sizing-guard.py` (PreToolUse on Write) - single consolidated guard
  that blocks bad writes BEFORE the file lands. For `sizings/*.json` it
  schema-validates, detects legacy field names with auto-fix suggestions,
  and rejects leakage fields. For `sizings/*.html` it scans for em-dashes,
  content-hygiene tokens, unsubstituted `__TOKEN__` leftovers, and runs
  the Node sidecar JS render check (catches $0-renders). For
  `temp/*-evidence*.md` it scans for em-dashes only. For `sizings/*.pptx`
  it skips all text scans (binary file) and allows the write through.
- `hooks/session.py` (SessionStart, source=startup only) - cleans stale
  research-evidence files older than 30 days.

The hook shares its validation logic with `scripts/spec-prepare.py` via
direct module import, and both pull required-field lists from
`scripts/_schema_loader.py` which loads `framework/sizing_spec_schema.json`
as the single source of truth.
