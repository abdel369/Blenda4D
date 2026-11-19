# Headless test of the splines module: every shape builds a real curve, every setting changes it, plain curves convert
# and come back, and sample() hands other modules the evaluated points.
#   Blender -b --factory-startup --python tools/tests/splines_engine.py
import math
import os
import sys
import traceback

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from blenda4d import kinds, splines  # noqa: E402

bpy.utils.register_class(kinds.BLENDA4D_OT_add_kind)
splines.register()
fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)
        print("FAIL", msg, flush=True)


def shape(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = splines.sample(ob, dg)
    flat = [tuple(round(c, 5) for c in p) for chain, _c in pts for p in chain]
    closed = tuple(c for _p, c in pts)
    return flat, closed


def bounds(flat):
    return [max(p[i] for p in flat) - min(p[i] for p in flat) for i in range(3)] if flat else [0, 0, 0]


for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)

for kind in splines.ORDER:
    try:
        bpy.ops.blenda4d.add_kind(kind=kind)
        ob = bpy.context.view_layer.objects.active
        check(ob is not None and ob.type == "CURVE" and ob["b4d_type"] == kind, f"{kind}: not a tagged curve")
        base, cl = shape(ob)
        check(len(base) > 3, f"{kind}: only {len(base)} points")
        print(kind, "points", len(base), "closed", cl, "size cm", [round(b * 100, 1) for b in bounds(base)], flush=True)
        s = ob.b4d_spline
        for name, label, typ, default, extra in splines.SHAPES[kind][4]:
            attr = splines._attr(kind, name)
            # switch on whatever greys this row out, so a change can show
            if typ != "E" and extra:
                sw, _, vals = extra.partition("=")
                swa = splines._attr(kind, sw)
                setattr(s, swa, vals.split("|")[-1] if vals else True)
            if kind == "helix" and name.endswith("bias"):
                s.helix_end_radius = 80.0            # bias only shows when the radius changes along the way
            before, _ = shape(ob)
            old = getattr(s, attr)
            if typ == "B":
                setattr(s, attr, not old)
            elif typ == "E":
                items = [i[0] for i in extra]
                setattr(s, attr, items[(items.index(old) + 1) % len(items)])
            elif typ == "S":
                setattr(s, attr, "50*cos(t*pi)+t^2")
            elif typ == "I":
                setattr(s, attr, old + 3)
            elif typ == "A":
                setattr(s, attr, old + math.radians(40))
            elif typ == "P":
                setattr(s, attr, 20.0 if old > 30 else 70.0)
            else:
                setattr(s, attr, old * 1.5 + 10)
            after, _ = shape(ob)
            check(after != before, f"{kind}.{name} ({label}) changes nothing")
            setattr(s, attr, old)
        for attr, val in (("plane", "XZ"), ("reverse", True), ("points", 3)):
            if attr == "points" and s.type == "LINEAR":
                s.type = "CUBIC"                     # the row is greyed for straight lines
            before, _ = shape(ob)
            setattr(s, attr, val)
            check(shape(ob)[0] != before, f"{kind}.{attr} changes nothing")
        for t in ("LINEAR", "CUBIC", "AKIMA", "BSPLINE", "BEZIER"):
            s.type = t
            f, _ = shape(ob)
            check(len(f) >= 2 and s.type == t, f"{kind}: type {t} gives {len(f)} points, reads {s.type}")
        if not splines.SHAPES[kind][3]:
            s.closed = True
            check(any(shape(ob)[1]), f"{kind}: Close Spline did not close")
    except Exception:
        traceback.print_exc()
        fails.append(kind + " crashed")

# the default circle: radius 200 cm, upright facing the front (Blender XZ)
bpy.ops.blenda4d.add_kind(kind="circle")
c = bpy.context.view_layer.objects.active
b = bounds(shape(c)[0])
check(abs(b[0] - 4.0) < 0.02 and abs(b[2] - 4.0) < 0.02 and b[1] < 1e-4, f"circle bounds {b}")
check(len(c.data.splines) == 1 and c.data.splines[0].use_cyclic_u, "circle not one closed spline")

# formula that tries anything other than maths is refused
check(splines.compile_formula("__import__('os')") is None, "formula accepted an import")
check(splines.compile_formula("open('x')") is None, "formula accepted open")
check(splines.compile_formula("100*Sin(t*PI)") is not None, "formula refused sin")

# animation: a keyed setting redraws on frame change
bpy.ops.blenda4d.add_kind(kind="star")
st = bpy.context.view_layer.objects.active
st.b4d_spline.star_outer_radius = 200.0
st.keyframe_insert('b4d_spline.star_outer_radius', frame=1)
st.b4d_spline.star_outer_radius = 400.0
st.keyframe_insert('b4d_spline.star_outer_radius', frame=10)
bpy.context.scene.frame_set(1)
w1 = bounds(shape(st)[0])[0]
bpy.context.scene.frame_set(10)
w10 = bounds(shape(st)[0])[0]
check(w10 > w1 * 1.5, f"animated star did not grow: {w1} -> {w10}")

# Make Editable
bpy.ops.blenda4d.add_kind(kind="rectangle")
r = bpy.context.view_layer.objects.active
before = shape(r)[0]
bpy.ops.blenda4d.spline_make_editable()
check("b4d_type" not in r and shape(r)[0] == before, "make editable changed the shape or kept the kind")

# plain Blender curve: type round trip keeps the Bezier handles
bpy.ops.curve.primitive_bezier_curve_add()
p = bpy.context.view_layer.objects.active
hl = [tuple(bp.handle_left) for bp in p.data.splines[0].bezier_points]
check(p.b4d_spline.type == "BEZIER", f"plain curve reads {p.b4d_spline.type}")
for t in ("LINEAR", "CUBIC", "AKIMA", "BSPLINE"):
    p.b4d_spline.type = t
    check(p.b4d_spline.type == t, f"plain curve: set {t}, reads {p.b4d_spline.type}")
p.b4d_spline.type = "BEZIER"
hl2 = [tuple(bp.handle_left) for bp in p.data.splines[0].bezier_points]
check(all((abs(a - b) < 1e-5) for x, y in zip(hl, hl2) for a, b in zip(x, y)), f"handles lost {hl} {hl2}")
p.b4d_spline.closed = True
check(p.data.splines[0].use_cyclic_u and p.b4d_spline.closed, "plain close")
n0 = len(shape(p)[0])
p.b4d_spline.points = 30
check(p.data.resolution_u == 31 and len(shape(p)[0]) > n0, "plain intermediate points")
# a bevelled curve still samples as a line
p.data.bevel_depth = 0.1
check(len(splines.sample(p)) == 1 and splines.sample(p)[0][1], "bevelled sample")

print("SPLINES TEST", "FAILED %d" % len(fails) if fails else "OK", flush=True)
sys.exit(1 if fails else 0)
