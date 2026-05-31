"""brand.py - Snowflake brand constants for PPTX generation.

Ported from:
  snowflake-pptx/scripts/node/SnowflakeCreativePptx/brand.js

Slide dimensions: 10.0" x 5.625" (matches SNOWFLAKE TEMPLATE JANUARY 2026.pptx).
Logo: graphic_snowflake_logo_blue.png  (279x62 px, aspect ~4.5:1).
"""
from __future__ import annotations

import pathlib

from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

# ── Colors ────────────────────────────────────────────────────────────────── #

COLORS = {
    "snowflakeBlue":  "29B5E8",
    "navy":           "11567F",   # template theme dk2
    "white":          "FFFFFF",
    "lightGray":      "F2F2F2",
    "darkGray":       "262626",   # template theme dk1
    "starBlue":       "71D3DC",   # template theme accent3
    "valenciaOrange": "FF9F36",
    "firstLight":     "D45B90",
    "purpleMoon":     "7D44CF",   # template theme accent5
}

# Convenience RGBColor objects for the most-used colors.
def rgb(hex_str: str) -> RGBColor:
    """Convert a 6-char hex string (no #) to RGBColor."""
    h = hex_str.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


BLUE   = rgb(COLORS["snowflakeBlue"])
NAVY   = rgb(COLORS["navy"])
WHITE  = rgb(COLORS["white"])
LGRAY  = rgb(COLORS["lightGray"])
DGRAY  = rgb(COLORS["darkGray"])

# Chart series colors in order (compute, serverless, AI, storage).
CHART_SERIES_COLORS = [
    rgb(COLORS["snowflakeBlue"]),
    rgb(COLORS["starBlue"]),
    rgb(COLORS["valenciaOrange"]),
    rgb(COLORS["purpleMoon"]),
]

# ── Fonts ─────────────────────────────────────────────────────────────────── #

FONTS = {
    "heading": "Arial",
    "body":    "Arial",
}

# ── Slide dimensions (10.0" x 5.625") ────────────────────────────────────── #

SLIDE_W = Inches(10.0)
SLIDE_H = Inches(5.625)

# ── Logo + template paths ─────────────────────────────────────────────────── #

# snowflake-pptx is a sibling plugin at plugins/snowflake-pptx/.
# brand.py lives at plugins/snowflake-sizing/renderer/pptx/brand.py, so
# 4 .parent() calls reach the plugins/ directory.
_PPTX_PLUGIN = pathlib.Path(__file__).resolve().parent.parent.parent.parent / "snowflake-pptx"
_LOGO_CANDIDATE = _PPTX_PLUGIN / "assets" / "icons" / "graphic_snowflake_logo_blue.png"

# Fallback: logo inside the sizing plugin's own assets.
_SIZING_PLUGIN = pathlib.Path(__file__).resolve().parent.parent.parent
_LOGO_FALLBACK = _SIZING_PLUGIN / "assets" / "icons" / "graphic_snowflake_logo_blue.png"

# Canonical Snowflake PPTX template (used by build_pptx.py for correct
# slide dimensions; falls back to Presentation() if the file is absent).
TEMPLATE_PATH = _PPTX_PLUGIN / "assets" / "templates" / "SNOWFLAKE TEMPLATE JANUARY 2026.pptx"

# Pre-built 7-slide base template with named layouts (cover, content, closer).
# Generated once by scripts/create-sizing-template.py and committed to the repo.
# build_pptx.py prefers this over TEMPLATE_PATH for faster, layout-aware builds.
BASE_TEMPLATE_PATH = _SIZING_PLUGIN / "assets" / "templates" / "sizing-base-template.pptx"


def logo_path() -> pathlib.Path | None:
    """Return path to the Snowflake logo PNG, or None if not found."""
    for candidate in (_LOGO_CANDIDATE, _LOGO_FALLBACK):
        if candidate.is_file():
            return candidate
    return None


# Logo geometry (279x62 px → aspect 4.496:1).
LOGO_W  = Inches(1.1)
LOGO_H  = Inches(1.1 * 62 / 279)   # ~0.244"
LOGO_X  = SLIDE_W - LOGO_W - Inches(0.2)   # right-aligned with margin
LOGO_Y  = Inches(0.18)

# ── Bottom accent bar ─────────────────────────────────────────────────────── #

BAR_H = Inches(0.24)
BAR_Y = SLIDE_H - BAR_H - Inches(0.22)   # ~5.165"
BAR_X = Inches(0.0)
BAR_W = SLIDE_W

# ── Typography helpers ────────────────────────────────────────────────────── #

# Font sizes as Pt objects for common roles.
SIZE_TITLE      = Pt(32)
SIZE_SUBTITLE   = Pt(18)
SIZE_HEADING    = Pt(14)
SIZE_BODY       = Pt(11)
SIZE_SMALL      = Pt(9)
SIZE_STAT_LABEL = Pt(9)
SIZE_STAT_VALUE = Pt(22)

# Standard content area (leaves room for logo/bar chrome).
CONTENT_L = Inches(0.4)
CONTENT_T = Inches(0.85)
CONTENT_W = SLIDE_W - Inches(0.8)   # 9.2"
CONTENT_H = SLIDE_H - Inches(1.4)   # 4.225"
