# snowflake-sizing

Generate accurate, defensible Snowflake consumption estimates and interactive customer-facing HTML proposals.

## Prerequisites

The skill performs mandatory live research against Glean and Gong. It will hard-fail at preflight if either is unavailable.

- **Glean MCP** — `cortex mcp add glean https://snowflake-be.glean.com/mcp/default --transport http`
- **SNOWHOUSE connection with `GONG_SHARE.GONG_DATA_CLOUD` access** — `cortex connections set snowhouse` (verify with `cortex connections list`)

Reduced research is only allowed via the narrow exceptions clause in `skills/snowflake-sizing/SKILL.md` (Phase 2 EXCEPTIONS).

## Usage

```bash
/snowflake-sizing <context-file> [options]
```

**Options:**

| Option | Default | Description |
|---|---|---|
| `--customer "Name"` | (from context file) | Customer name for proposal |
| `--years N` | `3` | Contract length in years |
| `--edition X` | `Enterprise` | Standard / Enterprise / Business Critical / VPS |
| `--region "X"` | `"AWS US East (Northern Virginia)"` | Full region string |

## Example

```bash
/snowflake-sizing temp/acme-discovery-notes.txt --customer "ACME Corp" --years 3 --edition Enterprise --region "AWS Europe (London)"
```

## Output

Three artifacts:

- `sizings/<customer-slug>-<N>year-sizing-v1-<YYYY-MM-DD>.html` — single self-contained interactive proposal.
- `sizings/<customer-slug>-<N>year-sizing-v1-<YYYY-MM-DD>.json` — portable sizing spec (the `SIZING_SPEC` object). Source of truth for the HTML and future export formats (PPTX, DOCX, XLSX).
- `temp/<customer-slug>-research-evidence.md` — Glean + Gong audit trail (B1/B2/B3 hits, Gong call inventory with retry log, verbatim transcript turns, and sizing-impacting findings).

The `sizings/` directory holds customer outputs; the generated `.html` and `.json` files are git-ignored (only the directory itself ships, via `.gitkeep`). `temp/` is also git-ignored (scratch files only).

### Sizing Spec (`.json`)

The `.json` file contains the complete `SIZING_SPEC` object — all workloads, serverless features, AI config, storage, metadata, assumptions, and confirm_required items. It is the source of truth from which the HTML is derived and from which future export formats (PPTX, DOCX, XLSX) will be generated.

**Browser round-trip:** Open any saved HTML and click **Export JSON** to extract the current `SIZING_SPEC` (including any browser edits) back to a `.json` file.

Open the HTML in any browser. The proposal is fully interactive — all configuration changes propagate immediately to all output sections (KPI tiles, Year-by-Year Breakdown, charts, Scenario Comparison).

### Interactive tabs

| Tab | What you can edit |
|---|---|
| **Global Settings** | Cloud / Region / Edition, contract years, annual growth %, default ramp curve, dev-start / go-live months, Platform Credit discount override |
| **Warehouses** | Size, hours/day, days/month, cluster min/max, auto-suspend; add / delete workload cards |
| **Serverless** | Toggle and size each serverless feature (Snowpipe, Search Optimization, Materialized Views, Dynamic Tables, etc.) |
| **AI / Cortex** | Cortex Complete, Cortex Agents, Snowflake Intelligence, Cortex Code (CLI / Snowsight / Desktop surfaces), Cortex Analyst, Cortex Search, Document AI, AI Functions |
| **SPCS** | Instance type, generation, node count, hours/month; add / delete instances |
| **OpenFlow** | Deployment (SPCS / BYOC), source connections, vCPU, hours/month; add / delete connectors |
| **Storage** | Raw TB, compression ratio, annual growth %, Time Travel days, churn rate %; per-year breakdown table refreshes live |
| **Collaboration** | Reader and Managed accounts with warehouse size, hours/day, days/month; add / delete accounts |
| **Replication** | Source / target regions, initial TB, monthly change TB, credits/TB, replica storage rate, growth/YoY; enable / disable per relationship |

### Output sections (all update live)

- **KPI tiles** — TCV, Year 1 cost, total credits, effective credit rate
- **Year-by-Year Breakdown** — per-workload credit and dollar totals for each contract year
- **Stacked bar chart** — annual spend by workload group
- **Donut chart** — credit share by workload group
- **Scenario Comparison** — Conservative (10% growth / slow ramp), Expected (20% / linear), Aggressive (35% / fast) side-by-side

### Additional features

- **Birdbox ramp curves** — per-workload power-law ramp from `dev_start_month` to `go_live_month` (Slowest / Slow / Linear / Fast / Fastest / Manual). Global Settings defaults seed all new rows; individual rows can override.
- **Platform Credit discount override** — toggle in Global Settings accepts a net rate ($/credit) or discount %. AI Credits remain fixed at $2.00 global / $2.20 regional (discount does not apply per Snowflake policy).
- **Save Version** — top-right button snapshots the current `SIZING_SPEC` (including all SE edits), bumps `meta.version_number`, and downloads a self-contained HTML file named `<slug>-<N>year-sizing-v<N>-<YYYY-MM-DD>.html`.
- **Export JSON** — downloads the current `SIZING_SPEC` as a portable `.json` file (same name convention as Save Version). Use this to round-trip browser edits back to disk, or to feed future export skills for PPTX/DOCX/XLSX generation.
- **Per-feature tooltips** — `ⓘ` icon next to every togglable feature explains what it is and how it bills. Hidden in print mode.
- **Editable assumptions** — Stated Assumptions and Requires Confirmation items are `contenteditable` in the browser. Add, delete, or reword inline; changes persist in `SIZING_SPEC` and are saved by Save Version.
- **Scenario toggle** — checkbox above the Scenario Comparison grid to show/hide the Conservative and Aggressive cards.
- **Print / Save as PDF** — floating button opens the browser print dialog. `@media print` hides all interactive controls, expands all tabs in flow, and reflows Chart.js canvases to A4 width.

## Context File Format

Any combination of:
- Call transcripts (plain text or copied from Gong)
- Completed sizing questionnaire (Word, PDF, or plain text)
- Discovery notes
- Company background

The more detail the better. Missing information will be flagged as assumptions or confirmed requirements.

## Pricing Data

Bundled in `assets/snowflake_pricing_master.json` — based on the Snowflake Service Consumption Table effective **2026-05-12**.

To update: edit `assets/snowflake_pricing_master.json` and update `metadata.effective_date`.

## Branding

Snowflake brand colours (`#29B5E8`, `#11567F`) applied throughout. The generated HTML embeds the official Snowflake wordmark and uses the official Texta + Lato + Source Code Pro fonts (base64-inlined) — no font CDN, fully offline-capable.

Brand assets are bundled under `assets/branding/`. To regenerate the inlinable font snippet after updating the source woff2 files:

```bash
bash assets/branding/build-snippets.sh
```
