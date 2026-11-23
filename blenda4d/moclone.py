# SPDX-License-Identifier: GPL-3.0-or-later
"""MoClone: the Cloner and the Matrix in the create column, the MoClone menu and the Attributes pages.

The objects themselves are node generators (generators.py builds and keeps them; moclone_nodes.py has their nodes).
Put objects under a Cloner and it places copies of them: in a row (Linear), a ring (Radial), a grid (Grid), a
honeycomb (Honeycomb) or on another object (Object). The Matrix makes the same arrangements as points, for other
Cloners to use; it shows as small cubes in the viewport and nothing in renders."""
import bpy

from . import generators as g
from . import kinds

ICONS = {"cloner": "MOD_ARRAY", "matrix": "LIGHTPROBE_VOLUME"}
TIPS = {"cloner": "Places copies of the objects under it in a row, ring, grid, honeycomb or on another object",
        "matrix": "Makes the points of a Cloner arrangement, shown as small cubes, for other Cloners to use"}


def _mode(v):
    return v("Mode")


def _mode_rows(cloner):
    rows = [("Mode", "Mode")]
    if cloner:
        rows += [("Clones", "Clones"), ("Reset Coordinates", "Reset Coordinates")]
    rows += [("Seed", "Seed"), None,
             # Object
             ("Object", "Object", lambda v: _mode(v) == "Object"),
             ("Distribution", "Distribution", lambda v: _mode(v) == "Object"),
             ("Object Count", "Count", lambda v: _mode(v) == "Object" and v("Distribution") in ("Surface", "Volume")),
             ("Align Clone", "Align Clone", lambda v: _mode(v) == "Object"),
             # Linear
             ("Count", "Count", lambda v: _mode(v) == "Linear"), ("Offset", "Offset", lambda v: _mode(v) == "Linear"),
             ("Linear Mode", "Mode", lambda v: _mode(v) == "Linear"), ("Amount", "Amount %", lambda v: _mode(v) == "Linear"),
             ("Position", "Position", lambda v: _mode(v) == "Linear"), ("Scale", "Scale %", lambda v: _mode(v) == "Linear"),
             ("Rotation", "Rotation", lambda v: _mode(v) == "Linear"), ("Step Mode", "Step Mode", lambda v: _mode(v) == "Linear"),
             ("Step Size", "Step Size %", lambda v: _mode(v) == "Linear"), ("Step Rotation", "Step Rotation", lambda v: _mode(v) == "Linear"),
             # Radial
             ("Radial Count", "Count", lambda v: _mode(v) == "Radial"), ("Radius", "Radius", lambda v: _mode(v) == "Radial"),
             ("Plane", "Plane", lambda v: _mode(v) == "Radial"), ("Align", "Align", lambda v: _mode(v) == "Radial"),
             ("Start Angle", "Start Angle", lambda v: _mode(v) == "Radial"), ("End Angle", "End Angle", lambda v: _mode(v) == "Radial"),
             ("Radial Offset", "Offset", lambda v: _mode(v) == "Radial"), ("Offset Variation", "Offset Variation %", lambda v: _mode(v) == "Radial"),
             # Grid
             ("Grid Count X", "Count . X", lambda v: _mode(v) == "Grid"), ("Grid Count Y", "Count . Y", lambda v: _mode(v) == "Grid"), ("Grid Count Z", "Count . Z", lambda v: _mode(v) == "Grid"), ("Grid Mode", "Mode", lambda v: _mode(v) == "Grid"),
             ("Grid Size", "Size", lambda v: _mode(v) == "Grid"), ("Form", "Form", lambda v: _mode(v) == "Grid"),
             ("Form Object", "Form Object", lambda v: _mode(v) == "Grid" and v("Form") == "Object"),
             ("Fill", "Fill %", lambda v: _mode(v) == "Grid"),
             # Honeycomb
             ("Honeycomb Direction", "Offset Direction", lambda v: _mode(v) == "Honeycomb"),
             ("Honeycomb Offset", "Offset %", lambda v: _mode(v) == "Honeycomb"),
             ("Width Count", "Width Count", lambda v: _mode(v) == "Honeycomb"), ("Height Count", "Height Count", lambda v: _mode(v) == "Honeycomb"),
             ("Honeycomb Mode", "Mode", lambda v: _mode(v) == "Honeycomb"),
             ("Width", "Width", lambda v: _mode(v) == "Honeycomb"), ("Height", "Height", lambda v: _mode(v) == "Honeycomb"),
             ("Honeycomb Plane", "Orientation", lambda v: _mode(v) == "Honeycomb"), ("Honeycomb Form", "Form", lambda v: _mode(v) == "Honeycomb"),
             ("Honeycomb Spline", "Spline", lambda v: _mode(v) == "Honeycomb" and v("Honeycomb Form") == "Spline")]
    return rows


def _only_mode(rows, ob):
    """Rows of the other modes are left out, not just dimmed: the page shows what the chosen mode uses."""
    out = []
    for r in rows:
        if r is not None and r[0] != "#" and len(r) > 2 and r[2] is not None:
            try:
                if not r[2](lambda name: g.gval(ob, name)):
                    continue
            except Exception:
                pass
        out.append(r)
    return out


def page_cloner(col, ob):
    if g._missing(col, ob):
        return
    if not g.kids_of(ob):
        g._hint(col, "Put objects under the Cloner")
    g._rows(col, ob, _only_mode(_mode_rows(True), ob))


def page_matrix(col, ob):
    if g._missing(col, ob):
        return
    g._rows(col, ob, _only_mode(_mode_rows(False), ob) + [None, ("Matrix Size", "Cube Size"), ("Show in Render", "Show in Render")])


def page_transform(col, ob):
    if g._missing(col, ob):
        return
    g._rows(col, ob, [("Clone Position", "Position"), ("Clone Scale", "Scale %"), ("Clone Rotation", "Rotation"), None,
                      ("Clone Color", "Color"), ("Clone Weight", "Weight %")])


def register():
    for k, page in (("cloner", page_cloner), ("matrix", page_matrix)):
        g.ICONS[k] = ICONS[k]
        g.TIPS[k] = TIPS[k]
        g.PAGES[k] = page
        kinds.add(k, g.LABELS[k], ICONS[k], create=(lambda k: lambda context: g.create(context, k))(k),
                  tabs=[("OBJECT", "Object"), ("TRANSFORM", "Transform")], pages={"OBJECT": page, "TRANSFORM": page_transform},
                  titles={"OBJECT": g.LABELS[k], "TRANSFORM": "Transform"},
                  describe=TIPS[k] + (" (selected objects go under it)" if k == "cloner" else ""))
        kinds.create_button("moclone", g.LABELS[k], k)


def unregister():
    pass
