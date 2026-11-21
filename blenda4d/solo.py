# SPDX-License-Identifier: GPL-3.0-or-later
"""Solo: show only the selected objects in the viewport, without moving the camera.

Every other object is hidden, and the names of the ones Solo hid are kept on the scene, so Solo Off shows exactly
those again: objects you had hidden yourself stay hidden. Parents that draw nothing themselves (generators, nulls)
stay visible, so a generator above a soloed object still shows its result.
  Solo            the selection and everything under it; again with the same selection: Solo Off
  Solo Single     the selection only, not what is under it
  Solo Hierarchy  the selection and everything under it
  Solo Off        everything Solo hid comes back"""
import bpy

SOLO_HIDDEN, SOLO_KEEP = "b4d_solo_hidden", "b4d_solo_keep"
MODES = (("TOGGLE", "Solo", "Show only the selected objects and what is under them; again to show everything"),
         ("SINGLE", "Solo Single", "Show only the selected objects, not what is under them"),
         ("HIERARCHY", "Solo Hierarchy", "Show only the selected objects and everything under them"),
         ("OFF", "Solo Off", "Show everything Solo hid"))


def is_on(scene=None):
    scene = scene or bpy.context.scene
    return scene is not None and scene.get(SOLO_HIDDEN) is not None


def _restore(scene):
    for n in scene.get(SOLO_HIDDEN, ()):
        ob = scene.objects.get(n)
        if ob is not None:
            try:
                ob.hide_set(False)
            except RuntimeError:
                pass
    for k in (SOLO_HIDDEN, SOLO_KEEP):
        if k in scene:
            del scene[k]


def _picked(context):
    """The selected objects. Blender cannot keep a hidden object selected, so an object Solo hid that is clicked in
    the Object Manager only becomes the active one: it counts as picked too."""
    out = [o for o in context.view_layer.objects if o.select_get()]
    act = context.view_layer.objects.active
    if act is not None and act not in out and act.name in context.scene.get(SOLO_HIDDEN, ()):
        out.append(act)
    return out


def run(context, mode="TOGGLE"):
    scene = context.scene
    sel = set(_picked(context))
    if is_on(scene):
        same = {o.name for o in sel} <= set(scene.get(SOLO_KEEP, ())) if sel else True
        _restore(scene)
        if mode == "OFF" or (mode == "TOGGLE" and same):
            return True
    elif mode == "OFF":
        return True
    if not sel:
        return False
    keep = set(sel)
    if mode != "SINGLE":
        for o in sel:
            keep |= set(o.children_recursive)
    for o in list(keep):                               # parents that draw nothing stay on: a generator above still shows
        p = o.parent
        while p is not None:
            if p.type == "EMPTY":
                keep.add(p)
            p = p.parent
    hidden = []
    for o in context.view_layer.objects:
        if o in keep or not o.visible_get():
            continue
        try:
            o.hide_set(True)
            hidden.append(o.name)
        except RuntimeError:
            pass
    scene[SOLO_HIDDEN] = hidden
    scene[SOLO_KEEP] = sorted(o.name for o in sel)
    return True


def redraw(context):
    for a in context.window.screen.areas:
        a.tag_redraw()


class BLENDA4D_OT_solo(bpy.types.Operator):
    bl_idname = "blenda4d.solo"
    bl_label = "Solo"
    bl_description = "Show only the selected objects in the viewport; the camera does not move. Again to show everything"
    bl_options = {"REGISTER", "UNDO"}
    mode: bpy.props.EnumProperty(items=MODES, default="TOGGLE", options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, props):
        return {m: d for m, _l, d in MODES}[props.mode]

    def execute(self, context):
        if not run(context, self.mode):
            self.report({"INFO"}, "Select the objects to solo first")
            return {"CANCELLED"}
        redraw(context)
        return {"FINISHED"}


def register():
    bpy.utils.register_class(BLENDA4D_OT_solo)


def unregister():
    bpy.utils.unregister_class(BLENDA4D_OT_solo)
