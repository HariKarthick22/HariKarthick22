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

    # Studio portraits are a subject on a light backdrop. Mapping raw brightness
    # to height would raise the empty backdrop and sink the face. Inverting
    # globally overcorrects — it turns dark hair and clothing into the bright
    # peaks. Instead, detect the backdrop and suppress it to zero while keeping
    # natural luminance inside the subject, so lit skin stays raised and hair
    # reads as recessed. The floor keeps dark regions above the cull threshold
    # so the silhouette does not lose its hair.
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    backdrop = float(np.median(border))
    centre = a[rows // 4: 3 * rows // 4, cols // 4: 3 * cols // 4]

    if backdrop > float(centre.mean()):
        subject = a < (backdrop - 0.10)
        if subject.sum() > 0.05 * a.size:
            vals = a[subject]
            v_lo, v_hi = float(vals.min()), float(vals.max())
            out = np.zeros_like(a)
            if v_hi - v_lo > 1e-6:
                out[subject] = 0.20 + 0.80 * (a[subject] - v_lo) / (v_hi - v_lo)
            else:
                out[subject] = 1.0
            a = out
        else:
            a = 1.0 - a       # no clean silhouette; fall back to a plain flip

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


# Code-glyph surface -------------------------------------------------------
# The portrait is drawn in the characters of an actual model definition. Each
# glyph sits at its cell's relief position, lifted by activation, coloured by
# inferno. Glyphs are absolutely positioned and centred, so the generic
# monospace fallback cannot shift the image.
CODE_SOURCE = (
    "class ActivationSurface(nn.Module):"
    "def __init__(self,d=512):super().__init__();"
    "self.enc=nn.Conv2d(3,d,3,padding=1);self.norm=nn.LayerNorm(d);"
    "self.attn=nn.MultiheadAttention(d,8);self.fc=nn.Linear(d,1)"
    "def forward(self,x):h=F.gelu(self.enc(x));h=self.norm(h.flatten(2).mT);"
    "a,_=self.attn(h,h,h);return torch.sigmoid(self.fc(a.mean(1)))"
)

C_COLS, C_ROWS = 88, 78
C_CELL_W, C_ROW_D = 5.6, 5.0
C_MAX_H = 26.0
C_X0, C_Y0 = 64.0, 96.0
C_FONT = 8.2


def _surface_code(field: list, theme: str) -> str:
    """Portrait rendered as source-code glyphs in relief."""
    rows, cols = len(field), len(field[0])
    bands: dict = {}
    i = 0

    for r in range(rows):
        for c in range(cols):
            v = field[r][c]
            ch = CODE_SOURCE[i % len(CODE_SOURCE)]
            i += 1
            if v < MIN_ACTIVATION or ch == " ":
                continue
            x = C_X0 + c * C_CELL_W
            y = C_Y0 + r * C_ROW_D - v * C_MAX_H
            esc = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}.get(ch, ch)
            bands.setdefault(r, []).append(
                f'<text x="{x:.1f}" y="{y:.1f}"'
                f' fill="{inferno(v, theme)}">{esc}</text>'
            )

    parts = []
    for r in sorted(bands):
        begin = r * 0.011
        parts.append(
            f'<g opacity="1">{"".join(bands[r])}'
            f'<animate attributeName="opacity" from="0" to="1"'
            f' begin="{begin:.3f}s" dur="0.45s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate"'
            f' from="0 18" to="0 0" begin="{begin:.3f}s" dur="0.45s"'
            f' calcMode="spline" keySplines="0.16 1 0.3 1"'
            f' keyTimes="0;1" fill="freeze"/></g>'
        )

    return (f'<g font-size="{C_FONT}" text-anchor="middle"'
            f' font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace">'
            + "".join(parts) + "</g>")


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
    # Report the field actually sampled, not the module default — the code and
    # relief styles use different grid resolutions.
    out.append(_mono_row(
        f"tensor(shape=({len(field)}, {len(field[0])}), dtype=float32)",
        px, y, 9.0, t["muted"]))
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


def build_svg(field: list, theme: str, style: str = "relief",
              code_field: list | None = None) -> str:
    if theme not in THEMES:
        raise ValueError(f"unknown theme {theme!r}; expected 'dark' or 'light'")
    if style not in ("relief", "code"):
        raise ValueError(f"unknown style {style!r}; expected 'relief' or 'code'")
    t = THEMES[theme]

    if style == "code":
        grid = f"{C_COLS}×{C_ROWS} · source"
        surface = _surface_code(code_field if code_field else field, theme)
    else:
        grid = f"{COLS}×{ROWS} · relief"
        surface = _surface(field, theme)

    header = "".join([
        _mono_row("ACTIVATION SURFACE", 40, 38, 11.0, t["accent"]),
        _mono_row(f"inferno · {grid}", 930, 38, 9.5, t["muted"]),
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
        f"{header}{surface}{_panel(code_field if style == 'code' and code_field else field, theme)}"
        f"</svg>"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--photo", help="path to a front-facing portrait")
    ap.add_argument("--style", choices=("relief", "code"), default="code",
                    help="extruded blocks, or the portrait drawn in source code")
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
    code_field = height_field(img, C_COLS, C_ROWS)
    for theme in ("dark", "light"):
        svg = build_svg(field, theme, args.style, code_field)
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
