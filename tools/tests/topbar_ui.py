# UI run of the command palette's right half (topbar.py): every button and hold-menu item is run once and checked,
# the hold menus are opened, and switching Blenda off must put the tool settings back.
#   BLENDER_USER_CONFIG=<scratch> B4D_OUT=<scratch> Blender --factory-startup --enable-event-simulate --window-geometry 100 60 1700 1000 \
#       --python tools/tests/topbar_ui.py
# Prints "B4D TB ok ..." per check and "B4D TB FAIL ..." for every check that does not hold.
import os
import runpy

import bpy

os.environ["B4D_STEPS"] = "wait"
HERE = os.path.dirname(os.path.abspath(__file__))
ns = runpy.run_path(os.path.join(HERE, "..", "try_ui.py"))
PLAN, shot, select = ns["PLAN"], ns["shot"], ns["select"]
_keep = {}


def win():
    return bpy.context.window_manager.windows[0]


def ctx():
    return bpy.context.temp_override(window=win(), screen=win().screen)


def check(name, ok):
    print("B4D TB", "ok" if ok else "FAIL", name, flush=True)


def ts():
    return bpy.context.scene.tool_settings


def view():
    from blenda4d import topbar
    with ctx():
        return topbar.main_view(bpy.context)


def op(idname, **kw):
    def go():
        with ctx():
            mod, fn = idname.split(".")
            print("B4D TB run", idname, kw, getattr(getattr(bpy.ops, mod), fn)(**kw), flush=True)
    return go


MENUS = ("snap", "workplane", "symmetry", "solo", "render_view", "render")
def open_menu(m):
    """Open a hold menu (Blender draws it right away: an error in its draw shows as a traceback in the log)."""
    return [op("wm.call_menu", name="BLENDA4D_MT_tb_" + m), lambda: None, lambda: None,
            lambda: win().event_simulate("ESC", "PRESS"), lambda: win().event_simulate("ESC", "RELEASE")]


def first():
    _keep.update(snap=ts().use_snap, axis=ts().use_transform_data_origin, soft=ts().use_proportional_edit_objects,
                 orient=bpy.context.scene.transform_orientation_slots[0].type, pivot=ts().transform_pivot_point,
                 elements=set(ts().snap_elements), target=ts().snap_target)
    bpy.app.handlers.render_init.append(lambda *a: _keep.__setitem__("torus_hidden", bpy.data.objects["Torus"].hide_render))
    bpy.context.scene.render.resolution_percentage = 5


def z_axis():
    return bpy.context.scene.cursor.matrix.to_3x3().col[2]


def near(a, b, eps=1e-4):
    return all(abs(x - y) < eps for x, y in zip(a, b))


steps = [first,
         op("blenda4d.tb_axis"), lambda: check("axis on", ts().use_transform_data_origin),
         op("blenda4d.tb_axis"), lambda: check("axis off", not ts().use_transform_data_origin),
         op("blenda4d.tb_snap"), lambda: check("snap on", ts().use_snap != _keep["snap"]),
         op("blenda4d.tb_snap_to", element="VERTEX"), lambda: check("snap point", "VERTEX" in ts().snap_elements),
         op("blenda4d.tb_snap_to", element="EDGE_MIDPOINT"), lambda: check("snap mid point", "EDGE_MIDPOINT" in ts().snap_elements),
         op("blenda4d.tb_snap_to", element="VOLUME"), lambda: check("snap volume", "VOLUME" in ts().snap_elements),
         op("blenda4d.tb_snap_to", element="CLOSEST"), lambda: check("snap nearest toggles", ts().snap_target != _keep["target"]),
         op("blenda4d.tb_snap_to", element="INCREMENT"),
         lambda: check("snap grid toggles", ("INCREMENT" in ts().snap_elements) != ("INCREMENT" in _keep["elements"])),
         op("blenda4d.tb_soft"), lambda: check("soft on (object mode)", ts().use_proportional_edit_objects),
         op("blenda4d.tb_workplane"),
         lambda: check("workplane mode", bpy.context.scene.transform_orientation_slots[0].type == "CURSOR" and ts().transform_pivot_point == "CURSOR"),
         op("blenda4d.tb_workplane_set", how="X"), lambda: check("locked X", near(z_axis(), (1, 0, 0))),
         op("blenda4d.tb_workplane_set", how="Z"), lambda: check("locked Z (Blender Y)", near(z_axis(), (0, 1, 0))),
         op("blenda4d.tb_workplane_set", how="Y"), lambda: check("locked Y (floor)", near(z_axis(), (0, 0, 1))),
         op("blenda4d.tb_workplane_set", how="CAMERA"),
         lambda: check("camera", near(bpy.context.scene.cursor.matrix.to_quaternion(), view()[2].region_3d.view_rotation, 1e-3)
                       or near(-bpy.context.scene.cursor.matrix.to_quaternion(), view()[2].region_3d.view_rotation, 1e-3)),
         op("blenda4d.tb_workplane_set", how="PLANAR"),
         lambda: check("planar is a world axis", max(abs(c) for c in z_axis()) > 0.999),
         lambda: select("Cube"), op("blenda4d.tb_workplane_set", how="TO_SELECTION"),
         lambda: check("workplane to selection", near(bpy.context.scene.cursor.location, bpy.data.objects["Cube"].matrix_world.translation)),
         op("blenda4d.tb_workplane_set", how="X"), lambda: setattr(bpy.context.scene.cursor, "location", (5, 5, 0)),
         lambda: select("Sphere"), op("blenda4d.tb_workplane_set", how="SELECTION_TO"),
         lambda: check("selection to workplane", near(bpy.data.objects["Sphere"].matrix_world.translation, (5, 5, 0))
                       and near(bpy.data.objects["Sphere"].matrix_world.to_3x3().normalized().col[2], (1, 0, 0))),
         lambda: select("Cube"),
         op("blenda4d.tb_symmetry", axis="X"), lambda: check("symmetry X", bpy.data.objects["Cube"].data.use_mirror_x),
         op("blenda4d.tb_symmetry", axis="Y"), lambda: check("symmetry Y (Blender Z)", bpy.data.objects["Cube"].data.use_mirror_z),
         op("blenda4d.tb_symmetry", axis="Y"), op("blenda4d.tb_symmetry", axis="X"),
         lambda: check("symmetry off", not bpy.data.objects["Cube"].data.use_mirror_x),
         op("blenda4d.tb_solo"), lambda: None,
         lambda: check("solo active", view()[2].local_view is not None
                       and bpy.data.objects["Cube"].local_view_get(view()[2]) and not bpy.data.objects["Sphere"].local_view_get(view()[2])),
         lambda: shot("tb_solo"),
         op("blenda4d.tb_solo"), lambda: None, lambda: check("solo off", view()[2].local_view is None),
         lambda: select("Group"), op("blenda4d.tb_solo", which="HIERARCHY"), lambda: None,
         lambda: check("solo hierarchy", view()[2].local_view is not None and bpy.data.objects["Cube"].local_view_get(view()[2])
                       and not bpy.data.objects["Torus"].local_view_get(view()[2])),
         op("blenda4d.tb_solo"), lambda: None,
         op("blenda4d.tb_render_view"), lambda: check("render view on", view()[2].shading.type == "RENDERED"),
         lambda: shot("tb_render_view"),
         op("blenda4d.tb_render_view"), lambda: check("render view off", view()[2].shading.type != "RENDERED"),
         op("blenda4d.tb_render_view", how="REGION"), lambda: check("render region on", bpy.context.scene.render.use_border),
         lambda: win().event_simulate("ESC", "PRESS"), lambda: win().event_simulate("ESC", "RELEASE"),
         lambda: select("Cube"), op("blenda4d.tb_render_view", how="SELECTION"),
         lambda: None] + [lambda: None] * 12 + [
         lambda: check("render selection hid the others while rendering", _keep.get("torus_hidden") is True),
         lambda: check("render selection puts them back", not bpy.data.objects["Torus"].hide_render),
         *[st for m in MENUS for st in open_menu(m)],
         op("blenda4d.tb_axis"), lambda: None, lambda: shot("tb_palette"),
         lambda: __import__("blenda4d").switch.set_mode(False)] + [lambda: None] * 6 + [
         lambda: check("off: snap back", ts().use_snap == _keep["snap"]),
         lambda: check("off: axis back", ts().use_transform_data_origin == _keep["axis"]),
         lambda: check("off: soft back", ts().use_proportional_edit_objects == _keep["soft"]),
         lambda: check("off: snap elements back", set(ts().snap_elements) == _keep["elements"]),
         lambda: check("off: orientation back", bpy.context.scene.transform_orientation_slots[0].type == _keep["orient"]),
         lambda: check("off: pivot back", ts().transform_pivot_point == _keep["pivot"]),
         lambda: check("off: render region back", not bpy.context.scene.render.use_border),
         lambda: __import__("blenda4d").switch.set_mode(True)] + [lambda: None] * 8 + [lambda: shot("tb_on_again")]
PLAN[-1:-1] = steps
