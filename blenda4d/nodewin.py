# SPDX-License-Identifier: GPL-3.0-or-later
"""The Node Editor window: one material's nodes in a window of their own.

  menu row      Create, Edit, View, Node, Select | + (add a node) | the material | Search (find a node)
  node canvas   Blender's shader node editor, pinned to this material, with a live preview on every node
  right panel   the material's preview, then the settings of the node you click (Blender's own controls, in
                sections); with no node picked, the material's page as in the Attribute Manager

Opened by double-clicking a material in the Material Manager, or Open Node Editor on the material page. The window's
screen carries the material's name (KEY), which is how the header and the panel know they are in this window."""
import bpy

from . import own_draw

KEY = "b4d_node_window"
CATEGORY = "Blenda 4D"
_own_header = [None]


def material_of(screen):
    name = screen.get(KEY) if screen is not None else None
    return bpy.data.materials.get(name) if name else None


def _previews_on(tree):
    for n in tree.nodes:
        if hasattr(n, "show_preview") and not n.show_preview and n.type not in {"FRAME", "REROUTE", "GROUP_INPUT",
                                                                                 "GROUP_OUTPUT"}:
            try:
                n.show_preview = True
            except (AttributeError, TypeError):
                pass


def _region(area, kind):
    return next((r for r in area.regions if r.type == kind), None)


def open_window(context, mat):
    """Open (or bring back) the Node Editor window for mat. True when it opened."""
    if not mat.use_nodes:
        mat.use_nodes = True
    wm = context.window_manager
    for w in wm.windows:                                  # already open for this material: show it again
        if w.screen.get(KEY) == mat.name:
            return True
    win = context.window or wm.windows[0]
    area = context.area if context.area is not None else max(win.screen.areas, key=lambda a: a.width * a.height)
    before = {w.as_pointer() for w in wm.windows}
    with context.temp_override(window=win, screen=win.screen, area=area):
        bpy.ops.wm.window_new()
    new = next((w for w in wm.windows if w.as_pointer() not in before), None)
    if new is None:
        return False
    new.screen[KEY] = mat.name
    ar = new.screen.areas[0]
    ar.type = "NODE_EDITOR"
    ar.ui_type = "ShaderNodeTree"
    sp = ar.spaces.active
    sp.shader_type = "OBJECT"
    sp.pin = True                                         # this material, whatever object is selected
    sp.node_tree = mat.node_tree
    sp.show_region_ui = True
    sp.show_region_toolbar = False
    sp.overlay.show_previews = True
    if hasattr(sp.overlay, "show_context_path"):
        sp.overlay.show_context_path = False             # no "Shader Nodetree" path in the corner
    _previews_on(mat.node_tree)

    def settle(tries=[30]):
        tries[0] -= 1
        try:
            reg = _region(ar, "WINDOW")
            side = _region(ar, "UI")
            if reg is None or reg.width < 2:
                return 0.05 if tries[0] > 0 else None
            if side is not None:
                try:
                    side.active_panel_category = CATEGORY
                except (TypeError, ValueError):
                    pass
            with bpy.context.temp_override(window=new, area=ar, region=reg):
                bpy.ops.node.view_all()
        except (ReferenceError, RuntimeError):
            pass
        return None
    bpy.app.timers.register(settle, first_interval=0.1)
    _keep_previews()
    return True


def _keep_previews():
    """While a Node Editor window is open, nodes added there show their preview too."""
    if bpy.app.timers.is_registered(_tick):
        return
    bpy.app.timers.register(_tick, first_interval=1.0)


def _tick():
    open_ = False
    for w in bpy.context.window_manager.windows:
        mat = material_of(w.screen)
        if mat is not None and mat.node_tree is not None:
            open_ = True
            _previews_on(mat.node_tree)
    return 1.0 if open_ else None


# --- the menu row ---------------------------------------------------------------------------------------------------

class BLENDA4D_MT_nodewin_edit(bpy.types.Menu):
    bl_label = "Edit"

    def draw(self, context):
        lay = self.layout
        lay.operator("ed.undo", text="Undo")
        lay.operator("ed.redo", text="Redo")
        lay.separator()
        lay.operator("node.clipboard_copy", text="Copy")
        lay.operator("node.clipboard_paste", text="Paste")
        lay.operator("node.duplicate_move", text="Duplicate")
        lay.operator("node.delete", text="Delete")
        lay.separator()
        lay.operator("node.select_all", text="Select All").action = "SELECT"
        lay.operator("node.select_all", text="Deselect All").action = "DESELECT"


def _header(self, context):
    mat = material_of(context.screen)
    if mat is None:
        return _own_header[0](self, context)
    lay = self.layout
    row = lay.row(align=True)
    row.menu("NODE_MT_add", text="Create")
    row.menu("BLENDA4D_MT_nodewin_edit", text="Edit")
    row.menu("NODE_MT_view", text="View")
    row.menu("NODE_MT_node", text="Node")
    row.menu("NODE_MT_select", text="Select")
    lay.separator(factor=2)
    lay.menu("NODE_MT_add", text="", icon="ADD")
    lay.label(text=mat.name, icon_value=lay.icon(mat))
    lay.separator_spacer()
    lay.operator("node.find_node", text="Search", icon="VIEWZOOM")


# --- the right panel ------------------------------------------------------------------------------------------------

class BLENDA4D_PT_nodewin(bpy.types.Panel):
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = CATEGORY
    bl_label = "Node"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return material_of(context.screen) is not None

    def draw(self, context):
        mat = material_of(context.screen)
        lay = self.layout
        tree = mat.node_tree
        node = tree.nodes.active if tree is not None else None
        if node is not None and (not node.select or node.type in {"OUTPUT_MATERIAL", "FRAME", "REROUTE"}):
            node = None
        head = lay.row()
        head.label(text=f"Material [{mat.name}]", icon_value=lay.icon(mat))
        ball = lay.split(factor=0.5)                      # the ball at the top left, half the panel wide
        ball.template_preview(mat, show_buttons=False)
        ball.column()
        from . import matpage
        if node is None:
            matpage.draw_material(lay, context, mat, head=False)
            return
        lay.separator()
        lay.label(text=node.label or node.name, icon="NODE")
        if hasattr(node, "draw_buttons_ext"):
            box = lay.column()
            node.draw_buttons_ext(context, box)
        col = lay.column()
        col.use_property_split = True
        col.use_property_decorate = False
        col.template_node_inputs(node)


classes = (BLENDA4D_MT_nodewin_edit, BLENDA4D_PT_nodewin)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    _own_header[0] = own_draw.swap("NODE_HT_header", _header)


def unregister():
    if _own_header[0] is not None:
        own_draw.restore("NODE_HT_header", _header)
        _own_header[0] = None
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
