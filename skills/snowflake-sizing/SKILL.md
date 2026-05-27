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

- `context_file` - required. Path to customer transcript, questionnaire, or notes.
- `--customer "Name"` - customer name override. If omitted, extract from context.
- `--years N` - contract length. Default: **3**.
- `--edition X` - Standard / Enterprise / Business Critical / VPS. Default: **Enterprise**.
- `--region "X"` - full region string. If omitted, infer from context; default `"AWS Europe (London)"`.
- `--skip-glean`, `--skip-gong` - reduce research (requires user confirmation; see EXCEPTIONS in research sub-skill).
- `--mode replication` or `--mode dr` - activate the replication research block (D1/D2/D3).

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

## Routing

Invoke the three sub-skills in sequence. Each one reads only the references
it needs - main-agent context stays slim.

1. **research** - `sub-skills/research/SKILL.md`
   Phase 1.5 preflight (Glean MCP + SNOWHOUSE) and Phase 2 research.
   Delegated to `agents/research-coordinator.md` which fans out three
   specialist agents (Glean / Gong / Replication) in parallel so transcripts
   and Glean blobs stay out of main context. Returns top 3 findings +
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

## Hooks active during this skill

- `hooks/preflight.py` (UserPromptSubmit) - injects setup reminders before
  the skill even starts running.
- `hooks/sizing-guard.py` (PreToolUse on Write) - single consolidated guard
  that blocks bad writes BEFORE the file lands. For `sizings/*.json` it
  schema-validates, detects legacy field names with auto-fix suggestions,
  and rejects leakage fields. For `sizings/*.html` it scans for em-dashes,
  content-hygiene tokens, unsubstituted `__TOKEN__` leftovers, and runs
  the Node sidecar JS render check (catches $0-renders). For
  `temp/*-evidence*.md` it scans for em-dashes only.
- `hooks/session.py` (SessionStart, source=startup only) - cleans stale
  research-evidence files older than 30 days.

The hook shares its validation logic with `scripts/spec-prepare.py` via
direct module import, and both pull required-field lists from
`scripts/_schema_loader.py` which loads `framework/sizing_spec_schema.json`
as the single source of truth.
