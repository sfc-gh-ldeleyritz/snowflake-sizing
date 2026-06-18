#!/usr/bin/env python3
"""Render the proposal HTML for every fixture in tests/fixtures/.

A dev/test helper that batch-renders all sizing-spec fixtures through the same
pipeline as scripts/render-html.py (renderer.compile_spec + the sizing-guard
PreToolUse hook), using the latest assets/templates/proposal-template.html. Use
it to smoke-test that every fixture still renders cleanly after a template or
renderer change.

Usage:
    python3 scripts/render-all-fixtures.py
    python3 scripts/render-all-fixtures.py --out-dir temp/fixtures-html
    python3 scripts/render-all-fixtures.py --fixtures-dir tests/fixtures

Each fixture <name>.json is rendered to <out-dir>/<name>.html. Per-fixture
status is printed; a non-zero exit code is returned if any fixture fails so the
script is CI-friendly.

Exit codes:
    0  every fixture rendered (sizing-guard hook PASS).
    1  one or more fixtures failed to render.
    2  argument / IO error (e.g. no fixtures found).
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import time

_THIS_DIR = pathlib.Path(__file__).resolve().parent
_PLUGIN_ROOT = _THIS_DIR.parent
_RENDER_CLI = _THIS_DIR / "render-html.py"
_DEFAULT_FIXTURES = _PLUGIN_ROOT / "tests" / "fixtures"
_DEFAULT_OUT = _PLUGIN_ROOT / "temp" / "fixtures-html"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fixtures-dir", type=pathlib.Path, default=_DEFAULT_FIXTURES,
                    help="Directory of sizing-spec *.json fixtures (default: tests/fixtures).")
    ap.add_argument("--out-dir", type=pathlib.Path, default=_DEFAULT_OUT,
                    help="Directory to write rendered *.html (default: temp/fixtures-html).")
    ap.add_argument("--template", type=pathlib.Path, default=None,
                    help="Override template path (default: render-html.py's default, the latest proposal template).")
    ap.add_argument("--live", action="store_true",
                    help="Fetch live calculator pricing per fixture. Default: --offline "
                         "(committed seed/cache) for deterministic, network-free smoke tests.")
    args = ap.parse_args()

    fixtures_dir = args.fixtures_dir.resolve()
    out_dir = args.out_dir.resolve()

    if not fixtures_dir.is_dir():
        print(f"error: fixtures dir not found: {fixtures_dir}", file=sys.stderr)
        return 2

    fixtures = sorted(fixtures_dir.glob("*.json"))
    if not fixtures:
        print(f"error: no *.json fixtures in {fixtures_dir}", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Rendering {len(fixtures)} fixture(s) from {fixtures_dir}")
    print(f"            -> {out_dir}\n")

    results: list[tuple[str, bool, str]] = []
    for spec in fixtures:
        out_html = out_dir / (spec.stem + ".html")
        cmd = [sys.executable, str(_RENDER_CLI), "--spec", str(spec), "--out", str(out_html)]
        if not args.live:
            cmd.append("--offline")
        if args.template is not None:
            cmd += ["--template", str(args.template.resolve())]

        t0 = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True)
        dt = time.perf_counter() - t0
        ok = proc.returncode == 0

        # Surface the most useful one-liner from render-html.py's output.
        detail = ""
        for line in (proc.stdout + proc.stderr).splitlines():
            s = line.strip()
            if s.startswith(("core TCV", "sizing-guard hook")):
                detail = s
        if not ok and not detail:
            detail = (proc.stderr.strip() or proc.stdout.strip()).splitlines()[-1:] or [""]
            detail = detail[0] if isinstance(detail, list) else detail

        status = "PASS" if ok else "FAIL"
        size = out_html.stat().st_size if (ok and out_html.exists()) else 0
        print(f"  [{status}] {spec.name:<48} {dt:5.2f}s  {size//1024 if size else 0:>4} KB  {detail}")
        results.append((spec.name, ok, proc.stdout + proc.stderr))

    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    print(f"\n{passed}/{len(results)} rendered OK" + (f", {failed} FAILED" if failed else ""))

    if failed:
        print("\n--- failures ---", file=sys.stderr)
        for name, ok, log in results:
            if not ok:
                print(f"\n### {name}\n{log.strip()}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
