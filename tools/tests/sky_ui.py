# UI run of the Sky object: the sample scene from tools/try_ui.py, then a Sky, a Physical Sky and an HDRI, each with
# its Attribute Manager page shown and the viewport in Material view, screenshotted.
#   BLENDER_USER_CONFIG=<scratch> B4D_OUT=<scratch> Blender --factory-startup --window-geometry 100 60 1700 1000 \
#       --python tools/tests/sky_ui.py
import os
import runpy

import bpy

os.environ["B4D_STEPS"] = "wait"
HERE = os.path.dirname(os.path.abspath(__file__))
ns = runpy.run_path(os.path.join(HERE, "..", "try_ui.py"))
PLAN, shot = ns["PLAN"], ns["shot"]
OUT = os.environ.get("B4D_OUT", "/tmp")


def ctx():
    w = bpy.context.window_manager.windows[0]
    return bpy.context.temp_override(window=w, screen=w.screen)


def add(kind):
    with ctx():
        bpy.ops.blenda4d.add_kind(kind=kind)
    bpy.context.window_manager.b4d_am_tab = "OBJECT"


def material_view():
    for a in bpy.context.window_manager.windows[0].screen.areas:
        if a.type == "VIEW_3D":
            a.spaces.active.shading.type = "MATERIAL"


def hdri():
    img = bpy.data.images.new("Studio HDRI", 256, 128, float_buffer=True)
    px = []
    for y in range(128):
        for x in range(256):
            t = y / 128.0
            px += [0.4 + 0.6 * t, 0.5 + 0.4 * t, 0.9, 1.0] if (x // 32) % 2 else [0.9 * t, 0.6 * t, 0.3, 1.0]
    img.pixels = px
    bpy.context.scene.b4d_sky_image = img


def report():
    from blenda4d import sky
    sc = bpy.context.scene
    print("B4D SKY", sc.world.name, [n.name for n in sc.world.node_tree.nodes], "views", sc.get("b4d_sky_views"), flush=True)


done = PLAN.pop()
PLAN += [material_view, lambda: add("sky"), lambda: None, lambda: None, report, lambda: shot("sky_page"),
         lambda: add("physical_sky"), lambda: None, lambda: None, report, lambda: shot("physical_sky_page"),
         hdri, lambda: None, lambda: None, report, lambda: shot("sky_hdri_page"),
         lambda: add("floor"), lambda: None, lambda: shot("floor_page"), done]
