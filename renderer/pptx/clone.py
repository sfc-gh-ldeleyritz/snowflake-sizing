"""clone.py - Slide cloning / duplication for the sizing PPTX generator.

Python port of the snowflake-pptx ``SlideCloner.cs`` deep-clone logic.  Three
public entry points:

  clone_slide_crossfile(src_prs, src_idx, dst_prs) -> Slide
      Deep-clone the slide at *src_idx* (SlideIdList ordering) from a *different*
      Presentation (the Jan 2026 master template) into *dst_prs*.  Copies image
      blobs into the destination package and re-points the slide layout by NAME
      against dst's existing layouts.  Used once, at template-bake time
      (scripts/create-sizing-template.py).

  duplicate_slide_inpackage(prs, donor_slide) -> Slide
      Deep-copy a donor slide that already lives in *prs* into a new slide in the
      same package, re-using the existing image/layout parts.  Used per render
      (renderer/pptx/slides.py).

  delete_slides(prs, predicate) -> int
      Remove every slide for which predicate(slide) is truthy, dropping both the
      OPC relationship and the sldId entry.  Masters/layouts/themes are kept.

Helpers: find_layout_by_name, donors_by_order (bake-order donor lookup).

Why clone instead of add_slide(layout)?  The designed Snowflake slides carry
their on-brand content baked into the slide XML itself (styled a:tbl tables with
no tableStyleId, big-number auto-shapes, etc.).  add_slide only inherits empty
layout placeholders, so the only way to reuse the real design is to copy the
slide's own shape tree verbatim and fix up its relationships.
"""
from __future__ import annotations

import copy
import io
from typing import Callable

from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.oxml.ns import qn

# spTree children that belong to the group itself (NOT shapes); never copied or
# removed during a clone.
_GROUP_OWN = {qn("p:nvGrpSpPr"), qn("p:grpSpPr")}

_R_EMBED = qn("r:embed")
_R_LINK = qn("r:link")


# ── Layout / donor lookup ──────────────────────────────────────────────────── #

def find_layout_by_name(prs, name: str):
    """Return the first slide layout matching *name* across all masters, else None."""
    for master in prs.slide_masters:
        for layout in master.slide_layouts:
            if layout.name == name:
                return layout
    return None


# Canonical bake order of the donor slides in sizing-base-template.pptx.  Both
# scripts/create-sizing-template.py (writer) and build_pptx.py (reader) import
# this list, so slide i in the base template is donor BAKED_DONOR_ORDER[i].  This
# index-based lookup replaced the old text-signature match, which keyed off donor
# sample wording that the bake now overwrites with real sizing scaffolding.
BAKED_DONOR_ORDER: list[str] = [
    "title",
    "agenda",
    "safe_harbor",
    "table_styled",
    "content",
    "thank_you",
    "understanding_costs",
]


def donors_by_order(prs) -> dict:
    """Map each donor kind to its slide in *prs* by BAKED_DONOR_ORDER index.

    Robust to the donor text re-baking (unlike a signature match), since position
    in the committed base template - not wording - identifies each donor."""
    slides = list(prs.slides)
    if len(slides) < len(BAKED_DONOR_ORDER):
        raise LookupError(
            f"Base template has {len(slides)} slides but {len(BAKED_DONOR_ORDER)} "
            "donors are expected. Re-run scripts/create-sizing-template.py."
        )
    return {kind: slides[i] for i, kind in enumerate(BAKED_DONOR_ORDER)}


# ── Shape-tree + image copying ─────────────────────────────────────────────── #

def _copy_shapes(src_slide, new_slide) -> None:
    """Replace *new_slide*'s shape tree with a deep copy of *src_slide*'s.

    Removes the placeholder shapes add_slide() cloned from the layout, then
    appends deep copies of every donor shape (everything except the group's own
    nvGrpSpPr / grpSpPr).
    """
    dst_tree = new_slide.shapes._spTree
    for child in list(dst_tree):
        if child.tag not in _GROUP_OWN:
            dst_tree.remove(child)
    for child in list(src_slide.shapes._spTree):
        if child.tag in _GROUP_OWN:
            continue
        dst_tree.append(copy.deepcopy(child))


def _remap_embedded_rids(new_slide, rid_map: dict[str, str]) -> None:
    """Rewrite r:embed / r:link attributes in the copied shape tree per *rid_map*."""
    if not rid_map:
        return
    for el in new_slide.shapes._spTree.iter():
        for attr in (_R_EMBED, _R_LINK):
            v = el.get(attr)
            if v is not None and v in rid_map:
                el.set(attr, rid_map[v])


def _copy_images_crossfile(src_slide, new_slide) -> None:
    """Copy image blobs from a foreign-package donor into *new_slide*'s package."""
    rid_map: dict[str, str] = {}
    for rId, rel in src_slide.part.rels.items():
        if rel.is_external or rel.reltype != RT.IMAGE:
            continue
        blob = rel.target_part.blob
        _img_part, new_rId = new_slide.part.get_or_add_image_part(io.BytesIO(blob))
        if new_rId != rId:
            rid_map[rId] = new_rId
    _remap_embedded_rids(new_slide, rid_map)


def _copy_images_inpackage(src_slide, new_slide) -> None:
    """Relate *new_slide* to the same image parts the donor already references."""
    rid_map: dict[str, str] = {}
    for rId, rel in src_slide.part.rels.items():
        if rel.is_external or rel.reltype != RT.IMAGE:
            continue
        new_rId = new_slide.part.relate_to(rel.target_part, RT.IMAGE)
        if new_rId != rId:
            rid_map[rId] = new_rId
    _remap_embedded_rids(new_slide, rid_map)


# ── Public clone API ───────────────────────────────────────────────────────── #

def clone_slide_crossfile(src_prs, src_idx: int, dst_prs):
    """Deep-clone slide *src_idx* (SlideIdList order) from *src_prs* into *dst_prs*.

    The destination must already contain a slide layout with the same NAME as the
    source slide's layout (true for the sizing base, which is built from the same
    master template).  Returns the new Slide in *dst_prs*.
    """
    src_slides = list(src_prs.slides)
    if not 0 <= src_idx < len(src_slides):
        raise IndexError(
            f"src_idx {src_idx} out of range [0, {len(src_slides)})"
        )
    src_slide = src_slides[src_idx]

    layout_name = src_slide.slide_layout.name
    dst_layout = find_layout_by_name(dst_prs, layout_name)
    if dst_layout is None:
        raise ValueError(
            f"Destination has no layout named {layout_name!r} "
            f"(needed to clone source slide index {src_idx})."
        )

    new_slide = dst_prs.slides.add_slide(dst_layout)
    _copy_shapes(src_slide, new_slide)
    _copy_images_crossfile(src_slide, new_slide)
    return new_slide


def duplicate_slide_inpackage(prs, donor_slide):
    """Deep-copy *donor_slide* (already in *prs*) into a new slide in *prs*.

    Re-uses the donor's existing layout and image parts.  Returns the new Slide.
    """
    layout = donor_slide.slide_layout
    new_slide = prs.slides.add_slide(layout)
    _copy_shapes(donor_slide, new_slide)
    _copy_images_inpackage(donor_slide, new_slide)
    return new_slide


def delete_slides(prs, predicate: Callable) -> int:
    """Remove every slide for which predicate(slide) is truthy.

    Drops the OPC relationship (so the slide part is detached) and removes the
    sldId entry.  Masters, layouts, and themes are untouched.  Returns the count
    of slides removed.
    """
    sld_id_lst = prs.slides._sldIdLst
    id_elems = list(sld_id_lst)
    slides = list(prs.slides)  # iterates in sldIdLst order -> aligns with id_elems
    removed = 0
    for sId, slide in zip(id_elems, slides):
        if predicate(slide):
            rId = sId.get(qn("r:id"))
            prs.part.drop_rel(rId)
            sld_id_lst.remove(sId)
            removed += 1
    return removed
