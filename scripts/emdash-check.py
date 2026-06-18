#!/usr/bin/env python3
"""Scan one or more files for U+2014 em-dash characters.

Exit 0 if every scanned file is clean.
Exit 1 if any em-dash is found, with file:line:col locations printed so
the caller can fix them.

This script's own source must remain free of literal U+2014 chars, so the
target codepoint is referenced via chr(0x2014).

Usage:
    python emdash-check.py path1 [path2 ...]
"""
import pathlib
import sys

EM_DASH = chr(0x2014)


def scan(paths):
    findings = []
    scanned = 0
    for raw in paths:
        p = pathlib.Path(raw)
        if not p.exists() or not p.is_file():
            continue
        scanned += 1
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            findings.append(f"{raw}: read error: {exc}")
            continue
        if EM_DASH not in text:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            idx = line.find(EM_DASH)
            while idx != -1:
                findings.append(f"{raw}:{lineno}:{idx + 1}: em-dash (U+2014)")
                idx = line.find(EM_DASH, idx + 1)
    return scanned, findings


def main():
    args = sys.argv[1:]
    if not args:
        print("usage: emdash-check.py path1 [path2 ...]", file=sys.stderr)
        sys.exit(2)
    scanned, findings = scan(args)
    if findings:
        print("emdash-check: FAILED")
        for line in findings:
            print(" ", line)
        print(
            f"  ({len(findings)} occurrence(s) across {scanned} scanned file(s))"
        )
        sys.exit(1)
    print(f"emdash-check: OK ({scanned} file(s) clean)")


if __name__ == "__main__":
    main()
