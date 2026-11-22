# SPDX-License-Identifier: GPL-3.0-or-later
"""Role areas: every Blenda manager is an area of its own, drawn with Blender's UI elements.

A role area is a Properties editor on its Tool tab, with its header and tab column hidden. The Tool tab has no
breadcrumb strip, and Blender draws the 3D View sidebar's "Tool" category inside it, so Blenda's panels register
there (VIEW_3D / UI / "Tool") and poll on the role of the area they are drawn in; in a real viewport sidebar the
role is None and they stay hidden. Which manager an area is lives in the editor's hidden tab flags, so it survives
saving, duplicating and switching.
"""
import bpy

ROLE_FLAGS = {
    "OBJECTS": "show_properties_world",
    "ATTRIBUTES": "show_properties_physics",
    "MATERIALS": "show_properties_particles",
    "VARIATIONS": "show_properties_effects",
    "PALETTE": "show_properties_texture",
    "MODES": "show_properties_constraints",
    "CREATE": "show_properties_modifiers",
    "ASSETS": "show_properties_data",
    "DOC_TABS": "show_properties_bone_constraints",
    "TIMELINE": "show_properties_material",
    "TL_BAR": "show_properties_collection",
    "TL_EDIT": "show_properties_object",
    "VIEW_TABS": "show_properties_strip",
    "MM_BAR": "show_properties_scene",
    "OM_BAR": "show_properties_output",
    "OM_HEAD": "show_properties_view_layer",
    "AB_BAR": "show_properties_bone",
}


def _flags(space):
    return [p.identifier for p in space.bl_rna.properties if p.identifier.startswith("show_properties_")]


def role(area):
    if area is None or area.type != "PROPERTIES" or not len(area.spaces):
        return None                            # an area being changed can have no editor yet: never read it
    space = area.spaces.active
    if space is None:
        return None
    if not getattr(space, "show_properties_tool", True):
        return None
    if space.show_region_header:               # only Render Settings, shown in the viewport's place, keeps its header:
        if getattr(space, "show_properties_render", False) and "RENDER" in ROLE_FLAGS:   # the viewport's tab row
            on = [name for name, flag in ROLE_FLAGS.items() if getattr(space, flag, False)]
            return "RENDER" if on == ["RENDER"] else None
        return None
    on = [name for name, flag in ROLE_FLAGS.items() if getattr(space, flag, False)]
    return on[0] if len(on) == 1 else None


def role_of(context):
    return role(getattr(context, "area", None))


def set_role(area, name):
    space = area.spaces.active
    try:
        space.context = "TOOL"
    except TypeError:
        pass
    for flag in _flags(space):
        setattr(space, flag, flag == "show_properties_tool" or flag == ROLE_FLAGS.get(name))
    space.show_region_header = False
    return space.context == "TOOL"


def areas(screen, name):
    return [a for a in screen.areas if role(a) == name]


def hide_nav(area, window=None):
    """A Properties editor's tab column can only be toggled with the operator."""
    for region in area.regions:
        if region.type == "NAVIGATION_BAR" and region.width > 1:
            kw = {"window": window} if window is not None else {}
            with bpy.context.temp_override(area=area, region=region, **kw):
                bpy.ops.screen.region_toggle(region_type="NAVIGATION_BAR")
            return True
    return False


class RolePanel:
    """Mixin for a Blenda panel that lives in one role area."""
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"
    bl_options = {"HIDE_HEADER"}
    role = None

    @classmethod
    def poll(cls, context):
        return role_of(context) == cls.role


# --- Blender's own Tool-tab panels are taken out while Blenda mode is on, and put back on switch-off -------------
_hidden = []


def hide_builtin_panels():
    for cls in list(bpy.types.Panel.__subclasses__()):
        if cls.__name__.startswith("BLENDA4D_") or not getattr(cls, "is_registered", False):
            continue
        if (getattr(cls, "bl_space_type", "") == "VIEW_3D" and getattr(cls, "bl_region_type", "") == "UI"
                and getattr(cls, "bl_category", "") == "Tool"):
            try:
                bpy.utils.unregister_class(cls)
                _hidden.append(cls)
            except RuntimeError:
                pass


def restore_builtin_panels():
    for cls in reversed(_hidden):
        try:
            bpy.utils.register_class(cls)
        except (RuntimeError, ValueError):
            pass
    _hidden.clear()


# --- the tab column can come back (a window still being laid out); its own draw hides it again right after -----
_nav_handle = []
_nav_pending = set()


def _nav_watch():
    context = bpy.context
    area, region = context.area, context.region
    if area is None or region is None or region.width <= 1 or role(area) is None:
        return
    key = area.as_pointer()
    if key in _nav_pending:
        return
    _nav_pending.add(key)
    window = context.window

    def hide():
        _nav_pending.discard(key)
        try:
            hide_nav(area, window)
        except (ReferenceError, RuntimeError):
            pass
        return None
    bpy.app.timers.register(hide, first_interval=0.0)


def register():
    hide_builtin_panels()
    _nav_handle.append(bpy.types.SpaceProperties.draw_handler_add(_nav_watch, (), "NAVIGATION_BAR", "POST_PIXEL"))


def unregister():
    while _nav_handle:
        bpy.types.SpaceProperties.draw_handler_remove(_nav_handle.pop(), "NAVIGATION_BAR")
    restore_builtin_panels()
