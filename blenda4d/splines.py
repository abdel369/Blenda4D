# SPDX-License-Identifier: GPL-3.0-or-later
"""Splines: parametric spline shapes (Circle, Rectangle, Arc, Star, Helix, ...) and the spline page of any curve.

A spline shape is an ordinary Blender Curve object. Its settings live in `ob.b4d_spline` (one property group per
object); every change writes the curve's splines again, so the object is always a real curve with real points:
anything that reads curves (Geometry Nodes Object Info, a Curve modifier, a bevel, another Blenda module) sees it.
The kind is stored as ob["b4d_type"] ("circle", "helix", ...). Shapes are worked out in Blenda's Y-up centimetres
on a chosen plane and written in Blender metres.

For other modules (Sweep, Lathe, Loft, Extrude):
    splines.is_spline(ob)          True for any curve object (shape or plain)
    splines.sample(ob, depsgraph)  [(points, closed)] the evaluated curve as point lists in object space, one per
                                   spline, with the intermediate points the object's settings ask for
In Geometry Nodes, an Object Info node pointed at the object gives the same curve (cyclic flags and resolution kept).

A plain Blender curve gets the same page: Type converts the curve in place (Bezier handles are kept aside and come
back when Type returns to Bezier), Close Spline sets every spline cyclic, Intermediate Points sets the resolution."""
import json
import math
import re

import bpy
from mathutils import Vector

from . import kinds

SCALE = 0.01                                     # 1 cm in Blender metres
SHAPE = "shape"                                  # marks a curve written by this module (curve["b4d_spline"])

TYPES = [("LINEAR", "Linear", "Straight lines between the points"),
         ("CUBIC", "Cubic", "A smooth curve through every point"),
         ("AKIMA", "Akima", "A smooth curve through every point that does not overshoot"),
         ("BSPLINE", "B-Spline", "A smooth curve pulled towards the points, not through them"),
         ("BEZIER", "Bezier", "Each point has its own handles")]
PLANES = [("XY", "XY", "Upright, facing the front view"), ("ZY", "ZY", "Upright, facing the side view"),
          ("XZ", "XZ", "Lying flat on the ground")]


# ------------------------------------------------------------------ the shapes and their settings
# kind -> (label, icon, natural Type, always closed, [(setting, label, kind, default, extra)], tip)
# setting kinds: D distance (cm), A angle (degrees), P percent, I whole number, B switch, E menu (extra = items), S text
SHAPES = {
    "circle": ("Circle", "CURVE_BEZCIRCLE", "BEZIER", True, [
        ("ellipse", "Ellipse", "B", False, None), ("radius", "Radius", "D", 200.0, None),
        ("radius_y", "Radius Y", "D", 100.0, "ellipse"), ("ring", "Ring", "B", False, None),
        ("inner_radius", "Inner Radius", "D", 100.0, "ring")], "A circle, an ellipse or a ring"),
    "rectangle": ("Rectangle", "MESH_PLANE", "LINEAR", True, [
        ("width", "Width", "D", 400.0, None), ("height", "Height", "D", 400.0, None),
        ("rounding", "Rounded Corners", "B", False, None), ("radius", "Corner Radius", "D", 50.0, "rounding")],
        "A rectangle, with or without rounded corners"),
    "arc": ("Arc", "SPHERECURVE", "BEZIER", False, [
        ("style", "Style", "E", "ARC", [("ARC", "Arc", "Just the arc"), ("SECTOR", "Pie Slice", "The arc and two lines to the centre"),
                                       ("SEGMENT", "Segment", "The arc closed by a straight line"),
                                       ("RING", "Ring Piece", "The arc with an inner arc")]),
        ("radius", "Radius", "D", 200.0, None), ("inner_radius", "Inner Radius", "D", 100.0, "style=RING"),
        ("start_angle", "Start Angle", "A", 0.0, None), ("end_angle", "End Angle", "A", 90.0, None)],
        "Part of a circle"),
    "star": ("Star", "SOLO_OFF", "LINEAR", True, [
        ("inner_radius", "Inner Radius", "D", 100.0, None), ("outer_radius", "Outer Radius", "D", 200.0, None),
        ("twist", "Twist", "P", 0.0, None), ("points", "Points", "I", 8, None)], "A star with any number of points"),
    "nside": ("Polygon", "MESH_CIRCLE", "LINEAR", True, [
        ("radius", "Radius", "D", 200.0, None), ("sides", "Sides", "I", 6, None),
        ("rounding", "Rounded Corners", "B", False, None), ("corner_radius", "Corner Radius", "D", 50.0, "rounding")],
        "A regular polygon with any number of sides"),
    "fourside": ("Four Sided", "MOD_LATTICE", "LINEAR", True, [
        ("style", "Style", "E", "DIAMOND", [("DIAMOND", "Diamond", ""), ("KITE", "Kite", ""),
                                           ("PARALLELOGRAM", "Parallelogram", ""), ("TRAPEZOID", "Trapezoid", "")]),
        ("width", "Width", "D", 200.0, None), ("height", "Height", "D", 200.0, None),
        ("slant", "Slant", "A", 30.0, "style=PARALLELOGRAM|TRAPEZOID")], "A diamond, kite, parallelogram or trapezoid"),
    "helix": ("Helix", "FORCE_VORTEX", "CUBIC", False, [
        ("start_radius", "Start Radius", "D", 200.0, None), ("end_radius", "End Radius", "D", 200.0, None),
        ("start_angle", "Start Angle", "A", 0.0, None), ("end_angle", "End Angle", "A", 720.0, None),
        ("radius_bias", "Radius Bias", "P", 50.0, None), ("height", "Height", "D", 200.0, None),
        ("height_bias", "Height Bias", "P", 50.0, None), ("steps", "Steps", "I", 100, None)],
        "A spiral that winds up along its height"),
    "flower": ("Flower", "FREEZE", "BEZIER", True, [
        ("inner_radius", "Inner Radius", "D", 100.0, None), ("outer_radius", "Outer Radius", "D", 200.0, None),
        ("petals", "Petals", "I", 6, None)], "Round petals around a centre"),
    "cogwheel": ("Cogwheel", "PREFERENCES", "LINEAR", True, [
        ("teeth", "Teeth", "I", 12, None), ("root_radius", "Root Radius", "D", 175.0, None),
        ("tip_radius", "Tip Radius", "D", 200.0, None), ("tip_width", "Tip Narrowing", "P", 0.0, None),
        ("hole", "Centre Hole", "B", True, None), ("hole_radius", "Hole Radius", "D", 50.0, "hole")],
        "A gear outline with square teeth"),
    "profile": ("Profile", "MOD_BUILD", "LINEAR", True, [
        ("style", "Shape", "E", "H", [("H", "H", ""), ("L", "L", ""), ("T", "T", ""), ("U", "U", ""), ("Z", "Z", "")]),
        ("height", "Height", "D", 200.0, None), ("width", "Width", "D", 100.0, None),
        ("web", "Upright Thickness", "D", 20.0, None), ("flange", "Bar Thickness", "D", 20.0, None)],
        "The cross section of a beam: H, L, T, U or Z"),
    "cycloid": ("Cycloid", "IPO_BOUNCE", "CUBIC", False, [
        ("style", "Style", "E", "CYCLOID", [("CYCLOID", "Along a Line", "A wheel rolling along a straight line"),
                                            ("EPI", "Outside a Circle", "A wheel rolling around the outside of a circle"),
                                            ("HYPO", "Inside a Circle", "A wheel rolling around the inside of a circle")]),
        ("radius", "Circle Radius", "D", 200.0, "style=EPI|HYPO"), ("wheel", "Wheel Radius", "D", 50.0, None),
        ("pen", "Pen Distance", "D", 50.0, None), ("start_angle", "Start Angle", "A", 0.0, None),
        ("end_angle", "End Angle", "A", 720.0, None)], "The path of a point on a rolling wheel"),
    "formula": ("Formula", "DRIVER_TRANSFORM", "CUBIC", False, [
        ("x_t", "X(t)", "S", "100*t", None), ("y_t", "Y(t)", "S", "100*sin(t*pi)", None), ("z_t", "Z(t)", "S", "0", None),
        ("t_min", "t From", "F", -1.0, None), ("t_max", "t To", "F", 1.0, None), ("samples", "Samples", "I", 100, None)],
        "A curve from three formulas of t (in cm)"),
}
ANGLE_KINDS = {"A"}
PLAIN = "spline"                                 # kind of a plain curve tagged by Blenda's own buttons


def _attr(kind, name):
    return f"{kind}_{name}"


def shape_kind(ob):
    k = ob.get("b4d_type") if ob is not None else None
    return k if ob is not None and ob.type == "CURVE" and k in SHAPES else None


def is_spline(ob):
    return ob is not None and ob.type == "CURVE"


def _s(ob, kind, name):
    v = getattr(ob.b4d_spline, _attr(kind, name))
    return math.degrees(v) if next(r[2] for r in SHAPES[kind][4] if r[0] == name) in ANGLE_KINDS else v


# ------------------------------------------------------------------ shape maths (plane coordinates, cm)
def _v(x, y, z=0.0):
    return Vector((x, y, z))


def _corners(pts):
    z = Vector()
    return [(p, z.copy(), z.copy()) for p in pts]


def _arc(r, a0, a1, ry=None):
    """Bezier points along an arc from a0 to a1 (radians), split into pieces of at most a quarter turn."""
    ry = r if ry is None else ry
    n = max(1, int(math.ceil(abs(a1 - a0) / (math.pi / 2) - 1e-9)))
    step = (a1 - a0) / n
    k = 4.0 / 3.0 * math.tan(step / 4.0)
    out = []
    for i in range(n + 1):
        a = a0 + step * i
        t = _v(-r * math.sin(a) * k, ry * math.cos(a) * k)
        out.append((_v(r * math.cos(a), ry * math.sin(a)), -t if i > 0 else Vector(), t if i < n else Vector()))
    return out


def _ellipse(r, ry, backwards=False):
    """A closed ellipse of four Bezier points."""
    a = _arc(r, 2 * math.pi, 0, ry) if backwards else _arc(r, 0, 2 * math.pi, ry)
    return [(a[0][0], a[-1][1], a[0][2])] + a[1:-1]


def _round(corners, r):
    """A closed polygon whose corners are rounded with radius r."""
    if r <= 1e-6:
        return _corners(corners)
    n, out = len(corners), []
    for i, p in enumerate(corners):
        u, v = corners[i - 1] - p, corners[(i + 1) % n] - p
        lu, lv = u.length, v.length
        if lu < 1e-9 or lv < 1e-9:
            continue
        u.normalize()
        v.normalize()
        half = 0.5 * u.angle(v)
        if half < 1e-6 or half > math.pi / 2 - 1e-6:
            out += _corners([p])
            continue
        d = min(r / math.tan(half), lu * 0.5, lv * 0.5)
        rr = d * math.tan(half)
        h = 4.0 / 3.0 * math.tan((math.pi - 2.0 * half) / 4.0) * rr
        out.append((p + u * d, Vector(), -u * h))
        out.append((p + v * d, -v * h, Vector()))
    return out


def _bias(t, b):
    """Spacing along 0..1: 50 % even, lower crowds the start, higher the end."""
    b = min(max(b / 100.0, 1e-4), 1.0 - 1e-4)
    return t / ((1.0 / b - 2.0) * (1.0 - t) + 1.0)


def _ring_of(n, r, start=math.pi / 2):
    return [_v(r * math.cos(start + 2 * math.pi * i / n), r * math.sin(start + 2 * math.pi * i / n)) for i in range(n)]


def _circle(ob):
    k = "circle"
    r = _s(ob, k, "radius")
    ry = _s(ob, k, "radius_y") if _s(ob, k, "ellipse") else r
    out = [(_ellipse(r, ry), True)]
    if _s(ob, k, "ring"):
        ri = _s(ob, k, "inner_radius")
        out.append((_ellipse(ri, ri * ry / max(r, 1e-9), True), True))
    return out


def _rectangle(ob):
    k = "rectangle"
    w, h = _s(ob, k, "width") / 2.0, _s(ob, k, "height") / 2.0
    c = [_v(-w, h), _v(-w, -h), _v(w, -h), _v(w, h)]
    return [(_round(c, _s(ob, k, "radius")) if _s(ob, k, "rounding") else _corners(c), True)]


def _arc_shape(ob):
    k = "arc"
    style, r = _s(ob, k, "style"), _s(ob, k, "radius")
    a0, a1 = math.radians(_s(ob, k, "start_angle")), math.radians(_s(ob, k, "end_angle"))
    if abs(a1 - a0) < 1e-6:
        a1 = a0 + 1e-3
    outer = _arc(r, a0, a1)
    if style == "ARC":
        return [(outer, None)]
    if style == "SECTOR":
        return [(outer + _corners([_v(0, 0)]), True)]
    if style == "SEGMENT":
        return [(outer, True)]
    return [(outer + _arc(_s(ob, k, "inner_radius"), a1, a0), True)]


def _star(ob):
    k = "star"
    ri, ro, n = _s(ob, k, "inner_radius"), _s(ob, k, "outer_radius"), max(2, _s(ob, k, "points"))
    tw = _s(ob, k, "twist") / 100.0 * math.pi / n
    pts = []
    for i in range(n):
        a = math.pi / 2 + 2 * math.pi * i / n
        pts.append(_v(ro * math.cos(a), ro * math.sin(a)))
        b = a + math.pi / n + tw
        pts.append(_v(ri * math.cos(b), ri * math.sin(b)))
    return [(_corners(pts), True)]


def _nside(ob):
    k = "nside"
    c = _ring_of(max(3, _s(ob, k, "sides")), _s(ob, k, "radius"))
    return [(_round(c, _s(ob, k, "corner_radius")) if _s(ob, k, "rounding") else _corners(c), True)]


def _fourside(ob):
    k = "fourside"
    style, a, b = _s(ob, k, "style"), _s(ob, k, "width") / 2.0, _s(ob, k, "height") / 2.0
    s = math.tan(math.radians(min(max(_s(ob, k, "slant"), -80.0), 80.0)))
    if style == "DIAMOND":
        pts = [_v(0, b), _v(-a, 0), _v(0, -b), _v(a, 0)]
    elif style == "KITE":
        pts = [_v(0, b), _v(-a, b * 0.4), _v(0, -b), _v(a, b * 0.4)]
    elif style == "PARALLELOGRAM":
        pts = [_v(-a + b * s, b), _v(-a - b * s, -b), _v(a - b * s, -b), _v(a + b * s, b)]
    else:
        pts = [_v(-a + 2 * b * s, b), _v(-a, -b), _v(a, -b), _v(a - 2 * b * s, b)]
    return [(_corners(pts), True)]


def _helix(ob):
    k = "helix"
    r0, r1 = _s(ob, k, "start_radius"), _s(ob, k, "end_radius")
    a0, a1 = math.radians(_s(ob, k, "start_angle")), math.radians(_s(ob, k, "end_angle"))
    h, n = _s(ob, k, "height"), max(2, _s(ob, k, "steps"))
    rb, hb = _s(ob, k, "radius_bias"), _s(ob, k, "height_bias")
    pts = []
    for i in range(n + 1):
        t = i / n
        a = a0 + (a1 - a0) * t
        r = r0 + (r1 - r0) * _bias(t, rb)
        pts.append(_v(r * math.cos(a), r * math.sin(a), h * _bias(t, hb)))
    return [(_corners(pts), None)]


def _flower(ob):
    k = "flower"
    ri, ro, n = _s(ob, k, "inner_radius"), _s(ob, k, "outer_radius"), max(1, _s(ob, k, "petals"))
    step = 2 * math.pi / n
    w = 1.2 * ro * math.tan(step / 2.0)
    out = []
    for i in range(n):
        a = math.pi / 2 + step * i
        t = _v(-math.sin(a), math.cos(a)) * w
        out.append((_v(ro * math.cos(a), ro * math.sin(a)), -t, t))
        b = a + step / 2.0
        out.append((_v(ri * math.cos(b), ri * math.sin(b)), Vector(), Vector()))
    return [(out, True)]


def _cogwheel(ob):
    k = "cogwheel"
    n = max(3, _s(ob, k, "teeth"))
    rr, rt = _s(ob, k, "root_radius"), _s(ob, k, "tip_radius")
    narrow = min(max(_s(ob, k, "tip_width") / 100.0, 0.0), 1.0)
    step = 2 * math.pi / n
    pts = []
    for i in range(n):                            # each tooth: up the flank, across the tip, down, along the root
        a = math.pi / 2 + step * i
        tip = 0.25 * step * (1.0 - narrow)
        for ang, r in ((a - 0.25 * step, rr), (a - tip, rt), (a + tip, rt), (a + 0.25 * step, rr)):
            pts.append(_v(r * math.cos(ang), r * math.sin(ang)))
    out = [(_corners(pts), True)]
    hr = _s(ob, k, "hole_radius")
    if _s(ob, k, "hole") and hr > 1e-6:
        out.append((_ellipse(hr, hr, True), True))
    return out


def _profile(ob):
    k = "profile"
    style = _s(ob, k, "style")
    ha, hb = _s(ob, k, "height") / 2, _s(ob, k, "width") / 2
    s, t = min(_s(ob, k, "web"), hb), min(_s(ob, k, "flange"), ha)
    hs, ht = s / 2, t / 2
    outlines = {
        "H": [(-hb, ha), (-hb, -ha), (-hb + s, -ha), (-hb + s, -ht), (hb - s, -ht), (hb - s, -ha), (hb, -ha), (hb, ha),
              (hb - s, ha), (hb - s, ht), (-hb + s, ht), (-hb + s, ha)],
        "L": [(-hb, ha), (-hb, -ha), (hb, -ha), (hb, -ha + t), (-hb + s, -ha + t), (-hb + s, ha)],
        "T": [(-hb, ha), (-hb, ha - t), (-hs, ha - t), (-hs, -ha), (hs, -ha), (hs, ha - t), (hb, ha - t), (hb, ha)],
        "U": [(-hb, ha), (-hb, -ha), (hb, -ha), (hb, ha), (hb - s, ha), (hb - s, -ha + t), (-hb + s, -ha + t), (-hb + s, ha)],
        "Z": [(-hs, ha), (-hs, -ha + t), (-hb, -ha + t), (-hb, -ha), (hs, -ha), (hs, ha - t), (hb, ha - t), (hb, ha)],
    }
    return [(_corners([_v(x, y) for x, y in outlines[style]]), True)]


def _cycloid(ob):
    k = "cycloid"
    style, R, r, p = _s(ob, k, "style"), _s(ob, k, "radius"), max(1e-3, _s(ob, k, "wheel")), _s(ob, k, "pen")
    t0, t1 = math.radians(_s(ob, k, "start_angle")), math.radians(_s(ob, k, "end_angle"))
    n = max(8, min(4000, int(abs(t1 - t0) / math.radians(5))))
    pts = []
    for i in range(n + 1):
        t = t0 + (t1 - t0) * i / n
        if style == "CYCLOID":
            pts.append(_v(r * t - p * math.sin(t), r - p * math.cos(t)))
        elif style == "EPI":
            q = (R + r) / r
            pts.append(_v((R + r) * math.cos(t) - p * math.cos(q * t), (R + r) * math.sin(t) - p * math.sin(q * t)))
        else:
            q = (R - r) / r
            pts.append(_v((R - r) * math.cos(t) + p * math.cos(q * t), (R - r) * math.sin(t) - p * math.sin(q * t)))
    return [(_corners(pts), None)]


FUNCS = {"sin": math.sin, "cos": math.cos, "tan": math.tan, "asin": math.asin, "acos": math.acos, "atan": math.atan,
         "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh, "sqrt": math.sqrt, "exp": math.exp, "ln": math.log,
         "log": math.log10, "abs": abs, "pi": math.pi, "e": math.e, "floor": math.floor, "ceil": math.ceil,
         "min": min, "max": max}


def compile_formula(text):
    """A formula of t as compiled Python, or None. Only t, numbers, + - * / ^ ( ) and the functions in FUNCS
    are accepted (any letter case), so nothing else can run."""
    src = (text or "0").replace("^", "**")
    if re.search(r"[^A-Za-z0-9_+\-*/(). ,]", src) or "__" in src:
        return None
    names = set(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", src))
    if any(n.lower() not in FUNCS and n.lower() != "t" for n in names):
        return None
    src = re.sub(r"[A-Za-z_][A-Za-z_0-9]*", lambda m: m.group(0).lower(), src)
    try:
        return compile(src, "<formula>", "eval")
    except SyntaxError:
        return None


def _formula(ob):
    k = "formula"
    codes = [compile_formula(_s(ob, k, n)) for n in ("x_t", "y_t", "z_t")]
    t0, t1, n = _s(ob, k, "t_min"), _s(ob, k, "t_max"), max(2, min(5000, _s(ob, k, "samples")))
    pts = []
    for i in range(n):
        t = t0 + (t1 - t0) * i / (n - 1)
        env = {"__builtins__": {}, **FUNCS, "t": t}
        xyz = []
        for c in codes:
            try:
                xyz.append(float(eval(c, env)) if c else 0.0)
            except (ArithmeticError, ValueError, TypeError):
                xyz.append(0.0)
        pts.append(Vector(xyz))
    return [(_corners(pts), None)]


BUILD = {"circle": _circle, "rectangle": _rectangle, "arc": _arc_shape, "star": _star, "nside": _nside,
         "fourside": _fourside, "helix": _helix, "flower": _flower, "cogwheel": _cogwheel, "profile": _profile,
         "cycloid": _cycloid, "formula": _formula}


# ------------------------------------------------------------------ writing Blender splines
def _to_blender(v, plane):
    """A plane point (cm) to Blender metres. Blenda shows Y up: shown (x, y, z) is Blender (x, z, y)."""
    a, b, c = v.x, v.y, v.z
    if plane == "ZY":
        x, y, z = -c, b, a
    elif plane == "XZ":
        x, y, z = a, c, -b          # lying flat: a shape's height (a helix) rises up, not down into the floor
    else:
        x, y, z = a, b, c
    return Vector((x * SCALE, z * SCALE, y * SCALE))


def _akima(P, closed):
    """Akima slopes: each point's tangent leans towards the flatter neighbouring chord, so the curve never overshoots."""
    n = len(P)
    if n < 2:
        return [Vector()] * n
    if closed:
        m = [P[(i + 1) % n] - P[i] for i in range(n)]

        def M(i):
            return m[i % n]
    else:
        m = [P[i + 1] - P[i] for i in range(n - 1)]
        m = [2 * m[0] - m[1] if n > 2 else m[0], m[0]] + m + [m[-1], 2 * m[-1] - m[-2] if n > 2 else m[-1]]

        def M(i):
            return m[i + 2]
    out = []
    for i in range(n):
        m0, m1, m2, m3 = M(i - 2), M(i - 1), M(i), M(i + 1)
        w1, w2 = (m3 - m2).length, (m1 - m0).length
        out.append((m1 + m2) * 0.5 if w1 + w2 < 1e-9 else (w1 * m1 + w2 * m2) / (w1 + w2))
    return out


def resolution(ob):
    return max(1, int(ob.b4d_spline.points) + 1)


def write(cu, segs, typ, natural, res, cap_dense=True):
    """Write segs [(points [(co, left, right)] in Blender space, closed)] into curve cu as Type typ."""
    cu.splines.clear()
    for pts, closed in segs:
        if len(pts) < 2:
            continue
        P = [p for p, _l, _r in pts]
        r = min(res, 4) if cap_dense and len(P) > 32 else res        # sampled shapes already carry their detail
        if typ == "BSPLINE":
            sp = cu.splines.new("NURBS")
            sp.points.add(len(P) - 1)
            for i, co in enumerate(P):
                sp.points[i].co = (co.x, co.y, co.z, 1.0)
            sp.order_u = min(4, len(P))
            sp.use_endpoint_u = not closed
            sp.use_cyclic_u = closed
            sp.resolution_u = r
            continue
        sp = cu.splines.new("BEZIER")
        sp.bezier_points.add(len(P) - 1)
        ak = _akima(P, closed) if typ == "AKIMA" else None
        smooth_by_auto = typ == "CUBIC" or (typ == "BEZIER" and natural == "CUBIC")
        for i, (co, l, rt) in enumerate(pts):
            bp = sp.bezier_points[i]
            bp.co = co
            if smooth_by_auto:
                bp.handle_left_type = bp.handle_right_type = "AUTO"
            elif typ == "AKIMA":
                bp.handle_left_type = bp.handle_right_type = "FREE"
                bp.handle_left, bp.handle_right = co - ak[i] / 3.0, co + ak[i] / 3.0
            elif l.length < 1e-9 and rt.length < 1e-9:     # a corner (Linear shapes keep their round parts)
                bp.handle_left_type = bp.handle_right_type = "VECTOR"
            else:
                bp.handle_left_type = bp.handle_right_type = "FREE"
                bp.handle_left = co + l if l.length > 1e-9 else co
                bp.handle_right = co + rt if rt.length > 1e-9 else co
        sp.use_cyclic_u = closed
        sp.resolution_u = r
    cu.resolution_u = res


def rebuild(ob):
    """Write a shape object's splines from its settings."""
    kind = shape_kind(ob)
    if kind is None:
        return
    s = ob.b4d_spline
    try:
        segs = BUILD[kind](ob)
    except (ValueError, ZeroDivisionError, OverflowError):
        segs = []
    natural, always = SHAPES[kind][2], SHAPES[kind][3]
    out = []
    for pts, closed in segs:
        if s.reverse:
            pts = [(p, r, l) for p, l, r in reversed(pts)]
        closed = (bool(s.closed) if not always else True) if closed is None else closed
        conv = []
        for p, l, r in pts:
            co = _to_blender(p, s.plane)
            conv.append((co, _to_blender(l, s.plane), _to_blender(r, s.plane)))
        out.append((conv, closed))
    typ = s.type
    if typ == "LINEAR" and natural != "LINEAR":
        out = [([(co, Vector(), Vector()) for co, _l, _r in pts], c) for pts, c in out]
    write(ob.data, out, typ, natural, resolution(ob))
    ob.data["b4d_spline"] = SHAPE
    ob.data.update_tag()
    ob.update_tag()


# ------------------------------------------------------------------ plain curves: Type, Close, Intermediate Points
def _plain_points(sp):
    if sp.type == "BEZIER":
        return [bp.co.copy() for bp in sp.bezier_points]
    return [Vector(p.co[:3]) for p in sp.points]


def plain_type(cu):
    sps = list(cu.splines)
    if not sps:
        return "BEZIER"
    sp = sps[0]
    if sp.type == "NURBS":
        return "BSPLINE"
    if sp.type == "POLY":
        return "LINEAR"
    types = {t for bp in sp.bezier_points for t in (bp.handle_left_type, bp.handle_right_type)}
    if types == {"VECTOR"}:
        return "LINEAR"
    if types == {"AUTO"}:
        return "CUBIC"
    if types == {"FREE"} and cu.get("b4d_akima"):
        return "AKIMA"
    return "BEZIER"


def _stash(cu):
    """Keep every Bezier point's handles so they come back when Type returns to Bezier."""
    data = []
    for sp in cu.splines:
        if sp.type != "BEZIER":
            return
        data.append([[*bp.co, *bp.handle_left, *bp.handle_right, bp.handle_left_type, bp.handle_right_type]
                     for bp in sp.bezier_points])
    cu["b4d_handles"] = json.dumps(data)


def _unstash(cu):
    try:
        data = json.loads(cu.get("b4d_handles", ""))
    except ValueError:
        return False
    sps = list(cu.splines)
    if len(data) != len(sps) or any(sp.type != "BEZIER" or len(d) != len(sp.bezier_points) for sp, d in zip(sps, data)):
        return False
    for sp, d in zip(sps, data):
        for bp, row in zip(sp.bezier_points, d):
            if (Vector(row[0:3]) - bp.co).length > 1e-5:
                return False
    for sp, d in zip(sps, data):
        for bp, row in zip(sp.bezier_points, d):
            bp.handle_left_type, bp.handle_right_type = "FREE", "FREE"
            bp.handle_left, bp.handle_right = row[3:6], row[6:9]
            bp.handle_left_type, bp.handle_right_type = row[9], row[10]
    return True


def set_plain_type(ob, typ):
    cu = ob.data
    old = plain_type(cu)
    if typ == old:
        return
    if old == "BEZIER":
        _stash(cu)
    segs = [([(p, Vector(), Vector()) for p in _plain_points(sp)], sp.use_cyclic_u) for sp in cu.splines]
    res = cu.resolution_u
    target = "CUBIC" if typ == "BEZIER" else typ
    write(cu, segs, target, "LINEAR", res, cap_dense=False)
    if "b4d_akima" in cu:
        del cu["b4d_akima"]
    if typ == "AKIMA":
        cu["b4d_akima"] = True
    if typ == "BEZIER" and not _unstash(cu):
        cu.update_tag()
        for sp in cu.splines:                     # smooth handles the person can now pull independently
            for bp in sp.bezier_points:
                bp.handle_left_type = bp.handle_right_type = "ALIGNED"
    cu.update_tag()


# ------------------------------------------------------------------ settings (one property group per object)
def _update(self, context):
    ob = self.id_data
    if shape_kind(ob):
        rebuild(ob)


def _type_get(self):
    ob = self.id_data
    if shape_kind(ob) or ob.type != "CURVE":
        return self.get("type_v", 4)
    return [t[0] for t in TYPES].index(plain_type(ob.data))


def _type_set(self, value):
    ob = self.id_data
    self["type_v"] = value
    if shape_kind(ob):
        rebuild(ob)
    elif ob.type == "CURVE":
        set_plain_type(ob, TYPES[value][0])


def _closed_get(self):
    ob = self.id_data
    if shape_kind(ob) or ob.type != "CURVE":
        return bool(self.get("closed_v", False))
    return any(sp.use_cyclic_u for sp in ob.data.splines)


def _closed_set(self, value):
    ob = self.id_data
    self["closed_v"] = bool(value)
    if shape_kind(ob):
        rebuild(ob)
    elif ob.type == "CURVE":
        for sp in ob.data.splines:
            sp.use_cyclic_u = bool(value)
        ob.data.update_tag()


def _points_get(self):
    ob = self.id_data
    if shape_kind(ob) or ob.type != "CURVE":
        return int(self.get("points_v", 11))
    return max(0, ob.data.resolution_u - 1)


def _points_set(self, value):
    ob = self.id_data
    self["points_v"] = int(value)
    if shape_kind(ob):
        rebuild(ob)
    elif ob.type == "CURVE":
        ob.data.resolution_u = max(1, int(value) + 1)
        for sp in ob.data.splines:
            sp.resolution_u = ob.data.resolution_u


def _prop(name, label, typ, default, extra, tip=""):
    if typ == "D":
        return bpy.props.FloatProperty(name=label, default=default, min=0.0, soft_max=2000.0, step=100, precision=1,
                                       description=tip or label + " in centimetres", update=_update)
    if typ == "F":
        return bpy.props.FloatProperty(name=label, default=default, precision=3, description=tip or label, update=_update)
    if typ == "A":
        return bpy.props.FloatProperty(name=label, default=math.radians(default), subtype="ANGLE",
                                       description=tip or label, update=_update)
    if typ == "P":
        return bpy.props.FloatProperty(name=label, default=default, min=-100.0 if name == "twist" else 0.0, max=100.0,
                                       subtype="PERCENTAGE", description=tip or label, update=_update)
    if typ == "I":
        lo = {"points": 2, "sides": 3, "teeth": 3, "petals": 1, "steps": 2, "samples": 2}.get(name, 0)
        return bpy.props.IntProperty(name=label, default=default, min=lo, soft_max=500, max=5000,
                                     description=tip or label, update=_update)
    if typ == "B":
        return bpy.props.BoolProperty(name=label, default=default, description=tip or label, update=_update)
    if typ == "E":
        return bpy.props.EnumProperty(name=label, items=extra, default=default, description=tip or label, update=_update)
    return bpy.props.StringProperty(name=label, default=default, description=tip or label, update=_update)


def _settings_class():
    ann = {
        "type": bpy.props.EnumProperty(name="Type", items=TYPES, get=_type_get, set=_type_set,
                                       description="How the curve runs between its points"),
        "closed": bpy.props.BoolProperty(name="Close Spline", get=_closed_get, set=_closed_set,
                                         description="Join the last point back to the first"),
        "points": bpy.props.IntProperty(name="Intermediate Points", min=0, soft_max=64, max=1024, get=_points_get,
                                        set=_points_set, description="Extra points worked out between each pair of points"),
        "plane": bpy.props.EnumProperty(name="Plane", items=PLANES, default="XY", update=_update,
                                        description="Which plane the shape lies in"),
        "reverse": bpy.props.BoolProperty(name="Reverse", default=False, update=_update,
                                          description="Run the spline the other way round"),
    }
    for kind, (_label, _icon, _nat, _cl, rows, _tip) in SHAPES.items():
        for name, label, typ, default, extra, *_ in rows:
            ann[_attr(kind, name)] = _prop(name, label, typ, default, extra if typ == "E" else None)
    return type("BLENDA4D_PG_spline", (bpy.types.PropertyGroup,), {"__annotations__": ann})


SETTINGS = _settings_class()


# ------------------------------------------------------------------ creating
def add_shape(context, kind, location=None):
    label, _icon, natural, _always, _rows, _tip = SHAPES[kind]
    cu = bpy.data.curves.new(label, "CURVE")
    cu.dimensions = "3D"
    cu.fill_mode = "FULL"
    ob = bpy.data.objects.new(label, cu)
    context.collection.objects.link(ob)
    ob["b4d_type"] = kind
    from .primitives import tidy_name
    tidy_name(ob)
    ob.location = context.scene.cursor.location if location is None else location
    s = ob.b4d_spline
    s["type_v"] = [t[0] for t in TYPES].index(natural)
    s["closed_v"] = False
    s["points_v"] = 11
    rebuild(ob)
    return ob


def _creator(kind):
    return lambda context: add_shape(context, kind)


class BLENDA4D_OT_spline_make_editable(bpy.types.Operator):
    """Turn this spline shape into a plain spline whose points can be edited"""
    bl_idname = "blenda4d.spline_make_editable"
    bl_label = "Make Editable"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return shape_kind(context.view_layer.objects.active) is not None

    def execute(self, context):
        ob = context.view_layer.objects.active
        s = ob.b4d_spline
        keep_type, keep_points = s.type, s.points
        del ob["b4d_type"]
        if "b4d_spline" in ob.data:
            del ob.data["b4d_spline"]
        if keep_type == "AKIMA":
            ob.data["b4d_akima"] = True
        ob.data.resolution_u = max(1, keep_points + 1)
        for sp in ob.data.splines:
            sp.resolution_u = ob.data.resolution_u
        return {"FINISHED"}


# ------------------------------------------------------------------ Attribute Manager pages
def _active_when(ob, kind, cond):
    """cond 'switch' or 'setting=A|B': is the row's switch on?"""
    if not cond:
        return True
    name, _, values = cond.partition("=")
    v = getattr(ob.b4d_spline, _attr(kind, name))
    return v in values.split("|") if values else bool(v)


def _spline_rows(col, ob, always_closed):
    s = ob.b4d_spline
    col.prop(s, "type")
    if not always_closed:                        # a shape that is always closed has no use for the switch
        col.prop(s, "closed")
    row = col.row()
    row.active = s.type != "LINEAR" or _has_curves(ob.data)       # straight lines get no points in between
    row.prop(s, "points")


def _has_curves(cu):
    return any(sp.type != "BEZIER" or any(bp.handle_left_type != "VECTOR" or bp.handle_right_type != "VECTOR"
                                          for bp in sp.bezier_points) for sp in cu.splines)


def page_shape(col, ob):
    kind = shape_kind(ob)
    if kind is None:
        return page_spline(col, ob)
    s = ob.b4d_spline
    for name, label, typ, _d, extra in SHAPES[kind][4]:
        row = col.row()
        cond = extra if typ != "E" else None
        row.active = _active_when(ob, kind, cond)
        row.prop(s, _attr(kind, name), text=label)
        if typ == "S" and compile_formula(getattr(s, _attr(kind, name))) is None:
            col.label(text="Not a formula of t: drawn as 0", icon="ERROR")
    col.separator()
    col.prop(s, "plane")
    col.prop(s, "reverse")
    col.separator()
    _spline_rows(col, ob, SHAPES[kind][3])
    col.separator()
    col.operator("blenda4d.spline_make_editable", icon="CURVE_DATA")


def page_spline(col, ob):
    """The page of a plain curve."""
    if ob.type != "CURVE":
        col.label(text="Not a spline")
        return
    cu = ob.data
    n = sum(len(sp.bezier_points) if sp.type == "BEZIER" else len(sp.points) for sp in cu.splines)
    col.label(text=f"Splines: {len(cu.splines)}    Points: {n}")
    _spline_rows(col, ob, False)


# ------------------------------------------------------------------ for other modules
def sample(ob, depsgraph=None):
    """The evaluated curve of any curve object as [(points, closed)]: one list of object-space Vectors per spline,
    with the intermediate points included (a closed spline does not repeat its first point)."""
    if ob is None or ob.type not in {"CURVE", "FONT"}:
        return []
    dg = depsgraph or bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    cu = ev.data if ev.type == "CURVE" else None
    if cu is not None and (cu.bevel_depth > 0 or cu.extrude > 0 or cu.bevel_object is not None):
        return _sample_math(cu)                  # a bevelled curve meshes as a tube; work the line out directly
    try:
        me = ev.to_mesh()
    except RuntimeError:
        return []
    try:
        return _chains(me)
    finally:
        ev.to_mesh_clear()


def _chains(me):
    co = [v.co.copy() for v in me.vertices]
    nb = {i: [] for i in range(len(co))}
    for e in me.edges:
        a, b = e.vertices
        nb[a].append(b)
        nb[b].append(a)
    seen, out = set(), []
    starts = [i for i in nb if len(nb[i]) == 1] + list(nb)
    for s in starts:
        if s in seen:
            continue
        chain, prev, cur = [s], None, s
        seen.add(s)
        while True:
            nxt = next((j for j in nb[cur] if j != prev and j not in seen), None)
            if nxt is None:
                break
            chain.append(nxt)
            seen.add(nxt)
            prev, cur = cur, nxt
        closed = len(chain) > 2 and s in nb[chain[-1]]
        if len(chain) > 1:
            out.append(([co[i] for i in chain], closed))
    return out


def _sample_math(cu):
    from mathutils.geometry import interpolate_bezier
    out = []
    for sp in cu.splines:
        res = max(1, sp.resolution_u)
        if sp.type != "BEZIER":
            out.append(([Vector(p.co[:3]) for p in sp.points], sp.use_cyclic_u))
            continue
        bps = list(sp.bezier_points)
        pts = []
        pairs = list(zip(bps, bps[1:])) + ([(bps[-1], bps[0])] if sp.use_cyclic_u and len(bps) > 1 else [])
        for a, b in pairs:
            seg = interpolate_bezier(a.co, a.handle_right, b.handle_left, b.co, res + 1)
            pts += seg[:-1]
        if not sp.use_cyclic_u and bps:
            pts.append(bps[-1].co.copy())
        out.append((pts, sp.use_cyclic_u))
    return out


# ------------------------------------------------------------------ animation: keyed settings redraw the shape
@bpy.app.handlers.persistent
def _on_frame(scene, *_args):
    for ob in scene.objects:
        if shape_kind(ob) and ob.animation_data and ob.animation_data.action:
            if _keyed(ob):
                rebuild(ob)


def _keyed(ob):
    ad = ob.animation_data
    try:
        curves = ad.action.fcurves
    except AttributeError:                       # layered actions keep their curves in channel bags
        curves = [fc for layer in ad.action.layers for strip in layer.strips
                  for bag in getattr(strip, "channelbags", ()) for fc in bag.fcurves]
    return any(fc.data_path.startswith("b4d_spline.") for fc in curves)


# ------------------------------------------------------------------ register
ORDER = ("circle", "rectangle", "arc", "nside", "star", "flower", "cogwheel", "helix", "fourside", "profile",
         "cycloid", "formula")


def register():
    bpy.utils.register_class(SETTINGS)
    bpy.utils.register_class(BLENDA4D_OT_spline_make_editable)
    bpy.types.Object.b4d_spline = bpy.props.PointerProperty(type=SETTINGS)
    kinds.add(PLAIN, "Spline", "CURVE_BEZCURVE", tabs=[("OBJECT", "Object")], pages={"OBJECT": page_spline},
              titles={"OBJECT": "Spline"})
    for kind in ORDER:
        label, icon, _n, _c, _rows, tip = SHAPES[kind]
        kinds.add(kind, label, icon, create=_creator(kind), tabs=[("OBJECT", "Object")], pages={"OBJECT": page_shape},
                  titles={"OBJECT": label + " Spline"}, describe=tip)
        kinds.create_button("splines", label, kind)
        kinds.menu_item("Create", label, kind)
    if _on_frame not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(_on_frame)


def unregister():
    if _on_frame in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(_on_frame)
    for kind in (PLAIN, *ORDER):
        kinds.KINDS.pop(kind, None)
    del bpy.types.Object.b4d_spline
    bpy.utils.unregister_class(BLENDA4D_OT_spline_make_editable)
    bpy.utils.unregister_class(SETTINGS)
