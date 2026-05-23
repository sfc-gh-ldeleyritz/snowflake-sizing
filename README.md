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

Two artifacts:

- `temp/<customer-slug>-<N>year-sizing.html` — single self-contained interactive proposal.
- `temp/<customer-slug>-research-evidence.md` — Glean + Gong audit trail (B1/B2/B3 hits, Gong call inventory with retry log, verbatim transcript turns, and sizing-impacting findings).

Open the HTML in any browser. The proposal includes:
- Executive summary with live TCV, Year 1 cost, and total credits
- Year-by-year bar chart and workload breakdown donut
- Interactive sliders for every variable (warehouse size, hours, clusters, serverless features, AI tokens, storage, etc.)
- 3-scenario comparison (Conservative / Expected / Aggressive)
- All assumptions listed with source citations
- Items requiring customer confirmation with quantified impact

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
