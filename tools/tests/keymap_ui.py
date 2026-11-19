# UI check of the Blenda 4D key map: real key presses (simulated events) in the viewport, then Preferences > Keymap.
#   BLENDER_USER_CONFIG=<scratch> BLENDER_USER_SCRIPTS=<scratch> B4D_OUT=<folder> \
#     Blender --factory-startup --enable-event-simulate --window-geometry 100 60 1700 1000 --python tools/tests/keymap_ui.py
import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT = os.environ.get("B4D_OUT", "/tmp")
import blenda4d  # noqa: E402
from blenda4d import keymap  # noqa: E402

blenda4d.register()
FAIL = []
_orig_unreg = keymap.unregister


def _unreg():
    wm = bpy.context.window_manager
    print("B4D unregister: wm", wm is not None, "windows", len(wm.windows) if wm else -1, flush=True)
    _orig_unreg()
    print("B4D unregister done", flush=True)


keymap.unregister = _unreg


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what, flush=True)
    if not ok:
        FAIL.append(what)


def win():
    return bpy.context.window_manager.windows[0]


def view_area():
    areas = [a for a in win().screen.areas if a.type == "VIEW_3D"]
    return max(areas, key=lambda a: a.width * a.height) if areas else None


def tool():
    return bpy.context.workspace.tools.from_space_view3d_mode("OBJECT", create=False).idname


def ev(t, v, **kw):
    w = win()
    a = view_area()
    x, y = a.x + a.width // 2 + kw.pop("dx", 0), a.y + a.height // 2 + kw.pop("dy", 0)
    w.event_simulate(type=t, value=v, x=x, y=y, **kw)


def press(t, **mods):
    ev(t, "PRESS", **mods)
    ev(t, "RELEASE", **mods)


def r3d():
    return view_area().spaces.active.region_3d


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_start():
    check(bpy.context.window_manager.keyconfigs.active.name == "Blenda_4D", "Blenda mode on: Blenda 4D key map active")
    ev("MOUSEMOVE", "NOTHING")


@step
def s_e():
    press("E")


@step
def s_e_check():
    check(tool() == "builtin.move", f"E -> Move tool ({tool()})")
    press("R")


@step
def s_r_check():
    check(tool() == "builtin.rotate", f"R -> Rotate tool ({tool()})")
    press("T")


@step
def s_t_check():
    check(tool() == "builtin.scale", f"T -> Scale tool ({tool()})")
    press("SPACE")


@step
def s_space_check():
    check(tool() == "builtin.select_box", f"Space -> selection tool ({tool()})")
    check(not bpy.context.screen.is_animation_playing, "Space in the viewport does not play")
    STATE["rot"] = r3d().view_rotation.copy()
    ev("THREE", "PRESS")


@step
def s_orbit_move():
    for i in range(1, 6):
        ev("MOUSEMOVE", "NOTHING", dx=i * 25, dy=i * 10)


@step
def s_orbit_release():
    ev("THREE", "RELEASE", dx=125, dy=50)


@step
def s_orbit_check():
    d = r3d().view_rotation.rotation_difference(STATE["rot"]).angle
    check(d > 0.05, f"hold 3 + move the mouse orbits the view ({d:.3f} rad)")
    STATE["loc"] = r3d().view_location.copy()
    ev("MOUSEMOVE", "NOTHING")
    ev("MIDDLEMOUSE", "PRESS", alt=True)


@step
def s_pan_move():
    for i in range(1, 6):
        ev("MOUSEMOVE", "NOTHING", dx=i * 20, alt=True)


@step
def s_pan_release():
    ev("MIDDLEMOUSE", "RELEASE", dx=100, alt=True)


@step
def s_pan_check():
    d = (r3d().view_location - STATE["loc"]).length
    check(d > 0.01, f"Alt + middle drag pans ({d:.3f})")
    STATE["rot"] = r3d().view_rotation.copy()
    ev("MOUSEMOVE", "NOTHING")
    ev("LEFTMOUSE", "PRESS", alt=True)


@step
def s_alt_orbit_move():
    for i in range(1, 6):
        ev("MOUSEMOVE", "NOTHING", dx=-i * 20, dy=i * 8, alt=True)


@step
def s_alt_orbit_release():
    ev("LEFTMOUSE", "RELEASE", dx=-100, dy=40, alt=True)


@step
def s_alt_orbit_check():
    d = r3d().view_rotation.rotation_difference(STATE["rot"]).angle
    check(d > 0.05, f"Alt + left drag orbits ({d:.3f} rad)")
    STATE["dist"] = r3d().view_distance
    ev("MOUSEMOVE", "NOTHING")
    ev("TWO", "PRESS")


@step
def s_zoom_move():
    for i in range(1, 6):
        ev("MOUSEMOVE", "NOTHING", dx=i * 20, dy=i * 20)


@step
def s_zoom_release():
    ev("TWO", "RELEASE", dx=100, dy=100)


@step
def s_zoom_check():
    d = abs(r3d().view_distance - STATE["dist"])
    check(d > 0.01, f"hold 2 + move zooms ({d:.3f})")
    STATE["dist"] = r3d().view_distance
    ev("MOUSEMOVE", "NOTHING")
    press("F2")


@step
def s_f2_check():
    check(r3d().view_perspective == "ORTHO", f"F2 -> top view ({r3d().view_perspective})")
    press("H")


@step
def s_h_check():
    check(abs(r3d().view_distance - STATE["dist"]) > 1e-4, "H frames everything (view changed)")
    bpy.ops.blenda4d.add_primitive(kind="cube")
    STATE["cube"] = bpy.context.view_layer.objects.active.name
    STATE["mods"] = len(bpy.context.view_layer.objects.active.modifiers)
    STATE["orient"] = bpy.context.scene.transform_orientation_slots[0].type
    press("W")


@step
def s_w_check():
    o = bpy.context.scene.transform_orientation_slots[0].type
    check(o != STATE["orient"], f"W switches world / object axes ({STATE['orient']} -> {o})")
    press("C")


@step
def s_c_check():
    ob = bpy.data.objects.get(STATE["cube"])
    check(STATE["mods"] > 0 and ob is not None and len(ob.modifiers) == 0 and len(ob.data.vertices) == 8,
          f"C makes the cube editable (modifiers {STATE['mods']} -> {len(ob.modifiers) if ob else '?'})")
    n = len(bpy.context.view_layer.objects)
    STATE["n"] = n
    ob = bpy.context.view_layer.objects.active
    if ob is None and bpy.context.view_layer.objects:
        ob = bpy.context.view_layer.objects[0]
        bpy.context.view_layer.objects.active = ob
    if ob:
        ob.select_set(True)
    press("BACK_SPACE")


@step
def s_del_check():
    check(len(bpy.context.view_layer.objects) == STATE["n"] - 1, "Backspace deletes the selected object")
    bpy.ops.screen.userpref_show(section="KEYMAP")


@step
def s_pref_wait():
    pass


@step
def s_prefs_shot():
    wins = bpy.context.window_manager.windows
    pw = next((w for w in wins if any(a.type == "PREFERENCES" for a in w.screen.areas)), None)
    check(pw is not None, "Preferences window opened")
    if pw:
        with bpy.context.temp_override(window=pw):
            bpy.ops.screen.screenshot(filepath=os.path.join(OUT, "prefs_keymap.png"))
    with bpy.context.temp_override(window=wins[0]):
        bpy.ops.screen.screenshot(filepath=os.path.join(OUT, "main.png"))
    check(bpy.context.preferences.keymap.active_keyconfig == "Blenda_4D", "Preferences name Blenda_4D as active key map")


@step
def s_done():
    print("KEYMAP UI", "PASSED" if not FAIL else "FAILED %d %s" % (len(FAIL), FAIL), flush=True)
    bpy.ops.wm.quit_blender()


STATE = {}
_i = [0]


def tick():
    if _i[0] >= len(STEPS):
        return None
    fn = STEPS[_i[0]]
    _i[0] += 1
    try:
        fn()
    except Exception:
        import traceback
        traceback.print_exc()
        FAIL.append(fn.__name__)
    return 0.6 if fn is not s_pref_wait else 2.0


bpy.app.timers.register(tick, first_interval=6.0)
