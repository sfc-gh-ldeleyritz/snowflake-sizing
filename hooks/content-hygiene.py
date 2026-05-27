#!/usr/bin/env python3
"""
PostToolUse content-hygiene hook for snowflake-sizing.

Fires on Write tool calls to sizings/*.html. Wraps scripts/content-hygiene-check.py
to block writes that contain forbidden citation prefixes or internal artefact
filenames in customer-facing text.

Decision protocol:
  - {"decision": "block", "reason": "..."}  -> agent must fix and retry
  - exit 0 with no output                    -> approved
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile

_PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent.parent
_HYGIENE_SCRIPT = _PLUGIN_ROOT / "scripts" / "content-hygiene-check.py"


def is_sizing_html(path: str) -> bool:
    if not path or not path.lower().endswith(".html"):
        return False
    normalized = path.replace("\\", "/")
    return "/sizings/" in normalized or os.path.basename(os.path.dirname(path)) == "sizings"


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if data.get("tool_name") != "Write":
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    content = tool_input.get("content", "")

    if not is_sizing_html(file_path):
        sys.exit(0)

    if not _HYGIENE_SCRIPT.exists():
        # Don't break the session if the script is missing.
        sys.exit(0)

    # Run the hygiene check against the about-to-be-written content. We can't
    # run it against the file path because Write hasn't completed flush yet
    # in PostToolUse on some hosts; persist content to a temp file instead.
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        proc = subprocess.run(
            ["python3", str(_HYGIENE_SCRIPT), tmp_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        sys.exit(0)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if proc.returncode != 0:
        # Reformat findings to reference the actual target path.
        findings = proc.stdout.replace(tmp_path, file_path)
        reason = (
            f"BLOCKED: Content-hygiene check failed for {file_path}\n\n"
            f"{findings}\n"
            "Citation prefixes (SOURCED:, ASSUMPTION:, REQUIRES_CONFIRMATION:) and "
            "internal artefact filenames must NEVER appear in customer-facing text. "
            "Citation prefixes belong only in the JSON 'source' metadata field of "
            "the SIZING_SPEC.\n\n"
            "Fix the offending fields in the spec, regenerate the HTML, then re-Write."
        )
        print(json.dumps({"decision": "block", "reason": reason}))

    sys.exit(0)


if __name__ == "__main__":
    main()
