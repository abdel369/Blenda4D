# SPDX-License-Identifier: GPL-3.0-or-later
"""F1-F4 switch between the Perspective, Top, Right and Front views, and each one comes back where you left it."""
import math

import bpy
from mathutils import Euler

from . import build, quadview, viewmenus

START_ROTATION = Euler((math.radians(65.0), 0.0, math.radians(35.0))).to_quaternion()

VIEWS = [("PERSP", "Perspective", "Perspective view"),
         ("TOP", "Top", "Top view"),
         ("RIGHT", "Right", "Right view"),
         ("FRONT", "Front", "Front view")]


def _region(area):
    return next((r for r in area.regions if r.type == "WINDOW"), None)


def _start_perspective(window, area):
    rv = area.spaces.active.region_3d
    rv.lock_rotation = False
    rv.view_perspective = "PERSP"
    rv.view_rotation = START_ROTATION
    try:
        with bpy.context.temp_override(window=window, screen=window.screen, area=area, region=_region(area)):
            bpy.ops.view3d.view_all(center=False)
    except RuntimeError:
        pass


def _leave_scene_camera(area):
    sp = area.spaces.active
    if sp.region_3d.view_perspective == "CAMERA":
        viewmenus.back_to_editor(area, sp)


def switch_single(window, area, target):
    current = quadview.corner_of_single(area)
    if current == target:
        if target == "PERSP":
            _leave_scene_camera(area)
        return

    quadview._saved[current] = quadview.state(area)
    saved = quadview._saved.get(target)
    if saved:
        quadview.apply(area, saved)
    elif quadview.AXIS[target]:
        quadview._axis_view(window, area, target)
    else:
        _start_perspective(window, area)

    if target == "PERSP":
        _leave_scene_camera(area)
        area.spaces.active.region_3d.lock_rotation = False
    quadview._saved["ALONE"] = target
    area.tag_redraw()


def _run(context, target):
    screen = context.screen
    views = quadview.views(screen)
    if len(views) > 1:
        keep = next((a for a in views if quadview.corner_of(a, screen) == target), None)
        if keep:
            build.run_steps(quadview.expand_steps(context.window, keep))
    else:
        switch_single(context.window, context.area, target)
    return {"FINISHED"}


def _make_operator(target, label, description):
    def execute(self, context):
        return _run(context, target)

    def poll(cls, context):
        return context.area is not None and context.area.type == "VIEW_3D" and not build.busy()

    return type(f"BLENDA4D_OT_view_{target.lower()}", (bpy.types.Operator,), {
        "bl_idname": f"blenda4d.view_{target.lower()}",
        "bl_label": label,
        "bl_description": description,
        "poll": classmethod(poll),
        "execute": execute,
    })


CLASSES = [_make_operator(*v) for v in VIEWS]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
