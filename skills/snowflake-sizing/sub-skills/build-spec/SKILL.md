---
name: snowflake-sizing-build-spec
description: Phase 3 + 4 of snowflake-sizing - assemble the SIZING_SPEC JSON object and apply per-month ramp + multi-year growth math.
---

# Build-Spec sub-skill (snowflake-sizing)

Loaded by the parent `snowflake-sizing` skill after the research sub-skill
returns. Inputs available: bootstrapped `meta` object, evidence file path,
context file content, top-3 findings summary.

Load these references on demand from `${CLAUDE_PLUGIN_ROOT}/skills/snowflake-sizing/references/`:

- `sizing-methodology.md` - the rulebook (always loaded for Phase 3)
- `field-names.md` - the wrong-vs-correct field-name reference
- `ai-feature-defaults.md` - Document AI placeholder shape, cortex_code 3-surface form, cortex_complete default model
- `content-hygiene.md` - rules for what may NEVER appear in customer-facing fields

---

## Phase 3 - Build the SIZING_SPEC

### Content hygiene (MANDATORY)

Before writing any visible-text field (`label`, `justification`, `note`,
`description`, `assumptions[]`, `confirm_required[].item`), apply the rules
in `references/content-hygiene.md`:

- No personal names from Gong transcripts.
- No internal artefact filenames.
- No citation prefixes (`SOURCED:`, `ASSUMPTION:`, `REQUIRES_CONFIRMATION:`)
  in customer-facing prose - those go only in the bare `source` enum field.

### AI feature defaults (MANDATORY)

Load `references/ai-feature-defaults.md`. Key rules:

1. The 12 `ai_cortex` keys + 6 `cortex_functions` sub-keys MUST all be
   present even when disabled. Missing any one throws a TypeError at boot
   and the page silently renders as $0. Use the disabled-placeholder shapes
   from the reference doc.
2. Default `cortex_complete.model` is `claude-sonnet-4-6`.
3. `cortex_code` uses the 3-surface form (`{ cli, snowsight, desktop }`).
4. Enable AI features only with explicit evidence; flag others in `confirm_required`.

### Workloads (SIZING_SPEC.workloads array)

> **CRITICAL: top-level array key is `workloads`. NEVER `warehouses`. The JS
> engine reads `SIZING_SPEC.workloads`; any other key renders as $0.**

Required shape per row (see `references/field-names.md` for the full list):

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
  "dev_start_month": 0,
  "go_live_month": 3,
  "ramp_curve": "linear",
  "justification": "<plain customer-facing prose - NO citation prefix>",
  "source": "SOURCED"
}
```

Create one row per distinct workload pattern. Apply the warehouse sizing
rules from `sizing-methodology.md`. Apply MCW (clusters_min/max) when
concurrency rules trigger. Always include a Development workload (XS, ~4
hrs/day, 22 days).

Label every numeric input: `source = SOURCED` (cite in `justification`),
`source = ASSUMPTION` (explain in `justification` and add to
`confirm_required` with quantified impact), or `source = ESTIMATED` (when
range-bounded but not pinned).

### Serverless features

For each of the 27 serverless features in the schema, set `enabled=true`
only with evidence. All 27 keys MUST be present (set `enabled=false` and
zero compute_hours_monthly otherwise) - the schema enforces this.

Key features to check: Snowpipe / Snowpipe Streaming (real-time ingestion),
Serverless Tasks (orchestration), Dynamic Tables (declarative pipeline),
Clustered Tables (large tables with selective filtering), Replication
(multi-region / DR), Search Optimization (point lookups on large tables).

### AI / Cortex features

Apply the rules from `references/ai-feature-defaults.md`. Use
`references/field-names.md` for the wrong-vs-correct field paths.

### SPCS, OpenFlow, Postgres, Collaboration, Replication

Use the shapes defined in `framework/sizing_spec_schema.json`. For OpenFlow
the `warehouse_size` MUST be the full name (`X-Small`, `Small`, `Medium`),
NOT abbreviated. For Replication, see `references/research-protocol.md` section 7.

### Storage

Set `time_travel_days=1` and `churn_rate_pct=10` unless evidence states
otherwise. Apply compression defaults from `sizing-methodology.md`.

### Growth

Set `meta.annual_growth_rate` from context (default 0.20 = 20%/yr). This
applies from year 2 onwards. Year 1 ramp is per-workload via the Birdbox
curve model - there is no top-level `growth_rates` array.

### Compile

Produce the complete SIZING_SPEC. Include all enabled workloads with their
`source`/`justification` fields, all 27 serverless features (most disabled),
all 12 `ai_cortex` keys (most disabled), `assumptions` array (20+ items
expected), and `confirm_required` array with quantified impacts.

---

## Phase 4 - Apply multi-year growth (per-month model)

For each workload row and each absolute month `m` (1-indexed across the full contract):

```
relative_month = ((m - 1) MOD 12) + 1
year_index     = ((m - 1) DIV 12)

ramp_factor    = clamp(((m_in_y1 - dev_start + 1) / (go_live - dev_start + 1)) ^ exponent, 0, 1)
                 where m_in_y1 = m for year 1; for year 2+, ramp_factor = 1.0
growth_factor  = (1 + annual_growth_rate) ^ year_index
month_factor   = ramp_factor * growth_factor
```

`exponent` comes from `pricing.ramp_curves.exponents[ramp_curve]`.

Year totals:

```
warehouse_credits_y    = Sum_workloads (cr_per_hr(size) * hrs/day * days/mo * avg_clusters) * Sum_months_in_y (month_factor)
serverless_credits_y   = Sum_workloads (monthly_serverless_credits * Sum_months_in_y month_factor)
ai_credits_y           = Sum_workloads (monthly_ai_credits * Sum_months_in_y month_factor)
storage_cost_y         = active_TB(y) * storage_rate * 12
spcs_cost_y            = Sum_instances (instance_cr/hr * hrs/mo * count * credit_rate * Sum_months_in_y month_factor)
openflow_cost_y        = per-instance sum * Sum_months_in_y month_factor
transfer + privatelink = tb * rate * 12
replication_cost_y     = (active_TB(y) + monthly_change_TB(y)*12) * cr_per_TB * credit_rate
                       + monthly_change_TB(y)*12 * egress_matrix[source][target]
                       + avg_TB(y) * replica_storage_per_TB_per_month * 12
                         (only if SIZING_SPEC.replication is present)
```

Print a summary table to the terminal:

```
Year | Credits | Compute $ | Serverless $ | AI $ | Storage $ | Replication $ | Total $
  1  |   ...  |    ...    |     ...      |  ... |    ...    |     ...       |   ...
TCV: $XXX,XXX
```

Omit the Replication column if `SIZING_SPEC.replication` is absent.

---

Hand control back to the parent skill, which will invoke the `render-html`
sub-skill next.
