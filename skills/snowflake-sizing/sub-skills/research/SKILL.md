---
name: snowflake-sizing-research
description: Phase 2 of snowflake-sizing - dispatch the research-coordinator which fans out three specialist subagents (Glean / Gong / Replication) in parallel.
---

# Research sub-skill (snowflake-sizing)

Loaded by the parent `snowflake-sizing` skill once `meta` is bootstrapped.
This sub-skill is a thin launcher: the protocol detail lives in
`references/research-protocol.md` and the heavy lifting is delegated to
`agents/research-coordinator.md`, which in turn fans out three specialist
agents (`research-glean-agent`, `research-gong-agent`,
`research-replication-agent`) in parallel so the main agent's context
stays slim and wall-clock time drops.

---

## Phase 1.5 - Preflight (delegated)

The research-coordinator runs the preflight (Glean MCP availability +
SNOWHOUSE Gong access). Hard gate - aborts with the exact setup
instructions if either fails.

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

The coordinator runs preflight, then launches the three specialists in
parallel (only the ones that apply: skip-flagged surfaces are not
spawned, and the replication specialist runs only when triggered). Each
specialist writes its own fragment under `temp/`; the coordinator
concatenates them into the final evidence path and returns ONLY a slim
summary - never raw transcripts or Glean blobs.

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

3. Hand control back to the parent `snowflake-sizing` skill, which will
   invoke the `build-spec` sub-skill next.

## Pre-fetched batch mode

If the parent invocation passed `Pre-fetched Glean Results:` and `Pre-fetched
Gong Results:` blobs in the prompt, pass these forward to the
research-coordinator in its prompt. The coordinator will route each blob
to the corresponding specialist, which skips its live queries and still
produces its fragment from the pre-fetched data - the audit trail is
required regardless of how the data was fetched.
