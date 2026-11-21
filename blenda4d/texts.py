# SPDX-License-Identifier: GPL-3.0-or-later
"""Text Spline: the create column's text button and the text object's Object page. Each row is one of Blender's own
text settings; the plane switch turns the object so its letters lie in the XY (front), ZY (side) or XZ (floor) plane
as Blenda shows the axes (Y up)."""
import math

import bpy

from . import managers

NAME = "Text Spline"
LABEL_SPLIT = 0.4

# Blenda's plane -> the object's rotation in Blender (Blenda shows Blender's Z as Y): XY faces the front,
# ZY faces the side, XZ lies on the floor
PLANES = {"XY": (math.pi / 2, 0.0, 0.0), "ZY": (math.pi / 2, 0.0, math.pi / 2), "XZ": (0.0, 0.0, 0.0)}


class BLENDA4D_OT_add_text(bpy.types.Operator):
    bl_idname = "blenda4d.add_text"
    bl_label = "Text Spline"
    bl_description = "Add a text object, standing in the XY plane"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        data = bpy.data.curves.new(NAME, "FONT")
        data.body = "Text"
        data.size = 2.0                                   # 200 cm, as other new objects are sized
        data.align_x = "LEFT"
        ob = bpy.data.objects.new(NAME, data)
        context.collection.objects.link(ob)
        ob.location = context.scene.cursor.location
        ob.rotation_euler = PLANES["XY"]
        for o in context.view_layer.objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        return {"FINISHED"}


def _row(col, owner, attr, label, **kw):
    r = col.row(align=True)
    r.use_property_split = False
    r.use_property_decorate = False
    sp = r.split(factor=LABEL_SPLIT, align=True)
    lab = sp.row()
    lab.alignment = "RIGHT"
    lab.label(text=label)
    field = sp.row(align=True)                        # a row, so Left / Middle / Right sit side by side
    if kw.get("expand"):
        field.prop(owner, attr, **kw)
    else:
        field.prop(owner, attr, text="", **kw)
    r.prop_decorator(owner, attr)
    return r


def page_object(col, ob):
    d = ob.data
    _row(col, d, "body", "Text")
    r = col.row(align=True)
    r.use_property_split = False
    sp = r.split(factor=LABEL_SPLIT, align=True)
    lab = sp.row()
    lab.alignment = "RIGHT"
    lab.label(text="Font")
    sp.template_ID(d, "font", open="font.open", unlink="font.unlink")
    _row(col, d, "b4d_align", "Align", expand=True)
    _row(col, d, "b4d_height", "Height")
    _row(col, d, "space_character", "Horizontal Spacing")
    _row(col, d, "space_line", "Vertical Spacing")
    col.separator()
    _row(col, ob, "b4d_text_plane", "Plane", expand=True)
    col.separator()
    col.label(text="Spline")
    _row(col, d, "resolution_u", "Points")


# --- settings shown the way the page names them ----------------------------------------------------------------------
ALIGN = [("LEFT", "Left", "Line up the lines on the left"), ("CENTER", "Middle", "Centre the lines"),
         ("RIGHT", "Right", "Line up the lines on the right")]


def _align_get(self):
    return {"LEFT": 0, "CENTER": 1, "RIGHT": 2}.get(self.align_x, 0)


def _align_set(self, v):
    self.align_x = ("LEFT", "CENTER", "RIGHT")[v]


def _height_get(self):
    return self.size


def _height_set(self, v):
    self.size = max(v, 0.0001)


def _plane_get(self):
    r = tuple(self.rotation_euler)
    best = min(PLANES, key=lambda k: sum((a - b) ** 2 for a, b in zip(r, PLANES[k])))
    return list(PLANES).index(best)


def _plane_set(self, v):
    self.rotation_euler = PLANES[list(PLANES)[v]]


def register():
    bpy.utils.register_class(BLENDA4D_OT_add_text)
    T = bpy.types.TextCurve
    T.b4d_align = bpy.props.EnumProperty(description='Line up the lines of text on the left, in the middle or on the right', name="Align", items=ALIGN, get=_align_get, set=_align_set)
    T.b4d_height = bpy.props.FloatProperty(name="Height", subtype="DISTANCE", unit="LENGTH", get=_height_get,
                                           set=_height_set, description="Height of the letters (Blender: Size)")
    bpy.types.Object.b4d_text_plane = bpy.props.EnumProperty(description='The plane the letters lie in: XY faces the front, ZY the side, XZ lies on the floor', 
        name="Plane", items=[(k, k, f"Letters in the {k} plane") for k in PLANES], get=_plane_get, set=_plane_set)
    managers.FONT_PAGE[:] = [page_object]
    from . import bars
    for g in bars.CREATE_GROUPS:                           # the text button makes a Text Spline
        if g and g[0] == "text":
            g[1][0] = (NAME, "OUTLINER_OB_FONT", "blenda4d.add_text", {})


def unregister():
    from . import bars
    for g in bars.CREATE_GROUPS:
        if g and g[0] == "text":
            g[1][0] = ("Text", "OUTLINER_OB_FONT", "object.text_add", {})
    managers.FONT_PAGE.clear()
    for owner, n in ((bpy.types.TextCurve, "b4d_align"), (bpy.types.TextCurve, "b4d_height"),
                     (bpy.types.Object, "b4d_text_plane")):
        if hasattr(owner, n):
            delattr(owner, n)
    bpy.utils.unregister_class(BLENDA4D_OT_add_text)
