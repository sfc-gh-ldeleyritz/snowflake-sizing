#!/usr/bin/env python3
"""
SessionStart hook for snowflake-sizing.

On 'startup' source only (not 'resume'/'clear'/'compact'):

1. Ensures the `temp/` and `sizings/` directories exist in the current
   working directory. spec-prepare.py and the agent's evidence-file
   writes both assume these dirs exist; first-run failures used to
   surface as `FileNotFoundError` from inside the hook chain.
2. Removes stale `temp/*-research-evidence.md` files older than 30 days.
   Other temp content (temp/resources/, temp/build_sizing.py, etc.) is
   left untouched per user direction.

This hook only emits output if it actually did something visible (created
a directory or removed stale evidence), to keep the session startup quiet.
"""

import datetime
import json
import pathlib
import sys

_PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent.parent
_PLUGIN_TEMP_DIR = _PLUGIN_ROOT / "temp"
_STALE_DAYS = 30

# Directories the skill expects to exist in the user's working directory
# the moment they invoke `/snowflake-sizing`. Auto-creating them removes a
# whole class of first-run FileNotFoundError failures from spec-prepare.py
# and the agent's evidence-file writes.
_CWD_BOOTSTRAP_DIRS = ("temp", "sizings")


def cleanup_stale_evidence():
    if not _PLUGIN_TEMP_DIR.is_dir():
        return []

    cutoff = datetime.datetime.now().timestamp() - (_STALE_DAYS * 86400)
    removed = []
    for p in _PLUGIN_TEMP_DIR.glob("*-research-evidence.md"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                removed.append(p.name)
        except OSError:
            continue
    return removed


def ensure_cwd_dirs() -> list[str]:
    """Create `temp/` and `sizings/` in CWD if missing. Returns the list of
    directories created (empty when both already existed)."""
    created: list[str] = []
    cwd = pathlib.Path.cwd()
    for name in _CWD_BOOTSTRAP_DIRS:
        target = cwd / name
        if target.exists():
            continue
        try:
            target.mkdir(parents=True, exist_ok=True)
            created.append(name)
        except OSError:
            # Permission failures etc. are non-fatal - the agent will see
            # the FileNotFoundError later and surface it. Don't wedge the
            # session startup over a CWD bootstrap.
            continue
    return created


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if data.get("hook_event_name") != "SessionStart":
        sys.exit(0)

    if data.get("source") != "startup":
        sys.exit(0)

    created_dirs = ensure_cwd_dirs()
    removed = cleanup_stale_evidence()

    msg_parts: list[str] = []
    if created_dirs:
        msg_parts.append(
            "snowflake-sizing: created working directories "
            + ", ".join(f"./{d}/" for d in created_dirs)
        )
    if removed:
        msg_parts.append(
            f"snowflake-sizing: cleaned up {len(removed)} stale research-evidence "
            f"file(s) (>{_STALE_DAYS} days): {', '.join(removed)}"
        )

    if msg_parts:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": "\n".join(msg_parts),
                    }
                }
            )
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
