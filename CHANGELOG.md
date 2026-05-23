# snowflake-sizing changelog

## [Unreleased]

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

- **Research is now mandatory.** SKILL.md adds a new `Phase 1.5 — Preflight (BLOCKING)` that hard-fails if the Glean MCP is not configured or the SNOWHOUSE connection is unavailable. The previous `"skip this operation and continue with A + B only"` escape hatch is removed.
- **Phase 2 is now a MANDATORY CHECKPOINT.** All three research operations (context file + Glean B1/B2/B3 + Gong C1/C2) MUST execute. Mandatory two-attempt retry on empty Gong C1 lookups (substring, abbreviation, parent account).
- **New `Phase 2.5 — Report Research Findings (BLOCKING)`** writes a sidecar `temp/<slug>-research-evidence.md` audit trail (Glean hits, Gong call inventory, verbatim transcript turns, sizing-impacting findings) and prints a short summary before Phase 3 may begin.
- **Phase 3 SOURCED tags must cite a concrete artifact** (context-file line, Glean URL, or `Gong <conversation_key[:10]> turn <N> — <speaker>: "<verbatim>"`). ASSUMPTION is only allowed when all three sources are silent on the data point.
- **Narrow EXCEPTIONS clause** — research may only be reduced when `--skip-glean` / `--skip-gong` is explicitly passed and the user confirms in chat, or the customer is `internal-test` / `demo` / `POC-template`. The reduction is logged verbatim in the evidence file.
- **New `references/research-protocol.md`** holds the verbatim Glean queries, Gong SQL templates, retry-on-empty table, and evidence file template.
- **commands/snowflake-sizing.md** now lists Glean + SNOWHOUSE as prerequisites so users get the right setup error early.
