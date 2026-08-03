import pytest

from lib.relief import (
    CELL_W,
    ORIGIN_X,
    ORIGIN_Y,
    ROW_D,
    column_faces,
    draw_order,
    project,
)


def test_origin_projects_to_origin_offset():
    assert project(0, 0, 0) == (ORIGIN_X, ORIGIN_Y)


def test_columns_advance_along_x_only():
    x0, y0 = project(0, 0, 0)
    x1, y1 = project(1, 0, 0)
    assert x1 - x0 == pytest.approx(CELL_W)
    assert y1 == y0, "columns must not drift vertically or the face shears"


def test_rows_advance_along_y_only():
    x0, y0 = project(0, 0, 0)
    x1, y1 = project(0, 1, 0)
    assert x1 == x0, "rows must not drift horizontally or the face shears"
    assert y1 - y0 == ROW_D


def test_height_lifts_the_point_upward():
    _, y_flat = project(3, 3, 0)
    _, y_tall = project(3, 3, 20)
    assert y_tall == y_flat - 20


def test_column_has_two_faces_of_four_points():
    faces = column_faces(2, 2, 10)
    assert set(faces) == {"top", "front"}
    for pts in faces.values():
        assert len(pts) == 4


def test_top_face_is_the_foreshortened_roof():
    faces = column_faces(2, 2, 10)
    xs = [p[0] for p in faces["top"]]
    ys = [p[1] for p in faces["top"]]
    assert max(xs) - min(xs) == pytest.approx(CELL_W)
    assert max(ys) - min(ys) == pytest.approx(ROW_D)


def test_front_face_height_equals_extrusion():
    faces = column_faces(2, 2, 26)
    ys = [p[1] for p in faces["front"]]
    assert max(ys) - min(ys) == 26


def test_front_face_hangs_below_the_roof():
    faces = column_faces(2, 2, 30)
    assert min(p[1] for p in faces["front"]) == max(p[1] for p in faces["top"])


def test_zero_height_column_has_a_degenerate_front():
    faces = column_faces(1, 1, 0)
    ys = [p[1] for p in faces["front"]]
    assert max(ys) - min(ys) == 0


def test_front_face_reaches_the_row_ground_line():
    _, ground_y = project(2, 3, 0)
    faces = column_faces(2, 2, 40)
    assert max(p[1] for p in faces["front"]) == ground_y


def test_draw_order_is_back_to_front():
    assert draw_order([(0, 5), (3, 0), (1, 2)]) == [(3, 0), (1, 2), (0, 5)]


def test_draw_order_is_stable_within_a_row():
    cells = [(0, 4), (1, 4), (2, 4)]
    assert draw_order(cells) == [(0, 4), (1, 4), (2, 4)]
