#!/usr/bin/env python3
"""3D isometric activation-surface banner for a GitHub profile README.

A photo becomes a height field: each cell's luminance drives both its extrusion
height and its inferno colour, rendered in 2:1 isometric projection as stacked
quads. This is the same idea as a matplotlib surface plot, executed in SVG so it
animates natively inside a GitHub README with no JS and no GIF.

Usage:
    python generate_banner.py --photo me.jpg
    python generate_banner.py                 # synthetic placeholder
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from lib.inferno import inferno, shade
from lib.relief import column_faces, draw_order
from lib.textpath import FONTS, advance_width, text_to_path

# ---------------------------------------------------------------------------
# Identity — edit to change the right-hand panel
# ---------------------------------------------------------------------------
IDENTITY = {
    "name": "Karthick A. R.",
    "role": "SOFTWARE + AI/ML DEVELOPER",
    "rows": [
        ("stack.lang", "Python · TypeScript · SQL"),
        ("stack.ml", "PyTorch · TensorFlow · scikit-learn"),
        ("stack.nlp", "Transformers · BioBERT · DistilBERT"),
        ("stack.web", "FastAPI · React · PostgreSQL"),
        ("agents", "7 active"),
        ("status", "student · shipping"),
    ],
}

W, H = 1180, 560
COLS, ROWS = 52, 58       # portrait aspect — a face is taller than it is wide
MAX_H = 34.0
MIN_ACTIVATION = 0.05     # below this the cell is background and costs nothing
MIN_FRONT_H = 1.2         # shorter than this, the front face is invisible
BAND_STAGGER = 0.016      # seconds between adjacent rows
RISE_DUR = 0.5
PANEL_X = 620.0

THEMES = {
    "dark": {
        "page": "#0B0A09", "surface": "#16130F", "border": "#2A241E",
        "text": "#F5EFE7", "muted": "#9C9186", "accent": "#F98E08",
        "grid": "#1E1A16",
    },
    "light": {
        "page": "#FAF7F2", "surface": "#FFFFFF", "border": "#E6DFD4",
        "text": "#16130F", "muted": "#6E655C", "accent": "#C2410C",
        "grid": "#EFE9DF",
    },
}


# ---------------------------------------------------------------------------
# Portrait
# ---------------------------------------------------------------------------
def synthetic_portrait(w: int = 360, h: int = 420) -> Image.Image:
    """Placeholder head-and-shoulders bust with a directional key light.

    Used when no photo is supplied so the pipeline is always runnable.
    """
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (xx - w / 2) / (w / 2)
    ny = (yy - h / 2) / (h / 2)

    def ellipse(cx, cy, rx, ry, soft=0.30):
        d = np.sqrt(((nx - cx) / rx) ** 2 + ((ny - cy) / ry) ** 2)
        return np.clip((1.0 - d) / soft + 0.5, 0.0, 1.0)

    cranium = ellipse(0.0, -0.34, 0.40, 0.46, 0.12)
    jaw = ellipse(0.0, -0.12, 0.31, 0.34, 0.16)
    neck = ellipse(0.0, 0.30, 0.13, 0.22, 0.20)
    shoulders = ellipse(0.0, 0.86, 0.86, 0.42, 0.20)

    mask = np.clip(cranium + jaw + neck + shoulders, 0.0, 1.0)

    # Key light from upper-left gives the surface something to sculpt.
    key = np.clip(0.62 - 0.46 * nx + 0.34 * (-ny), 0.05, 1.0)

    brow = ellipse(0.0, -0.30, 0.30, 0.05, 0.5) * 0.20
    nose = ellipse(0.0, -0.08, 0.055, 0.16, 0.4) * 0.28
    cheek_l = ellipse(-0.18, -0.10, 0.13, 0.14, 0.6) * 0.12
    cheek_r = ellipse(0.18, -0.10, 0.13, 0.14, 0.6) * 0.12
    eye_l = ellipse(-0.155, -0.235, 0.075, 0.042, 0.5) * -0.30
    eye_r = ellipse(0.155, -0.235, 0.075, 0.042, 0.5) * -0.30
    mouth = ellipse(0.0, 0.09, 0.11, 0.030, 0.5) * -0.18

    shaded = key + brow + nose + cheek_l + cheek_r + eye_l + eye_r + mouth
    lum = np.clip(shaded, 0.0, 1.0) * mask

    img = Image.fromarray((lum * 255).astype(np.uint8), mode="L")
    return img.filter(ImageFilter.GaussianBlur(1.4))


def height_field(img: Image.Image, cols: int = COLS, rows: int = ROWS) -> list:
    """Photo -> normalised activation grid in [0, 1]."""
    g = ImageOps.grayscale(img)
    g = ImageOps.autocontrast(g, cutoff=2)
    g = g.resize((cols, rows), Image.LANCZOS)

    a = np.asarray(g, dtype=np.float32) / 255.0
    lo, hi = float(a.min()), float(a.max())
    if hi - lo < 1e-6:
        return [[0.0] * cols for _ in range(rows)]
    a = (a - lo) / (hi - lo)
    a = np.power(a, 0.82)     # lift midtones so the face reads as relief
    return a.tolist()


# ---------------------------------------------------------------------------
# SVG
# ---------------------------------------------------------------------------
def _mono_row(text: str, x: float, y: float, size: float, fill: str,
              opacity: float = 1.0) -> str:
    """A monospace run pinned to an exact width.

    textLength + lengthAdjust makes the run metrics-independent, so the generic
    monospace fallback renders at the same width as JetBrains Mono would.
    """
    if not text:
        return ""
    width = advance_width(text, FONTS["mono"], size)
    esc = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    op = "" if opacity >= 1.0 else f' opacity="{opacity}"'
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size:.1f}" fill="{fill}"'
        f' textLength="{width:.1f}" lengthAdjust="spacing"'
        f' font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"'
        f' xml:space="preserve"{op}>{esc}</text>'
    )


def _surface(field: list, theme: str) -> str:
    """The extruded activation surface, grouped into animated row bands."""
    rows, cols = len(field), len(field[0])
    bands: dict = {}

    for c, r in draw_order([(c, r) for r in range(rows) for c in range(cols)]):
        v = field[r][c]
        if v < MIN_ACTIVATION:
            continue
        h = v * MAX_H
        top = inferno(v, theme)
        faces = column_faces(c, r, h)
        quads = []
        # Front first: the roof must paint over the wall of its own cell.
        if h >= MIN_FRONT_H:
            quads.append((faces["front"], shade(top, 0.52)))
        quads.append((faces["top"], top))
        bands.setdefault(r, []).extend(quads)

    parts = []
    for band in sorted(bands):
        begin = band * BAND_STAGGER
        paths = "".join(
            '<path d="M%.1f %.1fL%.1f %.1fL%.1f %.1fL%.1f %.1fZ" fill="%s"/>'
            % (p[0][0], p[0][1], p[1][0], p[1][1],
               p[2][0], p[2][1], p[3][0], p[3][1], colour)
            for p, colour in bands[band]
        )
        # The static attributes hold the FINAL state so non-SMIL renderers show
        # the finished surface. SMIL drives the intro from the `from` values.
        parts.append(
            f'<g opacity="1">{paths}'
            f'<animate attributeName="opacity" from="0" to="1"'
            f' begin="{begin:.3f}s" dur="{RISE_DUR}s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate"'
            f' from="0 30" to="0 0" begin="{begin:.3f}s" dur="{RISE_DUR}s"'
            f' calcMode="spline" keySplines="0.16 1 0.3 1"'
            f' keyTimes="0;1" fill="freeze"/>'
            f"</g>"
        )
    return "".join(parts)


def _panel(field: list, theme: str) -> str:
    """Right-hand identity and activation panel."""
    t = THEMES[theme]
    px = PANEL_X
    out = []

    out.append(
        f'<path d="{text_to_path(IDENTITY["name"], FONTS["display"], 34, px, 132)}"'
        f' fill="{t["text"]}"/>'
    )
    out.append(_mono_row(IDENTITY["role"], px, 156, 10.5, t["accent"]))
    out.append(
        f'<line x1="{px}" y1="176" x2="1140" y2="176"'
        f' stroke="{t["border"]}" stroke-width="1"/>'
    )

    y = 200.0
    for key, val in IDENTITY["rows"]:
        out.append(_mono_row(f"{key:<12}", px, y, 9.5, t["muted"]))
        out.append(_mono_row(val, px + 84, y, 9.5, t["text"]))
        y += 17.0

    y += 12.0
    out.append(
        f'<line x1="{px}" y1="{y - 12:.0f}" x2="1140" y2="{y - 12:.0f}"'
        f' stroke="{t["border"]}" stroke-width="1"/>'
    )
    out.append(_mono_row(
        f"tensor(shape=({ROWS}, {COLS}), dtype=float32)", px, y, 9.0, t["muted"]))
    y += 16.0

    # A quiet float grid sampled from the same field the surface is built from.
    # Sampled over the central crop so the panel shows the subject, not the
    # empty margin around it.
    rows_n, cols_n = len(field), len(field[0])
    c0, c1 = int(cols_n * 0.20), int(cols_n * 0.80)
    r0, r1 = int(rows_n * 0.08), int(rows_n * 0.92)
    step_r = max(1, (r1 - r0) // 11)
    step_c = max(1, (c1 - c0) // 8)

    for r in range(r0, r1, step_r):
        vals = [field[r][c] for c in range(c0, c1, step_c)][:8]
        if not vals:
            break
        line = " ".join(f"{v:.2f}" for v in vals)
        out.append(_mono_row(
            line, px, y, 9.0,
            inferno(max(0.28, sum(vals) / len(vals)), theme), opacity=0.9))
        y += 13.0
        if y > 500:
            break

    return "".join(out)


def build_svg(field: list, theme: str) -> str:
    if theme not in THEMES:
        raise ValueError(f"unknown theme {theme!r}; expected 'dark' or 'light'")
    t = THEMES[theme]

    header = "".join([
        _mono_row("ACTIVATION SURFACE", 40, 38, 11.0, t["accent"]),
        _mono_row(f"inferno · {COLS}×{ROWS} · relief", 940, 38, 9.5, t["muted"]),
        f'<line x1="40" y1="52" x2="1140" y2="52"'
        f' stroke="{t["border"]}" stroke-width="1"/>',
    ])

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}"'
        f' width="{W}" height="{H}" role="img"'
        f' aria-label="Karthick A. R. — Software and AI/ML developer">'
        f'<rect width="{W}" height="{H}" rx="14" fill="{t["page"]}"/>'
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="13.5"'
        f' fill="none" stroke="{t["border"]}" stroke-width="1"/>'
        f"{header}{_surface(field, theme)}{_panel(field, theme)}"
        f"</svg>"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--photo", help="path to a front-facing portrait")
    args = ap.parse_args()

    if args.photo:
        try:
            img = Image.open(args.photo)
        except Exception as e:
            print(f"cannot read photo {args.photo!r}: {e}", file=sys.stderr)
            return 1
    else:
        print("no --photo given; using synthetic placeholder", file=sys.stderr)
        img = synthetic_portrait()

    field = height_field(img)
    for theme in ("dark", "light"):
        svg = build_svg(field, theme)
        size = len(svg.encode())
        if size > 700_000:
            print(f"{theme}.svg is {size} bytes, over the 700000 budget",
                  file=sys.stderr)
            return 1
        with open(f"{theme}.svg", "w") as f:
            f.write(svg)
        print(f"{theme}.svg  {size:,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
