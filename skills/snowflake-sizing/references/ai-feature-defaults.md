# AI Feature Defaults

Loaded by: `sub-skills/build-spec/SKILL.md` Phase 3.

---

## Document AI - optional placeholder shape

Document AI is deprecated for new sizing - prefer `ai_extract` (under
`ai_cortex.cortex_functions`) with appropriate token volumes (default 70M
tokens/month when document extraction is a primary use case).

The three keys `document_ai`, `ai_parse_document_layout`, and
`ai_parse_document_ocr` are now OPTIONAL in the schema. The HTML
template uses optional chaining (`ai.document_ai?.enabled`) for the only
on-render dereference, and the TCV math has always guarded the others
with `&&`, so a sizing without those keys renders correctly. The
skeleton (`framework/sizing_spec_skeleton.json`) seeds all three with
`enabled: false` placeholders anyway, so spec-prepare's deep-merge
output always satisfies both the schema and the JS template - you do
NOT need to add them to the patch unless the customer actively uses
Document AI. When they DO use it, override the relevant keys in the
patch:

```json
"document_ai":               { "enabled": true, "compute_hours_monthly": 80 },
"ai_parse_document_layout":  { "enabled": true, "pages_per_month": 50000 },
"ai_parse_document_ocr":     { "enabled": true, "pages_per_month": 25000 }
```

Required `ai_cortex` keys are 9 (per the schema): `cortex_complete`,
`cortex_agents`, `snowflake_intelligence`, `cortex_code`, `cortex_analyst`,
`cortex_search`, `cortex_fine_tuning`, `cortex_functions`, `embeddings`.
The skeleton also ships the 3 optional Document AI siblings as disabled
placeholders, so the assembled spec has 12 `ai_cortex` keys total. See
`framework/sizing_spec_schema.json` `properties.ai_cortex.required` for
the canonical required list (also enforced by `scripts/_schema_loader.py`).

## Default model for cortex_complete

Always specify `claude-sonnet-4-6` (input: 1.65 AI cr/M, output: 8.25 AI cr/M).
Do not use unlisted, older, or smaller models as defaults.

## Cortex Code surfaces (3-surface form)

`ai_cortex.cortex_code = { cli, snowsight, desktop }`. Each entry:

```json
{ "enabled": false, "developers": 0, "queries_per_dev_per_day": 0, "avg_tokens_per_query": 0 }
```

The three surfaces (CLI / Snowsight / Cortex Code Desktop) bill at the same
Table 6(e) rate but reflect different per-developer usage patterns. Enable each
surface independently. Defaults:

| Surface | Typical queries/dev/day | Typical tokens/query | Notes |
|---|---|---|---|
| CLI | 5 - 20 | 800 - 1,500 | Power users in terminal; lightweight prompts. |
| Snowsight | 10 - 40 | 1,000 - 1,800 | SQL assist inside worksheets; medium usage. |
| Cortex Code Desktop | 30 - 80 | 1,200 - 2,500 | IDE assistant with inline suggestions + chat; heaviest usage. |

The legacy single-object shape
(`cortex_code.{enabled, developers, queries_per_dev_per_day, avg_tokens_per_query}`)
is auto-normalized by the template (legacy values land on `cli`), but new specs
MUST emit the three-surface form.

## Cortex Agents / Snowflake Intelligence token estimation

Direct `monthly_input_tokens_M` / `monthly_output_tokens_M` inputs are hard to
estimate from scratch. Derive them from a usage model instead. The HTML proposal
has a built-in helper row for both features — the AI should populate the same
fields in the patch so spec-prepare embeds the right token volumes.

**Formula** (per feature):
```
monthly_input_tokens_M  = users × sessions_per_user_per_day × messages_per_session
                          × avg_input_tokens_per_message / 1_000_000 × working_days_per_month
monthly_output_tokens_M = same, with avg_output_tokens_per_message
```

**Typical ranges:**

| Parameter | Light usage | Moderate | Heavy |
|---|---|---|---|
| `monthly_users` | 10 - 50 | 100 - 500 | 1,000+ |
| `sessions_per_user_per_day` | 1 - 2 | 2 - 5 | 10 - 20 |
| `messages_per_session` | 2 - 5 | 5 - 10 | 10 - 20 |
| `avg_input_tokens_per_message` | 500 - 1,500 | 1,500 - 3,000 | 3,000 - 8,000 |
| `avg_output_tokens_per_message` | 200 - 500 | 500 - 1,000 | 1,000 - 2,000 |
| `working_days_per_month` | 22 (default) | 22 | 22 - 30 |

Include all six helper fields in the patch alongside the derived token counts.
Example:
```json
"cortex_agents": {
  "enabled": true,
  "model": "claude-4-sonnet",
  "monthly_users": 200,
  "sessions_per_user_per_day": 3,
  "messages_per_session": 6,
  "avg_input_tokens_per_message": 2000,
  "avg_output_tokens_per_message": 600,
  "working_days_per_month": 22,
  "monthly_input_tokens_M": 15.84,
  "monthly_output_tokens_M": 4.75
}
```

## Enable-only-with-evidence rule

Enable AI features only when the customer has explicitly mentioned them or
where there is clear use-case evidence. Do NOT default-enable AI features.
If the customer is in a data-science or AI-forward industry, flag relevant
features in `confirm_required` instead.

## Discount scope

Negotiated capacity discounts apply to Platform Credits only. AI Credits
($2.00 global / $2.20 regional) keep the on-demand rate; the discount block
does NOT modify `meta.ai_credit_rate`.
