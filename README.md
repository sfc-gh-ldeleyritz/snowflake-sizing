# snowflake-sizing

Generate accurate, defensible Snowflake consumption estimates and interactive customer-facing HTML proposals.

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

A single self-contained HTML file at `temp/<customer-slug>-<N>year-sizing.html`.

Open it in any browser. The proposal includes:
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

Snowflake brand colours (`#29B5E8`, `#11567F`) and Open Sans font (via Google Fonts CDN). The Snowflake logo is rendered as inline SVG.
