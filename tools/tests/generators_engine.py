# Headless test of the generators module: every generator builds real geometry from its children, every Attribute
# Manager row changes the result, children are hidden and given back, and modifier generators follow their settings.
#   Blender -b --factory-startup --python tools/tests/generators_engine.py
import math
import os
import sys
import traceback

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from blenda4d import coords, generators as G, kinds  # noqa: E402

bpy.utils.register_class(kinds.BLENDA4D_OT_add_kind)
coords.register()
G.register()
fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)
        print("FAIL", msg, flush=True)


def update():
    G.sync_all()
    bpy.context.view_layer.update()
    G.sync_all()
    bpy.context.view_layer.update()


def sig(ob):
    """What a change could show in: counts, size, normals, attributes, sharp edges, instances."""
    update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    vs = [v.co for v in me.vertices]
    bb = [round(max(v[i] for v in vs) - min(v[i] for v in vs), 4) for i in range(3)] if vs else [0, 0, 0]
    c = [sum(v[i] for v in vs) / len(vs) for i in range(3)] if vs else [0, 0, 0]
    turn = round(sum(p.normal.dot(p.center - __import__("mathutils").Vector(c)) for p in me.polygons), 3)
    sharp = sum(1 for e in me.edges if e.use_edge_sharp)
    smooth = sum(1 for p in me.polygons if p.use_smooth)
    names = tuple(sorted(a.name for a in me.attributes if not a.name.startswith(".")))
    spread = round(sum(abs(v[0]) + abs(v[1]) + abs(v[2]) for v in vs), 3)
    out = (len(vs), len(me.polygons), tuple(bb), turn, sharp, smooth, names, spread)
    ev.to_mesh_clear()
    inst = sum(1 for i in dg.object_instances if i.is_instance and i.parent and i.parent.original == ob)
    return out + (inst,)


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)


def select(objs, active=None):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or (objs[0] if objs else None)


def circle(name, r=1.0, loc=(0, 0, 0), rot=(0, 0, 0)):
    bpy.ops.curve.primitive_bezier_circle_add(radius=r, location=loc, rotation=rot)
    ob = bpy.context.object
    ob.name = name
    return ob


def line(name, pts):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p, co in zip(sp.points, pts):
        p.co = (*co, 1.0)
    ob = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(ob)
    return ob


def cube(name, loc=(0, 0, 0), size=1.0):
    bpy.ops.mesh.primitive_cube_add(size=size, location=loc)
    ob = bpy.context.object
    ob.name = name
    return ob


def make(kind, kids):
    select(kids)
    bpy.ops.blenda4d.add_kind(kind=kind)
    gen = bpy.context.view_layer.objects.active
    check(gen is not None and gen.get("b4d_type") == kind, f"{kind}: not created")
    check(all(k.parent == gen for k in kids) or kind == "instance", f"{kind}: selection not put under it")
    return gen


def setv(gen, name, value):
    s = G.slot(gen, name)
    check(s is not None, f"{gen.get('b4d_type')}: no setting {name}")
    if s:
        setattr(*s, value)
        gen.update_tag()         # the Attribute Manager's field does this through the modifier's own update


def try_rows(gen, rows):
    """rows: (socket, new value, {setting: value first})"""
    k = gen["b4d_type"]
    for name, value, first in rows:
        for n2, v2 in first.items():
            setv(gen, n2, v2)
        before = sig(gen)
        old = G.gval(gen, name)
        old = tuple(old) if hasattr(old, "__len__") and not isinstance(old, str) else old
        setv(gen, name, value)
        after = sig(gen)
        check(after != before, f"{k}: row {name} -> {value!r} changed nothing")
        setv(gen, name, old)
        for n2, v2 in first.items():
            pass
        print(f"  {k}.{name}: {before[:3]} -> {after[:3]}", flush=True)


CAPS_ROWS = [("Start", False, {}), ("End", False, {}), ("Tessellation", "N-gons", {}), ("Tessellation", "Regular Grid", {}),
             ("Density", 60.0, {"Tessellation": "Even Mesh"}), ("Cap Size", 25.0, {"Tessellation": "Regular Grid"}),
             ("Quad Dominant", True, {"Tessellation": "Regular Grid"}),
             ("S Size", 5.0, {"Tessellation": "Triangles"}), ("S Shape", "Steps", {"S Size": 5.0}), ("S Subdivision", 6, {"S Size": 5.0}),
             ("S Tension", 20.0, {"S Size": 5.0, "S Shape": "Round"}), ("S Extrusion", True, {"S Offset": 5.0}),
             ("S Offset", 9.0, {"S Extrusion": True}),
             ("Separate Controls", True, {"S Size": 5.0, "S Extrusion": False}), ("E Size", 2.0, {"Separate Controls": True}),
             ("E Shape", "Straight", {"Separate Controls": True, "E Size": 4.0}), ("E Subdivision", 5, {"Separate Controls": True, "E Size": 4.0}),
             ("E Tension", 10.0, {"Separate Controls": True, "E Size": 4.0, "E Shape": "Round"}), ("E Extrusion", True, {"E Offset": 5.0}),
             ("E Offset", 7.0, {"E Extrusion": True}),
             ("Shell Selection", True, {}), ("Start Cap Selection", True, {}), ("End Cap Selection", True, {}),
             ("Start Bevel Selection", True, {"S Size": 5.0}), ("End Bevel Selection", True, {"S Size": 5.0, "Separate Controls": False})]


def case(name, fn):
    print("==", name, flush=True)
    try:
        clear()
        fn()
    except Exception:
        traceback.print_exc()
        fails.append(name + ": error")


def t_extrude():
    c = circle("Circle")
    gen = make("extrude", [c])
    s = sig(gen)
    print("  extrude", s[:3], flush=True)
    check(s[0] > 20 and abs(s[2][2] - 0.2) < 1e-3 and abs(s[2][0] - 2.0) < 0.01, f"extrude: wrong solid {s[:3]}")
    c2 = circle("Circle.hole", r=0.4)
    c2.parent = gen
    try_rows(gen, [("Direction", "X", {}), ("Offset", 50.0, {}), ("Movement", (10.0, 30.0, 5.0), {"Direction": "Movement Vector"}),
                   ("Subdivision", 4, {"Direction": "Auto"}), ("Reverse Normals", True, {}), ("Hierarchical", True, {})]
             + [r for r in CAPS_ROWS] + [("Bevel Outside", True, {"S Size": 5.0})])


def t_lathe():
    prof = line("Profile", [(0.5, 0, 0), (1.0, 0, 0.5), (0.6, 0, 1.0)])
    gen = make("lathe", [prof])
    s = sig(gen)
    print("  lathe", s[:3], flush=True)
    check(s[0] > 50 and abs(s[2][0] - 2.0) < 0.05 and abs(s[2][1] - 2.0) < 0.05, f"lathe: wrong size {s[:3]}")
    try_rows(gen, [("Angle", 180.0, {}), ("Subdivision", 8, {"Angle": 360.0}), ("Movement", 50.0, {}), ("Scaling", 50.0, {}),
                   ("Reverse Normals", True, {})])
    prof.data.splines[0].use_cyclic_u = True
    try_rows(gen, [("Start", False, {"Angle": 180.0}), ("End", False, {"Angle": 180.0}), ("S Size", 3.0, {"Angle": 180.0})])


def t_sweep():
    prof = circle("Profile", r=0.1, rot=(math.pi / 2, 0, 0))
    path = line("Path", [(0, 0, 0), (0, 0, 2), (1, 0, 3)])
    gen = make("sweep", [prof, path])
    s = sig(gen)
    print("  sweep", s[:3], flush=True)
    check(s[0] > 50 and s[2][2] > 2.9, f"sweep: wrong size {s[:3]}")
    try_rows(gen, [("End Scale", 300.0, {}), ("End Rotation", 90.0, {}), ("Start Growth", 30.0, {}), ("End Growth", 60.0, {}),
                   ("Banking", False, {}), ("Reverse Normals", True, {}), ("Start", False, {}), ("End", False, {}),
                   ("S Size", 3.0, {}), ("Shell Selection", True, {})])
    # live: moving the path changes the result
    before = sig(gen)
    path.data.splines[0].points[2].co = (2, 0, 4, 1)
    check(sig(gen) != before, "sweep: editing the path did not update it")


def t_loft():
    a = circle("A", r=1.0)
    b = circle("B", r=0.5, loc=(0, 0, 1))
    c = circle("C", r=0.8, loc=(0, 0, 2))
    gen = make("loft", [a, b, c])
    s = sig(gen)
    print("  loft", s[:3], flush=True)
    check(s[0] > 40 and abs(s[2][2] - 2.0) < 0.01, f"loft: wrong size {s[:3]}")
    try_rows(gen, [("Subdivision U", 30, {}), ("Subdivision V", 8, {}), ("Loop", True, {}), ("Linear Interpolation", True, {}),
                   ("Reverse Normals", True, {}), ("Start", False, {}), ("End", False, {}), ("E Size", 3.0, {"Separate Controls": True})])


def t_symmetry():
    k = cube("Box", loc=(1.5, 0, 0))
    gen = make("symmetry", [k])
    s = sig(gen)
    print("  symmetry", s[:3], flush=True)
    check(s[0] == 16 and abs(s[2][0] - 4.0) < 1e-3, f"symmetry: not mirrored {s[:3]}")
    check(k.display_type == "WIRE" and k.hide_render, "symmetry: child still shown")
    k.location.x = 0.5                       # touching the mirror plane: the points there weld
    try_rows(gen, [("Weld Points", False, {}), ("Mirror Plane", "XY", {})])
    k.location.x = 0.6                       # 20 cm apart: only a wide weld distance joins them
    try_rows(gen, [("Weld Tolerance", 30.0, {"Weld Points": True})])
    k.parent = None
    update()
    check(k.display_type == "TEXTURED" and not k.hide_render, "symmetry: child not given back")


def t_array():
    k = cube("Box", size=0.2)
    gen = make("array", [k])
    s = sig(gen)
    print("  array", s[:3], flush=True)
    check(s[0] == 8 * 8 and abs(s[2][0] - 5.2) < 0.05, f"array: wrong ring {s[:3]}")
    try_rows(gen, [("Radius", 100.0, {}), ("Copies", 3, {}), ("Amplitude", 50.0, {"Array Frequency": 1.0}),
                   ("Array Frequency", 2.0, {"Amplitude": 50.0}), ("Keep Instances", True, {})])
    bpy.context.scene.frame_set(13)
    setv(gen, "Amplitude", 50.0); setv(gen, "Array Frequency", 0.0)
    try_rows(gen, [("Frequency", 0.3, {})])


def t_instance():
    k = cube("Box", loc=(3, 0, 0))
    gen = make("instance", [k])
    s = sig(gen)
    check(s[0] == 8, f"instance: no copy {s[:3]}")
    check(G.gval(gen, "Reference Object") == k, "instance: reference not set")
    other = bpy.data.objects.new("Ico", bpy.data.meshes.new("Ico"))
    bpy.context.collection.objects.link(other)
    import bmesh
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0); bm.to_mesh(other.data); bm.free()
    try_rows(gen, [("Reference Object", other, {})])


def t_connect():
    a = cube("A", loc=(0, 0, 0))
    b = cube("B", loc=(1, 0, 0))
    gen = make("connect", [a, b])
    s = sig(gen)
    print("  connect", s[:3], flush=True)
    check(s[0] == 12, f"connect: not welded {s[:3]}")
    check(a.display_type == "WIRE", "connect: child still shown")
    far = cube("Far", loc=(5, 0, 0))
    far.parent = None
    try_rows(gen, [("Weld", False, {}), ("Tolerance", 200.0, {"Weld": True}), ("Objects", far, {})])


def t_boolean():
    a = cube("Base", size=2.0)
    b = cube("Cutter", loc=(1, 1, 1), size=1.0)
    gen = make("boolean", [a, b])
    s = sig(gen)
    print("  boolean", s[:3], flush=True)
    check(s[0] > 8 and abs(s[2][0] - 2.0) < 1e-3, f"boolean: no cut {s[:3]}")
    try_rows(gen, [("Operation", "Union", {}), ("Operation", "Intersect", {}), ("Operation", "Without", {}),
                   ("Hard Cut Edges", True, {"Angle Limit": False}), ("Mark Cut Edges", True, {})])
    setv(gen, "Angle Limit", True)
    # Fix Overlaps: only shows on a child that overlaps itself
    c = cube("C2", loc=(1.3, 1.3, 1.3), size=1.0)
    j = bpy.data.objects.new("Overlap", bpy.data.meshes.new("Overlap"))
    bpy.context.collection.objects.link(j)
    import bmesh
    bm = bmesh.new()
    for off in ((0, 0, 0), (0.5, 0.5, 0.5)):
        r = bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.translate(bm, verts=r["verts"], vec=off)
    bm.to_mesh(j.data); bm.free()
    bpy.data.objects.remove(c)
    b.parent = None
    j.parent = gen
    j.name = "Zcut"
    try_rows(gen, [("Fix Overlaps", False, {"Operation": "Subtract"})])


def t_metaball():
    a = cube("A", loc=(0, 0, 0), size=0.4)
    b = cube("B", loc=(0.6, 0, 0), size=0.4)
    gen = make("metaball", [a, b])
    s = sig(gen)
    print("  metaball", s[:3], flush=True)
    check(s[0] > 50 and s[2][0] > 1.0, f"metaball: no surface {s[:3]}")
    check(a.display_type == "WIRE", "metaball: child still shown")
    try_rows(gen, [("Radius", 30.0, {}), ("Blend", 10, {}), ("Swell", 5.0, {}), ("Viewport Detail", 10.0, {})])
    # Render Detail is used in renders only: the render depsgraph shows it
    setv(gen, "Render Detail", 10.0)
    from blenda4d import primitives
    check(abs(G.gval(gen, "Render Detail") - 10.0) < 1e-6, "metaball: render detail not kept")


def t_subdivision():
    k = cube("Box")
    gen = make("subdivision", [k])
    s = sig(k)
    check(s[0] == 98, f"subdivision: level 2 cube has {s[0]} points")
    for prop, value in (("b4d_sub_view", 3), ("b4d_sub_type", "SIMPLE"), ("b4d_sub_pre", 1), ("b4d_sub_boundary", "PRESERVE_CORNERS"),
                        ("b4d_sub_uv", "NONE"), ("b4d_sub_creases", False), ("b4d_sub_render", 4)):
        mod_before = {m.name: tuple(getattr(m, a) for a in ("levels", "render_levels", "subdivision_type", "uv_smooth", "boundary_smooth", "use_creases"))
                      for m in k.modifiers}
        old = getattr(gen, prop)
        setattr(gen, prop, value)
        update()
        mod_after = {m.name: tuple(getattr(m, a) for a in ("levels", "render_levels", "subdivision_type", "uv_smooth", "boundary_smooth", "use_creases"))
                     for m in k.modifiers}
        check(mod_after != mod_before, f"subdivision: {prop} changed nothing")
        setattr(gen, prop, old)
        update()
    gen["_b4d_enabled"] = False
    update()
    check(not k.modifiers[G.SUB_MOD].show_viewport, "subdivision: switching off did not stop it")
    gen["_b4d_enabled"] = True
    k.parent = None
    update()
    check(G.SUB_MOD not in k.modifiers, "subdivision: modifier stayed after leaving")


def t_reduce():
    import bmesh
    k = bpy.data.objects.new("Ball", bpy.data.meshes.new("Ball"))
    bpy.context.collection.objects.link(k)
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.0); bm.to_mesh(k.data); bm.free()
    gen = make("reduce", [k])
    s = sig(k)
    check(s[1] < len(k.data.polygons) * 0.3, f"reduce: {s[1]} of {len(k.data.polygons)} polygons left")
    for prop, value in (("b4d_red_strength", 50.0), ("b4d_red_triangulate", True), ("b4d_red_symmetry", True)):
        before = sig(k)
        old = getattr(gen, prop)
        setattr(gen, prop, value)
        check(sig(k) != before, f"reduce: {prop} changed nothing")
        setattr(gen, prop, old)
    gen.b4d_red_symmetry = True
    gen.b4d_red_strength = 70.0
    before = sig(k)
    gen.b4d_red_axis = "Z"
    check(sig(k) != before, "reduce: axis changed nothing")


def t_remesh():
    k = cube("Box", size=2.0)
    gen = make("remesh", [k])
    s = sig(k)
    check(s[1] > 6, f"remesh: no new mesh {s[:2]}")
    for prop, value, first in (("b4d_rm_density", 300.0, {}), ("b4d_rm_target", "COUNT", {}), ("b4d_rm_count", 5000, {"b4d_rm_target": "COUNT"}),
                               ("b4d_rm_smooth", 5, {})):
        for p2, v2 in first.items():
            setattr(gen, p2, v2)
        before = sig(k)
        old = getattr(gen, prop)
        setattr(gen, prop, value)
        check(sig(k) != before, f"remesh: {prop} changed nothing")
        setattr(gen, prop, old)


def t_nested():
    """Symmetry under Subdivision Surface: the mirrored result is smoothed once, the hidden child not at all."""
    k = cube("Box", loc=(1.5, 0, 0))
    sym = make("symmetry", [k])
    sub = make("subdivision", [sym])
    update()
    check(G.SUB_MOD in sym.modifiers and G.SUB_MOD not in k.modifiers, "nested: smoothed in the wrong place")


def t_spline_kids():
    """Blenda's own spline objects (splines.py) work as children, when that module is present."""
    try:
        from blenda4d import splines
    except ImportError:
        print("  splines module not present: skipped", flush=True)
        return
    splines.register()
    try:
        select([])
        bpy.ops.blenda4d.add_kind(kind="circle" if "circle" in kinds.KINDS else splines.ORDER[0])
        sp = bpy.context.view_layer.objects.active
        gen = make("extrude", [sp])
        s = sig(gen)
        print("  extrude of", sp.get("b4d_type"), s[:3], flush=True)
        check(s[0] > 8, f"spline kids: Extrude of a {sp.get('b4d_type')} made {s[:3]}")
        sp2 = None
        bpy.ops.blenda4d.add_kind(kind="helix" if "helix" in kinds.KINDS else splines.ORDER[0])
        sp2 = bpy.context.view_layer.objects.active
        select([])
        bpy.ops.blenda4d.add_kind(kind="circle" if "circle" in kinds.KINDS else splines.ORDER[0])
        prof = bpy.context.view_layer.objects.active
        sw = make("sweep", [prof, sp2])
        prof.name, sp2.name = "A profile", "B path"
        s = sig(sw)
        print("  sweep along", sp2.get("b4d_type"), s[:3], flush=True)
        check(s[0] > 50, f"spline kids: Sweep along a {sp2.get('b4d_type')} made {s[:3]}")
    finally:
        splines.unregister()


def t_rebuild_keeps_settings():
    c = circle("Circle")
    gen = make("extrude", [c])
    setv(gen, "Offset", 77.0)
    setv(gen, "Direction", "Z")
    c2 = circle("Second", r=0.3)
    c2.parent = gen
    update()
    check(abs(G.gval(gen, "Offset") - 77.0) < 1e-6 and G.gval(gen, "Direction") == "Z", "rebuild lost the settings")
    check(list(gen["b4d_kids"]) == ["Circle", "Second"], f"rebuild: kids {list(gen['b4d_kids'])}")


for n, f in [("extrude", t_extrude), ("lathe", t_lathe), ("sweep", t_sweep), ("loft", t_loft), ("symmetry", t_symmetry),
             ("array", t_array), ("instance", t_instance), ("connect", t_connect), ("boolean", t_boolean), ("metaball", t_metaball),
             ("subdivision", t_subdivision), ("reduce", t_reduce), ("remesh", t_remesh), ("nested", t_nested),
             ("spline kids", t_spline_kids), ("rebuild", t_rebuild_keeps_settings)]:
    case(n, f)

G.unregister()
print("B4D GENERATORS", "FAILS" if fails else "OK", len(fails), flush=True)
for f in fails:
    print("  -", f)
