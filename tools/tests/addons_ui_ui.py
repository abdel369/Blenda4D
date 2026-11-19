# UI run of the Add-ons menu with an outside add-on enabled (name in B4D_TEST_ADDON, found on BLENDER_USER_SCRIPTS):
# the Add-ons menu, its Add Menu Items popup (an item is picked with the keyboard and must make its object, also one
# that needs a viewport), the viewport sidebar (Add-on Panels, then N), the Blender Properties window, the Attribute
# Manager's Edit menu; then the switch off and on.
#   BLENDER_USER_CONFIG=<scratch> BLENDER_USER_SCRIPTS=<scratch>/scripts B4D_OUT=<scratch> B4D_TEST_ADDON=my_test_addon \
#     Blender --factory-startup --enable-event-simulate --window-geometry 100 60 1700 1000 --python tools/tests/addons_ui_ui.py
import os
import runpy

import addon_utils
import bpy

os.environ["B4D_STEPS"] = "wait"
HERE = os.path.dirname(os.path.abspath(__file__))
ns = runpy.run_path(os.path.join(HERE, "..", "try_ui.py"))
PLAN, shot = ns["PLAN"], ns["shot"]
ADDON = os.environ.get("B4D_TEST_ADDON", "")
if ADDON:
    addon_utils.enable(ADDON, default_set=True)


def win():
    return bpy.context.window_manager.windows[0]


def check(cond, what):
    print("B4D AOUI", "ok" if cond else "FAIL", what, flush=True)


def area_of(kind):
    return max((a for a in win().screen.areas if a.type == kind), key=lambda a: a.width * a.height)


def ov(kind):
    a = area_of(kind)
    return bpy.context.temp_override(window=win(), screen=win().screen, area=a,
                                     region=next(r for r in a.regions if r.type == "WINDOW"))


_mouse = [0, 0]


def key(t):
    win().event_simulate(t, "PRESS", x=_mouse[0], y=_mouse[1])
    win().event_simulate(t, "RELEASE", x=_mouse[0], y=_mouse[1])


def mouse_to_view():
    a = area_of("VIEW_3D")
    _mouse[:] = [a.x + a.width // 3, a.y + a.height // 2]
    win().event_simulate("MOUSEMOVE", "NOTHING", x=_mouse[0], y=_mouse[1])


def capture(name, small=False):
    """The window as it is on screen, popups included (Blender's own screenshot leaves menus out). macOS only:
    B4D_WINID is a helper printing "<window id> <layer> <width> <height>" for a process's windows."""
    tool = os.environ.get("B4D_WINID")
    if not tool:
        return shot(name)
    import subprocess
    rows = [r.split() for r in subprocess.run([tool, str(os.getpid())], capture_output=True, text=True).stdout.splitlines()]
    rows = [r for r in rows if len(r) >= 4 and r[1] == "0" and float(r[2]) > 200 and float(r[3]) > 100]
    if not rows:
        return shot(name)
    print("B4D AOUI windows", rows, flush=True)
    if small:                      # the floating window: the one closest to its size in Blender
        w = bpy.context.window_manager.windows[-1]
        rows.sort(key=lambda r: abs(float(r[2]) - w.width) + abs(float(r[3]) - w.height))
        wid = rows[0][0]
    else:
        wid = max(rows, key=lambda r: float(r[2]) * float(r[3]))[0]
    subprocess.run(["screencapture", "-x", "-o", "-l", wid, os.path.join(ns["OUT"], name + ".png")])
    print("B4D SHOT", name, flush=True)


def call_menu(name, kind="VIEW_3D"):
    def go():
        a = area_of(kind)
        r = next(r for r in a.regions if r.type == "WINDOW")
        with bpy.context.temp_override(window=win(), screen=win().screen, area=a, region=r):
            bpy.ops.wm.call_menu(name=name)
    return go


def addons_popup():
    a = area_of("PROPERTIES")          # as from the main menu bar: not the viewport
    with bpy.context.temp_override(window=win(), screen=win().screen, area=a, region=a.regions[0]):
        print("B4D AOUI popup", bpy.ops.blenda4d.addons_menu("INVOKE_DEFAULT", menu="BLENDA4D_MT_addons_add"), flush=True)


def pick(downs):
    def go():
        for _ in range(downs):
            key("DOWN_ARROW")
        key("RET")
    return go


def has(name):
    return lambda: check(any(o.name.startswith(name) for o in bpy.data.objects),
                         f"menu item made {name} {sorted(o.name for o in bpy.data.objects)}")


def sidebar(want, tag):
    return lambda: check(area_of("VIEW_3D").spaces.active.show_region_ui == want, f"{tag}: sidebar shown = {want}")


def panels():
    with ov("VIEW_3D"):
        bpy.ops.blenda4d.addon_panels()


def props():
    with ov("VIEW_3D"):
        print("B4D AOUI props", bpy.ops.blenda4d.blender_properties(), flush=True)


def props_check():
    wins = bpy.context.window_manager.windows
    check(len(wins) == 2, f"Properties window open ({len(wins)} windows)")
    if len(wins) == 2:
        a = wins[1].screen.areas[0]
        from blenda4d import roles
        check(a.type == "PROPERTIES" and roles.role(a) is None, f"plain Properties editor, tab {a.spaces.active.context}")
        print("B4D AOUI props window", wins[1].width, wins[1].height, wins[1].screen.is_temporary, flush=True)


def props_shot():
    capture("ao_props_window", small=True)


def keymap_n():
    kc = bpy.context.window_manager.keyconfigs.active
    hits = []
    for km in kc.keymaps:
        for kmi in km.keymap_items:
            if kmi.type == "N" and not (kmi.ctrl or kmi.alt or kmi.shift or kmi.oskey) and kmi.active:
                hits.append((km.name, kmi.idname, getattr(kmi.properties, "data_path", "")))
    print("B4D AOUI keymap", kc.name, "N:", hits, flush=True)


def last_op():
    ops = bpy.context.window_manager.operators
    a = area_of("VIEW_3D")
    print("B4D AOUI last op", ops[-1].bl_idname if len(ops) else None, "mouse", _mouse, "view", a.x, a.y, a.width, a.height, flush=True)


W = [lambda: None] * 3
done = PLAN.pop()
PLAN += [keymap_n, mouse_to_view, call_menu("BLENDA4D_MT_main_addons")] + W + [lambda: capture("ao_menu"), lambda: key("ESC"),
         mouse_to_view, addons_popup] + W + [lambda: capture("ao_add_popup"), pick(1)] + W + [has("ViewThing"),
         mouse_to_view, addons_popup] + W + [lambda: key("DOWN_ARROW"), lambda: capture("ao_add_popup_2"), pick(0)] + W + [has("TestThing"),
         lambda: shot("ao_after_add"),
         panels] + W + [sidebar(True, "Add-on Panels"), lambda: capture("ao_sidebar"),
         mouse_to_view, lambda: None, lambda: key("N"), last_op, sidebar(False, "N key")] + W + [sidebar(False, "N key (later)"),
         lambda: key("N"), sidebar(True, "N key again")] + W + [sidebar(True, "N key again"),
         call_menu("BLENDA4D_MT_view_panel", "VIEW_3D")] + W + [lambda: capture("ao_panel_menu"), lambda: key("ESC"),
         panels] + W + [sidebar(False, "Add-on Panels again"),
         props] + W * 2 + [props_check, lambda: capture("ao_props_main")] + W * 2 + [props_shot] + W + [props_shot,
         lambda: ns["blenda4d"].switch.set_mode(False)] + W * 3 + [
         lambda: check(len(bpy.context.window_manager.windows) == 1, "off: Properties window closed"),
         lambda: check(hasattr(bpy.types, "MYADDON_PT_sidebar") or not ADDON, "off: add-on panels untouched"),
         lambda: shot("ao_off"),
         lambda: ns["blenda4d"].switch.set_mode(True)] + W * 4 + [sidebar(False, "on again"),
         lambda: shot("ao_on"), done]
