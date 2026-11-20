# SPDX-License-Identifier: GPL-3.0-or-later
"""The viewport's menus: View, Cameras, Display, Options, Filter, Panel. Each item is one of Blender's own viewport
operators or settings (settings show their check mark), named in plain words; Blender shows its own shortcut beside
each operator. Settings Blender has no equivalent for are left out."""
import bpy


def _space(context):
    sp = context.space_data
    if sp is not None and sp.type == "VIEW_3D":
        return sp
    area = next((a for a in context.screen.areas if a.type == "VIEW_3D"), None)
    return area.spaces.active if area else None


def _heading(layout, text):
    layout.label(text=text)


class BLENDA4D_OT_use_camera(bpy.types.Operator):
    bl_idname = "blenda4d.use_camera"
    bl_label = "Use Camera"
    bl_description = "Look through this camera (it becomes the scene camera)"
    name: bpy.props.StringProperty()

    def execute(self, context):
        ob = bpy.data.objects.get(self.name)
        sp = _space(context)
        if ob is None or ob.type != "CAMERA" or sp is None:
            return {"CANCELLED"}
        context.scene.camera = ob
        sp.region_3d.view_perspective = "CAMERA"
        return {"FINISHED"}


class BLENDA4D_OT_default_camera(bpy.types.Operator):
    bl_idname = "blenda4d.default_camera"
    bl_label = "Default Camera"
    bl_description = "Leave the scene camera and look through the viewport's own camera"

    def execute(self, context):
        sp = _space(context)
        if sp is None:
            return {"CANCELLED"}
        if sp.region_3d.view_perspective == "CAMERA":
            sp.region_3d.view_perspective = "PERSP"
        return {"FINISHED"}


class BLENDA4D_OT_projection(bpy.types.Operator):
    bl_idname = "blenda4d.projection"
    bl_label = "Projection"
    bl_description = "Perspective or parallel (orthographic) projection"
    kind: bpy.props.EnumProperty(items=[("PERSP", "Perspective", ""), ("ORTHO", "Parallel", "")])

    def execute(self, context):
        sp = _space(context)
        if sp is None:
            return {"CANCELLED"}
        sp.region_3d.view_perspective = self.kind
        return {"FINISHED"}


class BLENDA4D_OT_show_types(bpy.types.Operator):
    bl_idname = "blenda4d.show_types"
    bl_label = "Show Object Types"
    bl_description = "Show every kind of object, or only geometry"
    only_geometry: bpy.props.BoolProperty()

    def execute(self, context):
        sp = _space(context)
        if sp is None:
            return {"CANCELLED"}
        for attr, _label in FILTER_TYPES:
            setattr(sp, attr, (not self.only_geometry) or attr in GEOMETRY)
        return {"FINISHED"}


class BLENDA4D_MT_view_view(bpy.types.Menu):
    bl_idname = "BLENDA4D_MT_view_view"
    bl_label = "View"

    def draw(self, context):
        layout = self.layout
        sp = _space(context)
        _heading(layout, "Frame")
        layout.operator("view3d.view_all", text="Frame All").center = False
        layout.operator("view3d.view_selected", text="Frame Selected")
        layout.operator("view3d.view_all", text="Frame All and Center Cursor").center = True
        layout.operator("view3d.view_center_cursor", text="Center on 3D Cursor")
        layout.separator()
        layout.operator("view3d.zoom_border", text="Zoom Region")
        layout.operator("view3d.zoom", text="Zoom In").delta = 1
        layout.operator("view3d.zoom", text="Zoom Out").delta = -1
        layout.separator()
        _heading(layout, "Render")
        layout.operator("view3d.render_border", text="Render Region")
        layout.operator("view3d.clear_render_border", text="Clear Render Region")
        layout.operator("render.opengl", text="Viewport Render Image", icon="RENDER_STILL")
        layout.operator("render.render", text="Render Image", icon="RENDER_STILL").use_viewport = True
        layout.separator()
        if sp is not None:
            layout.prop(sp, "lock_camera", text="Lock Camera to View")
        layout.operator("view3d.camera_to_view", text="Align Camera to View")
        layout.separator()
        layout.operator("screen.screen_full_area", text="Maximize Viewport")


class BLENDA4D_MT_view_cameras(bpy.types.Menu):
    bl_idname = "BLENDA4D_MT_view_cameras"
    bl_label = "Cameras"

    def draw(self, context):
        layout = self.layout
        sp = _space(context)
        _heading(layout, "Camera")
        in_cam = sp is not None and sp.region_3d.view_perspective == "CAMERA"
        layout.operator("blenda4d.default_camera", text="Default Camera", icon="CHECKMARK" if not in_cam else "BLANK1")
        cams = sorted((o for o in context.scene.objects if o.type == "CAMERA"), key=lambda o: o.name)
        for ob in cams:
            on = in_cam and context.scene.camera == ob
            layout.operator("blenda4d.use_camera", text=ob.name, icon="CHECKMARK" if on else "OUTLINER_OB_CAMERA").name = ob.name
        if not cams:
            col = layout.column()
            col.enabled = False
            col.label(text="No cameras in the scene")
        if sp is not None:
            layout.separator()
            layout.prop(sp, "lock_camera", text="Lock Camera to View")
        cam = context.scene.camera
        if cam is not None and cam.type == "CAMERA":
            layout.prop(cam.data, "show_safe_areas", text="Safe Frames")
            layout.prop(cam.data, "show_passepartout", text="Darken Outside the Frame")
        layout.separator()
        _heading(layout, "Projection")
        persp = sp is not None and sp.region_3d.view_perspective == "PERSP"
        ortho = sp is not None and sp.region_3d.view_perspective == "ORTHO"
        layout.operator("blenda4d.projection", text="Perspective", icon="CHECKMARK" if persp else "BLANK1").kind = "PERSP"
        layout.operator("blenda4d.projection", text="Parallel", icon="CHECKMARK" if ortho else "BLANK1").kind = "ORTHO"
        layout.separator()
        for axis, label in (("LEFT", "Left"), ("RIGHT", "Right"), ("FRONT", "Front"), ("BACK", "Back"),
                            ("TOP", "Top"), ("BOTTOM", "Bottom")):
            layout.operator("view3d.view_axis", text=label).type = axis
        if sp is not None:
            layout.separator()
            layout.prop(sp, "lens", text="Viewport Focal Length")


class BLENDA4D_MT_view_display(bpy.types.Menu):
    bl_idname = "BLENDA4D_MT_view_display"
    bl_label = "Display"

    def draw(self, context):
        layout = self.layout
        sp = _space(context)
        if sp is None:
            return
        sh = sp.shading
        _heading(layout, "Shading")
        for kind, label in (("WIREFRAME", "Wireframe"), ("SOLID", "Solid"), ("MATERIAL", "Material Preview"),
                            ("RENDERED", "Rendered")):
            layout.prop_enum(sh, "type", kind, text=label)
        layout.separator()
        if sh.type == "SOLID":
            _heading(layout, "Solid")
            for kind, label in (("STUDIO", "Studio Lighting"), ("MATCAP", "MatCap"), ("FLAT", "Flat")):
                layout.prop_enum(sh, "light", kind, text=label)
            layout.separator()
            for kind, label in (("MATERIAL", "Material Color"), ("OBJECT", "Object Color"), ("RANDOM", "Random Color"),
                                ("SINGLE", "Single Color")):
                layout.prop_enum(sh, "color_type", kind, text=label)
            layout.separator()
            layout.prop(sh, "show_cavity", text="Cavity")
            layout.prop(sh, "show_shadows", text="Shadows")
            layout.prop(sh, "show_object_outline", text="Outline")
        if sh.type in {"MATERIAL", "RENDERED"}:
            layout.prop(sh, "use_scene_lights" if sh.type == "MATERIAL" else "use_scene_lights_render", text="Scene Lights")
            layout.prop(sh, "use_scene_world" if sh.type == "MATERIAL" else "use_scene_world_render", text="Scene World")
        layout.separator()
        _heading(layout, "Wire")
        layout.prop(sp.overlay, "show_wireframes", text="Wireframe on Shaded")
        layout.prop(sh, "show_xray", text="X-Ray")
        layout.prop(sh, "show_backface_culling", text="Backface Culling")


class BLENDA4D_MT_view_options(bpy.types.Menu):
    bl_idname = "BLENDA4D_MT_view_options"
    bl_label = "Options"

    def draw(self, context):
        layout = self.layout
        sp = _space(context)
        if sp is None:
            return
        ov = sp.overlay
        layout.prop(ov, "show_overlays", text="Overlays")
        layout.prop(sp, "show_gizmo", text="Gizmos")
        layout.separator()
        _heading(layout, "Viewport")
        layout.prop(ov, "show_floor", text="Grid")
        layout.prop(ov, "show_axis_x", text="X Axis")
        layout.prop(ov, "show_axis_z", text="Y Axis")     # Blenda shows Blender's Z as Y
        layout.prop(ov, "show_axis_y", text="Z Axis")
        layout.prop(ov, "show_cursor", text="3D Cursor")
        layout.prop(ov, "show_stats", text="Statistics")
        layout.prop(ov, "show_text", text="View Name")
        layout.separator()
        _heading(layout, "Objects")
        layout.prop(ov, "show_outline_selected", text="Selection Outline")
        layout.prop(ov, "show_object_origins", text="Object Origins")
        layout.prop(ov, "show_relationship_lines", text="Relationship Lines")
        layout.prop(ov, "show_face_orientation", text="Face Orientation")
        layout.prop(ov, "show_motion_paths", text="Motion Paths")
        layout.prop(ov, "show_bones", text="Joints")
        layout.prop(ov, "show_extras", text="Lights, Cameras and Helpers")
        layout.prop(ov, "show_fade_inactive", text="Fade Inactive Objects")
        layout.separator()
        _heading(layout, "Clipping")
        layout.prop(sp, "clip_start", text="Near")
        layout.prop(sp, "clip_end", text="Far")


FILTER_TYPES = (("show_object_viewport_mesh", "Polygon"), ("show_object_viewport_curve", "Spline"),
                ("show_object_viewport_surf", "Surface"), ("show_object_viewport_meta", "Metaball"),
                ("show_object_viewport_font", "Text"), ("show_object_viewport_volume", "Volume"),
                ("show_object_viewport_pointcloud", "Point Cloud"), ("show_object_viewport_curves", "Hair"),
                ("show_object_viewport_grease_pencil", "Grease Pencil"),
                ("show_object_viewport_armature", "Joint"), ("show_object_viewport_lattice", "Lattice"),
                ("show_object_viewport_empty", "Null"), ("show_object_viewport_light", "Light"),
                ("show_object_viewport_light_probe", "Light Probe"), ("show_object_viewport_camera", "Camera"),
                ("show_object_viewport_speaker", "Speaker"))
GEOMETRY = {"show_object_viewport_mesh", "show_object_viewport_curve", "show_object_viewport_surf",
            "show_object_viewport_meta", "show_object_viewport_font", "show_object_viewport_volume",
            "show_object_viewport_pointcloud"}


class BLENDA4D_MT_view_filter(bpy.types.Menu):
    bl_idname = "BLENDA4D_MT_view_filter"
    bl_label = "Filter"

    def draw(self, context):
        layout = self.layout
        sp = _space(context)
        if sp is None:
            return
        layout.operator("blenda4d.show_types", text="Show Everything").only_geometry = False
        layout.operator("blenda4d.show_types", text="Geometry Only").only_geometry = True
        layout.separator()
        _heading(layout, "Objects")
        for attr, label in FILTER_TYPES:
            if hasattr(sp, attr):
                layout.prop(sp, attr, text=label)


class BLENDA4D_MT_view_panel(bpy.types.Menu):
    bl_idname = "BLENDA4D_MT_view_panel"
    bl_label = "Panel"

    def draw(self, context):
        layout = self.layout
        sp = _space(context)
        quad = sp is not None and len(sp.region_quadviews) > 0
        layout.operator("screen.region_quadview", text="Single View" if quad else "Four Views", icon="VIEW_ORTHO")
        layout.operator("screen.screen_full_area", text="Maximize Viewport")
        layout.separator()
        layout.operator("wm.window_new", text="New Window")


VIEW_CLASSES = [BLENDA4D_MT_view_view, BLENDA4D_MT_view_cameras, BLENDA4D_MT_view_display, BLENDA4D_MT_view_options,
                BLENDA4D_MT_view_filter, BLENDA4D_MT_view_panel]
OPS = (BLENDA4D_OT_use_camera, BLENDA4D_OT_default_camera, BLENDA4D_OT_projection, BLENDA4D_OT_show_types)
