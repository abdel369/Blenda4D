# Run Blenda 4D from this checkout in a plain Blender and take screenshots of its layout (a test harness).
#   BLENDER_USER_CONFIG=<scratch> Blender --window-geometry 100 60 1700 1000 --python tools/try_ui.py
# Environment: B4D_OUT (folder for screenshots), B4D_STEPS (comma list: cube,cloner,light,mats,assets,off,on).
import os
import sys
import traceback

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.environ.get("B4D_OUT", "/tmp")
STEPS = [s for s in os.environ.get("B4D_STEPS", "shot").split(",") if s]
import blenda4d  # noqa: E402

blenda4d.register()


def _color(m, rgba):
    m.diffuse_color = rgba
    if m.node_tree:
        bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf:
            bsdf.inputs["Base Color"].default_value = rgba


def scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    col = bpy.context.scene.collection
    bpy.ops.mesh.primitive_plane_add(size=40)
    bpy.context.object.name = "Floor"
    null = bpy.data.objects.new("Group", None)
    col.objects.link(null)
    bpy.ops.blenda4d.add_primitive(kind="cube")
    cube = bpy.context.object
    cube.location = (-2, 0, 1)
    cube.parent = null
    m = bpy.data.materials.new("Orange")
    _color(m, (0.9, 0.45, 0.15, 1))
    cube.data.materials.append(m)
    bpy.ops.blenda4d.add_primitive(kind="sphere")
    s = bpy.context.object
    s.location = (2, -1, 1)
    m2 = bpy.data.materials.new("Blue")
    _color(m2, (0.25, 0.45, 0.9, 1))
    s.data.materials.append(m2)
    bpy.ops.blenda4d.add_primitive(kind="torus")
    bpy.context.object.location = (0, 3, 0.4)
    bpy.ops.object.light_add(type="AREA", location=(3, -4, 6))
    bpy.ops.object.camera_add(location=(10, -10, 7))
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    cube.select_set(True)
    bpy.context.view_layer.objects.active = cube


def shot(name):
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
        bpy.ops.screen.screenshot(filepath=os.path.join(OUT, name + ".png"))
    print("B4D SHOT", name, flush=True)


def select(name):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob = bpy.data.objects[name]
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def toggle(name):
    from blenda4d import build, roles
    w = bpy.context.window_manager.windows[0]
    build.toggle(w, name, not roles.areas(w.screen, name))


def om_region():
    from blenda4d import roles
    a = roles.areas(bpy.context.window_manager.windows[0].screen, "OBJECTS")[0]
    return next(r for r in a.regions if r.type == "WINDOW")


def row_y(i):
    from blenda4d import managers
    r = om_region()
    h = managers.row_height()
    vy = -(managers.rows_top() + i + 0.5) * h
    return r.y + int(r.view2d.view_to_region(0, vy, clip=False)[1])


def row_index(name):
    from blenda4d import managers
    return [o.name for o, d in managers.visible_rows(bpy.context)].index(name)


def ev(t, v, x, y):
    bpy.context.window_manager.windows[0].event_simulate(t, v, x=x, y=y)


def calib():
    from blenda4d import managers
    r = om_region()
    rows = [o.name for o, d in managers.visible_rows(bpy.context)]
    print("B4D REGION", r.x, r.y, r.width, r.height, "rowh", managers.row_height(), flush=True)
    print("B4D ROWS", [(n, 1000 - row_y(i)) for i, n in enumerate(rows)], flush=True)


def drag_steps(src, dst):
    st = {}

    def press():
        r = om_region()
        st["x"] = r.x + int(os.environ.get("B4D_DRAGX", "70"))
        st["y0"] = row_y(row_index(src))
        st["y1"] = row_y(row_index(dst)) if dst else row_y(len([1 for _ in __import__("blenda4d").managers.visible_rows(bpy.context)]) + 1)
        ev("MOUSEMOVE", "NOTHING", st["x"], st["y0"])
        ev("LEFTMOUSE", "PRESS", st["x"], st["y0"])
    out = [press]
    for k in range(1, 7):
        out.append(lambda k=k: ev("MOUSEMOVE", "NOTHING", st["x"] + k, st["y0"] + (st["y1"] - st["y0"]) * k // 6))
    out += [lambda: shot("drag_mid_" + src), lambda: ev("LEFTMOUSE", "RELEASE", st["x"] + 6, st["y1"]), lambda: None,
            lambda: print("B4D PARENT", src, "->", getattr(bpy.data.objects[src].parent, "name", None),
                          "drop", repr(bpy.context.window_manager.b4d_om_drop), flush=True), lambda: shot("drag_done_" + src)]
    return out


PLAN = [lambda: None] * 4 + [scene] + [lambda: None] * 3
for s in STEPS:
    if s == "shot":
        PLAN += [lambda: shot("main")]
    elif s in ("cube", "light", "camera", "sphere", "torus"):
        n = {"cube": "Cube", "light": "Area", "camera": "Camera", "sphere": "Sphere", "torus": "Torus"}[s]
        PLAN += [lambda n=n: select(n), lambda: setattr(bpy.context.window_manager, "b4d_am_tab", "OBJECT"), lambda: None, lambda s=s: shot("sel_" + s)]
    elif s in ("mats", "assets"):
        PLAN += [lambda s=s: toggle({"mats": "MATERIALS", "assets": "ASSETS"}[s])] + [lambda: None] * 6 + [lambda s=s: shot("col_" + s)]
    elif s.startswith("click:"):
        n = s[6:]
        PLAN += [lambda n=n: (ev("MOUSEMOVE", "NOTHING", om_region().x + 200, row_y(row_index(n))),
                              ev("LEFTMOUSE", "PRESS", om_region().x + 200, row_y(row_index(n))),
                              ev("LEFTMOUSE", "RELEASE", om_region().x + 200, row_y(row_index(n)))), lambda: None,
                 lambda n=n: print("B4D ACTIVE", bpy.context.view_layer.objects.active.name, flush=True), lambda n=n: shot("click_" + n)]
    elif s.startswith("rename:"):
        n, new = s[7:].split(">")

        def dbl(n=n):
            x, y = om_region().x + 200, row_y(row_index(n))
            ev("MOUSEMOVE", "NOTHING", x, y)
            for _ in range(2):
                ev("LEFTMOUSE", "PRESS", x, y)
                ev("LEFTMOUSE", "RELEASE", x, y)

        def typ(new=new):
            w = bpy.context.window_manager.windows[0]
            for ch in new:
                w.event_simulate("A", "PRESS", unicode=ch)
                w.event_simulate("A", "RELEASE")
        PLAN += [dbl, lambda: None, lambda n=n: shot("rename_popup_" + n), lambda: bpy.context.window_manager.windows[0].event_simulate("A", "PRESS", oskey=True),
                 typ, lambda: shot("rename_typed_" + n),
                 lambda: bpy.context.window_manager.windows[0].event_simulate("RET", "PRESS"), lambda: None,
                 lambda: print("B4D NAMES", sorted(o.name for o in bpy.data.objects), flush=True), lambda n=n: shot("rename_done_" + n)]
    elif s.startswith("zoom:"):
        f = float(s[5:])

        def z(f=f):
            from blenda4d import roles
            w = bpy.context.window_manager.windows[0]
            for name in ("MODES", "CREATE"):
                for a in roles.areas(w.screen, name):
                    r = next(r for r in a.regions if r.type == "WINDOW")
                    with bpy.context.temp_override(window=w, area=a, region=r):
                        print("B4D ZOOM", name, [bpy.ops.view2d.zoom_in() for _ in range(int(f))], r.view2d.view_to_region(0, -100, clip=False), flush=True)
        PLAN += [z, lambda: None, lambda: None, lambda f=f: shot("zoom_%s" % f)]
    elif s == "matinfo":
        PLAN += [lambda: print("B4D MATS", [(m.name, m.users, m.is_grease_pencil) for m in bpy.data.materials], flush=True)]
    elif s.startswith("mmview:"):
        v = s[7:]
        PLAN += [lambda v=v: setattr(bpy.context.window_manager, "b4d_mm_view", v), lambda: None, lambda: None, lambda: None, lambda: None,
                 lambda v=v: shot("mm_" + v)]
    elif s.startswith("mmsearch:"):
        t = s[9:]
        PLAN += [lambda: setattr(bpy.context.window_manager, "b4d_mm_search", True),
                 lambda t=t: setattr(bpy.context.window_manager, "b4d_mm_filter", t), lambda: None, lambda: shot("mm_search")]
    elif s.startswith("mmsel:"):
        PLAN += [lambda n=s[6:]: setattr(bpy.context.window_manager, "b4d_material", n)]
    elif s == "wait":
        PLAN += [lambda: None] * 8
    elif s == "calib":
        PLAN += [calib]
    elif s.startswith("drag:"):
        a, b = s[5:].split(">")
        PLAN += drag_steps(a, b or None)
    elif s == "off":
        PLAN += [lambda: blenda4d.switch.set_mode(False)] + [lambda: None] * 6 + [lambda: print("B4D WORKSPACES", [w.name for w in bpy.data.workspaces], flush=True), lambda: shot("off")]
    elif s == "on":
        PLAN += [lambda: blenda4d.switch.set_mode(True)] + [lambda: None] * 8 + [lambda: shot("on_again")]
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
