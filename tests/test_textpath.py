import pytest

from lib.textpath import FONTS, advance_width, text_to_path


def test_returns_a_path_string():
    d = text_to_path("Karthick", FONTS["display"], 32, 0, 0)
    assert d.startswith("M")
    assert len(d) > 100


def test_longer_text_makes_longer_path():
    short = text_to_path("A", FONTS["display"], 32, 0, 0)
    long = text_to_path("AAAAAAAA", FONTS["display"], 32, 0, 0)
    assert len(long) > len(short)


def test_offset_shifts_the_geometry():
    a = text_to_path("A", FONTS["display"], 32, 0, 0)
    b = text_to_path("A", FONTS["display"], 32, 100, 0)
    assert a != b


def test_space_only_text_returns_empty_path():
    assert text_to_path("   ", FONTS["display"], 32, 0, 0) == ""


def test_empty_text_returns_empty_path():
    assert text_to_path("", FONTS["display"], 32, 0, 0) == ""


def test_missing_font_raises_naming_the_file():
    # A silent <text> fallback is the exact bug this module exists to prevent
    with pytest.raises(FileNotFoundError, match="NoSuchFont.ttf"):
        text_to_path("x", "fonts/NoSuchFont.ttf", 32, 0, 0)


def test_advance_width_scales_with_size():
    small = advance_width("Karthick", FONTS["display"], 16)
    large = advance_width("Karthick", FONTS["display"], 32)
    assert large == pytest.approx(small * 2, rel=1e-6)


def test_monospace_advance_is_uniform():
    one = advance_width("X", FONTS["mono"], 10)
    five = advance_width("XXXXX", FONTS["mono"], 10)
    assert five == pytest.approx(one * 5, rel=1e-6)
