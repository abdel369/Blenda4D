# SPDX-License-Identifier: GPL-3.0-or-later
"""The camera's Attribute Manager pages: Object (lens, field of view, film offset, focus), Physical (depth of field and
aperture), Details (clipping) and Composition (framing guides). Every row is one of Blender's own camera settings;
settings Blender has no equivalent for are left out rather than shown greyed."""

import bpy

from . import managers

TABS = [("PHYSICAL", "Physical", ""), ("DETAILS", "Details", ""), ("COMPOSITION", "Composition", "")]
TITLES = {"OBJECT": "Object Properties", "PHYSICAL": "Physical", "DETAILS": "Details", "COMPOSITION": "Composition Helpers"}

# guide toggle -> Blender's camera flag (two columns, as laid out on the page)
GUIDES = (("Grid", "show_composition_thirds"), ("Diagonal", "show_composition_center_diagonal"),
          ("Triangles", "show_composition_harmony_tri_a"), ("Golden Section", "show_composition_golden"),
          ("Crosshair", "show_composition_center"))


LABEL_SPLIT = 0.5            # label half / field half, so long names such as Field of View (Horizontal) fit


def _row(col, owner, attr, label, active=True, **kw):
    r = col.row(align=True)
    r.use_property_split = False                      # this row lays out its own label | field halves
    r.use_property_decorate = False
    r.active = bool(active)
    if owner.bl_rna.properties[attr].type == "BOOLEAN":
        sp = r.split(factor=LABEL_SPLIT)
        sp.label(text="")
        sp.prop(owner, attr, text=label, **kw)
    else:
        sp = r.split(factor=LABEL_SPLIT, align=True)
        lab = sp.row()
        lab.alignment = "RIGHT"
        lab.label(text=label)
        sp.prop(owner, attr, text="", **kw)
    r.prop_decorator(owner, attr)
    return r


def page_object(col, ob):
    cam = ob.data
    persp = cam.type == "PERSP"
    _row(col, cam, "type", "Projection")
    col.separator()
    _row(col, cam, "lens", "Focal Length", persp)
    _row(col, cam, "sensor_width", "Sensor Size")
    eq = cam.lens * 36.0 / max(cam.sensor_width, 0.001)
    r = col.row()
    r.active = persp
    r.label(text=f"35 mm equivalent focal length: {eq:.0f} mm")
    _row(col, cam, "angle_x", "Field of View (Horizontal)", persp)
    _row(col, cam, "angle_y", "Field of View (Vertical)", persp)
    _row(col, cam, "ortho_scale", "Zoom", cam.type == "ORTHO")
    col.separator()
    _row(col, cam, "b4d_offset_x", "Film Offset X (%)")
    _row(col, cam, "b4d_offset_y", "Film Offset Y (%)")
    col.separator()
    r = col.row(align=True)
    r.use_property_split = False
    r.use_property_decorate = False
    sp = r.split(factor=LABEL_SPLIT, align=True)
    lab = sp.row()
    lab.alignment = "RIGHT"
    lab.label(text="Focus Distance")
    f = sp.row(align=True)
    f.prop(cam.dof, "focus_distance", text="")
    f.operator("ui.eyedropper_depth", text="", icon="EYEDROPPER")
    r.prop_decorator(cam.dof, "focus_distance")
    _row(col, cam.dof, "focus_object", "Focus Object")


def page_physical(col, ob):
    dof = ob.data.dof
    _row(col, dof, "use_dof", "Depth of Field")
    col.separator()
    _row(col, dof, "aperture_fstop", "F-Stop (f/#)", dof.use_dof)
    col.separator()
    _row(col, dof, "aperture_blades", "Aperture Blades", dof.use_dof)
    _row(col, dof, "aperture_rotation", "Aperture Rotation", dof.use_dof)
    _row(col, dof, "aperture_ratio", "Aperture Ratio", dof.use_dof)


def page_details(col, ob):
    cam = ob.data
    _row(col, cam, "clip_start", "Near Clipping")
    _row(col, cam, "clip_end", "Far Clipping")
    col.separator()
    _row(col, cam, "show_limits", "Show Clipping Range")


def page_composition(col, ob):
    cam = ob.data
    _row(col, cam, "b4d_guides", "Enable")
    col.separator()
    grid = col.grid_flow(row_major=True, columns=2, even_columns=True)
    grid.use_property_split = False                   # checkbox with its name beside it, no keyframe dots
    grid.use_property_decorate = False
    grid.active = cam.b4d_guides
    for label, flag in GUIDES:
        grid.prop(cam, flag, text=label)


PAGES = {"OBJECT": page_object, "PHYSICAL": page_physical, "DETAILS": page_details, "COMPOSITION": page_composition}


# --- settings shown in the C4D-style units ---------------------------------------------------------------------------
def _offset(axis):
    attr = "shift_" + axis

    def get(self):
        return getattr(self, attr) * 100.0

    def set(self, v):
        setattr(self, attr, v / 100.0)
    return get, set


def _guides_get(self):
    return bool(self.get("b4d_guides_off") is None)


def _guides_set(self, on):
    """Turning the guides off remembers which were on; turning them back on restores them."""
    if not on and self.get("b4d_guides_off") is None:
        self["b4d_guides_off"] = [f for _l, f in GUIDES if getattr(self, f)]
        for _l, f in GUIDES:
            setattr(self, f, False)
    elif on and self.get("b4d_guides_off") is not None:
        for f in self["b4d_guides_off"]:
            setattr(self, f, True)
        del self["b4d_guides_off"]


def register():
    C = bpy.types.Camera
    for axis in ("x", "y"):
        g, s = _offset(axis)
        setattr(C, "b4d_offset_" + axis, bpy.props.FloatProperty(
            name="Film Offset " + axis.upper(), get=g, set=s, step=10, precision=1,
            description=f"Shift the image {('sideways' if axis == 'x' else 'up and down')} without turning the camera "
                        f"(Blender: Shift {axis.upper()})"))
    C.b4d_guides = bpy.props.BoolProperty(name="Composition Helpers", get=_guides_get, set=_guides_set,
                                          description="Show the framing guides chosen below in the camera view")
    managers.CAMERA_PAGES.update(PAGES)
    managers.CAMERA_TABS[:] = TABS
    managers.CAMERA_TITLES.update(TITLES)


def unregister():
    managers.CAMERA_PAGES.clear()
    managers.CAMERA_TABS.clear()
    managers.CAMERA_TITLES.clear()
    for n in ("b4d_offset_x", "b4d_offset_y", "b4d_guides"):
        if hasattr(bpy.types.Camera, n):
            delattr(bpy.types.Camera, n)
