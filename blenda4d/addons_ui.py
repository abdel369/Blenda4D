# SPDX-License-Identifier: GPL-3.0-or-later
"""Other add-ons' tools while Blenda mode is on.

Blenda's layout hides Blender's own menus, the viewport sidebar and the Properties editor, which is where installed
add-ons put their tools. The main menu's "Add-ons" menu gives them back:
  Add Menu Items / Object Menu Items   what add-ons added to Blender's Add and Object menus, under each add-on's
                                       name (found from the draw functions add-ons append to those menus), and
                                       Blender's whole menu as a sub-menu, so nothing is out of reach.
  Add-on Panels                        shows or hides the viewport sidebar, where add-ons have their own tabs
                                       (also in the viewport's Panel menu; N does the same in the viewport).
  Blender Properties...                a small window with Blender's own Properties editor: every tab and every
                                       add-on panel for the active object (also in the Attribute Manager's Edit menu).
The menus open over the main viewport, so an add-on's tool runs as if it had been picked from Blender's own menu.
Nothing is saved in the file. The Blender switch closes the Properties window."""
import sys

import bpy

OWN_PACKAGES = ("bl_ui", "bl_operators", "bpy", "bpy_extras", "_bpy_types", "bl_ui_utils", "nodeitems_utils")

# Blender menus whose add-on items are listed, grouped as in Blender (the Add menu and its sub-menus ...).
GROUPS = {
    "ADD": ("VIEW3D_MT_add", lambda n: n.startswith("VIEW3D_MT_") and n.endswith("_add")),
    "OBJECT": ("VIEW3D_MT_object", lambda n: n.startswith("VIEW3D_MT_object")),
}
_windows = []           # Properties windows opened here (window pointers)
_names = {}             # add-on module -> name shown


def _own_package():
    return __package__ or "blenda4d"


def _is_blender(module):
    if not module:
        return True
    own = _own_package()
    if module == own or module.startswith(own + "."):
        return True
    return module.split(".")[0] in OWN_PACKAGES


def _addon_of(module):
    """The enabled add-on (module name) a draw function comes from."""
    best = None
    for name in bpy.context.preferences.addons.keys():
        if (module == name or module.startswith(name + ".")) and (best is None or len(name) > len(best)):
            best = name
    return best or module.split(".")[0]


def addon_name(mod_name):
    if mod_name in _names:
        return _names[mod_name]
    label = None
    try:
        import addon_utils
        for m in addon_utils.modules(refresh=False):
            if m.__name__ == mod_name:
                label = addon_utils.module_bl_info(m).get("name")
                break
    except Exception:
        label = None
    if not label:
        mod = sys.modules.get(mod_name)
        label = getattr(mod, "bl_info", {}).get("name") if mod else None
    label = label or mod_name.rsplit(".", 1)[-1].replace("_", " ").title()
    _names[mod_name] = label
    return label


def _menus(group):
    top, match = GROUPS[group]
    names = [top] + sorted(n for n in dir(bpy.types) if n != top and match(n))
    out = []
    for n in names:
        cls = getattr(bpy.types, n, None)
        if isinstance(cls, type) and issubclass(cls, bpy.types.Menu):
            out.append(cls)
    return out


def contributions(group):
    """[(add-on name, [(menu class, draw function), ...]), ...] for the Add or Object group."""
    found = {}
    for cls in _menus(group):
        for fn in getattr(cls.draw, "_draw_funcs", ()) or ():
            mod = getattr(fn, "__module__", "") or ""
            if _is_blender(mod):
                continue
            found.setdefault(_addon_of(mod), []).append((cls, fn))
    return sorted(((addon_name(k), v) for k, v in found.items()), key=lambda e: e[0].lower())


def _menu_label(cls):
    return getattr(cls, "bl_label", "") or cls.__name__


def _draw_group(self, context, group):
    layout = self.layout
    layout.operator_context = "INVOKE_REGION_WIN"
    found = contributions(group)
    if not found:
        col = layout.column()
        col.enabled = False
        col.label(text="No add-on has added items here")
    for name, entries in found:
        layout.label(text=name, icon="PLUGIN")
        top = GROUPS[group][0]
        for cls, fn in entries:
            col = layout.column()
            col.operator_context = "INVOKE_REGION_WIN"
            if cls.__name__ != top:
                col.label(text="  " + _menu_label(cls) + ":")
            try:
                fn(_Proxy(self, col), context)
            except Exception as ex:
                sub = col.column()
                sub.enabled = False
                sub.label(text="(could not be drawn: %s)" % ex.__class__.__name__)
        layout.separator()
    layout.separator()
    layout.menu(GROUPS[group][0], text="All of Blender's %s Menu" % ("Add" if group == "ADD" else "Object"),
                icon="COLLAPSEMENU")


class _Proxy:
    """Lets an add-on's menu draw function write into a column of our menu, everything else from the menu itself."""

    def __init__(self, menu, layout):
        self._menu = menu
        self.layout = layout

    def __getattr__(self, name):
        return getattr(self._menu, name)


class BLENDA4D_MT_addons_add(bpy.types.Menu):
    bl_idname = "BLENDA4D_MT_addons_add"
    bl_label = "Add Menu Items"

    def draw(self, context):
        _draw_group(self, context, "ADD")


class BLENDA4D_MT_addons_object(bpy.types.Menu):
    bl_idname = "BLENDA4D_MT_addons_object"
    bl_label = "Object Menu Items"

    def draw(self, context):
        _draw_group(self, context, "OBJECT")


# --- the main viewport -------------------------------------------------------------------------------------------
def main_view(context):
    """(area, region) of the viewport to act in: the one the menu was opened from, or the largest in the window."""
    area = getattr(context, "area", None)
    if area is not None and area.type == "VIEW_3D":
        views = [area]
    else:
        window = context.window
        screen = window.screen if window else context.screen
        views = sorted((a for a in screen.areas if a.type == "VIEW_3D"), key=lambda a: -a.width * a.height) if screen else []
    if not views:
        return None, None
    region = next((r for r in views[0].regions if r.type == "WINDOW"), None)
    return views[0], region


class BLENDA4D_OT_addons_menu(bpy.types.Operator):
    bl_idname = "blenda4d.addons_menu"
    bl_label = "Add-on Menu Items"
    bl_description = "Show what installed add-ons added to Blender's menus, over the viewport"
    menu: bpy.props.StringProperty(default="BLENDA4D_MT_addons_add")

    def invoke(self, context, event):
        area, region = main_view(context)
        if area is None:
            bpy.ops.wm.call_menu(name=self.menu)
            return {"FINISHED"}
        with context.temp_override(window=context.window, area=area, region=region):
            bpy.ops.wm.call_menu(name=self.menu)
        return {"FINISHED"}

    def execute(self, context):
        return self.invoke(context, None)


class BLENDA4D_OT_addon_panels(bpy.types.Operator):
    bl_idname = "blenda4d.addon_panels"
    bl_label = "Add-on Panels"
    bl_description = "Show or hide the viewport sidebar, where installed add-ons have their own tabs"

    def execute(self, context):
        area, _region = main_view(context)
        if area is None:
            self.report({"INFO"}, "No viewport to show the panels in")
            return {"CANCELLED"}
        space = area.spaces.active
        space.show_region_ui = not space.show_region_ui
        area.tag_redraw()
        return {"FINISHED"}


def _own_windows(context):
    keep = {w.as_pointer(): w for w in context.window_manager.windows}
    _windows[:] = [p for p in _windows if p in keep]
    return [keep[p] for p in _windows]


class BLENDA4D_OT_blender_properties(bpy.types.Operator):
    bl_idname = "blenda4d.blender_properties"
    bl_label = "Blender Properties"
    bl_description = ("Open Blender's own Properties editor in a small window: all of its tabs and every add-on's "
                      "panels for the active object")

    def execute(self, context):
        wm = context.window_manager
        for old in _own_windows(context):          # Blender cannot bring a window to the front: open it again
            try:
                with context.temp_override(window=old):
                    bpy.ops.wm.window_close()
            except RuntimeError:
                pass
        before = {w.as_pointer() for w in wm.windows}
        bpy.ops.screen.drivers_editor_show("INVOKE_DEFAULT")       # Blender's way to open a small floating window
        win = next((w for w in wm.windows if w.as_pointer() not in before), None)
        if win is None:
            return {"CANCELLED"}
        _windows.append(win.as_pointer())
        area = win.screen.areas[0]
        area.type = "PROPERTIES"
        space = area.spaces.active
        for p in space.bl_rna.properties:
            if p.identifier.startswith("show_properties_"):
                setattr(space, p.identifier, True)
        space.show_region_header = True
        try:
            space.context = "OBJECT" if context.view_layer.objects.active else "SCENE"
        except TypeError:
            pass
        area.tag_redraw()
        return {"FINISHED"}


def close_windows():
    wm = bpy.context.window_manager
    if wm is None:
        return
    for w in _own_windows(bpy.context):
        try:
            with bpy.context.temp_override(window=w):
                bpy.ops.wm.window_close()
        except (RuntimeError, ReferenceError):
            pass
    _windows.clear()


# --- extra entries in Blenda's own menus ---------------------------------------------------------------------------
def _panel_menu(self, context):
    self.layout.separator()
    self.layout.operator("blenda4d.addon_panels", icon="MENU_PANEL")


def _am_edit_menu(self, context):
    self.layout.separator()
    self.layout.operator("blenda4d.blender_properties", text="Blender Properties...", icon="PROPERTIES")


HOOKS = (("BLENDA4D_MT_view_panel", _panel_menu), ("BLENDA4D_MT_am_edit", _am_edit_menu))
CLASSES = (BLENDA4D_MT_addons_add, BLENDA4D_MT_addons_object, BLENDA4D_OT_addons_menu, BLENDA4D_OT_addon_panels,
           BLENDA4D_OT_blender_properties)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    for idname, fn in HOOKS:
        menu = getattr(bpy.types, idname, None)
        if menu is not None:
            try:
                menu.remove(fn)
            except (ValueError, AttributeError):
                pass
            menu.append(fn)


def unregister():
    try:
        close_windows()
    except Exception as ex:
        print("Blenda 4D: Blender Properties window not closed:", ex)
    for idname, fn in HOOKS:
        menu = getattr(bpy.types, idname, None)
        if menu is not None:
            try:
                menu.remove(fn)
            except (ValueError, AttributeError):
                pass
    _names.clear()
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
