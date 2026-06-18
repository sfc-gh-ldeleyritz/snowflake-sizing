# Changelog

All notable changes to this project are documented here.

---

## [2.16.0] - 2026-06-08

### Added

- **Word (.docx) questionnaire generator** (`questionnaire/tools/build_questionnaire_docx.py`)
  — a customer-facing Word version of the sizing questionnaire, complementing the
  existing Excel generator (`build_questionnaire_xlsx.py`). Produces
  `questionnaire/snowflake-sizing-questionnaire.docx` from the same 45-question,
  11-category data set and the same Snowflake brand palette. Includes a branded
  cover page (logo, title, "How to answer" guidance, plugin version read from this
  CHANGELOG), then a single table with blue category-divider rows, a repeating
  dark-blue header, alternating row tint, and empty blue-shaded **Answer** and
  **Comments** cells. Since Word has no live dropdowns, enum and unit hints are
  rendered as grey guidance text inside each Answer cell (e.g. "Options: AWS /
  Azure / Google Cloud"). The internal Appendix A field mapping and the "Reason for
  Impact" column are omitted from the customer-facing document. Requires
  `python-docx`. Re-run with `python3 questionnaire/tools/build_questionnaire_docx.py`.

---

## [2.15.1] - 2026-06-08

### Fixed

- **Schema rejected the canonical three-surface `cortex_code` shape.**
  `framework/sizing_spec_schema.json` defined `ai_cortex.cortex_code` with only
  the legacy flat fields (`developers`, `queries_per_dev_per_day`,
  `avg_tokens_per_query`), `required: ["enabled"]`, and
  `additionalProperties: false`. But `compute_totals.py` (`cortex_code` →
  iterates `cli`/`snowsight`/`desktop`) and the proposal template both consume
  the three-surface form, and `references/ai-feature-defaults.md` instructs new
  specs to emit it. As a result a three-surface spec **failed schema validation**
  in `scripts/spec-prepare.py` and was blocked by the `hooks/sizing-guard.py`
  PreToolUse hook — the documented workflow was un-runnable, and it only worked
  in practice because every committed spec still used the flat form. The
  `cortex_code` schema now accepts **both** shapes (plus an optional top-level
  `model`), with `enabled` made optional so a pure three-surface spec validates;
  it remains `additionalProperties: false` so typos are still caught. Added a
  reusable `cortex_code_surface` definition for the per-surface objects.
  Backward-compatible: all existing flat fixtures, the example, and the skeleton
  placeholder (`{ "enabled": false }`) still validate.

### Changed

- **Docs** — `references/field-names.md` gains a "Cortex Code shape (two accepted
  forms)" section documenting the canonical three-surface form (`cli` / `snowsight`
  / `desktop` + optional `model`) and the legacy flat form (migrated onto `cli`
  by the template at render time).

### Tests

- **New schema-conformance regression** (`TestCortexCodeShapes` in
  `test_schema_conformance.py`) — locks in that the flat form, the three-surface
  form, and the `{ "enabled": false }` skeleton placeholder all validate, while an
  extra key on either the `cortex_code` object or a surface object is rejected.

---

## [2.15.0] - 2026-06-04

Aligned to plugin-scaffolder 3.1.0 canonical patterns.

### Changed

- **`commands/snowflake-sizing.md`** — Migrated to `skills/snowflake-sizing/SKILL.md`; `commands/` directory removed. Plugin now invoked via `$snowflake-sizing`. Drops the `commands` field from `plugin.json`.
- **`hooks/hooks.json` — hook matchers lowercased**: `"Write"` → `"write"` to match the canonical tool names the model emits.

### Added

- **`.cortex-plugin/plugin.json`** — Dual manifest so the plugin resolves under both the CoCo Desktop and SDK/CLI loaders.

---

## [2.14.0] - Python/JS growth parity, per-workload + AI growth, USD-only enforcement

### Fixed

- **Build-time `computed_totals` omitted the annual-growth factor the interactive
  render applied — the static TCV and the rendered headline disagreed.**
  `compute_totals.py::ramp_multiplier_for_year()` averaged the ramp but never
  multiplied by `(1 + growth) ^ (year − 1)`, while the template JS
  `rampMultiplierForYear()` did. On the Travelodge sizing this surfaced as
  `$394,565` in the JSON vs `$568,172` in the HTML. The Python helper now mirrors
  the JS exactly (year 1 = averaged ramp, years 2+ = full capacity × cumulative
  growth), so the embedded `computed_totals` equals the rendered TCV to the dollar.

- **A valid `dev_start_month: 0` was silently coerced to `2`.** The warehouse and
  default-window ramp lookups used `int(w.get("dev_start_month", default) or 2)`,
  and `0 or 2` evaluates to `2`. The JS uses `!= null` semantics, so every fixture
  with `dev_start = 0` (acme, feature-coverage, momentum, M&S, startup) had a
  year-1 warehouse/AI/serverless ramp that diverged from the render. Resolution is
  now centralised in `_resolve_ramp_window()` with the exact JS precedence
  (row → meta default → `0` / `3` / `linear`, honouring a literal `0`).

### Added

- **Per-workload growth (`workloads[].growth_rate`)** — an optional annual growth
  rate on a single warehouse row, overriding `meta.annual_growth_rate` (e.g. a
  fast-growing ML workload alongside a flat ELT workload).

- **AI growth (`meta.ai_growth_rate`)** — an optional, nullable growth rate for the
  AI/Cortex category; falls back to `meta.annual_growth_rate` when absent. Wired
  through both `compute_totals.py` and the template JS (`aiRamp`). Growth
  precedence everywhere: scenario band > per-workload `growth_rate` >
  `meta.annual_growth_rate` (default `0.20`).

- **USD-only currency enforcement.** The pre-write guard
  (`hooks/sizing-guard.py`) now rejects, on both the HTML and JSON write paths,
  non-USD currency symbols (£/€/¥), converted figures (`GBP 450,000`, `1.2M EUR`),
  and FX/conversion phrasing (`convert to`, `exchange rate`, `FX rate`,
  `indicative @`, …). A `confirm_required` note that merely *names* a billing
  currency is still allowed. A static "All figures in USD" caption was added to the
  proposal header and footer.

### Changed

- **`framework/sizing_spec_schema.json`** — declared optional `workloads[].growth_rate`
  (number 0–5) and `meta.ai_growth_rate` (nullable number); both schemas remain
  `additionalProperties: false`. `framework/sizing_spec_skeleton.json` seeds
  `meta.ai_growth_rate: null`.

- **Docs** — USD rule and the growth model (per-workload / AI / parity guarantee)
  documented in `SKILL.md`, `references/sizing-methodology.md`,
  `references/content-hygiene.md`, and `references/field-names.md`; README
  "Additional features" updated.

### Tests

- **New Python/JS growth-parity test** (`TestPythonJsGrowthParity` in
  `test_scenario_consistency.py`) — renders a fixture with all three growth knobs
  active (`annual_growth_rate`, `ai_growth_rate`, per-workload `growth_rate`), boots
  the real embedded JS via the Node sidecar, and asserts the JS headline equals the
  Python `core_tcv` to the dollar. Verified across all 12 fixtures: max divergence
  $0.48 (whole-dollar rounding only).

- **New `tests/test_sizing_guard.py`** — 16 tests covering the currency scanner and
  both guard write paths (blocks symbols / converted figures / conversion phrasing;
  allows USD figures and currency *names* in confirm notes).

- **Updated pins** — `test_acme_fixture_known_tcv` 341,858 → 466,553 (growth now
  applied); collaboration year-3 68,400 → 98,496 (growth on the full-ramp year);
  `feature-coverage-ai-serverless` 175,223 → 179,002 (the old value was a
  Python-only number from the `dev_start = 0` bug). Refreshed the M&S fixture's
  embedded `computed_totals` and cleaned `£` figures out of the acme fixture.

- Test count: 361 → 379 (all passing).

---

## [2.13.6] - Move OpenFlow runtime pricing into master spec; fix credits vs dollars

### Fixed

- **OpenFlow runtime vCPU-hour cost was treated as direct dollars instead of
  credits.** The v2.13.4 fix added `_OF_RUNTIME_RATE = 0.0225` as a hardcoded
  constant and placed the cost in a separate dollar bucket (bypassing the credit
  rate multiplier). `CreditConsumptionTable.pdf` Table 1(h) confirms the rate is
  **0.0225 Credits per vCPU per Hour**, not $/vCPU-hr. Fixed in both
  `calcOpenflowCost()` and `compute_totals.py::openflow_connector_monthly_credits()`
  to accumulate as credits (× `cr` → dollars).

- **HTML tooltip for OpenFlow incorrectly showed `$0.0225/vCPU-hr`.** Corrected
  to `0.0225 credits/vCPU-hr` to match the consumption table.

- **`openflow_connector_monthly_credits()` ignored `monthly_data_gb`.** The Python
  function only read `rows_per_day_M` (never written by the UI); ingest billing
  was always $0. Fixed to prefer `monthly_data_gb`, falling back to the
  `rows_per_day_M` conversion (mirrors the v2.13.2 fix on the HTML side).

### Changed

- **OpenFlow runtime pricing constants removed from `proposal-template.html` and
  `compute_totals.py`.** Both now derive the BYOC credits/vCPU-hr rate from
  `PRICING_DATA.openflow.data` at runtime, with a hardcoded fallback of 0.0225.

- **`assets/snowflake_pricing_master.json` — `openflow.sizes` added.** The
  runtime size tiers (Small = 1 vCPU, Medium = 4 vCPU, Large = 8 vCPU) are now
  defined in the master spec alongside the rate, giving both the HTML and Python
  engines a single source of truth.

---

## [2.13.5] - Fix silent $0 billing for cortex_code and SPCS; expand test coverage

### Fixed

- **`cortex_code` flat-format specs billed $0 despite `enabled: true`.** `compute_totals.py::ai_monthly_credits()` was migrated to a new per-surface schema (`cli`/`snowsight`/`desktop` sub-objects) but the JSON schema still defines — and enforces via `additionalProperties: false` — the original flat format (`enabled`, `developers`, `queries_per_dev_per_day`, `avg_tokens_per_query`). The per-surface loop found nothing and silently returned $0. Fixed by adding a flat-format fallback: when no surface sub-object matches and `enabled: true`, compute tokens from the top-level fields. Affected 4 fixtures: `feature-coverage-warehouses-3year`, `gsmai`, `momentum-group`, `travelodge`.

- **`feature-coverage-warehouses-3year` SPCS instances billed $0.** The fixture used old SPCS instance field names (`instance_type`, `generation`, `count`, `hours_monthly`); `compute_totals.py::spcs_monthly_credits()` reads the current names (`instance_family`, `num_instances`, `hours_per_day`, `days_per_month`). Updated fixture to use current field names — SPCS now correctly contributes 1,050 credits/month.

- **Discounted specs triggered a spurious `credit_rate mismatch` warning.** `pricing_validator.py` compared `meta.credit_rate` against the on-demand table without accounting for negotiated discounts. When `discount.enabled: true` and `meta.list_credit_rate` matches the expected rate, the credit_rate check is now skipped.

### Tests

- **New fixture `tests/fixtures/feature-coverage-ai-serverless-3year.json`** — synthetic 3-year AWS Enterprise spec (15% discount, `credit_rate: 2.55`) exercising 13 previously-uncovered compute paths: `cortex_fine_tuning`, `document_ai`, `ai_parse_document_layout/ocr`, `serverless_tasks_flex`, `hybrid_tables_requests`, `snowpipe_streaming_classic`, `open_catalog`, `logging`, `telemetry_data_ingest`, `archive_storage_retrieval`, `archive_storage_write`. TCV pinned at ~$175,223.

- **`test_acme_fixture_known_tcv`** tightened from a $200k–$600k sanity range to `pytest.approx(341_858, rel=0.01)`.

- **New `TestAiMonthlyCredits`** — direct numeric tests for `ai_monthly_credits()`: cortex_code flat-format regression, doubling-developers linearity, fine_tuning at known rate (500M tokens × 3.4 cr/M = 1700 cr), embeddings hardcoded rate (0.05 cr/M-token), all-disabled returns zero.

- **New `TestReplicationForYear`** — four tests for `replication_for_year()` math: year-1 includes initial TB, year-2 omits initial TB, storage cost positive, storage compounds year-over-year.

- **New `TestTransferMonthlyCost`** — seven tests for `transfer_monthly_cost()` math: same-region free, cross-region rate ($0.08/GB), egress rate ($0.154/GB), PrivateLink endpoints ($7.30/endpoint), PrivateLink TB processed, combined, all-disabled zero.

- **Reader-account billing test** added to `TestOtherCompute` — asserts reader-account collaboration cost is non-zero when `reader_accounts.enabled: true`.

- Test count: 329 → 361 (all passing).

---

## [2.13.4] - Fix OpenFlow Runtime size and nodes not affecting pricing

### Fixed

- **Changing Runtime size (Small/Medium/Large) or Runtime nodes on the OpenFlow
  tab had no effect on pricing.** `calcOpenflowCost()` only accounted for
  warehouse MERGE credits and Snowpipe Streaming ingest; it never read
  `runtime_size` or `runtime_nodes`. The billing model (`$0.0225/vCPU-hr`) was
  documented in the tooltip but not implemented. Fixed by adding runtime vCPU-hour
  cost as a direct-dollar accumulator (separate from credits, to avoid being
  multiplied by the credit rate): `vcpus × nodes × hours_monthly × $0.0225 × 12 × ramp`.

---

## [2.13.3] - Fix OpenFlow group header resetting to $0 on warehouse size change

### Fixed

- **OpenFlow group header showed $0 after changing Connector Type, Deployment, or
  Warehouse size (MERGE).** Those three selects call `updateOpenflowInstance()` —
  which runs `recalculate()` and correctly writes the totals into the DOM — then
  immediately call `populateOpenflowPanel()`, which rebuilds the entire container
  and overwrites the header with fresh zero values. No second `recalculate()` ran
  afterwards. Fixed by calling `updateGroupHeaderTotals()` at the end of
  `populateOpenflowPanel()` so any re-render of the panel restores the correct
  monthly credit and dollar totals.

---

## [2.13.2] - Fix SPCS, Collaboration, and OpenFlow tabs not updating pricing

### Fixed

- **SPCS tab changes had zero effect on pricing.** `calcSPCSCost()` was reading
  the legacy schema fields `instance_family`, `num_instances`, `hours_per_day`,
  and `days_per_month`, but the SPCS panel UI stores `instance_type`, `count`,
  and `hours_monthly`. All three fields resolved to `undefined`, so every SPCS
  instance always contributed $0 to the estimate. Fixed to read the current field
  names, with fallbacks to the legacy names for existing sizings.

- **Collaboration tab changes had zero effect on pricing.** `calcCollabCost()`
  was reading `SIZING_SPEC.collaboration.reader_accounts` (old single-object
  schema), but the Collaboration UI manages `SIZING_SPEC.collaboration.accounts[]`
  (an array populated by "Add Reader Account" / "Add Managed Account"). Any
  accounts added via the UI were invisible to the cost engine. Fixed to iterate
  `c.accounts`, with a fallback to the legacy `reader_accounts` object for old
  specs.

- **OpenFlow "Monthly data (GB)" had zero effect on pricing.** `calcOpenflowCost()`
  was reading `inst.rows_per_day_M`, which is never written by the UI. The
  "Monthly data (GB)" input updates `inst.monthly_data_gb`. Fixed to use
  `monthly_data_gb` directly, falling back to the `rows_per_day_M` conversion
  for any specs that still carry that legacy field.

---

## [2.13.1] - Fix PPTX "Serverless, AI & Other Compute" slide + export error handling

### Fixed

- **SPCS, OpenFlow, Data Transfer, and Collaboration costs always showed $0** on
  the "Serverless, AI & Other Compute" PPTX slide. `computeYearData()` computed
  these costs internally but only exposed their aggregate as `otherCost`;
  `_pptxComputedTotals()` hardcoded all four breakout fields to zero. Fixed by
  adding `spcsCost`, `openflowCost`, `transferCost`, and `collabCost` to the
  `yearData` row objects and wiring them through `pick()` in
  `_pptxComputedTotals()`. The Total row on that slide was also undercounting as
  a result — now correct.

- **Silent failure on PPTX export error.** `exportForPptx()` had no `try/catch`,
  so any error (JSZip CDN unavailable, XML parse failure, etc.) produced no
  user-visible feedback. Wrapped the build+download call in `try/catch` with an
  `alert()` on failure, consistent with the existing save-failure pattern.

---

## [2.13.0] - Remove the automated `--pptx` path (PPTX is browser-only)

### Removed

- **`--pptx` CLI flag** and the entire automated PPTX render path, which had
  been broken since `scripts/render-pptx.py`, `scripts/serve-pptx.py`, and the
  `renderer/pptx/` package were removed. PPTX is now produced **only** by the
  client-side **Export to PPTX** button in the proposal HTML, which builds the
  deck entirely in the browser from the in-page `SIZING_SPEC`.
- Deleted the dead/broken toolchain: `skills/snowflake-sizing/sub-skills/render-pptx/`,
  `scripts/pptx-qa-export.sh` (LibreOffice QA), `tests/test_pptx.py` (imported the
  missing `renderer.pptx` module), and `scripts/create-sizing-template.py` (broken
  base-deck generator depending on `renderer.pptx` + an external plugin).

### Changed

- Stripped the `--pptx` flag and stale render/bridge docs from
  `commands/snowflake-sizing.md`, `skills/snowflake-sizing/SKILL.md`, and
  `README.md`; each now documents PPTX as the in-browser button only.
- `hooks/sizing-guard.py` — removed the `sizing-pptx` path-kind branch (the
  agent no longer writes `.pptx` files).
- `framework/sizing_spec_schema.json` — tidied the top-level description to drop
  the stale `/export-pptx`, `/export-xlsx` mention and corrected the consuming-hook
  name to `hooks/sizing-guard.py`.

### Kept

- `assets/templates/proposal-template.html` (button + `pptxBuildFromSpec` +
  embedded `SIZING_BASE_TEMPLATE_B64`), `assets/templates/sizing-base-template.pptx`,
  `scripts/embed-pptx-assets.py` (the supported re-embed/maintenance path), and
  `scripts/html-render-check.mjs`.

---

## [2.12.2] - Slide 7 update + embed-pptx-assets script

### Added

- **`scripts/embed-pptx-assets.py`** — utility script that re-embeds
  `assets/templates/sizing-base-template.pptx` into `proposal-template.html`
  as the `SIZING_BASE_TEMPLATE_B64` base64 literal. Run after any edit to the
  PPTX template to keep the in-browser "Export to PPTX" export in sync.
  Usage: `python3 scripts/embed-pptx-assets.py` from the plugin root, then
  commit both files.

### Changed

- **Slide 7 (`understanding_costs`) updated** in
  `assets/templates/sizing-base-template.pptx`. The hand-authored
  "Understanding Your Snowflake Costs" content slide has been revised;
  `proposal-template.html` re-embedded accordingly.

---

## [2.12.1] - Fix "Click to add text" red-X placeholder on chart slides

### Fixed

- **Empty body placeholder visible on chart slides (slides 6 & 7).** `_buildYearChart`
  and `_buildDonut` clone the content donor slide, which carries a body content
  placeholder (`<p:ph/>`, `idx=1`). The previous code called
  `_setBodyParagraphs(bodies[0], [])` to clear its text, but the `<p:sp>` element
  remained in the XML. PowerPoint renders empty content placeholders as a large
  "Click to add text" box overlaid with a red X — covering the chart.
  Fixed by replacing the clear call with
  `_bodyShapes(doc).forEach(sp => sp.parentNode && sp.parentNode.removeChild(sp))`,
  which removes the placeholder shape entirely from the DOM before serializing, so
  only the injected `<p:graphicFrame>` (chart) occupies the body area.

---

## [2.12.0] - Browser-side PPTX generation (no local server required)

**"Export to PPTX"** now generates a Snowflake-branded `.pptx` directly in the
browser using JSZip — no local render bridge, no Python runtime, no
`scripts/serve-pptx.py` running in a terminal. Any SE can open the
self-contained HTML proposal, click the button, and download a ready-to-present
deck. The compiled HTML is fully standalone: the base template is embedded as
base64, JSZip is inlined, and all slide-building logic runs client-side.

Seven OPC/OOXML correctness bugs in the initial implementation were identified
by systematically diffing generated PPTXs against PowerPoint's repaired output
and fixed in this release. The deck now opens in PowerPoint on Mac without any
"found a problem with content" repair dialog.

### Added

- **`assets/templates/proposal-template.html` — browser-side PPTX generator.**
  `pptxBuildFromSpec(spec)` is a new async function that loads the base64-embedded
  `sizing-base-template.pptx` via JSZip, clones the 7 donor slides into 10
  generated slides (title, safe harbor, agenda, understanding costs, cost detail,
  year chart, donut chart, warehouse workloads, serverless/AI, closer), rewrites
  `presentation.xml`, `_rels/presentation.xml.rels`, `[Content_Types].xml`, and
  `docProps/app.xml`, then triggers a browser download. JSZip is inlined;
  no network requests are made.

- **`_fixZipVersionNeeded(bytes)` — ZIP spec compliance patch.**
  JSZip 3.x emits `version_needed=10` (1.0) on all entries including
  DEFLATE-compressed ones. The ZIP spec (and PowerPoint Mac) require
  `version_needed=20` (2.0) for DEFLATE. This function scans both the local-file
  headers (`PK\x03\x04`) and central-directory headers (`PK\x01\x02`) and patches
  any entry where `compress_method=8` and `version_needed=10`.

- **Slide builders** for each of the 10 output slides:
  `_buildTitle`, `_buildStaticSlide`, `_buildAgenda`, `_buildCostDetail`,
  `_buildYearChart`, `_buildDonut`, `_buildWorkloads`, `_buildServerlessAI`,
  `_buildCloser`. Charts use inline `<c:numCache>` / `<c:strCache>` data — no
  embedded Excel workbook required.

### Fixed

- **ZIP `version_needed` header (OPC compliance).** JSZip sets `version_needed=10`
  for DEFLATE entries; PowerPoint Mac validates this and triggered the repair
  dialog. Fixed by `_fixZipVersionNeeded` patching both header types after
  `generateAsync`.

- **Slide numbering and rId collision.** Generated slides started at `slide1.xml`,
  overlapping with the 7 donor slides still in the ZIP during build. Fixed by
  numbering generated slides from `slide8.xml` onward (`nextSlideNum =
  Object.keys(_DONOR_IDX).length + 1`). Slide rIds now start at
  `max(existing rIds) + 1` to avoid conflicts with slide-master and font rIds.

- **`docProps/app.xml` slide count not updated.** The base template had
  `<Slides>7</Slides>` (donor count). Fixed by replacing the `<Slides>` value,
  the `<vt:i4>` count in `HeadingPairs`, and the `<TitlesOfParts>` slide-title
  list with values derived from the generated slide set.

- **Orphaned `ppt/media/image18.png` (OPC violation).** The content donor
  (`slide5.xml.rels`) references `image18.png` via `rId2`. Both
  `_buildYearChart` and `_buildDonut` call `_stripRel(relsStr, 'rId2')` to swap
  in a chart relationship, removing the rels entry but leaving the image file in
  the ZIP with no referencing relationship — an OPC violation that PowerPoint
  repairs by deleting the file. Fixed by a general orphaned-media purge block
  that runs after all slide rels are finalized: scans every `.rels` file in the
  ZIP for `ppt/media/*` references and removes any media file not referenced.

- **`&amp;amp;` double-escape in `docProps/app.xml` titles.** The title
  extraction regex captured raw XML text (e.g. `Serverless, AI &amp; Other
  Compute`) and re-encoded it with `.replace(/&/g,'&amp;')`, turning `&amp;`
  into `&amp;amp;`. Fixed by decoding all five XML entities from the raw text
  before re-encoding for `app.xml`.

- **Duplicate `cNvPr id` in chart slides (OOXML schema violation).** `_injectChartFrame`
  assigned chart-frame shape IDs as `300 + chartIndex`. The content donor already
  has `<p:cNvPr id="302">` (`PlaceHolder 1`), so the second chart (donut,
  `chartIndex=2`, `id=302`) produced two shapes with the same id on `slide14`.
  Fixed by computing the shape ID dynamically: `max(existing cNvPr ids in xmlStr)
  + 1` instead of a fixed offset.

- **Empty `<p:txBody>` in chart slides (OOXML schema violation).** Chart slides
  call `_setBodyParagraphs(bodies[0], [])` to clear the donor body text. This
  removed all `<a:p>` elements and added none, leaving a `<p:txBody>` with no
  paragraphs. `CT_TextBody` requires at least one `<a:p>`. Fixed in
  `_setBodyParagraphs`: when `lines=[]` leaves the text body empty, a single
  paragraph is appended (proto paragraph cloned with all runs stripped) so the
  body satisfies the schema while remaining visually empty.

### Removed

- **`scripts/serve-pptx.py` — local render bridge** (deleted). The bridge is
  superseded by the browser-side generator. The "Export to PPTX" button no
  longer requires any local server.
- **`scripts/render-pptx.py`, `scripts/render-all-fixtures-pptx.py`** (deleted).
  CLI helpers for the now-removed Python PPTX path.
- **`renderer/pptx/` package** (deleted). `build_pptx.py`, `slides.py`,
  `charts.py`, `clone.py`, `inject.py`, `brand.py`. The browser-side generator
  replaces this entire package.

---

## [2.11.0] - Full compute-cost coverage in the PPTX deck (SPCS, OpenFlow, transfer, collaboration, replication)

The generated deck now reports the **entire** compute stack from the JSON spec,
not just warehouse / serverless / AI / storage. `framework/compute_totals.py`
(the authoritative math the renderer injects into both the HTML and the PPTX) is
extended with the previously JS-only categories — SPCS, OpenFlow + OpenFlow-Oracle,
data-transfer + PrivateLink, collaboration, and replication/DR — and the canonical
HTML template JS is brought back in sync, fixing field-name drift and a credit-rate
bug. The Serverless/AI slide and the cost-detail slide and charts now itemise these
categories so TCV reconciles end-to-end.

### Added

- **`framework/compute_totals.py` — other-compute stack.** New schema-keyed
  functions (`spcs_monthly_credits`, `openflow_connector_monthly_credits`,
  `openflow_oracle_cost_for_year`, `transfer_monthly_cost`,
  `collaboration_monthly_cost`, `replication_for_year`) feed five new per-year
  arrays (`spcs_cost_per_year`, `openflow_cost_per_year`,
  `data_transfer_cost_per_year`, `collaboration_cost_per_year`,
  `replication_cost_per_year`) plus `other_cost_per_year`. These are now included
  in `core_year_total` / `core_tcv`. All optional keys are guarded so lean specs
  stay at $0. SPCS rates resolve via the live calc block with a fallback to the
  static master tables. OpenFlow uses a pragmatic schema-driven model (warehouse
  MERGE credits + Snowpipe-Streaming ingest from `rows_per_day_M` via a documented
  bytes/row assumption); the BYOC infra/region/node topology the old JS assumed is
  dropped because it is not represented in the schema.
- **`renderer/pptx/slides.py` — itemised rows.** The Serverless/AI slide (now
  titled *Serverless, AI & Other Compute*) appends SPCS / OpenFlow / Data Transfer /
  Collaboration / Replication rows when non-zero (lean decks stay tight), and the
  *Cost Detail by Year* slide gains an **Other** row so its visible rows reconcile
  to the Total.
- **`renderer/pptx/charts.py` + `brand.py` — "Other" series.** The stacked-column
  chart and the category-mix donut add an *Other* series/slice (5th brand color)
  so the chart TCV matches the headline.
- **`tests/test_compute_totals.py` — coverage** for the new categories (presence,
  non-zero on the full fixture, `other == Σ categories`, total includes other,
  SPCS credit-rate scaling, collaboration subscriptions, lean-spec zero).

### Fixed

- **Credit-rate bug for SPCS & collaboration.** The HTML `computeYearData` added
  raw SPCS credits and reader-account credits to a dollar total without `× cr`,
  and `calcCollabCost` never counted native-app / marketplace subscriptions. SPCS
  now applies the credit rate and collaboration counts subscriptions in both the
  Python module and the HTML JS.
- **Schema field-name drift in the HTML JS.** `calcSPCSCost`, `calcOpenflowCost`,
  and `calcCollabCost` read fields that do not exist in schema-conformant specs
  (`generation/instance_type/hours_monthly/count`, `deployment/runtime_size/
  byoc_region/monthly_data_gb`, `collaboration.accounts[]`). They are rewritten to
  the real schema fields (`instance_family/num_instances/hours_per_day/
  days_per_month`, `warehouse_size/rows_per_day_M/warehouse_hours_monthly`,
  `reader_accounts/native_apps/marketplace`) and matched to the Python formulas.

### Known issue (pre-existing, out of scope)

- The Python `compute_core_totals` ramp model does **not** apply
  `meta.annual_growth_rate`, while the HTML live `recalculate()` does (and treats
  year 2+ as full-capacity). The PPTX (Python) and the live HTML headline therefore
  diverge on multi-year specs across *all* core categories — not just the new ones.
  This is unchanged by this release and tracked separately.

---

## [2.10.1] - Hand-authored "Understanding Your Snowflake Costs" slide preserved across re-bakes

The **Understanding Your Snowflake Costs** donor is now a hand-authored *One
Column Layout* content slide — a title, a "Pricing & sizing basis" subtitle, a
"Confidential" textbox, and Compute / Storage / Data-Transfer cost cards —
replacing the old Quote-Violet section divider that was cloned from the master
and text-swapped. Because this slide exists only in the committed base template
(not in the Snowflake master), the bake script now clones it from the committed
template and preserves it verbatim instead of regenerating (and clobbering) it.
No schema change; render output is unchanged for callers since the renderer
already duplicated the committed donor verbatim.

### Changed

- **`scripts/create-sizing-template.py` — understanding_costs sourced from the
  committed base template.** `main()` now loads the existing
  `sizing-base-template.pptx` and clones the `understanding_costs` donor from it
  (at its `BAKED_DONOR_ORDER` index) instead of from master idx 3, so a re-bake
  preserves the hand-authored cost-card slide byte-for-byte. A guard exits with a
  clear error if the committed template is missing or has fewer slides than the
  expected donor count (the slide cannot be recovered from the master). The
  per-donor log line now reports an honest source (`src=base[6]` vs
  `src=master[N]`), `_bake_understanding_costs` is now a no-op (the slide is
  complete and self-contained), and the `"understanding_costs": 3` entry was
  removed from `SRC_INDEX`. Module docstring updated accordingly.
- **`renderer/pptx/slides.py` — corrected stale comments.**
  `build_understanding_costs_slide` and its section header now describe the donor
  as the hand-authored One Column Layout content slide committed in the base
  template (duplicated verbatim), not a master-sourced section divider. Behavior
  unchanged.

---

## [2.10.0] - One-click PPTX export via a local render bridge

The proposal HTML's **"Export to PPTX"** button can now generate a real
`.pptx` in one click. A new stdlib-only bridge server, `scripts/serve-pptx.py`,
accepts the in-browser `SIZING_SPEC` over loopback HTTP, runs the same
`renderer/pptx/build_pptx.build()` path as the CLI, and streams the deck back
for the browser to download. When the bridge is **not** running the button
silently falls back to its previous behavior (downloading the spec JSON), so
emailed and standalone proposals are unaffected. No new dependencies; no schema
or template-rebake change.

### Added

- **`scripts/serve-pptx.py` — local PPTX render bridge.** A `ThreadingHTTPServer`
  (stdlib `http.server`) bound to `127.0.0.1:8765`, exposing `GET /health` and
  `POST /render-pptx`. The POST handler parses the request body as a
  `SIZING_SPEC`, calls `build(spec, pricing)` with **no** `out_path` (returns
  bytes only — nothing is written to disk), and replies with the deck as
  `application/vnd.openxmlformats-officedocument.presentationml.presentation`.
  Pricing is loaded once at startup from `assets/snowflake_pricing_master.json`
  (overridable via `--pricing`); because `build()` deep-copies before stripping,
  the in-memory pricing dict is reused safely across requests. Flags: `--port`
  (default 8765), `--host` (default `127.0.0.1`), `--open <html>`, `--no-open`.
  Malformed JSON returns `400`; a build exception returns `500` with the
  traceback text so the SE can fix the spec. Every response sets
  `Access-Control-Allow-Origin: *` (plus an `OPTIONS` preflight handler) so a
  `file://` proposal (`Origin: null`) can read the binary response; the button
  posts a safelisted `text/plain` content-type to avoid a preflight on the hot
  path.

### Changed

- **`assets/templates/proposal-template.html` — button wired to the bridge.**
  `exportForPptx()` is now `async`: it POSTs the current `SIZING_SPEC` to the
  bridge and, on success, downloads `<slug>-...-v<n>-<date>.pptx`. A shared
  `triggerDownload()` helper performs the blob download. On a network error or
  30s `AbortController` timeout it silently falls back to the JSON download via
  `downloadSpecJson()`; on an HTTP error from a running bridge it surfaces the
  server message via `alert()` and still drops the JSON as a safety net. The
  button **label is unchanged** ("Export to PPTX"); only its tooltip is
  updated to explain the bridge-vs-JSON behavior. Authoritative `computed_totals`
  and internal-pricing stripping happen server-side inside `build()`, so a
  browser-edited (possibly stale) `computed_totals` block cannot affect the deck.
- **`render-pptx` sub-skill SKILL.md** documents the one-click bridge: start
  `scripts/serve-pptx.py`, click the button for a direct `.pptx`, with the JSON
  fallback when the service is down.

---

## [2.9.1] - Vertical floating-button stack in the proposal HTML

Cosmetic refinement to `assets/templates/proposal-template.html`: the three
floating action buttons that v2.4.0 / v2.5.0 laid out as a horizontal top-right
row (each individually `position: fixed` at a hand-tuned `right` offset) now
stack **vertically** in a single flex container. No schema, script, or behavior
change — the `onclick` handlers (`exportForPptx()`, `saveSnapshot()`,
`window.print()`) and tooltips are untouched.

### Changed

- **Floating buttons are now a vertical flex stack.** A new `.fab-stack`
  container (`position: fixed; top/right: 16px; z-index: 1000; flex-direction:
  column; gap: 8px; align-items: stretch`) owns the positioning; the per-button
  rules (`.print-btn` / `.save-btn` / `.pptx-btn`) drop their individual
  `position/top/right/z-index` and keep only colors, borders, and shadows, with
  the shared `padding`/`border-radius`/`font` lifted onto `.fab-stack button`.
  `align-items: stretch` makes all three equal width, retiring the brittle
  16 / 185 / 355px `right` offsets that previously kept the row from overlapping.
  DOM order top-to-bottom is **Export to PPTX → Save HTML → Print / Save
  PDF**.
- **Two buttons renamed.** "Export for PPTX" → **"Export to PPTX"** (makes
  it explicit that the button downloads the sizing spec as JSON, not a deck);
  the v2.4.0 **"Print / Save as PDF"** label is shortened to **"Print / Save
  PDF"**. **Save HTML** is unchanged.
- **`@media print` hide rule** now lists `.fab-stack` in place of the three
  individual `.print-btn, .save-btn, .pptx-btn` classes, so the whole stack
  stays hidden in printed / exported PDF output.

---

## [2.9.0] - PPTX cost-mix doughnut, scenario comparison, and per-year ACV totals

Adds two toggleable slides to the native PPTX deck and surfaces per-year ACV
(annual contract value) on the year-by-year slide. Everything renders on the
existing v2.8.0 donors (`content`, `table_styled`) — **no template rebake, no
schema change**. The deck is now **up to 10 slides** (6 with all toggles off);
both new slides default ON via a `meta` flag.

### Added

- **Cost Mix doughnut (slide 6, `build_workload_donut_slide`)** — a native
  `DOUGHNUT` chart in `charts.py:add_workload_donut`. Primary mode plots each
  workload's Year-1 warehouse credits ("Compute Mix by Workload"); with fewer than
  two workloads it falls back to the Compute/Serverless/AI/Storage cost mix ("Cost
  Mix by Category"). Slices are colored per data point via a new `_color_points()`
  helper. Toggle: `meta.include_workload_donut`.
- **Scenario Comparison (slide 9, `build_scenario_slide`)** — a Conservative /
  Expected / Aggressive TCV table that re-runs the SAME `compute_core_totals()`
  engine on a deep-copied spec. Levers are a go-live month shift plus a RELATIVE
  ramp-curve step along `fastest < fast < linear < slow < slowest`, so TCV is
  always monotone **Conservative <= Expected <= Aggressive**. The Expected row reuses
  the authoritative `computed_totals`, so its TCV equals the deck headline exactly;
  it is bolded via the new `fill_table(bold_row_index=...)` keyword. Optional
  `spec.scenarios` (`{label, go_live_delta, curve_steps}`) overrides the defaults.
  Toggle: `meta.include_scenarios`.
- **Per-year ACV totals on the Year-by-Year slide** — `build_year_chart_slide`
  now sets the subtitle to each year's ACV (= `core_year_total[y]`) in dollars
  via `_acv_subtitle`, exact for terms up to 3 years and abbreviated beyond that
  so the line stays on one line and does not wrap into the chart.
- **`inject.fill_table(..., bold_row_index=...)`** — bolds a single highlighted
  row (reuses `_bold_row`), mirroring `bold_last_row`.
- **`tests/test_pptx.py`** — content + toggle tests for the doughnut and scenario
  slides, a per-year-ACV assertion, a `_shift_curve` unit suite, a
  scenario-monotonicity regression on the `healthcare-bc-slowramp`
  (`slowest`-baseline) fixture, and a `set_body_paragraphs` font-size unit test.

### Fixed

- **`inject.set_body_paragraphs(font_size=Pt(...))`** rendered text at the EMU
  value (e.g. `Pt(14)` -> 2032pt, whose giant bullet glyphs filled the slide as a
  blue "mosaic"). pptx `Length` subclasses `int`, so the `isinstance(font_size,
  int)` branch caught Pt/Emu/Inches and read their EMU integer as centipoints; the
  check now tests `Length` first and converts via `font_size.pt * 100`.

### Changed

- **`build_pptx.py`** threads `pricing` into the donut + scenario builders, reads
  the two new `meta` toggles (default true), wires the builders in deck order, and
  updates the slide-order docstring (up to 10 slides). `slides.py` module docstring
  and `_AGENDA_SECTIONS` updated to match.
- **`render-pptx/SKILL.md`** documents the 10-slide deck map, the toggles, the
  doughnut modes, the per-year ACV subtitle, and the scenario-engine consistency
  invariant; the visual-QA checklist and expected slide count are refreshed.

---

## [2.8.0] - PPTX deck styling & layout refinements

Polishes the native PPTX deck after design review: de-blues the styled tables to
white data rows, reorders the content slides to lead with costs, and drops the
redundant Executive Summary slide. The deck is now **8 slides** (6 with both the
safe-harbor and agenda toggles off), down from 9.

### Added

- **`inject.fill_table(..., data_row_fill=...)`** — a new keyword that recolors
  every data row (all rows after the header) via a new `_set_cell_fill()` helper,
  which rewrites each cell's existing `a:solidFill` in place (schema-order-safe)
  and leaves the header fill and the cells' light-gray bottom borders (the row
  gridlines) untouched. The three styled-table builders pass `"FFFFFF"`.
- **`tests/test_pptx.py`** — `test_data_rows_white` (header stays `11577F`, first
  data row is `FFFFFF`) and `test_no_exec_summary_slide`.

### Changed

- **Styled tables now read white.** The slide-19 donor ships all-blue rows
  (`29B5E8`); the cost-detail, warehouse-workloads, and serverless tables now
  render white (`FFFFFF`) data rows under the navy (`11577F`) header, with the
  donor's light-gray (`C8C8C8`) horizontal gridlines preserved and bold **Total**
  rows on the cost-detail and serverless tables.
- **Content slides reordered** to Cost Detail by Year → Year-by-Year chart →
  Warehouse Workloads → Serverless & AI / Cortex — updated in the `build_pptx.py`
  build order and the `slides.py` builder defs + section comments, with the agenda
  list and both module docstrings updated to match.
- **`scripts/create-sizing-template.py`** bakes the white data row into the
  committed `assets/templates/sizing-base-template.pptx` (`_bake_table_styled`),
  so the template's standalone styled table matches the rendered decks, and its
  baked agenda scaffolding matches the new section order. Template regenerated.

### Removed

- **Executive Summary slide** (`build_exec_summary_slide` plus its build call and
  import); the agenda no longer lists it.
- **Two now-unused donor slides** dropped from the base template, taking it from
  **8 → 6 donors** (`title`, `agenda`, `safe_harbor`, `table_styled`, `content`,
  `thank_you`): `four_column_numbers` (the former Executive Summary donor) and
  `two_column` (long unused — the serverless slide uses `table_styled`). Because
  donors are resolved by bake-order index, this was a lock-step change across the
  reader (`clone.BAKED_DONOR_ORDER`) and writer (`create-sizing-template.py`:
  `SRC_INDEX`, `_FOOTER_KINDS`, `_BAKERS`, and the `_bake_four_column` /
  `_bake_two_column` helpers + their sample-text constants), then a template regen.

### Notes

- The PPTX renderer is donor/clone-based: `build_pptx.py` duplicates pre-baked
  designer "donor" slides and injects content via `inject.py`, then deletes the
  donors — so these are content/layout refinements on that pipeline, not a new
  renderer.
- Slide-count test baseline dropped 7 → 6 (default deck 9 → 8).
- Validated: `scripts/render-pptx.py` on the acme fixture (8 slides, correct
  order, white rows + navy headers + bold totals, no Executive Summary, zero
  `29B5E8` data cells); LibreOffice PDF eyeball; full suite **351 passed**.

---

## [2.7.0] - pricing freshness automation & per-sizing pinning

Keeps pricing as fresh as possible for every service with a cache fallback, and
makes each delivered sizing reproducible. Calculator-backed rates auto-refresh
under guards; PDF-only sections are monitored (detect-only) so a human can update
them; every sizing pins the exact pricing it used.

### Added

- **`framework/pricing_checks.py`** — the structural + range guards (credit ∈ [1,10],
  storage ∈ [15,60], AI credit ∈ [1.5,2.5], Gen1 doubling, calc price types, static
  sections) factored into one importable `check_pricing()` shared by the CLI and the
  seed-refresh gate.
- **`scripts/refresh-seed.py`** — guarded auto-refresh of `assets/live_pricing_seed.json`:
  fetch live → run the guards → write **only** if they pass and the content changed;
  otherwise keep the last-good seed. `--dry-run` reports without writing.
- **`scripts/check-pdf-freshness.py`** — detect-only check that parses the `Effective:`
  date from the legal *Service Consumption Table* PDF and compares it to the master's
  `metadata.effective_date` (exit 0 in-sync / 1 stale / 2 skipped). Never edits the master.
- **`.github/workflows/pricing-refresh.yml`** — weekly + manual workflow: commits a
  guarded seed refresh, and opens/updates a GitHub issue when the PDF is newer than the
  master. Alerting is CI-only (no render-time staleness warnings).
- **Per-sizing `pricing_snapshot`** — `spec-prepare.py` stamps pricing provenance
  (master/calc dates, container id, source URLs, SHA-256) and writes a
  `sizings/<slug>.pricing.json` sidecar with the exact merged pricing. Documented in
  `framework/sizing_spec_schema.json`.
- **`live_pricing.build_pricing_snapshot()` / `pricing_sha256()`** — provenance helpers
  reused by spec-prepare and render.
- **`render-html.py --latest` / `--repin`** — render against fresh live pricing one-off,
  or refresh the pin.
- **Tests:** `tests/test_pricing_freshness.py` (21 cases) covering the guards, the
  refresh gate, PDF date parsing/decision, and snapshot pinning / reproducibility.

### Changed

- **`spec-prepare.py`** now builds totals against the merged live calculator pricing
  (live → cache → seed → master, `--offline` to force deterministic) instead of the
  static master alone, and returns the pricing it used so the CLI can pin it.
- **`render-html.py`** resolves pricing as: explicit `--pricing` > `--latest`/`--repin`
  fresh fetch > pinned sidecar (reproducible) > live/seed fallback, with a SHA-256
  integrity check on the pinned sidecar.
- **`verify-pricing-json.py`** is now a thin CLI over `framework/pricing_checks.py`
  (identical output and exit codes).

### Notes

- **Scope of "always latest":** calculator-backed rates (warehouse / credit / storage /
  AI credit / SPCS) refresh **automatically** under guards. PDF-only sections
  (`ai_features` token rates, serverless, OpenFlow, Postgres, replication, …) are
  **detect-only** — the workflow flags staleness but a human still hand-updates the
  master, so the lag is minimized, not eliminated.
- **Reproducibility:** a pinned re-render matches the original to the dollar; only the
  wall-clock `computed_at` / `generated_at` provenance stamps differ between runs.
- `computed_totals` is now documented in `framework/sizing_spec_schema.json` alongside
  the new `pricing_snapshot` (both optional; top-level `additionalProperties` already
  permitted them).
- The committed **seed and master are unchanged** by this release — only the tooling,
  CI, and pinning are added. `sizings/<slug>.pricing.json` sidecars are git-ignored
  local artifacts.
- Validated: `verify-pricing-json.py --offline` (0 warnings), `check-pdf-freshness.py`
  (in sync: master = PDF = 2026-05-29), `refresh-seed.py --dry-run` (guards pass, seed
  untouched); full non-pptx suite **322 passed**, including 21 new freshness tests.

---

## [2.6.1] - pricing data refresh (Service Consumption Table, May 29, 2026)

Refreshes `assets/snowflake_pricing_master.json` against the latest Snowflake
Service Consumption Table (Effective May 29, 2026). Gap analysis in
`temp/gap-report.md`. Data-only; no code changes.

### Added

- **claude-opus-4-8** across all four AI rate tables: Cortex AI Functions 6(a)
  (3.00 / 15.00, preview), SI/Agents/Analyst 6(d) (3.25 / 16.26 / 4.07 / 0.33),
  Cortex Code 6(e) (2.75 / 13.75 / 3.44 / 0.28), and REST API w/ caching 6(b)
  (AWS Regional 5.50 / 27.50 / 6.88 / 0.55 and AWS Global 5.00 / 25.00 / 6.25 / 0.50).
- **New 6(a) models:** gemini-3.5-flash (0.90 / 5.40), qwen3-32b (0.09 / 0.36),
  qwen3-next-80b-a3b (0.09 / 0.72), qwen3-vl-235b-a22b (0.32 / 1.60) — all preview.
- **openai-gpt-5-mini Azure Global** (0.25 / 2.00) added to REST API 6(b).
- **Table 6(g) "Other":** twelvelabs-pegasus-1-2 and twelvelabs-marengo-embed-3-0
  (multi-unit video/audio/image/text pricing).
- **AWS Asia Pacific (New Zealand)** region added across all 9 per-region tables
  (credit pricing 2a; storage standard/hybrid/SPCS-block/archive/Postgres/requests
  3a–3g; data transfer 4a and Outbound PrivateLink 4e), bringing region coverage to 56.

### Changed

- **Snowpark-Optimized MEMORY_16X** gains the **6XL = 768** column (Table 1c).
- **metadata:** effective_date 2026-05-12 → 2026-05-29, regions_covered 55 → 56,
  version 2.3 → 2.4, last_updated → 2026-05-31.

### Notes

- The legacy **claude-4-sonnet** row was removed from Tables 6(d)/6(e) in the
  May 29 SCT but is intentionally **retained (flagged legacy)** here to preserve
  backward selectability for existing sizings; it remains in 6(a) legacy and 6(b).
- The live-pricing **seed is unchanged**: `live_pricing.load_pricing()` reads
  `ai_features` (and all static sections) from the master and only attaches the
  `calc` block from the live/cache/seed source, so the AI additions take effect
  at render time directly from the master.
- Validated: `verify-pricing-json.py --offline` (0 warnings); full suite 315 passed.

---

## [2.6.0] - live pricing from the Snowflake calculator

### Added

- **Live pricing fetch.** New `framework/live_pricing.py` fetches the public
  Snowflake pricing calculator at render time. It scrapes the calculator page for
  its version-specific JSON endpoints (`pricing` + `regions`), fetches and parses
  them, and attaches them natively under a `calc` namespace via `merge_pricing()`.
  Endpoint discovery falls back to pinned URLs; the whole fetch falls back through
  a runtime cache (`assets/live_pricing_cache.json`, git-ignored) and a committed
  offline seed (`assets/live_pricing_seed.json`) to the static master, so a fresh
  clone always renders deterministically offline. CLI: `--refresh`,
  `--write-seed`, `--print-endpoints`, `--offline`.
- **Native-shape accessor layer.** `framework/calc_access.py` (Python) and a
  matching `PricingData` adapter inside `assets/templates/proposal-template.html`
  (JS) are the single source for reading rates from the `calc` block:
  `credit_rate`, `storage_rate`, `ai_credit_rate(s)`, `warehouse_credits`
  (gen1/gen2/snowpark + memory config), `spcs_families`/`spcs_credit`,
  `ai_token_rate`/`ai_models`, `calc_regions`, `region_product_families`.
- **Warehouse feature parity.** Workload cards gain a **Warehouse Type** selector
  (Standard Gen1 / Standard Gen2 / Snowpark-Optimized) with a memory-config picker
  for Snowpark, and the size dropdown now offers **5XL/6XL** for Gen1. Schema adds
  optional `gen`, `warehouse_type`, `memory_config` to each workload.
- **SPCS gen2 from live calculator.** The SPCS tab's gen2 families now come from
  the live SPCS compute pools (HIGHMEM_X64 / CPU_X64 / GPU) with their credit rates,
  replacing the static `spcs.spcs_gen2` table (legacy per-cloud lookup retained as a
  fallback). SPCS is JS-only, so there is no Python/JS drift risk.
- **`scripts/derive-rates.py`.** Phase 1 helper that resolves credit / AI-credit /
  storage rates (and available editions) for a cloud-region-edition from the live
  calculator, replacing hand-reading of the pricing JSON.
- **Region/edition availability check.** `validate_pricing()` now warns when a
  spec's edition is not offered in its region per the live `regions.json`
  `product_families`.
- **Tests.** New `tests/test_live_pricing.py` (fetch parsing, merge, accessors,
  offline fallback — network-free) plus calc-path coverage added to
  `test_compute_totals.py`, `test_pricing_validation.py`, and
  `test_schema_conformance.py`. A new `tests/fixtures/feature-coverage-warehouses-3year.json`
  exercises 6XL, Gen2, Snowpark-Optimized (memory configs), and live SPCS families
  (GPU / HIGHMEM); `test_golden_files.py` now renders fixtures against the
  offline-merged (calc) pricing — matching `render-html.py` — so those features are
  validated through the full render pipeline. Suite is now 315 passing.

### Changed

- **The 5XL/6XL = 1-credit bug is fixed.** `compute_totals.py` and the template JS
  now derive warehouse credits/hour through the accessor layer
  (`warehouse_credits()` / `whRate()`), so 5XL bills 256 cr/hr and 6XL 512 cr/hr
  (previously both silently fell through to 1). The static `WH_CREDITS` table is
  retained only as an offline fallback. Gen1 XS–4XL values are unchanged, so
  existing sizings are unaffected.
- **`pricing_validator.py`** lookups (`lookup_credit_rate`, `lookup_storage_rate`,
  `lookup_ai_credit_rate`) read the live `calc` block when present, falling back to
  the flattened tables — verified rate-for-rate identical to the static master for
  every bundled fixture.
- **`scripts/render-html.py`** defaults to a live fetch; `--offline` skips the
  network and `--pricing PATH` pins an explicit pricing JSON for deterministic
  tests / reproductions.
- **`render-all-fixtures-html.py`** renders fixtures `--offline` by default (against
  the committed seed) for deterministic, network-free smoke tests; `--live` opts in.
- **`scripts/verify-pricing-json.py`** rewritten from ~1000 lines of pinned exact
  values to structural + range sanity checks over the merged pricing (price types
  present, credit ∈ [1,10], storage ∈ [15,60], AI credit ∈ [1.5,2.5], Gen1 credits
  double per size step, Gen2/Snowpark/SPCS present and positive).
- **`SKILL.md`** Phase 1 now derives rates via `scripts/derive-rates.py`.

### Notes

- Cortex Complete / Cortex Analyst LLM **token** rates are not published by the
  calculator and remain sourced from the static `ai_features` tables (which are
  more complete than the calculator's model lists), keeping the Python first-load
  KPIs and the in-page JS recalculation in lockstep.

---

## [2.5.0] - native PPTX export (Snowflake-branded deck)

### Added

- **Native PowerPoint export.** A new `renderer/pptx/` package generates a Snowflake-branded `.pptx` deck directly from a sizing spec JSON, with no LibreOffice/Office dependency. `brand.py` holds the canonical Snowflake brand constants (palette, fonts), `charts.py` builds native python-pptx charts straight from the `computed_totals` arrays (editable in PowerPoint, not rasterized images), `slides.py` assembles the individual slides, and `build_pptx.py` is the public entry point.
- **Authoritative numbers, recomputed.** `build_pptx.py` re-runs `compute_core_totals()` against the spec rather than trusting any pre-baked figures, so the deck always reflects the canonical cost math.
- **`scripts/render-pptx.py` CLI.** Loads the spec JSON, builds the deck, and performs a sanity check that the output begins with the `PK` ZIP magic bytes (a valid `.pptx` is a ZIP container).
- **`scripts/pptx-qa-export.sh`.** A QA helper that renders the bundled fixtures to PPTX for visual inspection.
- **`render-pptx` sub-skill.** New `skills/snowflake-sizing/sub-skills/render-pptx/` wiring so the deck can be produced as part of the sizing workflow.
- **"Export for PPTX" button** in `assets/templates/proposal-template.html` and a matching `--pptx` flag on the `snowflake-sizing` command.
- **Unit tests.** `tests/test_pptx.py` covers the generator engine; the full suite is now 248 passing.

### Changed

- **`hooks/sizing-guard.py`** updated to allow the new pptx source/script paths.
- **`skills/snowflake-sizing/SKILL.md` and `commands/snowflake-sizing.md`** updated to document and wire the render-pptx sub-skill and the `--pptx` flag.

---

## [2.4.0] - remove one-click Download PDF; native Print is the sole PDF path

### Removed

- **The one-click "Download PDF" button and its `html2pdf.js` pipeline.** The
  `.pdf-btn` button, the `downloadPDF()` function, the html2pdf CDN `<script>`,
  and the entire screen-mode `body.pdf-export` CSS block (the maintenance-pair
  twin of `@media print`) are all deleted. Rasterizing the live DOM with
  html2canvas was fragile across browser widths and duplicated a whole CSS
  block; the native print dialog produces a cleaner, vector PDF with no extra
  dependency.
- **The headless PDF eval harness** that existed only to exercise that pipeline:
  `scripts/pdf-export-eval.mjs`, `scripts/pdf-whitespace-check.py`,
  `scripts/pdf-layout-judge.py`, `scripts/run-pdf-eval.sh`, plus the `package.json`
  / `package-lock.json` / `node_modules/` they pulled in (and the matching
  `.gitignore` lines). `scripts/render-all-fixtures.py` is retained.

### Changed

- **Native print-to-PDF is now the sole, primary export path.** The remaining
  Print button is renamed **"Print / Save as PDF"** and promoted to the primary
  navy style at top-right (the old Download PDF slot); **Save HTML** stays as the
  secondary white button and shifts left to clear the wider label.
- **`@media print` pagination hardened.** `.section` keeps its earlier fix of
  *not* using `break-inside: avoid` (a section is frequently taller than one A4
  page, so the constraint only produced a large dead gap before splitting anyway).
  The small indivisible inner units that previously only carried these
  protections inside `body.pdf-export` are now protected directly in `@media
  print`: `break-inside: avoid` on `.kpi-tile`, `.chart-row`, `.chart-container`,
  and `.year-table tr`, plus `break-after: avoid` on `.year-table thead`.
- **Kept the on-screen side-by-side chart layout in print.** `@media print` no
  longer collapses `.chart-row` to a single column; it inherits the base 2fr/1fr
  grid (stacked bar + donut, same as on screen). Collapsing to one column left the
  donut canvas at its stale on-screen size and overflowed it onto the Year-by-Year
  table. `.chart-container` also gets `min-width: 0` (prevents a grid-track blowout
  pushing the donut column off the page edge) and `overflow: hidden` (clips any
  residual canvas overflow to its own cell rather than the table).

---

## [2.3.0] - editable per-workload sourcing notes

### Added

- **The per-workload "SOURCED:" line is now editable and deletable**, mirroring
  the Stated Assumptions / Requires Confirmation lists. In `populateWorkloadCards()`
  the static `.justification` div became an editable `noteBlock`: the source label
  (`w.source`, e.g. `SOURCED` / `ASSUMPTION`) and the note text (`w.justification`)
  are both `contenteditable` (the colon stays outside the editable label), and a
  hover-revealed `✕` button (the shared `.item-delete-btn`) deletes the note. When a
  note has been deleted the card shows a dashed **"+ Add sourcing note"** button
  (the shared `.add-item-btn`) so it can be restored — matching the Add affordance
  the other editable lists already have.
- **`updateWorkloadNote()` / `removeWorkloadNote()` / `addWorkloadNote()` helpers.**
  `updateWorkloadNote` writes `source`/`justification` straight to the spec on
  input/blur with no `recalculate()` (the note is text-only and does not affect cost
  math, and skipping the re-render keeps inline-edit focus). `removeWorkloadNote`
  sets `justification = null` (the deleted state) and re-renders; `addWorkloadNote`
  seeds `source: 'SOURCED'`, re-renders, and focuses the new field.

### Changed

- **CSS for the editable note.** Added hover/focus styling for the note's
  `contenteditable` regions, a `.justification:hover .item-delete-btn` reveal rule,
  and `.justification.note-empty` handling. The empty-note "+ Add sourcing note"
  affordance is hidden in `@media print`, so a deleted note leaves no empty
  bordered block in the printed/exported PDF.

---

## [2.2.1] - Expected scenario locked to Year-by-Year TCV

### Fixed

- **Expected scenario card no longer drifts from the Year-by-Year Breakdown.**
  `updateScenarios()` computed the Expected TCV with a structurally different
  model than `recalculate()`: it forced every workload through a single synthetic
  go-live window (`default_go_live_month + shift`) instead of each workload's own
  `dev_start`/`go_live`/`ramp_curve`, omitted the entire `otherCost` stack
  (SPCS/OpenFlow/Oracle/transfer/collab/replication), and rounded the growth rate.
  On the acme-financial fixture the Expected card showed **$496,090** against a
  Year-by-Year headline of **$466,553**. The per-year calculation is now extracted
  into a single `computeYearData(opts)` engine; `recalculate()` calls
  `computeYearData(null)` and the Expected card reuses that same base case, so the
  two values are identical by construction ($466,553 == $466,553).

### Changed

- **Expected scenario is now the locked base case.** Its growth control writes
  straight to `meta.annual_growth_rate` (via new `updateExpectedGrowth()`) and
  triggers a full `recalculate()`, keeping the KPI TCV, Year-by-Year table, and
  Expected card aligned. The per-workload curve/go-live are shown as a descriptive
  subtitle (no override control). Conservative and Aggressive remain editable
  sensitivity bands (growth + curve), now computed over the **full** cost stack via
  `computeYearData({growth, curveOverride, goLiveShift})`.
- **`rampMultiplierForYear` / `defaultRampMultiplierForYear`** accept an optional
  `growthOverride` argument, replacing the previous `meta.annual_growth_rate`
  temp-swap hack in the scenario path. The `scenarioRampForYear` helper was removed.

### Tests

- **`scripts/html-render-check.mjs`** now parses the rendered `#scenarios` block
  and emits `expected_scenario_tcv` alongside `kpi_tcv`.
- **`tests/test_scenario_consistency.py`** (new) boots every `tests/fixtures/*.json`
  through the Node render harness and asserts `expected_scenario_tcv == kpi_tcv`
  (skips automatically when Node is unavailable). Full suite: 236 passed (+30).

---

## [2.2.0] - one-click Download PDF

### Added

- **Download PDF button.** A new floating primary button (`.pdf-btn`,
  `downloadPDF()`) rasterizes the live, edited proposal with `html2pdf.js`
  (loaded from the same jsDelivr CDN as Chart.js) and downloads a clean
  multi-page A4 PDF. Unlike the old `window.print()` path, it bypasses the
  browser print dialog entirely, so there are no browser-injected headers or
  footers, and it captures the SE's current on-screen edits. The filename
  reuses the slug/version/date convention from `saveSnapshot()` with a `.pdf`
  extension.
- **`body.pdf-export` CSS block.** Screen-mode equivalent of `@media print`
  (html2canvas does not honor `@media print`). It expands all tabs in flow,
  renders the `data-print-title` headers, applies page breaks, hides
  interactive chrome, and reflows charts to a single column. The two blocks
  are documented as a maintenance pair in `references/html-spec.md`.

### Changed

- **Print button is now a secondary fallback** labeled "Print" (was
  "Print / Save as PDF"). The three floating buttons (Download PDF, Print,
  Save HTML) were repositioned so they no longer overlap. `.pdf-btn` was
  added to the `@media print` hide list.

### Fixed

- **Download PDF: content shifted off-page on wide displays.** On a real wide
  browser (e.g. a 1440–1680px laptop) the PDF rendered with content pushed off
  the left edge — the header title and first KPI tiles disappeared and the right
  ~half of every page was blank. The cause was the `html2canvas: { windowWidth: 794, width: 794 }` capture override: forcing a narrow `windowWidth` re-maps
  html2canvas's capture origin against the live wide-window coordinates. Simply
  dropping the override is not enough either — in a wide browser html2canvas then
  computes a too-narrow output canvas (~719px for the 794px `.container`) and
  clips the right ~75px of every page. The fix in `downloadPDF()` requires all
  three of: `width: 794` (pins the output canvas to A4 content width),
  `windowWidth: window.innerWidth` (keeps layout at the real window width so
  html2canvas's origin math stays aligned), and an `onclone` callback that pins
  `<html>`/`<body>`/`.container` to 794px in the cloned document. Together these
  make the captured content fill exactly `0..794` with no left inset or right
  clip, deterministically across window widths. Verified at 1280/1440/1680px
  across the acme-financial, enterprise-gcp-fullstack, and light-and-wonder
  fixtures (~85 pages, zero clipping). `references/html-spec.md` documents the
  approach and warns that PDF changes must be verified at ≥1440px.
- **Download PDF: cropped charts and excessive whitespace.** The
  `body.pdf-export` block forced a page break before every tab
  (`page-break-before: always`), which made html2pdf emit ~15 mostly-empty
  pages, and its `.chart-row` / `.chart-container` rules lacked
  `break-inside: avoid`, so html2pdf's slice-based pagination cut charts in
  half. Tabs now flow continuously in the PDF path, and `break-inside: avoid`
  was added to charts and KPI tiles (sections/cards already had it) so whole
  charts/tiles move to the next page instead of being sliced. The tab
  `::before` heading also gets `page-break-after: avoid` to prevent orphaned
  section titles. The native `@media print` per-tab pagination is unchanged.

---

## [2.1.0] - ACV KPI, editable scenarios, Cortex token helper, Save HTML

Three rounds of feedback addressed in this release: two items from internal review
(`temp/feedback.md`) and three from a Gong demo session with Joel Brunger.

### Added

- **ACV KPI tile.** The fourth KPI tile is now "ACV (Avg / Year)" = TCV ÷ contract_years,
  replacing the previous "Recommended Commit" tile which was a redundant duplicate of
  Total TCV. The value updates live on every `recalculate()` call and in the
  DOMContentLoaded pre-population from `COMPUTED_TOTALS`.
- **Editable scenario parameters.** The Conservative, Expected, and Aggressive scenario
  cards in the Scenario Comparison section previously showed Growth % and Curve as
  disabled (read-only) inputs. Both fields are now editable selects/inputs wired to a new
  `updateScenarioParam(key, field, value)` helper. Changes update the card's per-year
  breakdown and TCV immediately via `updateScenarios()` without a full `recalculate()`.
  Parameters persist in `SIZING_SPEC.scenarios` so they survive a Save HTML round-trip.
  The Expected scenario seeds its `growth_pct` from `meta.annual_growth_rate` on first
  load, fixing the propagation bug where changing "Annual growth %" in Global Settings
  had no effect on the Expected scenario card.
- **`SIZING_SPEC.scenarios` block.** New top-level key added to
  `framework/sizing_spec_skeleton.json` with default Conservative / Expected / Aggressive
  tuples. `normalizeSpec()` in the template seeds the block from defaults (Expected growth
  seeded from `meta.annual_growth_rate`) when opening specs that predate this release.
- **Cortex token estimation helper (Cortex Agents + Snowflake Intelligence).** The AI
  panel now shows a helper row below each feature with six inputs:
  `monthly_users × sessions_per_user_per_day × messages_per_session × avg_input_tokens_per_message`
  (and `avg_output_tokens_per_message`) `× working_days_per_month`. Changing any field
  calls the new `deriveAgentTokens(feat)` function, which recomputes
  `monthly_input_tokens_M` / `monthly_output_tokens_M`, writes them back to SIZING_SPEC,
  and syncs the direct token inputs. Mirrors the existing Cortex Code
  `devs × queries/day × tokens/query` model. Helper field values persist in SIZING_SPEC
  alongside the derived token counts.
- **`skills/snowflake-sizing/references/ai-feature-defaults.md` — Cortex token
  estimation section.** Documents the `users × sessions × messages × tokens` formula,
  typical parameter ranges by usage profile (light / moderate / heavy), and an example
  patch dict with all six helper fields alongside derived `monthly_input_tokens_M` /
  `monthly_output_tokens_M`. Claude uses this guidance when building specs from research
  evidence.

### Changed

- **"Save HTML" button replaces "Export JSON".** The "Export JSON" button (which
  downloaded the SIZING_SPEC as a `.json` file) has been removed. The "Save Version"
  button is renamed "Save HTML" to make its function unambiguous — it already auto-
  increments `meta.version_number` and downloads a self-contained `.html` snapshot.
  The `exportSpec()` function is removed. The render-html sub-skill Phase 6 terminal
  summary updated accordingly.
- **`framework/sizing_spec_schema.json` — helper fields added to `cortex_agents` and
  `snowflake_intelligence`.** Eight new optional properties (`monthly_users`,
  `sessions_per_user_per_day`, `messages_per_session`, `avg_input_tokens_per_message`,
  `avg_output_tokens_per_message`, `working_days_per_month`, `model`,
  `monthly_cache_write_tokens_M`, `monthly_cache_read_tokens_M`) added to both objects.
  `additionalProperties: false` was blocking these fields from being saved in validated
  specs.

### Verified

```bash
# Full test suite passes unchanged
python3 -m pytest tests/ -q
# 196 passed in 0.49s

# Render + hook pass
python3 scripts/render-html.py \
  --spec tests/fixtures/acme-financial-3year-sizing.json \
  --out temp/output/joel-feedback.html
# sizing-guard hook: PASS
```

This release rearchitects how sizing proposals are generated and introduces the plugin's first automated test suite. Previously, `scripts/render-html.py` was a 270-line flat script mixing spec validation, Python math, token substitution, and file I/O with no test coverage and no way to call any stage independently. All rendering logic has been extracted into a new `renderer/` Python package with a clean public API (`compile_spec(spec, pricing, template, fonts_css) → CompileResult`), structured after the pattern established by `apps/architecture-diagrams-app/backend/renderer/`. A 196-test pytest suite in `tests/` verifies the pipeline end-to-end — ramp math, warehouse credits, storage formulas, serverless billing, spec validation, token substitution, HTML structure, and pricing rate correctness — all running in under one second with no LLM calls, no Node.js, and no network access. A programmatic cross-check of all 10 fixture outputs against `assets/snowflake_pricing_master.json` uncovered 9 wrong pricing values across 4 files (wrong region lookups, made-up AI credit tiers, stale storage proxies); these are corrected and the validator is now wired into the renderer so future specs emit a `[pricing-check]` warning before HTML is written. Python-computed totals (`COMPUTED_TOTALS`) are now embedded as a first-class JS variable in every rendered HTML, giving the in-page JS authoritative Python-side values for initial KPI display and eliminating the JS/Python drift on first load.

### Added

- **`renderer/` package.** New Python package at `renderer/` implementing the deterministic JSON-spec → HTML pipeline. Public surface: `compile_spec(spec, pricing, template, fonts_css) → CompileResult`. The `CompileResult` dataclass carries `html: str`, `spec: dict` (normalised, with `computed_totals` injected), and `computed_totals: dict`.

  - **`renderer/compiler.py`** — single entry point. Runs the four pipeline stages in order: (1) strip `utility_queries_reference` from pricing, (2) validate spec via `_schema_loader.SCHEMA`, (3) compute core totals and inject as `spec["computed_totals"]`, (4) build token map and substitute. Raises `SpecValidationError` on schema/domain failures; raises `ValueError` on unresolved `__TOKEN__` patterns. Also calls `validate_pricing` (see below) and emits any mismatches to stderr as `[pricing-check]` warnings before rendering continues.
  - **`renderer/spec_invariants.py`** — `strip_internal_pricing_data(pricing)` (deep-copies and strips `utility_queries_reference`, enforcing memory rule c4962f74 structurally rather than via agent recall); `validate_spec(spec)` (checks required top-level keys, required meta fields, edition/cloud enum values, workload fields needed for cost calculation — intentionally lighter than `spec-prepare.py`'s validator to accommodate real-world specs with extra fields from different schema versions).
  - **`renderer/html_builder.py`** — `build_token_map(spec, pricing, fonts_css, computed_totals)` builds the full substitution dict including the new `__COMPUTED_TOTALS__` token; `substitute_tokens(template, tokens)` performs serial ordered replacement; `check_substitution_complete(html)` raises `ValueError` listing all non-sentinel `__TOKEN__` leftovers.
  - **`renderer/pricing_validator.py`** — `REGION_ALIASES` dict mapping known LLM-generated region-string variants to canonical pricing-table keys (e.g. `"US East1 (N. Virginia)"` → `"US East (Northern Virginia)"`); `lookup_credit_rate`, `lookup_storage_rate`, `lookup_ai_credit_rate` against `credit_pricing.data` and `storage.standard.data` in the pricing JSON; `validate_pricing(spec, pricing) → list[str]` checks `meta.credit_rate`, `meta.storage_rate_per_tb`, and `meta.ai_credit_rate` with 0.01 tolerance. Unresolved regions emit an `UNRESOLVED_REGION` warning and skip numeric checks.
- **`tests/` pytest suite (196 tests, 0.55 s).** Zero LLM calls, zero Node.js, zero network.

  - `tests/conftest.py` — shared session-scoped fixtures: `plugin_root`, `skeleton`, `minimal_spec`, `real_pricing`, `minimal_pricing`, `template_text`, `fonts_css`, `acme_spec`.
  - `tests/test_compute_totals.py` — 24 unit tests for `framework/compute_totals.py`: ramp factor math, warehouse credits, storage growth formulas, serverless Snowpipe billing, `compute_core_totals` integration, known-TCV regression on `acme-financial`.
  - `tests/test_spec_validation.py` — 14 tests for `renderer/spec_invariants.py`: pricing data stripping (top-level, nested, list, idempotency), `validate_spec` happy-path and error paths (warehouses key, empty workloads, missing required keys, invalid edition/cloud enums).
  - `tests/test_html_builder.py` — 18 tests for `renderer/html_builder.py`: `fmt_credit_rate` formatting, token-map completeness, `__COMPUTED_TOTALS__` presence and validity, `substitute_tokens` behaviour, `check_substitution_complete` sentinel exemption and leftover detection.
  - `tests/test_html_integration.py` — 17 end-to-end tests calling `compile_spec()` with real assets on `acme-financial-3year-sizing.json`: HTML structure (`<!DOCTYPE html>`, `kpi-tcv` element, Chart.js reference), no unresolved tokens, `COMPUTED_TOTALS` embedded and matching `CompileResult`, sentinel preservation, `utility_queries_reference` absent, determinism (two renders of the same spec produce identical output modulo `computed_at` timestamp).
  - `tests/test_golden_files.py` — 70 parametrised tests (7 assertions × 10 fixtures): renders without error, no unresolved tokens, `COMPUTED_TOTALS` embedded, `core_tcv` > 0, TCV value in HTML matches `CompileResult`, HTML is deterministic, customer name in HTML.
  - `tests/test_pricing_validation.py` — 53 tests for `renderer/pricing_validator.py`: `lookup_credit_rate` for known regions, alias resolution, unknown → `None`, edition case-insensitivity; `lookup_storage_rate` for 7 regions; `lookup_ai_credit_rate` global vs regional classification; `validate_pricing` clean spec, wrong credit/storage/AI rates, `UNRESOLVED_REGION` flagging, multiple simultaneous mismatches; parametrised fixture suite asserting all 10 `tests/fixtures/*.json` produce zero pricing warnings.
  - `pytest.ini` — `testpaths = tests`.
- **`tests/fixtures/` — 10 canonical sizing JSON test fixtures.** Six copied from existing real customer sizings (`examples/` and `sizings/`) plus four new synthetic specs covering underrepresented parameter space:

  - `retail-ai-heavy-2year.json` — Azure Enterprise 2yr, heavy Cortex AI (Complete + Agents + Search + Analyst + Embeddings + sentiment/summarise functions), MCW BI, reader accounts. Tests: AI credit calculations, 2yr contract output length, Azure West US 2 rates.
  - `startup-gcp-minimal-1year.json` — GCP Standard 1yr, single M warehouse, Snowpipe Streaming, Cortex Complete (mistral-7b), fastest ramp. Tests: Standard edition, 1yr contract, GCP US Central1 rates, minimal serverless.
  - `enterprise-gcp-fullstack-3year.json` — GCP Enterprise 3yr, SPCS (CPU + GPU), OpenFlow (SAP ERP / Oracle WMS / Postgres), cross-continental replication, Cortex Complete + Snowflake Intelligence, 6 warehouses including 24/7 streaming ingest. Tests: full-featured spec with every optional block enabled.
  - `healthcare-bc-slowramp-3year.json` — AWS Business Critical 3yr, 90-day time travel (HIPAA maximum), slowest ramp (18-month migration), PrivateLink, hybrid tables, Trust Center + sensitive data classification + data quality monitoring, Cortex Complete for clinical document summarisation. Tests: BC edition, extreme storage overhead from long TT, late-loading ramp producing low Year 1 / high Year 2-3 pattern.
- **`__COMPUTED_TOTALS__` token and JS pre-population.** `proposal-template.html` now carries `const COMPUTED_TOTALS = __COMPUTED_TOTALS__;` immediately after the `SIZING_SPEC` declaration. The `DOMContentLoaded` handler pre-populates `kpi-tcv`, `kpi-yr1`, and `kpi-commit` from `COMPUTED_TOTALS.core_year_total` before `recalculate()` runs, so the proposal shows Python-authoritative values immediately on load regardless of whether the JS engine completes.

### Changed

- **`scripts/render-html.py` refactored to a thin CLI wrapper** (~100 lines, was 270). All pipeline logic — `_strip_utility_queries_reference`, `_build_token_map`, `_substitute`, `_check_substitution_complete`, `_fmt_credit_rate` — has moved into `renderer/`. The script now reads files, calls `renderer.compiler.compile_spec()`, runs the sizing-guard hook, and performs the atomic `tmp → rename` write. The printed summary (`core TCV: $X  (per-year [...])`) is unchanged. Exit codes unchanged.
- **`framework/compute_totals.py` is now the canonical source of numbers embedded in HTML.** The compiler always calls `compute_core_totals` and injects the result into `spec["computed_totals"]` before token substitution, so every rendered HTML carries fresh Python-computed values in both `SIZING_SPEC.computed_totals` and the new `COMPUTED_TOTALS` JS variable. The existing `DOMContentLoaded` console.info comparison (Python vs JS TCV) remains and is now structurally guaranteed to run on every render.

### Fixed

- **9 wrong pricing values across 4 fixture files**, all identified programmatically by running `validate_pricing` against the pricing JSON (effective May 12 2026):

  | File                                    | Field                   | Was                      | Correct                                                                                                | Root cause |
  | --------------------------------------- | ----------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------ | ---------- |
  | `acme-financial-3year-sizing.json`    | `storage_rate_per_tb` | $25.00 |**$24.00** | Assumption text falsely claimed "London not in pricing table"; AWS Europe (London) on-demand is $24.00 |            |
  | `enterprise-gcp-fullstack-3year.json` | `credit_rate`         | $3.00 |**$3.90**   | Used GCP US base rate instead of GCP Europe West 4 Enterprise ($3.90)                                  |            |
  | `enterprise-gcp-fullstack-3year.json` | `storage_rate_per_tb` | $22.00 |**$20.00** | Made-up interpolation; GCP Europe West 4 on-demand is $20.00                                           |            |
  | `enterprise-gcp-fullstack-3year.json` | `ai_credit_rate`      | $2.50 |**$2.20**   | Not a valid on-demand AI tier; EU regions get $2.20 regional rate                                      |            |
  | `healthcare-bc-slowramp-3year.json`   | `credit_rate`         | $5.50 |**$4.00**   | Confused AWS AP Sydney/Seoul BC ($5.50) with AWS US East (N. Virginia) BC ($4.00)                      |            |
  | `healthcare-bc-slowramp-3year.json`   | `storage_rate_per_tb` | $25.00 |**$23.00** | Used AP Sydney storage rate; AWS US East (N. Virginia) on-demand is $23.00                             |            |
  | `healthcare-bc-slowramp-3year.json`   | `ai_credit_rate`      | $3.00 |**$2.00**   | Arbitrary value; US base regions get the $2.00 global on-demand AI rate                                |            |
  | `retail-ai-heavy-2year.json`          | `credit_rate`         | $3.50 |**$3.00**   | Confused Azure Canada Central Enterprise ($3.50) with Azure West US 2 Enterprise ($3.00)               |            |
  | `retail-ai-heavy-2year.json`          | `storage_rate_per_tb` | $24.00 |**$23.00** | Used UK South rate; Azure West US 2 on-demand is $23.00                                                |            |

  Corrected in both `tests/fixtures/` and (for `acme-financial`) `examples/`. Affected TCV deltas: healthcare-bc $1,317k → $982k (−$335k); enterprise-gcp $10,142k → $12,623k (+$2.5M from higher correct rate); retail-ai-heavy $1,113k → $980k (−$133k).
- **`acme-financial` assumption text corrected.** The assumption *"Storage rate: $25/TB/month (proxy for AWS Europe London using EU Dublin rate; London not in pricing table)"* was factually wrong — AWS Europe (London) has been in the pricing table at $24.00/TB since at least v1.8. Assumption replaced with *"AWS Europe (London) on-demand storage rate per pricing table ($24.00/TB/month)."*

### Verified

```bash
# Full suite: 196 tests in 0.55s
python3 -m pytest tests/ -v

# Zero pricing warnings on all 10 fixtures after fixes
for f in tests/fixtures/*.json; do
    python3 scripts/render-html.py --spec "$f" --out /dev/null 2>&1 | grep pricing-check
done
# (no output)

# Re-rendered outputs in temp/output/ with corrected rates
for f in tests/fixtures/*.json; do
    slug=$(basename "$f" .json)
    python3 scripts/render-html.py --spec "$f" --out "temp/output/${slug}.html"
done
```

### Known follow-ups (not in this release)

- `renderer/pricing_validator.py` `REGION_ALIASES` is seeded from the 10 current fixtures only. New region-string variants from LLM-generated specs will emit `UNRESOLVED_REGION` warnings on first render; add the alias to `REGION_ALIASES` and the warning goes away permanently.
- The full TCV (SPCS / OpenFlow / Replication / Transfer / Collab) is still computed by JS at render time; `COMPUTED_TOTALS` carries only the four core categories (warehouse + serverless + AI + storage). The `[pricing-check]` pre-population therefore shows core-only values initially, which `recalculate()` overwrites with the full total within the same synchronous event-loop tick — no visible flash, but the pre-population ceiling is the core TCV.
- `test_html_integration.py` reads real assets from disk; it is an integration test not a pure unit test. Isolating it to a mock template would allow full parallelism and reduce disk I/O in CI.

: tool-name, Gong SQL, render-time hook bypass, doc-AI placeholder ergonomics

The Marks & Spencer sizing run surfaced five distinct in-flight failures, all infrastructure-level rather than methodology-level: (1) the Glean MCP tool whitelist used a name the host never registered, so the research-coordinator subagent self-blocked at preflight; (2) the Gong protocol's C2 transcript query used a join shape Snowflake rejects with `Unsupported feature 'lateral table function called with OUTER JOIN syntax or a join predicate (ON clause)'`, and C1 had no time filter so it returned scheduled future calls with no transcripts; (3) the `render-html` sub-skill described token substitution in prose, which let the agent fall back to a `bash python -c '... open(...).write(html)'` heredoc that bypassed the PreToolUse `sizing-guard.py` gate entirely; (4) `framework/sizing_spec_skeleton.json` did not seed the optional Document AI sibling keys, so the agent had to remember a separate rule to add them or the page crashed at `populateAIPanel()`; (5) `temp/` and `sizings/` did not exist on first run and `spec-prepare.py` and the agent's evidence-file writes both blew up with `FileNotFoundError`. This patch closes all five at the source.

### Added

- **`scripts/render-html.py`.** Single-entry HTML renderer that reads the spec, deep-strips `utility_queries_reference` blocks from the pricing JSON (memory rule c4962f74 enforced in code rather than agent recall), substitutes every template token, asserts no `__TOKEN__` leftovers (sentinel pair `__SIZING_SPEC_BEGIN__` / `__SIZING_SPEC_END__` is allow-listed), and invokes `hooks/sizing-guard.py` directly via subprocess with the same `Write` payload the real tool would emit. On hook PASS the script writes atomically and prints the same Phase 6 summary the agent would have printed; on hook BLOCK it surfaces the hook's reason and exits non-zero without touching the output path. This closes the bash-redirect bypass: there is no longer a code path that produces a sizing HTML without going through the PreToolUse gate.

### Changed

- **`framework/sizing_spec_skeleton.json` + `scripts/regen_skeleton.py`.** The skeleton now seeds the three optional Document AI keys (`document_ai`, `ai_parse_document_layout`, `ai_parse_document_ocr`) as disabled placeholders alongside the 9 schema-required `ai_cortex` keys (skeleton total: 12). The schema continues to mark them optional — the change is purely defensive: with the placeholders baked in, the agent never has to remember to add them and the JS template's `populateAIPanel()` and `calcAICost` paths never have to dereference an undefined node, even when the patch dict says nothing about Document AI. `regen_skeleton.py` carries an explicit `setdefault` block for the three keys with a comment explaining why they are seeded despite being optional.
- **`scripts/spec-prepare.py`.** `_write_spec` now `Path(args.out).parent.mkdir(parents=True, exist_ok=True)` immediately before writing. Combined with the session-hook bootstrap, first-run failures from a missing `sizings/` directory are gone.
- **`hooks/session.py`.** `SessionStart` (source=startup) now also creates `<cwd>/temp/` and `<cwd>/sizings/` if absent, in addition to the existing stale-evidence cleanup. Hook output stays silent unless something visible happened (directory created or stale evidence removed).
- **`skills/snowflake-sizing/SKILL.md` Phase 1.** `context_file` is now soft-required: if the value passed in `$ARGUMENTS` does not resolve to an existing file, the skill treats the entire argument string as inline scenario context and forwards it to the research-coordinator as `inline_scenario` instead. Unblocks ad-hoc invocations like `/snowflake-sizing Marks and Spencer wants to migrate 50TB...` without the SE having to first dump the prompt into a file. The audit trail records which mode was used.
- **`skills/snowflake-sizing/sub-skills/render-html/SKILL.md`.** Phase 5 Step 1 replaces the prose walkthrough of token substitution with a single instruction to run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render-html.py --spec ... --out ...`. The token table remains as documentation but is annotated "handled by render-html.py" rather than "the agent must substitute these". Adds an explicit "do NOT use bash redirects to write the HTML" warning for defense in depth.
- **`skills/snowflake-sizing/sub-skills/build-spec/SKILL.md`** and **`references/ai-feature-defaults.md`.** Doc updates: the skeleton already supplies the three Document AI placeholders, so the agent does not need to add them to the patch unless the customer actively uses Document AI. The `ai_cortex` count language is restated as "9 required (per the schema) + 3 optional Document AI placeholders the skeleton seeds = 12 keys in the assembled spec".
- **`agents/research-coordinator.md`.** Inputs section documents the `inline_scenario` fallback for when `context_file` does not resolve to an existing path; the coordinator forwards `inline_scenario` to every specialist in place of `context_file`.

### Fixed

- **Glean MCP tool whitelist used the wrong name.** `agents/research-coordinator.md`, `agents/research-glean-agent.md`, and `commands/snowflake-sizing.md` declared `mcp__glean_default__search` (and the three sibling Glean tools), but the host registers the Glean MCP server as `glean` and exposes `mcp__glean__search`. The result was a subagent that self-blocked at Phase 1.5 preflight because the tool it was supposed to call was not in its own whitelist. All four `mcp__glean_default__*` whitelist entries are renamed to `mcp__glean__*`. The single remaining string match is the explanatory sentence in `references/research-protocol.md` Section 1 documenting that the legacy alias is no longer in use.
- **Gong C1 returned future scheduled calls and Gong C2 used an unsupported `LATERAL FLATTEN ... ON TRUE` shape.** `references/research-protocol.md` Section 2:
  - **C1** now adds `AND c.PLANNED_START_DATETIME <= CURRENT_TIMESTAMP()` (filters out scheduled-but-not-yet-happened calls, which have no transcript) and surfaces a `has_transcript` flag via a correlated `EXISTS (SELECT 1 FROM CALL_TRANSCRIPTS ... WHERE TRANSCRIPT IS NOT NULL)` so the agent picks C2 calls from the rows where `has_transcript = TRUE`. `LIMIT` raised from 3 to 5 to keep two retry slots after the time filter narrows the set.
  - **C2** is rewritten as a CTE that does the `LATERAL FLATTEN` inside the comma-join form (no `ON TRUE` predicate), then a regular `JOIN` to `CONVERSATION_PARTICIPANTS` keyed on `CONVERSATION_KEY` + `speakerId`. Snowflake rejects `JOIN LATERAL FLATTEN(...) ON TRUE` together with a downstream join predicate (`Unsupported feature 'lateral table function called with OUTER JOIN syntax or a join predicate (ON clause)'`); the CTE form sidesteps that limitation cleanly.

### Verified

- `python3 scripts/regen_skeleton.py --check` exits 0; the regenerated skeleton has 12 `ai_cortex` keys (9 required + 3 Document AI placeholders) and matches the schema.
- `grep -rn 'mcp__glean_default__' agents commands hooks scripts skills framework` returns only the single explanatory sentence in `references/research-protocol.md`; zero whitelist references remain.
- End-to-end smoke run from a fresh CWD with no `temp/` or `sizings/` directory present:
  - `spec-prepare.py` against a synthetic patch that omits the three Document AI keys produces a spec containing all three placeholders, valid `core_tcv` (`$27,245`), and auto-creates `sizings/` on first write.
  - `render-html.py` against that spec writes the HTML, prints `sizing-guard hook: PASS`, embeds zero `utility_queries_reference` matches in the rendered output, and leaves only the two `__SIZING_SPEC_*__` sentinels behind.
- Negative path: putting an em-dash in the customer name (which lands in HTML scope via `__CUSTOMER__`) causes `render-html.py` to exit non-zero with the hook's two-line em-dash report (`line 5 col 22`, `line 487 col 39`) and **does not** write the output file. The render-html-as-script gate is now structurally equivalent to the `Write`-tool gate.

### Known follow-ups (not in this release)

- The em-dash hook scans HTML source bytes; em-dashes that land inside JSON-encoded strings in the embedded `SIZING_SPEC` are written as `\u2014` escapes by `json.dumps` (correct ASCII-safe encoding for JS embedding) and therefore are not visible to the byte-level scan. A literal em-dash in customer-facing prose still gets caught at the evidence-md stage (where transcripts are scanned pre-paste). This split is by existing design; no change in this release.

---

## [1.9.1] - Marks & Spencer retrospective: tool-name, Gong SQL, render-time hook bypass, doc-AI placeholder ergonomics

The Marks & Spencer sizing run surfaced five distinct in-flight failures — see the original entry below for full detail. This release closed all five at the source.

---

## [1.9.0] - Speed, error-prevention, and hooks consolidation

The previous-session retrospective on the Momentum Group sizing run identified four classes of in-flight correction, all traceable to four root causes: (1) hand-assembled JSON dicts with no skeleton, (2) post-write rather than pre-write validation, (3) HTML template hard-derefs of optional schema fields, and (4) JS-vs-Python TCV drift from divergent storage formulas. This release closes all four classes and additionally fans out the research phase into three parallel specialists.

### Added

- **`framework/sizing_spec_skeleton.json` + `scripts/regen_skeleton.py`.** A schema-derived, structurally complete neutral skeleton with every required key (9 `ai_cortex` placeholders, 27 serverless placeholders, eight optional-but-JS-required top-level blocks like `spcs` / `openflow` / `replication` / `data_transfer`). The build-spec phase clones the skeleton via deep-merge instead of constructing the dict from scratch, eliminating the entire class of "missing required key" errors. `regen_skeleton.py --check` is a CI-safe drift detector that exits non-zero when the skeleton falls out of sync with the schema.
- **`scripts/spec-prepare.py`.** Build-time normalizer the agent calls before Write. Deep-merges a small customer-specific patch over the skeleton; auto-renames every legacy field name (`storage_growth_pct` → `annual_growth_pct`, `monthly_tokens_input` → `monthly_input_tokens_M`, `indexed_gb` → `indexed_data_gb`, `monthly_credits` → `compute_hours_monthly`, `avg_clusters` → `clusters_min`/`clusters_max`); strips internal markers (`utility_queries_reference`, `_skeleton_marker`, `_comment`, `__doc__`); stamps an authoritative `computed_totals` block; runs schema validation in-process. Each rename is logged as a warning so the agent can fix the source patch on the next iteration.
- **`framework/compute_totals.py`.** Python port of the JS `recalculate()` core math (warehouse + serverless + AI + storage). Formulas now match the JS template to the cent for these four categories — closing the $416k-vs-$426k drift class. Output stamped into `SIZING_SPEC.computed_totals` by spec-prepare.
- **`hooks/sizing-guard.py`.** Single consolidated PreToolUse hook firing on `Write` to `sizings/*.json`, `sizings/*.html`, and `temp/*-evidence*.md`. JSON path: schema-validates, detects legacy field names with auto-fix suggestions, rejects leakage fields. HTML path: em-dash, content-hygiene tokens, unsubstituted `__TOKEN__` leftovers, and Node sidecar JS render check. Evidence-md path: em-dash scan (the previous-session bug had em-dashes leak through evidence files into customer text). Pre-write means the agent sees the error before the file lands; the retry loop is one Write attempt instead of write-validate-edit-rewrite.
- **`agents/research-coordinator.md`** + three specialists (`research-glean-agent.md`, `research-gong-agent.md`, `research-replication-agent.md`). Phase 2 research is now fanned out across three parallel agents (Glean B1/B2/B3, Gong C1/C2, optional Replication D1/D2/D3). Each specialist owns a fragment file under `temp/`; the coordinator concatenates them into the final evidence path. Wall-clock time drops; main-agent context still sees only the slim summary contract.

### Changed

- **`framework/sizing_spec_schema.json` `ai_cortex.required` trimmed 12 → 9.** `document_ai`, `ai_parse_document_layout`, `ai_parse_document_ocr` are now optional. The HTML template uses optional chaining (`ai.document_ai?.enabled`) for the only on-render dereference and `&&` guards everywhere else, so a sizing without those keys renders correctly. Supply them in the patch only when the customer actively uses Document AI. This fully closes the v1.7.0 silent-`$0` bug class — the keys are no longer a footgun.
- **`assets/templates/proposal-template.html`** — `populateAIPanel()` row for `document_ai` now uses `ai.document_ai?.enabled` and `ai.document_ai?.compute_hours_monthly ?? 0`. The `DOMContentLoaded` handler logs build-time core TCV (from `SIZING_SPEC.computed_totals`) alongside render-time JS TCV via `console.info`, providing a runtime audit trail for spotting Python-vs-JS drift.
- **`scripts/html-render-check.py`** refactored to delegate to `framework/compute_totals.py`. The Python TCV math is no longer duplicated; the back-compat shim `compute_year_totals(spec)` now returns full-core totals (warehouse + serverless + AI + storage) instead of warehouse + storage only, making the JS-vs-Python cross-check tighter.
- **`scripts/html-render-check.mjs`** — sandbox `console` rerouted to `process.stderr` with `[sandbox.*]` prefixes so the embedded HTML's `console.info` / `console.warn` / etc. no longer pollutes the JSON result line on stdout.
- **`scripts/_schema_loader.py`** — `required_ai_cortex()` invariant updated from "exactly 12 entries" to "exactly 9 entries" with an inline comment pointing at the v1.8 trim.
- **`hooks/hooks.json`** — `PostToolUse` block removed; replaced with a single `PreToolUse` matcher routing all `Write` events to `hooks/sizing-guard.py`.
- **`skills/snowflake-sizing/SKILL.md`** — Phase 2 routing now points at `agents/research-coordinator.md`; "Hooks active" section rewritten to reflect the consolidated `sizing-guard.py` and remove the two retired PostToolUse hooks.
- **`sub-skills/build-spec/SKILL.md`** — Phase 3 rewritten from "construct the SIZING_SPEC dict" to "build a small patch dict and run `scripts/spec-prepare.py --patch <patch.json> --out <spec.json>`". Phase 4 is now "inspect `computed_totals`" (the Python math is authoritative; manual hand-computation is gone).
- **`sub-skills/render-html/SKILL.md`** — Step 4 (the manual three-script parallel gate) collapsed into "the PreToolUse hook already covered all four checks; confirm it approved". The manual scripts (`emdash-check.py`, `content-hygiene-check.py`, `html-render-check.py`) remain available for verbose runs but are no longer part of the agent's normal path.
- **`sub-skills/research/SKILL.md`** — points at `agents/research-coordinator.md`; preflight detail moves to the coordinator (still hard-gates on Glean MCP + SNOWHOUSE).
- **`references/ai-feature-defaults.md`** — Document AI section rewritten: keys are now optional, supply via patch only when used, required `ai_cortex` count is 9.
- **`references/field-names.md`** — added an "Auto-fixed?" column flagging which legacy names spec-prepare rewrites silently versus which still trip the PreToolUse hook. Updated the `ai_cortex` count from 12 to 9 with a footnote on the Document AI optionality.
- **`hooks/preflight.py` context-reminder banner** — refreshed for v1.9 to reference `hooks/sizing-guard.py`, the spec-prepare flow, the 9-key `ai_cortex` count, and the optional Document AI placeholders. The previous banner advertised `hooks/content-hygiene.py` and `hooks/validate-sizing-json.py` (both deleted) and "all 12 ai_cortex keys" (now 9).

### Removed

- **`hooks/validate-sizing-json.py`.** Replaced by the consolidated `hooks/sizing-guard.py`.
- **`hooks/content-hygiene.py`.** Replaced by the consolidated `hooks/sizing-guard.py`.
- **`agents/research-agent.md`.** Replaced by the coordinator + three specialists.

### Verified

- Skeleton ↔ schema in sync: `python3 scripts/regen_skeleton.py --check` exits 0.
- Existing `examples/acme-financial-3year-sizing.json` continues to validate; rendering it still produces the byte-stable JS TCV ($466,635) it produced before this release.
- The previous-session failure mode (deleting `ai_cortex.document_ai` from a known-good spec → `TypeError` at boot → page renders $0) now succeeds: the JS engine renders the same $466,635 with the keys absent.
- `scripts/spec-prepare.py` correctly auto-renames every legacy field on a synthetic patch dict carrying all six known footguns, strips the `_comment` and `_skeleton_marker` markers, computes a non-zero core TCV, and produces a spec that passes the consolidated hook on first Write.
- The PreToolUse hook blocks legacy field names, leakage fields, em-dashes, content-hygiene tokens, and unsubstituted template tokens with actionable line-numbered error messages; it approves clean specs silently.

### Known follow-ups (not in this release)

- `scripts/spec-validate.py`, `scripts/_schema_loader.py` docstrings, `framework/sizing_spec_schema.json` description string, and `references/content-hygiene.md` still reference the retired hook filenames in their prose. These are doc-only references; they do not affect runtime behaviour. Cleanup in a follow-up release.
- The full TCV (including SPCS / OpenFlow / Replication / Transfer / Collab) is still JS-computed at render time; spec-prepare's `computed_totals` covers only the four "core" categories. Porting the remaining math to Python would let JS read the entire TCV from `computed_totals` directly. Tracked as a future enhancement.

---

## [1.8.0] - Pricing JSON verification and label fixes (May 2026 consumption table)

### Fixed

- **`spcs.cpu.description` referenced wrong table number.** Said `"Table 1(e)"` (Adaptive Compute); corrected to `"Table 1(f)"` (Gen1 SPCS CPU).
- **`spcs.gpu.description` referenced wrong table number.** Said `"Table 1(g)"` (Gen2 SPCS); corrected to `"Table 1(f)"` (Gen1 SPCS GPU, which shares the same table as CPU/HIGHMEM).
- **`ai_features.other_ai_features.description` referenced wrong table number.** Said `"Table 6(h)"` (Provisioned Throughput); corrected to `"Table 6(g)"` (Other AI Features).
- **Spurious `Translate` entry removed from `ai_features.utility_functions`.** A duplicate `{"function": "Translate", "rate": 1.5}` entry existed alongside the correct `AI_TRANSLATE` entry; only `AI_TRANSLATE` appears in PDF Table 6(a). The duplicate has been removed.

### Added

- **`scripts/verify-pricing-json.py`** — comprehensive spot-check script that encodes ground-truth values from every table in the May 12 2026 Snowflake Service Consumption Table PDF (Tables 1(a)–8) and compares them against `assets/snowflake_pricing_master.json`. Covers all 55 regions × 4 editions for credit pricing, all warehouse sizes, all SPCS families, all AI model rates, all storage and data-transfer tables, serverless multipliers, and org-usage tiers. Exits 0 when all checks pass.

### Changed

- **`assets/snowflake_pricing_master.json` metadata bumped.** `version` 2.2 → 2.3, `last_updated` updated to 2026-05-27 to reflect the May 12 2026 consumption table.

---

## [1.7.0] - Defense-in-depth fix for the silent `$0` AI-key bug

### Fixed

- **Silent `$0` page-render failure caused by missing `ai_cortex.document_ai`.** Symptom: `spec-validate.py`, the PostToolUse hook, `html-render-check.py`, em-dash, and content-hygiene gates all passed, but the rendered HTML proposal sat at `$0` for every KPI. Root cause: `populateAIPanel()` in `assets/templates/proposal-template.html` reads `ai.document_ai.enabled` (and other keys) without optional chaining; missing keys throw a `TypeError` at boot, the `DOMContentLoaded` handler aborts before `recalculate()` runs, and the page stays at its placeholder zeros. Compounding the bug, `SKILL.md` Phase 3 explicitly told agents *"Do NOT include `document_ai`, `ai_parse_document_layout`, or `ai_parse_document_ocr` in any spec"* — directly conflicting with the template's runtime requirement.

### Changed

- **`SKILL.md` § AI Feature Defaults rewritten.** The "do NOT include" guidance is replaced with: *Document AI is deprecated for new sizing — but the keys MUST still be present in `ai_cortex` because `populateAIPanel()` reads them without optional chaining; omission throws a TypeError and the page silently renders as $0. Use the documented disabled-placeholder shapes.* The new section enumerates the required placeholder shapes for `document_ai`, `ai_parse_document_layout`, and `ai_parse_document_ocr`, and points at the schema for the full list of 12 required `ai_cortex` keys.
- **`scripts/spec-validate.py` now enforces presence of every template-required AI key.** New `TEMPLATE_REQUIRED_AI_KEYS` constant lists all 12 entries (mirroring `framework/sizing_spec_schema.json` `properties.ai_cortex.required`); a parallel `TEMPLATE_REQUIRED_CORTEX_FUNCTIONS` constant covers the 6 sub-functions iterated unconditionally by `populateAIPanel()`. Each missing key produces a hard error that names the key, explains the failure mode (TypeError → silent `$0`), and points at the schema.
- **`hooks/validate-sizing-json.py` mirrors the same checks** so the `PostToolUse` hook blocks Write at the source. Both validators share the same constants list to prevent drift.
- **`scripts/html-render-check.py` upgraded to a real-JS execution gate.** Previously the script re-implemented the warehouse-credit math in Python and never exercised the actual DOM-rendering path. It now invokes the new `scripts/html-render-check.mjs` sidecar, which extracts the inline `<script>` block, evaluates it inside a Node `vm` context with stub `document`/`window`/`Chart` globals, fires the captured `DOMContentLoaded` handler in a `try/catch`, and reports both whether the boot sequence threw and what `kpi-tcv` `textContent` ended up. Failure prints the actual JavaScript stack trace pointing at the offending `populateXPanel()` function. The Python warehouse-credit math is retained as a secondary sanity check; a `js_tcv < py_tcv` mismatch is flagged as a warning.
- **`assets/snowflake_pricing_master.json` no longer references `research-protocol.md`.** The `utility_queries_reference` field that pointed at the internal markdown file (and tripped the content-hygiene gate when embedded in HTML) has been removed at source.

### Added

- **`scripts/html-render-check.mjs`** — Node 18+ sidecar that runs the proposal HTML's inline `<script>` block in a stubbed-DOM `vm` context. Returns `{ok, kpi_tcv, error, stack}` JSON. Catches missing-template-required-key errors that the Python math gate cannot.
- **Regression test confirming all four gates work for the same bug class.** Negative case: deliberately deleting `ai_cortex.document_ai` from a known-good spec / HTML now produces clear, named-key errors from `spec-validate.py`, the PostToolUse hook, AND the JS render check (with stack frame at `populateAIPanel`). Positive case: all four shipped specs (`gsmai`, `light-and-wonder`, `travelodge`, `examples/acme-financial`) continue to pass with zero false positives.

---

## [1.6.0] - Plugin layout aligned to monorepo conventions

### Changed

- **Folder reshape to match `snowflake-pptx` and other peer plugins.** `assets/` is now data-only; user-invokable utilities live in a new top-level `scripts/` directory; the HTML template moved out of `skills/.../references/` (which now holds markdown only) into `assets/templates/`.
  - `assets/spec-validate.py` → `scripts/spec-validate.py`
  - `assets/html-render-check.py` → `scripts/html-render-check.py`
  - `assets/emdash-check.py` → `scripts/emdash-check.py`
  - `skills/snowflake-sizing/references/_template.html` → `assets/templates/proposal-template.html`
- **`.claude-plugin/plugin.json` now declares `"hooks": "hooks/hooks.json"`.** Without this key, the `PostToolUse` validator was registered only when the plugin happened to live at this developer's path — installs from elsewhere silently lost the hook. The validator now ships activated for every install.
- **Hardcoded `~/Snowflake/Repos/aross-se-superpowers/plugins/snowflake-sizing/...` paths replaced with `${CLAUDE_PLUGIN_ROOT}/...` throughout `SKILL.md`.** Affects the pricing-data read in Phase 1, the three reference-doc reads in Phase 1, the template + brand-fonts reads in Phase 5, and the three Phase 5 gate invocations (`scripts/spec-validate.py`, `scripts/html-render-check.py`, `scripts/emdash-check.py`). The plugin now works from any caller's working directory and any installer's plugin root, not just this developer's box.
- **`SKILL.md` frontmatter trimmed** to `name` and `description` only. The `argument-hint` and `allowed-tools` keys are command-frontmatter fields (already correctly set on `commands/snowflake-sizing.md`); skill loaders ignore them. Removing the duplicates eliminates a drift source.
- **`hooks/hooks.json` matcher tightened from `Write|Edit` → `Write`.** The validator already early-returned for `Edit` (partial-content payloads can't be structurally validated). Tightening the matcher avoids spurious hook invocations.
- **`hooks/hooks.json` and `hooks/validate-sizing-json.py` normalised to `${CLAUDE_PLUGIN_ROOT}`.** Matches the convention used across `plugin-scaffolder` templates and the rest of the monorepo.

### Fixed

- **`hooks/validate-sizing-json.py` no longer prints the literal string `${CORTEX_PLUGIN_ROOT}` in block-decision error messages.** The schema reference now reads `framework/sizing_spec_schema.json (relative to plugin root)`, which is meaningful regardless of how the variable is expanded.
- **`skills/snowflake-sizing/references/html-spec.md` template path corrected** from the old `skills/snowflake-sizing/references/_template.html` to the new `assets/templates/proposal-template.html`.
- **`README.md` "sizings/ is git-tracked" claim corrected.** Generated `.html` and `.json` files in `sizings/` are now git-ignored (only `.gitkeep` ships) so customer outputs stay out of the plugin's git history.

### Hygiene

- **`.gitignore` expanded** to cover `.DS_Store`, `**/.DS_Store`, `.claude/settings.local.json`, and `sizings/*.{json,html}` (with `!sizings/.gitkeep` to preserve the directory).
- **`git rm --cached`** applied to three previously-tracked `.DS_Store` files (`./`, `skills/`, `skills/snowflake-sizing/`) and four real-customer sizings (`gsmai-3year-sizing-v1-2026-05-26.{html,json}`, `light-and-wonder-3year-sizing-v1-2026-05-26.{html,json}`). Removes customer names from git going forward; the working-tree files are unchanged.

### Files changed

- `.claude-plugin/plugin.json` — added `"hooks"` key
- `.gitignore` — added DS_Store / settings.local / sizings outputs
- `README.md` — corrected "sizings/ is git-tracked" line
- `skills/snowflake-sizing/SKILL.md` — frontmatter trim, all paths to `${CLAUDE_PLUGIN_ROOT}`, gate paths to `scripts/`, template path to `assets/templates/`
- `skills/snowflake-sizing/references/html-spec.md` — template path reference
- `hooks/hooks.json` — matcher narrowed, `${CLAUDE_PLUGIN_ROOT}` variable
- `hooks/validate-sizing-json.py` — block-decision error message cleaned
- File moves (git renames preserve history): 3 scripts `assets/` → `scripts/`; template `skills/.../references/_template.html` → `assets/templates/proposal-template.html`

---

## [1.5.0] - Default ramp window: dev_start=0, go_live=3

### Changed

- **Default `dev_start_month` changed from 2 → 0.** Billing ramp now begins from month 1 of the contract (month 0 seed means no months are zeroed out — the workload contributes from its first active month). Previously month 1 was always zero, which under-counted Year 1 spend for fast-moving deployments.
- **Default `go_live_month` changed from 11 → 3.** Reflects modern deployment patterns where customers reach steady-state by end of Q1 rather than end of year. Produces higher Year 1 multipliers (linear curve ~0.94 vs ~0.54 previously).
- **Global Settings "Dev start (month)" input `min` attribute changed from 1 → 0.** Allows the field to be set to 0 in the browser. The JS value display also changed from `|| 2` (which silently renders `2` when the stored value is `0`) to `?? 0` (nullish coalescing, correctly renders `0`).
- **Year 1 effective multiplier table in `sizing-methodology.md` updated.** New values for `dev_start=0, go_live=3`: Slowest 0.86, Slow 0.90, Linear 0.94, Fast 0.96, Fastest 0.98 (was: 0.31 / 0.43 / 0.54 / 0.69 / 0.79).

### Files changed

- `skills/snowflake-sizing/references/_template.html` — normalizeSpec defaults, rampMultiplierForYear fallbacks, scenario `|| 11` references, Global Settings input `min` and value expression
- `examples/acme-financial-3year-sizing.html` — same JS changes + embedded SIZING_SPEC meta defaults
- `examples/acme-financial-3year-sizing.json` — `meta.default_dev_start_month` and `meta.default_go_live_month`
- `skills/snowflake-sizing/SKILL.md` — meta block example, per-workload defaults table
- `skills/snowflake-sizing/references/sizing-methodology.md` — field descriptions, Year 1 multiplier table
- `framework/sizing_spec_schema.json` — `minimum` for `meta.default_dev_start_month` and `workloads[].dev_start_month` changed from 1 → 0

---

## [1.4.0] - Canonical JSON Schema + PostToolUse validation hook

### Added

- **`framework/sizing_spec_schema.json`** — canonical JSON Schema draft-07 for the full `SIZING_SPEC` artifact. Covers every top-level section (`meta`, `workloads`, `serverless`, `ai_cortex`, `spcs`, `openflow`, `openflow_oracle`, `postgres`, `storage`, `data_transfer`, `privatelink`, `collaboration`, `assumptions`, `confirm_required`, `replication`). Strict `additionalProperties: false` on `meta`, `workloads[]` items, all `serverless` features, all `ai_cortex` features, and all other leaf objects. Shared `$defs` for `source_field` (SOURCED/ASSUMPTION/ESTIMATED), `ramp_curve` (fastest/fast/linear/slow/slowest), `wh_size_abbreviated` (XS–6XL, for workloads and reader accounts), `wh_size_full` (X-Small–4X-Large, for OpenFlow instances), `serverless_compute`, and `cortex_function`. Documents known footguns inline via `description` fields (e.g. `cortex_complete.monthly_input_tokens_M`: *"WRONG: 'monthly_tokens_input'"*; `cortex_search.indexed_data_gb`: *"WRONG: 'indexed_gb'"*; `openflow.instances[].warehouse_size`: *"use full names, not abbreviations"*; `storage.standard.raw_tb_year1`: *"WRONG path: storage.raw_tb"*). Intended as the inter-skill contract consumed by future `/export-pptx` and `/export-xlsx` skills.
- **`hooks/validate-sizing-json.py`** — `PostToolUse` hook that fires on every `Write` to `sizings/*.json`. Skips `Edit` calls (partial content) and all non-sizing files. Validates: required top-level keys present; `warehouses` key absent; `meta.edition` / `meta.cloud` / `meta.default_ramp_curve` values within enum; all per-workload required fields present; workload `size` / `source` / `ramp_curve` within enum; legacy `avg_clusters` absent; `storage.standard.raw_tb_year1` path correct; `ai_cortex.cortex_complete.monthly_input_tokens_M` present when enabled; `ai_cortex.cortex_search.indexed_data_gb` correct; `ai_extract` not placed directly under `ai_cortex`; serverless features not using `monthly_credits`; OpenFlow `warehouse_size` not using abbreviations; `confirm_required` items have `item` + `impact_pct`. Returns `{"decision": "block", "reason": "..."}` with actionable error list on failure, exits 0 silently on pass.
- **`hooks/hooks.json`** — wires `validate-sizing-json.py` to the `PostToolUse` / `Write|Edit` event.

### Changed

- **SKILL.md Phase 5, spec structure gate** — added two-sentence note after the `spec-validate.py` invocation pointing to `${CORTEX_PLUGIN_ROOT}/framework/sizing_spec_schema.json` as the canonical full-field reference and explaining that `hooks/validate-sizing-json.py` enforces the same rules automatically on every `Write` to `sizings/*.json`.

---

## [1.3.0] - Spec validator, HTML render-check, SKILL.md schema hardening

### Added

- **`assets/spec-validate.py`** — standalone structural JSON validator for SIZING_SPEC files. Modelled on `emdash-check.py` (same exit 0/1 contract). Hard-fails on: `warehouses` key present instead of `workloads`; missing `workloads` key entirely; per-workload missing any of `id`, `label`, `size`, `hours_per_day`, `days_per_month`, `clusters_min`, `clusters_max`, `auto_suspend_seconds`, `dev_start_month`, `go_live_month`, `ramp_curve`; legacy `avg_clusters` field present; `storage.raw_tb` at top level instead of `storage.standard.raw_tb_year1`; `ai_cortex.cortex_complete.monthly_tokens_input` instead of `monthly_input_tokens_M`; `ai_cortex.cortex_search.indexed_gb` instead of `indexed_data_gb`; `ai_extract` directly under `ai_cortex` instead of `ai_cortex.cortex_functions.ai_extract`; serverless features using `monthly_credits` instead of `compute_hours_monthly`; OpenFlow `warehouse_size` using abbreviations (`XS`, `S`, etc.) instead of full names (`X-Small`, `Small`, etc.). Warns (non-fatal) on missing meta fields and absent `openflow_oracle` / `data_transfer` / `privatelink` keys.
- **`assets/html-render-check.py`** — Python replica of the JS `recalculate()` engine. Extracts the embedded `SIZING_SPEC` from a generated HTML file (via `__SIZING_SPEC_BEGIN__` / `__SIZING_SPEC_END__` sentinels), parses it, runs the warehouse ramp + storage cost model, and asserts TCV > 0 and Year 1 total > 0. On pass, prints the computed Year 1 / Year 2 / Year 3 / TCV summary so the SE can eyeball the numbers before opening the browser. On failure, prints a diagnosis: zero `credit_rate`, empty `workloads`, all ramps landing outside year 1, or unsubstituted `__SIZING_SPEC__` token. Exit 0/1.
- **`examples/acme-financial-3year-sizing.json`** — canonical reference JSON extracted from the existing `examples/acme-financial-3year-sizing.html`. Every field at the correct depth with the correct names. Future agent runs can diff against this file to catch field-name regressions before writing the HTML.
- **Phase 5 gate 5 — Spec structure gate (BLOCKING).** `python3 assets/spec-validate.py sizings/<slug>.json` added as the fifth quality gate. Must exit 0 before the HTML render check or em-dash gate may run.
- **Phase 5 gate 6 — HTML render check gate (BLOCKING).** `python3 assets/html-render-check.py sizings/<slug>.html` added as the sixth quality gate. Must exit 0 (TCV > 0) before the em-dash gate. A passing gate prints the Year 1/2/3/TCV summary, which is recorded verbatim in the Phase 6 output.

### Changed

- **SKILL.md Phase 3 `### Warehouses` renamed to `### Workloads (SIZING_SPEC.workloads array)`.** New critical callout: *"The top-level array key MUST be `workloads`. Do NOT use `warehouses`. The JS engine reads `SIZING_SPEC.workloads` — any other key renders as $0."* Required JSON shape block now shown verbatim with all mandatory fields including `clusters_min`, `clusters_max`, `auto_suspend_seconds`. Explicit note that `avg_clusters` is not read by the JS engine and must never be used.
- **SKILL.md Phase 3 `### AI / Cortex Features` — field name reference table added.** Six-row table mapping every commonly-wrong field name to its correct counterpart: `monthly_tokens_input` → `monthly_input_tokens_M`, `indexed_gb` → `indexed_data_gb`, top-level `ai_extract` → `ai_cortex.cortex_functions.ai_extract`, `monthly_credits` → `compute_hours_monthly`, `storage.raw_tb` → `storage.standard.raw_tb_year1`, `"XS"` → `"X-Small"`. Note added that `ai_cortex.cortex_functions` is a required sub-object even when all AI_ SQL functions are disabled.
- **SKILL.md Phase 5 quality gates renumbered.** Former gate 5 (em-dash) → gate 7. Former gate 6 (content hygiene) → gate 8. Phase 5 "re-run" reference updated from `steps 4–6` to `steps 4–8`.
- **SKILL.md Phase 6 output summary** now includes `🛡 spec-validate: PASS` and `🛡 html-render-check: PASS` lines before the existing em-dash and content hygiene lines.

---

## [1.2.0] - GSMAi post-run fixes: correctness, hygiene, parallelism

### Fixed

- **Gong C2 transcript SQL — `CT.CONVERSATION_KEY` compilation error.** The C2 query in `references/research-protocol.md` mixed implicit comma-join (`CALL_TRANSCRIPTS ct, LATERAL FLATTEN(...) t`) with an explicit `JOIN`, putting the `ct` alias out of scope in the `ON` clause. Rewrote to use `JOIN LATERAL FLATTEN(...) t ON TRUE` + explicit `JOIN` for `CONVERSATION_PARTICIPANTS`. Added `AND ct.TRANSCRIPT IS NOT NULL` to the `WHERE` clause and a NULL fallback rule: when TRANSCRIPT is NULL for a given key, fall back to `CALL_SPOTLIGHT_BRIEF` from C1 and record `[FALLBACK: CALL_SPOTLIGHT_BRIEF — TRANSCRIPT NULL]` in the evidence file.
- **Asset path resolution when invoked from a different plugin directory.** All file reads in SKILL.md Phase 1 (`assets/snowflake_pricing_master.json`, `sizing-methodology.md`, `html-spec.md`, `research-protocol.md`) now use absolute `~/Snowflake/Repos/aross-se-superpowers/plugins/snowflake-sizing/...` paths. Previously, relative paths resolved against the caller's working directory (e.g. `rfp-wizard`), causing a "File not found" failure for the pricing JSON.
- **Azure credit rate region mismatch.** The model was resolving freeform region text (e.g. "Azure North Europe") by partial string similarity and could land on the wrong row (e.g. `Sweden Central` at $3.60 instead of `North Europe (Ireland)` at $3.90). Root-fixed by a new alias table in SKILL.md Phase 1 (see Added below).
- **`temp/` path in evidence file template.** `references/research-protocol.md` §4 template still referenced `temp/<slug>-<N>year-sizing.html` (pre-`sizings/` era). Updated to `sizings/<slug>-<N>year-sizing-v1-<YYYY-MM-DD>.html`.
- **Document AI removed from sizing specs.** `document_ai`, `ai_parse_document_layout`, and `ai_parse_document_ocr` are deprecated and superseded by `AI_EXTRACT`. SKILL.md Phase 3 now explicitly prohibits these three features in new specs. `sizing-methodology.md` Document AI section replaced with a deprecation notice pointing to `ai_extract` (default 70M tokens/month for document-heavy use cases).
- **`cortex_complete` model default.** SKILL.md Phase 3 now specifies `claude-sonnet-4-6` (input: 1.65 AI cr/M, output: 8.25 AI cr/M) as the mandatory default. `sizing-methodology.md` Cortex Complete table updated: `claude-sonnet-4-6` added as first row with `← DEFAULT` marker; `claude-4-sonnet` (1.50/7.50) kept as legacy reference row.

### Added

- **Region alias table (Phase 1).** New "Region name resolution" block in SKILL.md Phase 1. Before looking up `credit_rate`, the model resolves user-supplied shorthand (e.g. `"North Europe"`, `"London"`, `"Virginia"`) to the canonical key in `credit_pricing.data`. Covers 10 common aliases across AWS/Azure/GCP. If no alias matches, the model prints the attempted string and the full key list for SE confirmation. After resolving, always prints `Region: <resolved key> | Credit rate: $X.XX/credit (<Edition>)` to the terminal before proceeding.
- **Content hygiene rules (Phase 3).** New `§ Content Hygiene (MANDATORY)` block added before the "Work through categories" section. Explicitly bans from all customer-facing fields (`label`, `justification`, `note`, `description`): individual personal names from Gong transcripts, internal file names (`sizing-methodology.md`, `customer-context.md`, etc.), raw citation prefixes (`SOURCED:`, `ASSUMPTION:`, `REQUIRES_CONFIRMATION:`), and internal tool references. Clarifies that citation labels belong only in the JSON `source` metadata field; justification text must be plain customer-facing prose.
- **Content hygiene gate (Phase 5, BLOCKING).** New quality gate runs after the em-dash gate. A short Python one-liner scans the generated HTML for banned patterns (`SOURCED:`, `ASSUMPTION:`, `sizing-methodology.md`, `customer-context.md`, `research-evidence.md`, `html-spec.md`, `research-protocol.md`). If any match, the gate exits non-zero and blocks Phase 6. Phase 6 output summary now includes `🛡 content hygiene: PASS`.

### Changed

- **Phase 1 reference reads parallelised.** SKILL.md instruction updated: all four Phase 1 reads (pricing JSON + 3 reference `.md` files) are launched in a single parallel batch. Previously the instruction said "read reference documents in parallel" but the pricing read was listed separately, encouraging sequential execution.
- **Phase 2 parallelism made explicit.** New `PARALLELISM RULE` block: A, B1, B2, B3, and C1 MUST run simultaneously in one batch. C2 launches the moment C1 returns — does NOT wait for A/B. Previously the protocol said "run in parallel" but lacked an explicit sequencing rule for C2, leading to full A/B/C completion before C2 was started.

---

### Added

- **Portable `.json` sizing spec.** Every skill run now writes the complete `SIZING_SPEC` object as a pretty-printed `.json` file alongside the HTML proposal. The spec is written **first** (before template substitution) so it is persisted even if HTML generation fails. It is the source of truth from which the HTML is derived and from which future export formats (PPTX, DOCX, XLSX) will be generated. Spec shape is identical to the `SIZING_SPEC` already embedded in the HTML — no structural changes.
- **`sizings/` output directory.** Both the HTML proposal and the `.json` spec are now written to the new git-tracked `sizings/` directory (was `temp/`). `temp/` remains git-ignored and is used only for scratch files (research evidence). Versioned filename convention: `<slug>-<N>year-sizing-v<version_number>-<YYYY-MM-DD>.{html,json}`.
- **"Export JSON" button.** Added to the proposal HTML next to "Save Version". Downloads the current `SIZING_SPEC` (including any browser edits) as a `.json` file using the same `<slug>-<N>year-sizing-v<N>-<YYYY-MM-DD>.json` naming convention. Enables round-tripping browser edits back to disk and provides the input file for future export skills (`/export-pptx`, `/export-xlsx`, etc.).

### Changed

- **SKILL.md Phase 5 rewritten as spec-first.** Step 1 is now: write `sizings/<slug>-<N>year-sizing-v1-<date>.json`. Step 2 onward: read template, substitute tokens, write `sizings/<slug>-<N>year-sizing-v1-<date>.html`. Quality check grep paths updated to `sizings/`. Phase 6 output summary updated to list all three artifacts.
- **Output paths changed from `temp/` to `sizings/`.** The HTML proposal and new JSON spec are written to `sizings/` (git-tracked). The research evidence file remains in `temp/` (git-ignored). `commands/snowflake-sizing.md` and `README.md` updated accordingly.

---

### Added

- **Optional Platform Credit discount override.** New toggle in the Global Settings tab lets the SE apply a negotiated capacity discount to all Platform-Credit-priced calculations (warehouses, serverless, replication compute). Two mutually-linked inputs accept either an exact net rate ($/credit) or a discount %; editing one auto-derives the other against the list rate. Read-only "List rate" and "Effective rate" displays bracket the inputs. Off by default; toggling off reverts to the list rate without losing what was typed. Persists in `SIZING_SPEC.meta.discount` (snapshot-safe). The header rate display updates live and renders a subtle ` (N% off list)` badge when the toggle is on. **AI Credits are intentionally untouched** ($2.00 global / $2.20 regional remain fixed) per Snowflake's [AI Pricing Sales GTM FAQ](https://docs.google.com/document/d/10k7wZLUN3tybElajcKuSccplCaYx4xEmx70HovXbVrw): *"Negotiated capacity discounts do not apply to AI Credits."* New JS helpers: `applyDiscount()`, `toggleDiscount()`, `updateDiscount()`. New header span `#hdr-discount-badge`. New CSS class `.discount-badge`. New `meta.list_credit_rate` field preserves the pricing-JSON rate; `meta.credit_rate` is the effective rate every calculation reads.
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

- **Storage tab breakdown table now stays live.** `recalculate()` now calls `updateStorageBreakdown()` at the end of every recalc cycle. Previously the per-year Compressed TB / Time Travel TB / Failsafe TB / Total TB / Annual $ table inside the Storage tab was rendered once at `DOMContentLoaded` and never refreshed — any change to Raw TB, Compression ratio, Annual growth %, Time Travel days, Churn rate %, Contract years, or Cloud+Region left it stale. A null guard on `storage-breakdown` makes the call safe before the Storage tab is first opened.
- **`storage_rate_per_tb` now re-derived when Cloud+Region changes.** `updateGlobal()` already looked up `list_credit_rate` from `PRICING_DATA.credit_pricing` on edition/cloud/region changes but silently kept the old storage rate. Switching regions (e.g. AWS US East -> Azure West Europe) now also looks up `PRICING_DATA.storage.standard.data` by `cloud` + `region` and updates `SIZING_SPEC.meta.storage_rate_per_tb` so KPI tiles and Year-by-Year Breakdown reflect the correct regional storage rate immediately.
- **Global Settings "List rate" display refreshes after region/edition change.** After `updateGlobal()` updates `list_credit_rate`, `populateGlobalSettings()` is now called to re-render the Global Settings panel. Previously the disabled "List rate ($/credit)" input kept the old value even though the header rate badge (via `updateHeaderInfo()`) had already updated.
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
- **SKILL.md Phase 5 quality check is now BLOCKING** and includes the em-dash gate. After token substitution, the skill must run `python3 assets/emdash-check.py temp/<slug>-<N>year-sizing.html temp/<slug>-research-evidence.md` and replace any U+2014 with `-` until the gate exits 0 before reporting success.
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

- **Glean B1/B2/B3 now run in the main agent (Phase 1.7).** Glean MCP OAuth is session-bound and does not propagate to subagents, which caused the previous `research-glean-agent` to fail at runtime. The main `snowflake-sizing` skill now executes B1/B2/B3 inline in a new Phase 1.7 (between bootstrap and routing) and forwards the results in-memory to `research-coordinator` under `Pre-fetched Glean Results:`. The coordinator transforms the blob into the Glean section of the evidence file using the template in `references/research-protocol.md` Section 1. **Removed `agents/research-glean-agent.md`** (no remaining callers). The coordinator's preflight is reduced to SNOWHOUSE Gong only - the Glean preflight is implicit since the parent agent already proved Glean availability by running the queries successfully. Mirrors the pattern established in `plugins/se-comments/skills/se-comments-batch/SKILL.md` Step 1.5.
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
