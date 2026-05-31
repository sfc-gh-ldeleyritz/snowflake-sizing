"""create-sizing-template.py - One-time script to generate sizing-base-template.pptx.

Loads the Snowflake master PPTX template, strips all 23 existing slides (keeping
the 7 slide masters + layouts + themes intact), then adds 7 blank sizing slides
using named layouts.  Saves the result to:

    plugins/snowflake-sizing/assets/templates/sizing-base-template.pptx

Run once and commit the output to version control.  build_pptx.py will load this
file as its base presentation so that all slide masters, brand colours, and named
layouts are available at render time.

Usage:
    cd plugins/snowflake-sizing
    python3 scripts/create-sizing-template.py
"""
from __future__ import annotations

import pathlib
import sys

from pptx import Presentation
from pptx.oxml.ns import qn

_SCRIPT_DIR   = pathlib.Path(__file__).resolve().parent
_PLUGIN_ROOT  = _SCRIPT_DIR.parent
_PPTX_PLUGIN  = _PLUGIN_ROOT.parent / "snowflake-pptx"

SOURCE_TEMPLATE = _PPTX_PLUGIN / "assets" / "templates" / "SNOWFLAKE TEMPLATE JANUARY 2026.pptx"
OUT_PATH        = _PLUGIN_ROOT / "assets" / "templates" / "sizing-base-template.pptx"

# Ordered slide configs: (layout_name, human_purpose)
SLIDE_CONFIGS = [
    ("1_Data Cloud_1_1_2", "cover"),
    ("One Column Layout",  "exec_summary"),
    ("One Column Layout",  "workloads"),
    ("One Column Layout",  "year_chart"),
    ("One Column Layout",  "serverless_ai"),
    ("One Column Layout",  "assumptions"),
    ("Thank You_1",        "closer"),
]


def find_layout(prs: Presentation, name: str):
    """Return the first slide layout matching *name* across all masters."""
    for master in prs.slide_masters:
        for layout in master.slide_layouts:
            if layout.name == name:
                return layout
    raise ValueError(
        f"Layout {name!r} not found in template.\n"
        "Available layouts:\n" +
        "\n".join(
            f"  [{master.slide_layouts.index(l)}] {l.name!r}"
            for master in prs.slide_masters
            for l in master.slide_layouts
        )
    )


def remove_all_slides(prs: Presentation) -> int:
    """Remove all slides from *prs* without touching masters/layouts."""
    sldIdLst = prs.slides._sldIdLst
    count = len(list(sldIdLst))
    for sId in list(sldIdLst):
        rId = sId.get(qn("r:id"))
        prs.part.drop_rel(rId)
        sldIdLst.remove(sId)
    return count


def main() -> None:
    if not SOURCE_TEMPLATE.is_file():
        print(f"ERROR: source template not found:\n  {SOURCE_TEMPLATE}", file=sys.stderr)
        print("\nMake sure the snowflake-pptx plugin is present at the expected path.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading: {SOURCE_TEMPLATE}")
    prs = Presentation(str(SOURCE_TEMPLATE))
    print(f"  Slide masters:  {len(prs.slide_masters)}")
    print(f"  Existing slides: {len(prs.slides)}")

    removed = remove_all_slides(prs)
    print(f"  Removed {removed} slides")

    print(f"\nAdding {len(SLIDE_CONFIGS)} sizing slides:")
    for layout_name, purpose in SLIDE_CONFIGS:
        layout = find_layout(prs, layout_name)
        prs.slides.add_slide(layout)
        print(f"  + [{purpose}] layout={layout_name!r}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUT_PATH))
    size_kb = OUT_PATH.stat().st_size // 1024
    print(f"\nSaved: {OUT_PATH}  ({size_kb} KB)")
    print("Done. Commit assets/templates/sizing-base-template.pptx to version control.")


if __name__ == "__main__":
    main()
