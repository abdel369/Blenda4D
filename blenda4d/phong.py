# SPDX-License-Identifier: GPL-3.0-or-later
"""Select › Phong Break Selection: a viewport tool for editable meshes. Click a polygon and its whole smoothing area is
selected, that is every polygon reached without crossing a hard edge. In edge mode the click selects the hard edges
around that area instead. Shift adds, Ctrl (or Cmd) removes. The area under the mouse is highlighted before you click.

Hard edges are open borders, edges whose polygons meet at more than the Phong Angle and, with Use Edge Breaks on, the
edges marked sharp (Blender's Mark Sharp). The angle is the tool's own while Override Phong is on, else the object's:
the Phong Angle of a Blenda primitive or of a Smooth by Angle modifier."""
import math

import bmesh
import bpy

TOOL = "blenda4d.phong_break_select"
_state = {"clicks": [], "hover": None, "batch": None, "handle": None}


def _object_angle(ob):
    """The object's own smoothing angle in radians: from its Phong Angle or Smooth by Angle modifier, else fully
    smooth (pi) when it is shaded smooth and 0 when it is flat."""
    for m in ob.modifiers:
        tree = getattr(m, "node_group", None) if m.type == "NODES" else None
        if tree is None or not m.show_viewport:
            continue
        sockets = {s.name: s.identifier for s in tree.interface.items_tree if getattr(s, "in_out", "") == "INPUT"}
        for name in ("Phong Angle", "Angle"):
            if name in sockets:
                if "Angle Limit" in sockets and not m.get(sockets["Angle Limit"], True):
                    return math.pi
                try:
                    return float(m[sockets[name]])
                except (KeyError, TypeError, ValueError):
                    pass
    polys = ob.data.polygons
    return math.pi if polys and any(p.use_smooth for p in polys) else 0.0


def _settings(ob):
    """(angle in radians, use edge breaks) for this object."""
    t = bpy.context.scene.blenda4d_phong_tool
    if t.override:
        return math.radians(t.angle), t.use_edges
    return _object_angle(ob), t.use_edges


def _hard(e, angle, use_edges):
    if len(e.link_faces) != 2:
        return True
    if use_edges and not e.smooth:
        return True
    return e.calc_face_angle(0.0) > angle + 1e-6


def _area(face, angle, use_edges):
    """The polygons reached from this one without crossing a hard edge."""
    seen, todo = {face}, [face]
    while todo:
        f = todo.pop()
        for e in f.edges:
            if e.hide or _hard(e, angle, use_edges):
                continue
            for g in e.link_faces:
                if g not in seen and not g.hide:
                    seen.add(g)
                    todo.append(g)
    return seen


def _elements(ob, face):
    """('FACE', polygons) in polygon or point mode, ('EDGE', the area's hard edges) in edge mode."""
    angle, use = _settings(ob)
    area = _area(face, angle, use)
    mode = bpy.context.tool_settings.mesh_select_mode
    if mode[1] and not mode[2]:
        return "EDGE", {e for f in area for e in f.edges if _hard(e, angle, use)}
    return "FACE", area


def _pick(context, co):
    """(object, bmesh, polygon) under a point in the region, or None."""
    from bpy_extras import view3d_utils
    from mathutils.bvhtree import BVHTree
    region, rv3d = context.region, context.region_data
    if region is None or rv3d is None:
        return None
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, co)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, co)
    best = None
    for ob in context.objects_in_mode_unique_data:
        if ob.type != "MESH":
            continue
        bm = bmesh.from_edit_mesh(ob.data)
        bm.faces.ensure_lookup_table()
        inv = ob.matrix_world.inverted()
        loc, _n, index, _d = BVHTree.FromBMesh(bm).ray_cast(inv @ origin, (inv.to_3x3() @ direction).normalized())
        if loc is None:
            continue
        dist = (ob.matrix_world @ loc - origin).length
        if best is None or dist < best[0]:
            best = (dist, ob, bm, bm.faces[index])
    return None if best is None else best[1:]


def _replay(context):
    """Select from the clicks again with the current settings, so the selection follows the options live."""
    obs = {ob.name: ob for ob in context.objects_in_mode_unique_data if ob.type == "MESH"}
    touched = set()
    for name, index, how in _state["clicks"]:
        ob = obs.get(name)
        if ob is None:
            continue
        bm = bmesh.from_edit_mesh(ob.data)
        bm.faces.ensure_lookup_table()
        if index >= len(bm.faces):
            continue
        if how == "SET":
            for f in bm.faces:
                f.select_set(False)
            for e in bm.edges:
                e.select_set(False)
        _kind, elems = _elements(ob, bm.faces[index])
        for x in elems:
            x.select_set(how != "SUB")
        bm.select_flush_mode()
        touched.add(ob)
    for ob in touched:
        bmesh.update_edit_mesh(ob.data)


class BLENDA4D_OT_phong_pick(bpy.types.Operator):
    bl_idname = "blenda4d.phong_pick"
    bl_label = "Phong Break Selection"
    bl_description = "Select the smoothing area under the mouse (edge mode: the hard edges around it)"
    bl_options = {"REGISTER", "UNDO"}
    mode: bpy.props.EnumProperty(items=(("SET", "Set", "Replace the selection"), ("ADD", "Add", "Add to the selection"),
                                        ("SUB", "Subtract", "Remove from the selection")))

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def invoke(self, context, event):
        hit = _pick(context, (event.mouse_region_x, event.mouse_region_y))
        if hit is None:
            if self.mode == "SET":
                bpy.ops.mesh.select_all(action="DESELECT")
                _state["clicks"] = []
            return {"FINISHED"}
        ob, _bm, face = hit
        click = (ob.name, face.index, self.mode)
        _state["clicks"] = [click] if self.mode == "SET" else _state["clicks"] + [click]
        _replay(context)
        return {"FINISHED"}


class BLENDA4D_OT_phong_hover(bpy.types.Operator):
    bl_idname = "blenda4d.phong_hover"
    bl_label = "Phong Break Highlight"
    bl_description = "Highlight the smoothing area under the mouse"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def invoke(self, context, event):
        hit = _pick(context, (event.mouse_region_x, event.mouse_region_y))
        key = None if hit is None else (hit[0].name, hit[2].index, _settings(hit[0]),
                                        tuple(context.tool_settings.mesh_select_mode))
        if key != _state["hover"]:
            _state["hover"] = key
            _state["batch"] = _highlight(hit) if hit else None
            if context.area:
                context.area.tag_redraw()
        return {"PASS_THROUGH"}


def _highlight(hit):
    import gpu
    from gpu_extras.batch import batch_for_shader
    ob, _bm, face = hit
    kind, elems = _elements(ob, face)
    mw = ob.matrix_world
    sh = gpu.shader.from_builtin("UNIFORM_COLOR")
    if kind == "FACE":
        pts = []
        for f in elems:
            loops = list(f.loops)
            for i in range(1, len(loops) - 1):
                pts += [mw @ loops[0].vert.co, mw @ loops[i].vert.co, mw @ loops[i + 1].vert.co]
        return sh, batch_for_shader(sh, "TRIS", {"pos": pts}), kind
    pts = [mw @ v.co for e in elems for v in e.verts]
    return sh, batch_for_shader(sh, "LINES", {"pos": pts}), kind


def _active_tool(context):
    try:
        return context.workspace.tools.from_space_view3d_mode(context.mode, create=False).idname
    except (AttributeError, RuntimeError, TypeError):
        return None


def _draw():
    b = _state["batch"]
    context = bpy.context
    if b is None or context.mode != "EDIT_MESH" or _active_tool(context) != TOOL:
        return
    import gpu
    sh, batch, kind = b
    gpu.state.blend_set("ALPHA")
    gpu.state.depth_test_set("LESS_EQUAL")
    if kind != "FACE":
        gpu.state.line_width_set(3.0)
    sh.uniform_float("color", (1.0, 0.75, 0.45, 0.35) if kind == "FACE" else (1.0, 0.62, 0.22, 1.0))
    batch.draw(sh)
    gpu.state.line_width_set(1.0)
    gpu.state.depth_test_set("NONE")
    gpu.state.blend_set("NONE")


class BLENDA4D_OT_phong_select_all(bpy.types.Operator):
    bl_idname = "blenda4d.phong_select_all"
    bl_label = "Select All"
    bl_description = "Select every hard edge of the meshes being edited"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        context.tool_settings.mesh_select_mode = (False, True, False)
        for ob in context.objects_in_mode_unique_data:
            if ob.type != "MESH":
                continue
            bm = bmesh.from_edit_mesh(ob.data)
            angle, use = _settings(ob)
            for f in bm.faces:
                f.select_set(False)
            for e in bm.edges:
                e.select_set(not e.hide and _hard(e, angle, use))
            bm.select_flush_mode()
            bmesh.update_edit_mesh(ob.data)
        _state["clicks"] = []
        return {"FINISHED"}


class BLENDA4D_OT_phong_break_selection(bpy.types.Operator):
    bl_idname = "blenda4d.phong_break_selection"
    bl_label = "Phong Break Selection"
    bl_description = ("Select smoothing areas and their hard edges: click a polygon to select every polygon up to the "
                      "hard edges around it (edge mode: those edges). Shift adds, Ctrl removes")

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.type == "MESH"

    def execute(self, context):
        if context.mode != "EDIT_MESH":                       # a polygon tool: open the mesh in polygon mode
            bpy.ops.blenda4d.set_mode(mode="POLYGONS")
        if context.mode != "EDIT_MESH":
            self.report({"WARNING"}, "Phong Break Selection works on an editable mesh")
            return {"CANCELLED"}
        bpy.ops.wm.tool_set_by_id(name=TOOL, space_type="VIEW_3D")
        for a in context.screen.areas:                       # the Attribute Manager shows the tool's options
            a.tag_redraw()
        return {"FINISHED"}


def _changed(self, context):
    _state["hover"] = None
    _state["batch"] = None
    if context.mode == "EDIT_MESH" and _state["clicks"]:
        _replay(context)
    for w in context.window_manager.windows:
        for a in w.screen.areas:
            a.tag_redraw()


class BLENDA4D_PG_phong_tool(bpy.types.PropertyGroup):
    override: bpy.props.BoolProperty(
        name="Override Phong", default=True, update=_changed,
        description="Use this tool's Phong Angle; off, each object's own (its Phong or Smooth by Angle setting)")
    angle: bpy.props.FloatProperty(
        name="Phong Angle", default=10.0, min=0.0, max=180.0, precision=0, update=_changed,
        description="Polygons meeting at more than this angle are split into separate smoothing areas")
    use_edges: bpy.props.BoolProperty(
        name="Use Edge Breaks", default=True, update=_changed,
        description="Edges marked as breaks also split smoothing areas (Blender: edges marked sharp)")


def _options(layout, context, compact=False):
    t = context.scene.blenda4d_phong_tool
    col = layout.row() if compact else layout.column()
    col.prop(t, "override")
    sub = col.row(align=True)
    sub.active = t.override
    sub.prop(t, "angle")
    col.prop(t, "use_edges")
    if not compact:
        col.separator()
    col.operator("blenda4d.phong_select_all")


def draw_page(layout, context):
    """The Attribute Manager's page while this tool is active: its options. False when another tool is."""
    if context.mode != "EDIT_MESH" or _active_tool(context) != TOOL or not hasattr(context.scene, "blenda4d_phong_tool"):
        return False
    layout.label(text="Phong Break Selection", icon="RESTRICT_SELECT_OFF")
    layout.label(text="Options")
    col = layout.column()
    col.use_property_split = True
    col.use_property_decorate = False
    _options(col, context)
    return True


class BLENDA4D_WT_phong_break(bpy.types.WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "EDIT_MESH"
    bl_idname = TOOL
    bl_label = "Phong Break Selection"
    bl_description = ("Click a polygon to select its smoothing area (edge mode: the hard edges around it). "
                      "Shift adds, Ctrl removes")
    bl_icon = "ops.generic.select"
    bl_keymap = (
        ("blenda4d.phong_pick", {"type": "LEFTMOUSE", "value": "PRESS"}, {"properties": [("mode", "SET")]}),
        ("blenda4d.phong_pick", {"type": "LEFTMOUSE", "value": "PRESS", "shift": True}, {"properties": [("mode", "ADD")]}),
        ("blenda4d.phong_pick", {"type": "LEFTMOUSE", "value": "PRESS", "ctrl": True}, {"properties": [("mode", "SUB")]}),
        ("blenda4d.phong_pick", {"type": "LEFTMOUSE", "value": "PRESS", "oskey": True}, {"properties": [("mode", "SUB")]}),
        ("blenda4d.phong_hover", {"type": "MOUSEMOVE", "value": "ANY", "any": True}, None),
    )

    def draw_settings(context, layout, tool):
        _options(layout, context, compact=True)


CLASSES = (BLENDA4D_OT_phong_pick, BLENDA4D_OT_phong_hover, BLENDA4D_OT_phong_select_all,
           BLENDA4D_OT_phong_break_selection, BLENDA4D_PG_phong_tool)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.blenda4d_phong_tool = bpy.props.PointerProperty(type=BLENDA4D_PG_phong_tool)
    bpy.utils.register_tool(BLENDA4D_WT_phong_break, separator=True)
    _state["handle"] = bpy.types.SpaceView3D.draw_handler_add(_draw, (), "WINDOW", "POST_VIEW")


def unregister():
    if _state["handle"] is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_state["handle"], "WINDOW")
        _state["handle"] = None
    bpy.utils.unregister_tool(BLENDA4D_WT_phong_break)
    del bpy.types.Scene.blenda4d_phong_tool
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
    _state.update(clicks=[], hover=None, batch=None)
