#!/usr/bin/env python3
"""Scan a sizing HTML/JSON for forbidden content-hygiene patterns.

Detects citation prefixes, internal artefact filenames, and other tokens
that must never appear in customer-facing fields. Mirrors the inline
python3 -c "..." gate that previously lived in SKILL.md Phase 5 step 8.

Exit 0 if every scanned file is clean.
Exit 1 if any forbidden pattern is found, with file:occurrence locations.

Usage:
    python3 content-hygiene-check.py path1.html [path2.html ...]
"""
import pathlib
import sys

# Patterns that must never appear inside customer-facing rendered text. The
# JSON `source` metadata field is allowed to contain these; this script
# scans the FULL file (HTML or JSON). For JSON files this means citation
# prefixes are technically allowed, but the script targets HTML output — the
# rendered surface customers see.
#
# When scanning JSON, the script is permissive about citation prefixes
# inside metadata fields (passing JSON through this gate is a belt-and-braces
# secondary check; the primary gate is the HTML scan).
FORBIDDEN_TOKENS = [
    "SOURCED:",
    "ASSUMPTION:",
    "REQUIRES_CONFIRMATION:",
    "sizing-methodology.md",
    "customer-context.md",
    "research-evidence.md",
    "html-spec.md",
    "research-protocol.md",
]


def scan(paths):
    findings = []
    scanned = 0
    for raw in paths:
        p = pathlib.Path(raw)
        if not p.exists() or not p.is_file():
            findings.append(f"{raw}: file not found")
            continue
        scanned += 1
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            findings.append(f"{raw}: read error: {exc}")
            continue
        # JSON specs are allowed to carry citation prefixes inside the
        # `source` metadata field; only flag them when scanning HTML.
        is_json = p.suffix.lower() == ".json"
        for token in FORBIDDEN_TOKENS:
            if is_json and token.endswith(":"):
                # SOURCED: / ASSUMPTION: / REQUIRES_CONFIRMATION: — allowed
                # inside JSON source metadata; skip in JSON files.
                continue
            if token in text:
                # Locate first occurrence for the error message.
                idx = text.find(token)
                # Compute line:col of first hit for actionable feedback.
                prefix = text[:idx]
                lineno = prefix.count("\n") + 1
                col = idx - prefix.rfind("\n")
                findings.append(f"{raw}:{lineno}:{col}: '{token}' present")
    return scanned, findings


def main():
    args = sys.argv[1:]
    if not args:
        print("usage: content-hygiene-check.py path1 [path2 ...]", file=sys.stderr)
        sys.exit(2)
    scanned, findings = scan(args)
    if findings:
        print("content-hygiene-check: FAILED")
        for line in findings:
            print(" ", line)
        print(
            f"  ({len(findings)} occurrence(s) across {scanned} scanned file(s))"
        )
        sys.exit(1)
    print(f"content-hygiene-check: OK ({scanned} file(s) clean)")


if __name__ == "__main__":
    main()
