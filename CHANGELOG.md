# snowflake-sizing changelog

## [Unreleased]

### Added
- **Birdbox-style per-workload ramp curves.** Replaces the legacy 55-90% Year-1 multiplier with the 5-curve power model from the Birdbox Planner V2: Slowest (x^4), Slow (x^2), Linear (x), Fast (x^0.5), Fastest (x^0.25), and Manual. Each workload row now carries `dev_start_month`, `go_live_month`, `ramp_curve` fields and ramps from 0 to 100% across that window. The `factor(m)` formula is `clamp(((m - dev_start + 1) / (go_live - dev_start + 1))^exponent, 0, 1)` with steady-state at 100% after go-live. `meta.default_ramp_curve` / `default_dev_start_month` / `default_go_live_month` seed defaults for new rows. Pricing data lives in `pricing.ramp_curves` (exponents + recommended-by-workload-type map). Reference: `Birdbox Planner V2.xlsx 'HIDDEN - LOOKUPS'`.
- **Replication / DR / Migration cost integration.** Full ~55x55 source/target egress matrix from the Apr 2026 Replication Cost Calculator embedded in `pricing.replication.egress_matrix` (51 sources, 52 targets including ECO Cache). New `calcReplicationForYear(year)` JS engine computes annual compute (`(active+growth+change)_TB x 4 cr/TB x $/credit` Year 1; `(growth+change)_TB x 4 cr/TB x $/credit` Year 2+), egress (same basis x `egress_matrix[src][tgt]`), and replica storage (`avg_TB x $/TB/mo x 12`). Verified against the calculator's documented 3-year total of $160,444.54 (Thailand to ECO Cache, 100 TB initial, 8 TB/month change, 15% growth, 10% YoY) - matches to the cent. New `<section id="replication">` renders in the proposal HTML only when `SIZING_SPEC.replication.enabled !== false`, with editable source/target dropdowns, initial TB, monthly change TB, credits/TB, replica storage rate, and growth/YoY inputs. Per-year breakdown table shows compute/egress/storage/total.
- **Replication research block (D1/D2/D3).** New `references/research-protocol.md` Section 7 codifies the SNOWHOUSE `accounting_etl + table_etl + schema_etl + database_etl` join SQL from the calculator's Utility Queries sheet (D1: top databases by replicated TB), the `SYSTEM$ESTIMATE_REPLICATION_COST` invocation pattern (D2), and the `account_usage.database_storage_usage_history` storage growth query (D3). Each query is tagged with the SIZING_SPEC field it populates. Activated when context mentions BCDR / DR / replication / migration or via `--mode dr`.
- **Per-query cache-write and cache-read tokens for SI/Agents.** `cortex_agents` and `snowflake_intelligence` SIZING_SPEC entries now carry `monthly_cache_write_tokens_M` and `monthly_cache_read_tokens_M` alongside input/output. Pricing sourced from `pricing.ai_features.intelligence_agents_analyst.data` (Table 6d cache_write / cache_read columns) - the calculator no longer omits these.
- **Migration scenario** subsection in `sizing-methodology.md` documenting how the same replication formulas apply for one-way bulk Snowflake migrations.

### Changed
- **All hardcoded AI rates removed from the JS engine.** `_template.html` and `html-spec.md` `calcAICredits()` no longer carry literal `1.88`, `9.41`, `2.51`, `12.55`, `67`, `6.3`, `3.40`, `8`, `3.33`, `0.5`, `1.39`, `1.60`, `0.10`, `1.50`, `5.00`, or `1.30`. Every rate is looked up from `PRICING_DATA.ai_features.*` at runtime - by model (Cortex Complete, SI/Agents, Fine-tuning) or by feature name (Cortex Search, Cortex Analyst API, Document AI, AI Parse Document, AI utility functions). Periodic JSON updates now flow through automatically; no per-PR rate audit needed.
- **`SIZING_SPEC.growth_rates` array removed.** Replaced by `meta.annual_growth_rate` (single number) plus per-workload ramp fields. Year 2+ totals scale by `(1 + annual_growth_rate)^(year-1)`. Backward-compat shim absorbs legacy specs in `normalizeSpec()` (seeds defaults if missing). The `recalculate()` engine and `updateScenarios()` function were both rewritten to use the new model. `updateGlobal('contract_years')` no longer rebuilds a `growth_rates` array.
- **3-scenario rule rebased.** Conservative/Expected/Aggressive now shift `(curve, go_live_month, growth)` together: Conservative = `slow` curve + 1 month later go-live + 10% growth; Expected = `linear` + unchanged go-live + 20% growth; Aggressive = `fast` curve + 1 month earlier go-live + 35% growth. The cards display growth%/curve/go-live-month read-only; the canonical edit paths are the per-workload ramp fields and the Global Settings tab defaults.
- **Global Settings UI** swaps the single percentage-based "Ramp curve" select for three controls: Default Ramp curve (Slowest/Slow/Linear/Fast/Fastest/Manual), Dev start month (number 1-36), Go-live month (number 1-36). Changing any one propagates the new value to every workload row's matching field for one-click rebaseline. Annual growth is now stored on `meta.annual_growth_rate` (was implicit in the rebuilt `growth_rates` array).
- **`pricing.replication.compute_credits_per_TB`** documented with `default: 4`, `range: [3, 5]`, and the metadata-scan caveat. Sizing methodology now lists the credits/TB selection guidance by payload profile (large few-objects = 3, mixed = 4, many small objects = 5).
- **`assets/snowflake_pricing_master.json` bumped to version 2.2** with new top-level `ramp_curves` and `replication` keys. Existing keys unchanged.

### Fixed
- **`examples/acme-financial-3year-sizing.html` regenerated** against the new template. Per-workload ramp fields populated with varied curves (Data Ingestion=fast, ELT=linear, BI=slow, Ad-hoc=linear, Dev=fastest) to showcase the new model. A sample replication block is included (N. Virginia -> Oregon DR replica) so the new section renders in the example. Em-dash gate passes.
- **html-spec.md hardcoded AI rates audit** (lines 539, 540, 549, 552, 559) now sourced from `PRICING_DATA.ai_features.*`. The rate-update workflow is now: edit `assets/snowflake_pricing_master.json` only - the JS engine and the next plugin run pick up the change automatically.

---

## Round 4 unreleased — editable assumptions / removed print-help

### Added
- **Editable Stated Assumptions and Requires Confirmation sections.** Both lists in the generated proposal are now fully editable in the browser without re-running the skill. Each assumption renders as a `contenteditable` `<li>`; each confirmation item's text renders as a `contenteditable` `<span>` (the CONFIRM badge is non-editable). An `oninput` handler syncs every keystroke back to `SIZING_SPEC.assumptions[i]` / `SIZING_SPEC.confirm_required[i].item`. A `✕` delete button appears on hover per item (calls `removeAssumption(i)` / `removeConfirmItem(i)`). `+ Add Assumption` and `+ Add Item` dashed buttons append a placeholder entry, re-render the list, and focus+select the new item. All edit controls are hidden in `@media print`. `saveSnapshot()` requires no changes — it already serialises the full `SIZING_SPEC`, so edits are preserved on next save.
- `_selectAll(el)` helper selects all text in a newly-added item for immediate overtyping.

### Changed
- **`html-spec.md` Section 7** updated to document the `contenteditable` list items, add/delete controls, print behavior, and the JS helpers: `removeAssumption`, `addAssumption`, `updateConfirmItem`, `removeConfirmItem`, `addConfirmItem`, `_selectAll`.

### Removed
- **Print-help tooltip** (`ⓘ` icon next to the Print button). Removed the `.print-help` CSS block and hover/focus rules, the `<span class="print-help">` HTML element, the `print_help` entry from `FEATURE_TOOLTIPS`, and `.print-help` from all four tooltip event-listener selectors. The Print button `title` attribute already provides adequate browser-native hover text.

### Fixed
- `examples/acme-financial-3year-sizing.html` regenerated from the canonical template (`skills/snowflake-sizing/references/_template.html`) with all tokens substituted (including `__BRAND_FONTS_CSS__`) and fresh `generated_date`. Picks up editable assumptions, removed print-help, and all prior template improvements.

---

## Round 3 unreleased — tooltips / Save Version / scenario toggle / AI unit chips

### Added
- **Per-feature tooltips.** Every togglable feature (Cortex Complete, Snowpipe, Search Optimization, Cortex Code surfaces, AI Functions, etc.) renders with a small `ⓘ` (U+24D8) info icon next to its label. A custom JS tooltip with viewport-aware positioning shows a one-line explanation of what the feature is and how it bills. Hidden in print mode. A separate `ⓘ` next to the Print button explains how to disable Chrome's "Headers and footers" for a clean PDF — those bars are browser-injected and cannot be suppressed by CSS.
- **Save Version button.** Top-right of the proposal, next to Print. Reads the current `SIZING_SPEC` (with all SE edits), bumps `meta.version_number`, regex-replaces the sentinel-wrapped block in the page source, and triggers a browser download as `<slug>-<years>year-sizing-v<N>-<YYYY-MM-DD>.html`. The saved file is a self-contained snapshot that picks up auto-incrementing on subsequent saves.
- **Scenario toggle.** Single checkbox above the Scenario Comparison grid: `[x] Show Conservative & Aggressive scenarios` (checked by default). When unchecked, only the Expected card renders, centered via `.scenario-grid.only-expected` (`grid-template-columns: minmax(0, 480px); justify-content: center`).
- **Persistent unit chips on AI/Cortex inputs.** Every numeric input on the AI tab (Cortex Complete, Cortex Agents, Snowflake Intelligence, Cortex Code surfaces, Cortex Analyst, Cortex Search, Document AI, AI Functions, Embeddings) now carries a small grey unit chip to its right (e.g. `input M tok/mo`, `output M tok/mo`, `devs`, `q/dev/day`, `tok/q`, `msgs/mo`, `GB indexed`, `hrs/mo`). Chips stay visible after the placeholder disappears so the SE can always read what each box means. Input/output chips on Cortex Complete / Cortex Agents / Snowflake Intelligence are differentiated (`input M tok/mo` vs `output M tok/mo`).
- **Workloads tab group-header row** with live `cr/mo` total above the first workload card. Helper `groupHeaderRow(featureLabel, configLabel, unit, totalElId)`; live total updated by `updateGroupHeaderTotals()` from `recalculate()`.

### Changed
- **Cortex Code split into three independent surfaces.** `ai_cortex.cortex_code` is now `{ cli, snowsight, desktop }`, each entry `{ enabled, developers, queries_per_dev_per_day, avg_tokens_per_query }`. Same Table 6(e) blended rate (~$2.51/M tokens) across all surfaces, but SEs can model realistic per-surface usage (CLI light, Desktop heavy IDE assists). `normalizeSpec()` auto-migrates legacy single-object `cortex_code` specs (legacy values land on `cli`); `populateAIPanel()` renders three labeled rows; `calcAICredits()` iterates the three surfaces. SKILL.md Phase 3 + sizing-methodology.md documented with per-surface heuristics: CLI 5–20 q/dev/day · Snowsight 10–40 · Desktop 30–80; tokens/query 800–2,500.
- **`SIZING_SPEC` declaration wrapped with sentinel comments** (`/* __SIZING_SPEC_BEGIN__ */ ... /* __SIZING_SPEC_END__ */`) so `saveSnapshot()` can locate and replace the spec literal deterministically. The example regenerates with sentinels intact.
- **`meta.version_number` field added** to the spec (initialised to 1 by SKILL.md Phase 4). Save Version increments and embeds it; re-saving an already-saved file continues to bump the counter.
- **Print stylesheet polish.** `@page` margin 12mm → 15mm so any browser-injected date/title/URL bars land in the unprintable margin. New elements added to the print-hidden list: `.save-btn`, `.print-help`, `.scenario-toggle`, `.info-icon`, `#tt-tip`. The `<title>` already interpolates `__CUSTOMER__`, so when Chrome's header is shown it reads `<Customer> - Snowflake Consumption Estimate` rather than the file path.
- **AI row grid widened.** `.ai-row` `grid-template-columns` changed from `2fr 1fr 1fr 100px` to `2fr 1.1fr 1.4fr 1.4fr` so the chip-wrapped data inputs no longer crowd the input boxes.
- **All AI numeric inputs carry `min="0"`** to prevent negative-number entry. Other panels already had `min="0"` (or `min="1"` for cluster counts).
- **SKILL.md Phase 6 output summary** now points SEs to the in-page Save Version button and includes the Chrome "Headers and footers" tip alongside the existing Print / Save as PDF instructions.
- **html-spec.md** adds new sections: Per-feature Tooltips, Save Version Button, Group-header rows with units, Scenario Toggle, Browser-injected headers/footers (CSS limitation note). Replaces the legacy Cortex Code calc snippet with the three-surface version.
- **sizing-methodology.md** Cortex Code section expanded to three surfaces with rough per-developer usage heuristics.

### Removed
- The static `<p>No AI/Cortex features enabled in current scope. Enable specific functions below to model future expansion.</p>` at the top of the AI tab — it always rendered regardless of whether AI features were enabled.
- Group-header rows on Serverless / AI / SPCS / OpenFlow / Storage / Collaboration tabs (Workloads keeps its row). They duplicated information already in the KPI tiles and per-card calculations and ate vertical space.

### Fixed
- `examples/acme-financial-3year-sizing.html` regenerated against the latest template so the committed reference file picks up all of the above (sentinel comments, tooltips, Save Version, scenario toggle, AI unit chips, three-surface Cortex Code shape via `normalizeSpec()` auto-migration). Em-dash gate clean.

---

## Round 1 unreleased — CRUD UI / print / em-dash gate

### Added
- **Add/delete UI in the generated proposal.** SEs can now mutate the live HTML during a customer call without re-running the skill:
  - **Warehouses** — every workload card has an editable label and a `Delete` button; `+ Add Workload` appends a card with sensible defaults (M / 4 hrs / 22 days / 1 cluster).
  - **SPCS instances** — full edit form per instance (label, generation, instance type, count, hours/month) with `Delete`; `+ Add SPCS Instance` appends and auto-enables the panel.
  - **OpenFlow instances** — per-connector cards (label, deployment, source connections, vCPU, hours/month) with `Delete`; `+ Add OpenFlow Instance` appends. Master `Enable OpenFlow billing` toggle remains.
  - **Reader / Managed accounts** — list of accounts with type badge (`reader` or `managed`), per-card `Delete`, and two add buttons (`+ Add Reader Account`, `+ Add Managed Account`). Type is display-only; both bill via the same compute model.
- **Print / Save as PDF.** A floating `Print / Save as PDF` button (top-right, hidden in print mode) opens the browser print dialog. New `@media print` stylesheet hides interactive controls (sliders, add/delete buttons, tab nav), expands all configuration tabs in flow with explicit page breaks, renders each tab's title from `data-print-title`, and forces `print-color-adjust: exact` so the navy header and badge colours render in the PDF. Chart.js canvases are reflowed via `beforeprint`/`afterprint`/`matchMedia('print')` listeners so they don't clip at A4 width.
- **`assets/emdash-check.py`** — standalone validator that scans files for U+2014 and prints `file:line:col` for each occurrence. Source uses `chr(0x2014)` so the script itself stays em-dash-free.

### Changed
- **SIZING_SPEC schema migration.**
  - `openflow.{deployment, source_connections, vcpu_per_connection, hours_monthly}` → `openflow.instances[]` (each entry: `{ id, label, deployment, source_connections, vcpu_per_connection, hours_monthly }`).
  - `collaboration.reader_accounts` → `collaboration.accounts[]` (each entry: `{ id, type, label, warehouse_size, hours_per_day, days_per_month }` with `type` either `"reader"` or `"managed"`).
  - The template's `normalizeSpec()` IIFE auto-migrates legacy single-object specs on load, so existing dossiers and the committed `examples/acme-financial-3year-sizing.html` continue to render unchanged. Newly generated specs MUST emit the array form.
- `recalculate()` and `calcCollabCost()` rewritten to iterate the new arrays; new helper `calcOpenflowCost(cr, ramp)` sums across `openflow.instances[]`.
- **SKILL.md Phase 5 quality check is now BLOCKING** and includes the em-dash gate. After token substitution, the skill must run `python3 assets/emdash-check.py temp/<slug>-<N>year-sizing.html temp/<slug>-research-evidence.md` and replace any U+2014 with ` - ` until the gate exits 0 before reporting success.
- **SKILL.md Phase 6 output summary** now reports `emdash check: PASS` and points SEs to the in-page `Print / Save as PDF` button.
- **html-spec.md** documents the new SPCS / OpenFlow / Collaboration list shapes, the Warehouses add/delete pattern, and adds a `Print / PDF Layout` section describing the `@media print` rules and chart reflow strategy.

### Fixed
- Removed the two em-dash characters in `skills/snowflake-sizing/references/_template.html` (page `<title>` and the `:root` brand-tokens comment) so the Phase 5 em-dash gate passes on first generation without rewriting.

---

## Earlier (still unreleased)

### Fixed
- `assets/snowflake_pricing_master.json` — corrected hallucinated AI model entries (`gemini-3-pro` → `gemini-3.1-pro`, removed nonexistent `openai-gpt-5-chat` and `claude-4-opus`).
- Storage prices for AWS Frankfurt/Sydney/Singapore/Tokyo and Azure UK South / West Europe now match PDF Table 3(a).

### Added
- Full coverage of all 30+ tables from the May 12 2026 Snowflake Service Consumption Table:
  - Hybrid Tables Storage (3b), ECO Cache (3d), Cloud Storage Requests (3g)
  - Specific Endpoints (4d), Outbound Privatelink (4e)
  - REST API with Prompt Caching (6b), REST API OSS (6c)
  - Combined Snowflake Intelligence / Cortex Agents / Cortex Analyst (6d)
  - Cortex Code (6e), Provisioned Throughput (6h)
  - Openflow Connector for Oracle (7), Organization Usage tiers (8)
- Storage tables now include capacity tier rates (tier_1 through tier_7) per region.
- Region coverage expanded to 55 regions across AWS / Azure / GCP for credit pricing, storage, data transfer, and privatelink.

### Changed
- `storage.on_demand` → `storage.standard` (richer schema with tiers).
- `ai_features.{snowflake_intelligence,cortex_agents,cortex_analyst}` → single `ai_features.intelligence_agents_analyst` reflecting PDF restructure.
- `metadata.version` 2.0 → 2.1.

### Known follow-ups (out of scope)
- `skills/snowflake-sizing/references/html-spec.md` lines 539–540 hardcode 1.88/9.41 for Cortex Agents — update to read from JSON.
- `skills/snowflake-sizing/references/html-spec.md` lines 549, 552, 559 hardcode 67 (Cortex Analyst), 6.3 (Cortex Search), 3.40 (fine-tuning) — update to read from JSON.

---

## Unreleased

- **Snowflake branding applied to HTML output.** The generated sizing estimate now uses the official Snowflake wordmark (`logo-white.svg`), brand fonts Texta (titles) + Lato (body) + Source Code Pro (monospace) inlined as base64 data URIs, and the canonical colour palette (`#29B5E8`, `#249EDC`, `#11567F`, `#003545`, `#76D0F1`) extracted from snowflake.com. All charts use a monochromatic blue scale. Footer includes the Snowflake mark and "Snowflake Confidential" line. Brand assets are bundled in `assets/branding/`; the `build-snippets.sh` script regenerates the inlinable font CSS on demand.
- **Offline-capable documents.** Fonts and logo are fully inlined — the HTML renders correctly with Wi-Fi disabled (only Chart.js still requires `cdn.jsdelivr.net`).
- **Template-based HTML generation.** Phase 5 now reads `skills/snowflake-sizing/references/_template.html` and substitutes 11 tokens (`__BRAND_FONTS_CSS__`, `__SIZING_SPEC__`, `__PRICING_DATA__`, `__CUSTOMER__`, etc.) instead of generating HTML from scratch. This ensures consistent branding across all runs and reduces LLM output size.
- **Committed example output.** `examples/acme-financial-3year-sizing.html` is now tracked in git as a reference/demo file.

- **Research is now mandatory.** SKILL.md adds a new `Phase 1.5 — Preflight (BLOCKING)` that hard-fails if the Glean MCP is not configured or the SNOWHOUSE connection is unavailable. The previous `"skip this operation and continue with A + B only"` escape hatch is removed.
- **Phase 2 is now a MANDATORY CHECKPOINT.** All three research operations (context file + Glean B1/B2/B3 + Gong C1/C2) MUST execute. Mandatory two-attempt retry on empty Gong C1 lookups (substring, abbreviation, parent account).
- **New `Phase 2.5 — Report Research Findings (BLOCKING)`** writes a sidecar `temp/<slug>-research-evidence.md` audit trail (Glean hits, Gong call inventory, verbatim transcript turns, sizing-impacting findings) and prints a short summary before Phase 3 may begin.
- **Phase 3 SOURCED tags must cite a concrete artifact** (context-file line, Glean URL, or `Gong <conversation_key[:10]> turn <N> — <speaker>: "<verbatim>"`). ASSUMPTION is only allowed when all three sources are silent on the data point.
- **Narrow EXCEPTIONS clause** — research may only be reduced when `--skip-glean` / `--skip-gong` is explicitly passed and the user confirms in chat, or the customer is `internal-test` / `demo` / `POC-template`. The reduction is logged verbatim in the evidence file.
- **New `references/research-protocol.md`** holds the verbatim Glean queries, Gong SQL templates, retry-on-empty table, and evidence file template.
- **commands/snowflake-sizing.md** now lists Glean + SNOWHOUSE as prerequisites so users get the right setup error early.
