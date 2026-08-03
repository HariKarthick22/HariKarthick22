import pytest

from lib.inferno import inferno, shade


def test_endpoints_dark():
    assert inferno(0.0, "dark") == "#000004"
    assert inferno(1.0, "dark") == "#FCFEA4"


def test_endpoints_light():
    assert inferno(0.0, "light") == "#EFE6D8"
    assert inferno(1.0, "light") == "#1A0A2E"


def test_midpoint_is_an_anchor():
    # 9 stops means t=0.5 lands exactly on index 4
    assert inferno(0.5, "dark") == "#BB3754"


def test_interpolates_between_stops():
    # t=0.0625 is exactly halfway between stop 0 (#000004) and stop 1 (#200C4A)
    assert inferno(0.0625, "dark") == "#100627"


def test_clamps_out_of_range():
    assert inferno(-3.0, "dark") == "#000004"
    assert inferno(99.0, "dark") == "#FCFEA4"


def test_rejects_unknown_theme():
    with pytest.raises(ValueError, match="unknown theme"):
        inferno(0.5, "solarized")


def test_shade_darkens():
    assert shade("#FCFEA4", 0.5) == "#7E7F52"


def test_shade_identity():
    assert shade("#BB3754", 1.0) == "#BB3754"


def test_shade_never_overflows():
    assert shade("#FCFEA4", 4.0) == "#FFFFFF"
