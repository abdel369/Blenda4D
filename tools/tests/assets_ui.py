# UI run of the Asset Browser: the sample scene from tools/try_ui.py, the browser opened on a scratch User Library
# (B4D_LIB, e.g. the library tools/tests/assets_engine.py filled), Home, a folder and the Materials tab screenshotted;
# then a picture dragged into the viewport, a right-click under the folder list, and the drop handler's check.
#   BLENDER_USER_CONFIG=<scratch> B4D_OUT=<scratch> B4D_LIB=<library> Blender --factory-startup \
#       --window-geometry 100 60 1700 1000 --python tools/tests/assets_ui.py
import os
import runpy

import bpy

os.environ["B4D_STEPS"] = "wait"
HERE = os.path.dirname(os.path.abspath(__file__))
ns = runpy.run_path(os.path.join(HERE, "..", "try_ui.py"))
PLAN, shot, toggle, ev = ns["PLAN"], ns["shot"], ns["toggle"], ns["ev"]
LIB = os.environ.get("B4D_LIB", "")
if LIB:
    bpy.context.preferences.filepaths.asset_libraries["User Library"].path = LIB


def area():
    from blenda4d import roles
    return roles.areas(bpy.context.window_manager.windows[0].screen, "ASSETS")[0]


def region():
    return next(r for r in area().regions if r.type == "WINDOW")


def redraw():
    area().tag_redraw()


def open_folder(f):
    from blenda4d import assets
    assets._st.update(folder=f, home=False)
    redraw()


def tab(t):
    bpy.context.window_manager.b4d_ab_tab = t
    redraw()


def tile_xy(i):
    """Window position of the middle of tile i's picture (the inverse of assets.asset_at)."""
    from blenda4d import assets
    g = assets._st["geom"]
    r = region()
    u = assets._unit()
    left = r.width * assets.SPLIT
    colw = (r.width - left) / g["cols"]
    row, col = divmod(i, g["cols"])
    vx = left + colw * (col + 0.5)
    vy = -((assets.TOP_UNITS + assets.HEAD_UNITS) * u + row * (g["scale"] + 1 + assets.GAP_UNITS) * u + g["scale"] * u / 2)
    x, y = r.view2d.view_to_region(vx, vy, clip=False)
    return r.x + int(x), r.y + int(y)


def calib():
    from blenda4d import assets
    r = region()
    g = assets._st["geom"]
    print("B4D AB REGION", r.x, r.y, r.width, r.height, "unit", assets._unit(), "geom", g and (g["cols"], g["keys"][:4]), flush=True)
    for i in range(min(4, len(g["keys"]) if g else 0)):
        x, y = tile_xy(i)
        w = bpy.context.window_manager.windows[0]
        with bpy.context.temp_override(window=w, area=area(), region=r):
            back = assets.asset_at(bpy.context, x, y)
        print("B4D AB TILE", i, g["keys"][i].split("|")[-1], (x, y), "screenshot", (x, 1000 - y),
              "asset_at", back and back.split("|")[-1], flush=True)


state = {}


def drag_start(i):
    from blenda4d import assets
    g = assets._st["geom"]
    state["n"] = len(bpy.data.objects)
    state["key"] = g["keys"][i]
    x, y = tile_xy(i)
    state["xy"] = (x, y)
    ev("MOUSEMOVE", "NOTHING", x, y)
    ev("LEFTMOUSE", "PRESS", x, y)


def drag_move(k, fx=0.5, fy=0.5):
    x, y = state["xy"]
    vp = next(a for a in bpy.context.window_manager.windows[0].screen.areas if a.type == "VIEW_3D")
    tx, ty = vp.x + int(vp.width * fx), vp.y + int(vp.height * fy)
    ev("MOUSEMOVE", "NOTHING", x + (tx - x) * k // 6, y + (ty - y) * k // 6)
    state["to"] = (tx, ty)


def drag_end():
    ev("LEFTMOUSE", "RELEASE", *state["to"])


def drag_report():
    new = len(bpy.data.objects) - state["n"]
    print("B4D AB DRAG", state["key"].split("|")[-1], "new objects", new,
          "active", getattr(bpy.context.view_layer.objects.active, "name", None),
          tuple(round(v, 2) for v in bpy.context.view_layer.objects.active.location),
          "materials", sorted((o.name, o.active_material.name) for o in bpy.data.objects if getattr(o, "active_material", None)),
          flush=True)


def ab_ctx():
    w = bpy.context.window_manager.windows[0]
    return bpy.context.temp_override(window=w, area=area(), region=region())


def new_folder():
    with ab_ctx():
        print("B4D AB NEWFOLDER", bpy.ops.blenda4d.ab_new_folder("EXEC_DEFAULT", name="Wood"), flush=True)


def folder_dialog():
    with ab_ctx():
        bpy.ops.blenda4d.ab_new_folder("INVOKE_DEFAULT")


def drop_files():
    src = os.path.join(os.path.dirname(LIB), "..", "eng", "inputs")
    src = os.path.normpath(src)
    with ab_ctx():
        print("B4D AB ADDFILES", bpy.ops.blenda4d.ab_add_files("EXEC_DEFAULT", directory=src,
              files=[{"name": n} for n in ("Ring.glb", "Bricks.jpg", "Sky.hdr")]), flush=True)


def wait_added():
    from blenda4d import assets_library as lib
    from blenda4d import assets
    print("B4D AB ADDED busy", lib.busy(), "shown", [a["name"] for a in assets.shown_assets(bpy.context)],
          "failed", lib.failures(), flush=True)


def right_click():
    r = region()
    x, y = r.x + 60, r.y + 60                       # empty space low in the folder column
    ev("MOUSEMOVE", "NOTHING", x, y)
    ev("RIGHTMOUSE", "PRESS", x, y)
    ev("RIGHTMOUSE", "RELEASE", x, y)


def drop_check():
    from blenda4d import assets
    w = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=w, area=area(), region=region()):
        here = assets.BLENDA4D_FH_asset_drop.poll_drop(bpy.context)
    vp = next(a for a in w.screen.areas if a.type == "VIEW_3D")
    with bpy.context.temp_override(window=w, area=vp, region=next(r for r in vp.regions if r.type == "WINDOW")):
        there = assets.BLENDA4D_FH_asset_drop.poll_drop(bpy.context)
    print("B4D AB DROP poll: browser", here, "viewport", there, flush=True)


W = [lambda: None] * 5
done = PLAN.pop()
PLAN += [lambda: toggle("ASSETS")] + W + [lambda: shot("ab_home")]
PLAN += [lambda: open_folder("Props")] + W + [lambda: shot("ab_props"), calib]
PLAN += [lambda: drag_start(2)] + [lambda k=k: drag_move(k, 0.3, 0.3) for k in range(1, 7)] + [
    lambda: shot("ab_drag_mid"), drag_end, lambda: None, drag_report, lambda: shot("ab_drag_done")]
PLAN += [lambda: drag_start(0)] + [lambda k=k: drag_move(k, 0.5, 0.42) for k in range(1, 7)] + [drag_end, lambda: None, drag_report]
PLAN += [lambda: tab("MATERIALS")] + W + [lambda: shot("ab_mats")]
PLAN += [lambda: tab("ALL"), lambda: open_folder("Props"), lambda: None, right_click, lambda: None, lambda: shot("ab_rmb"),
         lambda: ev("ESC", "PRESS", 0, 0), drop_check]
def menu_click():
    r = region()
    x, y = r.x + 60, r.y + 60
    ev("MOUSEMOVE", "NOTHING", x, y)
    ev("RIGHTMOUSE", "PRESS", x, y)
    ev("RIGHTMOUSE", "RELEASE", x, y)


def first_item():
    ev("MOUSEMOVE", "NOTHING", 90, 1000 - 843)
    ev("LEFTMOUSE", "PRESS", 90, 1000 - 843)
    ev("LEFTMOUSE", "RELEASE", 90, 1000 - 843)


PLAN += [menu_click, lambda: None, first_item, lambda: None, lambda: None, lambda: shot("ab_folder_dialog"),
         lambda: ev("ESC", "PRESS", 0, 0), lambda: None,
         new_folder] + W + [lambda: shot("ab_new_folder"), drop_files, lambda: shot("ab_adding")] + [lambda: None] * 25 + [
         wait_added, lambda: shot("ab_added")]
PLAN += [done]
