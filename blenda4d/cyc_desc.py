# SPDX-License-Identifier: GPL-3.0-or-later
"""The Cyc Wall: a photo-studio backdrop. A floor runs back, bends up through a quarter-circle Curve and rises as the
back wall, so the corner has no seam. Width runs along X, Length is the floor's depth (front to the foot of the wall,
the curve included) and Height the top of the wall. Defaults: 10 m x 5 m x 10 m with a 2 m curve."""

CYC_WALL = "cyc"

# (socket name, socket type, default, row key)
PARAMS = (
    ("Width", "FLOAT", 1000.0, "cyc.width"),
    ("Height", "FLOAT", 500.0, "cyc.height"),
    ("Length", "FLOAT", 1000.0, "cyc.length"),
    ("Curve", "FLOAT", 200.0, "cyc.curve"),
    ("Width Segments", "INT", 10, "cyc.width_segments"),
    ("Floor Segments", "INT", 10, "cyc.floor_segments"),
    ("Curve Segments", "INT", 12, "cyc.curve_segments"),
    ("Wall Segments", "INT", 6, "cyc.wall_segments"),
)


def inputs():
    """The generator inputs, in primitives.PRIMS form."""
    return list(PARAMS)
