# One UI run of the generators module (window mode, screenshots of the Attribute Manager with a generator selected):
#   B4D_OUT=<scratch> BLENDER_USER_CONFIG=<scratch>/config Blender --factory-startup --window-geometry 100 60 1700 1000 \
#       --python tools/tests/generators_ui.py
import math
import os
import sys
import traceback

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT = os.environ.get("B4D_OUT", "/tmp")
import blenda4d  # noqa: E402

blenda4d.register()


def shot(name):
    w = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=w, screen=w.screen, area=w.screen.areas[0]):
        bpy.ops.screen.screenshot(filepath=os.path.join(OUT, name + ".png"))
    print("B4D SHOT", name, flush=True)


def only(objs):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0] if objs else None


def add(kind, objs):
    only(objs)
    bpy.ops.blenda4d.add_kind(kind=kind)
    return bpy.context.view_layer.objects.active


def scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    bpy.ops.curve.primitive_bezier_circle_add(radius=1.0, location=(-4, 0, 1), rotation=(math.pi / 2, 0, 0))
    ex = add("extrude", [bpy.context.object])
    ex.name = "Extrude"
    bpy.ops.curve.primitive_bezier_circle_add(radius=0.25, rotation=(math.pi / 2, 0, 0))
    prof = bpy.context.object
    prof.name = "Shape"
    bpy.ops.curve.primitive_bezier_curve_add(location=(0, 0, 1), rotation=(0, math.pi / 2, 0))
    path = bpy.context.object
    path.name = "Path"
    add("sweep", [prof, path])
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(4.7, 0, 1))
    sym = add("symmetry", [bpy.context.object])
    sym.location = (4, 0, 0)
    bpy.ops.mesh.primitive_cube_add(size=1.2, location=(0, -3, 0.8))
    add("subdivision", [bpy.context.object])
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(-2, -3, 0.6))
    a = bpy.context.object
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.4, location=(-1.4, -3, 0.9))
    add("metaball", [a, bpy.context.object])
    print("B4D GROUP", [(m[0], m[2]) for m in blenda4d.bars.GROUPS["generators"]], flush=True)
    print("B4D OBJECTS", [(o.name, o.get("b4d_type"), o.parent and o.parent.name) for o in bpy.context.scene.objects], flush=True)


def select(name, tab="OBJECT"):
    ob = bpy.data.objects[name]
    only([ob])
    bpy.context.window_manager.b4d_am_tab = tab


def frame():
    w = bpy.context.window_manager.windows[0]
    area = max((a for a in w.screen.areas if a.type == "VIEW_3D"), key=lambda a: a.width * a.height)
    reg = next(r for r in area.regions if r.type == "WINDOW")
    only(list(bpy.context.scene.objects))
    with bpy.context.temp_override(window=w, screen=w.screen, area=area, region=reg):
        bpy.ops.view3d.view_axis(type="FRONT")
        bpy.ops.view3d.view_selected()
        bpy.ops.view3d.view_orbit(angle=0.5, type="ORBITUP")
        bpy.ops.view3d.view_orbit(angle=0.5, type="ORBITLEFT")


def menu():
    w = bpy.context.window_manager.windows[0]
    area = next(a for a in w.screen.areas if a.type == "VIEW_3D")
    with bpy.context.temp_override(window=w, screen=w.screen, area=area):
        bpy.ops.wm.call_menu(name="BLENDA4D_MT_create_generators")


def caps_on():
    from blenda4d import generators as G
    ob = bpy.data.objects["Extrude"]
    for name, v in (("S Size", 5.0), ("S Subdivision", 4)):
        setattr(*G.slot(ob, name), v)
    ob.update_tag()


W = [lambda: None]
PLAN = W * 5 + [scene] + W * 2 + [frame] + W * 2
for name, tab in (("Extrude", "OBJECT"), ("Extrude", "CAPS"), ("Extrude", "SELECT"), ("Sweep", "OBJECT"),
                  ("Symmetry", "OBJECT"), ("Subdivision Surface", "OBJECT"), ("Metaball", "OBJECT")):
    if tab == "CAPS":
        PLAN += [caps_on]
    PLAN += [lambda n=name, t=tab: select(n, t)] + W * 2 + [lambda n=name, t=tab: shot(f"am_{n.replace(' ', '_')}_{t}")]
PLAN += [menu] + W * 2 + [lambda: shot("create_menu")]
PLAN += [lambda: open(os.path.join(OUT, "done.txt"), "w").write("ok"), lambda: bpy.ops.wm.quit_blender()]
_i = [0]


def tick():
    try:
        PLAN[_i[0]]()
    except Exception:
        traceback.print_exc()
    _i[0] += 1
    return 0.6 if _i[0] < len(PLAN) else None


bpy.app.timers.register(tick, first_interval=1.5)
