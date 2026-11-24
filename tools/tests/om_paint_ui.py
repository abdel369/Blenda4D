# UI run of painting the Object Manager's visibility dots: press on a dot and drag down the rows, plain and with
# Alt (Option on a Mac): every row passed takes the first row's new state; with Alt both dots. Also the checks.
#   BLENDER_USER_CONFIG=<scratch> B4D_OUT=<scratch> \
#     Blender --factory-startup --enable-event-simulate --window-geometry 100 60 1700 1000 --python tools/tests/om_paint_ui.py
import os
import sys
import traceback

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import blenda4d  # noqa: E402

blenda4d.register()
from blenda4d import managers as M, roles, switch  # noqa: E402

OUT = os.environ.get("B4D_OUT", "/tmp")
NAMES = ("A", "B", "C", "D")
steps, results = [], []


def win():
    return bpy.context.window_manager.windows[0]


def om_area():
    return next(a for a in win().screen.areas if a.type == "PROPERTIES" and roles.role(a) == "OBJECTS")


def dot_xy(i, render):
    """Window coordinates of row i's upper (viewport) or lower (render) dot, or its check."""
    a = om_area(); r = next(x for x in a.regions if x.type == "WINDOW")
    with bpy.context.temp_override(window=win(), area=a, region=r):
        rows = M.visible_rows(bpy.context)
        sx = M.status_x(bpy.context, r, rows)
        b, t = M._row_y(r, i)
    x = r.x + sx + 2
    y = r.y + (b + (t - b) * (0.25 if render else 0.75))
    return int(x), int(y), rows


def state():
    return {n: (M.vis_state(bpy.data.objects[n], "hide_viewport"), M.vis_state(bpy.data.objects[n], "hide_render")) for n in NAMES}


def setup():
    switch.set_mode(True)
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    for n in reversed(NAMES):
        o = bpy.data.objects.new(n, bpy.data.meshes.new(n)); bpy.context.scene.collection.objects.link(o)
    for a in win().screen.areas:
        a.tag_redraw()


def stroke(render, alt):
    def go():
        x, y, rows = dot_xy(0, render)
        print("ROWS", [r[0].name for r in rows], "start", x, y, flush=True)
        w = win()
        w.event_simulate("MOUSEMOVE", "NOTHING", x=x, y=y)
        if alt:
            w.event_simulate("LEFT_ALT", "PRESS", x=x, y=y)        # held like a hand holds it (Option on a Mac)
        w.event_simulate("LEFTMOUSE", "PRESS", x=x, y=y, alt=alt)
        _, ylast, _ = dot_xy(len(NAMES) - 1, render)
        for k in range(1, 13):
            w.event_simulate("MOUSEMOVE", "NOTHING", x=x, y=int(y + (ylast - y) * k / 12), alt=alt)
        w.event_simulate("LEFTMOUSE", "RELEASE", x=x, y=ylast, alt=alt)
        if alt:
            w.event_simulate("LEFT_ALT", "RELEASE", x=x, y=ylast)
    return go


def alt_click(render):
    def go():
        x, y, _ = dot_xy(1, render); w = win()
        w.event_simulate("MOUSEMOVE", "NOTHING", x=x, y=y)
        w.event_simulate("LEFT_ALT", "PRESS", x=x, y=y)
        w.event_simulate("LEFTMOUSE", "PRESS", x=x, y=y, alt=True); w.event_simulate("LEFTMOUSE", "RELEASE", x=x, y=y, alt=True)
        w.event_simulate("LEFT_ALT", "RELEASE", x=x, y=y)
    return go


def check_drag():
    def go():
        x, y, _ = dot_xy(0, False); a = om_area(); r = next(q for q in a.regions if q.type == "WINDOW")
        x += int(M._unit(r) + 4); _, ylast, _ = dot_xy(len(NAMES) - 1, False); w = win()
        w.event_simulate("MOUSEMOVE", "NOTHING", x=x, y=y); w.event_simulate("LEFTMOUSE", "PRESS", x=x, y=y)
        for k in range(1, 13):
            w.event_simulate("MOUSEMOVE", "NOTHING", x=x, y=int(y + (ylast - y) * k / 12))
        w.event_simulate("LEFTMOUSE", "RELEASE", x=x, y=ylast)
    return go


def check(label, want):
    def go():
        s = state()
        ok = all(want(v) for v in s.values())
        results.append((label, ok, s))
        print("OMPAINT", "ok  " if ok else "FAIL", label, s, flush=True)
    return go


def reset():
    for n in NAMES:
        for a in ("hide_viewport", "hide_render"):
            M.set_vis(bpy.data.objects[n], a, 0)


steps += [setup, reset, stroke(True, False), check("drag down the render dots", lambda v: v[1] == 1 and v[0] == 0),
          reset, stroke(True, True), check("Alt-drag down the render dots sets both", lambda v: v == (1, 1)),
          reset, stroke(False, True), check("Alt-drag down the viewport dots sets both", lambda v: v == (1, 1)),
          reset, alt_click(True), lambda: results.append(("Alt-click one dot sets both", state()["B"] == (1, 1), state())) or print("OMPAINT", "ok  " if state()["B"] == (1, 1) else "FAIL", "Alt-click one dot sets both", state(), flush=True),
          reset, check_drag(), lambda: print("OMPAINT", "ok  " if all(not bpy.data.objects[n].b4d_enabled for n in NAMES) else "FAIL", "drag down the checks", [bpy.data.objects[n].b4d_enabled for n in NAMES], flush=True)]


def tick():
    if not steps:
        bpy.ops.wm.quit_blender(); return None
    try:
        steps.pop(0)()
    except Exception:
        traceback.print_exc(); steps.clear()
    return 1.0


bpy.app.timers.register(tick, first_interval=4)
