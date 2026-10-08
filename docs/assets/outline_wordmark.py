"""Outline the "derailment" wordmark into one SVG path for make_logo.py.

Usage (dev-only dependencies, not part of the package):
    uvx --with fonttools --with uharfbuzz python docs/assets/outline_wordmark.py \
        Overpass[wght].ttf derailment 48 -0.02

Download the font from https://github.com/google/fonts/tree/main/ofl/overpass
(SIL Open Font License 1.1). The script pins the variable font to wght 700,
shapes the text with HarfBuzz (so kerning is applied), adds the tracking in
em, and prints JSON with the path (baseline at y=0, y pointing down) and the
total advance. Paste ``path`` and ``advance`` into make_logo.py.
"""

from __future__ import annotations

import io
import json
import sys

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont


def shape(font_bytes: bytes, text: str) -> hb.Buffer:
    """Shape ``text`` with kerning and ligatures enabled."""
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    hb.shape(hb.Font(hb.Face(hb.Blob(font_bytes))), buffer, {"kern": True, "liga": True})
    return buffer


def outline(font_path: str, text: str, size: float, tracking_em: float) -> dict:
    """Return the outlined path and the advance width at ``size`` units."""
    font = instantiateVariableFont(TTFont(font_path), {"wght": 700})
    data = io.BytesIO()
    font.save(data)
    scale = size / font["head"].unitsPerEm
    tracking = tracking_em * font["head"].unitsPerEm
    glyph_order, glyph_set = font.getGlyphOrder(), font.getGlyphSet()
    pen = SVGPathPen(glyph_set, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
    x = 0.0
    shaped = shape(data.getvalue(), text)
    for info, pos in zip(shaped.glyph_infos, shaped.glyph_positions, strict=True):
        # font units point up from the baseline; SVG points down, baseline at y=0
        transform = (scale, 0, 0, -scale, (x + pos.x_offset) * scale, -pos.y_offset * scale)
        glyph_set[glyph_order[info.codepoint]].draw(TransformPen(pen, transform))
        x += pos.x_advance + tracking
    return {"path": pen.getCommands(), "advance": round((x - tracking) * scale, 2)}


if __name__ == "__main__":
    font_arg, text_arg, size_arg, tracking_arg = sys.argv[1:5]
    print(json.dumps(outline(font_arg, text_arg, float(size_arg), float(tracking_arg))))
