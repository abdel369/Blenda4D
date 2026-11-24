# SPDX-License-Identifier: GPL-3.0-or-later
"""Add-on preferences: whether Blenda 4D's layout is on when Blender starts."""
import bpy


class BLENDA4D_Prefs(bpy.types.AddonPreferences):
    bl_idname = __package__

    mode: bpy.props.BoolProperty(name="Start in Blenda 4D", default=True,
                                 description="Show Blenda 4D's layout when Blender starts")
    mm_filter: bpy.props.EnumProperty(
        name="Material Manager", default="HIGHLIGHT",
        description="What the Material Manager does with the materials of the selected objects",
        items=[("HIGHLIGHT", "Highlight Materials of Selected Objects",
                "Every material stays in the Material Manager; the ones the selected objects use are framed in white"),
               ("ONLY", "Show Only Materials of Selected Objects",
                "With objects selected, the Material Manager shows only their materials; with nothing selected, all of them")],
        update=lambda self, context: _mm_redraw())

    def draw(self, context):
        self.layout.prop(self, "mode")
        self.layout.prop(self, "mm_filter")
        from . import updates
        updates.draw_prefs(self.layout)


def _mm_redraw():
    try:
        from . import matman
        matman._tag_redraw()
    except Exception:
        pass


def get():
    return bpy.context.preferences.addons[__package__].preferences


def register():
    bpy.utils.register_class(BLENDA4D_Prefs)


def unregister():
    bpy.utils.unregister_class(BLENDA4D_Prefs)
