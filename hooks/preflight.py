#!/usr/bin/env python3
"""
UserPromptSubmit preflight hook for snowflake-sizing.

Detects /snowflake-sizing slash command invocations and $snowflake-sizing
skill activations. Injects a reminder of the two prerequisites (Glean MCP,
SNOWHOUSE connection) and the content-hygiene rules so the agent has them
before Phase 1.5 runs.

The skill itself still hard-fails at Phase 1.5 if either prerequisite is
missing; this hook just gives a faster, clearer signal up front.
"""

import json
import sys

DOMAIN_TRIGGERS = [
    "/snowflake-sizing",
    "$snowflake-sizing",
]

KEYWORD_PAIRS = [
    ("snowflake", "sizing"),
    ("snowflake", "consumption estimate"),
    ("snowflake", "pricing proposal"),
]


def is_relevant_prompt(prompt: str) -> bool:
    text = prompt.lower()
    for trig in DOMAIN_TRIGGERS:
        if trig in text:
            return True
    for a, b in KEYWORD_PAIRS:
        if a in text and b in text:
            return True
    return False


CONTEXT_REMINDER = (
    "snowflake-sizing context reminder:\n\n"
    "PREREQUISITES (the skill will hard-fail at Phase 1.5 if either is missing):\n"
    "  1. Glean MCP must be configured:\n"
    "       cortex mcp add glean https://snowflake-be.glean.com/mcp/default --transport http\n"
    "  2. SNOWHOUSE connection with GONG_SHARE.GONG_DATA_CLOUD access must be active:\n"
    "       cortex connections set snowhouse\n"
    "     Verify with: cortex connections list\n\n"
    "PRE-WRITE GUARD (hooks/sizing-guard.py runs on every Write to sizings/*.json,\n"
    "sizings/*.html, and temp/*-evidence*.md - blocks BEFORE the file lands):\n"
    "  - JSON: schema validation, legacy field-name detection (run\n"
    "    scripts/spec-prepare.py to auto-rename), leakage-field rejection.\n"
    "  - HTML: em-dash, content-hygiene tokens, unsubstituted __TOKEN__\n"
    "    leftovers, Node sidecar JS render check (catches $0-renders).\n"
    "  - Evidence: em-dash scan to keep transcripts paste-safe.\n\n"
    "BUILD-SPEC FLOW (v1.9): write a small patch dict, then call\n"
    "scripts/spec-prepare.py --patch <patch.json> --out sizings/<slug>.json.\n"
    "spec-prepare deep-merges over framework/sizing_spec_skeleton.json,\n"
    "auto-renames legacy field names, and stamps an authoritative\n"
    "computed_totals block. Required ai_cortex keys are 9 (not 12);\n"
    "Document AI keys are now optional. Top-level array key is 'workloads',\n"
    "NEVER 'warehouses' (renders as $0).\n"
    "  - See framework/sizing_spec_schema.json for the canonical contract.\n"
)


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    prompt = data.get("prompt", "")
    if not is_relevant_prompt(prompt):
        sys.exit(0)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": CONTEXT_REMINDER,
        }
    }
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
