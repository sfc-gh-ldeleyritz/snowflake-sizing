# AI Feature Defaults

Loaded by: `sub-skills/build-spec/SKILL.md` Phase 3.

---

## Document AI - optional placeholder shape

Document AI is deprecated for new sizing - prefer `ai_extract` (under
`ai_cortex.cortex_functions`) with appropriate token volumes (default 70M
tokens/month when document extraction is a primary use case).

The three keys `document_ai`, `ai_parse_document_layout`, and
`ai_parse_document_ocr` are now OPTIONAL. The HTML template uses optional
chaining (`ai.document_ai?.enabled`) for the only on-render dereference, and
the TCV math has always guarded the others with `&&`. Spec-prepare's
skeleton omits them; supply them in the patch only when the customer
actively uses Document AI:

```json
"document_ai":               { "enabled": true, "compute_hours_monthly": 80 },
"ai_parse_document_layout":  { "enabled": true, "pages_per_month": 50000 },
"ai_parse_document_ocr":     { "enabled": true, "pages_per_month": 25000 }
```

Required `ai_cortex` keys are now 9 (down from 12): `cortex_complete`,
`cortex_agents`, `snowflake_intelligence`, `cortex_code`, `cortex_analyst`,
`cortex_search`, `cortex_fine_tuning`, `cortex_functions`, `embeddings`.
See `framework/sizing_spec_schema.json` `properties.ai_cortex.required` for
the canonical list (also enforced by `scripts/_schema_loader.py`).

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
