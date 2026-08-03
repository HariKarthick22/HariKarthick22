"""Inferno colormap sampling.

Anchor values extracted from matplotlib 3.10.0. Inferno is perceptually uniform
and colorblind-safe by construction, which is why it is used here rather than a
hand-picked palette.
"""

RAMPS = {
    # matplotlib inferno, 9 evenly spaced samples
    "dark": [
        (0x00, 0x00, 0x04), (0x20, 0x0C, 0x4A), (0x57, 0x0F, 0x6D),
        (0x89, 0x22, 0x69), (0xBB, 0x37, 0x54), (0xE4, 0x5A, 0x31),
        (0xF9, 0x8E, 0x08), (0xF8, 0xCB, 0x34), (0xFC, 0xFE, 0xA4),
    ],
    # Contrast-corrected for a cream page: same hue path, inverted lightness.
    # Straight inferno is unusable on light backgrounds because its bright end
    # (pale gold) disappears entirely.
    "light": [
        (0xEF, 0xE6, 0xD8), (0xF8, 0xCB, 0x34), (0xF9, 0x8E, 0x08),
        (0xE4, 0x5A, 0x31), (0xBB, 0x37, 0x54), (0x89, 0x22, 0x69),
        (0x57, 0x0F, 0x6D), (0x20, 0x0C, 0x4A), (0x1A, 0x0A, 0x2E),
    ],
}


def inferno(t: float, theme: str = "dark") -> str:
    """Sample the ramp at t in [0, 1]. Out-of-range values are clamped."""
    try:
        stops = RAMPS[theme]
    except KeyError:
        raise ValueError(f"unknown theme {theme!r}; expected 'dark' or 'light'")

    t = min(1.0, max(0.0, t))
    pos = t * (len(stops) - 1)
    i = min(int(pos), len(stops) - 2)
    f = pos - i
    a, b = stops[i], stops[i + 1]
    return "#%02X%02X%02X" % tuple(round(a[c] + (b[c] - a[c]) * f) for c in range(3))


def shade(hex_color: str, factor: float) -> str:
    """Multiply a hex colour's channels. Used for isometric side faces."""
    h = hex_color.lstrip("#")
    ch = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    return "#%02X%02X%02X" % tuple(min(255, round(c * factor)) for c in ch)
