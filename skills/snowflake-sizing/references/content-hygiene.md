# Content Hygiene Rules

Loaded by: `sub-skills/build-spec/SKILL.md` Phase 3 (write rules) and
`sub-skills/render-html/SKILL.md` Phase 5 (gate). Enforced automatically by
`hooks/content-hygiene.py` (PostToolUse on Write to `sizings/*.html`) which
shells out to `scripts/content-hygiene-check.py`.

---

## Forbidden in customer-facing fields

The following MUST NEVER appear in any field that renders as visible text in
the HTML proposal (`label`, `justification`, `note`, `description`, anything
in `assumptions[]` or `confirm_required[].item`):

- **Personal names** from Gong transcripts or internal contacts (first or
  last names of any individuals).
- **Internal artefact filenames**: `sizing-methodology.md`,
  `customer-context.md`, `research-evidence.md`, `html-spec.md`,
  `research-protocol.md`, or any other internal artefact.
- **Citation prefixes** in visible text: `SOURCED:`, `ASSUMPTION:`,
  `REQUIRES_CONFIRMATION:`.
- References to internal tools, systems, or methodology artefacts.
- **Non-USD currency**: currency symbols `£`, `€`, `¥`, any converted figure
  (e.g. `GBP 450,000`, `450k EUR`), or conversion phrasing (`convert to`,
  `exchange rate`, `FX rate`, `indicative @`). All figures are USD and are
  never converted. A `confirm_required` item may *name* a billing currency in
  prose (e.g. "Confirm GBP billing currency with deal desk") as long as it
  carries no converted figure.

## Where citation prefixes ARE allowed

The `source` metadata field on each workload row carries the bare enum value
(`SOURCED`, `ASSUMPTION`, or `ESTIMATED`). The full citation string belongs
in `justification` - which is also customer-facing - so the prefix is
rewritten as plain prose before it lands in `justification`.

Wrong (would fail the gate):

```json
{
  "label": "BI Analytics",
  "justification": "SOURCED: Gong abc123 turn 14 - Jay: 50 concurrent users",
  "source": "SOURCED"
}
```

Right:

```json
{
  "label": "BI Analytics",
  "justification": "Sized for the stated 50 concurrent BI users.",
  "source": "SOURCED"
}
```

Keep raw citations in the evidence file at
`temp/<slug>-research-evidence.md` for audit trail; they don't need to live
in the spec.

## How the gate runs

`scripts/content-hygiene-check.py path1.html [path2.html ...]` exits 0 on
clean files, exits 1 with `file:line:col: '<token>' present` for each
forbidden pattern. The PostToolUse hook wraps the same script and blocks
`Write` calls that introduce a violation.

For JSON files the citation prefixes are tolerated (they appear in the
`source` field as enum values like `SOURCED`); the script only blocks
these tokens when scanning HTML.
