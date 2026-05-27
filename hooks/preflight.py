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
    "CONTENT HYGIENE (enforced by hooks/content-hygiene.py on every Write to sizings/*.html):\n"
    "  - No personal names from Gong transcripts in customer-facing fields.\n"
    "  - No internal artefact filenames (sizing-methodology.md, customer-context.md, etc.).\n"
    "  - No citation prefixes (SOURCED:, ASSUMPTION:, REQUIRES_CONFIRMATION:) in visible text.\n"
    "  - Citation prefixes belong only in the JSON 'source' metadata field.\n\n"
    "VALIDATION (enforced by hooks/validate-sizing-json.py on every Write to sizings/*.json):\n"
    "  - Top-level array key is 'workloads', NEVER 'warehouses' (renders as $0).\n"
    "  - All 12 ai_cortex.* keys must be present (set enabled:false if unused) -\n"
    "    populateAIPanel() throws TypeError on missing keys, page renders $0.\n"
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
