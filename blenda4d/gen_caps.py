# SPDX-License-Identifier: GPL-3.0-or-later
"""Caps and bevels shared by Extrude / Lathe / Loft / Sweep, and the Regular Grid of the primitives' Slice
.

Everything is built flat: the contour lies in XY and +Z points away from the object, callers move the result
into place. A bevel pushes the cap outward (the object gets taller): the
contour stays, each bevel ring is the contour moved inward by a and outward by h."""
import math

from .primitives import _math, _cm


def vmath(nodes, links, op, a, b=None, scale=None):
    n = nodes.new("ShaderNodeVectorMath"); n.operation = op
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if hasattr(v, "is_output"):
            links.new(v, n.inputs[i])
        else:
            n.inputs[i].default_value = v
    if scale is not None:
        if hasattr(scale, "is_output"):
            links.new(scale, n.inputs["Scale"])
        else:
            n.inputs["Scale"].default_value = scale
    return n.outputs[0]


def dot(nodes, links, a, b):
    n = nodes.new("ShaderNodeVectorMath"); n.operation = "DOT_PRODUCT"
    links.new(a, n.inputs[0])
    if hasattr(b, "is_output"):
        links.new(b, n.inputs[1])
    else:
        n.inputs[1].default_value = b
    return n.outputs["Value"]


def switch(nodes, links, kind, flag, off, on):
    s = nodes.new("GeometryNodeSwitch"); s.input_type = kind
    links.new(flag, s.inputs["Switch"])
    for name, v in (("False", off), ("True", on)):
        if hasattr(v, "is_output"):
            links.new(v, s.inputs[name])
        else:
            s.inputs[name].default_value = v
    return s.outputs[0]


def index_switch(nodes, links, kind, index, values):
    s = nodes.new("GeometryNodeIndexSwitch"); s.data_type = kind
    while len(s.index_switch_items) < len(values):
        s.index_switch_items.new()
    links.new(index, s.inputs["Index"])
    for k, v in enumerate(values):
        if hasattr(v, "is_output"):
            links.new(v, s.inputs[k + 1])
        else:
            s.inputs[k + 1].default_value = v
    return s.outputs[0]


def join(nodes, links, geos):
    j = nodes.new("GeometryNodeJoinGeometry")
    for g in geos:
        links.new(g, j.inputs[0])
    return j.outputs[0]


def merge(nodes, links, geo, dist=1e-5):
    m = nodes.new("GeometryNodeMergeByDistance"); links.new(geo, m.inputs["Geometry"]); m.inputs["Distance"].default_value = dist
    return m.outputs["Geometry"]


def combine(nodes, links, x=None, y=None, z=None):
    c = nodes.new("ShaderNodeCombineXYZ")
    for name, v in (("X", x), ("Y", y), ("Z", z)):
        if v is None:
            continue
        if hasattr(v, "is_output"):
            links.new(v, c.inputs[name])
        else:
            c.inputs[name].default_value = v
    return c.outputs[0]


def separate(nodes, links, v):
    s = nodes.new("ShaderNodeSeparateXYZ"); links.new(v, s.inputs[0])
    return s.outputs


def position(nodes):
    return nodes.new("GeometryNodeInputPosition").outputs[0]


def move(nodes, links, geo, translation=None, rotation=None, scale=None):
    t = nodes.new("GeometryNodeTransform"); links.new(geo, t.inputs["Geometry"])
    for name, v in (("Translation", translation), ("Rotation", rotation), ("Scale", scale)):
        if v is None:
            continue
        if hasattr(v, "is_output"):
            links.new(v, t.inputs[name])
        else:
            t.inputs[name].default_value = v
    return t.outputs["Geometry"]


def flip(nodes, links, geo):
    f = nodes.new("GeometryNodeFlipFaces"); links.new(geo, f.inputs["Mesh"])
    return f.outputs["Mesh"]


def align_z(nodes, links, normal):
    """(rotation taking +Z to normal, its inverse)."""
    a = nodes.new("FunctionNodeAlignRotationToVector"); a.axis = "Z"; a.pivot_axis = "AUTO"
    links.new(normal, a.inputs["Vector"])
    i = nodes.new("FunctionNodeInvertRotation"); links.new(a.outputs[0], i.inputs[0])
    return a.outputs[0], i.outputs[0]


def fill(nodes, links, curve, mode):
    f = nodes.new("GeometryNodeFillCurve"); f.inputs["Mode"].default_value = mode
    links.new(curve, f.inputs["Curve"])
    g = nodes.new("GeometryNodeInputNamedAttribute"); g.data_type = "INT"; g.inputs["Name"].default_value = "b4d_group"
    links.new(g.outputs["Attribute"], f.inputs["Group ID"])         # ArtSmart: each shape fills alone; elsewhere absent, so 0
    return f.outputs["Mesh"]


def grid_fill(nodes, links, curve, spacing, jitter=0.0, quad=None, margin=0.0):
    """Regular grid inside the contour, stitched to it with a triangle band (holes respected)."""
    ngon = fill(nodes, links, curve, "Triangles")      # what the rays test inside against: an N-gon fill of a dense
                                                       # outline with holes can come out broken (letters got no grid)
    bb = nodes.new("GeometryNodeBoundBox"); links.new(ngon, bb.inputs["Geometry"])    # the filled shape, not the curve:
                                                       # a curve's box counts its Bezier handles, which in an SVG can lie
                                                       # metres away (the grid grew to 258 m and missed the letters)
    size = vmath(nodes, links, "SUBTRACT", bb.outputs["Max"], bb.outputs["Min"])
    centre = vmath(nodes, links, "SCALE", vmath(nodes, links, "ADD", bb.outputs["Min"], bb.outputs["Max"]), scale=0.5)
    sx, sy, _sz = separate(nodes, links, size)
    longest = _math(nodes, "MAXIMUM", sx, sy, links)
    sp = _math(nodes, "MAXIMUM", spacing, _math(nodes, "DIVIDE", longest, 200.0, links), links)
    g = nodes.new("GeometryNodeMeshGrid")
    links.new(sx, g.inputs["Size X"]); links.new(sy, g.inputs["Size Y"])
    links.new(_math(nodes, "ADD", _math(nodes, "CEIL", _math(nodes, "DIVIDE", sx, sp, links), None, links), 1, links), g.inputs["Vertices X"])
    links.new(_math(nodes, "ADD", _math(nodes, "CEIL", _math(nodes, "DIVIDE", sy, sp, links), None, links), 1, links), g.inputs["Vertices Y"])
    grid = move(nodes, links, g.outputs["Mesh"], translation=centre)
    p = position(nodes)
    ray = nodes.new("GeometryNodeRaycast")
    links.new(ngon, ray.inputs["Target Geometry"])
    links.new(vmath(nodes, links, "ADD", p, (0.0, 0.0, 1.0)), ray.inputs["Source Position"])
    ray.inputs["Ray Direction"].default_value = (0.0, 0.0, -1.0); ray.inputs["Ray Length"].default_value = 2.0
    edges = nodes.new("GeometryNodeCurveToMesh"); links.new(curve, edges.inputs["Curve"])
    prox = nodes.new("GeometryNodeProximity"); prox.target_element = "EDGES"
    links.new(edges.outputs["Mesh"], prox.inputs["Geometry"]); links.new(p, prox.inputs["Sample Position"])
    # Judged per grid square, at its centre: a square stays only when no part of the contour comes within its
    # half-diagonal (plus the jitter and a margin), so it lies wholly inside. Judging its corners instead let a sharp
    # inner corner (the notches of N, A, 4) poke into a kept square, and the band filled around it left holes.
    reach = _math(nodes, "ADD", _math(nodes, "MULTIPLY", sp, 0.8 + 1.5 * jitter, links), margin, links)
    far = _math(nodes, "GREATER_THAN", prox.outputs["Distance"], reach, links)
    keep = _math(nodes, "MULTIPLY", ray.outputs["Is Hit"], far, links)
    de = nodes.new("GeometryNodeDeleteGeometry"); de.domain = "FACE"; de.mode = "ALL"
    links.new(grid, de.inputs["Geometry"]); links.new(_math(nodes, "LESS_THAN", keep, 0.5, links), de.inputs["Selection"])
    inner = de.outputs["Geometry"]
    if jitter:
        r = nodes.new("FunctionNodeRandomValue"); r.data_type = "FLOAT_VECTOR"
        r.inputs[0].default_value = (-jitter, -jitter, 0.0); r.inputs[1].default_value = (jitter, jitter, 0.0)
        sp2 = nodes.new("GeometryNodeSetPosition"); links.new(inner, sp2.inputs["Geometry"])
        links.new(vmath(nodes, links, "SCALE", r.outputs[0], scale=sp), sp2.inputs["Offset"])
        inner = sp2.outputs["Geometry"]
    tri = nodes.new("GeometryNodeTriangulate"); links.new(inner, tri.inputs["Mesh"])
    tri.inputs["Quad Method"].default_value = "Fixed Alternate"
    body = tri.outputs["Mesh"] if quad is None else switch(nodes, links, "GEOMETRY", quad, tri.outputs["Mesh"], inner)
    fc = nodes.new("GeometryNodeInputMeshEdgeNeighbors")
    m2c = nodes.new("GeometryNodeMeshToCurve"); links.new(inner, m2c.inputs["Mesh"])
    links.new(_math(nodes, "LESS_THAN", fc.outputs["Face Count"], 1.5, links), m2c.inputs["Selection"])
    band = fill(nodes, links, join(nodes, links, [curve, m2c.outputs["Curve"]]), "Triangles")
    return merge(nodes, links, join(nodes, links, [body, band]))


def flat_fill(nodes, links, o, curve, margin=0.0):
    """Cap surface of a contour lying in XY, per Tessellation."""
    cyc = nodes.new("GeometryNodeInputSplineCyclic").outputs[0]
    op = nodes.new("GeometryNodeDeleteGeometry"); op.domain = "CURVE"
    links.new(curve, op.inputs["Geometry"]); links.new(_math(nodes, "LESS_THAN", cyc, 0.5, links), op.inputs["Selection"])
    closed = op.outputs["Geometry"]
    tris = fill(nodes, links, closed, "Triangles")
    bb = nodes.new("GeometryNodeBoundBox"); links.new(tris, bb.inputs["Geometry"])     # not the curve (its handles)
    sx, sy, _z = separate(nodes, links, vmath(nodes, links, "SUBTRACT", bb.outputs["Max"], bb.outputs["Min"]))
    longest = _math(nodes, "MAXIMUM", sx, sy, links)
    dens = _math(nodes, "DIVIDE", longest, _math(nodes, "ADD", 2.0, _math(nodes, "MULTIPLY", o["Density"], 0.4, links), links), links)
    return index_switch(nodes, links, "GEOMETRY", o["Tessellation"], [
        tris, tris, switch(nodes, links, "GEOMETRY", has_holes(nodes, links, closed), fill(nodes, links, closed, "N-gons"), tris),
        grid_fill(nodes, links, closed, dens, 0.3, o["Quad Dominant"], margin),
        grid_fill(nodes, links, closed, _cm(nodes, links, o["Cap Size"]), 0.0, o["Quad Dominant"], margin)])


def has_holes(nodes, links, curve):
    """True when some contour runs the other way round from another (inward_ring winds a hole against its outline).
    Blender's N-gon fill turns a hole into a keyhole face that its own triangulation covers again, so such caps fill
    with triangles: Blender's N-gons cannot hold a hole. Measured: a lone "B" came out solid."""
    nxt = nodes.new("GeometryNodeOffsetPointInCurve"); nxt.inputs["Offset"].default_value = 1
    at = nodes.new("GeometryNodeFieldAtIndex"); at.domain = "POINT"; at.data_type = "FLOAT_VECTOR"
    links.new(position(nodes), at.inputs["Value"]); links.new(nxt.outputs["Point Index"], at.inputs["Index"])
    a, b = separate(nodes, links, position(nodes)), separate(nodes, links, at.outputs[0])
    cross = _math(nodes, "SUBTRACT", _math(nodes, "MULTIPLY", a["X"], b["Y"], links), _math(nodes, "MULTIPLY", b["X"], a["Y"], links), links)
    per = nodes.new("GeometryNodeFieldOnDomain"); per.domain = "POINT"; per.data_type = "FLOAT"; links.new(cross, per.inputs[0])
    st = nodes.new("GeometryNodeAttributeStatistic"); st.data_type = "FLOAT"; st.domain = "CURVE"      # each contour's mean: its winding
    links.new(curve, st.inputs["Geometry"]); links.new(per.outputs[0], st.inputs["Attribute"])
    both = _math(nodes, "MULTIPLY", _math(nodes, "LESS_THAN", st.outputs["Min"], 0.0, links), _math(nodes, "GREATER_THAN", st.outputs["Max"], 0.0, links), links)
    return _math(nodes, "GREATER_THAN", both, 0.5, links)


def side_value(nodes, links, o, side, name, kind="FLOAT"):
    if side == "S":
        return o["S " + name]
    return switch(nodes, links, kind, o["Separate Controls"], o["S " + name], o["E " + name])


def bevel_profile(nodes, links, o, side):
    """(profile curve: x = inward, y = outward; inward total a; outward total h; size S; offset O)."""
    S = _cm(nodes, links, side_value(nodes, links, o, side, "Size"))
    n = _math(nodes, "MAXIMUM", side_value(nodes, links, o, side, "Subdivision", "INT"), 1, links)
    shape = side_value(nodes, links, o, side, "Shape", "INT")
    ext = side_value(nodes, links, o, side, "Extrusion", "BOOLEAN")
    O = switch(nodes, links, "FLOAT", ext, 0.0, _cm(nodes, links, side_value(nodes, links, o, side, "Offset")))
    T = _math(nodes, "DIVIDE", side_value(nodes, links, o, side, "Tension"), 100.0, links)
    rows = index_switch(nodes, links, "FLOAT", shape, [n, n, _math(nodes, "MULTIPLY", n, 2.0, links), n])
    line = nodes.new("GeometryNodeMeshLine"); line.mode = "OFFSET"; line.count_mode = "TOTAL"
    links.new(_math(nodes, "ADD", rows, 2, links), line.inputs["Count"])
    i = nodes.new("GeometryNodeInputIndex").outputs[0]
    k = _math(nodes, "MAXIMUM", _math(nodes, "SUBTRACT", i, 1, links), 0.0, links)
    t = _math(nodes, "DIVIDE", k, rows, links)
    th = _math(nodes, "MULTIPLY", t, math.pi / 2, links)
    a_r = _math(nodes, "SUBTRACT", 1.0, _math(nodes, "COSINE", th, None, links), links)
    h_r = _math(nodes, "SINE", th, None, links)
    a_m = _math(nodes, "ADD", t, _math(nodes, "MULTIPLY", _math(nodes, "SUBTRACT", a_r, t, links), T, links), links)
    h_m = _math(nodes, "ADD", t, _math(nodes, "MULTIPLY", _math(nodes, "SUBTRACT", h_r, t, links), T, links), links)
    half = _math(nodes, "DIVIDE", k, 2.0, links)
    a_s = _math(nodes, "DIVIDE", _math(nodes, "FLOOR", half, None, links), n, links)
    h_s = _math(nodes, "DIVIDE", _math(nodes, "CEIL", half, None, links), n, links)
    a = index_switch(nodes, links, "FLOAT", shape, [a_m, 0.0, a_s, a_m])
    h = index_switch(nodes, links, "FLOAT", shape, [h_m, t, h_s, h_m])
    after = _math(nodes, "GREATER_THAN", i, 0.5, links)
    y = _math(nodes, "ADD", _math(nodes, "MULTIPLY", h, S, links), _math(nodes, "MULTIPLY", after, O, links), links)
    sp = nodes.new("GeometryNodeSetPosition"); links.new(line.outputs["Mesh"], sp.inputs["Geometry"])
    links.new(combine(nodes, links, _math(nodes, "MULTIPLY", a, S, links), y), sp.inputs["Position"])
    m2c = nodes.new("GeometryNodeMeshToCurve"); links.new(sp.outputs["Geometry"], m2c.inputs["Mesh"])
    a_end = index_switch(nodes, links, "FLOAT", shape, [S, 0.0, S, S])
    return m2c.outputs["Curve"], a_end, _math(nodes, "ADD", S, O, links), S, O


def dedupe(nodes, links, curve, dist=1e-4):
    """The contour without doubled points (an SVG's sharp corners often have two in one place). A bevel moves each
    copy its own way while the cap can only meet one, which left a small gap at every such corner. A point lying on
    the one before it is deleted; each spline stays closed."""
    prev = nodes.new("GeometryNodeOffsetPointInCurve"); prev.inputs["Offset"].default_value = -1
    at = nodes.new("GeometryNodeFieldAtIndex"); at.domain = "POINT"; at.data_type = "FLOAT_VECTOR"
    links.new(position(nodes), at.inputs["Value"]); links.new(prev.outputs["Point Index"], at.inputs["Index"])
    d = nodes.new("ShaderNodeVectorMath"); d.operation = "DISTANCE"
    links.new(position(nodes), d.inputs[0]); links.new(at.outputs[0], d.inputs[1])
    same = _math(nodes, "LESS_THAN", d.outputs["Value"], dist, links)
    de = nodes.new("GeometryNodeDeleteGeometry"); de.domain = "POINT"
    links.new(curve, de.inputs["Geometry"]); links.new(same, de.inputs["Selection"])
    return de.outputs["Geometry"]


def inward_ring(nodes, links, curve):
    """Contour in XY with Z-up normals, wound so the curve normal points into the material (holes included)."""
    base = nodes.new("GeometryNodeSetCurveNormal"); base.inputs["Mode"].default_value = "Z Up"
    links.new(curve, base.inputs["Curve"])
    ng = fill(nodes, links, curve, "N-gons")
    nrm = nodes.new("GeometryNodeInputNormal").outputs[0]
    src = vmath(nodes, links, "ADD", vmath(nodes, links, "ADD", position(nodes), vmath(nodes, links, "SCALE", nrm, scale=1e-3)), (0.0, 0.0, 1.0))
    ray = nodes.new("GeometryNodeRaycast")
    links.new(ng, ray.inputs["Target Geometry"]); links.new(src, ray.inputs["Source Position"])
    ray.inputs["Ray Direction"].default_value = (0.0, 0.0, -1.0); ray.inputs["Ray Length"].default_value = 2.0
    # stored per point first: Evaluate on Domain would run the ray from each spline's average point
    st = nodes.new("GeometryNodeStoreNamedAttribute"); st.data_type = "FLOAT"; st.domain = "POINT"
    st.inputs["Name"].default_value = "b4d_in"
    links.new(base.outputs["Curve"], st.inputs["Geometry"]); links.new(_math(nodes, "ADD", ray.outputs["Is Hit"], 0.0, links), st.inputs["Value"])
    rd = nodes.new("GeometryNodeInputNamedAttribute"); rd.data_type = "FLOAT"; rd.inputs["Name"].default_value = "b4d_in"
    dom = nodes.new("GeometryNodeFieldOnDomain"); dom.domain = "CURVE"; dom.data_type = "FLOAT"
    links.new(rd.outputs["Attribute"], dom.inputs[0])
    wrong = _math(nodes, "LESS_THAN", dom.outputs[0], 0.5, links)
    cyc = nodes.new("GeometryNodeInputSplineCyclic").outputs[0]
    rev = nodes.new("GeometryNodeReverseCurve"); links.new(st.outputs["Geometry"], rev.inputs["Curve"])
    links.new(_math(nodes, "GREATER_THAN", _math(nodes, "MULTIPLY", wrong, cyc, links), 0.5, links), rev.inputs["Selection"])
    return rev.outputs["Curve"]


def inset(nodes, links, ring, distance):
    nrm = nodes.new("GeometryNodeInputNormal").outputs[0]
    sp = nodes.new("GeometryNodeSetPosition"); links.new(ring, sp.inputs["Geometry"])
    links.new(vmath(nodes, links, "SCALE", nrm, scale=distance), sp.inputs["Offset"])
    return sp.outputs["Geometry"]


def sweep_ring(nodes, links, ring, profile):
    # measured (Blender 5.2, Z-up normals): Curve to Mesh puts profile Y on -Z
    c = nodes.new("GeometryNodeCurveToMesh")
    links.new(ring, c.inputs["Curve"]); links.new(move(nodes, links, profile, scale=(1.0, -1.0, 1.0)), c.inputs["Profile Curve"])
    return c.outputs["Mesh"]


# which part of a Caps-and-Bevels solid a face is, kept on the faces as .b4d_part:
# a material tag's Selection names a part by its code (C1, C2, R1, R2) or by the
# Selections tab's tag name. piece() writes cap / bevel; the extrude then turns them into the start and end codes.
PART_ATTR = ".b4d_part"
PART_SHELL, PART_CAP, PART_BEVEL = 0, 1, 2
PART_CODES = {"C1": 1, "C2": 2, "R1": 3, "R2": 4}           # start cap, end cap, start bevel, end bevel
PART_NAMES = {"Shell": 0, "Start Cap": 1, "End Cap": 2, "Start Bevel": 3, "End Bevel": 4}


def part(nodes, links, geo, value):
    """Mark every face of geo as one part; value is a number or a socket."""
    st = nodes.new("GeometryNodeStoreNamedAttribute"); st.data_type = "INT"; st.domain = "FACE"
    links.new(geo, st.inputs["Geometry"]); st.inputs["Name"].default_value = PART_ATTR
    if hasattr(value, "is_output"):
        links.new(value, st.inputs["Value"])
    else:
        st.inputs["Value"].default_value = int(value)
    return st.outputs["Geometry"]


def part_field(nodes):
    a = nodes.new("GeometryNodeInputNamedAttribute"); a.data_type = "INT"; a.inputs["Name"].default_value = PART_ATTR
    return a.outputs["Attribute"]


def side_part(nodes, links, geo, start):
    """A piece's cap / bevel marks as the start or end codes: cap 1 -> C1 or C2, bevel 2 -> R1 or R2."""
    v = _math(nodes, "SUBTRACT", _math(nodes, "MULTIPLY", part_field(nodes), 2.0, links), 1.0 if start else 0.0, links)
    return part(nodes, links, geo, v)


def cap_surface(nodes, links, o, clean, contour, margin):
    """The cap inside contour, which is clean with each point moved (clean and contour have the same points, in the
    same order). Filling contour itself left holes: moved along their normals, the points near a sharp corner cross
    over each other and the fill reads the little loop that makes as a hole. So the clean outline is filled and only
    its edge points are then moved where contour has them; at such a corner the cap folds over by a hair instead."""
    idx = nodes.new("GeometryNodeInputIndex").outputs[0]
    to = nodes.new("GeometryNodeSampleIndex"); to.data_type = "FLOAT_VECTOR"; to.domain = "POINT"
    links.new(contour, to.inputs["Geometry"]); links.new(position(nodes), to.inputs["Value"]); links.new(idx, to.inputs["Index"])
    st = nodes.new("GeometryNodeStoreNamedAttribute"); st.data_type = "FLOAT_VECTOR"; st.domain = "POINT"
    st.inputs["Name"].default_value = "b4d_to"
    links.new(clean, st.inputs["Geometry"]); links.new(to.outputs[0], st.inputs["Value"])
    pts = nodes.new("GeometryNodeCurveToPoints"); pts.mode = "EVALUATED"; links.new(st.outputs["Geometry"], pts.inputs["Curve"])
    surf = flat_fill(nodes, links, o, clean, margin)
    near = nodes.new("GeometryNodeSampleNearest"); near.domain = "POINT"
    links.new(pts.outputs["Points"], near.inputs["Geometry"])
    at = nodes.new("GeometryNodeSampleIndex"); at.data_type = "FLOAT_VECTOR"; at.domain = "POINT"
    links.new(pts.outputs["Points"], at.inputs["Geometry"]); links.new(position(nodes), at.inputs["Value"])
    links.new(near.outputs["Index"], at.inputs["Index"])
    rd = nodes.new("GeometryNodeInputNamedAttribute"); rd.data_type = "FLOAT_VECTOR"; rd.inputs["Name"].default_value = "b4d_to"
    dest = nodes.new("GeometryNodeSampleIndex"); dest.data_type = "FLOAT_VECTOR"; dest.domain = "POINT"
    links.new(pts.outputs["Points"], dest.inputs["Geometry"]); links.new(rd.outputs["Attribute"], dest.inputs["Value"])
    links.new(near.outputs["Index"], dest.inputs["Index"])
    gap = nodes.new("ShaderNodeVectorMath"); gap.operation = "DISTANCE"
    links.new(at.outputs[0], gap.inputs[0]); links.new(position(nodes), gap.inputs[1])
    on_edge = _math(nodes, "LESS_THAN", gap.outputs["Value"], 1e-6, links)
    sp = nodes.new("GeometryNodeSetPosition"); links.new(surf, sp.inputs["Geometry"])
    links.new(on_edge, sp.inputs["Selection"]); links.new(dest.outputs[0], sp.inputs["Position"])
    rm = nodes.new("GeometryNodeRemoveAttribute"); links.new(sp.outputs["Geometry"], rm.inputs["Geometry"])
    rm.inputs["Name"].default_value = "b4d_to"
    return rm.outputs["Geometry"]


def piece(nodes, links, o, side, ring, clean=None):
    """Bevel + cap on a flat contour: base at z = 0, outward = +Z. clean: the contour before ring was offset from it
    (the same points), when it was; the cap is filled from it."""
    from .node_arrange import subgroup
    tree, name = nodes.id_data, {"S": "Start", "E": "End"}.get(side, str(side))

    def bevel(n, l):                                    # each half its own node group: one box in the tree
        prof, a_end, h_end, S, O = bevel_profile(n, l, o, side)
        return part(n, l, sweep_ring(n, l, ring, prof), PART_BEVEL), a_end, h_end, S, O
    wall, a_end, h_end, S, O = subgroup(tree, name + " Bevel", bevel)
    cap = subgroup(tree, name + " Cap", lambda n, l: part(n, l, move(n, l, cap_surface(n, l, o, ring if clean is None else clean,
                                                                                       inset(n, l, ring, a_end), _math(n, "ABSOLUTE", a_end, None, l)),
                                                                    translation=combine(n, l, z=h_end)), PART_CAP))
    has = _math(nodes, "GREATER_THAN", _math(nodes, "ADD", S, _math(nodes, "ABSOLUTE", O, None, links), links), 1e-6, links)
    return switch(nodes, links, "GEOMETRY", has, cap, merge(nodes, links, join(nodes, links, [wall, cap])))


def outward(nodes, links, geo):
    """Flip a closed solid that came out inside-out: its signed volume is the sum of area * (normal . position)."""
    area = nodes.new("GeometryNodeInputMeshFaceArea").outputs[0]
    nrm = nodes.new("GeometryNodeInputNormal").outputs[0]
    st = nodes.new("GeometryNodeAttributeStatistic"); st.domain = "FACE"; st.data_type = "FLOAT"
    links.new(geo, st.inputs["Geometry"])
    links.new(_math(nodes, "MULTIPLY", area, dot(nodes, links, nrm, position(nodes)), links), st.inputs["Attribute"])
    return switch(nodes, links, "GEOMETRY", _math(nodes, "LESS_THAN", st.outputs["Sum"], 0.0, links), geo, flip(nodes, links, geo))
