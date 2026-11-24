# SPDX-License-Identifier: GPL-3.0-or-later
"""Lights: the create column's lights group and the Create menu entries (Light, Spot Light, Target Light, Area Light,
PBR Light, IES Light, Infinite Light, Sun Light), and the Attribute Manager pages of every light: General, Details,
Shadow, and Profile for an IES Light. Lights made in plain Blender get the same pages.

Every light is a Blender light object. Its kind (ob["b4d_type"]) follows the light's type: when the Type row changes,
the kind changes with it."""
import os

import bpy

from . import kinds

# kind -> (Blender light type, name, icon, tooltip)
KINDS = {
    "light": ("POINT", "Light", "LIGHT_POINT", "A light that shines in all directions from one point"),
    "spot_light": ("SPOT", "Spot Light", "LIGHT_SPOT", "A light that shines in a cone"),
    "target_light": ("SPOT", "Target Light", "LIGHT_SPOT", "A spot light that always aims at a target null; move the null to aim it"),
    "area_light": ("AREA", "Area Light", "LIGHT_AREA", "A light from a flat shape: the bigger it is, the softer the shadows"),
    "pbr_light": ("AREA", "PBR Light", "LIGHT_AREA",
                  "A large area light with soft shadows and real-world falloff, a good start for product shots"),
    "ies_light": ("POINT", "IES Light", "LIGHT_POINT", "A light shaped by a measured light profile (.ies file)"),
    "infinite_light": ("SUN", "Infinite Light", "LIGHT_SUN", "Parallel light from far away, the same strength everywhere"),
    "sun_light": ("SUN", "Sun Light", "LIGHT_SUN", "Warm, slightly soft daylight coming in at an angle"),
}
ORDER = ("light", "spot_light", "target_light", "area_light", "pbr_light", "ies_light", "infinite_light", "sun_light")
BASE = {"POINT": "light", "SPOT": "spot_light", "AREA": "area_light", "SUN": "infinite_light"}
ENERGY = {"POINT": 1000.0, "SPOT": 1000.0, "AREA": 500.0, "SUN": 3.0}
HEIGHT = 3.0                                   # new lights sit this far above the origin
LABEL = "Light Object"
TABS = [("OBJECT", "General"), ("DETAILS", "Details"), ("SHADOW", "Shadow")]
TITLES = {"OBJECT": "General", "DETAILS": "Details", "SHADOW": "Shadow", "PROFILE": "Profile"}
FALLOFF_NODE, MULTIPLY_NODE = "B4D Falloff", "B4D Profile Strength"


# --- making lights -----------------------------------------------------------------------------------------------
def new_light(context, kind):
    typ, name = KINDS[kind][0], KINDS[kind][1]
    li = bpy.data.lights.new(name, typ)
    li.energy = ENERGY[typ]
    if typ in {"POINT", "SPOT"}:
        li.shadow_soft_size = 0.1              # a small round source: slightly soft shadows
    oc = getattr(li, "octane", None)           # Octane turns a new light into its own; left alone, a point light
    if oc is not None:                         # becomes a toon light and a sun a toon directional light
        for attr, value in (("octane_point_light_type", "Sphere"), ("octane_directional_light_type", "Directional")):
            try:
                setattr(oc, attr, value)
            except (AttributeError, TypeError):
                pass
    ob = bpy.data.objects.new(name, li)
    context.collection.objects.link(ob)
    ob.location = (0.0, 0.0, HEIGHT)
    ob["b4d_type"] = kind
    if context.scene.render.engine == "octane":    # Octane converts only lights made by Blender's Add operator
        try:
            from . import sceneconvert
            sceneconvert.light_to_octane(ob)
        except Exception as e:
            print("Blenda 4D: Octane light", e)
    return ob


def _make(kind):
    def create(context):
        ob = new_light(context, kind)
        li = ob.data
        if kind == "area_light":
            li.size = 1.0
        elif kind == "pbr_light":
            li.shape = "RECTANGLE"
            li.size, li.size_y = 2.0, 2.0
            li.energy = 800.0
            li.spread = 3.14159265
            li.use_shadow_jitter = True        # soft shadows in the viewport as well
            li.b4d_falloff = "QUADRATIC"
        elif kind == "target_light":
            add_target(context, ob)
        elif kind == "infinite_light":
            li.angle = 0.0
        elif kind == "sun_light":
            li.energy = 4.0
            li.use_temperature = True
            li.temperature = 5500.0
            li.angle = 0.0093                  # about the size the sun looks from the ground
            ob.rotation_euler = (0.70, 0.0, 0.52)
        em = octane_emission(ob)                # Octane's copy of the brightness, made before it was set above
        if em is not None:
            em.inputs["Power"].default_value = li.energy
        return ob
    return create


def add_target(context, ob):
    """A null at the origin that the light keeps aiming at (a Track To constraint)."""
    t = bpy.data.objects.new(ob.name + ".Target", None)
    t.empty_display_type = "PLAIN_AXES"
    t.empty_display_size = 0.3
    context.collection.objects.link(t)
    c = ob.constraints.new("TRACK_TO")
    c.name = "Target"
    c.target = t
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    return t


def _create_ies(context):
    bpy.ops.blenda4d.light_ies_add("INVOKE_DEFAULT")
    return None


# --- light node tree: falloff and profile (used by Cycles renders) ------------------------------------------------
def _emission(li):
    nt = li.node_tree
    if nt is None:
        return None
    return next((n for n in nt.nodes if n.type == "EMISSION"), None)


def ies_node(li):
    nt = li.node_tree if li is not None else None
    return next((n for n in nt.nodes if n.type == "TEX_IES"), None) if nt else None


def rewire(li):
    """Connect the profile and the falloff to the emission strength, or leave it plain when neither is used."""
    em = _emission(li)
    if em is None:
        return
    nt = li.node_tree
    strength = em.inputs["Strength"]
    for link in list(strength.links):
        nt.links.remove(link)
    falloff = nt.nodes.get(FALLOFF_NODE)
    mult = nt.nodes.get(MULTIPLY_NODE)
    src = []
    if li.b4d_falloff != "QUADRATIC":
        if falloff is None:
            falloff = nt.nodes.new("ShaderNodeLightFalloff")
            falloff.name = falloff.label = FALLOFF_NODE
            falloff.location = (em.location.x - 220, em.location.y - 160)
        falloff.inputs["Strength"].default_value = 1.0
        src.append(falloff.outputs["Linear" if li.b4d_falloff == "LINEAR" else "Constant"])
    elif falloff is not None:
        nt.nodes.remove(falloff)
    ies = ies_node(li)
    if ies is not None:
        src.append(ies.outputs[0])
    if len(src) == 2:
        if mult is None:
            mult = nt.nodes.new("ShaderNodeMath")
            mult.name = mult.label = MULTIPLY_NODE
            mult.operation = "MULTIPLY"
            mult.location = (em.location.x - 180, em.location.y + 40)
        nt.links.new(src[0], mult.inputs[0])
        nt.links.new(src[1], mult.inputs[1])
        nt.links.new(mult.outputs[0], strength)
    else:
        if mult is not None:
            nt.nodes.remove(mult)
        if src:
            nt.links.new(src[0], strength)
        else:
            strength.default_value = 1.0


def set_profile(ob, path):
    """Shape the light with the profile in an .ies file. The file is copied into the scene, so the light keeps
    working if the file moves."""
    li = ob.data
    if li.node_tree is None:
        li.use_nodes = True
    nt = li.node_tree
    node = ies_node(li)
    if node is None:
        node = nt.nodes.new("ShaderNodeTexIES")
        em = _emission(li)
        if em is not None:
            node.location = (em.location.x - 420, em.location.y)
    node.mode = "INTERNAL"
    old = node.ies
    node.ies = bpy.data.texts.load(path)
    if old is not None and old.users == 0:
        bpy.data.texts.remove(old)
    li["b4d_ies_file"] = path
    rewire(li)
    return node


def _falloff_update(self, context):
    rewire(self)


# --- operators ---------------------------------------------------------------------------------------------------
class _ProfilePicker:
    filepath: bpy.props.StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})
    filter_glob: bpy.props.StringProperty(default="*.ies", options={"HIDDEN"})

    def invoke(self, context, event):
        from . import lights_ies
        self.filepath = lights_ies.ensure_files() + os.sep      # starts among the starter profiles
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def _path_ok(self):
        return bool(self.filepath) and os.path.isfile(bpy.path.abspath(self.filepath))


class BLENDA4D_OT_light_ies_add(_ProfilePicker, bpy.types.Operator):
    """Create a light shaped by a light profile: pick an .ies file"""
    bl_idname = "blenda4d.light_ies_add"
    bl_label = "Create IES Light"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if not self._path_ok():
            self.report({"WARNING"}, "Pick an .ies file")
            return {"CANCELLED"}
        ob = new_light(context, "ies_light")
        ob.data.shadow_soft_size = 0.05
        try:
            set_profile(ob, bpy.path.abspath(self.filepath))
        except (RuntimeError, OSError) as ex:
            self.report({"WARNING"}, f"Could not read the profile: {ex}")
        ob.name = os.path.splitext(os.path.basename(self.filepath))[0].replace("_", " ")
        for o in context.view_layer.objects.selected:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        return {"FINISHED"}


class BLENDA4D_OT_light_ies_load(_ProfilePicker, bpy.types.Operator):
    """Pick an .ies file to shape the selected light"""
    bl_idname = "blenda4d.light_ies_load"
    bl_label = "Load Profile"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        ob = context.view_layer.objects.active
        return ob is not None and ob.type == "LIGHT"

    def execute(self, context):
        if not self._path_ok():
            return {"CANCELLED"}
        try:
            set_profile(context.view_layer.objects.active, bpy.path.abspath(self.filepath))
        except (RuntimeError, OSError) as ex:
            self.report({"WARNING"}, f"Could not read the profile: {ex}")
            return {"CANCELLED"}
        return {"FINISHED"}


class BLENDA4D_OT_light_ies_clear(bpy.types.Operator):
    """Take the profile off: the light shines evenly again"""
    bl_idname = "blenda4d.light_ies_clear"
    bl_label = "Remove Profile"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        ob = context.view_layer.objects.active
        return ob is not None and ob.type == "LIGHT" and ies_node(ob.data) is not None

    def execute(self, context):
        li = context.view_layer.objects.active.data
        node = ies_node(li)
        li.node_tree.nodes.remove(node)
        rewire(li)
        return {"FINISHED"}


# --- Attribute Manager pages ---------------------------------------------------------------------------------------
# Each page is a list of rows, so the drawing and the tests read the same list:
#   ("prop", owner, attr, label, active)   ("label", text)   ("op", idname, text, icon)   ("sep",)
def _soft_row(ob, label="Radius"):
    d = ob.data
    if d.type == "SUN":
        return ("prop", d, "angle", "Angle", True)
    if d.type == "AREA":
        return None
    return ("prop", d, "shadow_soft_size", label, True)


def _track(ob):
    return next((c for c in ob.constraints if c.type == "TRACK_TO"), None)


def octane_emission(ob):
    """The light's Octane emission node while Octane renders, or None. Octane ignores the light's own Intensity and
    Color: its brightness is the emission node's Power (Octane tab > Emission), so the General page shows that."""
    try:
        if bpy.context.scene.render.engine != "octane" or not ob.data.use_nodes or ob.data.node_tree is None:
            return None
    except AttributeError:
        return None
    return next((n for n in ob.data.node_tree.nodes if n.bl_idname.endswith("Emission") and "Power" in n.inputs), None)


def _emission_color(em):
    tex = em.inputs.get("Texture")
    if tex is None or tex.is_linked or not hasattr(tex, "default_value"):
        return None
    try:
        return tex if len(tex.default_value) in (3, 4) else None
    except TypeError:
        return None


def rows_general(ob):
    d = ob.data
    em = octane_emission(ob)
    if em is not None:
        col = _emission_color(em)
        return [("prop", col, "default_value", "Color", True) if col is not None else ("prop", d, "color", "Color", True),
                ("prop", em.inputs["Power"], "default_value", "Intensity", True),
                ("prop", em.inputs["Surface brightness"], "default_value", "Same Brightness at Any Size", True)
                if "Surface brightness" in em.inputs else ("sep",),
                ("prop", d, "type", "Type", True),
                ("prop", ob, "visible_camera", "Visible in Render", True)]
    return [("prop", d, "color", "Color", True),
            ("prop", d, "use_temperature", "Use Temperature", True),
            ("prop", d, "temperature", "Temperature", d.use_temperature),
            ("prop", d, "energy", "Intensity", True),
            ("prop", d, "exposure", "Exposure", True),
            ("prop", d, "type", "Type", True),
            ("prop", d, "use_shadow", "Shadow", True),
            ("prop", ob, "visible_camera", "Visible in Render", True)]


def rows_details(ob):
    d = ob.data
    out = []
    t = _track(ob)
    if t is not None:
        out += [("prop", t, "target", "Target", True), ("sep",)]
    if d.type == "SPOT":
        out += [("prop", d, "spot_size", "Cone Angle", True),
                ("prop", d, "spot_blend", "Edge Softness", True),
                ("prop", d, "use_square", "Square Cone", True),
                ("prop", d, "show_cone", "Show Cone", True)]
    if d.type == "AREA":
        long = d.shape in {"RECTANGLE", "ELLIPSE"}
        out += [("prop", d, "shape", "Area Shape", True),
                ("prop", d, "size", "Size X" if long else "Size", True),
                ("prop", d, "size_y", "Size Y", long),
                ("prop", d, "spread", "Spread", True),
                ("prop", d, "normalize", "Same Power at Any Size", True)]
    if d.type in {"POINT", "SPOT"}:
        out += [("prop", d, "shadow_soft_size", "Radius", True),
                ("prop", d, "use_soft_falloff", "Soft Falloff", True)]
    if d.type == "SUN":
        out += [("prop", d, "angle", "Angle", True)]
    out.append(("sep",))
    if d.type != "SUN":
        out += [("prop", d, "b4d_falloff", "Falloff", True),
                ("prop", d, "use_custom_distance", "Limit Distance", True),
                ("prop", d, "cutoff_distance", "Distance", d.use_custom_distance),
                ("sep",)]
    out += [("prop", d, "diffuse_factor", "Diffuse", True),
            ("prop", d, "specular_factor", "Specular", True),
            ("prop", d, "transmission_factor", "Transmission", True),
            ("prop", d, "volume_factor", "Volume", True)]
    return out


def rows_shadow(ob):
    d = ob.data
    on = d.use_shadow
    out = [("prop", d, "use_shadow", "Cast Shadows", True)]
    soft = _soft_row(ob)
    if soft is not None:
        out.append(("prop", soft[1], soft[2], "Softness " + ("(Angle)" if d.type == "SUN" else "(Radius)"), on))
    else:
        out.append(("label", "The area's size sets how soft its shadows are"))
    out += [("prop", d, "use_shadow_jitter", "Soft Shadows in Viewport", on),
            ("prop", d, "shadow_jitter_overblur", "Overblur", on and d.use_shadow_jitter),
            ("prop", d, "shadow_filter_radius", "Filter", on),
            ("prop", d, "shadow_maximum_resolution", "Resolution Limit", on)]
    if d.type != "SUN":
        out.append(("prop", d, "use_absolute_resolution", "Absolute Resolution", on))
    return out


def rows_profile(ob):
    d = ob.data
    node = ies_node(d)
    if d.type not in {"POINT", "SPOT"}:
        return [("label", "A profile shapes point and spot lights only")]
    if node is None:
        return [("label", "No profile on this light"), ("op", "blenda4d.light_ies_load", "Load Profile...", "FILEBROWSER")]
    return [("prop", node, "ies", "Profile", True),
            ("op", "blenda4d.light_ies_load", "Load Profile...", "FILEBROWSER"),
            ("op", "blenda4d.light_ies_clear", "Remove Profile", "X"),
            ("label", "The profile shapes the light in Cycles renders")]


def draw_rows(col, rows):
    for r in rows:
        if r[0] == "sep":
            col.separator()
        elif r[0] == "label":
            col.label(text=r[1])
        elif r[0] == "op":
            col.operator(r[1], text=r[2], icon=r[3])
        else:
            _, owner, attr, label, active = r
            row = col.row()
            row.active = bool(active)
            if owner.bl_rna.properties[attr].type == "BOOLEAN":
                row.prop(owner, attr, text=label, toggle=0, icon="NONE")   # a checkbox, never an icon button
            else:
                row.prop(owner, attr, text=label)


def _page(rows_fn):
    def page(col, ob):
        if ob.type != "LIGHT" or ob.data is None:
            col.label(text="This object is not a light")
            return
        draw_rows(col, rows_fn(ob))
    return page


PAGES = {"OBJECT": _page(rows_general), "DETAILS": _page(rows_details), "SHADOW": _page(rows_shadow),
         "PROFILE": _page(rows_profile)}


def rows(ob, tab):
    return {"OBJECT": rows_general, "DETAILS": rows_details, "SHADOW": rows_shadow, "PROFILE": rows_profile}[tab](ob)


# --- plain Blender lights and type changes --------------------------------------------------------------------------
def resolve(ob):
    """The kind of a light that was not made here (or whose kind was lost)."""
    if ob.type != "LIGHT" or ob.data is None:
        return None
    return "ies_light" if ies_node(ob.data) is not None else BASE.get(ob.data.type)


def sync_kinds(*_args):
    """After a light's Type changes, its kind follows (an Area Light switched to Spot becomes a Spot Light)."""
    for ob in bpy.data.objects:
        if ob.type != "LIGHT" or ob.data is None or ob.library is not None:
            continue
        k = ob.get("b4d_type")
        if k in KINDS and KINDS[k][0] != ob.data.type:
            ob["b4d_type"] = BASE.get(ob.data.type, "light")


_OWNER = object()


def _subscribe(*_args):
    bpy.msgbus.clear_by_owner(_OWNER)
    bpy.msgbus.subscribe_rna(key=(bpy.types.Light, "type"), owner=_OWNER, args=(), notify=sync_kinds)


_subscribe = bpy.app.handlers.persistent(_subscribe)


# --- register ------------------------------------------------------------------------------------------------------
classes = (BLENDA4D_OT_light_ies_add, BLENDA4D_OT_light_ies_load, BLENDA4D_OT_light_ies_clear)
_saved = {}


def _group_entry(kind):
    return (KINDS[kind][1], KINDS[kind][2], "blenda4d.add_kind", {"kind": kind})


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Light.b4d_falloff = bpy.props.EnumProperty(
        name="Falloff", update=_falloff_update, default="QUADRATIC",
        description="How the light weakens with distance (Linear and None show in Cycles renders)",
        items=[("QUADRATIC", "Inverse Square", "Real-world falloff: at twice the distance a quarter of the light"),
               ("LINEAR", "Linear", "Weakens more slowly than in the real world"),
               ("CONSTANT", "None", "The same strength at any distance")])
    for kind in ORDER:
        typ, name, icon, tip = KINDS[kind]
        tabs = TABS + ([("PROFILE", "Profile")] if kind == "ies_light" else [])
        kinds.add(kind, LABEL, icon, create=_create_ies if kind == "ies_light" else _make(kind), tabs=tabs,
                  pages=PAGES, titles=TITLES, describe=tip)
        kinds.menu_item("Create", name, kind, icon)
    if hasattr(kinds, "resolver"):
        kinds.resolver(resolve)
    # the create column's lights group: ours, in this order (the group it had comes back on unregister)
    from . import bars
    group = bars.GROUPS.get("lights")
    if group is not None:
        _saved.setdefault("group", list(group))
        group[:] = [_group_entry(k) for k in ORDER]
    # the Create menu's plain Blender "Light" entry is replaced by the entries above
    from . import menus
    items = menus.MAIN.get("Create", [])
    for i, it in enumerate(items):
        if isinstance(it, tuple) and len(it) == 4 and it[1] == "object.light_add":
            _saved["menu"] = (i, it)
            del items[i]
            break
    _subscribe()
    if _subscribe not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_subscribe)


def unregister():
    if _subscribe in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_subscribe)
    bpy.msgbus.clear_by_owner(_OWNER)
    from . import bars, menus
    if "group" in _saved and bars.GROUPS.get("lights") is not None:
        bars.GROUPS["lights"][:] = _saved.pop("group")
    if "menu" in _saved:
        i, it = _saved.pop("menu")
        items = menus.MAIN.get("Create", [])
        if it not in items:
            items.insert(min(i, len(items)), it)
    if hasattr(kinds, "RESOLVERS") and resolve in kinds.RESOLVERS:
        kinds.RESOLVERS.remove(resolve)
    del bpy.types.Light.b4d_falloff
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
