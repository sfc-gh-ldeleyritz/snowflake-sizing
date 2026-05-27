---
name: snowflake-sizing-research
description: Phase 2 of snowflake-sizing - dispatch the research-coordinator which fans out specialist subagents (Gong + optional Replication) in parallel. Glean B1/B2/B3 are pre-fetched by the parent (Phase 1.7) and forwarded as an in-memory blob.
---

# Research sub-skill (snowflake-sizing)

Loaded by the parent `snowflake-sizing` skill once `meta` is bootstrapped
and Phase 1.7 (Glean pre-fetch) has populated `pre_fetched_glean` in
parent-agent memory.

This sub-skill is a thin launcher: the protocol detail lives in
`references/research-protocol.md` and the heavy lifting is delegated to
`agents/research-coordinator.md`, which in turn fans out Gong (and
optionally Replication) specialist agents in parallel so the main agent's
context stays slim and wall-clock time drops. There is **no Glean
specialist subagent** - Glean MCP OAuth is session-bound and only works in
the parent agent, so the coordinator receives the pre-fetched blob and
transforms it into the Glean section of the evidence file directly.

---

## Phase 1.5 - Preflight (delegated)

The research-coordinator runs the SNOWHOUSE Gong preflight only - the
Glean preflight is implicit, since Phase 1.7 of the parent skill already
proved Glean MCP availability by running B1/B2/B3 successfully. Hard
gate - aborts with the exact setup instructions if SNOWHOUSE access fails.

The narrow EXCEPTIONS clause - reduced research is permitted ONLY when:

- `--skip-glean` is explicitly passed AND user confirms in chat.
- `--skip-gong` is explicitly passed AND user confirms in chat.
- Customer name is `internal-test`, `demo`, or `POC-template`.

In any of these cases, the coordinator records the fact verbatim under
`## Research scope reduction` in the evidence file before proceeding.

---

## Phase 2 - Dispatch the research-coordinator (MANDATORY CHECKPOINT)

Launch `research-coordinator` (under `agents/research-coordinator.md`) with:

- `customer` - the parsed customer name (full and short form if both exist)
- `context_file` - the path passed to `/snowflake-sizing`
- Flags: `--skip-glean`, `--skip-gong`, `--mode replication`, `--mode dr`
  (forward whatever the parent skill received)
- `slug` - lowercased customer name with spaces -> hyphens, non-alphanumerics stripped
- `evidence_path` - `temp/<slug>-research-evidence.md`
- **`pre_fetched_glean`** - the in-memory blob built in Phase 1.7 of the
  parent skill, OR `glean_skipped: true` when `--skip-glean` was honored.
  Embed the JSON blob inline in the coordinator's prompt under a
  `Pre-fetched Glean Results:` header so the coordinator can parse it.

The coordinator runs SNOWHOUSE preflight, then launches the Gong specialist
(and optionally the Replication specialist) in parallel - skip-flagged
surfaces are not spawned, and the replication specialist runs only when
triggered. The coordinator transforms `pre_fetched_glean` into the Glean
section of the evidence file directly. Each subagent specialist writes its
own fragment under `temp/`; the coordinator concatenates Glean (from blob)
+ Gong + optional Replication into the final evidence path and returns
ONLY a slim summary - never raw transcripts or Glean blobs.

## Phase 2.5 - Verify and proceed

When the research-coordinator returns:

1. Confirm the evidence file exists at `temp/<slug>-research-evidence.md`.
   If not, abort and surface the coordinator's last message to the user.
2. Print this summary verbatim to the terminal (the coordinator's return
   string is already in this shape):

   ```
   Research complete
      Glean hits: B1=N, B2=N, B3=N
      Gong calls reviewed: <call1> (<date>), <call2> (<date>)
      Top 3 sizing-impacting findings:
      1. ...
      2. ...
      3. ...
      Evidence file: temp/<slug>-research-evidence.md
   Proceeding to build-spec.
   ```

   The Glean hit counts come from `pre_fetched_glean` - the parent agent
   knows them already and the coordinator simply parrots them back.

3. Hand control back to the parent `snowflake-sizing` skill, which will
   invoke the `build-spec` sub-skill next.

## Pre-fetched batch mode (extended)

`pre_fetched_glean` is the **standard** input for this sub-skill (built in
Phase 1.7 of the parent skill). If a higher-level batch orchestrator
(e.g. a sizing-batch wrapper) also pre-fetches Gong results, pass them
forward to the research-coordinator under `Pre-fetched Gong Results:`. The
coordinator will route that blob to the gong specialist, which will skip
its live SQL and produce its fragment from the pre-fetched data - the
audit trail is required regardless of how the data was fetched.
