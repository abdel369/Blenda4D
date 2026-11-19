# One UI run of the Render Settings window (window mode, screenshots):
#   B4D_OUT=<scratch> BLENDER_USER_CONFIG=<scratch>/config Blender --factory-startup --window-geometry 100 60 1700 1000 \
#       --python tools/tests/render_settings_ui.py
import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT = os.environ.get("B4D_OUT", "/tmp")
import blenda4d  # noqa: E402

blenda4d.register()


def log(*a):
    print("B4D", *a, flush=True)


def shot(name, win=None):
    wm = bpy.context.window_manager
    w = win or wm.windows[0]
    if w.screen.is_temporary:                  # a floating window: Blender only allows the window itself as context
        with bpy.context.temp_override(window=w):
            bpy.ops.screen.screenshot(filepath=os.path.join(OUT, name + ".png"))
    else:
        with bpy.context.temp_override(window=w, screen=w.screen, area=w.screen.areas[0]):
            bpy.ops.screen.screenshot(filepath=os.path.join(OUT, name + ".png"))
    log("SHOT", name)


def rs_window():
    from blenda4d import render_settings, roles
    return next((w for w in bpy.context.window_manager.windows
                 if any(roles.role(a) == render_settings.ROLE for a in w.screen.areas)), None)


def open_from_tab():
    w = bpy.context.window_manager.windows[0]
    area = max((a for a in w.screen.areas if a.type == "VIEW_3D"), key=lambda a: a.width * a.height)
    reg = next(r for r in area.regions if r.type == "WINDOW")
    with bpy.context.temp_override(window=w, screen=w.screen, area=area, region=reg):
        log("OPEN", bpy.ops.blenda4d.render_settings())


def report():
    w = rs_window()
    log("RS WINDOW", w is not None, w and (w.width, w.height), w and [(a.type, a.width, a.height) for a in w.screen.areas])
    sc = bpy.context.scene
    log("SETS", [r.name for r in sc.b4d_rsets], "active", sc.b4d_rs_loaded)


def nav():
    from blenda4d import roles
    w = rs_window()
    a = w.screen.areas[0]
    log("NAV", [(r.type, r.width) for r in a.regions])
    try:
        log("HIDE", roles.hide_nav(a, w))
    except Exception as ex:
        log("HIDE ERR", type(ex).__name__, ex)


def redraw():
    w = rs_window()
    if w:
        for a in w.screen.areas:
            a.tag_redraw()


_big = {}


def big_page(on):
    """Draw the page in the main window's viewport area for a full-height screenshot, then put the viewport back."""
    from blenda4d import render_settings, roles
    w = bpy.context.window_manager.windows[0]
    if on:
        render_settings.OPEN_AT_FIRST = {"output", "save", "samples", "motion_blur", "color", "light_paths", "volumes"}
        area = max((a for a in w.screen.areas if a.type == "VIEW_3D"), key=lambda a: a.width * a.height)
        _big["area"] = area
        area.type = "PROPERTIES"
        roles.set_role(area, render_settings.ROLE)
        roles.hide_nav(area, w)
    else:
        _big["area"].type = "VIEW_3D"
    log("ENGINE", bpy.context.scene.render.engine)


def scroll(n):
    w = bpy.context.window_manager.windows[0]
    area = _big["area"]
    reg = next(r for r in area.regions if r.type == "WINDOW")
    with bpy.context.temp_override(window=w, screen=w.screen, area=area, region=reg):
        for _ in range(n):
            bpy.ops.view2d.scroll_down()


def open_sections():
    w = rs_window()
    # make the window bigger so every section fits on the screenshot
    bpy.context.scene.render.engine = "CYCLES"


def add_two():
    bpy.ops.blenda4d.rs_add()
    bpy.ops.blenda4d.rs_duplicate()
    bpy.context.scene.b4d_rsets[2].name = "Final 4K"


def eevee():
    bpy.context.scene.render.engine = "BLENDER_EEVEE"


def off():
    blenda4d.switch.set_mode(False)


def after_off():
    log("AFTER OFF windows", len(bpy.context.window_manager.windows), "rs window", rs_window() is not None)


def page(key):
    wm = bpy.context.window_manager
    from blenda4d import render_settings
    wm.b4d_rs_page = [p[0] for p in render_settings.PAGES].index(key)


def engine(e):
    bpy.context.scene.render.engine = e


def setup_values():
    sc = bpy.context.scene
    add_two()
    sc.b4d_render.frame_range = "CURRENT"
    sc.b4d_render.annotations = "Client review cut, 720p"
    sc.b4d_render.v_preset = "HD720"


def big(name, *steps):
    out = list(steps) + [redraw_main] + [lambda: None] * 6 + [lambda: shot(name), redraw_main, lambda: None, lambda: None, lambda: shot(name)]
    return out


def redraw_main():
    for a in bpy.context.window_manager.windows[0].screen.areas:
        a.tag_redraw()


W = [lambda: None] * 3
PLAN = ([lambda: None] * 30 + [setup_values, open_from_tab] + [lambda: None] * 10 +
        [report, nav, redraw] + W + [lambda: shot("rs_window", rs_window()), redraw] + W + [lambda: shot("rs_window", rs_window())] +
        [lambda: big_page(True)] + W +
        big("page_output", lambda: page("OUTPUT"), lambda: setattr(bpy.context.scene.b4d_render, "show_region", True)) +
        big("page_save", lambda: page("SAVE")) +
        big("page_multipass", lambda: page("MULTIPASS")) +
        big("page_volumes", lambda: page("VOLUMES")) +
        big("page_lightpaths", lambda: engine("CYCLES"), lambda: page("LIGHT_PATHS")) +
        big("page_motion_cycles", lambda: page("MOTION_BLUR")) +
        [lambda: big_page(False), lambda: None, off] + [lambda: None] * 10 + [after_off] +
        [lambda: open(os.path.join(OUT, "done.txt"), "w").write("ok")])
_i = [0]


def tick():
    if _i[0] >= len(PLAN):
        return None
    try:
        PLAN[_i[0]]()
    except Exception:
        import traceback
        traceback.print_exc()
    _i[0] += 1
    return 0.2


bpy.app.timers.register(tick, first_interval=1.0)
