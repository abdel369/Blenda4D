# SPDX-License-Identifier: GPL-3.0-or-later
"""Blenda's menus, drawn with Blender's own menu widgets.

A menu is a list of items: (label, operator, {props}, icon) runs a Blender or Blenda operator; (label, None, ...)
is shown greyed (nothing behind it yet); "-" is a separator; ("menu", label, idname) opens a sub-menu (Blender's
own lists such as Open Recent and Import are used as they are, being lists of files and formats, not layout)."""
import bpy

SEP = "-"


def item(label, op=None, icon="NONE", **props):
    return (label, op, props, icon)


def sub(label, idname, icon="NONE"):
    return ("menu", label, idname, icon)


def draw_items(layout, items):
    for it in items:
        if it == SEP:
            layout.separator()
            continue
        if it[0] == "menu":
            layout.menu(it[2], text=it[1], icon=it[3])
            continue
        label, op, props, icon = it
        if op is None:
            col = layout.column()
            col.enabled = False
            col.operator("blenda4d.noop", text=label, icon=icon)
            continue
        o = layout.operator(op, text=label, icon=icon)
        for k, v in props.items():
            try:
                setattr(o, k, v)
            except (AttributeError, TypeError):
                pass


class BLENDA4D_OT_noop(bpy.types.Operator):
    bl_idname = "blenda4d.noop"
    bl_label = "Not available yet"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        return {"CANCELLED"}


MAIN = {
    "File": [item("New", "wm.read_homefile", "FILE_NEW"), item("Open...", "wm.open_mainfile", "FILE_FOLDER"),
             sub("Open Recent", "TOPBAR_MT_file_open_recent"), SEP,
             item("Save", "wm.save_mainfile", "FILE_TICK"), item("Save As...", "wm.save_as_mainfile"),
             item("Save Copy...", "wm.save_as_mainfile", copy=True), item("Revert", "wm.revert_mainfile"), SEP,
             sub("Import", "TOPBAR_MT_file_import", "IMPORT"), sub("Export", "TOPBAR_MT_file_export", "EXPORT"), SEP,
             item("Quit", "wm.quit_blender", "QUIT")],
    "Edit": [item("Undo", "ed.undo", "LOOP_BACK"), item("Redo", "ed.redo", "LOOP_FORWARDS"),
             item("Undo History...", "ed.undo_history"), SEP,
             item("Copy", "view3d.copybuffer", "COPYDOWN"), item("Paste", "view3d.pastebuffer", "PASTEDOWN"),
             item("Delete", "object.delete", "X"), SEP,
             item("Select All", "object.select_all", action="SELECT"), item("Deselect All", "object.select_all", action="DESELECT"),
             SEP, item("Preferences...", "screen.userpref_show", "PREFERENCES")],
    "Create": [item("Cube", "blenda4d.add_primitive", "MESH_CUBE", kind="cube"), item("Sphere", "blenda4d.add_primitive", "MESH_UVSPHERE", kind="sphere"),
               item("Cylinder", "blenda4d.add_primitive", "MESH_CYLINDER", kind="cylinder"), item("Cone", "blenda4d.add_primitive", "MESH_CONE", kind="cone"),
               item("Torus", "blenda4d.add_primitive", "MESH_TORUS", kind="torus"), item("Plane", "blenda4d.add_primitive", "MESH_PLANE", kind="plane"),
               item("Disc", "blenda4d.add_primitive", "MESH_CIRCLE", kind="disc"), item("Pyramid", "blenda4d.add_primitive", "MESH_CONE", kind="pyramid"),
               item("Tube", "blenda4d.add_primitive", "MESH_CYLINDER", kind="tube"), item("Capsule", "blenda4d.add_primitive", "MESH_CAPSULE", kind="capsule"),
               item("Oil Tank", "blenda4d.add_primitive", "MESH_CAPSULE", kind="oiltank"), item("Platonic", "blenda4d.add_primitive", "MESH_ICOSPHERE", kind="platonic"),
               item("Landscape", "blenda4d.add_primitive", "RNDCURVE", kind="landscape"), item("Relief", "blenda4d.add_primitive", "IMAGE_DATA", kind="relief"),
               item("Figure", "blenda4d.add_primitive", "ARMATURE_DATA", kind="figure"), item("Bezier", "blenda4d.add_primitive", "SURFACE_NSURFACE", kind="bezier"),
               item("Cyc Wall", "blenda4d.add_primitive", "MESH_GRID", kind="cyc"), SEP,
               item("Spline", "curve.primitive_bezier_curve_add", "CURVE_BEZCURVE"), item("Circle", "curve.primitive_bezier_circle_add", "CURVE_BEZCIRCLE"),
               item("Text", "object.text_add", "OUTLINER_OB_FONT"), SEP,
               item("Null", "object.empty_add", "OUTLINER_OB_EMPTY"), item("Camera", "object.camera_add", "OUTLINER_OB_CAMERA"),
               item("Light", "object.light_add", "OUTLINER_OB_LIGHT", type="AREA")],
    "Modes": [item("Model", "object.mode_set", "OBJECT_DATAMODE", mode="OBJECT"), item("Points", "blenda4d.set_mode", "VERTEXSEL", mode="POINTS"),
              item("Edges", "blenda4d.set_mode", "EDGESEL", mode="EDGES"), item("Polygons", "blenda4d.set_mode", "FACESEL", mode="POLYGONS")],
    "Select": [item("Select All", "object.select_all", action="SELECT"), item("Deselect All", "object.select_all", action="DESELECT"),
               item("Invert Selection", "object.select_all", action="INVERT"), SEP,
               item("Live Selection", "wm.tool_set_by_id", "RESTRICT_SELECT_OFF", name="builtin.select_circle", space_type="VIEW_3D"),
               item("Rectangle Selection", "wm.tool_set_by_id", name="builtin.select_box", space_type="VIEW_3D"),
               item("Lasso Selection", "wm.tool_set_by_id", name="builtin.select_lasso", space_type="VIEW_3D")],
    "Tools": [item("Move", "wm.tool_set_by_id", name="builtin.move", space_type="VIEW_3D"), item("Scale", "wm.tool_set_by_id", name="builtin.scale", space_type="VIEW_3D"),
              item("Rotate", "wm.tool_set_by_id", name="builtin.rotate", space_type="VIEW_3D"), SEP, item("Measure", "wm.tool_set_by_id", name="builtin.measure", space_type="VIEW_3D")],
    "Spline": [item("Pen", "wm.tool_set_by_id", name="builtin.pen", space_type="VIEW_3D"), item("Sketch", "wm.tool_set_by_id", name="builtin.draw", space_type="VIEW_3D")],
    "Mesh": [item("Extrude", "wm.tool_set_by_id", name="builtin.extrude_region", space_type="VIEW_3D"), item("Inset", "wm.tool_set_by_id", name="builtin.inset_faces", space_type="VIEW_3D"),
             item("Bevel", "wm.tool_set_by_id", name="builtin.bevel", space_type="VIEW_3D"), item("Loop Cut", "wm.tool_set_by_id", name="builtin.loop_cut", space_type="VIEW_3D"),
             item("Knife", "wm.tool_set_by_id", name="builtin.knife", space_type="VIEW_3D")],
    "Volume": [item("Volume Builder"), item("Volume Mesher")],
    "MoClone": [item("Cloner"), item("Matrix"), item("Fracture"), item("Voronoi Fracture"), SEP, item("Effectors"), item("Fields")],
    "Character": [item("Joint", "object.armature_add", "BONE_DATA")],
    "Animate": [item("Record Active Objects", "anim.keyframe_insert", "REC"), item("Delete Keyframes", "anim.keyframe_delete_v3d")],
    "Simulate": [item("Rigid Body", "rigidbody.object_add"), item("Cloth", "object.modifier_add", type="CLOTH")],
    "Tracker": [item("Motion Tracker")],
    "Render": [item("Render View", "render.render", "RENDER_STILL"), item("Render to Render Viewer", "blenda4d.render", "RENDER_RESULT"),
               item("Render Animation", "blenda4d.render", "RENDER_ANIMATION", animation=True), SEP,
               item("Render Viewer", "render.view_show", "IMAGE"), item("Render Settings...", "blenda4d.render_settings", "SCENE"), SEP],
    "Add-ons": [item("Get Extensions...", "screen.userpref_show", "PLUGIN", section="EXTENSIONS"),
                item("Add-on Preferences...", "screen.userpref_show", "PREFERENCES", section="ADDONS"), SEP,
                item("Add Menu Items...", "blenda4d.addons_menu", "ADD", menu="BLENDA4D_MT_addons_add"),
                item("Object Menu Items...", "blenda4d.addons_menu", "OBJECT_DATA", menu="BLENDA4D_MT_addons_object"),
                item("Add-on Panels", "blenda4d.addon_panels", "MENU_PANEL"),
                item("Blender Properties...", "blenda4d.blender_properties", "PROPERTIES")],
    "Window": [item("Material Manager", "blenda4d.toggle_column", "MATERIAL", name="MATERIALS"),
               item("Asset Browser", "blenda4d.toggle_column", "ASSET_MANAGER", name="ASSETS"), SEP,
               item("New Window", "wm.window_new"), item("Toggle Full Screen", "wm.window_fullscreen_toggle")],
    "Help": [item("Blender Manual", "wm.url_open_preset", "HELP", type="MANUAL"), item("About Blender", "wm.splash_about", "BLENDER")],
}



def _make(label, items, prefix):
    idname = f"BLENDA4D_MT_{prefix}_" + "".join(c for c in label.lower() if c.isalnum())

    def draw(self, context):
        draw_items(self.layout, items)
        from . import kinds
        extra = kinds.menu_items(label)
        if extra:
            self.layout.separator()
            for text, kind, icon in extra:
                self.layout.operator("blenda4d.add_kind", text=text, icon=icon).kind = kind
    return type(idname, (bpy.types.Menu,), {"bl_idname": idname, "bl_label": label, "draw": draw})


MAIN_CLASSES = [_make(k, v, "main") for k, v in MAIN.items()]
from .viewmenus import OPS as VIEW_OPS, VIEW_CLASSES  # noqa: E402  the viewport's own menus (viewmenus.py)


def menu_bar(layout, classes, labels=None):
    row = layout.row(align=True)
    row.alignment = "LEFT"
    try:
        row.emboss = "PULLDOWN_MENU"
    except (AttributeError, TypeError):
        pass
    for cls in classes:
        if labels is None or cls.bl_label in labels:
            row.menu(cls.bl_idname, text=cls.bl_label)
    return row


def simple_menu(label, items, manager="mgr"):
    """A manager's own menu (Object Manager File / Edit ..., Attribute Manager Mode / Edit ...)."""
    return _make(label, items, manager)


classes = (BLENDA4D_OT_noop, *VIEW_OPS, *MAIN_CLASSES, *VIEW_CLASSES)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
