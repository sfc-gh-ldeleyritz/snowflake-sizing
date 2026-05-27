# AI Feature Defaults

Loaded by: `sub-skills/build-spec/SKILL.md` Phase 3.

---

## Document AI - deprecated, but keys still required

Document AI is deprecated for new sizing - prefer `ai_extract` (under
`ai_cortex.cortex_functions`) with appropriate token volumes (default 70M
tokens/month when document extraction is a primary use case).

However, the keys `document_ai`, `ai_parse_document_layout`, and
`ai_parse_document_ocr` MUST still be present in `ai_cortex` because
`populateAIPanel()` reads `ai.document_ai.enabled` and
`ai.document_ai.compute_hours_monthly` directly without optional chaining.
Omitting them throws a TypeError at boot, the `DOMContentLoaded` handler
aborts, and the page silently renders all dollar values as $0.

Use the disabled-placeholder shapes:

```json
"document_ai":               { "enabled": false, "compute_hours_monthly": 0 },
"ai_parse_document_layout":  { "enabled": false, "pages_per_month": 0 },
"ai_parse_document_ocr":     { "enabled": false, "pages_per_month": 0 }
```

See `examples/acme-financial-3year-sizing.json` for the canonical placeholder
shape, and `framework/sizing_spec_schema.json` `properties.ai_cortex.required`
for the full list of 12 required keys (also enforced by `scripts/spec-validate.py`
and `hooks/validate-sizing-json.py`).

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

## Enable-only-with-evidence rule

Enable AI features only when the customer has explicitly mentioned them or
where there is clear use-case evidence. Do NOT default-enable AI features.
If the customer is in a data-science or AI-forward industry, flag relevant
features in `confirm_required` instead.

## Discount scope

Negotiated capacity discounts apply to Platform Credits only. AI Credits
($2.00 global / $2.20 regional) keep the on-demand rate; the discount block
does NOT modify `meta.ai_credit_rate`.
