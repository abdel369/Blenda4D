# SPDX-License-Identifier: GPL-3.0-or-later
"""Make Editable (C) and Ctrl+drag copy.

Make Editable: a primitive becomes a plain polygon object. Its own generator is applied and its kind is dropped, so
its procedural settings are gone and the Object Manager shows it as a polygon object. Deformers on it stay live.
A spline shape becomes a plain spline; any other object is converted to a mesh as Blender does it.

Ctrl+drag on the Move handle: the selected objects are copied first, then the handle moves the copies."""
import bpy

from . import primitives


def _apply(context, ob, mod):
    with context.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
        bpy.ops.object.modifier_apply(modifier=mod.name)


def make_editable(context, ob):
    """True when the object changed."""
    kind = ob.get("b4d_type")
    if ob.type == "MESH" and kind in primitives.TYPE_TO_KIND:
        if ob.data.users > 1:
            ob.data = ob.data.copy()
        for mod in list(primitives._own_mods(ob)):
            _apply(context, ob, mod)
        del ob["b4d_type"]
        return True
    from . import splines
    if splines.shape_kind(ob) is not None:
        with context.temp_override(object=ob, active_object=ob):
            bpy.ops.blenda4d.spline_make_editable()
        return True
    if ob.type in {"MESH", "CURVE", "SURFACE", "META", "FONT", "CURVES", "POINTCLOUD"}:
        with context.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
            bpy.ops.object.convert(target="MESH")
        if "b4d_type" in ob and primitives.GENERATOR_MOD not in ob.modifiers:
            del ob["b4d_type"]
        return True
    return False


class BLENDA4D_OT_make_editable(bpy.types.Operator):
    bl_idname = "blenda4d.make_editable"
    bl_label = "Make Editable"
    bl_description = "Turn the selected primitives into polygon objects whose points can be edited (their settings go)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(context.selected_objects or context.active_object)

    def execute(self, context):
        obs = list(context.selected_objects) or [context.active_object]
        done = sum(make_editable(context, ob) for ob in obs if ob is not None)
        if not done:
            self.report({"INFO"}, "Nothing to make editable")
            return {"CANCELLED"}
        for a in context.screen.areas:
            a.tag_redraw()
        return {"FINISHED"}


class BLENDA4D_OT_copy_for_drag(bpy.types.Operator):
    """Copy the selected objects; the drag that started this goes on to move the copies"""
    bl_idname = "blenda4d.copy_for_drag"
    bl_label = "Copy and Move"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(context.selected_objects)

    def invoke(self, context, event):
        bpy.ops.object.duplicate(linked=False)
        return {"FINISHED", "PASS_THROUGH"}


classes = (BLENDA4D_OT_make_editable, BLENDA4D_OT_copy_for_drag)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
