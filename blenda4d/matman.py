# SPDX-License-Identifier: GPL-3.0-or-later
"""Material Manager: menu row, tool row (New, Asset Browser, Apply, Pick, Delete, Delete Unused, Delete Duplicates,
Search), the materials as previews (Icon View), a list (List View) or a list with their textures (Layer View), and a
bottom strip with the three views and the preview size slider. Everything is Blender's own buttons and previews.

The bottom strip is an area of its own (role MM_BAR) under the Material Manager, because a panel cannot be pinned
to the bottom of its area."""
import bpy

from . import menus, roles

PX_MIN, PX_MAX = 20, 160
VIEWS = (("LIST", "List View", "Material names in a list", "LONGDISPLAY", 0),
         ("ICONS", "Icon View", "Material previews in a grid", "IMGDISPLAY", 1),
         ("LAYERS", "Layer View", "Material names in a list, each with the textures it uses", "RENDERLAYERS", 2))


def current(context):
    return bpy.data.materials.get(context.window_manager.b4d_material)


ORDER = "b4d_mm_order"     # a material's place in the Material Manager once it has been dragged (C4D: any order)
SEL = "b4d_mm_sel"         # selected in the Material Manager (the active one is wm.b4d_material)


def all_materials():
    out = [m for m in bpy.data.materials if not m.is_grease_pencil and not m.name.startswith(".")]
    out.reverse()                                     # newest first
    ranked = sorted((m for m in out if ORDER in m), key=lambda m: m[ORDER])
    return [m for m in out if ORDER not in m] + ranked    # new materials first, then the order the user dragged


def is_selected(context, mat):
    return mat.name == context.window_manager.b4d_material or bool(mat.get(SEL))


def selected(context):
    return [m for m in materials(context) if is_selected(context, m)]


def select_only(context, mats, active=None):
    names = {m.name for m in mats}
    for m in bpy.data.materials:
        if m.get(SEL) and m.name not in names:
            del m[SEL]
    for m in mats:
        m[SEL] = True
    if active is not None:
        context.window_manager.b4d_material = active.name
    elif context.window_manager.b4d_material not in names:
        context.window_manager.b4d_material = mats[0].name if mats else ""


def click_select(context, mat, event):
    """Click: only this material. Cmd/Ctrl: add or take away this one. Shift: every material from the active one to
    this one (C4D's Material Manager)."""
    wm = context.window_manager
    if event.oskey or event.ctrl:
        sel = selected(context)
        if mat in sel:
            sel.remove(mat)
            select_only(context, sel, sel[-1] if sel and wm.b4d_material == mat.name else None)
            if not sel:
                wm.b4d_material = ""
            return
        select_only(context, sel + [mat], mat)
        return
    if event.shift and current(context) is not None:
        mats = materials(context)
        a, b = mats.index(current(context)), mats.index(mat) if mat in mats else 0
        lo, hi = sorted((a, b))
        select_only(context, mats[lo:hi + 1], current(context))
        return
    select_only(context, [mat], mat)


def reorder(moving, before=None):
    """Put the moving materials just before another material (None: at the end), keeping everything else in order."""
    rest = [m for m in all_materials() if m not in moving]
    at = rest.index(before) if before in rest else len(rest)
    for i, m in enumerate(rest[:at] + list(moving) + rest[at:]):
        m[ORDER] = i


def only_selected():
    """True when the Material Manager shows only the selected objects' materials (the preference), else it
    highlights them."""
    try:
        from . import settings
        return settings.get().mm_filter == "ONLY"
    except (KeyError, AttributeError):
        return False


def used_by_selected(context):
    """The materials the selected objects use (their material tags), or None when no object is selected."""
    obs = [o for o in context.view_layer.objects if o.select_get()]
    if not obs:
        return None
    return {s.material.name for o in obs for s in getattr(o, "material_slots", ()) if s.material is not None}


def materials(context):
    wm = context.window_manager
    out = all_materials()
    if only_selected():
        used = used_by_selected(context)
        if used is not None:
            out = [m for m in out if m.name in used]
    if wm.b4d_mm_search and wm.b4d_mm_filter:
        needle = wm.b4d_mm_filter.lower()
        out = [m for m in out if needle in m.name.lower()]
    return out


def remove_material(mat):
    """Unpin it from any node editor first: freeing a tree an editor still shows crashes the next draw."""
    tree = mat.node_tree
    for screen in bpy.data.screens:
        for a in screen.areas:
            for sp in a.spaces:
                if sp.type == "NODE_EDITOR" and tree is not None and sp.node_tree == tree:
                    sp.pin = False
                    sp.node_tree = None
            a.tag_redraw()
    bpy.data.materials.remove(mat)


def _put_on(ob, mat):
    if not hasattr(getattr(ob, "data", None), "materials"):
        return False
    if ob.data.materials:
        ob.data.materials[0] = mat
    else:
        ob.data.materials.append(mat)
    return True


def _tag_redraw():
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            if roles.role(a) in ("MATERIALS", "MM_BAR", "OBJECTS", "ATTRIBUTES"):
                a.tag_redraw()


class BLENDA4D_OT_mm_apply(bpy.types.Operator):
    bl_idname = "blenda4d.mm_apply"
    bl_label = "Apply Material"
    bl_description = "Give the selected objects a material tag for each selected material"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return current(context) is not None and bool(sel_objects(context))

    def execute(self, context):
        mats = selected(context)                          # every selected material, as new tags (C4D: Apply)
        obs = [ob for ob in sel_objects(context) if hasattr(getattr(ob, "data", None), "materials")]
        from . import material_tag
        for ob in obs:
            for m in mats:
                ob.data.materials.append(m)
            material_tag.ensure(ob)
            from . import managers
            managers.show_last(ob)
            ob.update_tag()
        _tag_redraw()
        return {"FINISHED"} if obs and mats else {"CANCELLED"}


class BLENDA4D_OT_mm_pick(bpy.types.Operator):
    bl_idname = "blenda4d.mm_pick"
    bl_label = "Pick Material"
    bl_description = "Select the material of the active object"

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and bool(getattr(getattr(ob, "data", None), "materials", None)) and ob.data.materials[0] is not None

    def execute(self, context):
        context.window_manager.b4d_material = context.active_object.data.materials[0].name
        _tag_redraw()
        return {"FINISHED"}


class BLENDA4D_OT_mm_delete(bpy.types.Operator):
    bl_idname = "blenda4d.mm_delete"
    bl_label = "Delete Material"
    bl_description = "Delete the selected materials"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return current(context) is not None

    def invoke(self, context, event):
        used = [m for m in selected(context) if m.users - int(m.use_fake_user) > 0]
        if used:
            names = ", ".join(f"\"{m.name}\"" for m in used[:3]) + (" and more" if len(used) > 3 else "")
            return context.window_manager.invoke_confirm(self, event, title="Delete Material",
                                                         message=f"{names} {'is' if len(used) == 1 else 'are'} used by objects. Delete anyway?",
                                                         confirm_text="Delete")
        return self.execute(context)

    def execute(self, context):
        for m in selected(context):                       # every selected material
            remove_material(m)
        context.window_manager.b4d_material = ""
        _tag_redraw()
        return {"FINISHED"}


class BLENDA4D_OT_mm_delete_unused(bpy.types.Operator):
    bl_idname = "blenda4d.mm_delete_unused"
    bl_label = "Delete Unused Materials"
    bl_description = "Delete every material that no object uses"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # a deleted object's mesh stays until the file is saved and still counts as a user; leftovers do not count
        left = {}
        for coll in (bpy.data.meshes, bpy.data.curves, bpy.data.metaballs, bpy.data.volumes, bpy.data.hair_curves,
                     bpy.data.pointclouds):
            for d in coll:
                if d.users == 0:
                    for m in d.materials:
                        if m is not None:
                            left[m.name] = left.get(m.name, 0) + 1
        gone = 0
        for m in list(materials(context)):
            if m.users - int(m.use_fake_user) - left.get(m.name, 0) <= 0:
                remove_material(m)
                gone += 1
        if bpy.data.materials.get(context.window_manager.b4d_material) is None:
            context.window_manager.b4d_material = ""
        self.report({"INFO"}, f"Deleted {gone} unused material{'s' if gone != 1 else ''}")
        _tag_redraw()
        return {"FINISHED"}


def _socket_value(s):
    v = getattr(s, "default_value", None)
    try:
        return tuple(round(x, 5) for x in v)
    except TypeError:
        return round(v, 5) if isinstance(v, float) else v


def fingerprint(m):
    """Two materials are duplicates when every setting, node and link matches; names do not count."""
    own = tuple((p.identifier, repr(getattr(m, p.identifier))) for p in m.bl_rna.properties
                if p.type in ("BOOLEAN", "INT", "FLOAT", "ENUM") and not p.is_readonly and not getattr(p, "is_array", False)
                and p.identifier != "use_fake_user" and not p.identifier.startswith("paint_"))
    if m.node_tree is None:
        return own, tuple(round(x, 5) for x in m.diffuse_color)
    nodes = sorted(m.node_tree.nodes, key=lambda n: n.name)
    index = {n.name: i for i, n in enumerate(nodes)}
    data = []
    for n in nodes:
        extra = tuple((p.identifier, repr(getattr(n, p.identifier))) for p in n.bl_rna.properties
                      if p.type == "ENUM" and not p.is_readonly and p.identifier != "bl_static_type")
        data.append((n.bl_idname, extra, n.image.name if getattr(n, "image", None) else None,
                     tuple((s.name, _socket_value(s)) for s in n.inputs)))
    wires = sorted((index[l.from_node.name], l.from_socket.name, index[l.to_node.name], l.to_socket.name)
                   for l in m.node_tree.links)
    return own, tuple(data), tuple(wires)


class BLENDA4D_OT_mm_delete_duplicates(bpy.types.Operator):
    bl_idname = "blenda4d.mm_delete_duplicates"
    bl_label = "Delete Duplicate Materials"
    bl_description = "Delete materials identical to another one; whatever used them gets the one that stays"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        keep, gone = {}, 0
        for m in sorted(materials(context), key=lambda x: (len(x.name), x.name)):    # "Mat" stays, "Mat.001" goes
            k = keep.setdefault(fingerprint(m), m)
            if k != m:
                m.user_remap(k)
                remove_material(m)
                gone += 1
        if bpy.data.materials.get(context.window_manager.b4d_material) is None:
            context.window_manager.b4d_material = ""
        self.report({"INFO"}, f"Deleted {gone} duplicate material{'s' if gone != 1 else ''}")
        _tag_redraw()
        return {"FINISHED"}


CHECK_A = (0.541, 0.553, 0.565)       # the grey checkerboard behind each preview ball
CHECK_B = (0.380, 0.388, 0.396)
USED = 2                              # a tile's state besides selected (True): used by a selected object
USED_FRAME = (0.92, 0.92, 0.92)       # thin white frame: the selected objects use this material (Highlight)
FRAME = (0.992, 0.647, 0.247)         # thin orange frame around the selected material's preview
_pcoll = []
_tiles = {}                           # key -> (checksum, preview)


def tile_icon(mat, selected, px, layout):
    """Blender's own preview render of the material, laid on a checkerboard (and framed when selected).
    Falls back to the plain preview until Blender has rendered it."""
    import numpy as np
    plain = layout.icon(mat)
    ball = next((b for fn in BALLS for b in (fn(mat),) if b is not None), None) if _pcoll else None
    if ball is not None:                              # a renderer without previews: drawn from the material's values
        return _tile(mat, selected, px, ball)
    p = mat.preview
    if p is None or not _pcoll:
        return plain
    w, h = p.image_size
    pix = p.image_pixels_float
    if not w or not h:
        w, h = p.icon_size
        pix = p.icon_pixels_float
        if not w or not h:
            return plain
    src = np.empty(w * h * 4, np.float32)
    pix.foreach_get(src)
    if not src[3::4].any():
        return plain                                  # not rendered yet
    return _tile(mat, selected, px, src.reshape(h, w, 4))


BALLS = []                            # fn(material) -> its picture (height, width, 4) or None


def _tile(mat, selected, px, img):
    import numpy as np
    h, w = img.shape[:2]
    src = img.ravel()
    f = max(1, round(w / max(px, 1))) if selected else 0
    key = f"{mat.name}|{f}|{selected}"
    check = hash(src[::61].tobytes()) ^ hash((w, h))
    hit = _tiles.get(key)
    if hit is not None and hit[0] == check:
        return hit[1].icon_id
    sq = max(2, w // 8)
    yy, xx = np.mgrid[0:h, 0:w]
    bg = np.where((((yy // sq) + (xx // sq)) % 2 == 0)[..., None], np.array(CHECK_A, np.float32), np.array(CHECK_B, np.float32))
    a = img[..., 3:4]
    out = np.empty((h, w, 4), np.float32)
    out[..., :3] = img[..., :3] * a + bg * (1 - a)
    out[..., 3] = 1.0
    if f:
        for sl in (np.s_[:f, :], np.s_[-f:, :], np.s_[:, :f], np.s_[:, -f:]):
            out[sl][..., :3] = FRAME if selected != USED else USED_FRAME
    pcoll = _pcoll[0]
    prev = pcoll.get(key) or pcoll.new(key)
    prev.image_size = (w, h)
    prev.image_pixels_float.foreach_set(out.ravel())
    _tiles[key] = (check, prev)
    return prev.icon_id


def _textures(mat):
    if mat.node_tree is None:
        return []
    return sorted({n.image.name for n in mat.node_tree.nodes if getattr(n, "image", None) is not None})


_tool_scale = [1.25]       # the tool row's height scale as last drawn; GRID_TOP was measured at 1.25
TOOL_BUTTONS = 11


def draw_tools(layout, context):
    """The tool row under the menus: buttons joined in groups across the whole width (Blender shares the width out
    evenly), about as tall as they are wide."""
    layout.use_property_split = False
    wm = context.window_manager
    ui = context.preferences.system.ui_scale
    region = context.region
    width = (region.width / ui if region is not None else 250) - 2 * LEFT
    s = max(1.0, min(1.4, width / TOOL_BUTTONS / 20))
    _tool_scale[0] = s                                  # the tiles below start lower or higher with it (tile_at)
    row = layout.row(align=False)
    row.scale_y = s
    g = row.row(align=True)
    g.operator("blenda4d.new_material", text="", icon="ADD")
    g.operator("blenda4d.toggle_column", text="", icon="ASSET_MANAGER",
               depress=bool(roles.areas(context.screen, "ASSETS"))).name = "ASSETS"
    g = row.row(align=True)
    g.operator("blenda4d.mm_apply", text="", icon="CHECKMARK")
    g.operator("blenda4d.mm_pick", text="", icon="EYEDROPPER")
    g = row.row(align=True)
    g.operator("blenda4d.mm_delete", text="", icon="TRASH")
    g.operator("blenda4d.mm_delete_unused", text="", icon="ORPHAN_DATA")
    g.operator("blenda4d.mm_delete_duplicates", text="", icon="DUPLICATE")
    g = row.row(align=True)
    g.operator("blenda4d.mm_to_octane", text="", icon="SHADING_RENDERED")
    g.operator("blenda4d.mm_to_blender", text="", icon="BLENDER")
    g = row.row(align=True)
    g.operator("blenda4d.mm_filter_toggle", text="", icon="FILTER", depress=only_selected())
    g.prop(wm, "b4d_mm_search", text="", icon="VIEWZOOM", toggle=True, icon_only=True)
    if wm.b4d_mm_search:
        layout.prop(wm, "b4d_mm_filter", text="", icon="VIEWZOOM", placeholder="Search")


def draw_materials(layout, context):
    layout.use_property_split = False       # the Tool tab turns it on, which keeps an empty label column on the left
    wm = context.window_manager
    cur = wm.b4d_material
    mats = materials(context)
    used = used_by_selected(context) if not only_selected() else None
    used = used or set()

    def state(mat, on):
        return True if on else (USED if mat.name in used else False)
    if wm.b4d_mm_view == "ICONS":
        px = wm.b4d_mm_px
        cols, cw = grid_columns(context, px)
        grid = layout.column(align=True)               # rows packed close: a small gap, the name right under each ball
        for i in range(0, len(mats), cols):
            if i:
                grid.separator(factor=ROW_SEP)
            row = grid.row(align=True)
            row.alignment = "LEFT"
            for j in range(cols):
                if i + j >= len(mats):
                    break
                cell = row.column(align=True)
                cell.ui_units_x = cw / 20
                mat = mats[i + j]
                on = is_selected(context, mat)
                cell.template_icon(icon_value=tile_icon(mat, state(mat, on), px, layout), scale=px / 20)
                cell.operator("blenda4d.mat_pick", text=mat.name, emboss=on, depress=on).name = mat.name
        return
    col = layout.column(align=False)
    s = max(1.0, min(wm.b4d_mm_px, 80) / 20)            # the size slider grows the list rows too
    for mat in mats:
        row = col.row(align=False)
        row.alignment = "LEFT"
        on = is_selected(context, mat)
        row.template_icon(icon_value=tile_icon(mat, state(mat, on), wm.b4d_mm_px, layout), scale=s)
        name = row.column(align=True)
        name.separator(factor=max(0.0, (s - 1) * 1.25))     # level with the middle of the preview
        name.operator("blenda4d.mat_pick", text=mat.name, emboss=on, depress=on).name = mat.name
        if wm.b4d_mm_view == "LAYERS":
            texs = _textures(mat)
            box = col.column(align=True)
            box.active = False
            for t in texs or ["No textures"]:
                r = box.row()
                r.separator(factor=s * 2.2)
                r.label(text=t, icon="IMAGE_DATA" if texs else "BLANK1")


def draw_bar(layout, context):
    layout.use_property_split = False
    wm = context.window_manager
    row = layout.row(align=False)
    views = row.row(align=True)
    views.prop(wm, "b4d_mm_view", expand=True, icon_only=True)
    row.separator_spacer()
    size = row.row(align=True)
    size.ui_units_x = 8
    from .managers import size_bar
    size_bar(size, "b4d_mm_px", step=8)


class BLENDA4D_PT_mm_bar(roles.RolePanel, bpy.types.Panel):
    bl_label = "Material View"
    role = "MM_BAR"

    def draw(self, context):
        draw_bar(self.layout, context)


def _px_update(self, context):
    _tag_redraw()


GRID_TOP = 4.3         # units from the panel's top to the first row of tiles (title, menus, tool row): measured
NAME_UNITS = 1.0       # a tile's name button under its preview
TILE_GAP = 6           # pixels between tiles, side by side
ROW_SEP = 0.5          # separator factor between rows of tiles
ROW_GAP = 0.15         # units between rows of tiles that separator makes: measured (64 px tiles repeat every 87 px)
LEFT = 11              # pixels from the panel's left edge to the first tile's cell: measured


def grid_columns(context, px):
    """(columns, column width in pixels at 100 %) of the icon view: as many as fit, each a ball and a small gap."""
    ui = context.preferences.system.ui_scale
    cw = px + TILE_GAP
    return max(1, int((context.region.width / ui - LEFT - 4) // cw)), cw


def tile_at(context, x, y):
    """(material, "name" | "preview") under region point x, y in the icon view, or (None, None) on empty space."""
    wm = context.window_manager
    mats = materials(context)
    region = context.region
    if wm.b4d_mm_view != "ICONS" or region is None:
        return None, None
    ui = context.preferences.system.ui_scale
    unit = 20 * ui
    vx, vy = region.view2d.region_to_view(x, y)
    down = -vy                                      # view y runs down from 0 at the panel's top
    px = wm.b4d_mm_px
    cols, cw = grid_columns(context, px)
    pitch = px * ui + (NAME_UNITS + ROW_GAP) * unit
    top = (GRID_TOP + _tool_scale[0] - 1.25) * unit
    if down < top:
        return None, "above"                        # the title, menus and tool row
    row, dy = divmod(down - top, pitch)
    col = int((vx - LEFT * ui) // (cw * ui))
    if not 0 <= col < cols:
        return None, None
    i = int(row) * cols + col
    if i >= len(mats) or (vx - LEFT * ui) - col * cw * ui > px * ui:
        return None, None
    if dy <= px * ui:
        return mats[i], "preview"
    if dy <= px * ui + NAME_UNITS * unit:
        return mats[i], "name"
    return None, None


class BLENDA4D_OT_mm_double(bpy.types.Operator):
    bl_idname = "blenda4d.mm_double"
    bl_label = "Material Manager Double-Click"
    bl_description = "Double-click a material to open its nodes; its name to rename it; empty space for a new material"
    bl_options = {"UNDO", "INTERNAL"}
    name: bpy.props.StringProperty(options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return roles.role(context.area) == "MATERIALS"

    def invoke(self, context, event):
        mat, part = tile_at(context, event.mouse_region_x, event.mouse_region_y)
        if part == "above":
            return {"PASS_THROUGH"}
        if mat is None:
            bpy.ops.blenda4d.new_material()
            _tag_redraw()
            return {"FINISHED"}
        if part != "name":                          # the preview: the material's nodes in the Node Editor window
            from . import nodewin
            context.window_manager.b4d_material = mat.name
            nodewin.open_window(context, mat)
            return {"FINISHED"}
        self.name = mat.name
        context.window_manager.b4d_material = mat.name
        return context.window_manager.invoke_popup(self, width=max(160, context.window_manager.b4d_mm_px * 2))

    def draw(self, context):
        mat = bpy.data.materials.get(self.name)
        if mat is not None:
            self.layout.activate_init = True        # the field opens for typing with the whole name selected
            self.layout.prop(mat, "name", text="", icon="MATERIAL")

    def execute(self, context):
        return {"FINISHED"}


class BLENDA4D_OT_mm_click(bpy.types.Operator):
    bl_idname = "blenda4d.mm_click"
    bl_label = "Material Manager Click"
    bl_description = ("Click a material to select it, Cmd/Ctrl-click to add or take one away, Shift-click for every "
                      "material from the active one; click empty space to select none")
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        return roles.role(context.area) == "MATERIALS"

    def invoke(self, context, event):
        mat, part = tile_at(context, event.mouse_region_x, event.mouse_region_y)
        if part == "above" or (mat is None and context.window_manager.b4d_mm_view != "ICONS"):
            return {"PASS_THROUGH"}
        wm = context.window_manager
        from . import matpage
        if mat is None:                             # empty space: no material selected, the object shows again
            select_only(context, [])
            wm.b4d_material = ""
            if wm.b4d_am_subject.startswith(matpage.SUBJECT + ":"):
                wm.b4d_am_subject = ""
        else:
            click_select(context, mat, event)
            if current(context) is not None:
                matpage.show(context, current(context))
        for a in context.screen.areas:
            a.tag_redraw()
        return {"FINISHED"}


# --- tiles follow edits ---------------------------------------------------------------------------------------------
# A tile copies Blender's own preview of the material; Blender re-renders that preview only when it draws the
# material's icon itself, which the tiles never do. So an edited material asks for a new render here. (Blender's
# change list leaves out materials no object uses, so the nodes are compared instead.)
_stale = set()
_wait = [0]


_sigs = {}                   # material -> signature of what its preview shows


def _value(v):
    try:
        return tuple(round(x, 5) for x in v)
    except TypeError:
        return round(v, 5) if isinstance(v, float) else v


def _signature(mat):
    """What the preview depends on: every node's kind, unlinked input values and the links."""
    tree = mat.node_tree
    if not mat.use_nodes or tree is None:
        return hash((tuple(mat.diffuse_color), mat.metallic, mat.roughness))
    parts = []
    for n in tree.nodes:
        parts.append(n.bl_idname)
        for i in n.inputs:
            if not i.is_linked and hasattr(i, "default_value"):
                parts.append(_value(i.default_value))
        img = getattr(n, "image", None)
        if img is not None:
            parts.append(img.name)
    parts.extend((lk.from_socket.identifier, lk.from_node.name, lk.to_socket.identifier, lk.to_node.name) for lk in tree.links)
    return hash(tuple(parts))


def _watch():
    """While a Material Manager is open: a material whose nodes changed gets a new preview render."""
    wm = bpy.context.window_manager
    if wm is None or not any(roles.role(a) == "MATERIALS" for w in wm.windows for a in w.screen.areas):
        return 1.0
    for mat in bpy.data.materials:
        if mat.is_grease_pencil:
            continue
        sig = _signature(mat)
        old = _sigs.get(mat.name)
        _sigs[mat.name] = sig
        if old is not None and old != sig:
            _stale.add(mat.name)
    if _stale and not bpy.app.timers.is_registered(_rerender):
        bpy.app.timers.register(_rerender, first_interval=0.3)      # once the edit has settled
    return 0.5


def _rerender():
    wm = bpy.context.window_manager
    window = wm.windows[0] if wm and wm.windows else None
    for name in list(_stale):
        mat = bpy.data.materials.get(name)
        if mat is None or window is None:
            continue
        try:
            with bpy.context.temp_override(window=window, id=mat):
                bpy.ops.ed.lib_id_generate_preview()
        except (RuntimeError, TypeError):
            pass
    _stale.clear()
    _wait[0] = 12                                    # redraw for a few seconds while the render finishes
    if not bpy.app.timers.is_registered(_redraw_until_done):
        bpy.app.timers.register(_redraw_until_done, first_interval=0.25)
    return None


def _redraw_until_done():
    _tag_redraw()
    _wait[0] -= 1
    return 0.25 if _wait[0] > 0 else None


def tile_rect(context, region, i):
    """(x0, y0, x1, y1) in region pixels of tile i's preview and name in the icon view."""
    wm = context.window_manager
    ui = context.preferences.system.ui_scale
    unit = 20 * ui
    px = wm.b4d_mm_px
    cols, cw = grid_columns(context, px)
    pitch = px * ui + (NAME_UNITS + ROW_GAP) * unit
    row, col = divmod(i, cols)
    vx0 = LEFT * ui + col * cw * ui
    vtop = -((GRID_TOP + _tool_scale[0] - 1.25) * unit + row * pitch)
    x0, y1 = region.view2d.view_to_region(vx0, vtop, clip=False)
    x1, y0 = region.view2d.view_to_region(vx0 + px * ui, vtop - px * ui - NAME_UNITS * unit, clip=False)
    return x0, y0, x1, y1


_drag = {}                 # what the Material Manager draws while dragging: "box" or "line" (region pixels)
_draw = []


class BLENDA4D_OT_mm_drag(bpy.types.Operator):
    bl_idname = "blenda4d.mm_drag"
    bl_label = "Drag in the Material Manager"
    bl_description = ("Drag a selected material to move it (every selected one goes along), or onto an object in the "
                      "viewport or the Object Manager to give it a material tag; Cmd/Ctrl-drag drops "
                      "copies. Drag from empty space or an unselected material to select with a box (Shift or Cmd/Ctrl adds)")
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return roles.role(context.area) == "MATERIALS" and context.window_manager.b4d_mm_view == "ICONS"

    def invoke(self, context, event):
        self.region = context.region
        x, y = event.mouse_prev_press_x - self.region.x, event.mouse_prev_press_y - self.region.y
        mat, part = tile_at(context, x, y)
        if part == "above":
            return {"PASS_THROUGH"}
        self.mats = materials(context)
        self.copy = event.ctrl or event.oskey
        if mat is None or not is_selected(context, mat):   # C4D: from empty space or an unselected material, a box
            self.mode = "BOX"
            self.start_mat = mat                            # leaving the panel with it: it is dragged out instead
            self.add = event.shift or event.ctrl or event.oskey
            self.before = selected(context) if self.add else []
            _drag.clear()
            _drag["box"] = [x, y, x, y]
        else:                                               # a selected material: move them all (Cmd/Ctrl copies)
            self.mode = "MOVE"
            self.moving = selected(context)
            _drag.clear()
            context.window.cursor_modal_set("HAND")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _index(self, context, x, y):
        """Where a drop at region x, y goes in the shown list: before the tile under it (left half) or after it."""
        best = None
        for i in range(len(self.mats)):
            x0, y0, x1, y1 = tile_rect(context, self.region, i)
            if y0 <= y <= y1 and x0 - 8 <= x <= x1 + 8:
                return (i if x < (x0 + x1) / 2 else i + 1), (x0 - 3 if x < (x0 + x1) / 2 else x1 + 3, y0, y1)
            if y0 <= y <= y1 and x > x1:
                best = (i + 1, (x1 + 3, y0, y1))
        if best:
            return best
        if self.mats:
            x0, y0, x1, y1 = tile_rect(context, self.region, len(self.mats) - 1)
            if y < y0:
                return len(self.mats), (x1 + 3, y0, y1)
        return None, None

    def _box(self, context):
        x0, x1 = sorted((_drag["box"][0], _drag["box"][2]))
        y0, y1 = sorted((_drag["box"][1], _drag["box"][3]))
        hit = []
        for i, m in enumerate(self.mats):
            a0, b0, a1, b1 = tile_rect(context, self.region, i)
            if a1 >= x0 and a0 <= x1 and b1 >= y0 and b0 <= y1:
                hit.append(m)
        sel = self.before + [m for m in hit if m not in self.before]
        select_only(context, sel, hit[0] if hit and not self.add else None)
        if not sel:
            context.window_manager.b4d_material = ""

    def modal(self, context, event):
        x, y = event.mouse_x - self.region.x, event.mouse_y - self.region.y
        if event.type in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"}:
            if self.mode == "BOX" and getattr(self, "start_mat", None) is not None and not (
                    0 <= x < self.region.width and 0 <= y < self.region.height):
                select_only(context, [self.start_mat], self.start_mat)   # out of the panel: drag the material out
                self.mode, self.moving = "MOVE", [self.start_mat]
                _drag.clear()
                context.window.cursor_modal_set("HAND")
            elif self.mode == "BOX":
                _drag["box"][2:] = [x, y]
                self._box(context)
            else:
                _i, line = self._index(context, x, y)
                _drag.clear()
                if line:
                    _drag["line"] = line
            _tag_redraw()
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "RELEASE":
            if self.mode == "MOVE":
                context.window.cursor_modal_restore()
                if not (0 <= x < self.region.width and 0 <= y < self.region.height):
                    _drag.clear()
                    _tag_redraw()
                    return {"FINISHED"} if drop_on_object(context, self.moving, event) else {"CANCELLED"}
                i, _line = self._index(context, x, y)
                if i is not None:
                    shown = self.mats
                    after = [m for m in shown[i:] if m not in self.moving]
                    anchor = after[0] if after else None   # the drop goes just before this one (None: last)
                    if anchor is None and shown:
                        full = all_materials()
                        later = full[full.index(shown[-1]) + 1:] if shown[-1] in full else []
                        anchor = next((m for m in later if m not in self.moving), None)
                    moving = self.moving
                    if self.copy or event.ctrl or event.oskey:       # Cmd/Ctrl: copies, dropped here
                        moving = [m.copy() for m in self.moving]
                        for m in moving:
                            m.pop(ORDER, None)
                    reorder(moving, anchor)
                    select_only(context, moving, moving[0])
                    from . import matpage
                    matpage.show(context, moving[0])
            _drag.clear()
            _tag_redraw()
            return {"FINISHED"}
        if event.type in {"ESC", "RIGHTMOUSE"}:
            if self.mode == "BOX":
                select_only(context, self.before)
            else:
                context.window.cursor_modal_restore()
            _drag.clear()
            _tag_redraw()
            return {"CANCELLED"}
        return {"RUNNING_MODAL"}


def object_under(context, event):
    """The object under the mouse in a viewport (what its surface shows) or on an Object Manager row, or None."""
    from . import assets, managers
    area, region = assets._viewport_under(context, event.mouse_x, event.mouse_y)
    if area is not None:
        _loc, ob = assets.drop_point(context, region, event.mouse_x, event.mouse_y)
        return ob
    for a in context.window.screen.areas:
        if roles.role(a) != "OBJECTS":
            continue
        for r in a.regions:
            if r.type == "WINDOW" and r.x <= event.mouse_x < r.x + r.width and r.y <= event.mouse_y < r.y + r.height:
                with context.temp_override(area=a, region=r):
                    rows = managers.visible_rows(bpy.context)
                    i = managers.row_at(bpy.context, r, event.mouse_y)
                return rows[i][0] if 0 <= i < len(rows) else None
    return None


def drop_on_object(context, mats, event):
    """C4D: a material dropped on an object (in a viewport or on its Object Manager row) becomes a new material tag."""
    ob = object_under(context, event)
    if ob is None or not hasattr(getattr(ob, "data", None), "materials"):
        return False
    add_tags(context, ob, mats)
    return True


def add_tags(context, ob, mats):
    """New material tags on the object, the last one shown in the Attribute Manager with the object selected (C4D)."""
    from . import material_tag
    for m in mats:
        ob.data.materials.append(m)
    material_tag.ensure(ob)
    from . import managers
    managers.show_last(ob)
    ob.update_tag()
    vl = context.view_layer
    for o in vl.objects:
        if o is not None and o != ob and o.select_get():
            o.select_set(False)
    try:
        ob.select_set(True)
        vl.objects.active = ob
        context.window_manager.b4d_am_subject = f"{material_tag.SUBJECT}:{ob.name}:{len(ob.material_slots) - 1}"
    except RuntimeError:
        pass
    for a in context.window.screen.areas:
        a.tag_redraw()


def _draw_drag():
    context = bpy.context
    if not _drag or roles.role(context.area) != "MATERIALS":
        return
    import gpu
    from gpu_extras.batch import batch_for_shader
    sh = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.blend_set("ALPHA")
    if "box" in _drag:
        x0, x1 = sorted((_drag["box"][0], _drag["box"][2]))
        y0, y1 = sorted((_drag["box"][1], _drag["box"][3]))
        sh.uniform_float("color", (1.0, 1.0, 1.0, 0.08))
        batch_for_shader(sh, "TRIS", {"pos": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]}, indices=[(0, 1, 2), (0, 2, 3)]).draw(sh)
        sh.uniform_float("color", (1.0, 1.0, 1.0, 0.6))
        batch_for_shader(sh, "LINE_LOOP", {"pos": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]}).draw(sh)
    if "line" in _drag:
        x, y0, y1 = _drag["line"]
        w = max(1.0, context.preferences.system.ui_scale)
        sh.uniform_float("color", (0.92, 0.92, 0.92, 1.0))
        batch_for_shader(sh, "TRIS", {"pos": [(x - w, y0), (x + w, y0), (x + w, y1), (x - w, y1)]}, indices=[(0, 1, 2), (0, 2, 3)]).draw(sh)
    gpu.state.blend_set("NONE")


# --- right-click menu (C4D's Material Manager) ----------------------------------------------------------------------
class BLENDA4D_OT_mm_context(bpy.types.Operator):
    bl_idname = "blenda4d.mm_context"
    bl_label = "Material Menu"
    bl_description = "Right-click a material for what can be done with it"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        return roles.role(context.area) == "MATERIALS"

    def invoke(self, context, event):
        mat, part = tile_at(context, event.mouse_region_x, event.mouse_region_y)
        if part == "above":
            return {"PASS_THROUGH"}
        if mat is not None and not is_selected(context, mat):
            select_only(context, [mat], mat)                 # a right-click picks the material first, as in C4D
            _tag_redraw()
        bpy.ops.wm.call_menu(name="BLENDA4D_MT_mm_context")
        return {"FINISHED"}


class BLENDA4D_MT_mm_context(bpy.types.Menu):
    bl_idname = "BLENDA4D_MT_mm_context"
    bl_label = ""

    def draw(self, context):
        lay = self.layout
        lay.operator_context = "INVOKE_DEFAULT"
        lay.operator("blenda4d.mm_edit", text="Edit...", icon="NODETREE")
        lay.operator("blenda4d.mm_apply", text="Apply", icon="MATERIAL")
        lay.operator("blenda4d.mm_rename", text="Rename...", icon="SORTALPHA")
        lay.separator()
        lay.operator("blenda4d.mm_select_of_active", text="Select Materials of Active Objects", icon="RESTRICT_SELECT_OFF")
        lay.operator("blenda4d.mm_select_users", text="Select Material Tags/Objects", icon="OBJECT_DATA")
        lay.operator("blenda4d.mm_select_same", text="Select Materials with same Reflectance", icon="SHADING_RENDERED")
        lay.separator()
        lay.operator("blenda4d.mm_render", text="Render Materials", icon="RENDER_STILL").every = False
        lay.operator("blenda4d.mm_render", text="Render All Materials", icon="RENDERLAYERS").every = True
        lay.operator("blenda4d.mm_sort", text="Sort Materials", icon="SORTALPHA")
        lay.separator()
        lay.operator("blenda4d.mm_delete", text="Delete", icon="TRASH")
        lay.operator("blenda4d.mm_delete_unused", text="Delete Unused Materials", icon="TRASH")
        lay.operator("blenda4d.mm_delete_duplicates", text="Delete Duplicate Materials", icon="TRASH")


class BLENDA4D_OT_mm_edit(bpy.types.Operator):
    bl_idname = "blenda4d.mm_edit"
    bl_label = "Edit Material"
    bl_description = "Open the material in the Node Editor window"

    @classmethod
    def poll(cls, context):
        return current(context) is not None

    def execute(self, context):
        from . import nodewin
        nodewin.open_window(context, current(context))
        return {"FINISHED"}


class BLENDA4D_OT_mm_rename(bpy.types.Operator):
    bl_idname = "blenda4d.mm_rename"
    bl_label = "Rename Material"
    bl_description = "Rename the selected material"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return current(context) is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=200)

    def draw(self, context):
        mat = current(context)
        if mat is not None:
            self.layout.activate_init = True
            self.layout.prop(mat, "name", text="", icon="MATERIAL")

    def execute(self, context):
        return {"FINISHED"}


def sel_objects(context):
    """The selected objects, read from the view layer: in a Properties editor context.selected_objects can be empty."""
    return [o for o in context.view_layer.objects if o is not None and o.select_get()]


def _users(mats):
    names = {m.name for m in mats}
    return [ob for ob in bpy.context.scene.objects
            if any(s.material is not None and s.material.name in names for s in getattr(ob, "material_slots", []))]


class BLENDA4D_OT_mm_select_of_active(bpy.types.Operator):
    bl_idname = "blenda4d.mm_select_of_active"
    bl_label = "Select Materials of Active Objects"
    bl_description = "Select the materials the selected objects use"

    def execute(self, context):
        mats = []
        for ob in sel_objects(context):
            for s in getattr(ob, "material_slots", []):
                if s.material is not None and s.material not in mats:
                    mats.append(s.material)
        select_only(context, mats, mats[0] if mats else None)
        _tag_redraw()
        return {"FINISHED"}


class BLENDA4D_OT_mm_select_users(bpy.types.Operator):
    bl_idname = "blenda4d.mm_select_users"
    bl_label = "Select Material Tags/Objects"
    bl_description = "Select every object that has a tag with the selected materials"
    bl_options = {"UNDO"}

    def execute(self, context):
        users = _users(selected(context))
        for o in context.view_layer.objects:
            if o is not None:
                o.select_set(o in users)
        if users:
            context.view_layer.objects.active = users[0]
        _tag_redraw()
        return {"FINISHED"}


class BLENDA4D_OT_mm_select_same(bpy.types.Operator):
    bl_idname = "blenda4d.mm_select_same"
    bl_label = "Select Materials with same Reflectance"
    bl_description = "Select every material whose settings and nodes match the selected one"

    @classmethod
    def poll(cls, context):
        return current(context) is not None

    def execute(self, context):
        fp = fingerprint(current(context))
        same = [m for m in materials(context) if fingerprint(m) == fp]
        select_only(context, same, current(context))
        _tag_redraw()
        return {"FINISHED"}


class BLENDA4D_OT_mm_render(bpy.types.Operator):
    bl_idname = "blenda4d.mm_render"
    bl_label = "Render Materials"
    bl_description = "Render the previews again (the selected materials, or all)"
    every: bpy.props.BoolProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        for m in (materials(context) if self.every else selected(context)):
            _stale.add(m.name)
        if _stale and not bpy.app.timers.is_registered(_rerender):
            bpy.app.timers.register(_rerender, first_interval=0.05)
        return {"FINISHED"}


class BLENDA4D_OT_mm_sort(bpy.types.Operator):
    bl_idname = "blenda4d.mm_sort"
    bl_label = "Sort Materials"
    bl_description = "Put the materials in alphabetical order"
    bl_options = {"UNDO"}

    def execute(self, context):
        for i, m in enumerate(sorted(all_materials(), key=lambda m: m.name.lower())):
            m[ORDER] = i
        _tag_redraw()
        return {"FINISHED"}


_keys = []


class BLENDA4D_OT_mm_filter_toggle(bpy.types.Operator):
    """Show only the materials of the selected objects (on), or show every material and frame the selected objects'
    ones in white (off). Also in the add-on's preferences"""
    bl_idname = "blenda4d.mm_filter_toggle"
    bl_label = "Show Only Materials of Selected Objects"

    def execute(self, context):
        from . import settings
        p = settings.get()
        p.mm_filter = "HIGHLIGHT" if p.mm_filter == "ONLY" else "ONLY"
        context.preferences.is_dirty = True
        _tag_redraw()
        return {"FINISHED"}


_last_sel = [None]


@bpy.app.handlers.persistent
def _selection_changed(*_args):
    """Redraw the Material Manager when the selected objects change: it frames or shows their materials."""
    try:
        now = frozenset(o.name for o in bpy.context.view_layer.objects if o.select_get())
    except AttributeError:
        return
    if now != _last_sel[0]:
        _last_sel[0] = now
        _tag_redraw()


classes = (BLENDA4D_OT_mm_filter_toggle, BLENDA4D_OT_mm_click, BLENDA4D_OT_mm_drag, BLENDA4D_OT_mm_context, BLENDA4D_MT_mm_context, BLENDA4D_OT_mm_edit, BLENDA4D_OT_mm_rename,
           BLENDA4D_OT_mm_select_of_active, BLENDA4D_OT_mm_select_users, BLENDA4D_OT_mm_select_same, BLENDA4D_OT_mm_render, BLENDA4D_OT_mm_sort, BLENDA4D_OT_mm_double, BLENDA4D_OT_mm_apply, BLENDA4D_OT_mm_pick, BLENDA4D_OT_mm_delete, BLENDA4D_OT_mm_delete_unused,
           BLENDA4D_OT_mm_delete_duplicates, BLENDA4D_PT_mm_bar)


def register():
    import bpy.utils.previews
    _pcoll.append(bpy.utils.previews.new())
    for c in classes:
        bpy.utils.register_class(c)
    from . import matconvert, sceneconvert
    matconvert.register()
    sceneconvert.register()
    if _selection_changed not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_selection_changed)
    W = bpy.types.WindowManager
    W.b4d_mm_view = bpy.props.EnumProperty(description='Show materials as previews, as a list, or as a list with their textures', name="View", items=VIEWS, default="ICONS", update=_px_update)
    W.b4d_mm_px = bpy.props.IntProperty(description='How large the material previews are', name="Preview Size", default=64, min=PX_MIN, max=PX_MAX, subtype="PIXEL",
                                        update=_px_update)
    W.b4d_mm_search = bpy.props.BoolProperty(name="Search Materials", description="Search materials by name")
    W.b4d_mm_filter = bpy.props.StringProperty(description='Show only materials whose name contains this', name="Search", options={"TEXTEDIT_UPDATE"}, update=_px_update)
    if not bpy.app.timers.is_registered(_watch):
        bpy.app.timers.register(_watch, first_interval=1.0, persistent=True)
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is not None:
        km = kc.keymaps.new(name="Property Editor", space_type="PROPERTIES")
        _keys.append((km.name, km.keymap_items.new("blenda4d.mm_double", "LEFTMOUSE", "DOUBLE_CLICK").idname))
        for mods in ({}, {"shift": True}, {"ctrl": True}, {"oskey": True}):
            _keys.append((km.name, km.keymap_items.new("blenda4d.mm_click", "LEFTMOUSE", "CLICK", **mods).idname))
            _keys.append((km.name, km.keymap_items.new("blenda4d.mm_drag", "LEFTMOUSE", "CLICK_DRAG", **mods).idname))
        _keys.append((km.name, km.keymap_items.new("blenda4d.mm_context", "RIGHTMOUSE", "PRESS").idname))
        _draw.append(bpy.types.SpaceProperties.draw_handler_add(_draw_drag, (), "WINDOW", "POST_PIXEL"))


def unregister():
    from . import matconvert, sceneconvert
    sceneconvert.unregister()
    matconvert.unregister()
    if _selection_changed in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_selection_changed)
    while _draw:
        bpy.types.SpaceProperties.draw_handler_remove(_draw.pop(), "WINDOW")
    for t in (_watch, _rerender, _redraw_until_done):
        if bpy.app.timers.is_registered(t):
            bpy.app.timers.unregister(t)
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is not None:                               # looked up fresh: held keymap items can be freed at quit
        for name, idname in _keys:
            km = kc.keymaps.get(name)
            if km is not None:
                for kmi in list(km.keymap_items):
                    if kmi.idname == idname:
                        km.keymap_items.remove(kmi)
    _keys.clear()
    W = bpy.types.WindowManager
    for n in ("b4d_mm_view", "b4d_mm_px", "b4d_mm_search", "b4d_mm_filter"):
        delattr(W, n)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
    from bpy.utils import previews
    for pc in _pcoll:
        previews.remove(pc)
    _pcoll.clear()
    _tiles.clear()
