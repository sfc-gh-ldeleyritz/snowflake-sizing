"""inject.py - Content injection into cloned designer slides.

Python port of the relevant ``ContentInjector.cs`` paths.  Operates directly on
the DrawingML XML (lxml) so that the donor slide's baked-in formatting
(run rPr, cell fills, table styling) is preserved - python-pptx's high-level
``cell.text = ...`` / ``run.text`` setters would discard run properties.

Injection targets shapes by placeholder ROLE + POSITION (not by sample text), so
the renderer stays correct after scripts/create-sizing-template.py re-bakes the
donor wording.  The donor slides come from a Google-Slides export where
placeholder idx values are NOT unique (the cover carries three idx=0 TITLE
placeholders), hence role + geometry rather than idx.

Public surface:
  find_title_placeholder / find_subtitle_placeholder(slide) -> shape | None
      Title  = topmost TITLE-type placeholder (else topmost text shape).
      Subtitle = the SUBTITLE-type placeholder (else a header-band shape below
      the title).

  body_placeholders(slide) -> list[shape]
      Text shapes in the content band (below the header, above the footer),
      left-to-right - the one/two-column donor bodies.

  number_shapes / caption_shapes(slide) -> list[shape]
      The four-column donor's big-number AUTO_SHAPEs and the tall caption boxes
      beneath them, each left-to-right.

  find_largest_body(slide) -> shape | None
      Largest-area non-title text shape (the agenda donor's body sits in the
      header band beside a narrow title, so it needs area, not position).

  set_title / set_subtitle(slide, text) -> bool
  set_shape_text(shape, text) -> None
      Set a shape's first run, blanking the rest, preserving run formatting.
  set_paragraph_texts(shape, lines) -> None
      Set each paragraph to a line (the cover's two-tone two-line title).

  set_body_paragraphs(shape, lines, font_size=None) -> None
      Replace a text placeholder's paragraphs with *lines*, cloning the donor's
      first run/paragraph so font, colour and bullet formatting carry over.

  add_footer(slide, text) -> shape
      Add a small gray Confidential-style footer textbox at the bottom-left.

  fill_table(slide, headers, rows, col_ratios=None, ...) -> table element
      Find the slide's a:tbl, grow/shrink its grid to match the data, fill cells
      in place (preserving cell styling), scale row height + fonts to fit, and
      redistribute column widths (mirrors HandleTableData + SetTableRowCells +
      RemoveEmptyTableColumns, extended with row/column GROWTH).
"""
from __future__ import annotations

import copy

from lxml import etree
from pptx.dml.color import RGBColor
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

# Donor styled-table geometry (slide18.xml / table_styled).
_DONOR_ROW_H = 476640          # EMU per row in the donor table (~0.52")
_MAX_TABLE_CY = 3_300_000      # max table height; keeps tall tables clear of the
                               # ~5.0" Confidential footer (table top ~1.1") so a
                               # 7+ row table never collides with bottom chrome
_MIN_FONT_SZ = 700             # 7pt floor when scaling cell fonts down

_AP = qn("a:p")
_AR = qn("a:r")
_AT = qn("a:t")
_ATC = qn("a:tc")
_ATR = qn("a:tr")
_RPR = qn("a:rPr")
_END_RPR = qn("a:endParaRPr")
_DEF_RPR = qn("a:defRPr")
_TCPR = qn("a:tcPr")
_SOLIDFILL = qn("a:solidFill")
_SRGBCLR = qn("a:srgbClr")


# ── Placeholder / position targeting ───────────────────────────────────────── #

# Vertical bands (EMU) on the 10.0" x 5.625" slide used to classify shapes by
# role.  Header (title + subtitle) sits above _HEADER_BAND_MAX; the content body
# between header and footer; the slide-number + Confidential footer below
# _FOOTER_BAND_MIN.  The four-column donor's numbers/captions share a top band but
# differ in height (numbers are short, captions tall).
_HEADER_BAND_MAX = 1_050_000   # title + subtitle live above this
_FOOTER_BAND_MIN = 4_500_000   # slide number + footer live below this
_NUM_BAND_MAX = 1_500_000      # four-column number/caption top band
_NUM_MAX_H = 900_000           # big-number shapes are short
_CAPTION_MIN_H = 1_400_000     # caption boxes are tall


def _ph_format(shape):
    """Return shape.placeholder_format when shape is a typed placeholder, else None."""
    try:
        pf = shape.placeholder_format
    except (ValueError, AttributeError):
        return None
    if pf is not None and pf.type is not None:
        return pf
    return None


def _ph_type(shape):
    pf = _ph_format(shape)
    return pf.type if pf is not None else None


def _is_placeholder(shape) -> bool:
    return _ph_format(shape) is not None


def _is_slide_number(shape) -> bool:
    return _ph_type(shape) == PP_PLACEHOLDER.SLIDE_NUMBER


def _text_shapes(slide, *, drop_slide_number: bool = True) -> list:
    """All shapes with a text frame, optionally excluding the slide-number placeholder."""
    out = []
    for sh in slide.shapes:
        if not sh.has_text_frame:
            continue
        if drop_slide_number and _is_slide_number(sh):
            continue
        out.append(sh)
    return out


def text_shapes_by_position(slide) -> list:
    """Text shapes (excluding slide numbers) sorted top-to-bottom, left-to-right."""
    return sorted(_text_shapes(slide), key=lambda s: ((s.top or 0), (s.left or 0)))


def find_title_placeholder(slide):
    """Return the title shape: topmost TITLE-type placeholder, else topmost text shape."""
    cands = _text_shapes(slide)
    if not cands:
        return None
    titles = [s for s in cands
              if _ph_type(s) in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE)]
    pool = titles or cands
    return min(pool, key=lambda s: ((s.top or 0), (s.left or 0)))


def find_subtitle_placeholder(slide):
    """Return the subtitle: the SUBTITLE-type placeholder, else a header-band shape below the title."""
    for sh in _text_shapes(slide):
        if _ph_type(sh) == PP_PLACEHOLDER.SUBTITLE:
            return sh
    title = find_title_placeholder(slide)
    ttop = (title.top or 0) if title is not None else -1
    band = [s for s in _text_shapes(slide)
            if s is not title and ttop < (s.top or 0) < _HEADER_BAND_MAX]
    return min(band, key=lambda s: s.top or 0) if band else None


def body_placeholders(slide) -> list:
    """Text shapes in the content band (below header, above footer), left-to-right.

    Serves the one-column (content) and two-column donors.  Excludes the title,
    subtitle, slide number, and any bottom Confidential footer.  NOT for the
    four-column donor - see number_shapes / caption_shapes."""
    title = find_title_placeholder(slide)
    subtitle = find_subtitle_placeholder(slide)
    out = []
    for sh in _text_shapes(slide):
        if sh is title or sh is subtitle:
            continue
        top = sh.top or 0
        if _HEADER_BAND_MAX <= top < _FOOTER_BAND_MIN:
            out.append(sh)
    return sorted(out, key=lambda s: ((s.top or 0), (s.left or 0)))


def find_largest_body(slide):
    """Return the largest-area non-title text shape (excludes the slide number).

    Used for the agenda donor, whose body sits in the header band beside a narrow
    title, so position-band selection (body_placeholders) would miss it."""
    title = find_title_placeholder(slide)
    best, best_area = None, -1
    for sh in _text_shapes(slide):
        if sh is title:
            continue
        area = (sh.width or 0) * (sh.height or 0)
        if area > best_area:
            best, best_area = sh, area
    return best


def number_shapes(slide) -> list:
    """The four-column donor's big-number AUTO_SHAPEs (short, non-placeholder), left-to-right."""
    out = []
    for sh in slide.shapes:
        if not sh.has_text_frame or _is_placeholder(sh):
            continue
        top = sh.top or 0
        if _HEADER_BAND_MAX < top < _NUM_BAND_MAX and (sh.height or 0) < _NUM_MAX_H:
            out.append(sh)
    return sorted(out, key=lambda s: s.left or 0)


def caption_shapes(slide) -> list:
    """The four-column donor's tall caption boxes under the numbers, left-to-right."""
    out = []
    for sh in _text_shapes(slide):
        top = sh.top or 0
        if top < _NUM_BAND_MAX and (sh.height or 0) > _CAPTION_MIN_H:
            out.append(sh)
    return sorted(out, key=lambda s: s.left or 0)


def remove_shapes(slide, predicate) -> int:
    """Remove every top-level shape for which predicate(shape) is truthy.

    Returns the number of shapes removed.  Used to strip donor decorations that
    don't belong in the injected slide (e.g. the title donor's sample presenter
    headshot + name block)."""
    removed = 0
    for shape in list(slide.shapes):
        if predicate(shape):
            shape._element.getparent().remove(shape._element)
            removed += 1
    return removed


# ── Title / subtitle / single-shape text ───────────────────────────────────── #

def _set_para_first_run(ap, text: str) -> None:
    """Set paragraph *ap*'s first run to *text*, blanking its other runs.

    Preserves the first run's rPr; appends a bare run if the paragraph has none."""
    runs = ap.findall(_AR)
    if runs:
        t = runs[0].find(_AT)
        if t is None:
            t = etree.SubElement(runs[0], _AT)
        t.text = text
        for extra in runs[1:]:
            ap.remove(extra)
    else:
        _append_run(ap, text)


def set_shape_text(shape, text: str) -> None:
    """Set *shape*'s first run to *text* (preserving formatting), blanking all other runs.

    The first paragraph holding a run is the target; every other paragraph's runs
    are blanked so stale donor sample text on a second line clears."""
    txBody = shape.text_frame._txBody
    paras = txBody.findall(_AP)
    if not paras:
        return
    target = next((p for p in paras if p.find(_AR) is not None), paras[0])
    _set_para_first_run(target, text)
    for p in paras:
        if p is target:
            continue
        for r in p.findall(_AR):
            tt = r.find(_AT)
            if tt is not None:
                tt.text = ""


def set_paragraph_texts(shape, lines: list[str]) -> None:
    """Set each paragraph of *shape* to the matching line, preserving per-paragraph runs.

    Used for the cover's two-tone two-line title (line 0 customer, line 1
    proposal).  Extra existing paragraphs are blanked; extra lines clone the last
    paragraph so their styling carries over."""
    txBody = shape.text_frame._txBody
    paras = txBody.findall(_AP)
    if not paras:
        return
    for i, line in enumerate(lines):
        if i < len(paras):
            _set_para_first_run(paras[i], line)
        else:
            np = copy.deepcopy(paras[-1])
            _set_para_first_run(np, line)
            txBody.append(np)
    for p in paras[len(lines):]:
        _set_para_first_run(p, "")


def set_title(slide, text: str) -> bool:
    """Set the slide's title shape to *text*.  Returns False if no title found."""
    ph = find_title_placeholder(slide)
    if ph is None:
        return False
    set_shape_text(ph, text)
    return True


def set_subtitle(slide, text: str) -> bool:
    """Set the slide's subtitle shape to *text*.  Returns False if no subtitle found."""
    ph = find_subtitle_placeholder(slide)
    if ph is None:
        return False
    set_shape_text(ph, text)
    return True


def add_footer(slide, text: str, *, color: RGBColor | None = None):
    """Add a small gray Confidential-style footer textbox at the bottom-left.

    Positioned in the footer band (top > _FOOTER_BAND_MIN) so the targeting
    helpers above never mistake it for a body/subtitle shape."""
    box = slide.shapes.add_textbox(Inches(0.4), Inches(5.0), Inches(3.0), Inches(0.3))
    tf = box.text_frame
    tf.word_wrap = False
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = text
    run.font.size = Pt(8)
    run.font.name = "Arial"
    run.font.color.rgb = color if color is not None else RGBColor(0x8C, 0x8C, 0x8C)
    return box


def set_speaker_notes(slide, text: str) -> None:
    """Set *slide*'s speaker-notes text, one paragraph per newline-delimited line.

    Creates the notes slide if the slide doesn't have one yet.  Used to move
    long-form context (assumptions, open items, next steps) off the visible
    slide and into the presenter notes pane."""
    tf = slide.notes_slide.notes_text_frame
    lines = text.split("\n") or [""]
    tf.text = lines[0]
    for line in lines[1:]:
        tf.add_paragraph().text = line


# ── Body paragraph injection ───────────────────────────────────────────────── #

def set_body_paragraphs(shape, lines: list[str], font_size=None, tight: bool = False) -> None:
    """Replace *shape*'s paragraphs with *lines*, cloning donor run formatting.

    The first paragraph containing a run is used as the prototype so that font,
    colour and bullet settings are preserved.  *font_size* (a pptx Pt/Emu length
    or int centipoints) optionally overrides the run size.  *tight* compresses
    inter-paragraph spacing so long lists clear the slide footer.
    """
    txBody = shape.text_frame._txBody
    paras = txBody.findall(_AP)
    if not paras:
        return

    proto = next((p for p in paras if p.find(_AR) is not None), paras[0])

    sz_val = None
    if font_size is not None:
        sz_val = int(font_size) if isinstance(font_size, int) else int(font_size.pt * 100)

    new_paras = []
    for line in lines:
        np = copy.deepcopy(proto)
        runs = np.findall(_AR)
        if runs:
            first = runs[0]
            t = first.find(_AT)
            if t is None:
                t = etree.SubElement(first, _AT)
            t.text = line
            for extra in runs[1:]:
                np.remove(extra)
            if sz_val is not None:
                rpr = first.find(_RPR)
                if rpr is not None:
                    rpr.set("sz", str(sz_val))
        else:
            _append_run(np, line, sz_val)
        new_paras.append(np)

    for p in paras:
        txBody.remove(p)
    for np in new_paras:
        txBody.append(np)

    if tight:
        # Use the python-pptx paragraph API so spacing XML is inserted in the
        # schema-correct order (lnSpc, spcBef, spcAft).
        for p in shape.text_frame.paragraphs:
            p.line_spacing = 1.0
            p.space_before = Pt(3)
            p.space_after = Pt(3)


def _append_run(ap, text: str, sz_val=None) -> None:
    """Append a minimal a:r (with optional size) to paragraph *ap*."""
    r = etree.SubElement(ap, _AR)
    if sz_val is not None:
        rpr = etree.SubElement(r, _RPR)
        rpr.set("sz", str(sz_val))
    t = etree.SubElement(r, _AT)
    t.text = text


def replace_caption(shape, text: str) -> None:
    """Set the text of *shape*'s LAST paragraph, preserving leading paragraphs.

    The four-column-numbers donor captions use empty spacer paragraphs to push
    the caption below the big number; this edits only the caption run so those
    spacers (and thus the vertical offset) are kept intact."""
    txBody = shape.text_frame._txBody
    paras = txBody.findall(_AP)
    if not paras:
        return
    target = paras[-1]
    runs = target.findall(_AR)
    if runs:
        t = runs[0].find(_AT)
        if t is None:
            t = etree.SubElement(runs[0], _AT)
        t.text = text
        for extra in runs[1:]:
            target.remove(extra)
    else:
        _append_run(target, text)


def set_runs_font_size(shape, sz_centipoints: int, *, word_wrap: bool | None = None) -> None:
    """Force every run size in *shape* to *sz_centipoints* (e.g. 2800 = 28pt).

    Used to shrink the donor's 36pt big-number text so longer values like
    '$12.6M' fit on one line."""
    if word_wrap is not None:
        shape.text_frame.word_wrap = word_wrap
    for rpr in shape.text_frame._txBody.iter(_RPR, _END_RPR):
        rpr.set("sz", str(sz_centipoints))


# ── Table injection ────────────────────────────────────────────────────────── #

def _find_tbl(slide):
    for el in slide.shapes._spTree.iter(qn("a:tbl")):
        return el
    return None


def _graphic_frame_of(tbl):
    el = tbl.getparent()
    gf_tag = qn("p:graphicFrame")
    while el is not None and el.tag != gf_tag:
        el = el.getparent()
    return el


def _set_cell_text(tc, text: str, sibling_cells=None) -> None:
    """Set *tc*'s text, preserving run formatting (first a:t gets text, rest blank).

    Empty cells (no run) clone a run from a sibling cell so injected text inherits
    the row's styling (used for the donor's empty header corner cell)."""
    t_elems = tc.findall(".//" + _AT)
    if t_elems:
        t_elems[0].text = text
        for extra in t_elems[1:]:
            extra.text = ""
        return

    # Empty cell: clone a prototype run from a sibling, else build a bare run.
    proto_r = None
    if sibling_cells:
        for sib in sibling_cells:
            if sib is tc:
                continue
            r = sib.find(".//" + _AR)
            if r is not None:
                proto_r = r
                break
    ap = tc.find(".//" + _AP)
    if ap is None:
        return
    if proto_r is not None:
        nr = copy.deepcopy(proto_r)
        t = nr.find(_AT)
        if t is None:
            t = etree.SubElement(nr, _AT)
        t.text = text
        end = ap.find(_END_RPR)
        if end is not None:
            end.addprevious(nr)
        else:
            ap.append(nr)
    else:
        _append_run(ap, text)


def _set_row_cells(tr, values) -> None:
    cells = tr.findall(_ATC)
    for i, tc in enumerate(cells):
        _set_cell_text(tc, values[i] if i < len(values) else "", sibling_cells=cells)


def _bold_row(tr) -> None:
    """Set bold on every run (and end-paragraph mark) in table row *tr*.

    Used to emphasize a table's Total row.  Inserts an a:rPr before a:t when a
    run has none, so bare cloned runs still bold."""
    for tc in tr.findall(_ATC):
        for ap in tc.iter(_AP):
            for r in ap.findall(_AR):
                rpr = r.find(_RPR)
                if rpr is None:
                    rpr = r.makeelement(_RPR, {})
                    r.insert(0, rpr)
                rpr.set("b", "1")
            end = ap.find(_END_RPR)
            if end is not None:
                end.set("b", "1")


def _set_cell_fill(tc, hex_rgb: str) -> None:
    """Override table cell *tc*'s fill to solid *hex_rgb* (e.g. "FFFFFF").

    Mutates the donor cell's existing a:solidFill in place (schema-order-safe -
    the fill group sits after the a:ln* borders); falls back to appending one
    (after any borders) when absent.  Used to de-blue the styled donor's data
    rows to white while leaving the header's fill and the cells' light-gray
    bottom borders (the row gridlines) untouched."""
    tcPr = tc.find(_TCPR)
    if tcPr is None:
        tcPr = etree.SubElement(tc, _TCPR)
    sf = tcPr.find(_SOLIDFILL)
    if sf is None:
        for tag in ("a:noFill", "a:gradFill", "a:blipFill", "a:pattFill", "a:grpFill"):
            for el in tcPr.findall(qn(tag)):
                tcPr.remove(el)
        sf = etree.SubElement(tcPr, _SOLIDFILL)
    for child in list(sf):
        sf.remove(child)
    etree.SubElement(sf, _SRGBCLR).set("val", hex_rgb)


def _set_column_count(tbl, target: int) -> None:
    grid = tbl.find(qn("a:tblGrid"))
    cols = grid.findall(qn("a:gridCol"))
    cur = len(cols)
    if target == cur or target < 1:
        return
    trs = tbl.findall(_ATR)
    if target < cur:
        for i in range(cur - 1, target - 1, -1):
            grid.remove(cols[i])
            for tr in trs:
                tcs = tr.findall(_ATC)
                if i < len(tcs):
                    tr.remove(tcs[i])
    else:
        for _ in range(target - cur):
            last_col = grid.findall(qn("a:gridCol"))[-1]
            last_col.addnext(copy.deepcopy(last_col))
            for tr in trs:
                tcs = tr.findall(_ATC)
                last_tc = tcs[-1]
                last_tc.addnext(copy.deepcopy(last_tc))


def _set_row_count(tbl, target: int) -> None:
    trs = tbl.findall(_ATR)
    cur = len(trs)
    if target == cur or target < 1:
        return
    if target < cur:
        for i in range(cur - 1, target - 1, -1):
            trs[i].getparent().remove(trs[i])
    else:
        proto = trs[1] if cur > 1 else trs[-1]   # a data row (preserve data styling)
        last = trs[-1]
        for _ in range(target - cur):
            nr = copy.deepcopy(proto)
            last.addnext(nr)
            last = nr


def _scale_fonts(scope, scale: float) -> None:
    """Multiply every explicit font size under *scope* by *scale* (with a floor)."""
    for el in scope.iter():
        if el.tag in (_RPR, _END_RPR, _DEF_RPR):
            sz = el.get("sz")
            if sz:
                el.set("sz", str(max(_MIN_FONT_SZ, int(int(sz) * scale))))


def _distribute_widths(tbl, col_ratios, total_width: int | None = None) -> None:
    grid = tbl.find(qn("a:tblGrid"))
    cols = grid.findall(qn("a:gridCol"))
    n = len(cols)
    if n == 0:
        return
    # Distribute over the table's intended display width (the graphic-frame
    # width), NOT the sum of current gridCol widths - growing/shrinking columns
    # changes that sum and would otherwise inflate/shrink the whole table.
    total = total_width if total_width and total_width > 0 else sum(int(c.get("w") or 0) for c in cols)
    if total <= 0:
        total = 8_228_880
    if col_ratios and len(col_ratios) == n:
        ratios = list(col_ratios)
    elif n > 1:
        ratios = [0.30] + [0.70 / (n - 1)] * (n - 1)   # styled default: emphasized col0
    else:
        ratios = [1.0]
    rsum = sum(ratios) or 1.0
    acc = 0
    for i, c in enumerate(cols):
        w = int(total * ratios[i] / rsum) if i < n - 1 else (total - acc)
        acc += w
        c.set("w", str(w))
        ext = c.find(qn("a:extLst"))   # drop stale cached widths
        if ext is not None:
            c.remove(ext)


def fill_table(
    slide,
    headers: list[str] | None,
    rows: list[list[str]],
    *,
    col_ratios=None,
    max_table_cy: int = _MAX_TABLE_CY,
    top_emu: int | None = None,
    bold_last_row: bool = False,
    data_row_fill: str | None = None,
):
    """Fill the slide's styled a:tbl with *headers* + *rows*, growing/shrinking it.

    Args:
        headers:    header row values, or None to skip the header row.
        rows:       list of data rows (each a list of cell strings).
        col_ratios: optional per-column width ratios (len must equal column count);
                    defaults to the styled 30%/70% split with an emphasized col 0.
        max_table_cy: vertical EMU budget; row height + fonts scale to fit.
        top_emu:    optional new table top (a:off y) - lets callers drop the table
                    below an injected subtitle.
        bold_last_row: bold every run in the final row (emphasizes a Total row).
        data_row_fill: optional hex RGB (e.g. "FFFFFF") applied as the fill of
                    every data row (all rows after the header), leaving the
                    header's donor fill intact - de-blues the styled donor's
                    all-blue rows to white while keeping the gridline borders.

    Returns the a:tbl element (or None when the slide has no table).
    """
    tbl = _find_tbl(slide)
    if tbl is None:
        return None

    target_cols = (
        len(headers) if headers
        else (len(rows[0]) if rows else len(tbl.find(qn("a:tblGrid")).findall(qn("a:gridCol"))))
    )
    _set_column_count(tbl, target_cols)

    target_rows = (1 if headers else 0) + len(rows)
    _set_row_count(tbl, max(target_rows, 1))

    trs = tbl.findall(_ATR)
    ri = 0
    if headers:
        _set_row_cells(trs[0], headers)
        ri = 1
    for i, row_vals in enumerate(rows):
        if ri + i < len(trs):
            _set_row_cells(trs[ri + i], row_vals)

    if bold_last_row and trs:
        _bold_row(trs[-1])

    if data_row_fill and trs:
        for tr in trs[(1 if headers else 0):]:
            for tc in tr.findall(_ATC):
                _set_cell_fill(tc, data_row_fill)

    # Row height + font scaling to fit the vertical budget.
    nrows = len(trs)
    row_h = min(_DONOR_ROW_H, max_table_cy // max(nrows, 1))
    scale = row_h / _DONOR_ROW_H
    for tr in trs:
        tr.set("h", str(int(row_h)))
        if scale < 1.0:
            _scale_fonts(tr, scale)

    # Resize / reposition the containing graphic frame.
    frame_cx = None
    gf = _graphic_frame_of(tbl)
    if gf is not None:
        xfrm = gf.find(qn("p:xfrm"))
        if xfrm is not None:
            ext = xfrm.find(qn("a:ext"))
            if ext is not None:
                frame_cx = int(ext.get("cx") or 0) or None
                ext.set("cy", str(int(row_h) * nrows))
            if top_emu is not None:
                off = xfrm.find(qn("a:off"))
                if off is not None:
                    off.set("y", str(int(top_emu)))

    # Distribute columns across the frame's display width (so grown/shrunk
    # tables still fill - and never exceed - the original frame footprint).
    _distribute_widths(tbl, col_ratios, total_width=frame_cx)
    return tbl
