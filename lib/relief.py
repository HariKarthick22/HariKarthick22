"""Relief projection for the activation surface.

Pure geometry — no colour, no SVG.

Why not true isometric: a 2:1 isometric projection rotates the source grid 45
degrees on screen, which makes a face unrecognisable. The relief projection maps
grid columns directly to image x and grid rows to image y, so the subject stays
upright, while extrusion height plus a foreshortened top face still produce real
depth and real occlusion.

Each extruded cell shows two faces:
    top    — a CELL_W x ROW_D rectangle, the foreshortened "roof"
    front  — a CELL_W x height rectangle dropping to the row's ground line

Side faces are omitted because horizontally adjacent columns hide them, which
halves the emitted geometry.
"""

CELL_W = 9.4      # screen px per grid column
ROW_D = 7.0       # screen px per grid row (the foreshortened depth axis)
ORIGIN_X = 64.0
ORIGIN_Y = 104.0


def project(col: int, row: int, height: float) -> tuple:
    """Grid coordinate plus extrusion height -> screen point."""
    x = ORIGIN_X + col * CELL_W
    y = ORIGIN_Y + row * ROW_D - height
    return (x, y)


def column_faces(col: int, row: int, height: float) -> dict:
    """The two visible faces of an extruded cell, each as 4 screen points."""
    x0, y0 = project(col, row, height)
    x1 = x0 + CELL_W
    y1 = y0 + ROW_D                  # far edge of the roof
    y2 = y1 + height                 # ground line for this row
    return {
        "top": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
        "front": [(x0, y1), (x1, y1), (x1, y2), (x0, y2)],
    }


def draw_order(cells: list) -> list:
    """Painter's algorithm: ascending row draws back to front.

    Row 0 is the far edge of the surface. A tall column in a nearer row must be
    painted later so it occludes what stands behind it.
    """
    return sorted(cells, key=lambda cr: cr[1])
