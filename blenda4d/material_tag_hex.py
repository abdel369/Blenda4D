# SPDX-License-Identifier: GPL-3.0-or-later
"""Seamless textures: hex tiling hides the repeats of a tiled image.

The surface is cut into hexagon-shaped patches on a triangle grid (Mikkelsen 2022, "Practical Real-Time Hex-Tiling");
each patch reads the image turned, shifted and scaled by its own random numbers, and neighbouring patches blend into
each other, so no straight repeat is left to see. Two ways to blend:

- ONE (default): every render sample picks one of the three nearby patches at random, weighted by how close it is,
  so each image is read once; the samples average into the soft blend (low sample counts show grain in the blend).
- THREE: reads each image three times and mixes them: smooth at any sample count, three times the reads. Images that
  feed a Bump or Displacement always use it, because those nodes look at nearby points.

Normal maps are turned with their patch, so lighting stays right in turned patches.
material_tag.py builds it with apply() when the first tag on a material turns Seamless on, and takes it out with
remove() after the last one turns it off. The settings come from each object (see _drive), so an object that shares
the material with Seamless off keeps its plain texture."""
import json
import math

import bpy

R3 = math.sqrt(3.0)
GROUP_ONE = "Blenda Seamless"
GROUP_THREE = "Blenda Seamless x3"
GROUP_NORMAL = "Blenda Seamless Normal"
MARK = "b4d_seamless"            # on every node apply() adds, so remove() finds them
RESTORE = "b4d_seamless_restore"  # on the material: the links remove() puts back

INPUTS = (       # name, default, min, max
    ("Patch Size", 1.0, 0.05, 20.0),
    ("Blend", 0.15, 0.0, 1.0),
    ("Blend Sharpness", 0.7, 0.0, 0.99),
    ("Random Turn", 180.0, 0.0, 180.0),
    ("Random Shift", 1.0, 0.0, 1.0),
    ("Random Size", 0.0, 0.0, 1.0),
    ("Seed", 0.0, 0.0, 100000.0),
)


class _Nodes:
    """Adds and links nodes in one tree."""

    def __init__(self, tree):
        self.tree = tree

    def node(self, kind, **props):
        n = self.tree.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def put(self, sock, val):
        if isinstance(val, bpy.types.NodeSocket):
            self.tree.links.new(val, sock)
        elif sock.type == "VECTOR" and isinstance(val, (int, float)):
            sock.default_value = (val, val, val)
        else:
            sock.default_value = val

    def m(self, op, a, b=None, c=None):
        n = self.node("ShaderNodeMath", operation=op)
        for i, v in enumerate((a, b, c)):
            if v is not None:
                self.put(n.inputs[i], v)
        return n.outputs[0]

    def v(self, op, a, b=None, scale=None):
        n = self.node("ShaderNodeVectorMath", operation=op)
        self.put(n.inputs[0], a)
        if b is not None:
            self.put(n.inputs[1], b)
        if scale is not None:
            self.put(n.inputs["Scale"], scale)
        return n.outputs["Value" if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else "Vector"]

    def sep(self, vec):
        n = self.node("ShaderNodeSeparateXYZ")
        self.put(n.inputs[0], vec)
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def comb(self, x, y, z=0.0):
        n = self.node("ShaderNodeCombineXYZ")
        for i, val in enumerate((x, y, z)):
            self.put(n.inputs[i], val)
        return n.outputs[0]


def _new_group(name, inputs, outputs):
    old = bpy.data.node_groups.get(name)
    if old:
        bpy.data.node_groups.remove(old)
    tree = bpy.data.node_groups.new(name, "ShaderNodeTree")
    for nm, kind, default, lo, hi in inputs:
        s = tree.interface.new_socket(nm, in_out="INPUT", socket_type=kind)
        if default is not None:
            s.default_value = default
        if lo is not None:
            s.min_value, s.max_value = lo, hi
    for nm, kind in outputs:
        tree.interface.new_socket(nm, in_out="OUTPUT", socket_type=kind)
    g = _Nodes(tree)
    return g, g.node("NodeGroupInput").outputs, g.node("NodeGroupOutput").inputs


def _patch_inputs():
    return [("Vector", "NodeSocketVector", None, None, None)] + [(nm, "NodeSocketFloat", d, lo, hi) for nm, d, lo, hi in INPUTS]


def _norm(g, ws):
    total = g.m("MAXIMUM", g.m("ADD", g.m("ADD", ws[0], ws[1]), ws[2]), 1e-8)
    return [g.m("DIVIDE", w, total) for w in ws]


def _gain(g, w, kexp):
    """A contrast curve on a weight: sharper blend, same centre."""
    lo = g.m("MULTIPLY", g.m("POWER", g.m("MULTIPLY", w, 2.0), kexp), 0.5)
    hi = g.m("SUBTRACT", 1.0, g.m("MULTIPLY", g.m("POWER", g.m("MULTIPLY_ADD", w, -2.0, 2.0), kexp), 0.5))
    below = g.m("LESS_THAN", w, 0.5)
    return g.m("MULTIPLY_ADD", below, g.m("SUBTRACT", lo, hi), hi)


def _grid(g, i):
    """The three patch centres around this point (grid coordinates) and their blend weights."""
    x, y, _ = g.sep(g.v("SCALE", i["Vector"], scale=g.m("DIVIDE", 2 * R3, i["Patch Size"])))
    sx = g.m("SUBTRACT", x, g.m("MULTIPLY", y, 1 / R3))
    sy = g.m("MULTIPLY", y, 2 / R3)
    bx, by = g.m("FLOOR", sx), g.m("FLOOR", sy)
    fx, fy = g.m("FRACT", sx), g.m("FRACT", sy)
    fsum = g.m("ADD", fx, fy)
    k = g.m("GREATER_THAN", fsum, 1.0)
    nk = g.m("SUBTRACT", 1.0, k)
    k2 = g.m("MULTIPLY_ADD", k, 2.0, -1.0)
    w = (g.m("MULTIPLY", g.m("SUBTRACT", fsum, 1.0), k2),
         g.m("SUBTRACT", k, g.m("MULTIPLY", fy, k2)),
         g.m("SUBTRACT", k, g.m("MULTIPLY", fx, k2)))
    verts = ((g.m("ADD", bx, k), g.m("ADD", by, k)),
             (g.m("ADD", bx, k), g.m("ADD", by, nk)),
             (g.m("ADD", bx, nk), g.m("ADD", by, k)))
    gamma = g.m("DIVIDE", 1.0, g.m("MAXIMUM", i["Blend"], 0.02))
    ws = _norm(g, [g.m("POWER", g.m("MAXIMUM", wi, 0.0), gamma) for wi in w])
    kexp = g.m("LOGARITHM", g.m("SUBTRACT", 1.0, i["Blend Sharpness"]), 0.5)
    return verts, _norm(g, [_gain(g, wi, kexp) for wi in ws])


def _seed(g, i):
    """The seed plus the object's own random number: every object and instance gets its own layout."""
    info = g.node("ShaderNodeObjectInfo")
    return g.m("MULTIPLY_ADD", info.outputs["Random"], 997.0, i["Seed"])


def _patch(g, i, vert, seed):
    """Texture coordinates inside one patch: turned, scaled and shifted by the patch's random numbers."""
    vx, vy = vert
    to_tex = g.m("DIVIDE", i["Patch Size"], 2 * R3)
    centre = g.comb(g.m("MULTIPLY", g.m("MULTIPLY_ADD", vy, 0.5, vx), to_tex),
                    g.m("MULTIPLY", g.m("MULTIPLY", vy, R3 / 2), to_tex))
    a = g.node("ShaderNodeTexWhiteNoise", noise_dimensions="4D")
    g.put(a.inputs["Vector"], g.comb(vx, vy))
    g.put(a.inputs["W"], seed)
    b = g.node("ShaderNodeTexWhiteNoise", noise_dimensions="4D")
    g.put(b.inputs["Vector"], g.comb(vx, vy))
    g.put(b.inputs["W"], g.m("ADD", seed, 0.5))
    r, gg, bb = g.sep(a.outputs["Color"])
    angle = g.m("MULTIPLY", g.m("MULTIPLY_ADD", r, 2.0, -1.0), g.m("RADIANS", i["Random Turn"]))
    scale = g.m("POWER", 2.0, g.m("MULTIPLY", g.m("MULTIPLY_ADD", b.outputs["Value"], 2.0, -1.0), i["Random Size"]))
    rot = g.node("ShaderNodeVectorRotate", rotation_type="Z_AXIS")
    g.put(rot.inputs["Vector"], i["Vector"])
    g.put(rot.inputs["Center"], centre)
    g.put(rot.inputs["Angle"], angle)
    local = g.v("SCALE", g.v("SUBTRACT", rot.outputs[0], centre), scale=g.m("DIVIDE", 1.0, scale))
    shift = g.v("SCALE", g.comb(gg, bb), scale=i["Random Shift"])
    return g.v("ADD", g.v("ADD", local, centre), shift), angle, scale


def _clean(g, i):
    ins = {s.name: s for s in i if s.name}
    ins["Patch Size"] = g.m("MAXIMUM", ins["Patch Size"], 0.05)
    return ins


def _build_one():
    g, i, o = _new_group(GROUP_ONE, _patch_inputs(), [
        ("Vector", "NodeSocketVector"), ("Angle", "NodeSocketFloat"), ("Scale", "NodeSocketFloat"),
        ("Weights", "NodeSocketColor")])
    i = _clean(g, i)
    verts, ws = _grid(g, i)
    pick = g.node("ShaderNodeTexWhiteNoise", noise_dimensions="3D")     # a fresh random number per render sample
    g.put(pick.inputs["Vector"], g.node("ShaderNodeNewGeometry").outputs["Position"])
    u = pick.outputs["Value"]
    first = g.m("LESS_THAN", u, ws[0])
    upto2 = g.m("LESS_THAN", u, g.m("ADD", ws[0], ws[1]))
    mask = (first, g.m("SUBTRACT", upto2, first), g.m("SUBTRACT", 1.0, upto2))

    def chosen(axis):
        acc = g.m("MULTIPLY", mask[0], verts[0][axis])
        for mk, vt in zip(mask[1:], verts[1:]):
            acc = g.m("MULTIPLY_ADD", mk, vt[axis], acc)
        return acc

    uv, angle, scale = _patch(g, i, (chosen(0), chosen(1)), _seed(g, i))
    g.put(o["Vector"], uv)
    g.put(o["Angle"], angle)
    g.put(o["Scale"], scale)
    g.put(o["Weights"], g.comb(*ws))
    return g.tree


def _build_three():
    outs = []
    for n in (1, 2, 3):
        outs += [(f"Vector {n}", "NodeSocketVector"), (f"Angle {n}", "NodeSocketFloat"),
                 (f"Scale {n}", "NodeSocketFloat"), (f"Weight {n}", "NodeSocketFloat")]
    g, i, o = _new_group(GROUP_THREE, _patch_inputs(), outs)
    i = _clean(g, i)
    verts, ws = _grid(g, i)
    seed = _seed(g, i)
    for n, (vt, w) in enumerate(zip(verts, ws), 1):
        uv, angle, scale = _patch(g, i, vt, seed)
        g.put(o[f"Vector {n}"], uv)
        g.put(o[f"Angle {n}"], angle)
        g.put(o[f"Scale {n}"], scale)
        g.put(o[f"Weight {n}"], w)
    return g.tree


def _encode(g, slope):
    sx, sy, _ = g.sep(slope)
    n = g.v("NORMALIZE", g.comb(sx, sy, 1.0))
    return g.v("ADD", g.v("SCALE", n, scale=0.5), 0.5)


def _build_normal():
    """A tangent normal colour -> slope, turned and scaled with its patch; also as a colour again."""
    g, i, o = _new_group(GROUP_NORMAL, [
        ("Color", "NodeSocketColor", (0.5, 0.5, 1.0, 1.0), None, None),
        ("Angle", "NodeSocketFloat", 0.0, None, None),
        ("Scale", "NodeSocketFloat", 1.0, None, None)],
        [("Color", "NodeSocketColor"), ("Slope", "NodeSocketVector")])
    nx, ny, nz = g.sep(g.v("SUBTRACT", g.v("SCALE", i["Color"], scale=2.0), 1.0))
    nz = g.m("MAXIMUM", nz, 0.02)
    rot = g.node("ShaderNodeVectorRotate", rotation_type="Z_AXIS")     # the pattern is turned by -Angle: so are its slopes
    g.put(rot.inputs["Vector"], g.comb(g.m("DIVIDE", nx, nz), g.m("DIVIDE", ny, nz)))
    g.put(rot.inputs["Angle"], g.m("MULTIPLY", i["Angle"], -1.0))
    slope = g.v("SCALE", rot.outputs[0], scale=g.m("DIVIDE", 1.0, i["Scale"]))
    g.put(o["Slope"], slope)
    g.put(o["Color"], _encode(g, slope))
    return g.tree


def groups():
    found = [bpy.data.node_groups.get(n) for n in (GROUP_ONE, GROUP_THREE, GROUP_NORMAL)]
    if all(found):
        return found
    return [_build_one(), _build_three(), _build_normal()]


def _group_node(g, tree, label):
    n = g.node("ShaderNodeGroup")
    n.node_tree = tree
    n.label = label
    n[MARK] = True
    return n


def _vector_source(g, img):
    if img.inputs["Vector"].is_linked:
        return img.inputs["Vector"].links[0].from_socket
    uv = g.node("ShaderNodeTexCoord")
    uv[MARK] = True
    return uv.outputs["UV"]


# each object stores three vectors per material (material_tag._push): zeros mean no turn, shift or size change,
# so an object with Seamless off sees its plain texture
DRIVEN = (("hx", ("Random Turn", "Random Shift", "Random Size")),
          ("hy", ("Blend", "Blend Sharpness", "Seed")),
          ("hz", ("Patch Size",)))


def _drive(g, node, prefix):
    for part, names in DRIVEN:
        a = g.node("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name=f"{prefix}_{part}")
        for name, sock in zip(names, g.sep(a.outputs["Vector"])):
            g.put(node.inputs[name], sock)


def _feeds(sock, kinds, depth=4):
    """True when this output reaches a node of these types within a few links (a Bump behind a Color Ramp)."""
    for lk in sock.links:
        n = lk.to_node
        if n.type in kinds or (depth > 1 and any(_feeds(o, kinds, depth - 1) for o in n.outputs)):
            return True
    return False


SLOPED = ("BUMP", "DISPLACEMENT", "VECTOR_DISPLACEMENT")


def built(mat):
    return bool(mat and mat.node_tree and RESTORE in mat)


def apply(mat, prefix, mode="ONE"):
    """Hex-tile every image of a node material, its settings read from each object's values named after prefix."""
    one, three, normal = groups()
    tree = mat.node_tree
    g = _Nodes(tree)
    before = {n.name for n in tree.nodes}
    links, interp = [], {}
    hexes = {}       # one grid node per coordinate source and read count: all channels share one layout
    for img in [n for n in tree.nodes if n.type == "TEX_IMAGE" and not n.get(MARK)]:
        vec = img.inputs["Vector"]
        links.append((img.name, vec.identifier) + ((vec.links[0].from_node.name, vec.links[0].from_socket.identifier)
                                                   if vec.links else (None, None)))
        triple = mode == "THREE" or any(_feeds(o, SLOPED) for o in img.outputs)
        src = _vector_source(g, img)
        hk = (src.node.name, src.identifier, triple)
        if hk not in hexes:
            hexes[hk] = _group_node(g, three if triple else one, "Seamless")
            g.put(hexes[hk].inputs["Vector"], src)
            _drive(g, hexes[hk], prefix)
        h = hexes[hk]
        targets = [(lk.from_socket.name, lk.to_socket) for out in img.outputs for lk in out.links]
        for name, to in targets:
            links.append((to.node.name, to.identifier, img.name, img.outputs[name].identifier))
        if not triple:
            # Cubic reads no mip levels: in a blend zone neighbouring pixels read different patches, and EEVEE would
            # take that jump as a far-away surface and read a blurred level (outlines round every patch)
            interp[img.name] = img.interpolation
            img.interpolation = "Cubic"
            g.put(img.inputs["Vector"], h.outputs["Vector"])
            for name, to in targets:
                if name == "Color" and to.node.type == "NORMAL_MAP":
                    nrm = _group_node(g, normal, "Seamless Normal")
                    g.put(nrm.inputs["Color"], img.outputs["Color"])
                    g.put(nrm.inputs["Angle"], h.outputs["Angle"])
                    g.put(nrm.inputs["Scale"], h.outputs["Scale"])
                    g.put(to, nrm.outputs["Color"])
            continue
        reads = [img]
        for _ in range(2):
            c = tree.nodes.new("ShaderNodeTexImage")
            c.image, c.interpolation, c.extension = img.image, img.interpolation, img.extension
            c.projection = img.projection
            c[MARK] = True
            reads.append(c)
        for n, r in enumerate(reads, 1):
            g.put(r.inputs["Vector"], h.outputs[f"Vector {n}"])
        for name, to in targets:
            w = [h.outputs[f"Weight {n}"] for n in (1, 2, 3)]
            if name == "Color" and to.node.type == "NORMAL_MAP":
                slope = None
                for n, r in enumerate(reads, 1):
                    nrm = _group_node(g, normal, "Seamless Normal")
                    g.put(nrm.inputs["Color"], r.outputs["Color"])
                    g.put(nrm.inputs["Angle"], h.outputs[f"Angle {n}"])
                    g.put(nrm.inputs["Scale"], h.outputs[f"Scale {n}"])
                    part = g.v("SCALE", nrm.outputs["Slope"], scale=w[n - 1])
                    slope = part if slope is None else g.v("ADD", slope, part)
                g.put(to, _encode(g, slope))
            elif name == "Color":
                mix = None
                for r, wn in zip(reads, w):
                    part = g.v("SCALE", r.outputs["Color"], scale=wn)
                    mix = part if mix is None else g.v("ADD", mix, part)
                g.put(to, mix)
            else:
                mix = None
                for r, wn in zip(reads, w):
                    mix = g.m("MULTIPLY", r.outputs[name], wn) if mix is None else g.m("MULTIPLY_ADD", r.outputs[name], wn, mix)
                g.put(to, mix)
    for n in tree.nodes:
        if n.name not in before:
            n[MARK] = True
    mat[RESTORE] = json.dumps({"links": links, "interp": interp})
    return list(hexes.values())


def remove(mat):
    """Take out every node apply() added and put the material's own links back."""
    tree = mat.node_tree
    data = json.loads(mat.get(RESTORE) or "{}")
    for n in [n for n in tree.nodes if n.get(MARK)]:
        tree.nodes.remove(n)
    for to_node, to_id, from_node, from_id in data.get("links", []):
        tn, fn = tree.nodes.get(to_node), tree.nodes.get(from_node) if from_node else None
        if tn is None:
            continue
        to = next((s for s in tn.inputs if s.identifier == to_id), None)
        if fn is None:                    # it had nothing wired in: leave it unwired
            for lk in list(to.links if to is not None else ()):
                tree.links.remove(lk)
            continue
        fr = next((s for s in fn.outputs if s.identifier == from_id), None)
        if to is not None and fr is not None:
            tree.links.new(fr, to)
    for name, mode in data.get("interp", {}).items():
        if tree.nodes.get(name):
            tree.nodes[name].interpolation = mode
    if RESTORE in mat:
        del mat[RESTORE]


def sync(mat, prefix):
    """Build again when the material gained an image since: the new image joins the grid."""
    if built(mat) and any(n.type == "TEX_IMAGE" and not n.get(MARK) and not
                          (n.inputs["Vector"].links and n.inputs["Vector"].links[0].from_node.get(MARK))
                          for n in mat.node_tree.nodes):
        remove(mat)
        apply(mat, prefix)
