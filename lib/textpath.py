"""Convert display text to SVG path outlines.

GitHub proxies README SVGs through camo, so webfonts never load. Any <text>
element with a custom font-family silently falls back to whatever the visitor
happens to have installed, breaking every hand-tuned metric. Display text is
therefore converted to geometry at generation time.

Monospace runs are NOT converted — they use <text> with explicit per-glyph x,
which makes them metrics-independent at a fraction of the byte cost.
"""
import os

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

FONTS = {
    "display": "fonts/SourceSerif4-Semibold.ttf",
    "mono": "fonts/JetBrainsMono-Regular.ttf",
}

_cache = {}


def _load(font_file: str) -> TTFont:
    if font_file not in _cache:
        if not os.path.exists(font_file):
            raise FileNotFoundError(
                f"bundled font missing: {font_file} — run the fonts/ download step"
            )
        _cache[font_file] = TTFont(font_file)
    return _cache[font_file]


def advance_width(s: str, font_file: str, size: float) -> float:
    """Total advance of `s` at `size`, in screen px."""
    font = _load(font_file)
    upem = font["head"].unitsPerEm
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    total = 0.0
    for ch in s:
        name = cmap.get(ord(ch))
        total += hmtx[name][0] if name else upem * 0.5
    return total * (size / upem)


def text_to_path(s: str, font_file: str, size: float, x: float, y: float) -> str:
    """Return an SVG path `d` string for `s`, baseline-positioned at (x, y).

    The y axis is flipped during transform because font units run upward while
    SVG user units run downward.
    """
    font = _load(font_file)
    upem = font["head"].unitsPerEm
    scale = size / upem
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]

    commands = []
    pen_x = 0.0
    for ch in s:
        name = cmap.get(ord(ch))
        if name is None:
            pen_x += upem * 0.5
            continue
        svg_pen = SVGPathPen(glyph_set)
        transform = (scale, 0, 0, -scale, x + pen_x * scale, y)
        glyph_set[name].draw(TransformPen(svg_pen, transform))
        d = svg_pen.getCommands()
        if d:
            commands.append(d)
        pen_x += hmtx[name][0]

    return "".join(commands)
