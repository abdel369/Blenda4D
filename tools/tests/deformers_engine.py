# Headless test of the deformers module: every deformer bends the object it sits under, every Attribute Manager row
# changes the result, the deformer reaches siblings under a Null, the box takes the deformation, copies get their own
# settings, the check mark switches it off, and deleting a deformer gives the object back.
#   Blender -b --factory-startup --python tools/tests/deformers_engine.py
import math
import os
import sys
import traceback

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from blenda4d import deformers as D, kinds  # noqa: E402

bpy.utils.register_class(kinds.BLENDA4D_OT_add_kind)
D.register()
fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)
        print("FAIL", msg, flush=True)
    else:
        print("ok  ", msg, flush=True)


def update():
    for _ in range(2):
        D.sync(bpy.context.scene)
        bpy.context.view_layer.update()


def points(ob):
    update()
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    out = [tuple(round(c, 5) for c in v.co) for v in me.vertices]
    ev.to_mesh_clear()
    return out


def clear():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)


def column(name="Column"):
    """A tall subdivided box so bends show."""
    bpy.ops.mesh.primitive_cube_add(size=1)
    ob = bpy.context.object
    ob.name = name
    ob.scale = (0.5, 0.5, 2.0)
    bpy.ops.object.transform_apply(scale=True)
    m = ob.modifiers.new("Sub", "SUBDIVIDE" if False else "SUBSURF")
    m.subdivision_type = "SIMPLE"
    m.levels = 3
    bpy.ops.object.modifier_apply(modifier=m.name)
    return ob


MENUS = ("b4d_def_mode", "b4d_def_origin", "b4d_def_wrap_mode", "b4d_def_shape", "b4d_def_along", "b4d_def_interp")


def setv(ob, key, v):
    """Set a page row the way the field does: menus through their property, numbers on the custom property."""
    if key in MENUS:
        setattr(ob, key, v)
    else:
        ob[key] = list(v) if isinstance(v, tuple) else v
        ob.update_tag()


def create(kind, parent):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    if parent is not None:
        parent.select_set(True)
        bpy.context.view_layer.objects.active = parent
    else:
        bpy.context.view_layer.objects.active = None
    bpy.ops.blenda4d.add_kind(kind=kind)
    return bpy.context.view_layer.objects.active


ROWS = {      # the page rows of each kind and a value that must change the shape (applied after the base settings)
    "bend": [("b4d_def_angle", math.radians(90)), ("b4d_def_direction", math.radians(90)), ("b4d_def_keep", False),
             ("b4d_def_origin", "TOP"), ("b4d_def_size", (250.0, 250.0, 100.0)), ("b4d_def_mode", "UNLIMITED")],
    "twist": [("b4d_def_angle", math.radians(120)), ("b4d_def_size", (40.0, 40.0, 100.0)), ("b4d_def_mode", "WITHIN")],
    "taper": [("b4d_def_strength", 60.0), ("b4d_def_curvature", 100.0), ("b4d_def_fillet", True),
              ("b4d_def_size", (250.0, 250.0, 100.0)), ("b4d_def_mode", "WITHIN")],
    "bulge": [("b4d_def_strength", 60.0), ("b4d_def_curvature", 100.0), ("b4d_def_fillet", True),
              ("b4d_def_size", (250.0, 250.0, 100.0)), ("b4d_def_mode", "UNLIMITED")],
    "shear": [("b4d_def_strength", 40.0), ("b4d_def_direction", math.radians(90)), ("b4d_def_curvature", 100.0),
              ("b4d_def_fillet", True), ("b4d_def_size", (250.0, 250.0, 100.0)), ("b4d_def_mode", "UNLIMITED")],
    "wave": [("b4d_def_height", 30.0), ("b4d_def_wavelength", 80.0), ("b4d_def_phase", 1.0), ("b4d_def_shape", "RIPPLE"),
             ("b4d_def_speed", 1.0)],
    "displace": [("b4d_def_height", 30.0), ("b4d_def_noise_size", 40.0), ("b4d_def_detail", 6.0), ("b4d_def_seed", 3),
                 ("b4d_def_speed", 1.0), ("b4d_def_along", "AXIS")],
    "smooth": [("b4d_def_iterations", 30), ("b4d_def_strength", 50.0)],
}


def frame_check(ob):
    """Speed rows only show while the animation plays: compare two frames."""
    a = points(ob)
    bpy.context.scene.frame_set(30)
    b = points(ob)
    bpy.context.scene.frame_set(1)
    return a != b


def test_kind(kind):
    clear()
    col = column()
    rest = points(col)
    d = create(kind, col)
    check(d is not None and d.parent == col and D.kind_of(d) == kind, f"{kind}: made under the selected object")
    check(any(D._owner(m) == d for m in col.modifiers), f"{kind}: the parent got its modifier")
    if kind in D.BOX_KINDS:
        check(abs(d['b4d_def_size'][2] - 200.0) < 0.5 and abs(d['b4d_def_size'][0] - 50.0) < 0.5,
              f"{kind}: box fitted to the parent {tuple(round(c, 1) for c in d['b4d_def_size'])}")
        box0 = points(d)
        check(len(box0) == 4 * (33), f"{kind}: own box has its points ({len(box0)})")
    if kind in ("bend", "twist", "taper", "bulge", "shear"):
        check(points(col) == rest, f"{kind}: no change at strength 0")
    prev = points(col)
    for attr, v in ROWS[kind]:
        setv(d, attr, v)
        now = points(col)
        changed = now != prev
        if attr == "b4d_def_speed":
            changed = frame_check(col)
        check(changed, f"{kind}: row {attr} changes the shape")
        prev = now
    check(len(points(col)) == len(rest), f"{kind}: point count kept")
    if kind in D.BOX_KINDS:
        check(points(d) != box0, f"{kind}: the box takes the deformation")
    # moving the deformer moves the effect
    if kind != "smooth":                                # smoothing does not depend on where the deformer is
        before = points(col)
        d.location.x += 0.3
        d.rotation_euler.y += 0.3
        check(points(col) != before, f"{kind}: moving the deformer changes the effect")
    # the check mark switches it off
    d["_b4d_enabled"] = False
    check(points(col) == rest, f"{kind}: switched off gives the object back")
    d["_b4d_enabled"] = True
    check(points(col) != rest, f"{kind}: switched on again")
    # deleting it gives the object back
    bpy.data.objects.remove(d)
    check(points(col) == rest and not any(D._owner(m) is not None for m in col.modifiers),
          f"{kind}: deleted deformer leaves no modifier")


def test_bend_shape():
    clear()
    col = column()
    d = create("bend", col)
    setv(d, "b4d_def_angle", math.radians(90))
    pts = points(col)
    xs = [p[0] for p in pts]
    zs = [p[2] for p in pts]
    # a 2 m column bent 90 degrees with length kept: the top ends up off to the side at about 2/(pi/2) = 1.27 m
    check(max(xs) > 1.0 and max(zs) < 1.4, f"bend: 90 degrees lays the top over (x {max(xs):.2f}, z {max(zs):.2f})")
    setv(d, "b4d_def_angle", math.radians(360))
    pts = points(col)
    check(max(p[2] for p in pts) < 0.7, "bend: 360 degrees curls into a ring")


def test_twist_shape():
    clear()
    col = column()
    d = create("twist", col)
    setv(d, "b4d_def_angle", math.radians(90))
    top = [p for p in points(col) if p[2] > 0.999]
    corner = max(top, key=lambda p: p[0] + p[1])
    check(abs(abs(corner[0]) - 0.25) < 0.01 or abs(abs(corner[1]) - 0.25) < 0.01, f"twist: top turned ({corner})")
    bottom = [p for p in points(col) if p[2] < -0.999]
    check(max(p[0] for p in bottom) > 0.249, "twist: bottom stays")


def test_null_siblings():
    clear()
    null = bpy.data.objects.new("Null", None)
    bpy.context.scene.collection.objects.link(null)
    a, b = column("A"), column("B")
    b.location.x = 2
    a.parent = b.parent = null
    rest = points(a), points(b)
    d = create("taper", None)
    d.parent = null
    setv(d, "b4d_def_size", (300.0, 300.0, 200.0))
    setv(d, "b4d_def_strength", 80.0)
    check(points(a) != rest[0] and points(b) != rest[1], "under a Null: deforms every sibling")
    d.parent = a
    check(points(b) == rest[1] and points(a) != rest[0], "moved under A: only A")


def test_order_and_copy():
    clear()
    col = column()
    t = create("twist", col)
    setv(t, "b4d_def_angle", 1.0)
    b = create("bend", col)
    check(b.parent == col, "a second deformer, with the first one selected, goes beside it")
    setv(b, "b4d_def_angle", 1.0)
    names = [m.name for m in col.modifiers if D._owner(m)]
    check(names == ["Bend", "Twist"], f"modifiers follow the Object Manager order ({names})")
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    b.select_set(True)
    bpy.context.view_layer.objects.active = b
    bpy.ops.object.duplicate()
    c = bpy.context.object
    update()
    check(D.tree_of(c) is not None and D.tree_of(c) != D.tree_of(b), "a copied deformer gets its own tree")
    before = points(col)
    setv(c, "b4d_def_angle", 2.0)
    after = points(col)
    check(before != after and abs(b['b4d_def_angle'] - 1.0) < 1e-6, "the copy's settings are its own")
    check(len([m for m in col.modifiers if D._owner(m)]) == 3, "three deformers, three modifiers")


def test_lattice():
    clear()
    col = column()
    rest = points(col)
    d = create("lattice", col)
    check(d.type == "LATTICE" and abs(d.scale.z - 2.0) < 0.01, f"lattice: fitted cage ({tuple(d.scale)})")
    check(points(col) == rest, "lattice: no change until its points move")
    d.data.points[-1].co_deform.x += 0.4
    check(points(col) != rest, "lattice: moving a point deforms")
    prev = points(col)
    setv(d, "b4d_def_strength", 50.0)
    check(points(col) != prev, "lattice: Strength row")
    prev = points(col)
    setv(d, "b4d_def_interp", "KEY_LINEAR")
    check(points(col) != prev, "lattice: Interpolation row")
    d.b4d_def_grid = (100.0, 100.0, 300.0)
    check(abs(d.scale.z - 3.0) < 1e-4, "lattice: Grid Size row sets the cage size")
    d.data.points_u = 4
    check(len(d.data.points) == 4 * 3 * 3, "lattice: Grid Points row")
    with bpy.context.temp_override(active_object=d, object=d):
        bpy.ops.blenda4d.lattice_reset()
    setv(d, "b4d_def_strength", 100.0)
    check(points(col) == rest, "lattice: Reset Points gives the shape back")


def test_shrinkwrap():
    clear()
    col = column()
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.5, location=(0, 0, 0))
    ball = bpy.context.object
    ball.name = "Ball"
    rest = points(col)
    d = create("shrinkwrap", col)
    check(points(col) == rest, "shrinkwrap: no target, no change")
    setv(d, "b4d_def_target", ball)
    pts = points(col)
    r = [math.sqrt(sum(c * c for c in p)) for p in pts]
    check(min(r) > 1.4 and max(r) < 1.51, f"shrinkwrap: points land on the ball ({min(r):.2f}..{max(r):.2f})")
    prev = pts
    for attr, v in (("b4d_def_strength", 50.0), ("b4d_def_wrap_mode", "NORMAL"), ("b4d_def_wrap_mode", "AXIS"),
                    ("b4d_def_distance", 60.0)):
        setv(d, attr, v)
        now = points(col)
        check(now != prev, f"shrinkwrap: row {attr}={v} changes the shape")
        prev = now


def test_mode_off():
    """Blenda mode off: the module unregisters, the deformed shape stays."""
    clear()
    col = column()
    d = create("bend", col)
    setv(d, "b4d_def_angle", 1.2)
    bent = points(col)
    D.unregister()
    bpy.context.view_layer.update()
    ev = col.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    after = [tuple(round(c, 5) for c in v.co) for v in ev.vertices]
    check(after == bent, "mode off: the bend stays as it was")
    d["b4d_def_angle"] = 0.3
    d.update_tag()
    bpy.context.view_layer.update()
    ev = col.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    check([tuple(round(c, 5) for c in v.co) for v in ev.vertices] != bent, "mode off: the setting still drives the bend")
    d["b4d_def_angle"] = 1.2
    D.register()
    check(abs(d['b4d_def_angle'] - 1.2) < 1e-6, "mode on again: the setting is still there")


for t in (lambda: [test_kind(k) for k in ROWS], test_bend_shape, test_twist_shape, test_null_siblings, test_order_and_copy,
          test_lattice, test_shrinkwrap, test_mode_off):
    try:
        t()
    except Exception:
        traceback.print_exc()
        fails.append("exception")
print("DEFORMERS RESULT", "PASS" if not fails else f"FAIL {len(fails)}: {fails}", flush=True)
