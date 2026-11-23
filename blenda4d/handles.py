# SPDX-License-Identifier: GPL-3.0-or-later
"""Object handles: the yellow dots on a selected object that you drag in the viewport to change its settings
(a Cloner's radius or size, a field's radius...). The Attribute Manager follows live; Escape puts the value back;
each drag is one undo step.

A module adds handles for its objects with provide(fn): fn(ob) returns a list of Handle or None. A handle sits at a
point in the object's own space and moves along a direction there (or freely in the view's plane when the direction is
None); dragging calls set(value) with the new place (a Vector in the object's space) and the place it started."""
import math

import bpy
from bpy_extras import view3d_utils
from mathutils import Vector, geometry

DOT = (253 / 255, 228 / 255, 115 / 255, 1.0)     # the handle yellow
INNER = (0.62, 0.38, 1.0, 1.0)                   # an Inner Offset handle is purple
HOT = (1.0, 1.0, 1.0, 1.0)
DOT_R, HIT = 4.0, 10
_providers = []
_draws = []
_keys = []
_shown = {}                                      # area pointer -> [(x, y, handle)] in region pixels
_drag = [None]


class Handle:
    def __init__(self, name, at, set, axis=None, label=None, colour=DOT, readout=None):
        self.name = name                # what it sets, for the readout ("Radius")
        self.at = Vector(at)            # where it sits, in the object's own space
        self.axis = Vector(axis).normalized() if axis is not None else None
        self.set = set                  # set(new_place, start_place)
        self.colour = colour
        self.readout = readout          # () -> text while dragging


def provide(fn):
    if fn not in _providers:
        _providers.append(fn)


def handles_of(ob):
    out = []
    for fn in _providers:
        try:
            out += fn(ob) or []
        except Exception as ex:                    # a provider must never break drawing
            print("Blenda 4D: handles:", ex)
    return out


def _target(context):
    ob = context.active_object
    if ob is None or not ob.select_get() or context.mode != "OBJECT" or not ob.visible_get():
        return None
    return ob


def _region_xy(context, world):
    return view3d_utils.location_3d_to_region_2d(context.region, context.region_data, world)


def _draw():
    import gpu
    from gpu_extras.batch import batch_for_shader
    context = bpy.context
    area = context.area
    if area is None:
        return
    key = area.as_pointer()
    _shown[key] = []
    ob = _target(context)
    if ob is None:
        return
    hs = handles_of(ob)
    if not hs:
        return
    s = context.preferences.system.ui_scale
    sh = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.blend_set("ALPHA")
    mw = ob.matrix_world
    dragging = _drag[0]
    for h in hs:
        p = _region_xy(context, mw @ h.at)
        if p is None:
            continue
        _shown[key].append((p.x, p.y, h))
        hot = dragging is not None and dragging == h.name
        r = DOT_R * s * (1.3 if hot else 1.0)
        for col, rr in (((0.0, 0.0, 0.0, 0.6), r + 1.2 * s), (HOT if hot else h.colour, r)):   # a dark rim, then the dot
            pts = [(p.x, p.y)] + [(p.x + math.cos(2 * math.pi * i / 16) * rr, p.y + math.sin(2 * math.pi * i / 16) * rr) for i in range(17)]
            sh.uniform_float("color", col)
            batch_for_shader(sh, "TRI_FAN", {"pos": pts}).draw(sh)
    gpu.state.blend_set("NONE")


def hit(context, x, y, second=False):
    """The dot under the mouse; with second, the next one when two sit on the same spot (a Cone's Top Radius on its
    Height: Shift picks it)."""
    s = context.preferences.system.ui_scale
    near = sorted((max(abs(hx - x), abs(hy - y)), i, h) for i, (hx, hy, h) in enumerate(_shown.get(context.area.as_pointer(), []))
                  if max(abs(hx - x), abs(hy - y)) <= HIT * s)
    if not near:
        return None
    return near[1][2] if second and len(near) > 1 else near[0][2]


class BLENDA4D_OT_handle_drag(bpy.types.Operator):
    """Drag a handle to change the object's setting"""
    bl_idname = "blenda4d.handle_drag"
    bl_label = "Drag Handle"
    bl_options = {"INTERNAL", "UNDO"}

    def invoke(self, context, event):
        from . import switch
        if not switch.is_on() or context.region is None or context.region.type != "WINDOW":
            return {"PASS_THROUGH"}
        ob = _target(context)
        if ob is None:
            return {"PASS_THROUGH"}
        h = hit(context, event.mouse_region_x, event.mouse_region_y, second=event.shift)
        if h is None:
            return {"PASS_THROUGH"}
        self.ob, self.hname = ob, h.name
        self.start = h.at.copy()
        self.axis = h.axis
        self.undo = bpy.data.objects.get(ob.name) and _snapshot(ob)
        _drag[0] = h.name
        context.window.cursor_modal_set("SCROLL_XY")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _place(self, context, event):
        """Where the mouse is, in the object's space: on the handle's line, or on the view plane through the start."""
        region, rv3d = context.region, context.region_data
        co = (event.mouse_region_x, event.mouse_region_y)
        o = view3d_utils.region_2d_to_origin_3d(region, rv3d, co)
        d = view3d_utils.region_2d_to_vector_3d(region, rv3d, co)
        inv = self.ob.matrix_world.inverted()
        lo, ld = inv @ o, (inv.to_3x3() @ d).normalized()
        if self.axis is not None:
            a, b = self.start, self.start + self.axis
            near = geometry.intersect_line_line(a, b, lo, lo + ld)
            return near[0] if near else self.start
        n = (inv.to_3x3() @ (rv3d.view_rotation @ Vector((0, 0, -1)))).normalized()
        p = geometry.intersect_line_plane(lo, lo + ld, self.start, n)
        return p if p is not None else self.start

    def modal(self, context, event):
        if event.type in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"}:
            h = next((x for x in handles_of(self.ob) if x.name == self.hname), None)
            if h is not None:
                h.set(self._place(context, event), self.start)
                self.ob.update_tag()
                text = h.readout() if h.readout else None
                context.workspace.status_text_set(f"{h.name}: {text}" if text else h.name)
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "RELEASE":
            self._end(context)
            return {"FINISHED"}
        if event.type in {"ESC", "RIGHTMOUSE"}:
            _restore(self.ob, self.undo)
            self._end(context)
            return {"CANCELLED"}
        return {"RUNNING_MODAL"}

    def _end(self, context):
        _drag[0] = None
        context.window.cursor_modal_restore()
        context.workspace.status_text_set(None)
        context.area.tag_redraw()
        for a in context.screen.areas:                 # the Attribute Manager shows the new value
            a.tag_redraw()


# Escape puts every setting a handle can reach back as it was
_SNAP = []                                       # fn(ob) -> state, fn(ob, state)


def snapshot_with(take, give):
    _SNAP.append((take, give))


def _snapshot(ob):
    return [(give, take(ob)) for take, give in _SNAP]


def _restore(ob, snap):
    for give, state in snap or []:
        try:
            give(ob, state)
        except Exception:
            pass
    ob.update_tag()


def register():
    bpy.utils.register_class(BLENDA4D_OT_handle_drag)
    _draws.append(bpy.types.SpaceView3D.draw_handler_add(_draw, (), "WINDOW", "POST_PIXEL"))
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name="3D View", space_type="VIEW_3D", region_type="WINDOW")
        for shift in (False, True):
            _keys.append((km, km.keymap_items.new(BLENDA4D_OT_handle_drag.bl_idname, "LEFTMOUSE", "PRESS", shift=shift, head=True)))


def unregister():
    for km, kmi in _keys:
        try:
            km.keymap_items.remove(kmi)
        except (ReferenceError, RuntimeError):
            pass
    _keys.clear()
    for h in _draws:
        bpy.types.SpaceView3D.draw_handler_remove(h, "WINDOW")
    _draws.clear()
    _shown.clear()
    bpy.utils.unregister_class(BLENDA4D_OT_handle_drag)
