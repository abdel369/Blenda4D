# UI run for the lights module: the try_ui sample scene, then lights made from the create column and their pages.
#   BLENDER_USER_CONFIG=<scratch> B4D_OUT=<folder> Blender --factory-startup --window-geometry 100 60 1700 1000 \
#       --python tools/tests/lights_ui.py
import importlib.util
import os

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["B4D_STEPS"] = ""
spec = importlib.util.spec_from_file_location("try_ui", os.path.join(ROOT, "tools", "try_ui.py"))
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)
done = ui.PLAN.pop()
W = lambda: bpy.context.window_manager.windows[0]          # noqa: E731


def tab(t):
    bpy.context.window_manager.b4d_am_tab = t
    for a in W().screen.areas:
        a.tag_redraw()


def make(kind):
    with bpy.context.temp_override(window=W()):
        bpy.ops.blenda4d.add_kind(kind=kind)


def ies_picker():
    with bpy.context.temp_override(window=W()):
        print("B4D IES", bpy.ops.blenda4d.create("INVOKE_DEFAULT", group="lights", index=5), flush=True)


def esc():
    w = bpy.context.window_manager.windows[-1]
    try:
        w.event_simulate("ESC", "PRESS")
        w.event_simulate("ESC", "RELEASE")
    except RuntimeError:
        print("B4D ESC skipped: run with --enable-event-simulate to close the picker", flush=True)


def ies_made():
    from blenda4d import lights_ies
    with bpy.context.temp_override(window=W()):
        bpy.ops.blenda4d.light_ies_add(filepath=os.path.join(lights_ies.ensure_files(), "Batwing.ies"))


def group_menu():
    with bpy.context.temp_override(window=W()):
        bpy.ops.wm.call_menu(name="BLENDA4D_MT_create_lights")


def picker_shot():
    w = bpy.context.window_manager.windows[-1]
    with bpy.context.temp_override(window=w):
        bpy.ops.screen.screenshot(filepath=os.path.join(ui.OUT, "ies_picker.png"))


def windows():
    print("B4D WINDOWS", [[(a.type, a.spaces.active.params.directory.decode() if a.spaces.active.params else None)
                           for a in w.screen.areas if a.type == "FILE_BROWSER"] for w in bpy.context.window_manager.windows],
          flush=True)


def report():
    print("B4D OBJECTS", [(o.name, o.type, o.get("b4d_type")) for o in bpy.data.objects], flush=True)


N = lambda k=2: [lambda: None] * k                      # noqa: E731
steps = [lambda: make("target_light"), lambda: tab("OBJECT"), *N(), lambda: ui.shot("light_general"),
         lambda: tab("DETAILS"), *N(), lambda: ui.shot("light_details"),
         lambda: tab("SHADOW"), *N(), lambda: ui.shot("light_shadow"),
         lambda: make("pbr_light"), lambda: tab("DETAILS"), *N(), lambda: ui.shot("pbr_details"),
         lambda: make("sun_light"), lambda: tab("OBJECT"), *N(), lambda: ui.shot("sun_general"),
         ies_picker, *N(3), *N(2), picker_shot, windows, esc, *N(), windows, *N(),
         ies_made, lambda: tab("PROFILE"), *N(), lambda: ui.shot("ies_profile"),
         lambda: ui.select("Area"), lambda: tab("DETAILS"), *N(), lambda: ui.shot("plain_area_details"),
         group_menu, *N(), lambda: ui.shot("lights_group_menu"), esc, report]
ui.PLAN += steps + [done, lambda: bpy.ops.wm.quit_blender()]
