# SPDX-License-Identifier: GPL-3.0-or-later
"""Object Manager: turn the whole scene into an Octane scene, or an Octane scene into a Blender one.

To Octane: Octane renders it (with a kernel), every material the scene's objects use becomes an Octane material
(matconvert.to_octane), every light gets Octane's own emission nodes the way Octane's Add Light menu makes them (its
power and colour taken from the light's Intensity and Color), and the world gets Octane's environment (an HDRI's
picture, or the background colour and strength).

To Blender: Cycles renders it, every Octane material becomes a Principled BSDF (matconvert.to_blender), every light
goes back to Blender's own light with the Octane emission's power and colour, and the world gets Blender's Background
from Octane's environment. The scene's objects, cameras and animation are not touched; Undo puts everything back."""
import bpy

from . import matconvert

LIGHT_TYPES = {"POINT": ("octane_point_light_type", "Sphere"), "SUN": ("octane_directional_light_type", "Directional")}


def _scene_materials(scene):
    seen, out = set(), []
    for ob in scene.objects:
        for s in getattr(ob, "material_slots", ()):
            m = s.material
            if m is not None and m.name not in seen and m.library is None:
                seen.add(m.name)
                out.append(m)
    return out


def _octane_emission(light):
    if not light.use_nodes or light.node_tree is None:
        return None
    return next((n for n in light.node_tree.nodes if n.bl_idname.startswith("Octane") and "Power" in n.inputs), None)


# --- lights ----------------------------------------------------------------------------------------------------------------------
def light_to_octane(ob):
    light = ob.data
    if _octane_emission(light) is not None:
        return False
    from octane.nodes.base_node_tree import NodeTreeHandler
    energy, color = light.energy, tuple(light.color)
    kind = LIGHT_TYPES.get(light.type)
    if kind is not None:
        setattr(light.octane, kind[0], kind[1])
    if light.node_tree is not None:                   # Octane builds on Blender's default light nodes only
        light.node_tree.nodes.clear()
    light.use_nodes = False
    light.use_nodes = True
    if light.node_tree is not None and not light.node_tree.nodes:
        out = light.node_tree.nodes.new("ShaderNodeOutputLight")
        out.name = NodeTreeHandler.LIGHT_OUTPUT_NODE_NAME
        em = light.node_tree.nodes.new("ShaderNodeEmission")
        light.node_tree.links.new(em.outputs[0], out.inputs[0])
    NodeTreeHandler.update_new_light(ob)
    em = _octane_emission(light)
    if em is None:
        return False
    em.inputs["Power"].default_value = energy
    tex = em.inputs.get("Texture")
    if tex is not None and not tex.is_linked:
        try:
            tex.default_value = color[:len(tex.default_value)] if len(tex.default_value) == 3 else (*color, 1.0)
        except TypeError:
            pass
    return True


def light_to_blender(ob):
    light = ob.data
    em = _octane_emission(light)
    if em is None:
        return False
    light.energy = float(em.inputs["Power"].default_value)
    tex = em.inputs.get("Texture")
    if tex is not None and not tex.is_linked:
        try:
            light.color = tuple(tex.default_value)[:3]
        except (TypeError, ValueError):
            pass
    light.node_tree.nodes.clear()
    out = light.node_tree.nodes.new("ShaderNodeOutputLight")
    e = light.node_tree.nodes.new("ShaderNodeEmission")
    e.location = (-200, 0)
    light.node_tree.links.new(e.outputs[0], out.inputs[0])
    light.use_nodes = False
    return True


# --- world -----------------------------------------------------------------------------------------------------------------------
def _world_output(tree, target):
    return next((n for n in tree.nodes if n.bl_idname == "ShaderNodeOutputWorld" and n.target == target), None)


def world_to_octane(world):
    if world is None:
        return False
    if not world.use_nodes or world.node_tree is None:
        world.use_nodes = True
    tree = world.node_tree
    if any(n.bl_idname == "OctaneEditorWorldOutputNode" for n in tree.nodes):
        return False
    from . import octane_live
    if octane_live.sky(world):                         # an HDRI: Octane's environment shows the same picture
        return True
    out = _world_output(tree, "ALL") or next((n for n in tree.nodes if n.bl_idname == "ShaderNodeOutputWorld"), None)
    color, strength = (0.05, 0.05, 0.05), 1.0
    if out is not None and out.inputs[0].is_linked:
        bg = out.inputs[0].links[0].from_node
        if "Color" in bg.inputs and not bg.inputs["Color"].is_linked:
            color = tuple(bg.inputs["Color"].default_value)[:3]
        if "Strength" in bg.inputs:
            strength = float(bg.inputs["Strength"].default_value)
    elif world.color is not None:
        color = tuple(world.color)
    x, y = out.location if out is not None else (300, 0)
    rgb = tree.nodes.new("OctaneRGBColor"); rgb.location = (x - 600, y - 260)
    env = tree.nodes.new("OctaneTextureEnvironment"); env.location = (x - 300, y - 260)
    oct_out = tree.nodes.new("OctaneEditorWorldOutputNode"); oct_out.location = (x, y - 260)
    try:
        rgb.a_value = color
    except (AttributeError, TypeError):
        pass
    env.inputs["Power"].default_value = strength
    tree.links.new(rgb.outputs[0], env.inputs["Texture"])
    tree.links.new(env.outputs[0], oct_out.inputs[0])
    if out is not None and out.target == "ALL":
        out.target = "CYCLES"
        eevee = tree.nodes.new("ShaderNodeOutputWorld"); eevee.target = "EEVEE"; eevee.location = (x, y + 160)
        if out.inputs[0].is_linked:
            tree.links.new(out.inputs[0].links[0].from_socket, eevee.inputs[0])
    return True


def world_to_blender(world):
    if world is None or world.node_tree is None:
        return False
    tree = world.node_tree
    octs = [n for n in tree.nodes if n.bl_idname.startswith("Octane")]
    if not octs:
        return False
    oct_out = next((n for n in octs if n.bl_idname == "OctaneEditorWorldOutputNode"), None)
    env = oct_out.inputs[0].links[0].from_node if oct_out is not None and oct_out.inputs[0].is_linked else None
    color, strength, img = (0.05, 0.05, 0.05), 1.0, None
    if env is not None:
        if "Power" in env.inputs:
            strength = float(env.inputs["Power"].default_value)
        img = matconvert._image_up(env.inputs.get("Texture"))
        t = env.inputs.get("Texture")
        if t is not None and t.is_linked and img is None:
            up = t.links[0].from_node
            v = getattr(up, "a_value", None)
            if v is not None:
                color = tuple(v)[:3]
        elif t is not None and hasattr(t, "default_value"):
            try:
                color = tuple(t.default_value)[:3]
            except TypeError:
                pass
    for n in octs:
        tree.nodes.remove(n)
    keep = _world_output(tree, "CYCLES") or _world_output(tree, "ALL")
    for n in [n for n in tree.nodes if n.bl_idname == "ShaderNodeOutputWorld" and n != keep]:
        tree.nodes.remove(n)
    if keep is not None and keep.inputs[0].is_linked:
        keep.target = "ALL"                            # Blender's own world was kept for Cycles: give it to every engine
        return True
    out = keep or tree.nodes.new("ShaderNodeOutputWorld")
    out.target = "ALL"
    bg = tree.nodes.new("ShaderNodeBackground"); bg.location = (out.location.x - 250, out.location.y)
    bg.inputs["Strength"].default_value = strength
    if img is not None:
        te = tree.nodes.new("ShaderNodeTexEnvironment"); te.image = img; te.location = (bg.location.x - 300, bg.location.y)
        tree.links.new(te.outputs["Color"], bg.inputs["Color"])
    else:
        bg.inputs["Color"].default_value = (*color, 1.0)
    tree.links.new(bg.outputs[0], out.inputs[0])
    return True


# --- whole scene -----------------------------------------------------------------------------------------------------------------
def to_octane(context):
    from . import octane_live
    scene = context.scene
    scene.render.engine = "octane"
    octane_live._ready(scene)
    done = {"materials": 0, "lights": 0, "world": 0}
    for m in _scene_materials(scene):
        if not matconvert.is_octane(m):
            try:
                done["materials"] += bool(matconvert.to_octane(m))
            except Exception as e:
                print("Blenda 4D: material to Octane", m.name, e)
    for ob in scene.objects:
        if ob.type == "LIGHT":
            try:
                done["lights"] += light_to_octane(ob)
            except Exception as e:
                print("Blenda 4D: light to Octane", ob.name, e)
    done["world"] = int(world_to_octane(scene.world))
    return done


def to_blender(context):
    scene = context.scene
    done = {"materials": 0, "lights": 0, "world": 0}
    for m in _scene_materials(scene):
        if matconvert.is_octane(m):
            try:
                done["materials"] += bool(matconvert.to_blender(m))
            except Exception as e:
                print("Blenda 4D: material to Blender", m.name, e)
    for ob in scene.objects:
        if ob.type == "LIGHT":
            done["lights"] += light_to_blender(ob)
    done["world"] = int(world_to_blender(scene.world))
    scene.render.engine = "CYCLES"
    return done


def _say(done):
    return (f"{done['materials']} material{'s' if done['materials'] != 1 else ''}, "
            f"{done['lights']} light{'s' if done['lights'] != 1 else ''}"
            + (", the world" if done["world"] else "") + " converted")


class BLENDA4D_OT_scene_to_octane(bpy.types.Operator):
    """Convert the whole scene for Octane: render with Octane, Octane materials, Octane lights (from each light's
    Intensity and Color) and Octane's environment for the world"""
    bl_idname = "blenda4d.scene_to_octane"
    bl_label = "Convert Scene to Octane"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if not matconvert.octane_ready():
            cls.poll_message_set("Octane is not installed")
            return False
        return True

    def execute(self, context):
        self.report({"INFO"}, _say(to_octane(context)))
        return {"FINISHED"}


class BLENDA4D_OT_scene_to_blender(bpy.types.Operator):
    """Convert an Octane scene for Blender: render with Cycles, Blender materials (Principled BSDF), Blender lights
    (from each Octane emission's power and colour) and Blender's Background for the world"""
    bl_idname = "blenda4d.scene_to_blender"
    bl_label = "Convert Scene to Blender"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        self.report({"INFO"}, _say(to_blender(context)))
        return {"FINISHED"}


CLASSES = (BLENDA4D_OT_scene_to_octane, BLENDA4D_OT_scene_to_blender)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
