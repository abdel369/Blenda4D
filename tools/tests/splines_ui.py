# One UI run of the splines module (window mode, screenshots of the Attribute Manager with a shape selected):
#   B4D_OUT=<scratch> BLENDER_USER_CONFIG=<scratch>/config Blender --factory-startup --window-geometry 100 60 1700 1000 \
#       --python tools/tests/splines_ui.py
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


def scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    for kind, x in (("star", -5), ("helix", -1.5), ("cogwheel", 2), ("circle", 5.5)):
        bpy.ops.blenda4d.add_kind(kind=kind)
        bpy.context.view_layer.objects.active.location = (x, 0, 2.5)
    bpy.ops.curve.primitive_bezier_curve_add(location=(0, 0, -1))
    print("B4D GROUP", [m[0] for m in __import__("blenda4d").bars.GROUPS["splines"]], flush=True)


def select(name):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob = next(o for o in bpy.data.objects if o.name == name or (name == "Plain" and "b4d_type" not in o))
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.context.window_manager.b4d_am_tab = "OBJECT"


def frame():
    w = bpy.context.window_manager.windows[0]
    area = max((a for a in w.screen.areas if a.type == "VIEW_3D"), key=lambda a: a.width * a.height)
    reg = next(r for r in area.regions if r.type == "WINDOW")
    for o in bpy.context.view_layer.objects:
        o.select_set(True)
    with bpy.context.temp_override(window=w, screen=w.screen, area=area, region=reg):
        bpy.ops.view3d.view_axis(type="FRONT")
        bpy.ops.view3d.view_selected()


def menu():
    w = bpy.context.window_manager.windows[0]
    area = next(a for a in w.screen.areas if a.type == "VIEW_3D")
    with bpy.context.temp_override(window=w, screen=w.screen, area=area):
        bpy.ops.wm.call_menu(name="BLENDA4D_MT_create_splines")


W = [lambda: None]
PLAN = W * 5 + [scene] + W * 2 + [frame] + W * 2
for name in ("Star", "Helix", "Cogwheel", "Plain"):
    PLAN += [lambda n=name: select(n)] + W * 2 + [lambda n=name: shot("am_" + n)]
PLAN += [menu] + W * 2 + [lambda: shot("create_menu")]
PLAN += [lambda: open(os.path.join(OUT, "done.txt"), "w").write("ok")]
_i = [0]


def tick():
    try:
        PLAN[_i[0]]()
    except Exception:
        traceback.print_exc()
    _i[0] += 1
    return 0.6 if _i[0] < len(PLAN) else None


bpy.app.timers.register(tick, first_interval=1.5)
