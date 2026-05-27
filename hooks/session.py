#!/usr/bin/env python3
"""
SessionStart cleanup hook for snowflake-sizing.

On 'startup' source only (not 'resume'/'clear'/'compact'), removes stale
temp/*-research-evidence.md files older than 30 days. Other temp content
(temp/resources/, temp/build_sizing.py, etc.) is left untouched per user
direction.

This hook only emits output if it actually removed something, to keep the
session startup quiet.
"""

import datetime
import json
import pathlib
import sys

_PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent.parent
_TEMP_DIR = _PLUGIN_ROOT / "temp"
_STALE_DAYS = 30


def cleanup_stale_evidence():
    if not _TEMP_DIR.is_dir():
        return []

    cutoff = datetime.datetime.now().timestamp() - (_STALE_DAYS * 86400)
    removed = []
    for p in _TEMP_DIR.glob("*-research-evidence.md"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                removed.append(p.name)
        except OSError:
            continue
    return removed


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if data.get("hook_event_name") != "SessionStart":
        sys.exit(0)

    if data.get("source") != "startup":
        sys.exit(0)

    removed = cleanup_stale_evidence()
    if removed:
        msg = (
            f"snowflake-sizing: cleaned up {len(removed)} stale research-evidence "
            f"file(s) (>{_STALE_DAYS} days): {', '.join(removed)}"
        )
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": msg,
                    }
                }
            )
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
