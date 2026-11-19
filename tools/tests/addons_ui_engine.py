# Headless check of the Add-ons menu lists: a draw function from an outside module appended to Blender's Add menu
# and to a sub-menu (Mesh) is listed under that module's name; Blender's own and Blenda's are not.
#   Blender -b --factory-startup --python tools/tests/addons_ui_engine.py      (prints "B4D AO ok/FAIL ...")
import os
import sys

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
import blenda4d  # noqa: E402

blenda4d.register()
from blenda4d import switch  # noqa: E402

switch.set_mode(True)
from blenda4d import addons_ui  # noqa: E402

fails = []


def check(cond, what):
    print("B4D AO", "ok" if cond else "FAIL", what, flush=True)
    if not cond:
        fails.append(what)


def fake_add(self, context):
    self.layout.operator("mesh.primitive_cube_add", text="Fake Cube")


def fake_mesh(self, context):
    self.layout.operator("mesh.primitive_cube_add", text="Fake Mesh Cube")


def fake_object(self, context):
    self.layout.operator("object.shade_smooth", text="Fake Smooth")


for fn in (fake_add, fake_mesh, fake_object):
    fn.__module__ = "fake_tools_addon"
bpy.types.VIEW3D_MT_add.append(fake_add)
bpy.types.VIEW3D_MT_mesh_add.append(fake_mesh)
bpy.types.VIEW3D_MT_object.append(fake_object)

add = dict(addons_ui.contributions("ADD"))
check(list(add) == ["Fake Tools Addon"], f"Add group lists only the outside add-on {list(add)}")
names = sorted(c.__name__ for c, f in add.get("Fake Tools Addon", []))
check(names == ["VIEW3D_MT_add", "VIEW3D_MT_mesh_add"], f"Add menu and Mesh sub-menu both found {names}")
obj = dict(addons_ui.contributions("OBJECT"))
check([f.__name__ for c, f in obj.get("Fake Tools Addon", [])] == ["fake_object"], "Object menu item found")
check(addons_ui._is_blender("bl_ui.space_view3d") and addons_ui._is_blender(addons_ui.__package__),
      "Blender's and Blenda's own draw functions are left out")
check(not addons_ui._is_blender("bl_ext.user_default.some_tool"), "extensions count as add-ons")
for op in ("addons_menu", "addon_panels", "blender_properties"):
    check(hasattr(bpy.ops.blenda4d, op) and getattr(bpy.ops.blenda4d, op).get_rna_type() is not None, "operator " + op)
panel_menu = bpy.types.BLENDA4D_MT_view_panel.draw._draw_funcs
check(panel_menu.count(addons_ui._panel_menu) == 1, "Panel menu has Add-on Panels once")
check(bpy.types.BLENDA4D_MT_am_edit.draw._draw_funcs.count(addons_ui._am_edit_menu) == 1, "AM Edit menu entry once")
switch.set_mode(False)
check(not hasattr(bpy.types, "BLENDA4D_MT_addons_add"), "switch off: menus taken back")
check(fake_add in bpy.types.VIEW3D_MT_add.draw._draw_funcs, "switch off: the add-on's own menu entry is untouched")
switch.set_mode(True)
check(bpy.types.BLENDA4D_MT_view_panel.draw._draw_funcs.count(addons_ui._panel_menu) == 1, "on again: Panel entry once")
switch.set_mode(False)
blenda4d.unregister()
print("B4D AO", "ALL OK" if not fails else "FAILS %d" % len(fails), flush=True)
