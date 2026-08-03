import re
import xml.etree.ElementTree as ET

import pytest

from generate_banner import COLS, ROWS, build_svg, height_field, synthetic_portrait


@pytest.fixture(scope="module")
def field():
    return height_field(synthetic_portrait(), COLS, ROWS)


def test_field_has_expected_shape(field):
    assert len(field) == ROWS
    assert all(len(r) == COLS for r in field)


def test_field_values_are_normalised(field):
    flat = [v for row in field for v in row]
    assert min(flat) >= 0.0 and max(flat) <= 1.0


def test_field_reaches_full_brightness(field):
    flat = [v for row in field for v in row]
    assert max(flat) > 0.85, "contrast stretch is broken — surface will look flat"


def test_field_has_real_background(field):
    flat = [v for row in field for v in row]
    dark = sum(1 for v in flat if v < 0.05)
    assert dark > len(flat) * 0.1, "no background means the subject has no silhouette"


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_svg_is_well_formed(theme, field):
    ET.fromstring(build_svg(field, theme))


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_svg_within_size_budget(theme, field):
    size = len(build_svg(field, theme).encode())
    assert size <= 700_000, f"{theme}.svg is {size} bytes, budget is 700000"


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_no_webfont_references(theme, field):
    svg = build_svg(field, theme)
    assert "@font-face" not in svg
    assert "<link" not in svg
    assert "fonts.googleapis" not in svg


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_no_script_tags(theme, field):
    assert "<script" not in build_svg(field, theme)


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_reveal_animation_runs_once(theme, field):
    svg = build_svg(field, theme)
    assert "<animate" in svg
    assert 'repeatCount="indefinite"' not in svg
    assert 'fill="freeze"' in svg


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_static_state_is_the_finished_surface(theme, field):
    # Non-SMIL renderers must show the completed surface, not an empty canvas.
    svg = build_svg(field, theme)
    assert '<g opacity="1">' in svg
    assert '<g opacity="0">' not in svg


def test_mono_text_is_metrics_independent(field):
    # Every monospace run must pin its width so the generic fallback matches.
    svg = build_svg(field, "dark")
    for tag in re.findall(r"<text[^>]*>", svg):
        assert ' x="' in tag
        assert "textLength=" in tag
        assert 'lengthAdjust="spacing"' in tag


def test_rejects_unknown_theme(field):
    with pytest.raises(ValueError, match="unknown theme"):
        build_svg(field, "solarized")


def test_flat_field_produces_empty_surface():
    flat = [[0.0] * COLS for _ in range(ROWS)]
    svg = build_svg(flat, "dark")
    assert "<svg" in svg
    assert "<path" in svg  # display text still renders
