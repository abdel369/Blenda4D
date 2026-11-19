# SPDX-License-Identifier: GPL-3.0-or-later
"""Render Settings: a floating window drawn with Blender's own lists, fields and menus.

Left: the Renderer dropdown, the list of sections (Output, Save, Multi-Pass, Anti-Aliasing, Options, Material
Override, and the renderer's own sections), then the scene's saved render settings and a "Render Setting..." menu.
Right: the page of the section picked in the list, with its title on top.

A scene keeps any number of named render settings; one is active and the scene shows its values. Picking another
setting stores what the scene shows into the one that was active, then puts the picked one's values on the scene.
Saving the file stores the active one first, so reopening and switching never writes old values back.

Frame Range, Frame Rate and Save act when rendering through blenda4d.render (Render menu): the scene's frame range
and rate are set for the render and put back when it ends or is cancelled.

Opened from the viewport's "Render Settings" tab and Render > Render Settings...; the window is a Properties editor
on its Tool tab with the RENDER role (see roles.py)."""
import json

import bpy

from . import roles

ROLE = "RENDER"
DEFAULT_NAME = "Render Setting"

# --- tables ------------------------------------------------------------------------------------------------------
PRESETS = (("CUSTOM", "Custom", 0, 0), ("HD720", "1280 x 720 (HD)", 1280, 720), ("HD1080", "1920 x 1080 (Full HD)", 1920, 1080),
           ("UHD", "3840 x 2160 (4K UHD)", 3840, 2160), ("DCI2K", "2048 x 1080 (2K)", 2048, 1080),
           ("DCI4K", "4096 x 2160 (4K)", 4096, 2160), ("SQ1080", "1080 x 1080 (Square)", 1080, 1080),
           ("VERT1080", "1080 x 1920 (Vertical)", 1080, 1920), ("SOCIAL", "1080 x 1350 (Portrait 4:5)", 1080, 1350),
           ("VGA", "640 x 480", 640, 480), ("SD", "720 x 576 (SD)", 720, 576))
SIZE_UNITS = (("PX", "Pixels", ""), ("CM", "cm", ""), ("MM", "mm", ""), ("IN", "Inches", ""), ("PT", "Points", ""),
              ("PC", "Picas", ""))
PER_INCH = {"CM": 2.54, "MM": 25.4, "IN": 1.0, "PT": 72.0, "PC": 6.0}
DPI_UNITS = (("IN", "Pixels/Inch (DPI)", ""), ("CM", "Pixels/cm", ""))
FILM = (("CUSTOM", "Custom", 0.0), ("SQUARE", "Square (1:1)", 1.0), ("STD", "Standard (4:3)", 4 / 3),
        ("HDTV", "HDTV (16:9)", 16 / 9), ("PHOTO", "Photo (3:2)", 1.5), ("PORTRAIT", "Portrait (4:5)", 0.8),
        ("VERT", "Vertical (9:16)", 9 / 16), ("WIDE", "Widescreen (1.85:1)", 1.85), ("SCOPE", "Scope (2.39:1)", 2.39))
PIXEL = (("CUSTOM", "Custom", 0.0), ("SQUARE", "Square", 1.0), ("ANA133", "Anamorphic (1.333)", 4 / 3),
         ("ANA2", "Anamorphic (2.0)", 2.0))
FRAME_RANGES = (("MANUAL", "Manual", "Render the frames from From to To"),
                ("CURRENT", "Current Frame", "Render only the frame the timeline is on"),
                ("ALL", "All Frames", "Render the scene's whole frame range"),
                ("PREVIEW", "Preview Range", "Render the timeline's preview range"))
PASSES = (("pass_z", "use_pass_z", "Depth"), ("pass_mist", "use_pass_mist", "Mist"), ("pass_normal", "use_pass_normal", "Normal"),
          ("pass_ao", "use_pass_ambient_occlusion", "Ambient Occlusion"), ("pass_diffuse", "use_pass_diffuse_color", "Diffuse Color"),
          ("pass_glossy", "use_pass_glossy_color", "Glossy Color"), ("pass_emit", "use_pass_emit", "Emission"),
          ("pass_env", "use_pass_environment", "Environment"), ("pass_object", "use_pass_object_index", "Object Index"),
          ("pass_material", "use_pass_material_index", "Material Index"))
# (key, title, switch) of every section; switch = (owner kind, attribute) of the checkbox beside its list row
PAGES = (("OUTPUT", "Output", None), ("SAVE", "Save", ("rs", "save")), ("MULTIPASS", "Multi-Pass", ("rs", "multipass")),
         ("AA", "Anti-Aliasing", None), ("OPTIONS", "Options", None), ("OVERRIDE", "Material Override", ("rs", "material_override")),
         ("MOTION_BLUR", "Motion Blur", ("render", "use_motion_blur")), ("COLOR", "Color Management", None),
         ("LIGHT_PATHS", "Light Paths", None), ("VOLUMES", "Volumes", None))

# What a render setting stores: (owner, attribute). Owners are resolved by _owner().
TRACK = (
    ("render", "engine"),
    ("render", "resolution_x"), ("render", "resolution_y"), ("render", "resolution_percentage"),
    ("render", "pixel_aspect_x"), ("render", "pixel_aspect_y"), ("render", "fps"), ("render", "fps_base"),
    ("render", "use_border"), ("render", "use_crop_to_border"), ("render", "border_min_x"), ("render", "border_max_x"),
    ("render", "border_min_y"), ("render", "border_max_y"),
    ("rs", "lock_ratio"), ("rs", "dpi"), ("rs", "dpi_unit"), ("rs", "size_unit"), ("rs", "use_scene_fps"), ("rs", "fps"),
    ("rs", "frame_range"), ("rs", "frame_from"), ("rs", "frame_to"), ("rs", "frame_step"), ("rs", "annotations"),
    ("rs", "save"),
    ("render", "filepath"), ("render", "use_file_extension"), ("render", "use_overwrite"), ("render", "use_placeholder"),
    ("image", "file_format"), ("image", "color_mode"), ("image", "color_depth"), ("image", "quality"),
    ("image", "compression"), ("render", "film_transparent"),
    ("rs", "multipass"), *(("rs", p[0]) for p in PASSES),
    ("rs", "material_override"), ("rs", "override_material"),
    ("eevee", "taa_render_samples"), ("eevee", "taa_samples"), ("render", "filter_size"),
    ("cycles", "samples"), ("cycles", "preview_samples"), ("cycles", "use_adaptive_sampling"),
    ("cycles", "adaptive_threshold"), ("cycles", "adaptive_min_samples"), ("cycles", "time_limit"),
    ("cycles", "use_denoising"), ("cycles", "denoiser"), ("cycles", "use_preview_denoising"),
    ("cycles", "pixel_filter_type"), ("cycles", "filter_width"),
    ("display", "render_aa"), ("display", "viewport_aa"),
    ("render", "use_simplify"), ("render", "simplify_subdivision_render"), ("render", "simplify_child_particles_render"),
    ("render", "threads_mode"), ("render", "threads"), ("render", "use_persistent_data"), ("render", "dither_intensity"),
    ("render", "use_compositing"),
    ("render", "use_motion_blur"), ("render", "motion_blur_position"), ("render", "motion_blur_shutter"),
    ("cycles", "rolling_shutter_type"), ("cycles", "rolling_shutter_duration"),
    ("eevee", "motion_blur_steps"), ("eevee", "motion_blur_max"), ("eevee", "motion_blur_depth_scale"),
    ("display_device", "display_device"), ("view", "view_transform"), ("view", "look"), ("view", "exposure"),
    ("view", "gamma"),
    ("cycles", "max_bounces"), ("cycles", "diffuse_bounces"), ("cycles", "glossy_bounces"),
    ("cycles", "transmission_bounces"), ("cycles", "volume_bounces"), ("cycles", "transparent_max_bounces"),
    ("cycles", "sample_clamp_direct"), ("cycles", "sample_clamp_indirect"), ("cycles", "blur_glossy"),
    ("cycles", "caustics_reflective"), ("cycles", "caustics_refractive"),
    ("eevee", "volumetric_tile_size"), ("eevee", "volumetric_samples"), ("eevee", "volumetric_sample_distribution"),
    ("eevee", "volumetric_start"), ("eevee", "volumetric_end"), ("eevee", "use_volumetric_shadows"),
    ("eevee", "volumetric_shadow_samples"),
)
# set before the rest: which values are allowed later depends on these
FIRST = (("render", "engine"), ("display_device", "display_device"), ("view", "view_transform"),
         ("image", "file_format"), ("image", "color_mode"), ("image", "color_depth"))
# a new setting keeps the scene's own values for these (a new setting must not send renders somewhere else, and
# Blender's built-in defaults for colour management do not match what a new file uses)
KEEP_ON_NEW = {"render.filepath", "display_device.display_device", "view.view_transform", "view.look"}
# a new setting starts from these where Blender's own default is not the usual starting point
NEW_VALUES = {"render.resolution_x": 1280, "render.resolution_y": 720}


def _owner(scene, kind):
    if kind == "render":
        return scene.render
    if kind == "image":
        return scene.render.image_settings
    if kind == "view":
        return scene.view_settings
    if kind == "display_device":
        return scene.display_settings
    if kind == "display":
        return scene.display
    if kind == "rs":
        return scene.b4d_render
    return getattr(scene, kind, None)          # "cycles" only exists while the Cycles add-on is on


def capture(scene):
    """The scene's current render values, as plain JSON-ready values."""
    out = {}
    for kind, attr in TRACK:
        own = _owner(scene, kind)
        if own is None or not hasattr(own, attr):
            continue
        v = getattr(own, attr)
        if isinstance(v, bpy.types.ID):
            v = v.name
        elif v is None:
            v = ""
        out[f"{kind}.{attr}"] = round(v, 6) if isinstance(v, float) else v
    return out


def apply_values(scene, values):
    """Put stored values on the scene; a value the scene no longer accepts is skipped."""
    first = [f"{k}.{a}" for k, a in FIRST]
    for key in first + [k for k in values if k not in first]:
        if key not in values:
            continue
        kind, attr = key.split(".", 1)
        own = _owner(scene, kind)
        if own is None or not hasattr(own, attr):
            continue
        v = values[key]
        if key == "rs.override_material":
            v = bpy.data.materials.get(v) if v else None
        try:
            if getattr(own, attr) != v:
                setattr(own, attr, v)
        except (TypeError, ValueError, AttributeError):
            pass


def defaults(scene):
    """Blender's built-in default for every tracked value (used by New)."""
    out = {}
    for kind, attr in TRACK:
        own = _owner(scene, kind)
        key = f"{kind}.{attr}"
        if own is None or not hasattr(own, attr):
            continue
        if key in KEEP_ON_NEW:
            out[key] = getattr(own, attr)
            continue
        if key in NEW_VALUES:
            out[key] = NEW_VALUES[key]
            continue
        prop = own.bl_rna.properties[attr]
        if prop.type == "POINTER":
            out[key] = ""
            continue
        d = getattr(prop, "default", None)
        if prop.type == "ENUM" and d not in {i.identifier for i in prop.enum_items}:
            d = getattr(own, attr)
        out[key] = d if d is not None else getattr(own, attr)
    return out


# --- values the Output page shows (they read and write the real render data) -------------------------------------
def _sc(p):
    return p.id_data


def _ratio(rd):
    return rd.resolution_x / max(1, rd.resolution_y)


def _w_set(self, v):
    rd = _sc(self).render
    r = _ratio(rd)
    rd.resolution_x = max(4, v)
    if self.lock_ratio:
        rd.resolution_y = max(4, round(rd.resolution_x / r))


def _h_set(self, v):
    rd = _sc(self).render
    r = _ratio(rd)
    rd.resolution_y = max(4, v)
    if self.lock_ratio:
        rd.resolution_x = max(4, round(rd.resolution_y * r))


def _per_unit(self):
    return self.dpi / PER_INCH[self.size_unit] if self.size_unit != "PX" else 1.0


def _preset_get(self):
    rd = _sc(self).render
    return next((i for i, row in enumerate(PRESETS) if i and (row[2], row[3]) == (rd.resolution_x, rd.resolution_y)), 0)


def _preset_set(self, i):
    if i:
        rd = _sc(self).render
        rd.resolution_x, rd.resolution_y = PRESETS[i][2], PRESETS[i][3]


def _table_get(table, value):
    return next((i for i, row in enumerate(table) if i and abs(row[2] - value) < 0.002), 0)


def _film_get(self):
    return _ratio(_sc(self).render)


def _film_set(self, v):
    rd = _sc(self).render
    rd.resolution_y = max(4, round(rd.resolution_x / max(0.001, v)))


def _pix_get(self):
    rd = _sc(self).render
    return rd.pixel_aspect_x / max(1e-6, rd.pixel_aspect_y)


def _pix_set(self, v):
    rd = _sc(self).render
    rd.pixel_aspect_x, rd.pixel_aspect_y = max(1.0, v), max(1.0, 1.0 / max(1e-6, v))


def _border(attr, flip, wide):
    def get(self):
        rd = _sc(self).render
        size = rd.resolution_x if wide else rd.resolution_y
        v = getattr(rd, attr)
        return round((1 - v if flip else v) * size)

    def set_(self, v):
        rd = _sc(self).render
        size = rd.resolution_x if wide else rd.resolution_y
        f = max(0.0, min(1.0, v / max(1, size)))
        setattr(rd, attr, 1 - f if flip else f)
    return get, set_


def _dpi_changed(self, _context):
    rd = _sc(self).render
    rd.ppm_base, rd.ppm_factor = 0.0254, self.dpi        # pixels per inch, written into saved images


def _dpi_v_get(self):
    return self.dpi / 2.54 if self.dpi_unit == "CM" else self.dpi


def _dpi_v_set(self, v):
    self.dpi = v * 2.54 if self.dpi_unit == "CM" else v


def frame_span(scene):
    """(first, last, step) the Frame Range setting renders."""
    p = scene.b4d_render
    if p.frame_range == "ALL":
        return scene.frame_start, scene.frame_end, scene.frame_step
    if p.frame_range == "PREVIEW" and scene.use_preview_range:
        return scene.frame_preview_start, scene.frame_preview_end, scene.frame_step
    if p.frame_range == "PREVIEW":
        return scene.frame_start, scene.frame_end, scene.frame_step
    if p.frame_range == "MANUAL":
        return p.frame_from, max(p.frame_from, p.frame_to), p.frame_step
    return scene.frame_current, scene.frame_current, 1


def _span_get(index):
    def get(self):
        return frame_span(_sc(self))[index]
    return get


def _span_set(attr):
    def set_(self, v):                     # typing a frame switches Frame Range to Manual
        first, last, step = frame_span(_sc(self))
        self.frame_from, self.frame_to, self.frame_step = first, last, step
        setattr(self, attr, v)
        self.frame_range = "MANUAL"
    return set_


def _passes_changed(self, _context):
    """Multi-Pass on: the passes ticked on its page are rendered. Off: only the combined image."""
    for vl in _sc(self).view_layers:
        for prop, attr, _label in PASSES:
            if hasattr(vl, attr):
                setattr(vl, attr, self.multipass and getattr(self, prop))


def _override_changed(self, _context):
    mat = self.override_material if self.material_override else None
    for vl in _sc(self).view_layers:
        if vl.material_override != mat:
            vl.material_override = mat


def _pass(name):
    return bpy.props.BoolProperty(name=name, default=False, update=_passes_changed)


class BLENDA4D_RenderProps(bpy.types.PropertyGroup):
    pass_z: _pass("Depth")
    pass_mist: _pass("Mist")
    pass_normal: _pass("Normal")
    pass_ao: _pass("Ambient Occlusion")
    pass_diffuse: _pass("Diffuse Color")
    pass_glossy: _pass("Glossy Color")
    pass_emit: _pass("Emission")
    pass_env: _pass("Environment")
    pass_object: _pass("Object Index")
    pass_material: _pass("Material Index")
    save: bpy.props.BoolProperty(name="Save", default=True,
                                 description="Write still renders to the file below (animations are always written)")
    multipass: bpy.props.BoolProperty(name="Multi-Pass", default=False, update=_passes_changed,
                                      description="Render the extra image passes ticked on the Multi-Pass page")
    material_override: bpy.props.BoolProperty(name="Material Override", default=False, update=_override_changed,
                                              description="Render every object with one material")
    override_material: bpy.props.PointerProperty(type=bpy.types.Material, name="Material", update=_override_changed)
    lock_ratio: bpy.props.BoolProperty(name="Lock Ratio", default=False,
                                       description="Changing the width or height keeps the picture's proportions")
    dpi: bpy.props.FloatProperty(name="Resolution", default=72.0, min=1.0, update=_dpi_changed)
    dpi_unit: bpy.props.EnumProperty(name="Resolution Unit", items=DPI_UNITS, default="IN")
    size_unit: bpy.props.EnumProperty(name="Size Unit", items=SIZE_UNITS, default="PX",
                                      description="Show the width and height in pixels or as a print size at this resolution")
    use_scene_fps: bpy.props.BoolProperty(name="Use Scene Frame Rate", default=True,
                                            description="Render at the scene's frame rate; off, render at the rate below")
    fps: bpy.props.IntProperty(name="Frame Rate", default=30, min=1, max=1000)
    frame_range: bpy.props.EnumProperty(name="Frame Range", items=FRAME_RANGES, default="CURRENT")
    frame_from: bpy.props.IntProperty(name="From", default=0)
    frame_to: bpy.props.IntProperty(name="To", default=0)
    frame_step: bpy.props.IntProperty(name="Frame Step", default=1, min=1)
    annotations: bpy.props.StringProperty(name="Annotations", default="", description="A note kept with this render setting")
    show_region: bpy.props.BoolProperty(name="Region Borders", default=False, description="Show the region's borders")
    # the fields the Output page shows
    v_preset: bpy.props.EnumProperty(name="Preset", items=[(r[0], r[1], "") for r in PRESETS], get=_preset_get, set=_preset_set)
    v_width: bpy.props.IntProperty(name="Width", min=4, soft_max=16384, subtype="PIXEL",
                                   get=lambda s: _sc(s).render.resolution_x, set=_w_set)
    v_height: bpy.props.IntProperty(name="Height", min=4, soft_max=16384, subtype="PIXEL",
                                    get=lambda s: _sc(s).render.resolution_y, set=_h_set)
    v_phys_w: bpy.props.FloatProperty(name="Width", precision=2, min=0.0, get=lambda s: _sc(s).render.resolution_x / _per_unit(s),
                                      set=lambda s, v: _w_set(s, round(v * _per_unit(s))))
    v_phys_h: bpy.props.FloatProperty(name="Height", precision=2, min=0.0, get=lambda s: _sc(s).render.resolution_y / _per_unit(s),
                                      set=lambda s, v: _h_set(s, round(v * _per_unit(s))))
    v_dpi: bpy.props.FloatProperty(name="Resolution", precision=0, min=1.0, get=_dpi_v_get, set=_dpi_v_set,
                                   description="Pixels per inch or per cm, saved into the images; sets the print size")
    v_film: bpy.props.FloatProperty(name="Film Aspect", precision=4, min=0.001, max=1000.0, get=_film_get, set=_film_set,
                                    description="Width divided by height; changing it changes the height")
    v_film_p: bpy.props.EnumProperty(name="Film Aspect Preset", items=[(r[0], r[1], "") for r in FILM],
                                     get=lambda s: _table_get(FILM, _film_get(s)), set=lambda s, i: i and _film_set(s, FILM[i][2]))
    v_pix: bpy.props.FloatProperty(name="Pixel Aspect", precision=3, min=0.001, max=1000.0, get=_pix_get, set=_pix_set,
                                   description="Shape of one pixel: 1 is square, above 1 is wider than tall")
    v_pix_p: bpy.props.EnumProperty(name="Pixel Aspect Preset", items=[(r[0], r[1], "") for r in PIXEL],
                                    get=lambda s: _table_get(PIXEL, _pix_get(s)), set=lambda s, i: i and _pix_set(s, PIXEL[i][2]))
    v_left: bpy.props.IntProperty(name="Left Border", min=0, get=_border("border_min_x", False, True)[0], set=_border("border_min_x", False, True)[1])
    v_right: bpy.props.IntProperty(name="Right Border", min=0, get=_border("border_max_x", True, True)[0], set=_border("border_max_x", True, True)[1])
    v_top: bpy.props.IntProperty(name="Top Border", min=0, get=_border("border_max_y", True, False)[0], set=_border("border_max_y", True, False)[1])
    v_bottom: bpy.props.IntProperty(name="Bottom Border", min=0, get=_border("border_min_y", False, False)[0], set=_border("border_min_y", False, False)[1])
    v_from: bpy.props.IntProperty(name="From", get=_span_get(0), set=_span_set("frame_from"))
    v_to: bpy.props.IntProperty(name="To", get=_span_get(1), set=_span_set("frame_to"))
    v_step: bpy.props.IntProperty(name="Frame Step", min=1, get=_span_get(2), set=_span_set("frame_step"))


# --- the list of render settings -------------------------------------------------------------------------------
def sets(scene):
    return scene.b4d_rsets


def commit(scene):
    """Store what the scene shows into the active render setting."""
    i = scene.b4d_rs_loaded
    if 0 <= i < len(sets(scene)):
        sets(scene)[i].values = json.dumps(capture(scene))


def load(scene, index):
    scene.b4d_rs_loaded = index
    apply_values(scene, json.loads(sets(scene)[index].values or "{}"))


def ensure(scene):
    """The first render setting takes over the scene as it stands."""
    if len(sets(scene)):
        return
    r = sets(scene).add()
    r.name = DEFAULT_NAME
    scene.b4d_rs_loaded = 0
    _set_index(scene, 0)
    commit(scene)


def _unique(scene, base):
    names = {r.name for r in sets(scene)}
    if base not in names:
        return base
    i = 1
    while f"{base}.{i:03d}" in names:
        i += 1
    return f"{base}.{i:03d}"


_quiet = [False]


def _set_index(scene, index):
    """Move the list's highlight without the update below running."""
    _quiet[0] = True
    try:
        scene.b4d_rs_index = index
    finally:
        _quiet[0] = False


def _picked(scene, _context):
    """List selection changed: the picked setting becomes the active one."""
    if _quiet[0]:
        return
    i = scene.b4d_rs_index
    if not (0 <= i < len(sets(scene))) or i == scene.b4d_rs_loaded:
        return
    commit(scene)
    load(scene, i)


def _select(scene, index):
    """Make index active without storing the scene into it first (it already holds its own values)."""
    _set_index(scene, index)
    load(scene, index)


class BLENDA4D_RenderSet(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name", default=DEFAULT_NAME)
    values: bpy.props.StringProperty(default="{}")


class BLENDA4D_RenderPage(bpy.types.PropertyGroup):
    key: bpy.props.StringProperty()


class BLENDA4D_UL_render_sets(bpy.types.UIList):
    bl_idname = "BLENDA4D_UL_render_sets"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):
        layout.prop(item, "name", text="", emboss=False, icon="RENDER_STILL")


def page_shown(scene, key):
    e = scene.render.engine
    if key == "MOTION_BLUR":
        return e != "BLENDER_WORKBENCH"
    if key == "LIGHT_PATHS":
        return e == "CYCLES" and getattr(scene, "cycles", None) is not None
    if key == "VOLUMES":
        return e == "BLENDER_EEVEE"
    return True


def _switch_owner(scene, switch):
    return scene.b4d_render if switch[0] == "rs" else scene.render


class BLENDA4D_UL_render_pages(bpy.types.UIList):
    bl_idname = "BLENDA4D_UL_render_pages"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):
        page = next((p for p in PAGES if p[0] == item.key), None)
        if page is None:
            return
        row = layout.row(align=True)
        if page[2]:
            row.prop(_switch_owner(context.scene, page[2]), page[2][1], text="")
        else:
            row.label(text="", icon="BLANK1")
        row.label(text=page[1])

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        flags = [self.bitflag_filter_item if page_shown(context.scene, it.key) else 0 for it in items]
        return flags, []


def ensure_pages(wm):
    pages = wm.b4d_rs_pages
    if [p.key for p in pages] == [p[0] for p in PAGES]:
        return
    pages.clear()
    for key, _title, _switch in PAGES:
        pages.add().key = key


def current_page(context):
    wm = context.window_manager
    i = wm.b4d_rs_page
    key = wm.b4d_rs_pages[i].key if 0 <= i < len(wm.b4d_rs_pages) else "OUTPUT"
    return key if page_shown(context.scene, key) else "OUTPUT"


# --- operators ---------------------------------------------------------------------------------------------------
class BLENDA4D_OT_rs_add(bpy.types.Operator):
    bl_idname = "blenda4d.rs_add"
    bl_label = "New"
    bl_description = "Add a render setting with default values and make it the active one"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        ensure(scene)
        commit(scene)
        r = sets(scene).add()
        r.name = _unique(scene, DEFAULT_NAME)
        r.values = json.dumps(defaults(scene))
        _select(scene, len(sets(scene)) - 1)
        return {"FINISHED"}


class BLENDA4D_OT_rs_duplicate(bpy.types.Operator):
    bl_idname = "blenda4d.rs_duplicate"
    bl_label = "Duplicate"
    bl_description = "Copy the active render setting and make the copy the active one"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        ensure(scene)
        commit(scene)
        src = sets(scene)[scene.b4d_rs_loaded]
        r = sets(scene).add()
        r.name = _unique(scene, src.name)
        r.values = src.values
        sets(scene).move(len(sets(scene)) - 1, scene.b4d_rs_loaded + 1)
        _select(scene, scene.b4d_rs_loaded + 1)
        return {"FINISHED"}


class BLENDA4D_OT_rs_remove(bpy.types.Operator):
    bl_idname = "blenda4d.rs_remove"
    bl_label = "Delete"
    bl_description = "Delete the active render setting; the one above it becomes active"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return len(sets(context.scene)) > 1

    def execute(self, context):
        scene = context.scene
        i = scene.b4d_rs_loaded
        sets(scene).remove(i)
        _select(scene, max(0, min(i - 1, len(sets(scene)) - 1)))
        return {"FINISHED"}


class BLENDA4D_OT_rs_move(bpy.types.Operator):
    bl_idname = "blenda4d.rs_move"
    bl_label = "Move"
    bl_description = "Move the active render setting up or down the list"
    bl_options = {"REGISTER", "UNDO"}
    step: bpy.props.IntProperty(default=-1)

    @classmethod
    def description(cls, context, props):
        return "Move the active render setting up the list" if props.step < 0 else "Move the active render setting down the list"

    def execute(self, context):
        scene = context.scene
        i = scene.b4d_rs_loaded
        j = i + self.step
        if not (0 <= i < len(sets(scene)) and 0 <= j < len(sets(scene))):
            return {"CANCELLED"}
        sets(scene).move(i, j)
        scene.b4d_rs_loaded = j
        _set_index(scene, j)
        return {"FINISHED"}


class BLENDA4D_OT_rs_rename(bpy.types.Operator):
    bl_idname = "blenda4d.rs_rename"
    bl_label = "Rename Render Setting"
    bl_description = "Give the active render setting a new name"
    bl_options = {"REGISTER", "UNDO"}
    name: bpy.props.StringProperty(name="Name")

    @classmethod
    def poll(cls, context):
        return len(sets(context.scene)) > 0

    def invoke(self, context, event):
        self.name = sets(context.scene)[context.scene.b4d_rs_loaded].name
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        sets(context.scene)[context.scene.b4d_rs_loaded].name = self.name or DEFAULT_NAME
        return {"FINISHED"}


class BLENDA4D_MT_render_setting(bpy.types.Menu):
    bl_idname = "BLENDA4D_MT_render_setting"
    bl_label = "Render Setting"

    def draw(self, context):
        lay = self.layout
        lay.operator("blenda4d.rs_add", icon="ADD")
        lay.operator("blenda4d.rs_duplicate", icon="DUPLICATE")
        lay.operator("blenda4d.rs_remove", icon="REMOVE")
        lay.separator()
        lay.operator("blenda4d.rs_rename", text="Rename...", icon="GREASEPENCIL")
        lay.operator("blenda4d.rs_move", text="Move Up", icon="TRIA_UP").step = -1
        lay.operator("blenda4d.rs_move", text="Move Down", icon="TRIA_DOWN").step = 1


# --- rendering with the setting's frame range, frame rate and Save ----------------------------------------------
_stash = {}


@bpy.app.handlers.persistent
def _restore(*_args):
    """Put back the frame range and rate prepare() changed for a render."""
    scene = _stash.pop("scene", None)
    values = _stash.pop("values", {})
    _stash.clear()
    if scene is None:
        return
    try:
        scene.frame_start, scene.frame_end = values["frame_start"], values["frame_end"]
        if scene.frame_start != values["frame_start"]:       # Blender keeps start <= end: set again in the other order
            scene.frame_start = values["frame_start"]
        scene.frame_step = values["frame_step"]
        scene.render.fps, scene.render.fps_base = values["fps"], values["fps_base"]
    except (ReferenceError, KeyError):
        pass


def prepare(scene, animation):
    """Set the scene's frame range and rate for a render; _restore() puts them back."""
    _restore()
    p = scene.b4d_render
    keep = {"frame_start": scene.frame_start, "frame_end": scene.frame_end, "frame_step": scene.frame_step,
            "fps": scene.render.fps, "fps_base": scene.render.fps_base}
    _stash.update(scene=scene, values=keep)
    if animation:
        first, last, step = frame_span(scene)
        if first > scene.frame_end:          # Blender keeps start <= end: move the end first
            scene.frame_end = last
            scene.frame_start = first
        else:
            scene.frame_start = first
            scene.frame_end = last
        scene.frame_step = step
    if not p.use_scene_fps:
        scene.render.fps, scene.render.fps_base = p.fps, 1.0


class BLENDA4D_OT_render(bpy.types.Operator):
    bl_idname = "blenda4d.render"
    bl_label = "Render"
    bl_description = "Render with the active render setting: its frame range, frame rate and Save switch"
    animation: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        scene = context.scene
        prepare(scene, self.animation)
        save = scene.b4d_render.save and not self.animation
        try:
            res = bpy.ops.render.render("EXEC_DEFAULT" if bpy.app.background else "INVOKE_DEFAULT",
                                        animation=self.animation, write_still=save)
        except RuntimeError as ex:
            _restore()
            self.report({"ERROR"}, str(ex))
            return {"CANCELLED"}
        if bpy.app.background or "RUNNING_MODAL" not in res:   # finished (or never started): put the scene back now
            _restore()
        return {"FINISHED"}


# --- the window ------------------------------------------------------------------------------------------------
def _window_with_role(context):
    for w in context.window_manager.windows:
        if any(roles.role(a) == ROLE for a in w.screen.areas):
            return w
    return None


class BLENDA4D_OT_render_settings(bpy.types.Operator):
    bl_idname = "blenda4d.render_settings"
    bl_label = "Render Settings"
    bl_description = "Open the Render Settings window: saved render settings and their values"

    def execute(self, context):
        ensure(context.scene)
        wm = context.window_manager
        ensure_pages(wm)
        old = _window_with_role(context)
        if old is not None:                      # Blender cannot bring a window to the front: open it again
            with context.temp_override(window=old):
                bpy.ops.wm.window_close()
        before = {w.as_pointer() for w in wm.windows}
        bpy.ops.screen.drivers_editor_show("INVOKE_DEFAULT")       # Blender's way to open a small floating window
        win = next((w for w in wm.windows if w.as_pointer() not in before), None)
        if win is None:
            return {"CANCELLED"}
        area = win.screen.areas[0]
        area.type = "PROPERTIES"
        roles.set_role(area, ROLE)

        def finish():
            try:
                roles.hide_nav(area, win)
                area.tag_redraw()
            except (ReferenceError, RuntimeError):
                pass
            return None
        bpy.app.timers.register(finish, first_interval=0.05)
        return {"FINISHED"}


def _close_windows():
    wm = bpy.context.window_manager
    if wm is None:
        return
    for w in list(wm.windows):
        if any(roles.role(a) == ROLE for a in w.screen.areas):
            try:
                with bpy.context.temp_override(window=w):
                    bpy.ops.wm.window_close()
            except (RuntimeError, ReferenceError):
                pass


# --- pages -------------------------------------------------------------------------------------------------------
LABEL_F = 0.4          # the label column, as Blender's own property-split rows


def _label_col(col, label, active=True):
    split = col.split(factor=LABEL_F)
    split.active = active
    lab = split.row()
    lab.alignment = "RIGHT"
    lab.label(text=label)
    return split


def _info(col, label, text):
    """A read-only line: label in the label column, text where the fields are."""
    _label_col(col, label).label(text=text)


def _field(col, label, owner, attr, menu=None, wide=False, active=True):
    """Label on the left, a short value field, and an optional dropdown beside it (Width + unit)."""
    right = _label_col(col, label, active)
    if wide:
        right.prop(owner, attr, text="")
        return
    pair = right.split(factor=0.4)
    pair.prop(owner, attr, text="")
    if menu:
        pair.prop(menu[0], menu[1], text="")


def _rows(col, owner, attrs):
    for attr, text in attrs:
        if owner is not None and hasattr(owner, attr):
            col.prop(owner, attr, text=text)


def draw_output(col, scene):
    rd, p = scene.render, scene.b4d_render
    _field(col, "Preset", p, "v_preset", wide=True)
    px = p.size_unit == "PX"
    _field(col, "Width", p, "v_width" if px else "v_phys_w", menu=(p, "size_unit"))
    _field(col, "Height", p, "v_height" if px else "v_phys_h")
    _field(col, "Lock Ratio", p, "lock_ratio")
    _field(col, "Resolution", p, "v_dpi", menu=(p, "dpi_unit"))
    w = rd.resolution_x * rd.resolution_percentage // 100
    h = rd.resolution_y * rd.resolution_percentage // 100
    _info(col, "Image Resolution:", f"{w} x {h} Pixel")
    _field(col, "Render Scale", rd, "resolution_percentage")
    split = col.split(factor=LABEL_F)
    lab = split.row()
    lab.alignment = "RIGHT"
    lab.prop(p, "show_region", text="", icon="DOWNARROW_HLT" if p.show_region else "RIGHTARROW", emboss=False)
    lab.label(text="Render Region")
    split.prop(rd, "use_border", text="")
    if p.show_region:
        _field(col, "Crop to Region", rd, "use_crop_to_border", active=rd.use_border)
        for attr, label in (("v_left", "Left Border"), ("v_top", "Top Border"), ("v_right", "Right Border"),
                            ("v_bottom", "Bottom Border")):
            _field(col, label, p, attr, active=rd.use_border)
    col.separator(type="LINE")
    _field(col, "Film Aspect", p, "v_film", menu=(p, "v_film_p"))
    _field(col, "Pixel Aspect", p, "v_pix", menu=(p, "v_pix_p"))
    _field(col, "Use Scene Frame Rate", p, "use_scene_fps")
    _field(col, "Frame Rate", rd if p.use_scene_fps else p, "fps", active=not p.use_scene_fps)
    col.separator(type="LINE")
    _field(col, "Frame Range", p, "frame_range", wide=True)
    manual = p.frame_range == "MANUAL"
    _field(col, "From", p, "v_from", active=manual)
    _field(col, "To", p, "v_to", active=manual)
    _field(col, "Frame Step", p, "v_step", active=manual)
    first, last, step = frame_span(scene)
    n = max(0, (last - first) // max(1, step) + 1)
    _info(col, "Frames:", f"{n} frames (from {first} to {last})")
    col.separator(type="LINE")
    _field(col, "Annotations", p, "annotations", wide=True)


def draw_save(col, scene):
    rd = scene.render
    img = rd.image_settings
    col.prop(scene.b4d_render, "save", text="Save Still Renders")
    col.prop(rd, "filepath", text="File")
    col.prop(img, "file_format", text="Format")
    col.row().prop(img, "color_mode", text="Color", expand=True)
    if len(img.bl_rna.properties["color_depth"].enum_items) > 1:
        col.row().prop(img, "color_depth", text="Depth", expand=True)
    if img.file_format in {"JPEG", "WEBP", "AVIF", "JPEG2000"}:
        col.prop(img, "quality", text="Quality")
    elif img.file_format == "PNG":
        col.prop(img, "compression", text="Compression")
    col.prop(rd, "film_transparent", text="Transparent Background")
    col.prop(rd, "use_file_extension", text="File Extensions")
    col.prop(rd, "use_overwrite", text="Overwrite Existing Files")
    col.prop(rd, "use_placeholder", text="Placeholders")


def draw_multipass(col, scene):
    p = scene.b4d_render
    col.prop(p, "multipass")
    sub = col.column(heading="Passes")
    sub.active = p.multipass
    for prop, _attr, label in PASSES:
        sub.prop(p, prop, text=label)
    _info(col, "Always:", "Combined (the finished image)")


def draw_samples(col, scene):
    e = scene.render.engine
    cy = getattr(scene, "cycles", None)
    if e == "CYCLES" and cy is not None:
        sub = col.column(align=True)
        sub.prop(cy, "samples", text="Render Samples")
        sub.prop(cy, "preview_samples", text="Viewport Samples")
        col.prop(cy, "use_adaptive_sampling", text="Adaptive Sampling")
        sub = col.column(align=True)
        sub.active = cy.use_adaptive_sampling
        sub.prop(cy, "adaptive_threshold", text="Noise Threshold")
        sub.prop(cy, "adaptive_min_samples", text="Min Samples")
        col.prop(cy, "time_limit", text="Time Limit")
        col.prop(cy, "use_denoising", text="Denoise Render")
        sub = col.column()
        sub.active = cy.use_denoising
        sub.prop(cy, "denoiser", text="Denoiser")
        col.prop(cy, "use_preview_denoising", text="Denoise Viewport")
        col.prop(cy, "pixel_filter_type", text="Pixel Filter")
        col.prop(cy, "filter_width", text="Filter Width")
    elif e == "BLENDER_WORKBENCH":
        col.prop(scene.display, "render_aa", text="Render")
        col.prop(scene.display, "viewport_aa", text="Viewport")
    else:
        sub = col.column(align=True)
        sub.prop(scene.eevee, "taa_render_samples", text="Render Samples")
        sub.prop(scene.eevee, "taa_samples", text="Viewport Samples")
        col.prop(scene.render, "filter_size", text="Filter Size")


def draw_options(col, scene):
    rd = scene.render
    col.prop(rd, "use_simplify", text="Simplify")
    sub = col.column(align=True)
    sub.active = rd.use_simplify
    sub.prop(rd, "simplify_subdivision_render", text="Max Subdivision")
    sub.prop(rd, "simplify_child_particles_render", text="Child Particles")
    col.separator(type="LINE")
    col.prop(rd, "threads_mode", text="Threads")
    sub = col.column()
    sub.active = rd.threads_mode == "FIXED"
    sub.prop(rd, "threads", text="Thread Count")
    col.prop(rd, "use_persistent_data", text="Keep Data Between Frames")
    col.prop(rd, "dither_intensity", text="Dither")
    col.prop(rd, "use_compositing", text="Compositing")


def draw_override(col, scene):
    p = scene.b4d_render
    col.prop(p, "material_override")
    sub = col.column()
    sub.active = p.material_override
    sub.prop(p, "override_material", text="Material")


def draw_motion_blur(col, scene):
    rd = scene.render
    col.prop(rd, "use_motion_blur", text="Motion Blur")
    col = col.column()
    col.active = rd.use_motion_blur
    col.prop(rd, "motion_blur_position", text="Position")
    col.prop(rd, "motion_blur_shutter", text="Shutter")
    cy = getattr(scene, "cycles", None)
    if rd.engine == "CYCLES" and cy is not None:
        col.prop(cy, "rolling_shutter_type", text="Rolling Shutter")
        sub = col.column()
        sub.active = rd.use_motion_blur and cy.rolling_shutter_type != "NONE"
        sub.prop(cy, "rolling_shutter_duration", text="Rolling Duration")
    elif rd.engine == "BLENDER_EEVEE":
        col.prop(scene.eevee, "motion_blur_steps", text="Steps")
        col.prop(scene.eevee, "motion_blur_max", text="Max Blur")
        col.prop(scene.eevee, "motion_blur_depth_scale", text="Depth Scale")


def draw_color(col, scene):
    col.prop(scene.display_settings, "display_device", text="Display")
    col.prop(scene.view_settings, "view_transform", text="View")
    col.prop(scene.view_settings, "look", text="Look")
    col.prop(scene.view_settings, "exposure", text="Exposure")
    col.prop(scene.view_settings, "gamma", text="Gamma")


def draw_light_paths(col, scene):
    cy = scene.cycles
    sub = col.column(align=True)
    _rows(sub, cy, (("max_bounces", "Total Bounces"), ("diffuse_bounces", "Diffuse"), ("glossy_bounces", "Glossy"),
                    ("transmission_bounces", "Transmission"), ("volume_bounces", "Volume"),
                    ("transparent_max_bounces", "Transparent")))
    sub = col.column(align=True)
    _rows(sub, cy, (("sample_clamp_direct", "Clamp Direct"), ("sample_clamp_indirect", "Clamp Indirect")))
    col.prop(cy, "blur_glossy", text="Filter Glossy")
    col.prop(cy, "caustics_reflective", text="Reflective Caustics")
    col.prop(cy, "caustics_refractive", text="Refractive Caustics")


def draw_volumes(col, scene):
    ee = scene.eevee
    col.prop(ee, "volumetric_tile_size", text="Resolution")
    col.prop(ee, "volumetric_samples", text="Steps")
    col.prop(ee, "volumetric_sample_distribution", text="Distribution")
    sub = col.column(align=True)
    sub.prop(ee, "volumetric_start", text="Start")
    sub.prop(ee, "volumetric_end", text="End")
    col.prop(ee, "use_volumetric_shadows", text="Volume Shadows")
    sub = col.column()
    sub.active = ee.use_volumetric_shadows
    sub.prop(ee, "volumetric_shadow_samples", text="Shadow Steps")


PAGE_DRAW = {"OUTPUT": draw_output, "SAVE": draw_save, "MULTIPASS": draw_multipass, "AA": draw_samples,
             "OPTIONS": draw_options, "OVERRIDE": draw_override, "MOTION_BLUR": draw_motion_blur, "COLOR": draw_color,
             "LIGHT_PATHS": draw_light_paths, "VOLUMES": draw_volumes}


def draw_page(layout, context):
    scene, wm = context.scene, context.window_manager
    split = layout.split(factor=0.3)
    left = split.column()
    top = left.row()
    top.use_property_split = True
    top.use_property_decorate = False
    top.prop(scene.render, "engine", text="Renderer")
    if len(wm.b4d_rs_pages):
        left.template_list(BLENDA4D_UL_render_pages.bl_idname, "", wm, "b4d_rs_pages", wm, "b4d_rs_page",
                           rows=len([p for p in PAGES if page_shown(scene, p[0])]))
    left.separator(factor=2.0)
    if len(sets(scene)):
        left.template_list(BLENDA4D_UL_render_sets.bl_idname, "", scene, "b4d_rsets", scene, "b4d_rs_index", rows=4)
    else:
        left.operator("blenda4d.rs_add", text="New Render Setting", icon="ADD")
    left.menu(BLENDA4D_MT_render_setting.bl_idname, text="Render Setting...")
    right = split.column()
    key = current_page(context)
    right.label(text=next(p[1] for p in PAGES if p[0] == key))
    col = right.column()
    col.use_property_split = True
    col.use_property_decorate = False
    PAGE_DRAW[key](col, scene)


class BLENDA4D_PT_render_settings(roles.RolePanel, bpy.types.Panel):
    bl_label = "Render Settings"
    role = ROLE

    def draw(self, context):
        draw_page(self.layout, context)


# --- saving: the active setting keeps what the scene shows -----------------------------------------------------
@bpy.app.handlers.persistent
def _commit_on_save(*_args):
    for scene in bpy.data.scenes:
        try:
            if len(sets(scene)):
                commit(scene)
        except Exception as ex:                  # never stop a save
            print("Blenda 4D: render setting not stored:", ex)


CLASSES = (BLENDA4D_RenderProps, BLENDA4D_RenderSet, BLENDA4D_RenderPage, BLENDA4D_UL_render_sets,
           BLENDA4D_UL_render_pages, BLENDA4D_OT_rs_add, BLENDA4D_OT_rs_duplicate, BLENDA4D_OT_rs_remove,
           BLENDA4D_OT_rs_move, BLENDA4D_OT_rs_rename, BLENDA4D_MT_render_setting, BLENDA4D_OT_render,
           BLENDA4D_OT_render_settings, BLENDA4D_PT_render_settings)
HANDLERS = (("save_pre", _commit_on_save), ("render_complete", _restore), ("render_cancel", _restore))


def _fill_pages():
    try:
        ensure_pages(bpy.context.window_manager)
    except AttributeError:
        return 0.2
    return None


def register():
    roles.ROLE_FLAGS[ROLE] = "show_properties_render"
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    S = bpy.types.Scene
    S.b4d_render = bpy.props.PointerProperty(type=BLENDA4D_RenderProps)
    S.b4d_rsets = bpy.props.CollectionProperty(type=BLENDA4D_RenderSet)
    S.b4d_rs_index = bpy.props.IntProperty(name="Render Setting", default=0, update=_picked)
    S.b4d_rs_loaded = bpy.props.IntProperty(default=0)
    WM = bpy.types.WindowManager
    WM.b4d_rs_pages = bpy.props.CollectionProperty(type=BLENDA4D_RenderPage)
    WM.b4d_rs_page = bpy.props.IntProperty(name="Section", default=0)
    for name, fn in HANDLERS:
        if fn not in getattr(bpy.app.handlers, name):
            getattr(bpy.app.handlers, name).append(fn)
    bpy.app.timers.register(_fill_pages, first_interval=0.0)


def unregister():
    try:
        _close_windows()
    except Exception as ex:
        print("Blenda 4D: render settings window not closed:", ex)
    _restore()
    for name, fn in HANDLERS:
        if fn in getattr(bpy.app.handlers, name):
            getattr(bpy.app.handlers, name).remove(fn)
    if bpy.app.timers.is_registered(_fill_pages):
        bpy.app.timers.unregister(_fill_pages)
    for T, names in ((bpy.types.WindowManager, ("b4d_rs_page", "b4d_rs_pages")),
                     (bpy.types.Scene, ("b4d_rs_loaded", "b4d_rs_index", "b4d_rsets", "b4d_render"))):
        for name in names:
            if hasattr(T, name):
                delattr(T, name)
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    roles.ROLE_FLAGS.pop(ROLE, None)
