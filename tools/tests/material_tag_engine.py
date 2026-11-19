# Headless test of material tags: the tag's rows change the material's nodes and a small render, a second object
# sharing the material keeps its own values, Seamless builds and removes the hex nodes, projections differ.
#   BLENDER_USER_CONFIG=<scratch> Blender -b --factory-startup --python tools/tests/material_tag_engine.py
import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from blenda4d import kinds, managers, material_tag, material_tag_hex, menus  # noqa: E402

FAIL = []
OUT = os.environ.get("B4D_OUT", "/tmp")


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what, flush=True)
    if not cond:
        FAIL.append(what)


def setup():
    menus.register()
    managers.register()
    bpy.utils.register_class(kinds.BLENDA4D_OT_add_kind)
    material_tag.register()
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    img = bpy.data.images.new("Grid", 64, 64)
    img.generated_type = "COLOR_GRID"
    mat = bpy.data.materials.new("Rock")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    em = nt.nodes.new("ShaderNodeEmission")               # emission: the render is the texture itself, no lighting
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    obs = []
    for name in ("A", "B"):
        bpy.ops.mesh.primitive_plane_add(size=2)
        ob = bpy.context.object
        ob.name = name
        ob.data.materials.append(mat)
        obs.append(ob)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1)
    ball = bpy.context.object
    ball.name = "Ball"
    ball.data.materials.append(mat.copy())
    ball.material_slots[0].material.name = "BallMat"
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 2.2
    cam.location = (0, 0, 5)
    bpy.context.scene.collection.objects.link(cam)
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 8
    sc.cycles.use_denoising = False
    sc.cycles.seed = 1
    sc.render.resolution_x = sc.render.resolution_y = 48
    sc.render.film_transparent = True
    return obs[0], obs[1], ball, mat


def render(ob):
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = o != ob
    sc = bpy.context.scene
    sc.render.filepath = os.path.join(OUT, "mt_render.png")
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(sc.render.filepath, check_existing=False)
    px = list(im.pixels)
    bpy.data.images.remove(im)
    return px


def diff(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / max(len(a), 1)


def tex_of(mat):
    return next(n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and not n.get(material_tag_hex.MARK))


def main():
    a, b, ball, mat = setup()
    base_a, base_b = render(a), render(b)
    check(diff(base_a, base_b) < 1e-4, "A and B look the same before any tag change")
    bpy.ops.blenda4d.mat_tag_pick(name="A", slot=0)
    check(bpy.context.window_manager.b4d_am_subject == "TAG:A:0", "picking the swatch makes the tag the subject")
    check(len(a.b4d_mat_tags) == 1, "the pick made the tag's settings row")
    n0 = len(mat.node_tree.nodes)
    check(not any(n.get(material_tag.MARK) for n in mat.node_tree.nodes), "looking at a tag adds no nodes")

    t = a.b4d_mat_tags[0]
    t.length_u = 50.0
    tex = tex_of(mat)
    src = tex.inputs["Vector"].links[0].from_node if tex.inputs["Vector"].links else None
    check(src is not None and src.get(material_tag.MARK) == "map" and src.node_tree.name == material_tag.MAP_GROUP,
          "Length puts the Tag Mapping group in front of the image")
    p = material_tag.prefix(mat)
    check(abs(a[p + "_b"][0] - 1.0) < 1e-6 and abs(t.tiles_u - 2.0) < 1e-6, "Length U 50 % = 2 tiles, stored on A")
    check(p + "_b" not in b, "B has no values of its own")
    r_len = render(a)
    check(diff(r_len, base_a) > 0.01, f"Length U changes A's render ({diff(r_len, base_a):.4f})")
    check(diff(render(b), base_b) < 1e-4, "B's render is unchanged (shared material, own values)")

    t.offset_v = 25.0
    r_off = render(a)
    check(diff(r_off, r_len) > 0.01, f"Offset V changes the render ({diff(r_off, r_len):.4f})")
    t.offset_v = 0.0

    t.tiles_v = 3.0
    check(abs(t.length_v - 100.0 / 3) < 1e-4, "Tiles V sets Length V")
    r_tv = render(a)
    check(diff(r_tv, r_len) > 0.01, "Tiles V changes the render")
    t.length_v = 100.0

    t.length_u = 50.0
    t.offset_u = 25.0
    r_tile = render(a)
    t.tile = False
    check(any(n.get(material_tag.MARK) == "mask" for n in mat.node_tree.nodes), "Tile off adds the tile-off nodes")
    r_notile = render(a)
    check(diff(r_notile, r_tile) > 0.01, f"Tile off changes the render ({diff(r_notile, r_tile):.4f})")
    check(diff(render(b), base_b) < 1e-4, "B still shows the plain texture with A's Tile off")
    t.tile = True
    check(diff(render(a), r_tile) < 1e-4, "Tile on again: the same render as before")
    t.offset_u = 0.0

    # second object's own values
    bpy.ops.blenda4d.mat_tag_pick(name="B", slot=0)
    tb = b.b4d_mat_tags[0]
    tb.length_v = 25.0
    check(abs(a[p + "_b"][1]) < 1e-6 and abs(b[p + "_b"][1] - 3.0) < 1e-6, "B's Length V is B's alone")
    check(sum(1 for n in mat.node_tree.nodes if n.get(material_tag.MARK) == "map") == 1, "one mapping node serves both")

    # seamless
    before_links = (tex.inputs["Vector"].links[0].from_node.name, len(mat.node_tree.nodes))
    r_plain, r_plain_b = render(a), render(b)
    t.seamless = True
    check(material_tag_hex.built(mat), "Seamless builds the hex nodes")
    vec_src = tex.inputs["Vector"].links[0].from_node
    check(vec_src.get(material_tag_hex.MARK) and vec_src.node_tree.name == material_tag_hex.GROUP_ONE,
          "the image reads its coordinates through the Seamless group")
    check(a[p + "_hx"][0] == 180.0 and b[p + "_hx"][0] == 0.0, "A turns its patches, B (Seamless off) does not")
    r_seam = render(a)
    rb = render(b)
    check(diff(rb, r_plain_b) < 0.01, f"B keeps its plain texture while A is Seamless ({diff(rb, r_plain_b):.4f})")
    check(diff(r_seam, r_plain) > 0.01, f"Seamless changes A's render ({diff(r_seam, r_plain):.4f})")
    t.hex_seed = 7
    r_seed = render(a)
    check(diff(r_seed, r_seam) > 0.005, f"Seed changes the layout ({diff(r_seed, r_seam):.4f})")
    for prop, val in (("hex_blend", 60.0), ("hex_patch", 300.0), ("hex_turn", 20.0), ("hex_shift", 0.0), ("hex_size", 80.0),
                      ("hex_sharpness", 10.0)):
        old = getattr(t, prop)
        r0 = render(a)
        setattr(t, prop, val)
        r1 = render(a)
        check(diff(r1, r0) > 0.002, f"{prop} changes the render ({diff(r1, r0):.4f})")
        setattr(t, prop, old)
    t.seamless = False
    check(not material_tag_hex.built(mat), "Seamless off takes the hex nodes out")
    check((tex.inputs["Vector"].links[0].from_node.name, len(mat.node_tree.nodes)) == before_links,
          "the material's own links and nodes are back")
    check(diff(render(a), r_plain) < 1e-4, "and the render is as before Seamless")

    # projections on the ball
    bpy.ops.blenda4d.mat_tag_pick(name="Ball", slot=0)
    bm = ball.material_slots[0].material
    tc = ball.b4d_mat_tags[0]
    tc.length_u = 100.0                                    # touch: wires the material with no visible change
    r_uv = render(ball)
    shots = {}
    for proj in ("FLAT", "SPHERICAL", "CYLINDRICAL", "CUBIC"):
        tc.projection = proj
        shots[proj] = render(ball)
        if proj == "SPHERICAL":     # a UV sphere's own UVs are a spherical projection: the two should match
            check(diff(shots[proj], r_uv) < 0.01, f"Spherical matches the UV sphere's own UVs ({diff(shots[proj], r_uv):.4f})")
        else:
            check(diff(shots[proj], r_uv) > 0.005, f"Projection {proj} differs from UV ({diff(shots[proj], r_uv):.4f})")
    check(diff(shots["FLAT"], shots["CUBIC"]) > 0.005, "Flat and Cubic differ")
    tc.projection = "FLAT"
    r0 = render(ball)
    tc.size = (1.0, 1.0, 1.0)
    check(diff(render(ball), r0) > 0.005, "Size changes the flat projection")
    tc.position = (0.3, 0.0, 0.0)
    r1 = render(ball)
    tc.rotation = (0.0, 0.0, 0.7)
    check(diff(render(ball), r1) > 0.005, "Rotation changes the flat projection")
    bpy.ops.blenda4d.mat_tag_fit(name="Ball", slot=0)
    check(all(abs(s - 2.0) < 1e-3 for s in tc.size) and all(abs(c) < 1e-3 for c in tc.position), "Fit to Object: ball bounds")

    # rename and slot change
    mat.name = "Rock Renamed"
    material_tag.wire(mat)
    p2 = material_tag.prefix(mat)
    names = {n.attribute_name for n in mat.node_tree.nodes if n.type == "ATTRIBUTE"}
    check(all(nm.startswith(p2) for nm in names) and (p2 + "_b") in a, "renamed material: nodes read the new names")
    check(diff(render(a), r_plain) < 1e-4, "renamed material renders the same")

    # EEVEE reads the same per-object values
    sc = bpy.context.scene
    try:
        sc.render.engine = "BLENDER_EEVEE"
    except TypeError:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
    t.length_u = 100.0
    ea = render(a)
    t.length_u = 20.0
    eb = render(a)
    check(diff(ea, eb) > 0.01, f"EEVEE: Length U changes A's render ({diff(ea, eb):.4f})")
    check(diff(render(b), ea) > 0.01, "EEVEE: B (Length V 25 %) differs from A")

    print("B4D FAIL" if FAIL else "B4D PASS", len(FAIL), FAIL, flush=True)


main()
