"""brand.py - Snowflake brand constants for PPTX generation.

Ported from:
  snowflake-pptx/scripts/node/SnowflakeCreativePptx/brand.js

Slide dimensions: 13.333" x 7.5" (widescreen / LAYOUT_WIDE).
Logo: graphic_snowflake_logo_blue.png  (279x62 px, aspect ~4.5:1).
"""
from __future__ import annotations

import pathlib

from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

# ── Colors ────────────────────────────────────────────────────────────────── #

COLORS = {
    "snowflakeBlue":  "29B5E8",
    "navy":           "1B2A3B",
    "white":          "FFFFFF",
    "lightGray":      "F2F2F2",
    "darkGray":       "333333",
    "starBlue":       "75CDD7",
    "valenciaOrange": "FF9F36",
    "firstLight":     "D45B90",
    "purpleMoon":     "7254A3",
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

# Chart series colors in order (warehouse, serverless, AI, storage).
CHART_SERIES_COLORS = [
    rgb(COLORS["snowflakeBlue"]),
    rgb(COLORS["starBlue"]),
    rgb(COLORS["valenciaOrange"]),
    rgb(COLORS["purpleMoon"]),
]

# ── Fonts ─────────────────────────────────────────────────────────────────── #

FONTS = {
    "heading": "Arial Black",
    "body":    "Arial",
}

# ── Slide dimensions (13.333" x 7.5") ────────────────────────────────────── #

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

# ── Logo ──────────────────────────────────────────────────────────────────── #

# Canonical logo path in the snowflake-pptx plugin (sibling plugin).
_PPTX_PLUGIN = pathlib.Path(__file__).resolve().parent.parent.parent.parent / "snowflake-pptx"
_LOGO_CANDIDATE = _PPTX_PLUGIN / "assets" / "icons" / "graphic_snowflake_logo_blue.png"

# Fallback: any PNG in sizing plugin assets.
_SIZING_PLUGIN = pathlib.Path(__file__).resolve().parent.parent.parent
_LOGO_FALLBACK = _SIZING_PLUGIN / "assets" / "icons" / "graphic_snowflake_logo_blue.png"

def logo_path() -> pathlib.Path | None:
    """Return path to the Snowflake logo PNG, or None if not found."""
    for candidate in (_LOGO_CANDIDATE, _LOGO_FALLBACK):
        if candidate.is_file():
            return candidate
    return None

# Logo geometry (279x62 px → aspect 4.496:1).
LOGO_W  = Inches(1.5)
LOGO_H  = Inches(1.5 * 62 / 279)   # ~0.334"
LOGO_X  = SLIDE_W - LOGO_W - Inches(0.23)   # right-aligned with margin
LOGO_Y  = Inches(0.25)

# ── Bottom accent bar ─────────────────────────────────────────────────────── #

BAR_H = Inches(0.325)
BAR_Y = SLIDE_H - BAR_H - Inches(0.325)   # ~6.85"
BAR_X = Inches(0.0)
BAR_W = SLIDE_W

# ── Typography helpers ────────────────────────────────────────────────────── #

# Font sizes as Pt objects for common roles.
SIZE_TITLE      = Pt(32)
SIZE_SUBTITLE   = Pt(18)
SIZE_HEADING    = Pt(14)
SIZE_BODY       = Pt(11)
SIZE_SMALL      = Pt(9)
SIZE_STAT_LABEL = Pt(10)
SIZE_STAT_VALUE = Pt(28)

# Standard content area (leaves room for logo bar and accent bar).
CONTENT_L = Inches(0.5)
CONTENT_T = Inches(1.1)
CONTENT_W = SLIDE_W - Inches(1.0)
CONTENT_H = SLIDE_H - Inches(1.8)
