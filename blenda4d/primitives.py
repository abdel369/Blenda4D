# SPDX-License-Identifier: GPL-3.0-or-later
"""Parametric primitives as live Geometry Nodes generators.

Every node-group input is one setting, in Blenda's units (cm, counts), named by its Attribute Manager row key.
Geometry is produced in Blender metres (cm * 0.01). An object's kind is stored as its "b4d_type" (the PRIMS key)."""
import bpy

SCALE = 0.01

from . import cyc_desc

# kind -> (object type, label, [(socket name, socket type, default, Attribute Manager row key)])
PRIMS = {
    "cyc": (cyc_desc.CYC_WALL, "Cyc Wall", cyc_desc.inputs()),          # Blenda's own studio backdrop
    "cube": ("cube", "Cube", [
        ("Size", "VECTOR", (200.0, 200.0, 200.0), 'cube.size'),
        ("Segments X", "INT", 1, 'cube.segments_x'), ("Segments Y", "INT", 1, 'cube.segments_y'), ("Segments Z", "INT", 1, 'cube.segments_z'),
        ("Separate Surfaces", "BOOL", False, 'cube.separate_surfaces'), ("Fillet", "BOOL", False, 'cube.fillet'),
        ("Fillet Radius", "FLOAT", 3.0, 'cube.fillet_radius'), ("Fillet Subdivision", "INT", 3, 'cube.fillet_subdivision'),
    ]),
    "sphere": ("sphere", "Sphere", [("Radius", "FLOAT", 100.0, 'sphere.radius'), ("Segments", "INT", 32, 'sphere.segments'),
                               ("Type", "INT", 0, 'sphere.type'), ("Render Perfect", "BOOL", True, 'sphere.render_perfect')]),
    "cylinder": ("cylinder", "Cylinder", [
        ("Radius", "FLOAT", 50.0, 'cylinder.radius'), ("Height", "FLOAT", 200.0, 'cylinder.height'),
        ("Height Segments", "INT", 1, 'cylinder.height_segments'), ("Rotation Segments", "INT", 36, 'cylinder.rotation_segments'), ("Orientation", "INT", 2, 'cylinder.orientation'),
        ("Caps", "BOOL", True, 'cylinder.caps'), ("Cap Segments", "INT", 1, 'cylinder.cap_segments'), ("Fillet", "BOOL", False, 'cylinder.fillet'),
        ("Fillet Segments", "INT", 5, 'cylinder.fillet_segments'), ("Fillet Radius", "FLOAT", 5.0, 'cylinder.fillet_radius'), ("Slice", "BOOL", False, 'slice.on'), ("From", "FLOAT", 0.0, 'slice.from'), ("To", "FLOAT", 180.0, 'slice.to'), ("Regular Grid", "BOOL", False, 'slice.regular'), ("Width", "FLOAT", 10.0, 'slice.width'),
    ]),
    "plane": ("plane", "Plane", [
        ("Width", "FLOAT", 400.0, 'plane.width'), ("Height", "FLOAT", 400.0, 'plane.height'),
        ("Width Segments", "INT", 20, 'plane.width_segments'), ("Height Segments", "INT", 20, 'plane.height_segments'), ("Orientation", "INT", 2, 'plane.orientation'),
    ]),
    "disc": ("disc", "Disc", [("Inner Radius", "FLOAT", 0.0, 'disc.inner_radius'), ("Outer Radius", "FLOAT", 100.0, 'disc.outer_radius'), ("Disc Segments", "INT", 1, 'disc.disc_segments'),
                            ("Rotation Segments", "INT", 36, 'disc.rotation_segments'), ("Orientation", "INT", 2, 'disc.orientation'), ("Slice", "BOOL", False, 'slice.on'), ("From", "FLOAT", 0.0, 'slice.from'), ("To", "FLOAT", 180.0, 'slice.to'), ("Regular Grid", "BOOL", False, 'slice.regular'), ("Width", "FLOAT", 10.0, 'slice.width')]),
    "cone": ("cone", "Cone", [
        ("Top Radius", "FLOAT", 0.0, 'cone.top_radius'), ("Bottom Radius", "FLOAT", 100.0, 'cone.bottom_radius'),
        ("Height", "FLOAT", 200.0, 'cone.height'), ("Height Segments", "INT", 8, 'cone.height_segments'),
        ("Rotation Segments", "INT", 36, 'cone.rotation_segments'), ("Orientation", "INT", 2, 'cone.orientation'),
        ("Caps", "BOOL", True, 'cone.caps'), ("Cap Segments", "INT", 1, 'cone.cap_segments'), ("Top Fillet", "BOOL", False, 'cone.top_fillet'),
        ("Top Fillet Size", "FLOAT", 10.0, 'cone.top_fillet_radius'), ("Top Fillet Depth", "FLOAT", 10.0, 'cone.top_fillet_height'), ("Bottom Fillet", "BOOL", False, 'cone.bottom_fillet'),
        ("Bottom Fillet Size", "FLOAT", 10.0, 'cone.bottom_fillet_radius'), ("Bottom Fillet Depth", "FLOAT", 10.0, 'cone.bottom_fillet_height'), ("Fillet Segments", "INT", 5, 'cone.fillet_segments'), ("Slice", "BOOL", False, 'slice.on'), ("From", "FLOAT", 0.0, 'slice.from'), ("To", "FLOAT", 180.0, 'slice.to'), ("Regular Grid", "BOOL", False, 'slice.regular'), ("Width", "FLOAT", 10.0, 'slice.width'),
    ]),
    "torus": ("torus", "Torus", [
        ("Ring Radius", "FLOAT", 100.0, 'torus.ring_radius'), ("Pipe Radius", "FLOAT", 20.0, 'torus.pipe_radius'),
        ("Ring Segments", "INT", 36, 'torus.ring_segments'), ("Pipe Segments", "INT", 8, 'torus.pipe_segments'), ("Orientation", "INT", 2, 'torus.orientation'), ("Slice", "BOOL", False, 'slice.on'), ("From", "FLOAT", 0.0, 'slice.from'), ("To", "FLOAT", 180.0, 'slice.to'), ("Regular Grid", "BOOL", False, 'slice.regular'), ("Width", "FLOAT", 10.0, 'slice.width'),
    ]),
    "pyramid": ("pyramid", "Pyramid", [("Size", "VECTOR", (200.0, 200.0, 200.0), 'pyramid.size'), ("Segments", "INT", 1, 'pyramid.segments'), ("Orientation", "INT", 2, 'pyramid.orientation')]),
    "tube": ("tube", "Tube", [
        ("Inner Radius", "FLOAT", 50.0, 'tube.inner_radius'), ("Outer Radius", "FLOAT", 100.0, 'tube.outer_radius'),
        ("Rotation Segments", "INT", 36, 'tube.rotation_segments'), ("Cap Segments", "INT", 1, 'tube.cap_segments'),
        ("Height", "FLOAT", 100.0, 'tube.height'), ("Height Segments", "INT", 1, 'tube.height_segments'), ("Orientation", "INT", 2, 'tube.orientation'),
        ("Fillet", "BOOL", False, 'tube.fillet'), ("Fillet Segments", "INT", 8, 'tube.fillet_segments'), ("Fillet Radius", "FLOAT", 10.0, 'tube.fillet_radius'), ("Slice", "BOOL", False, 'slice.on'), ("From", "FLOAT", 0.0, 'slice.from'), ("To", "FLOAT", 180.0, 'slice.to'), ("Regular Grid", "BOOL", False, 'slice.regular'), ("Width", "FLOAT", 10.0, 'slice.width'),
    ]),
    "oiltank": ("oiltank", "Oil Tank", [
        ("Radius", "FLOAT", 100.0, 'oiltank.radius'), ("Height", "FLOAT", 200.0, 'oiltank.height'), ("Height Segments", "INT", 4, 'oiltank.height_segments'),
        ("Cap Height", "FLOAT", 25.0, 'oiltank.cap_height'), ("Cap Segments", "INT", 4, 'oiltank.cap_segments'), ("Rotation Segments", "INT", 16, 'oiltank.rotation_segments'), ("Orientation", "INT", 2, 'oiltank.orientation'), ("Slice", "BOOL", False, 'slice.on'), ("From", "FLOAT", 0.0, 'slice.from'), ("To", "FLOAT", 180.0, 'slice.to'), ("Regular Grid", "BOOL", False, 'slice.regular'), ("Width", "FLOAT", 10.0, 'slice.width'),
    ]),
    "capsule": ("capsule", "Capsule", [
        ("Radius", "FLOAT", 50.0, 'capsule.radius'), ("Height", "FLOAT", 200.0, 'capsule.height'), ("Height Segments", "INT", 4, 'capsule.height_segments'),
        ("Cap Segments", "INT", 4, 'capsule.cap_segments'), ("Rotation Segments", "INT", 16, 'capsule.rotation_segments'), ("Orientation", "INT", 2, 'capsule.orientation'), ("Slice", "BOOL", False, 'slice.on'), ("From", "FLOAT", 0.0, 'slice.from'), ("To", "FLOAT", 180.0, 'slice.to'), ("Regular Grid", "BOOL", False, 'slice.regular'), ("Width", "FLOAT", 10.0, 'slice.width'),
    ]),
    "platonic": ("platonic", "Platonic", [("Radius", "FLOAT", 100.0, 'platonic.radius'), ("Segments", "INT", 1, 'platonic.segments'), ("Type", "INT", 4, 'platonic.type')]),
    # Relief: an image's brightness lifts a grid; defaults follow the Landscape
    "relief": ("relief", "Relief", [
        ("Size", "VECTOR", (400.0, 100.0, 400.0), 'relief.size'), ("Width Segments", "INT", 100, 'relief.width_segments'), ("Depth Segments", "INT", 100, 'relief.depth_segments'),
        ("Bottom Level", "FLOAT", 0.0, 'relief.bottom_level'), ("Top Level", "FLOAT", 100.0, 'relief.top_level'), ("Orientation", "INT", 2, 'relief.orientation'),
        ("Spherical", "BOOL", False, 'relief.spherical'), ("Image", "IMAGE", None, 'relief.image'),
    ]),
    "landscape": ("landscape", "Landscape", [
        ("Size", "VECTOR", (600.0, 100.0, 600.0), 'landscape.size'), ("Width Segments", "INT", 100, 'landscape.width_segments'),
        ("Depth Segments", "INT", 100, 'landscape.depth_segments'), ("Rough Furrows", "FLOAT", 0.5, 'landscape.rough_furrows'), ("Fine Furrows", "FLOAT", 0.5, 'landscape.fine_furrows'),
        ("Scale", "FLOAT", 1.0, 'landscape.scale'), ("Sea Level", "FLOAT", 0.0, 'landscape.sea_level'), ("Plateau Level", "FLOAT", 1.0, 'landscape.plateau_level'),
        ("Multifractal", "BOOL", True, 'landscape.multifractal'), ("Seed", "INT", 0, 'landscape.seed'), ("Orientation", "INT", 2, 'landscape.orientation'),
        ("Flatten Edges", "BOOL", False, 'landscape.borders_at_sea_level'), ("Spherical", "BOOL", False, 'landscape.spherical'),
        # Blender's Noise Texture controls
        ("Noise Type", "INT", 1, 'landscape.noise_type'), ("Noise Scale", "FLOAT", 2.0, 'landscape.noise_scale'), ("Lacunarity", "FLOAT", 2.0, 'landscape.lacunarity'),
        ("Distortion", "FLOAT", 0.0, 'landscape.distortion'), ("Offset", "FLOAT", 0.0, 'landscape.offset'), ("Gain", "FLOAT", 1.0, 'landscape.gain'),
    ]),
    "figure": ("figure", "Figure", [("Height", "FLOAT", 180.0, 'figure.height'), ("Segments", "INT", 14, 'figure.segments')]),
    "bezier": ("bezier", "Bezier", [
        ("Subdivision X", "INT", 24, 'bezier.subdivision_x'), ("Subdivision Y", "INT", 24, 'bezier.subdivision_y'),
        ("Control Points X", "INT", 3, 'bezier.grid_points_x'), ("Control Points Y", "INT", 3, 'bezier.grid_points_y'),
        ("Closed X", "BOOL", False, 'bezier.closed_x'), ("Closed Y", "BOOL", False, 'bezier.closed_y'),
    ]),
}
# Platonic types
PLATONIC_TYPES = ("Tetra", "Hexa", "Octa", "Dodeca", "Icosa", "Bucky")
TYPE_TO_KIND = {v[0]: k for k, v in PRIMS.items()}
SOCKET = {"FLOAT": "NodeSocketFloat", "INT": "NodeSocketInt", "VECTOR": "NodeSocketVector", "BOOL": "NodeSocketBool",
          "MENU": "NodeSocketMenu", "IMAGE": "NodeSocketImage"}
# menu settings: the group input is a menu; a Menu Switch turns the chosen label into its number for the nodes
CYCLES = {
    ("sphere", "Type"): [("Standard", 0), ("Hemisphere", 5), ("Tetrahedron", 1), ("Hexahedron", 2), ("Octahedron", 3), ("Icosahedron", 4)],
    ("platonic", "Type"): [("Tetra", 0), ("Hexa", 1), ("Octa", 2), ("Dodeca", 3), ("Icosa", 4), ("Bucky", 5)],
    ("landscape", "Noise Type"): [("fBM", 0), ("Multifractal", 1), ("Hybrid Multifractal", 2), ("Ridged Multifractal", 3), ("Hetero Terrain", 4)],
}
NOISE_TYPES = ("FBM", "MULTIFRACTAL", "HYBRID_MULTIFRACTAL", "RIDGED_MULTIFRACTAL", "HETERO_TERRAIN")
GROUP_VERSIONS = {"landscape": 2, "cube": 3, "pyramid": 2, "oiltank": 2}    # raised when a generator's nodes change meaning
AXES = [("+X", 0), ("-X", 1), ("+Y", 2), ("-Y", 3), ("+Z", 4), ("-Z", 5)]      # Orientation
for _k in ("cylinder", "plane", "disc", "cone", "torus", "pyramid", "tube", "oiltank", "capsule", "landscape", "relief"):
    CYCLES[(_k, "Orientation")] = AXES


def _group_name(kind):
    return f"Blenda {PRIMS[kind][1]}"


def _math(nodes, op, a, b=None, links=None):
    n = nodes.new("ShaderNodeMath")
    n.operation = op
    if hasattr(a, "is_output"):
        links.new(a, n.inputs[0])
    else:
        n.inputs[0].default_value = a
    if b is not None:
        if hasattr(b, "is_output"):
            links.new(b, n.inputs[1])
        else:
            n.inputs[1].default_value = b
    return n.outputs[0]


def _cm(nodes, links, sock):
    """cm socket -> metres."""
    return _math(nodes, "MULTIPLY", sock, SCALE, links)


def _segs(nodes, links, sock, offset=1):
    return _math(nodes, "ADD", sock, offset, links)


def _fillet_cube(nodes, links, o, size):
    """A rounded box with a clean grid. A cube of cells, seg + 2 * sub per axis, has its lines moved so seg cells cover the
    flat part and sub cells each fillet band, at even angles; the corners then bend out to the radius."""
    def m(op, a, b=None):
        return _math(nodes, op, a, b, links)

    def clamp01(v):
        return m("MINIMUM", m("MAXIMUM", v, 0.0), 1.0)

    sub = m("MAXIMUM", o["Fillet Subdivision"], 1.0)
    dim = nodes.new("ShaderNodeSeparateXYZ")
    links.new(size.outputs[0], dim.inputs[0])
    half = {k: m("MULTIPLY", dim.outputs[k], 0.5) for k in "XYZ"}
    r = m("MINIMUM", m("MINIMUM", _cm(nodes, links, o["Fillet Radius"]), half["X"]), m("MINIMUM", half["Y"], half["Z"]))
    segs = {"X": o["Segments X"], "Y": o["Segments Z"], "Z": o["Segments Y"]}          # shown Y is Blender Z
    cube = nodes.new("GeometryNodeMeshCube")
    cube.inputs["Size"].default_value = (2.0, 2.0, 2.0)
    for k in "XYZ":
        cells = m("ADD", segs[k], m("MULTIPLY", sub, 2.0))
        links.new(m("ADD", cells, 1.0), cube.inputs["Vertices " + k])
    pos = nodes.new("ShaderNodeSeparateXYZ")
    links.new(nodes.new("GeometryNodeInputPosition").outputs[0], pos.inputs[0])
    placed, inner = {}, {}
    quarter = 0.78539816
    for k in "XYZ":
        cells = m("ADD", segs[k], m("MULTIPLY", sub, 2.0))
        i = m("MULTIPLY", m("MULTIPLY", m("ADD", pos.outputs[k], 1.0), 0.5), cells)
        inner[k] = m("MAXIMUM", m("SUBTRACT", half[k], r), 0.0)
        lower = m("SUBTRACT", 1.0, clamp01(m("DIVIDE", i, sub)))
        upper = clamp01(m("DIVIDE", m("SUBTRACT", i, m("ADD", sub, segs[k])), sub))
        flat = clamp01(m("DIVIDE", m("SUBTRACT", i, sub), m("MAXIMUM", segs[k], 1.0)))
        x = m("SUBTRACT", m("MULTIPLY", m("MULTIPLY", inner[k], 2.0), flat), inner[k])
        x = m("SUBTRACT", x, m("MULTIPLY", r, m("TANGENT", m("MULTIPLY", lower, quarter))))
        placed[k] = m("ADD", x, m("MULTIPLY", r, m("TANGENT", m("MULTIPLY", upper, quarter))))
    core, off = {}, {}
    for k in "XYZ":
        core[k] = m("MINIMUM", m("MAXIMUM", placed[k], m("MULTIPLY", inner[k], -1.0)), inner[k])
        off[k] = m("SUBTRACT", placed[k], core[k])
    length = m("SQRT", m("ADD", m("ADD", m("MULTIPLY", off["X"], off["X"]), m("MULTIPLY", off["Y"], off["Y"])), m("MULTIPLY", off["Z"], off["Z"])))
    grow = m("DIVIDE", r, m("MAXIMUM", length, 1e-6))
    final = nodes.new("ShaderNodeCombineXYZ")
    for k in "XYZ":
        links.new(m("ADD", core[k], m("MULTIPLY", off[k], grow)), final.inputs[k])
    setp = nodes.new("GeometryNodeSetPosition")
    links.new(cube.outputs["Mesh"], setp.inputs["Geometry"])
    links.new(final.outputs[0], setp.inputs["Position"])
    return setp.outputs["Geometry"]


def ensure_group(kind):
    name = _group_name(kind)
    tree = bpy.data.node_groups.get(name)
    if tree is not None:
        return tree
    _, label, inputs = PRIMS[kind]
    tree = bpy.data.node_groups.new(name, "GeometryNodeTree")
    tree.is_modifier = True
    tree.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    menu_ids = {}
    for sname, stype, default, _pid in inputs:
        cyc = CYCLES.get((kind, sname))
        if cyc is not None:
            s = tree.interface.new_socket(sname, in_out="INPUT", socket_type="NodeSocketMenu")
            menu_ids[sname] = cyc
            continue
        s = tree.interface.new_socket(sname, in_out="INPUT", socket_type=SOCKET[stype])
        if default is not None:
            s.default_value = default
        if stype == "INT":
            s.min_value = 1
            s.max_value = 1000
        elif stype in ("FLOAT", "VECTOR") and not sname.endswith(("Furrows", "Scale", "Level", "Type", "From", "To")):
            s.min_value = 0.0                # interface sockets carry no length unit: the AM row adds "cm"
            s.max_value = 100000.0           # a finite range: Blender draws the slider widget only with one
        if stype == "FLOAT" and "Radius" in sname and "Fillet" in sname:
            s.max_value = 100.0              # slider range for the fillet radius
        if sname == "Seed":
            s.min_value, s.max_value = -(2 ** 31), 2 ** 31 - 1
        elif sname == "Distortion":
            s.min_value, s.max_value = -1000.0, 1000.0
    nodes, links = tree.nodes, tree.links
    gin = nodes.new("NodeGroupInput")
    gout = nodes.new("NodeGroupOutput")
    o = dict((sock.name, sock) for sock in gin.outputs)
    for sname, cyc in menu_ids.items():
        ms = nodes.new("GeometryNodeMenuSwitch")
        ms.data_type = "INT"
        ms.enum_items.clear()
        for label, cid in cyc:
            ms.enum_items.new(label)
        links.new(gin.outputs[sname], ms.inputs["Menu"])
        for label, cid in cyc:
            ms.inputs[label].default_value = cid
        o[sname] = ms.outputs[0]                      # downstream code sees the menu's number
        default_label = next((l for l, c in cyc if c == dict(((n, d) for n, t, d, i in inputs))[sname]), cyc[0][0])
        tree.interface.items_tree[sname].default_value = default_label
    if kind == "cube":
        n = nodes.new("GeometryNodeMeshCube")
        sep = nodes.new("ShaderNodeSeparateXYZ")
        links.new(o["Size"], sep.inputs[0])
        comb = nodes.new("ShaderNodeCombineXYZ")
        links.new(_cm(nodes, links, sep.outputs["X"]), comb.inputs["X"])
        links.new(_cm(nodes, links, sep.outputs["Z"]), comb.inputs["Y"])  # depth (shown Z) -> Blender Y
        links.new(_cm(nodes, links, sep.outputs["Y"]), comb.inputs["Z"])  # height (shown Y) -> Blender Z
        links.new(comb.outputs[0], n.inputs["Size"])
        links.new(_segs(nodes, links, o["Segments X"]), n.inputs["Vertices X"])
        links.new(_segs(nodes, links, o["Segments Y"]), n.inputs["Vertices Z"])  # shown Y is Blender Z
        links.new(_segs(nodes, links, o["Segments Z"]), n.inputs["Vertices Y"])
        out = n.outputs["Mesh"]
        # Fillet: the even grid stays on the flat faces, with Fillet Subdivision rows around every edge
        sw = nodes.new("GeometryNodeSwitch")
        sw.input_type = "GEOMETRY"
        links.new(o["Fillet"], sw.inputs["Switch"])
        links.new(out, sw.inputs["False"])
        links.new(_fillet_cube(nodes, links, o, comb), sw.inputs["True"])
        out = sw.outputs[0]
        # Separate Surfaces: split the mesh's edges so every face is its own island
        split = nodes.new("GeometryNodeSplitEdges")
        links.new(out, split.inputs["Mesh"])
        sw2 = nodes.new("GeometryNodeSwitch")
        sw2.input_type = "GEOMETRY"
        links.new(o["Separate Surfaces"], sw2.inputs["Switch"])
        links.new(out, sw2.inputs["False"])
        links.new(split.outputs["Mesh"], sw2.inputs["True"])
        out = sw2.outputs[0]
    elif kind == "sphere":
        # Type numbers: 0 Standard, 5 Hemisphere, 1 Tetra, 2 Hexa, 3 Octa, 4 Icosa
        r = _cm(nodes, links, o["Radius"])
        uv = nodes.new("GeometryNodeMeshUVSphere")
        links.new(r, uv.inputs["Radius"])
        links.new(o["Segments"], uv.inputs["Segments"])
        links.new(_math(nodes, "DIVIDE", o["Segments"], 2.0, links), uv.inputs["Rings"])
        # Polyhedron types: a subdivided tetra/hexa/octa/icosahedron whose points are pushed out to the radius;
        # Hexahedron shows the cube's quad grid, the others triangles.
        # Segments -> subdivision level: 32 segments = 4 levels (16 quads per cube edge).
        lvl = _math(nodes, "ROUND", _math(nodes, "LOGARITHM", _math(nodes, "MAXIMUM", _math(nodes, "DIVIDE", o["Segments"], 2.0, links), 1, links), 2.0, links), None, links)
        lvl = _math(nodes, "MINIMUM", lvl, 6, links)

        def cone(verts, fill):
            c = nodes.new("GeometryNodeMeshCone"); c.fill_type = fill
            c.inputs["Vertices"].default_value = verts
            c.inputs["Radius Top"].default_value = 0.0
            c.inputs["Radius Bottom"].default_value = 1.0
            c.inputs["Depth"].default_value = 1.0
            return c.outputs["Mesh"]

        def xform(g, translate=(0, 0, 0), scale=(1, 1, 1)):
            t = nodes.new("GeometryNodeTransform")
            links.new(g, t.inputs["Geometry"])
            t.inputs["Translation"].default_value = translate
            t.inputs["Scale"].default_value = scale
            return t.outputs["Geometry"]

        def on_sphere(g):
            """Subdivide the base solid, then push every point onto the sphere of radius r."""
            sub = nodes.new("GeometryNodeSubdivideMesh")
            links.new(g, sub.inputs["Mesh"]); links.new(lvl, sub.inputs["Level"])
            p = nodes.new("GeometryNodeInputPosition")
            nrm = nodes.new("ShaderNodeVectorMath"); nrm.operation = "NORMALIZE"; links.new(p.outputs[0], nrm.inputs[0])
            sc = nodes.new("ShaderNodeVectorMath"); sc.operation = "SCALE"
            links.new(nrm.outputs[0], sc.inputs[0]); links.new(r, sc.inputs["Scale"])
            sp = nodes.new("GeometryNodeSetPosition")
            links.new(sub.outputs["Mesh"], sp.inputs["Geometry"]); links.new(sc.outputs[0], sp.inputs["Position"])
            return sp.outputs["Geometry"]

        def tri_sphere(base):
            """Every triangular face of `base` becomes a lattice of n*n triangles (n = 2^level), the way
            The tetra/octahedron spheres are subdivided, then the points go onto the sphere."""
            n = _math(nodes, "POWER", 2.0, lvl, links)
            grid = nodes.new("GeometryNodeMeshGrid")
            grid.inputs["Size X"].default_value = 1.0; grid.inputs["Size Y"].default_value = 1.0
            nv = _math(nodes, "ADD", n, 1, links)
            links.new(nv, grid.inputs["Vertices X"]); links.new(nv, grid.inputs["Vertices Y"])
            g = xform(grid.outputs["Mesh"], translate=(0.5, 0.5, 0))          # u, v in 0..1
            tri = nodes.new("GeometryNodeTriangulate"); tri.inputs["Quad Method"].default_value = "Fixed Alternate"
            links.new(g, tri.inputs["Mesh"])
            gp = nodes.new("GeometryNodeInputPosition"); gs = nodes.new("ShaderNodeSeparateXYZ"); links.new(gp.outputs[0], gs.inputs[0])
            outside = _math(nodes, "GREATER_THAN", _math(nodes, "ADD", gs.outputs["X"], gs.outputs["Y"], links), 1.001, links)
            cut = nodes.new("GeometryNodeDeleteGeometry"); cut.domain = "POINT"
            links.new(tri.outputs["Mesh"], cut.inputs["Geometry"]); links.new(outside, cut.inputs["Selection"])
            # keep (u, v) as an attribute: instancing moves the lattice to each face centre
            uvs = nodes.new("GeometryNodeStoreNamedAttribute"); uvs.data_type = "FLOAT_VECTOR"; uvs.domain = "POINT"
            uvs.inputs["Name"].default_value = "b4d_uv"
            up = nodes.new("GeometryNodeInputPosition")
            links.new(cut.outputs["Geometry"], uvs.inputs["Geometry"]); links.new(up.outputs[0], uvs.inputs["Value"])
            lattice = uvs.outputs["Geometry"]
            # per face of the base: its three corner positions A, B, C as face attributes
            geo = base
            idx = nodes.new("GeometryNodeInputIndex")
            for k, nm in enumerate(("A", "B", "C")):
                cof = nodes.new("GeometryNodeCornersOfFace")
                links.new(idx.outputs[0], cof.inputs["Face Index"]); cof.inputs["Sort Index"].default_value = k
                voc = nodes.new("GeometryNodeVertexOfCorner"); links.new(cof.outputs["Corner Index"], voc.inputs["Corner Index"])
                smp = nodes.new("GeometryNodeSampleIndex"); smp.data_type = "FLOAT_VECTOR"; smp.domain = "POINT"
                links.new(base, smp.inputs["Geometry"]); vp = nodes.new("GeometryNodeInputPosition")
                links.new(vp.outputs[0], smp.inputs["Value"]); links.new(voc.outputs["Vertex Index"], smp.inputs["Index"])
                st = nodes.new("GeometryNodeStoreNamedAttribute"); st.data_type = "FLOAT_VECTOR"; st.domain = "FACE"
                st.inputs["Name"].default_value = "b4d_" + nm
                links.new(geo, st.inputs["Geometry"]); links.new(smp.outputs[0], st.inputs["Value"])
                geo = st.outputs["Geometry"]
            pts = nodes.new("GeometryNodeMeshToPoints"); pts.mode = "FACES"; links.new(geo, pts.inputs["Mesh"])
            inst = nodes.new("GeometryNodeInstanceOnPoints")
            links.new(pts.outputs["Points"], inst.inputs["Points"]); links.new(lattice, inst.inputs["Instance"])
            real = nodes.new("GeometryNodeRealizeInstances"); links.new(inst.outputs["Instances"], real.inputs["Geometry"])
            # P = A + u (B - A) + v (C - A)
            ruv = nodes.new("GeometryNodeInputNamedAttribute"); ruv.data_type = "FLOAT_VECTOR"; ruv.inputs["Name"].default_value = "b4d_uv"
            rs = nodes.new("ShaderNodeSeparateXYZ"); links.new(ruv.outputs["Attribute"], rs.inputs[0])
            att = {}
            for nm in ("A", "B", "C"):
                na = nodes.new("GeometryNodeInputNamedAttribute"); na.data_type = "FLOAT_VECTOR"; na.inputs["Name"].default_value = "b4d_" + nm
                att[nm] = na.outputs["Attribute"]
            def vsub(x, y):
                v = nodes.new("ShaderNodeVectorMath"); v.operation = "SUBTRACT"; links.new(x, v.inputs[0]); links.new(y, v.inputs[1]); return v.outputs[0]
            def vscale(x, f):
                v = nodes.new("ShaderNodeVectorMath"); v.operation = "SCALE"; links.new(x, v.inputs[0]); links.new(f, v.inputs["Scale"]); return v.outputs[0]
            def vadd(x, y):
                v = nodes.new("ShaderNodeVectorMath"); v.operation = "ADD"; links.new(x, v.inputs[0]); links.new(y, v.inputs[1]); return v.outputs[0]
            P = vadd(att["A"], vadd(vscale(vsub(att["B"], att["A"]), rs.outputs["X"]), vscale(vsub(att["C"], att["A"]), rs.outputs["Y"])))
            setp = nodes.new("GeometryNodeSetPosition"); links.new(real.outputs["Geometry"], setp.inputs["Geometry"]); links.new(P, setp.inputs["Position"])
            merge = nodes.new("GeometryNodeMergeByDistance"); links.new(setp.outputs["Geometry"], merge.inputs["Geometry"])
            merge.inputs["Distance"].default_value = 1e-4
            # outward normals, then the push onto the sphere
            nrm = nodes.new("GeometryNodeInputNormal"); fp = nodes.new("GeometryNodeInputPosition")
            dot = nodes.new("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"; links.new(nrm.outputs[0], dot.inputs[0]); links.new(fp.outputs[0], dot.inputs[1])
            inward = _math(nodes, "LESS_THAN", dot.outputs["Value"], 0.0, links)
            flip = nodes.new("GeometryNodeFlipFaces"); links.new(merge.outputs["Geometry"], flip.inputs["Mesh"]); links.new(inward, flip.inputs["Selection"])
            p2 = nodes.new("GeometryNodeInputPosition")
            un = nodes.new("ShaderNodeVectorMath"); un.operation = "NORMALIZE"; links.new(p2.outputs[0], un.inputs[0])
            sc = nodes.new("ShaderNodeVectorMath"); sc.operation = "SCALE"; links.new(un.outputs[0], sc.inputs[0]); links.new(r, sc.inputs["Scale"])
            sp = nodes.new("GeometryNodeSetPosition"); links.new(flip.outputs["Mesh"], sp.inputs["Geometry"]); links.new(sc.outputs[0], sp.inputs["Position"])
            return sp.outputs["Geometry"]

        # Mesh Cone: base at z = 0, apex at z = Depth
        tc = nodes.new("GeometryNodeMeshCone"); tc.fill_type = "NGON"
        tc.inputs["Vertices"].default_value = 3; tc.inputs["Radius Top"].default_value = 0.0
        tc.inputs["Radius Bottom"].default_value = 0.9428090; tc.inputs["Depth"].default_value = 4 / 3
        tetra = xform(tc.outputs["Mesh"], translate=(0, 0, -1 / 3))         # regular: apex (0,0,1), base at z = -1/3
        top = cone(4, "NONE")                                               # apex (0,0,1), square base at z = 0
        join = nodes.new("GeometryNodeJoinGeometry")
        links.new(xform(top, scale=(1, 1, -1)), join.inputs[0]); links.new(top, join.inputs[0])
        merge0 = nodes.new("GeometryNodeMergeByDistance"); links.new(join.outputs[0], merge0.inputs["Geometry"])
        octa = merge0.outputs["Geometry"]
        hexa_n = nodes.new("GeometryNodeMeshCube"); hexa_n.inputs["Size"].default_value = (2, 2, 2)
        ico = nodes.new("GeometryNodeMeshIcoSphere"); links.new(r, ico.inputs["Radius"])
        links.new(_math(nodes, "ADD", lvl, 1, links), ico.inputs["Subdivisions"])
        # hemisphere: delete the lower half of the UV sphere
        pos = nodes.new("GeometryNodeInputPosition"); sep = nodes.new("ShaderNodeSeparateXYZ"); links.new(pos.outputs[0], sep.inputs[0])
        below = _math(nodes, "LESS_THAN", sep.outputs["Z"], -0.0001, links)
        dele = nodes.new("GeometryNodeDeleteGeometry"); dele.domain = "FACE"
        links.new(uv.outputs["Mesh"], dele.inputs["Geometry"]); links.new(below, dele.inputs["Selection"])
        sw = nodes.new("GeometryNodeIndexSwitch"); sw.data_type = "GEOMETRY"
        while len(sw.index_switch_items) < 6:
            sw.index_switch_items.new()
        links.new(o["Type"], sw.inputs["Index"])
        links.new(uv.outputs["Mesh"], sw.inputs[1])          # 0 Standard
        links.new(tri_sphere(tetra), sw.inputs[2])           # 1 Tetrahedron
        links.new(on_sphere(hexa_n.outputs["Mesh"]), sw.inputs[3])   # 2 Hexahedron
        links.new(tri_sphere(octa), sw.inputs[4])            # 3 Octahedron
        links.new(ico.outputs["Mesh"], sw.inputs[5])         # 4 Icosahedron
        links.new(dele.outputs["Geometry"], sw.inputs[6])   # 5 Hemisphere
        out = sw.outputs[0]
    elif kind == "cylinder":
        n = nodes.new("GeometryNodeMeshCylinder")
        links.new(_cm(nodes, links, o["Radius"]), n.inputs["Radius"])
        links.new(_cm(nodes, links, o["Height"]), n.inputs["Depth"])
        links.new(o["Rotation Segments"], n.inputs["Vertices"])
        links.new(o["Height Segments"], n.inputs["Side Segments"])
        n2 = nodes.new("GeometryNodeMeshCylinder"); n2.fill_type = "NONE"
        for src, dst in (("Radius", "Radius"), ("Height", "Depth")):
            links.new(_cm(nodes, links, o[src]), n2.inputs[dst])
        links.new(o["Rotation Segments"], n2.inputs["Vertices"]); links.new(o["Height Segments"], n2.inputs["Side Segments"])
        sw = nodes.new("GeometryNodeSwitch"); sw.input_type = "GEOMETRY"
        links.new(o["Caps"], sw.inputs["Switch"]); links.new(n2.outputs["Mesh"], sw.inputs["False"]); links.new(n.outputs["Mesh"], sw.inputs["True"])
        out = _rim_fillet(nodes, links, sw.outputs[0], o["Fillet"], o["Fillet Radius"], o["Fillet Segments"])
    elif kind == "cyc":
        out = _cyc(nodes, links, o)
    elif kind == "plane":
        n = nodes.new("GeometryNodeMeshGrid")
        links.new(_cm(nodes, links, o["Width"]), n.inputs["Size X"])
        links.new(_cm(nodes, links, o["Height"]), n.inputs["Size Y"])
        links.new(_segs(nodes, links, o["Width Segments"]), n.inputs["Vertices X"])
        links.new(_segs(nodes, links, o["Height Segments"]), n.inputs["Vertices Y"])
        out = n.outputs["Mesh"]
    elif kind == "disc":
        # Inner Radius > 0 makes a ring, Disc Segments = radial subdivision -> a polar grid
        out = _polar_grid(nodes, links, _cm(nodes, links, o["Inner Radius"]), _cm(nodes, links, o["Outer Radius"]),
                          o["Disc Segments"], o["Rotation Segments"])
    elif kind == "cone":
        n = nodes.new("GeometryNodeMeshCone")
        links.new(_cm(nodes, links, o["Top Radius"]), n.inputs["Radius Top"])
        links.new(_cm(nodes, links, o["Bottom Radius"]), n.inputs["Radius Bottom"])
        links.new(_cm(nodes, links, o["Height"]), n.inputs["Depth"])
        links.new(o["Height Segments"], n.inputs["Side Segments"])
        links.new(o["Rotation Segments"], n.inputs["Vertices"])
        # Blender's cone sits on z=0; ours is centred on its axis
        t = nodes.new("GeometryNodeTransform")
        links.new(n.outputs["Mesh"], t.inputs["Geometry"])
        half = _math(nodes, "MULTIPLY", _cm(nodes, links, o["Height"]), -0.5, links)
        comb = nodes.new("ShaderNodeCombineXYZ")
        links.new(half, comb.inputs["Z"])
        links.new(comb.outputs[0], t.inputs["Translation"])
        out = t.outputs["Geometry"]
        # Caps off: drop the two cap faces (the faces whose normal runs along the axis)
        nrm = nodes.new("GeometryNodeInputNormal"); sep = nodes.new("ShaderNodeSeparateXYZ"); links.new(nrm.outputs[0], sep.inputs[0])
        is_cap = _math(nodes, "GREATER_THAN", _math(nodes, "ABSOLUTE", sep.outputs["Z"], None, links), 0.999, links)
        de = nodes.new("GeometryNodeDeleteGeometry"); de.domain = "FACE"
        links.new(out, de.inputs["Geometry"]); links.new(is_cap, de.inputs["Selection"])
        sw = nodes.new("GeometryNodeSwitch"); sw.input_type = "GEOMETRY"
        links.new(o["Caps"], sw.inputs["Switch"]); links.new(de.outputs["Geometry"], sw.inputs["False"]); links.new(out, sw.inputs["True"])
        out = sw.outputs[0]
        # top / bottom fillets: bevel the rim at that end (radius = the fillet radius, height is drawn by the bevel width)
        pos = nodes.new("GeometryNodeInputPosition"); psep = nodes.new("ShaderNodeSeparateXYZ"); links.new(pos.outputs[0], psep.inputs[0])
        top_sel = _math(nodes, "GREATER_THAN", psep.outputs["Z"], 0.0, links)
        out = _rim_fillet(nodes, links, out, o["Top Fillet"], o["Top Fillet Size"], o["Fillet Segments"], top_sel)
        bot_sel = _math(nodes, "LESS_THAN", psep.outputs["Z"], 0.0, links)
        out = _rim_fillet(nodes, links, out, o["Bottom Fillet"], o["Bottom Fillet Size"], o["Fillet Segments"], bot_sel)
    elif kind == "torus":
        ring = nodes.new("GeometryNodeCurvePrimitiveCircle")
        pipe = nodes.new("GeometryNodeCurvePrimitiveCircle")
        links.new(_cm(nodes, links, o["Ring Radius"]), ring.inputs["Radius"])
        links.new(o["Ring Segments"], ring.inputs["Resolution"])
        links.new(_cm(nodes, links, o["Pipe Radius"]), pipe.inputs["Radius"])
        links.new(o["Pipe Segments"], pipe.inputs["Resolution"])
        c2m = nodes.new("GeometryNodeCurveToMesh")
        c2m.inputs["Fill Caps"].default_value = False
        links.new(ring.outputs["Curve"], c2m.inputs["Curve"])
        links.new(pipe.outputs["Curve"], c2m.inputs["Profile Curve"])
        out = c2m.outputs["Mesh"]
    elif kind == "pyramid":
        n = nodes.new("GeometryNodeMeshCone")
        n.inputs["Vertices"].default_value = 4
        n.inputs["Radius Top"].default_value = 0.0
        n.inputs["Radius Bottom"].default_value = 0.70710678            # unit square base, corners on the circle
        n.inputs["Depth"].default_value = 1.0
        links.new(o["Segments"], n.inputs["Side Segments"])
        sep = nodes.new("ShaderNodeSeparateXYZ")
        links.new(o["Size"], sep.inputs[0])
        t = nodes.new("GeometryNodeTransform")
        links.new(n.outputs["Mesh"], t.inputs["Geometry"])
        t.inputs["Rotation"].default_value = (0.0, 0.0, 0.78539816)       # edges parallel to the axes
        comb = nodes.new("ShaderNodeCombineXYZ")
        links.new(_cm(nodes, links, sep.outputs["X"]), comb.inputs["X"])
        links.new(_cm(nodes, links, sep.outputs["Z"]), comb.inputs["Y"])  # depth (shown Z) -> Blender Y
        links.new(_cm(nodes, links, sep.outputs["Y"]), comb.inputs["Z"])  # height (shown Y) -> Blender Z
        # Blender's cone stands on z = 0; the pyramid is centred on its axis. Sized after the turn, so width stays width
        t2 = nodes.new("GeometryNodeTransform")
        links.new(t.outputs["Geometry"], t2.inputs["Geometry"])
        links.new(comb.outputs[0], t2.inputs["Scale"])
        c2 = nodes.new("ShaderNodeCombineXYZ")
        links.new(_math(nodes, "MULTIPLY", _cm(nodes, links, sep.outputs["Y"]), -0.5, links), c2.inputs["Z"])
        links.new(c2.outputs[0], t2.inputs["Translation"])
        out = t2.outputs["Geometry"]
    elif kind == "tube":
        # revolve: a closed rectangle profile (radial x height) swept around a near-zero circle
        q = nodes.new("GeometryNodeCurvePrimitiveQuadrilateral")
        q.mode = "RECTANGLE"
        width = _math(nodes, "SUBTRACT", _cm(nodes, links, o["Outer Radius"]), _cm(nodes, links, o["Inner Radius"]), links)
        links.new(width, q.inputs["Width"])
        links.new(_cm(nodes, links, o["Height"]), q.inputs["Height"])
        mid = _math(nodes, "MULTIPLY", _math(nodes, "ADD", _cm(nodes, links, o["Outer Radius"]), _cm(nodes, links, o["Inner Radius"]), links), 0.5, links)
        sub = nodes.new("GeometryNodeSubdivideCurve")
        links.new(q.outputs["Curve"], sub.inputs["Curve"])
        links.new(_math(nodes, "SUBTRACT", o["Height Segments"], 1, links), sub.inputs["Cuts"])
        out = _revolve(nodes, links, sub.outputs["Curve"], mid, o["Rotation Segments"])
        out = _rim_fillet(nodes, links, out, o["Fillet"], o["Fillet Radius"], o["Fillet Segments"])
    elif kind in ("oiltank", "capsule"):
        r = _cm(nodes, links, o["Radius"])
        h = _cm(nodes, links, o["Height"])
        cap = _cm(nodes, links, o["Cap Height"]) if kind == "oiltank" else r
        half = _math(nodes, "MULTIPLY", h, 0.5, links)
        body_half = _math(nodes, "MAXIMUM", _math(nodes, "SUBTRACT", half, cap, links), 0.0, links)   # the straight side runs -body_half .. body_half (a sphere when the radius reaches half the height)
        # right-hand silhouette: bottom cap arc, side line, top cap arc (each its own spline)
        # a slice of a sphere (curved caps): it meets the side at an angle and only
        # turns tangent as a hemisphere. Half angle formulas stay exact as the cap goes flat.
        sweep = _math(nodes, "MULTIPLY", _math(nodes, "ARCTANGENT", _math(nodes, "DIVIDE", _math(nodes, "MAXIMUM", cap, _math(nodes, "MULTIPLY", r, 0.001, links), links), r, links), None, links), 2.0, links)
        half_sweep = _math(nodes, "SINE", _math(nodes, "MULTIPLY", sweep, 0.5, links), None, links)

        def arc(top):
            line = nodes.new("GeometryNodeCurvePrimitiveLine")
            sub = nodes.new("GeometryNodeSubdivideCurve")
            links.new(line.outputs["Curve"], sub.inputs["Curve"])
            links.new(_math(nodes, "SUBTRACT", o["Cap Segments"], 1, links), sub.inputs["Cuts"])
            t = nodes.new("GeometryNodeSplineParameter").outputs["Factor"]
            ang = _math(nodes, "MULTIPLY", sweep, _math(nodes, "SUBTRACT", 1.0, t, links) if top else t, links)   # from the pole; the rim comes first on the top cap
            x = _math(nodes, "MULTIPLY", r, _math(nodes, "DIVIDE", _math(nodes, "SINE", ang, None, links), _math(nodes, "SINE", sweep, None, links), links), links)
            rise = _math(nodes, "DIVIDE", _math(nodes, "MULTIPLY", _math(nodes, "SINE", _math(nodes, "MULTIPLY", _math(nodes, "ADD", sweep, ang, links), 0.5, links), None, links), _math(nodes, "SINE", _math(nodes, "MULTIPLY", _math(nodes, "SUBTRACT", sweep, ang, links), 0.5, links), None, links), links), _math(nodes, "MULTIPLY", half_sweep, half_sweep, links), links)
            y = _math(nodes, "ADD", body_half, _math(nodes, "MULTIPLY", cap, rise, links), links)
            pos = nodes.new("ShaderNodeCombineXYZ")
            links.new(x, pos.inputs["X"]); links.new(y if top else _math(nodes, "MULTIPLY", y, -1.0, links), pos.inputs["Y"])
            sp = nodes.new("GeometryNodeSetPosition")
            links.new(sub.outputs["Curve"], sp.inputs["Geometry"]); links.new(pos.outputs[0], sp.inputs["Position"])
            return sp.outputs["Geometry"]
        line = nodes.new("GeometryNodeCurvePrimitiveLine")
        p0 = nodes.new("ShaderNodeCombineXYZ"); p1 = nodes.new("ShaderNodeCombineXYZ")
        links.new(r, p0.inputs["X"]); links.new(_math(nodes, "MULTIPLY", body_half, -1.0, links), p0.inputs["Y"])
        links.new(r, p1.inputs["X"]); links.new(body_half, p1.inputs["Y"])
        links.new(p0.outputs[0], line.inputs["Start"]); links.new(p1.outputs[0], line.inputs["End"])
        sub = nodes.new("GeometryNodeSubdivideCurve")
        links.new(line.outputs["Curve"], sub.inputs["Curve"])
        links.new(_math(nodes, "SUBTRACT", o["Height Segments"], 1, links), sub.inputs["Cuts"])
        join = nodes.new("GeometryNodeJoinGeometry")
        for g in (arc(False), sub.outputs["Curve"], arc(True)):
            links.new(g, join.inputs[0])
        out = _revolve(nodes, links, join.outputs[0], None, o["Rotation Segments"])
    elif kind == "platonic":
        out = _platonic(nodes, links, o)
    elif kind == "landscape":
        out = _landscape(nodes, links, o)
    elif kind == "relief":
        out = _relief(nodes, links, o)
    elif kind == "figure":
        out = _figure(nodes, links, o)
    elif kind == "bezier":
        n = nodes.new("GeometryNodeMeshGrid")
        n.inputs["Size X"].default_value = 4.0                       # 400 cm control net
        n.inputs["Size Y"].default_value = 4.0
        links.new(_segs(nodes, links, o["Subdivision X"]), n.inputs["Vertices X"])
        links.new(_segs(nodes, links, o["Subdivision Y"]), n.inputs["Vertices Y"])
        out = n.outputs["Mesh"]
    else:
        raise ValueError(kind)
    if "Slice" in o:
        out = _slice(nodes, links, out, o, kind)
    if "Orientation" in o:
        out = _orient(nodes, links, out, o["Orientation"])
    links.new(_uv(tree, _material(tree, _phong(tree, out))), gout.inputs["Geometry"])
    if kind in GROUP_VERSIONS:
        tree["kit_version"] = GROUP_VERSIONS[kind]
    return tree


@bpy.app.handlers.persistent
def upgrade_groups(_file=None):
    """Older files carry earlier node groups: move their objects onto the current ones, keeping the values."""
    for kind, version in GROUP_VERSIONS.items():
        _upgrade_group(kind, version)
    for kind in PRIMS:
        tree = bpy.data.node_groups.get(_group_name(kind))
        if tree is not None:
            ensure_uv(tree)


def _upgrade_group(kind, version):
    name = _group_name(kind)
    old = bpy.data.node_groups.get(name)
    if old is None or old.get("kit_version") == version:
        return
    old.name = name + " old"
    new = ensure_group(kind)
    for ob in bpy.data.objects:
        for mod in ob.modifiers:
            if mod.type != "NODES" or mod.node_group is not old:
                continue
            kept = {}
            for it in old.interface.items_tree:
                if it.item_type == "SOCKET" and it.in_out == "INPUT" and it.socket_type != "NodeSocketGeometry":
                    kept[it.name] = getattr(*input_slot(mod, it.name))
            mod.node_group = new
            for sname, value in kept.items():
                try:
                    socket = new.interface.items_tree[sname].socket_type
                    set_input(mod, sname, bool(value) if socket == "NodeSocketBool" else value)
                except (KeyError, TypeError, ValueError):
                    pass
    if old.users == 0:
        bpy.data.node_groups.remove(old)


def _cyc(nodes, links, o):
    """Cyc Wall (cyc_desc.py): one grid whose rows follow the profile - floor, quarter-circle Curve, wall - so the bend
    is seamless. Blender axes: width X, depth Y (shown Z), height Z (shown Y); the floor's front edge at -Length/2."""
    def m(op, a, b=None):
        return _math(nodes, op, a, b, links)
    fs, cs, ws = (m("MAXIMUM", o[k], 1.0) for k in ("Floor Segments", "Curve Segments", "Wall Segments"))
    rows = m("ADD", m("ADD", fs, cs), ws)                                         # row count - 1
    W, H, L = _cm(nodes, links, o["Width"]), _cm(nodes, links, o["Height"]), _cm(nodes, links, o["Length"])
    R = m("MINIMUM", _cm(nodes, links, o["Curve"]), m("MINIMUM", H, L))           # the curve fits inside the floor and wall
    grid = nodes.new("GeometryNodeMeshGrid")
    links.new(W, grid.inputs["Size X"]); grid.inputs["Size Y"].default_value = 1.0
    links.new(_segs(nodes, links, o["Width Segments"]), grid.inputs["Vertices X"])
    links.new(m("ADD", rows, 1.0), grid.inputs["Vertices Y"])
    pos = nodes.new("GeometryNodeInputPosition").outputs[0]
    sep = nodes.new("ShaderNodeSeparateXYZ"); links.new(pos, sep.inputs[0])
    r = m("ROUND", m("MULTIPLY", m("ADD", sep.outputs["Y"], 0.5), rows))        # this vertex's profile row
    front, back = m("MULTIPLY", L, -0.5), m("MULTIPLY", L, 0.5)
    # floor: front edge to the start of the curve
    y_floor = m("ADD", front, m("MULTIPLY", m("DIVIDE", r, fs), m("SUBTRACT", L, R)))
    # curve: a quarter circle about (back - R, R)
    a = m("MULTIPLY", m("DIVIDE", m("SUBTRACT", r, fs), cs), 1.5707963267948966)
    y_arc = m("ADD", m("SUBTRACT", back, R), m("MULTIPLY", R, m("SINE", a)))
    z_arc = m("SUBTRACT", R, m("MULTIPLY", R, m("COSINE", a)))
    # wall: top of the curve to Height
    z_wall = m("ADD", R, m("MULTIPLY", m("DIVIDE", m("SUBTRACT", r, m("ADD", fs, cs)), ws), m("SUBTRACT", H, R)))

    def pick(cond, yes, no):
        sw = nodes.new("GeometryNodeSwitch"); sw.input_type = "FLOAT"
        links.new(cond, sw.inputs["Switch"])
        for key, v in (("True", yes), ("False", no)):
            if hasattr(v, "is_output"):
                links.new(v, sw.inputs[key])
            else:
                sw.inputs[key].default_value = v
        return sw.outputs[0]
    on_floor = m("LESS_THAN", r, m("ADD", fs, 0.5))
    on_wall = m("GREATER_THAN", r, m("ADD", m("ADD", fs, cs), 0.5))
    y = pick(on_floor, y_floor, pick(on_wall, back, y_arc))
    z = pick(on_floor, 0.0, pick(on_wall, z_wall, z_arc))
    xyz = nodes.new("ShaderNodeCombineXYZ")
    links.new(sep.outputs["X"], xyz.inputs["X"]); links.new(y, xyz.inputs["Y"]); links.new(z, xyz.inputs["Z"])
    sp = nodes.new("GeometryNodeSetPosition"); links.new(grid.outputs["Mesh"], sp.inputs["Geometry"]); links.new(xyz.outputs[0], sp.inputs["Position"])
    return sp.outputs["Geometry"]


def _polar_grid(nodes, links, r_in, r_out, radial_segs, rot_segs):
    """Disc / ring as a polar grid: (rot_segs + 1) x (radial_segs + 1) vertices, seam and centre merged."""
    g = nodes.new("GeometryNodeMeshGrid")
    nx = _math(nodes, "ADD", rot_segs, 1, links); ny = _math(nodes, "ADD", radial_segs, 1, links)
    links.new(nx, g.inputs["Vertices X"]); links.new(ny, g.inputs["Vertices Y"])
    idx = nodes.new("GeometryNodeInputIndex").outputs[0]
    i = _math(nodes, "FLOOR", _math(nodes, "DIVIDE", idx, ny, links), None, links)       # Grid index = x * NY + y
    j = _math(nodes, "FLOORED_MODULO", idx, ny, links)
    ang = _math(nodes, "MULTIPLY", _math(nodes, "DIVIDE", i, rot_segs, links), 6.283185307, links)
    rad = _math(nodes, "ADD", r_in, _math(nodes, "MULTIPLY", _math(nodes, "SUBTRACT", r_out, r_in, links), _math(nodes, "DIVIDE", j, radial_segs, links), links), links)
    comb = nodes.new("ShaderNodeCombineXYZ")
    links.new(_math(nodes, "MULTIPLY", rad, _math(nodes, "COSINE", ang, None, links), links), comb.inputs["X"])
    links.new(_math(nodes, "MULTIPLY", rad, _math(nodes, "SINE", ang, None, links), links), comb.inputs["Y"])
    sp = nodes.new("GeometryNodeSetPosition"); links.new(g.outputs["Mesh"], sp.inputs["Geometry"]); links.new(comb.outputs[0], sp.inputs["Position"])
    m = nodes.new("GeometryNodeMergeByDistance"); links.new(sp.outputs["Geometry"], m.inputs["Geometry"]); m.inputs["Distance"].default_value = 1e-5
    return m.outputs["Geometry"]


def _rim_fillet(nodes, links, geo, flag, radius_cm, segments, extra_sel=None):
    """Round the sharp rims (edges whose face angle is above 45 deg) with a bevel while `flag` is on."""
    if not hasattr(bpy.types, "GeometryNodeMeshBevel"):
        return geo
    bev = nodes.new("GeometryNodeMeshBevel")
    links.new(geo, bev.inputs["Mesh"])
    ea = nodes.new("GeometryNodeInputMeshEdgeAngle")
    sel = _math(nodes, "GREATER_THAN", ea.outputs["Unsigned Angle"], 0.785, links)
    if extra_sel is not None:
        sel = _math(nodes, "MULTIPLY", sel, extra_sel, links)
    if "Selection" in bev.inputs:
        links.new(_math(nodes, "GREATER_THAN", sel, 0.5, links), bev.inputs["Selection"])
    links.new(_cm(nodes, links, radius_cm), bev.inputs["Width"] if "Width" in bev.inputs else bev.inputs[1])
    if "Segments" in bev.inputs:
        links.new(_math(nodes, "MINIMUM", segments, 50, links), bev.inputs["Segments"])
    sw = nodes.new("GeometryNodeSwitch"); sw.input_type = "GEOMETRY"
    links.new(flag, sw.inputs["Switch"]); links.new(geo, sw.inputs["False"]); links.new(bev.outputs[0], sw.inputs["True"])
    return sw.outputs[0]


def _slice_solid(nodes, links, geo, o):
    """Closed solids: intersect with a pie wedge from From to To, so both cuts get real flat cap faces."""
    bb = nodes.new("GeometryNodeBoundBox"); links.new(geo, bb.inputs["Geometry"])
    diff = nodes.new("ShaderNodeVectorMath"); diff.operation = "SUBTRACT"
    links.new(bb.outputs["Max"], diff.inputs[0]); links.new(bb.outputs["Min"], diff.inputs[1])
    ln = nodes.new("ShaderNodeVectorMath"); ln.operation = "LENGTH"; links.new(diff.outputs[0], ln.inputs[0])
    big = _math(nodes, "ADD", _math(nodes, "MULTIPLY", ln.outputs["Value"], 2.0, links), 1.0, links)
    span = _math(nodes, "FLOORED_MODULO", _math(nodes, "SUBTRACT", o["To"], o["From"], links), 360.0, links)
    arc = nodes.new("GeometryNodeCurveArc"); arc.mode = "RADIUS"
    arc.inputs["Resolution"].default_value = 32
    links.new(big, arc.inputs["Radius"])
    links.new(_math(nodes, "RADIANS", o["From"], None, links), arc.inputs["Start Angle"])
    links.new(_math(nodes, "RADIANS", span, None, links), arc.inputs["Sweep Angle"])
    arc.inputs["Connect Center"].default_value = True
    fill = nodes.new("GeometryNodeFillCurve"); fill.inputs["Mode"].default_value = "N-gons"
    links.new(arc.outputs["Curve"], fill.inputs["Curve"])
    up = nodes.new("ShaderNodeCombineXYZ"); links.new(_math(nodes, "MULTIPLY", big, 2.0, links), up.inputs["Z"])
    ex = nodes.new("GeometryNodeExtrudeMesh"); ex.mode = "FACES"; ex.inputs["Individual"].default_value = False
    links.new(fill.outputs["Mesh"], ex.inputs["Mesh"]); links.new(up.outputs[0], ex.inputs["Offset"])
    flip = nodes.new("GeometryNodeFlipFaces"); links.new(fill.outputs["Mesh"], flip.inputs["Mesh"])
    jn = nodes.new("GeometryNodeJoinGeometry"); links.new(ex.outputs["Mesh"], jn.inputs[0]); links.new(flip.outputs["Mesh"], jn.inputs[0])
    mg = nodes.new("GeometryNodeMergeByDistance"); links.new(jn.outputs[0], mg.inputs["Geometry"]); mg.inputs["Distance"].default_value = 1e-5
    dn = nodes.new("ShaderNodeCombineXYZ"); links.new(_math(nodes, "MULTIPLY", big, -1.0, links), dn.inputs["Z"])
    tr = nodes.new("GeometryNodeTransform"); links.new(mg.outputs["Geometry"], tr.inputs["Geometry"]); links.new(dn.outputs[0], tr.inputs["Translation"])
    b = nodes.new("GeometryNodeMeshBoolean"); b.operation = "INTERSECT"; b.solver = "EXACT"
    links.new(geo, b.inputs[1]); links.new(tr.outputs["Geometry"], b.inputs[1])   # inputs[1] is the multi-input "Mesh"
    cut = _slice_faces(nodes, links, b.outputs["Mesh"], o)
    full = _math(nodes, "LESS_THAN", span, 0.001, links)
    sw = nodes.new("GeometryNodeSwitch"); sw.input_type = "GEOMETRY"
    links.new(_math(nodes, "GREATER_THAN", full, 0.5, links), sw.inputs["Switch"]); links.new(cut, sw.inputs["False"]); links.new(geo, sw.inputs["True"])
    return sw.outputs[0]


def _slice_faces(nodes, links, solid, o):
    """The flat cut faces: long triangles normally (no new points), an even triangle grid of size Width with
    Regular Grid."""
    from . import gen_caps as gc
    planes = []
    for deg, sgn in ((o["From"], 1.0), (o["To"], -1.0)):
        ang = _math(nodes, "RADIANS", deg, None, links)
        c, s_ = _math(nodes, "COSINE", ang, None, links), _math(nodes, "SINE", ang, None, links)
        radial = gc.combine(nodes, links, c, s_)
        normal = gc.combine(nodes, links, _math(nodes, "MULTIPLY", s_, sgn, links), _math(nodes, "MULTIPLY", c, -sgn, links))
        planes.append((radial, normal))

    def on_plane(radial, normal):
        p = gc.position(nodes)
        close = _math(nodes, "LESS_THAN", _math(nodes, "ABSOLUTE", gc.dot(nodes, links, p, normal), None, links), 1e-4, links)
        return _math(nodes, "MULTIPLY", close, _math(nodes, "GREATER_THAN", gc.dot(nodes, links, p, radial), -1e-4, links), links)

    nrm = nodes.new("GeometryNodeInputNormal").outputs[0]
    flats = []
    for radial, normal in planes:
        facing = _math(nodes, "GREATER_THAN", _math(nodes, "ABSOLUTE", gc.dot(nodes, links, nrm, normal), None, links), 0.999, links)
        close = _math(nodes, "LESS_THAN", _math(nodes, "ABSOLUTE", gc.dot(nodes, links, gc.position(nodes), normal), None, links), 1e-4, links)
        flats.append(_math(nodes, "MULTIPLY", facing, close, links))
    is_cut = _math(nodes, "GREATER_THAN", _math(nodes, "ADD", flats[0], flats[1], links), 0.5, links)
    tri = nodes.new("GeometryNodeTriangulate"); links.new(solid, tri.inputs["Mesh"]); links.new(is_cut, tri.inputs["Selection"])
    de = nodes.new("GeometryNodeDeleteGeometry"); de.domain = "FACE"; de.mode = "ONLY_FACE"
    links.new(solid, de.inputs["Geometry"]); links.new(is_cut, de.inputs["Selection"])
    shell = de.outputs["Geometry"]
    fc = nodes.new("GeometryNodeInputMeshEdgeNeighbors").outputs["Face Count"]
    width = _cm(nodes, links, o["Width"])
    parts = [shell]
    for radial, normal in planes:
        sel = _math(nodes, "MULTIPLY", _math(nodes, "LESS_THAN", fc, 1.5, links), on_plane(radial, normal), links)
        m2c = nodes.new("GeometryNodeMeshToCurve"); links.new(shell, m2c.inputs["Mesh"])
        links.new(_math(nodes, "GREATER_THAN", sel, 0.5, links), m2c.inputs["Selection"])
        cyc = nodes.new("GeometryNodeSetSplineCyclic"); links.new(m2c.outputs["Curve"], cyc.inputs["Curve"]); cyc.inputs["Cyclic"].default_value = True
        R, Rinv = gc.align_z(nodes, links, normal)
        flat = gc.move(nodes, links, cyc.outputs["Curve"], rotation=Rinv)
        parts.append(gc.move(nodes, links, gc.grid_fill(nodes, links, flat, width), rotation=R))
    grid = gc.merge(nodes, links, gc.join(nodes, links, parts), 1e-4)
    return gc.switch(nodes, links, "GEOMETRY", o["Regular Grid"], tri.outputs["Mesh"], grid)


def _slice(nodes, links, geo, o, kind=None):
    """Slice settings: keep the wedge between From and To (angles around the object's axis;
    measured in the shown XZ plane = Blender XY). The cut faces are not filled yet."""
    pos = nodes.new("GeometryNodeInputPosition"); sep = nodes.new("ShaderNodeSeparateXYZ"); links.new(pos.outputs[0], sep.inputs[0])
    ang = _math(nodes, "DEGREES", _math(nodes, "ARCTAN2", sep.outputs["Y"], sep.outputs["X"], links), None, links)
    ang = _math(nodes, "FLOORED_MODULO", ang, 360.0, links)
    a0 = _math(nodes, "FLOORED_MODULO", o["From"], 360.0, links); a1 = _math(nodes, "FLOORED_MODULO", o["To"], 360.0, links)
    # inside when a0 <= ang <= a1 (or the wrapped range when a0 > a1)
    rel = _math(nodes, "FLOORED_MODULO", _math(nodes, "SUBTRACT", ang, a0, links), 360.0, links)
    span = _math(nodes, "FLOORED_MODULO", _math(nodes, "SUBTRACT", a1, a0, links), 360.0, links)
    full = _math(nodes, "LESS_THAN", _math(nodes, "ABSOLUTE", _math(nodes, "SUBTRACT", o["To"], o["From"], links), None, links), 0.001, links)
    outside = _math(nodes, "GREATER_THAN", rel, span, links)
    outside = _math(nodes, "MULTIPLY", outside, _math(nodes, "SUBTRACT", 1.0, full, links), links)
    de = nodes.new("GeometryNodeDeleteGeometry"); de.domain = "FACE"
    links.new(geo, de.inputs["Geometry"]); links.new(_math(nodes, "GREATER_THAN", outside, 0.5, links), de.inputs["Selection"])
    sw = nodes.new("GeometryNodeSwitch"); sw.input_type = "GEOMETRY"
    cut = de.outputs["Geometry"]
    if kind in ("capsule", "oiltank", "tube", "torus", "cone", "cylinder"):
        solid = _slice_solid(nodes, links, geo, o)
        if "Caps" in o:                                  # an uncapped cylinder / cone is an open shell: keep the plain cut
            pick = nodes.new("GeometryNodeSwitch"); pick.input_type = "GEOMETRY"
            links.new(o["Caps"], pick.inputs["Switch"]); links.new(cut, pick.inputs["False"]); links.new(solid, pick.inputs["True"])
            cut = pick.outputs[0]
        else:
            cut = solid
    links.new(o["Slice"], sw.inputs["Switch"]); links.new(geo, sw.inputs["False"]); links.new(cut, sw.inputs["True"])
    return sw.outputs[0]


def _orient(nodes, links, geo, axis_id):
    """Orientation: the object points along +X / -X / +Y / -Y / +Z / -Z (shown axes; +Y = Blender +Z = built as is)."""
    import math
    sw = nodes.new("GeometryNodeIndexSwitch"); sw.data_type = "VECTOR"
    while len(sw.index_switch_items) < 6:
        sw.index_switch_items.new()
    links.new(axis_id, sw.inputs["Index"])
    h = math.pi / 2
    for k, e in ((1, (0, h, 0)), (2, (0, -h, 0)), (3, (0, 0, 0)), (4, (math.pi, 0, 0)), (5, (-h, 0, 0)), (6, (h, 0, 0))):
        sw.inputs[k].default_value = e
    t = nodes.new("GeometryNodeTransform"); links.new(geo, t.inputs["Geometry"]); links.new(sw.outputs[0], t.inputs["Rotation"])
    return t.outputs["Geometry"]


def _revolve(nodes, links, profile, radial_offset, segments):
    """Revolve a profile drawn in the XY plane (X = radial distance, Y = height) around the Y axis:
    the profile is swept along a tiny circle whose resolution is the rotation segment count."""
    circle = nodes.new("GeometryNodeCurvePrimitiveCircle")
    circle.mode = "RADIUS"
    circle.inputs["Radius"].default_value = 0.00001
    links.new(segments, circle.inputs["Resolution"])
    # Curve to Mesh places the profile's X along the curve normal and its Y along the binormal (Z up);
    # the circle lies in XY so the profile needs X -> radial (binormal) and Y -> up: swap by rotating the profile
    t = nodes.new("GeometryNodeTransform")
    links.new(profile, t.inputs["Geometry"])
    if radial_offset is not None:
        tr = nodes.new("ShaderNodeCombineXYZ")
        links.new(radial_offset, tr.inputs["X"])
        links.new(tr.outputs[0], t.inputs["Translation"])
    # measured (Blender 5.2): the profile's X already lands on the radial direction and its Y on Z, no rotation needed
    c2m = nodes.new("GeometryNodeCurveToMesh")
    links.new(circle.outputs["Curve"], c2m.inputs["Curve"])
    links.new(t.outputs["Geometry"], c2m.inputs["Profile Curve"])
    # one connected surface: weld the profile pieces (capsule / oil tank bands) and close the pole rings,
    # otherwise a Subdivision Surface above the primitive creases at every seam
    merge = nodes.new("GeometryNodeMergeByDistance")
    links.new(c2m.outputs["Mesh"], merge.inputs["Geometry"])
    merge.inputs["Distance"].default_value = 1e-4
    return merge.outputs["Geometry"]


def _platonic(nodes, links, o):
    r = _cm(nodes, links, o["Radius"])
    sw = nodes.new("GeometryNodeIndexSwitch")
    sw.data_type = "GEOMETRY"
    while len(sw.index_switch_items) < 6:
        sw.index_switch_items.new()
    links.new(o["Type"], sw.inputs["Index"])

    def cube(size_factor):
        c = nodes.new("GeometryNodeMeshCube")
        s = nodes.new("ShaderNodeCombineXYZ")
        v = _math(nodes, "MULTIPLY", r, size_factor, links)
        for k in ("X", "Y", "Z"):
            links.new(v, s.inputs[k])
        links.new(s.outputs[0], c.inputs["Size"])
        return c.outputs["Mesh"]

    def ico(scale):
        i = nodes.new("GeometryNodeMeshIcoSphere")
        i.inputs["Subdivisions"].default_value = 1
        links.new(_math(nodes, "MULTIPLY", r, scale, links), i.inputs["Radius"])
        return i.outputs["Mesh"]

    def hull(g):
        h = nodes.new("GeometryNodeConvexHull")
        links.new(g, h.inputs["Geometry"])
        return h.outputs["Convex Hull"]

    def face_points(g):
        p = nodes.new("GeometryNodeMeshToPoints")
        p.mode = "FACES"
        links.new(g, p.inputs["Mesh"])
        return p.outputs["Points"]

    # tetra: four alternate corners of the cube (x*y*z > 0), hull
    cb = cube(1.1547005)                                  # cube edge 2r/sqrt(3): corners on the sphere of radius r
    pos = nodes.new("GeometryNodeInputPosition")
    sep = nodes.new("ShaderNodeSeparateXYZ"); links.new(pos.outputs[0], sep.inputs[0])
    prod = _math(nodes, "MULTIPLY", _math(nodes, "MULTIPLY", sep.outputs["X"], sep.outputs["Y"], links), sep.outputs["Z"], links)
    neg = _math(nodes, "LESS_THAN", prod, 0.0, links)
    dele = nodes.new("GeometryNodeDeleteGeometry"); dele.domain = "POINT"
    links.new(cb, dele.inputs["Geometry"]); links.new(neg, dele.inputs["Selection"])
    links.new(hull(dele.outputs["Geometry"]), sw.inputs[1])     # item 0 = Tetra
    links.new(cube(1.1547005), sw.inputs[2])                     # Hexa
    links.new(hull(face_points(cube(2.0))), sw.inputs[3])        # Octa: face centres of a cube of half-size r
    links.new(hull(face_points(ico(1.2584))), sw.inputs[4])      # Dodeca: face centres of an icosahedron (1/0.7947)
    links.new(ico(1.0), sw.inputs[5])                            # Icosa
    # Bucky: hull of the points at 1/3 and 2/3 of every icosahedron edge (truncated icosahedron)
    base = ico(1.1514)                                           # 1/0.8685 keeps the vertices on the sphere of radius r
    ev = nodes.new("GeometryNodeInputMeshEdgeVertices")
    join = nodes.new("GeometryNodeJoinGeometry")
    for a, b in ((2.0, 1.0), (1.0, 2.0)):
        vm = nodes.new("ShaderNodeVectorMath"); vm.operation = "SCALE"
        links.new(ev.outputs["Position 1"], vm.inputs[0]); vm.inputs["Scale"].default_value = a / 3.0
        vm2 = nodes.new("ShaderNodeVectorMath"); vm2.operation = "SCALE"
        links.new(ev.outputs["Position 2"], vm2.inputs[0]); vm2.inputs["Scale"].default_value = b / 3.0
        add = nodes.new("ShaderNodeVectorMath"); add.operation = "ADD"
        links.new(vm.outputs[0], add.inputs[0]); links.new(vm2.outputs[0], add.inputs[1])
        p = nodes.new("GeometryNodeMeshToPoints"); p.mode = "EDGES"
        links.new(base, p.inputs["Mesh"]); links.new(add.outputs[0], p.inputs["Position"])
        links.new(p.outputs["Points"], join.inputs[0])
    links.new(hull(join.outputs[0]), sw.inputs[6])
    # Segments: subdivide every face (N x N per face; here the nearest power of two)
    lvl = _math(nodes, "ROUND", _math(nodes, "LOGARITHM", _math(nodes, "MAXIMUM", o["Segments"], 1, links), 2.0, links), None, links)
    sd = nodes.new("GeometryNodeSubdivideMesh")
    links.new(sw.outputs[0], sd.inputs["Mesh"]); links.new(lvl, sd.inputs["Level"])
    return sd.outputs["Mesh"]


def _relief(nodes, links, o):
    """Size X and Z the grid, Size Y the height; the image's brightness lifts each point. Bottom Level
    floods from below (100 % leaves a plane), Top Level truncates from above (0 % leaves a plane), and like the Landscape
    the rest is lifted again to the full height. The origin sits at the lowest point. Spherical: a globe of radius
    Size X / 2 with the relief on top, the image wrapped once around it."""
    sep = nodes.new("ShaderNodeSeparateXYZ"); links.new(o["Size"], sep.inputs[0])
    sx, sy, sz = (_cm(nodes, links, sep.outputs[k]) for k in "XYZ")
    g = nodes.new("GeometryNodeMeshGrid")
    links.new(sx, g.inputs["Size X"]); links.new(sz, g.inputs["Size Y"])
    links.new(_segs(nodes, links, o["Width Segments"]), g.inputs["Vertices X"])
    links.new(_segs(nodes, links, o["Depth Segments"]), g.inputs["Vertices Y"])
    pos = nodes.new("ShaderNodeSeparateXYZ"); links.new(nodes.new("GeometryNodeInputPosition").outputs[0], pos.inputs[0])
    u = _math(nodes, "DIVIDE", pos.outputs["X"], _math(nodes, "MAXIMUM", sx, 0.001, links), links)      # -0.5 .. 0.5
    v = _math(nodes, "DIVIDE", pos.outputs["Y"], _math(nodes, "MAXIMUM", sz, 0.001, links), links)
    uv = nodes.new("ShaderNodeCombineXYZ")
    links.new(_math(nodes, "ADD", u, 0.5, links), uv.inputs["X"]); links.new(_math(nodes, "ADD", v, 0.5, links), uv.inputs["Y"])
    tex = nodes.new("GeometryNodeImageTexture"); tex.extension = "EXTEND"
    links.new(o["Image"], tex.inputs["Image"]); links.new(uv.outputs[0], tex.inputs["Vector"])
    gray = nodes.new("ShaderNodeVectorMath"); gray.operation = "DOT_PRODUCT"      # brightness, the weights of Blender's RGB to BW
    links.new(tex.outputs["Color"], gray.inputs[0]); gray.inputs[1].default_value = (0.2126, 0.7152, 0.0722)
    lo = _math(nodes, "DIVIDE", o["Bottom Level"], 100.0, links)
    hi = _math(nodes, "DIVIDE", o["Top Level"], 100.0, links)
    clamp = nodes.new("ShaderNodeClamp")
    links.new(gray.outputs["Value"], clamp.inputs["Value"]); links.new(lo, clamp.inputs["Min"]); links.new(hi, clamp.inputs["Max"])
    span = _math(nodes, "MAXIMUM", _math(nodes, "SUBTRACT", hi, lo, links), 0.0001, links)
    height = _math(nodes, "MULTIPLY", _math(nodes, "DIVIDE", _math(nodes, "SUBTRACT", clamp.outputs[0], lo, links), span, links), sy, links)
    off = nodes.new("ShaderNodeCombineXYZ"); links.new(height, off.inputs["Z"])
    sp = nodes.new("GeometryNodeSetPosition")
    links.new(g.outputs["Mesh"], sp.inputs["Geometry"]); links.new(off.outputs[0], sp.inputs["Offset"])
    lon = _math(nodes, "MULTIPLY", u, 6.283185307, links)
    lat = _math(nodes, "MULTIPLY", v, 3.141592654, links)
    ring = _math(nodes, "COSINE", lat, None, links)
    ball = nodes.new("ShaderNodeCombineXYZ")
    links.new(_math(nodes, "MULTIPLY", ring, _math(nodes, "COSINE", lon, None, links), links), ball.inputs["X"])
    links.new(_math(nodes, "MULTIPLY", ring, _math(nodes, "SINE", lon, None, links), links), ball.inputs["Y"])
    links.new(_math(nodes, "SINE", lat, None, links), ball.inputs["Z"])
    vm = nodes.new("ShaderNodeVectorMath"); vm.operation = "SCALE"
    links.new(ball.outputs[0], vm.inputs[0])
    links.new(_math(nodes, "ADD", _math(nodes, "MULTIPLY", sx, 0.5, links), height, links), vm.inputs["Scale"])
    globe = nodes.new("GeometryNodeSetPosition")
    links.new(g.outputs["Mesh"], globe.inputs["Geometry"]); links.new(vm.outputs[0], globe.inputs["Position"])
    weld = nodes.new("GeometryNodeMergeByDistance"); links.new(globe.outputs["Geometry"], weld.inputs["Geometry"])
    weld.inputs["Distance"].default_value = 0.0001
    shape = nodes.new("GeometryNodeSwitch"); shape.input_type = "GEOMETRY"
    links.new(o["Spherical"], shape.inputs["Switch"])
    links.new(sp.outputs["Geometry"], shape.inputs["False"]); links.new(weld.outputs["Geometry"], shape.inputs["True"])
    return shape.outputs[0]


def _relief_file(ob, context):
    """Relief Texture: the chosen file loads once and feeds the Image input."""
    mod = next((m for m in ob.modifiers if m.type == "NODES" and m.node_group), None)
    if mod is None:
        return
    path = bpy.path.abspath(ob.b4d_relief_file)
    img = None
    if path:
        # the pixel values as stored (mid-grey = half height), in a copy of its own so a material on the same file keeps its colours
        img = next((i for i in bpy.data.images if i.get("b4d_relief") and bpy.path.abspath(i.filepath) == path), None)
        if img is None:
            try:
                img = bpy.data.images.load(path, check_existing=False)
                img.colorspace_settings.name = "Non-Color"
                img["b4d_relief"] = True
            except RuntimeError:
                img = None
    set_input(mod, "Image", img)
    ob.update_tag()


def _landscape(nodes, links, o):
    """Size: X and Z the grid, Y the height of the terrain. Rough and Fine Furrows set coarse and fine ridges, Scale how
    deep the valleys run. Sea and Plateau Level cut the terrain from below and above and the rest is stretched back to
    full height (100 % Sea or 0 % Plateau leave a plane). Flatten Edges lowers the edge. Spherical wraps it
    around a globe of radius Size X / 2."""
    sep = nodes.new("ShaderNodeSeparateXYZ"); links.new(o["Size"], sep.inputs[0])
    sx, sy, sz = (_cm(nodes, links, sep.outputs[k]) for k in "XYZ")
    g = nodes.new("GeometryNodeMeshGrid")
    links.new(sx, g.inputs["Size X"])
    links.new(sz, g.inputs["Size Y"])
    links.new(_segs(nodes, links, o["Width Segments"]), g.inputs["Vertices X"])
    links.new(_segs(nodes, links, o["Depth Segments"]), g.inputs["Vertices Y"])
    wide = _math(nodes, "MAXIMUM", sx, 0.001, links)
    deep = _math(nodes, "MAXIMUM", sz, 0.001, links)
    pos = nodes.new("ShaderNodeSeparateXYZ"); links.new(nodes.new("GeometryNodeInputPosition").outputs[0], pos.inputs[0])
    u = _math(nodes, "DIVIDE", pos.outputs["X"], wide, links)                   # -0.5 .. 0.5 across the grid
    v = _math(nodes, "DIVIDE", pos.outputs["Y"], deep, links)
    # the pattern is sampled on the flat grid, or on the globe so that its seam does not show
    flat = nodes.new("ShaderNodeCombineXYZ")
    links.new(_math(nodes, "MULTIPLY", u, 2.0, links), flat.inputs["X"])
    links.new(_math(nodes, "MULTIPLY", _math(nodes, "DIVIDE", pos.outputs["Y"], wide, links), 2.0, links), flat.inputs["Y"])
    lon = _math(nodes, "MULTIPLY", u, 6.283185307, links)
    lat = _math(nodes, "MULTIPLY", v, 3.141592654, links)
    ring = _math(nodes, "COSINE", lat, None, links)
    ball = nodes.new("ShaderNodeCombineXYZ")
    links.new(_math(nodes, "MULTIPLY", ring, _math(nodes, "COSINE", lon, None, links), links), ball.inputs["X"])
    links.new(_math(nodes, "MULTIPLY", ring, _math(nodes, "SINE", lon, None, links), links), ball.inputs["Y"])
    links.new(_math(nodes, "SINE", lat, None, links), ball.inputs["Z"])
    where = nodes.new("GeometryNodeSwitch"); where.input_type = "VECTOR"
    links.new(o["Spherical"], where.inputs["Switch"])
    links.new(flat.outputs[0], where.inputs["False"]); links.new(ball.outputs[0], where.inputs["True"])
    detail = _math(nodes, "MULTIPLY", o["Fine Furrows"], 8.0, links)

    def noise(kind):
        n = nodes.new("ShaderNodeTexNoise")
        n.noise_dimensions = "4D"; n.normalize = True; n.noise_type = kind
        links.new(where.outputs[0], n.inputs["Vector"])
        links.new(o["Seed"], n.inputs["W"])
        links.new(o["Noise Scale"], n.inputs["Scale"])
        links.new(detail, n.inputs["Detail"])
        links.new(o["Rough Furrows"], n.inputs["Roughness"])
        links.new(o["Lacunarity"], n.inputs["Lacunarity"])
        links.new(o["Distortion"], n.inputs["Distortion"])
        for name in ("Offset", "Gain"):           # only the types that use them have these sockets
            if name in n.inputs:
                links.new(o[name], n.inputs[name])
        return n.outputs["Fac"]

    pick = nodes.new("GeometryNodeIndexSwitch"); pick.data_type = "FLOAT"
    while len(pick.index_switch_items) < len(NOISE_TYPES):
        pick.index_switch_items.new()
    links.new(o["Noise Type"], pick.inputs["Index"])
    outs = [noise(k) for k in NOISE_TYPES]
    for i, out in enumerate(outs):
        links.new(out, pick.inputs[i + 1])
    algo = nodes.new("GeometryNodeSwitch"); algo.input_type = "FLOAT"           # Multifractal off: "a different algorithm"
    links.new(o["Multifractal"], algo.inputs["Switch"])
    links.new(outs[0], algo.inputs["False"]); links.new(pick.outputs[0], algo.inputs["True"])
    # the full range of this surface fills 0..1, so Size Y is the real height
    stat = nodes.new("GeometryNodeAttributeStatistic"); stat.data_type = "FLOAT"; stat.domain = "POINT"
    links.new(g.outputs["Mesh"], stat.inputs["Geometry"]); links.new(algo.outputs[0], stat.inputs["Attribute"])
    fit = nodes.new("ShaderNodeMapRange")
    links.new(algo.outputs[0], fit.inputs["Value"])
    links.new(stat.outputs["Min"], fit.inputs["From Min"]); links.new(stat.outputs["Max"], fit.inputs["From Max"])
    shaped = _math(nodes, "POWER", fit.outputs[0], o["Scale"], links)
    clamp = nodes.new("ShaderNodeClamp")
    links.new(shaped, clamp.inputs["Value"])
    links.new(o["Sea Level"], clamp.inputs["Min"]); links.new(o["Plateau Level"], clamp.inputs["Max"])
    span = _math(nodes, "MAXIMUM", _math(nodes, "SUBTRACT", o["Plateau Level"], o["Sea Level"], links), 0.0001, links)
    lifted = _math(nodes, "DIVIDE", _math(nodes, "SUBTRACT", clamp.outputs[0], o["Sea Level"], links), span, links)
    edge = _math(nodes, "MINIMUM", _math(nodes, "SUBTRACT", 0.5, _math(nodes, "ABSOLUTE", u, None, links), links),
                 _math(nodes, "SUBTRACT", 0.5, _math(nodes, "ABSOLUTE", v, None, links), links), links)
    fade = nodes.new("ShaderNodeMapRange"); fade.interpolation_type = "SMOOTHSTEP"
    links.new(edge, fade.inputs["Value"])
    fade.inputs["From Min"].default_value = 0.0; fade.inputs["From Max"].default_value = 0.1
    border = nodes.new("GeometryNodeSwitch"); border.input_type = "FLOAT"
    links.new(o["Flatten Edges"], border.inputs["Switch"])
    links.new(lifted, border.inputs["False"])
    links.new(_math(nodes, "MULTIPLY", lifted, fade.outputs[0], links), border.inputs["True"])
    height = _math(nodes, "MULTIPLY", border.outputs[0], sy, links)
    off = nodes.new("ShaderNodeCombineXYZ"); links.new(height, off.inputs["Z"])
    sp = nodes.new("GeometryNodeSetPosition")
    links.new(g.outputs["Mesh"], sp.inputs["Geometry"]); links.new(off.outputs[0], sp.inputs["Offset"])
    # Spherical: the globe, its seam and poles merged shut
    vm = nodes.new("ShaderNodeVectorMath"); vm.operation = "SCALE"
    links.new(ball.outputs[0], vm.inputs[0])
    links.new(_math(nodes, "ADD", _math(nodes, "MULTIPLY", sx, 0.5, links), height, links), vm.inputs["Scale"])
    globe = nodes.new("GeometryNodeSetPosition")
    links.new(g.outputs["Mesh"], globe.inputs["Geometry"]); links.new(vm.outputs[0], globe.inputs["Position"])
    weld = nodes.new("GeometryNodeMergeByDistance"); links.new(globe.outputs["Geometry"], weld.inputs["Geometry"])
    weld.inputs["Distance"].default_value = 0.0001
    shape = nodes.new("GeometryNodeSwitch"); shape.input_type = "GEOMETRY"
    links.new(o["Spherical"], shape.inputs["Switch"])
    links.new(sp.outputs["Geometry"], shape.inputs["False"]); links.new(weld.outputs["Geometry"], shape.inputs["True"])
    return shape.outputs[0]


# the Figure: a box mannequin (part, size, centre) in fractions of its height, feet on the ground (y = 0)
FIGURE_PARTS = (
    ("head", (0.14, 0.12, 0.15), (0.0, 0.93, 0.0)), ("neck", (0.06, 0.04, 0.06), (0.0, 0.855, 0.0)),
    ("torso", (0.30, 0.22, 0.14), (0.0, 0.72, 0.0)), ("hips", (0.26, 0.10, 0.14), (0.0, 0.56, 0.0)),
    ("upper arm L", (0.07, 0.22, 0.07), (0.235, 0.71, 0.0)), ("upper arm R", (0.07, 0.22, 0.07), (-0.235, 0.71, 0.0)),
    ("lower arm L", (0.06, 0.20, 0.06), (0.235, 0.50, 0.0)), ("lower arm R", (0.06, 0.20, 0.06), (-0.235, 0.50, 0.0)),
    ("hand L", (0.05, 0.08, 0.03), (0.235, 0.36, 0.0)), ("hand R", (0.05, 0.08, 0.03), (-0.235, 0.36, 0.0)),
    ("upper leg L", (0.11, 0.24, 0.11), (0.075, 0.39, 0.0)), ("upper leg R", (0.11, 0.24, 0.11), (-0.075, 0.39, 0.0)),
    ("lower leg L", (0.09, 0.24, 0.09), (0.075, 0.15, 0.0)), ("lower leg R", (0.09, 0.24, 0.09), (-0.075, 0.15, 0.0)),
    ("foot L", (0.09, 0.03, 0.18), (0.075, 0.015, 0.045)), ("foot R", (0.09, 0.03, 0.18), (-0.075, 0.015, 0.045)),
)


def _figure(nodes, links, o):
    h = _cm(nodes, links, o["Height"])
    verts = _math(nodes, "ADD", _math(nodes, "DIVIDE", _math(nodes, "MAXIMUM", o["Segments"], 4, links), 4.0, links), 1, links)
    join = nodes.new("GeometryNodeJoinGeometry")
    for name, size, centre in FIGURE_PARTS:
        c = nodes.new("GeometryNodeMeshCube")
        c.label = name
        s = nodes.new("ShaderNodeCombineXYZ")
        links.new(_math(nodes, "MULTIPLY", h, size[0], links), s.inputs["X"])
        links.new(_math(nodes, "MULTIPLY", h, size[2], links), s.inputs["Y"])     # depth -> Blender Y
        links.new(_math(nodes, "MULTIPLY", h, size[1], links), s.inputs["Z"])     # height -> Blender Z
        links.new(s.outputs[0], c.inputs["Size"])
        for k in ("Vertices X", "Vertices Y", "Vertices Z"):
            links.new(verts, c.inputs[k])
        t = nodes.new("GeometryNodeTransform")
        links.new(c.outputs["Mesh"], t.inputs["Geometry"])
        tr = nodes.new("ShaderNodeCombineXYZ")
        links.new(_math(nodes, "MULTIPLY", h, centre[0], links), tr.inputs["X"])
        links.new(_math(nodes, "MULTIPLY", h, centre[2], links), tr.inputs["Y"])
        links.new(_math(nodes, "MULTIPLY", h, centre[1], links), tr.inputs["Z"])
        links.new(tr.outputs[0], t.inputs["Translation"])
        links.new(t.outputs["Geometry"], join.inputs[0])
    return join.outputs[0]


PHONG_ANGLE = "Phong Angle"
PHONG_LIMIT = "Angle Limit"


def _phong(tree, geometry):
    """Primitives carry Phong shading: smooth, with edges sharp above the angle limit."""
    import math
    nodes, links = tree.nodes, tree.links
    if PHONG_ANGLE not in tree.interface.items_tree:
        s = tree.interface.new_socket(PHONG_ANGLE, in_out="INPUT", socket_type="NodeSocketFloat")
        s.subtype = "ANGLE"
        s.default_value = math.radians(80.0)
        s.min_value = 0.0
        s.max_value = math.pi
    if PHONG_LIMIT not in tree.interface.items_tree:
        tree.interface.new_socket(PHONG_LIMIT, in_out="INPUT", socket_type="NodeSocketBool").default_value = True
    gin = next(n for n in nodes if n.bl_idname == "NodeGroupInput")
    smooth = nodes.new("GeometryNodeSetShadeSmooth")
    smooth.domain = "FACE"
    smooth.inputs["Shade Smooth"].default_value = True
    links.new(geometry, smooth.inputs["Geometry"])
    angle = nodes.new("GeometryNodeInputMeshEdgeAngle")
    cmp = nodes.new("FunctionNodeCompare")
    cmp.data_type = "FLOAT"
    cmp.operation = "LESS_THAN"
    links.new(angle.outputs["Unsigned Angle"], cmp.inputs[0])
    links.new(gin.outputs[PHONG_ANGLE], cmp.inputs[1])
    edges = nodes.new("GeometryNodeSetShadeSmooth")
    edges.domain = "EDGE"
    links.new(smooth.outputs["Geometry"], edges.inputs["Geometry"])
    # Angle Limit off: every edge smooth, the angle does not matter
    nt = nodes.new("FunctionNodeBooleanMath"); nt.operation = "NOT"
    links.new(gin.outputs[PHONG_LIMIT], nt.inputs[0])
    either = nodes.new("FunctionNodeBooleanMath"); either.operation = "OR"
    links.new(cmp.outputs["Result"], either.inputs[0]); links.new(nt.outputs[0], either.inputs[1])
    links.new(either.outputs[0], edges.inputs["Shade Smooth"])
    return edges.outputs["Geometry"]


MATERIAL_SOCKET = "Material"


USE_MATERIAL_SOCKET = "Use Material"


def _use_material(tree, sm):
    """Only a set material paints the output: an empty one would wipe what children bring (a Cloner's clones lost
    their material, found Nov 3 2026). With no material tag, the children's materials show."""
    if USE_MATERIAL_SOCKET not in tree.interface.items_tree:
        sock = tree.interface.new_socket(USE_MATERIAL_SOCKET, in_out="INPUT", socket_type="NodeSocketBool")
        sock.default_value = True                       # as before: a stage paints until told the slot is empty
        sock.hide_in_modifier = True
    gin = next(n for n in tree.nodes if n.bl_idname == "NodeGroupInput")
    tree.links.new(gin.outputs[USE_MATERIAL_SOCKET], sm.inputs["Selection"])


def _material(tree, geometry):
    """The texture tag: generated geometry takes the material of the group's Material input."""
    nodes, links = tree.nodes, tree.links
    if MATERIAL_SOCKET not in tree.interface.items_tree:
        tree.interface.new_socket(MATERIAL_SOCKET, in_out="INPUT", socket_type="NodeSocketMaterial")
    gin = next(n for n in nodes if n.bl_idname == "NodeGroupInput")
    sm = nodes.new("GeometryNodeSetMaterial")
    links.new(geometry, sm.inputs["Geometry"])
    links.new(gin.outputs[MATERIAL_SOCKET], sm.inputs["Material"])
    _use_material(tree, sm)
    return sm.outputs["Geometry"]


def _patch_use_material(tree):
    """Groups made before Use Material existed: link it to their material stage."""
    if USE_MATERIAL_SOCKET in tree.interface.items_tree:
        return False
    sms = [n for n in tree.nodes if n.type == "SET_MATERIAL" and n.inputs["Material"].is_linked
           and n.inputs["Material"].links[0].from_socket.name == MATERIAL_SOCKET]
    for sm in sms:
        _use_material(tree, sm)
    return bool(sms)


def ensure_material(tree):
    """Add the material stage to a primitive group made before it existed."""
    if MATERIAL_SOCKET in tree.interface.items_tree:
        return _patch_use_material(tree)
    gout = next(n for n in tree.nodes if n.bl_idname == "NodeGroupOutput")
    link = next((l for l in tree.links if l.to_node == gout), None)
    if link is None:
        return False
    src = link.from_socket
    tree.links.remove(link)
    tree.links.new(_material(tree, src), gout.inputs["Geometry"])
    return True


def set_material(ob, mat, index=0):
    """Assign a material: the object's slot (the texture tag in the Object Manager) and, for a
    primitive, the generator's Material input so the generated geometry carries it."""
    if ob is None or not hasattr(ob.data, "materials"):
        return False
    mats = ob.data.materials
    while len(mats) <= index:
        mats.append(None)
    if mats[index] != mat:
        mats[index] = mat
    if index == 0:
        material_output(ob, mat)
    return True


GENERATOR_MOD = "Blenda Generator"      # the modifier name generators.py gives its own node tree


def _own_mods(ob):
    """The modifiers whose node tree builds this object's own geometry: a primitive's generator or a generator object's
    tree. Deformer trees (which change another object's geometry) are never painted."""
    k = ob.get("b4d_type")
    for i, mod in enumerate(ob.modifiers):
        if mod.type != "NODES" or mod.node_group is None or not mod.node_group.name.startswith("Blenda "):
            continue
        if mod.name == GENERATOR_MOD or (k in PRIMS and i == 0):
            yield mod


def material_output(ob, mat):
    """The material a generator paints its whole output with."""
    for mod in _own_mods(ob):
        tree = mod.node_group
        if ensure_material(tree):
            mod.node_group = tree           # refresh the modifier's socket properties for the new input
        sock = tree.interface.items_tree.get(MATERIAL_SOCKET)
        if sock is None:
            continue
        try:
            owner, attr = input_slot(mod, sock.identifier)
        except KeyError:
            mod.node_group = tree
            owner, attr = input_slot(mod, sock.identifier)
        current = owner.value if attr == "value" else mod.get(sock.identifier)
        if current != mat:
            set_input(mod, sock.identifier, mat)
            ob.update_tag()                 # a value set through properties.inputs does not tag the object
        use = tree.interface.items_tree.get(USE_MATERIAL_SOCKET)
        if use is not None:
            try:
                set_input(mod, use.identifier, mat is not None)
            except KeyError:
                mod.node_group = tree
                set_input(mod, use.identifier, mat is not None)
            ob.update_tag()


def material_parts(ob, tags):
    """Material tags with a Selection on a generator: each paints only its part, later tags over earlier ones. A part is named by its code (C1 start cap, C2 end cap, R1 start bevel, R2 end bevel), by its
    Selections-tab name (Shell, Start Cap, End Cap, Start Bevel, End Bevel), or by any named face selection."""
    from . import gen_caps as gc
    mod = next((m for m in ob.modifiers if m.type == "NODES" and m.node_group and m.node_group.name.startswith("Blenda ")), None)
    if mod is None:
        return
    tree = mod.node_group
    nodes, links = tree.nodes, tree.links
    for n in [n for n in nodes if n.name.startswith("Blenda Part Material")]:
        nodes.remove(n)
    gout = next(n for n in nodes if n.bl_idname == "NodeGroupOutput")
    link = next((l for l in links if l.to_node == gout), None)
    if link is None:
        return
    src = link.from_socket
    done = False
    for k, (mat, sel) in enumerate(tags):
        if mat is None or not sel:
            continue
        code = gc.PART_CODES.get(sel.upper(), gc.PART_NAMES.get(sel))
        if code is not None:
            cmp = nodes.new("FunctionNodeCompare"); cmp.data_type = "INT"; cmp.operation = "EQUAL"; cmp.name = f"Blenda Part Material Cmp {k}"
            links.new(gc.part_field(nodes), cmp.inputs[0]); cmp.inputs[1].default_value = code
            field = cmp.outputs[0]
        else:
            na = nodes.new("GeometryNodeInputNamedAttribute"); na.data_type = "BOOLEAN"; na.inputs["Name"].default_value = sel
            na.name = f"Blenda Part Material Sel {k}"
            field = na.outputs["Attribute"]
        sm = nodes.new("GeometryNodeSetMaterial"); sm.name = f"Blenda Part Material {k}"
        links.new(src, sm.inputs["Geometry"]); links.new(field, sm.inputs["Selection"]); sm.inputs["Material"].default_value = mat
        src, done = sm.outputs["Geometry"], True
    if done:
        links.new(src, gout.inputs[link.to_socket.name])
    ob.update_tag()


def _uv(tree, geometry):
    """UVs the textures read: a box projection, each face seen along its main axis and scaled by the object's
    largest size, so one tile spans the object. Per-primitive layouts are not made yet."""
    nodes, links = tree.nodes, tree.links
    tree["kit_uv"] = UV_VERSION
    box = nodes.new("GeometryNodeBoundBox"); links.new(geometry, box.inputs["Geometry"])
    span = nodes.new("ShaderNodeVectorMath"); span.operation = "SUBTRACT"
    links.new(box.outputs["Max"], span.inputs[0]); links.new(box.outputs["Min"], span.inputs[1])
    sz = nodes.new("ShaderNodeSeparateXYZ"); links.new(span.outputs[0], sz.inputs[0])
    big = _math(nodes, "MAXIMUM", _math(nodes, "MAXIMUM", sz.outputs[0], sz.outputs[1], links), sz.outputs[2], links)
    big = _math(nodes, "MAXIMUM", big, 1e-6, links)
    centre = nodes.new("ShaderNodeVectorMath"); centre.operation = "MULTIPLY_ADD"
    links.new(span.outputs[0], centre.inputs[0]); centre.inputs[1].default_value = (0.5, 0.5, 0.5); links.new(box.outputs["Min"], centre.inputs[2])
    rel = nodes.new("ShaderNodeVectorMath"); rel.operation = "SUBTRACT"
    links.new(nodes.new("GeometryNodeInputPosition").outputs[0], rel.inputs[0]); links.new(centre.outputs[0], rel.inputs[1])
    p = nodes.new("ShaderNodeSeparateXYZ"); links.new(rel.outputs[0], p.inputs[0])
    nrm = nodes.new("GeometryNodeInputNormal")
    on_face = nodes.new("GeometryNodeFieldOnDomain"); on_face.domain = "FACE"; on_face.data_type = "FLOAT_VECTOR"
    links.new(nrm.outputs[0], on_face.inputs[0])
    n = nodes.new("ShaderNodeVectorMath"); n.operation = "ABSOLUTE"; links.new(on_face.outputs[0], n.inputs[0])
    ns = nodes.new("ShaderNodeSeparateXYZ"); links.new(_tie_break(tree, n.outputs[0]), ns.inputs[0])
    x_main = _math(nodes, "MULTIPLY", _math(nodes, "GREATER_THAN", ns.outputs[0], ns.outputs[1], links), _math(nodes, "GREATER_THAN", ns.outputs[0], ns.outputs[2], links), links)
    z_main = _math(nodes, "MULTIPLY", _math(nodes, "GREATER_THAN", ns.outputs[2], ns.outputs[0], links), _math(nodes, "GREATER_THAN", ns.outputs[2], ns.outputs[1], links), links)

    def pick(a, b, c):                        # x-facing: a, z-facing: c, otherwise: b
        return _math(nodes, "ADD", _math(nodes, "MULTIPLY", x_main, a, links),
                     _math(nodes, "MULTIPLY", _math(nodes, "SUBTRACT", 1.0, x_main, links),
                           _math(nodes, "ADD", _math(nodes, "MULTIPLY", z_main, c, links), _math(nodes, "MULTIPLY", _math(nodes, "SUBTRACT", 1.0, z_main, links), b, links), links), links), links)
    u = _math(nodes, "ADD", _math(nodes, "DIVIDE", pick(p.outputs[1], p.outputs[0], p.outputs[0]), big, links), 0.5, links)
    v = _math(nodes, "ADD", _math(nodes, "DIVIDE", pick(p.outputs[2], p.outputs[2], p.outputs[1]), big, links), 0.5, links)
    uv = nodes.new("ShaderNodeCombineXYZ"); links.new(u, uv.inputs[0]); links.new(v, uv.inputs[1])
    st = nodes.new("GeometryNodeStoreNamedAttribute"); st.data_type = "FLOAT2"; st.domain = "CORNER"
    st.inputs["Name"].default_value = "UVMap"
    links.new(geometry, st.inputs["Geometry"]); links.new(uv.outputs[0], st.inputs["Value"])
    return st.outputs["Geometry"]


UV_VERSION = 2
TIE = (0.0, 1e-4, 2e-4)        # a face facing two or three axes alike (a Tetra's) picks Z, then Y, the same on every triangle


def _tie_break(tree, axes):
    """Without it, rounding picks the axis per triangle and segmented faces turn into a patchwork."""
    add = tree.nodes.new("ShaderNodeVectorMath"); add.operation = "ADD"; add.label = "kit_uv_tie"
    add.inputs[1].default_value = TIE
    tree.links.new(axes, add.inputs[0])
    return add.outputs[0]


def _upgrade_uv(tree):
    """Version 1 had no tie break: put it between the normal's absolute value and the axis split."""
    tree["kit_uv"] = UV_VERSION
    if any(n.label == "kit_uv_tie" for n in tree.nodes):
        return True
    absn = next((n for n in tree.nodes if n.bl_idname == "ShaderNodeVectorMath" and n.operation == "ABSOLUTE"
                 and n.inputs[0].links and n.inputs[0].links[0].from_node.bl_idname == "GeometryNodeFieldOnDomain"), None)
    if absn is None:
        return False
    for link in list(absn.outputs[0].links):
        to = link.to_socket
        tree.links.remove(link)
        tree.links.new(_tie_break(tree, absn.outputs[0]), to)
    return True


def ensure_uv(tree):
    """Add the UV stage to a primitive group made before it existed, or bring an older one up to date."""
    if tree.get("kit_uv"):
        return tree["kit_uv"] < UV_VERSION and _upgrade_uv(tree)
    gout = next((n for n in tree.nodes if n.bl_idname == "NodeGroupOutput"), None)
    link = next((l for l in tree.links if l.to_node == gout), None) if gout else None
    if link is None:
        return False
    src = link.from_socket
    tree.links.remove(link)
    tree.links.new(_uv(tree, src), gout.inputs["Geometry"])
    return True


def ensure_phong(tree):
    """Add the Phong stage to a primitive group made before it existed."""
    if PHONG_ANGLE in tree.interface.items_tree:
        return False
    gout = next(n for n in tree.nodes if n.bl_idname == "NodeGroupOutput")
    link = next((l for l in tree.links if l.to_node == gout), None)
    if link is None:
        return False
    src = link.from_socket
    tree.links.remove(link)
    tree.links.new(_phong(tree, src), gout.inputs["Geometry"])
    return True


def tidy_name(ob):
    """Blender numbers duplicates 'Cube.001'; Blenda numbers them 'Cube.1'."""
    import re
    m = re.match(r"^(.*)\.(\d{3})$", ob.name)
    if m:
        base, n = m.group(1), int(m.group(2))
        want = f"{base}.{n}"
        if want not in bpy.data.objects:
            ob.name = want
    return ob.name


def add_primitive(context, kind, name=None, params=None, collection=None):
    """New object with the generator modifier; params = {row key: value}."""
    kind_name, label, inputs = PRIMS[kind]
    mesh = bpy.data.meshes.new(name or label)
    ob = bpy.data.objects.new(name or label, mesh)
    (collection or context.collection).objects.link(ob)
    ob["b4d_type"] = kind_name
    tidy_name(ob)
    tree = ensure_group(kind)
    mod = ob.modifiers.new(label, "NODES")
    mod.node_group = tree
    if params:
        set_params(ob, params)
    return ob


def input_slot(mod, ident):
    """(owner, attribute) of a modifier input: Blender 5.x keeps them in
    mod.properties.inputs.<ident>.value, 4.2-4.5 as the ID property mod[ident]."""
    props = getattr(mod, "properties", None)
    if props is not None and hasattr(props, "inputs"):
        slot = getattr(props.inputs, ident, None)
        if slot is None and mod.node_group is not None:
            # inputs are keyed by socket identifier (Socket_3); resolve a socket *name* to it
            for it in mod.node_group.interface.items_tree:
                if it.item_type == "SOCKET" and it.in_out == "INPUT" and it.name == ident:
                    slot = getattr(props.inputs, it.identifier, None)
                    break
        if slot is None:
            raise KeyError(f"modifier {mod.name!r} has no input {ident!r}")
        return slot, "value"
    return mod, f'["{ident}"]'


def cycle_id(kind, sname, value):
    """A menu setting's number from its label; anything else is already a number."""
    return dict(CYCLES.get((kind, sname), ())).get(value, value)


def cycle_label(kind, sname, value):
    """The menu label of a number; an unknown number keeps the menu as it is (None)."""
    return next((label for label, cid in CYCLES.get((kind, sname), ()) if cid == int(value)), None)


def set_input(mod, ident, value):
    owner, attr = input_slot(mod, ident)
    if attr == "value":
        owner.value = value
    else:
        mod[ident] = value


def set_params(ob, params):
    mod = next((m for m in ob.modifiers if m.type == "NODES" and m.node_group
                and m.node_group.name.startswith("Blenda ")), None)
    if mod is None:
        return
    kind = TYPE_TO_KIND.get(ob.get("b4d_type"))
    if kind is None:
        return
    by_key = {key: (sname, stype) for sname, stype, _d, key in PRIMS[kind][2]}
    for key, value in params.items():
        if key not in by_key:
            continue
        sname, stype = by_key[key]
        ident = mod.node_group.interface.items_tree[sname].identifier
        if (kind, sname) in CYCLES:
            label = cycle_label(kind, sname, value)
            if label is not None:
                set_input(mod, ident, label)
        elif stype == "VECTOR":
            set_input(mod, ident, tuple(float(v) for v in value))
        elif stype == "INT":
            set_input(mod, ident, int(value))
        elif stype == "BOOL":
            set_input(mod, ident, bool(value))
        else:
            set_input(mod, ident, float(value))


class BLENDA4D_OT_add_primitive(bpy.types.Operator):
    """Add a parametric primitive"""
    bl_idname = "blenda4d.add_primitive"
    bl_label = "Add Primitive"
    bl_options = {"REGISTER", "UNDO"}
    kind: bpy.props.EnumProperty(items=[(k, v[1], "") for k, v in PRIMS.items()], default="cube")

    def execute(self, context):
        ob = add_primitive(context, self.kind)
        ob.location = context.scene.cursor.location
        for o in context.view_layer.objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        return {"FINISHED"}




classes = (BLENDA4D_OT_add_primitive,)


def _sync_materials():
    """Keep each primitive's and generator's material input in step with its first material slot, however the slot
    was set: Blender's own material slots, a drop from the Asset Browser, another add-on (found Nov 19 2026: a
    material given outside set_material left the generated geometry without one, drawn white)."""
    try:
        for ob in bpy.data.objects:
            if not hasattr(ob.data, "materials") or not any(True for _ in _own_mods(ob)):
                continue
            mat = ob.material_slots[0].material if len(ob.material_slots) else None
            material_output(ob, mat)
    except (ReferenceError, RuntimeError, AttributeError, KeyError) as ex:
        print("Blenda 4D: material sync", ex)
    return 0.5


def register():
    if not bpy.app.timers.is_registered(_sync_materials):
        bpy.app.timers.register(_sync_materials, first_interval=0.5, persistent=True)
    bpy.app.handlers.load_post.append(upgrade_groups)
    bpy.app.timers.register(upgrade_groups, first_interval=0.5)      # a file named on the command line loads before the kit
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Object.b4d_relief_file = bpy.props.StringProperty(description='The picture whose brightness raises the surface (Blender: Displace texture image)', name="Texture", subtype="FILE_PATH", update=_relief_file)


def unregister():
    if bpy.app.timers.is_registered(_sync_materials):
        bpy.app.timers.unregister(_sync_materials)
    del bpy.types.Object.b4d_relief_file
    if upgrade_groups in bpy.app.handlers.load_post:      # opening a file drops handlers that are not persistent
        bpy.app.handlers.load_post.remove(upgrade_groups)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
