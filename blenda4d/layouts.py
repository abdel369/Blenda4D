# SPDX-License-Identifier: GPL-3.0-or-later
"""Saved layouts: one "Layout:" dropdown in the main menu bar. Standard is built in; every layout someone saves is
added to the list. A layout records which optional managers are shown and each area's share of the window."""
import json
import os

import bpy

from . import roles

STANDARD = "Standard"
_state = {"current": STANDARD}


def _file():
    folder = bpy.utils.user_resource("CONFIG", path="blenda4d", create=True)
    return os.path.join(folder, "layouts.json")


def load():
    try:
        with open(_file()) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data):
    with open(_file(), "w") as f:
        json.dump(data, f, indent=1)


def names():
    return [STANDARD] + sorted(load())


def current_name():
    return _state["current"]


def snapshot(window):
    screen = window.screen
    return {"materials": bool(roles.areas(screen, "MATERIALS")), "assets": bool(roles.areas(screen, "ASSETS")),
            "locked": False}


class BLENDA4D_OT_layout_use(bpy.types.Operator):
    bl_idname = "blenda4d.layout_use"
    bl_label = "Use Layout"
    bl_description = "Switch to this saved layout"
    name: bpy.props.StringProperty()

    def execute(self, context):
        from . import build
        entry = load().get(self.name, {}) if self.name != STANDARD else {}
        _state["current"] = self.name
        build.run_steps(build.steps(context.window, materials=entry.get("materials", False), assets=entry.get("assets", False)))
        return {"FINISHED"}


class BLENDA4D_OT_layout_save(bpy.types.Operator):
    bl_idname = "blenda4d.layout_save"
    bl_label = "Save Current Layout As"
    bl_description = "Save the current layout under a name; it is added to the Layout menu"
    name: bpy.props.StringProperty(name="Name", default="My Layout")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if not self.name.strip() or self.name == STANDARD:
            self.report({"WARNING"}, "Choose another name")
            return {"CANCELLED"}
        data = load()
        data[self.name] = snapshot(context.window)
        save(data)
        _state["current"] = self.name
        return {"FINISHED"}


class BLENDA4D_OT_layout_rename(bpy.types.Operator):
    bl_idname = "blenda4d.layout_rename"
    bl_label = "Rename Layout"
    bl_description = "Give this saved layout another name"
    name: bpy.props.StringProperty(name="New Name")

    @classmethod
    def poll(cls, context):
        return _state["current"] != STANDARD

    def invoke(self, context, event):
        self.name = _state["current"]
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        data = load()
        old = _state["current"]
        if old in data and self.name.strip() and self.name != STANDARD:
            data[self.name] = data.pop(old)
            save(data)
            _state["current"] = self.name
        return {"FINISHED"}


class BLENDA4D_OT_layout_delete(bpy.types.Operator):
    bl_idname = "blenda4d.layout_delete"
    bl_label = "Delete Layout"
    bl_description = "Delete this saved layout"

    @classmethod
    def poll(cls, context):
        return _state["current"] != STANDARD

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        data = load()
        data.pop(_state["current"], None)
        save(data)
        _state["current"] = STANDARD
        return {"FINISHED"}


class BLENDA4D_OT_layout_reset(bpy.types.Operator):
    bl_idname = "blenda4d.layout_reset"
    bl_label = "Reset to Default"
    bl_description = "Put the Standard layout back as it was first built"

    def execute(self, context):
        from . import build
        build.run_steps(build.steps(context.window))
        _state["current"] = STANDARD
        return {"FINISHED"}


class BLENDA4D_MT_layouts(bpy.types.Menu):
    bl_idname = "BLENDA4D_MT_layouts"
    bl_label = "Layout"

    def draw(self, context):
        layout = self.layout
        for n in names():
            layout.operator("blenda4d.layout_use", text=n, icon="CHECKMARK" if n == _state["current"] else "BLANK1").name = n
        layout.separator()
        layout.operator("blenda4d.layout_save", text="Save Current Layout As...")
        layout.operator("blenda4d.layout_rename", text="Rename Layout...")
        layout.operator("blenda4d.layout_delete", text="Delete Layout...")
        layout.separator()
        layout.operator("blenda4d.layout_reset", text="Reset to Default")
        col = layout.column()
        col.enabled = False
        col.operator("blenda4d.noop", text="Lock Layout")


classes = (BLENDA4D_OT_layout_use, BLENDA4D_OT_layout_save, BLENDA4D_OT_layout_rename, BLENDA4D_OT_layout_delete,
           BLENDA4D_OT_layout_reset, BLENDA4D_MT_layouts)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
