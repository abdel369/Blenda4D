# SPDX-License-Identifier: GPL-3.0-or-later
"""Auto Arrange: lays a node tree out so a person can read it.

Every wire runs left to right. Nodes sit in columns: each node one column left of the furthest node it feeds
(a layered layout), and within a column nodes are sorted by where their wires land, then packed with even gaps, so
wires cross as little as they can. A wire that would skip past a column goes through reroute points, one per column
it passes, so it runs straight instead of cutting across other nodes. Nodes are never renamed or collapsed.

Trees Blenda 4D builds (generators, primitives, deformers) wrap each stage of the build in a labelled frame
(`stage()` below). Those frames are laid out one after another from left to right, each frame's own nodes laid out
inside it, and every frame that reads the group's settings gets its own Group Input with only the sockets it uses,
so no long wires run across the whole tree.

The Node Editor's header has an Auto Arrange button for any tree, materials included."""
from contextlib import contextmanager

import bpy

GAP_X = 70          # between columns
GAP_Y = 24          # between nodes in a column
GAP_FRAME = 90      # between frames
HEADER = 36         # a node's header
SOCKET = 22         # the step between sockets
REROUTE_TAG = "b4d_reroute"


# --- frames for the stages of a build ----------------------------------------------------------------------------

@contextmanager
def stage(tree, label):
    """Every node created inside the block goes into one frame with this label."""
    before = {n.as_pointer() for n in tree.nodes}
    yield
    new = [n for n in tree.nodes if n.as_pointer() not in before and n.type != "FRAME" and n.parent is None
           and n.bl_idname not in ("NodeGroupInput", "NodeGroupOutput")]
    if not new:
        return
    frame = tree.nodes.new("NodeFrame")
    frame.label = label
    frame.label_size = 16
    frame.shrink = True
    for n in new:
        n.parent = frame


# --- sizes --------------------------------------------------------------------------------------------------------

def _size(n, scale):
    """A node's width and height in view units: Blender measures them when it draws the node; a tree that has not
    been drawn yet gets an estimate from its sockets."""
    if n.type == "REROUTE":
        return 16.0, 16.0
    w, h = n.dimensions
    if w > 0 and h > 0:
        return w / scale, h / scale
    ins = [s for s in n.inputs if s.enabled and not s.hide]
    outs = [s for s in n.outputs if s.enabled and not s.hide]
    rows = len(outs) + sum(4 if s.type == "VECTOR" and not s.hide_value and not s.is_linked else 1 for s in ins)
    props = len(n.bl_rna.properties) - len(bpy.types.Node.bl_rna.properties)
    extra = {"TEX_IMAGE": 150, "MAPPING": 30, "BSDF_PRINCIPLED": 120}.get(n.type, 26 if props > 2 else 0)
    return float(n.width), HEADER + rows * SOCKET + extra


def _sock_y(n, sock, is_output, h):
    """How far below the node's top a socket sits: outputs first under the header, inputs at the bottom."""
    if n.type == "REROUTE":
        return h / 2
    if is_output:
        outs = [s for s in n.outputs if s.enabled and not s.hide]
        i = outs.index(sock) if sock in outs else 0
        return HEADER + (i + 0.5) * SOCKET
    ins = [s for s in n.inputs if s.enabled and not s.hide]
    i = ins.index(sock) if sock in ins else len(ins) - 1
    return h - (len(ins) - i - 0.5) * SOCKET


def _isotonic(want, heights, gaps):
    """Tops for one column, in its order, as close to `want` as possible with each node below the last plus a gap
    (pool adjacent violators)."""
    off, acc = [], 0.0
    for i, h in enumerate(heights):
        off.append(acc)
        acc += h + gaps[i]
    blocks = []
    for v in (w - o for w, o in zip(want, off)):
        blocks.append([v, 1.0, 1])
        while len(blocks) > 1 and blocks[-2][0] > blocks[-1][0]:
            b = blocks.pop()
            a = blocks[-1]
            a[0] = (a[0] * a[1] + b[0] * b[1]) / (a[1] + b[1])
            a[1] += b[1]
            a[2] += b[2]
    out = []
    for mean, _w, count in blocks:
        out += [mean] * count
    return [v + o for v, o in zip(out, off)]


# --- the layered layout of one set of nodes ----------------------------------------------------------------------

def _edges(tree, members):
    return [(l.from_node, l.from_socket, l.to_node, l.to_socket) for l in tree.links
            if l.is_valid and not l.is_hidden and l.from_node in members and l.to_node in members
            and l.from_node != l.to_node]


def _columns(nodes, succ):
    col, busy = {}, set()

    def rank(n):
        if n in col:
            return col[n]
        if n in busy:                                  # a cycle: break it here
            return 0
        busy.add(n)
        col[n] = 1 + max((rank(b) for b, _a, _b in succ[n]), default=-1)
        busy.discard(n)
        return col[n]
    for n in nodes:
        rank(n)
    return col


def _reroute_long(tree, members, col):
    """A wire that skips columns goes through one reroute per column it passes. One output feeding several far
    nodes shares the chain. Returns the reroutes made (already in `col`)."""
    made = []
    chains = {}                                        # (from_socket pointer, column) -> reroute
    for l in list(tree.links):
        a, b = l.from_node, l.to_node
        if a not in members or b not in members or not l.is_valid or l.is_hidden:
            continue
        span = col[a] - col[b]
        if span <= 1 or a.bl_idname == "NodeGroupInput":     # settings wires stay direct: the frame's own
            continue                                          # Group Input sits right beside what reads it
        src = l.from_socket
        to_sock = l.to_socket
        parent = b.parent if b.parent is not None and b.parent == a.parent else None
        for c in sorted({col[a] - 1, col[b] + 1}, reverse=True):   # one point leaving the source, one arriving
            key = (l.from_socket.as_pointer(), c)
            r = chains.get(key)
            if r is None:
                r = tree.nodes.new("NodeReroute")
                r[REROUTE_TAG] = True
                if parent is not None:
                    r.parent = parent
                tree.links.new(src, r.inputs[0])
                chains[key] = r
                col[r] = c
                made.append(r)
            src = r.outputs[0]
        tree.links.remove(l)
        tree.links.new(src, to_sock)
    return made


def layout(tree, nodes, scale=1.0, reroutes=True):
    """Place `nodes` in columns. Returns {node: (x, y)} relative positions (x of the left edge, y of the top,
    y growing downwards) and the block's (width, height)."""
    members = set(nodes)
    succ = {n: [] for n in nodes}
    for a, sa, b, sb in _edges(tree, members):
        succ[a].append((b, sa, sb))
    col = _columns(nodes, succ)
    if reroutes:
        for r in _reroute_long(tree, members, col):
            members.add(r)
            nodes = list(nodes) + [r]
    succ = {n: [] for n in nodes}
    pred = {n: [] for n in nodes}
    for a, sa, b, sb in _edges(tree, members):
        succ[a].append((b, sa, sb))
        pred[b].append((a, sa, sb))
    size = {n: _size(n, scale) for n in nodes}
    ncols = 1 + max(col.values(), default=0)
    columns = [[] for _ in range(ncols)]
    seen = set()

    def visit(n):                                      # first order: from the outputs through their inputs
        if n in seen:
            return
        seen.add(n)
        columns[col[n]].append(n)
        for a, _sa, sb in sorted(pred[n], key=lambda e: list(n.inputs).index(e[2]) if e[2] in list(n.inputs) else 0):
            visit(a)
    for n in sorted((n for n in nodes if col[n] == 0), key=lambda n: -n.location.y):
        visit(n)
    for n in nodes:
        visit(n)
    top = {}

    def want_from(n):
        h = size[n][1]
        ys = [top[b] + _sock_y(b, sb, False, size[b][1]) - _sock_y(n, sa, True, h) for b, sa, sb in succ[n] if b in top]
        return sum(ys) / len(ys) if ys else None

    y = 0.0
    for n in columns[0]:
        top[n] = y
        y += size[n][1] + GAP_Y
    for c in range(1, ncols):
        want, y = {}, 0.0
        for n in columns[c]:
            w = want_from(n)
            want[n] = w if w is not None else y
            y = want[n] + size[n][1] + GAP_Y
        columns[c].sort(key=lambda n: want[n])
        tops = _isotonic([want[n] for n in columns[c]], [size[n][1] for n in columns[c]], [GAP_Y] * len(columns[c]))
        for n, t in zip(columns[c], tops):
            top[n] = t
    right, x = [], 0.0
    for c in range(ncols):
        wmax = max((size[n][0] for n in columns[c]), default=0.0)
        right.append(x)
        x -= wmax + GAP_X
    pos = {}
    for c in range(ncols):
        for n in columns[c]:
            w = size[n][0]
            cx = right[c] - (max((size[m][0] for m in columns[c]), default=w) + w) / 2   # centred in its column
            if n.type == "REROUTE":
                pos[n] = (cx, top[n])
            else:
                pos[n] = (right[c] - w, top[n])
    if not pos:
        return {}, (0.0, 0.0)
    x0 = min(p[0] for p in pos.values())
    y0 = min(p[1] for p in pos.values())
    pos = {n: (p[0] - x0, p[1] - y0) for n, p in pos.items()}
    width = max(p[0] + size[n][0] for n, p in pos.items())
    height = max(p[1] + size[n][1] for n, p in pos.items())
    return pos, (width, height)


def _put(n, x, y):
    """Place a node at absolute (x, y), y up as Blender has it."""
    if hasattr(n, "location_absolute"):
        n.location_absolute = (x, y)
    else:
        p = n.parent
        ox = oy = 0.0
        while p is not None:
            ox += p.location.x
            oy += p.location.y
            p = p.parent
        n.location = (x - ox, y - oy)


# --- whole trees -------------------------------------------------------------------------------------------------

def _clear_reroutes(tree):
    """Reroutes an earlier arrange added: their wires go back to being direct, so the new layout makes its own."""
    for r in [n for n in tree.nodes if n.type == "REROUTE" and n.get(REROUTE_TAG)]:
        src = r.inputs[0].links[0].from_socket if r.inputs[0].links else None
        outs = [l.to_socket for l in r.outputs[0].links]
        tree.nodes.remove(r)
        if src is not None:
            for s in outs:
                tree.links.new(src, s)


def _split_group_inputs(tree, frames):
    """Each frame that reads the group's settings gets its own Group Input, showing only the sockets it uses."""
    gins = [n for n in tree.nodes if n.bl_idname == "NodeGroupInput"]
    if not gins:
        return
    main = gins[0]
    for f in frames:
        kids = {n for n in tree.nodes if n.parent == f}
        uses = [l for l in tree.links if l.from_node in gins and l.to_node in kids]
        if not uses:
            continue
        own = next((n for n in kids if n.bl_idname == "NodeGroupInput"), None)
        if own is None:
            own = tree.nodes.new("NodeGroupInput")
            own.parent = f
        for l in uses:
            if l.from_node == own:
                continue
            name, to = l.from_socket.identifier, l.to_socket
            sock = next((s for s in own.outputs if s.identifier == name), None)
            if sock is None:
                continue
            tree.links.remove(l)
            tree.links.new(sock, to)
        used = {l.from_socket.identifier for l in tree.links if l.from_node == own}
        for s in own.outputs:
            s.hide = s.identifier not in used
    for g in gins:                                     # the first Group Input: only what is still read outside frames
        used = {l.from_socket.identifier for l in tree.links if l.from_node == g}
        if g.parent is None:
            for s in g.outputs:
                s.hide = s.identifier not in used


def arrange(tree, scale=1.0):
    """Lay the whole tree out. Returns the number of nodes placed."""
    if tree is None:
        return 0
    _clear_reroutes(tree)
    frames = [n for n in tree.nodes if n.type == "FRAME" and n.parent is None]
    staged = bool(frames) and tree.bl_idname == "GeometryNodeTree" and any(f.label for f in frames)
    out = next((n for n in tree.nodes if n.bl_idname in ("NodeGroupOutput", "ShaderNodeOutputMaterial")
                and getattr(n, "is_active_output", True)), None)
    ax, ay = (out.location.x, out.location.y) if out is not None else (0.0, 0.0)
    if staged:
        _split_group_inputs(tree, frames)
        placed = _arrange_stages(tree, frames, scale)
    else:
        nodes = [n for n in tree.nodes if n.type != "FRAME"]
        pos, _wh = layout(tree, nodes, scale)
        placed = {n: (p[0], -p[1]) for n, p in pos.items()}
    if not placed:
        return 0
    if out is not None and out in placed:                # the output keeps its place, so the view does not jump
        dx, dy = ax - placed[out][0], ay - placed[out][1]
    else:
        dx = dy = 0.0
    for n, (x, y) in placed.items():
        _put(n, x + dx, y + dy)
    for n in tree.nodes:                               # nodes made by code start selected: none should look picked
        n.select = False
    return len(placed)


def _arrange_stages(tree, frames, scale):
    """Frames left to right in the order the data flows; each frame's nodes laid out inside it."""
    owner = {}
    for n in tree.nodes:
        p = n.parent
        while p is not None and p.parent is not None:
            p = p.parent
        if n.type != "FRAME":
            owner[n] = p
    # frame order: a frame comes after every frame it reads from
    deps = {f: set() for f in frames}
    for l in tree.links:
        fa, fb = owner.get(l.from_node), owner.get(l.to_node)
        if fa in deps and fb in deps and fa != fb:
            deps[fb].add(fa)
    level = {}

    def lv(f, busy=()):
        if f in level:
            return level[f]
        if f in busy:
            return 0
        level[f] = 1 + max((lv(d, busy + (f,)) for d in deps[f]), default=-1)
        return level[f]
    for f in frames:
        lv(f)
    blocks = {}
    for f in frames:
        kids = [n for n in tree.nodes if owner.get(n) == f]
        blocks[f] = layout(tree, kids, scale)
    loose = [n for n in tree.nodes if n.type != "FRAME" and owner.get(n) is None]
    gin = [n for n in loose if n.bl_idname == "NodeGroupInput"]
    gout = [n for n in loose if n.bl_idname == "NodeGroupOutput"]
    rest = [n for n in loose if n not in gin and n not in gout]
    placed = {}
    x = 0.0
    if gin:
        y = 0.0
        for g in gin:
            w, h = _size(g, scale)
            placed[g] = (x, -y)
            y += h + GAP_Y
        x += max(_size(g, scale)[0] for g in gin) + GAP_FRAME
    if rest:
        pos, (w, h) = layout(tree, rest, scale)
        for n, p in pos.items():
            placed[n] = (x + p[0], -p[1])
        x += w + GAP_FRAME
    nlev = 1 + max(level.values(), default=0)
    for k in range(nlev):
        col = sorted((f for f in frames if level[f] == k), key=lambda f: f.label)
        y, wmax = 0.0, 0.0
        for f in col:
            pos, (w, h) = blocks[f]
            for n, p in pos.items():
                placed[n] = (x + p[0], -(y + p[1]))
            y += h + GAP_FRAME
            wmax = max(wmax, w)
        x += wmax + GAP_FRAME
    for g in gout:
        placed[g] = (x, 0.0)
    return placed


# --- the Node Editor button ---------------------------------------------------------------------------------------

class BLENDA4D_OT_node_arrange(bpy.types.Operator):
    """Lay the nodes out neatly: wires left to right, as few crossings as possible, long wires through reroutes"""
    bl_idname = "blenda4d.node_arrange"
    bl_label = "Auto Arrange"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        sp = context.space_data
        return sp is not None and sp.type == "NODE_EDITOR" and sp.edit_tree is not None

    def execute(self, context):
        tree = context.space_data.edit_tree
        n = arrange(tree, context.preferences.system.ui_scale)
        win, area = context.window, context.area
        region = next((r for r in area.regions if r.type == "WINDOW"), None)

        def frame_all():                               # after a redraw, once frames have fitted their nodes
            try:
                with bpy.context.temp_override(window=win, area=area, region=region):
                    bpy.ops.node.view_all()
            except (ReferenceError, RuntimeError, TypeError):
                pass
        area.tag_redraw()
        bpy.app.timers.register(frame_all, first_interval=0.05)
        self.report({"INFO"}, f"Arranged {n} nodes")
        return {"FINISHED"}


def _header(self, context):
    if context.space_data is not None and context.space_data.edit_tree is not None:
        self.layout.operator(BLENDA4D_OT_node_arrange.bl_idname, text="Auto Arrange", icon="NODETREE")


def register():
    bpy.utils.register_class(BLENDA4D_OT_node_arrange)
    bpy.types.NODE_HT_header.append(_header)


def unregister():
    bpy.types.NODE_HT_header.remove(_header)
    bpy.utils.unregister_class(BLENDA4D_OT_node_arrange)


# --- heavy stages as node groups -----------------------------------------------------------------------------------

PART_OWNER = "b4d_part_of"
_SOCKET_TYPE = {"VALUE": "NodeSocketFloat", "INT": "NodeSocketInt", "BOOLEAN": "NodeSocketBool",
                "VECTOR": "NodeSocketVector", "RGBA": "NodeSocketColor", "GEOMETRY": "NodeSocketGeometry",
                "ROTATION": "NodeSocketRotation", "MATRIX": "NodeSocketMatrix", "STRING": "NodeSocketString",
                "OBJECT": "NodeSocketObject", "MATERIAL": "NodeSocketMaterial", "MENU": "NodeSocketMenu",
                "COLLECTION": "NodeSocketCollection", "IMAGE": "NodeSocketImage", "TEXTURE": "NodeSocketTexture"}


class _PortLinks:
    """The `links` a stage builds with inside its group: a wire from a socket of the outer tree comes in through the
    group's input (one input per outer socket), so the stage's own code needs no change."""

    def __init__(self, inner):
        self.inner = inner
        self.gin = inner.nodes.new("NodeGroupInput")
        self.ports = []                                # [(outer socket, input index)]

    def port(self, sock):
        for s, i in self.ports:
            if s == sock:
                return self.gin.outputs[i]
        name = sock.name or "Value"
        self.inner.interface.new_socket(name, in_out="INPUT", socket_type=_SOCKET_TYPE.get(sock.type, "NodeSocketFloat"))
        i = len(self.ports)
        self.ports.append((sock, i))
        return self.gin.outputs[i]

    def new(self, a, b, *args, **kw):
        if a.id_data != self.inner:
            a = self.port(a)
        return self.inner.links.new(a, b, *args, **kw)

    def remove(self, link):
        return self.inner.links.remove(link)

    def __iter__(self):
        return iter(self.inner.links)


def subgroup(tree, label, fn):
    """Build one stage inside its own node group and put that group in `tree` as a single node labelled `label`.
    fn(nodes, links) builds the stage and returns a socket or a tuple of sockets; the same come back, now outputs
    of the group node in `tree`."""
    name = f"{tree.name} {label}"
    old = bpy.data.node_groups.get(name)
    if old is not None:
        bpy.data.node_groups.remove(old)
    inner = bpy.data.node_groups.new(name, tree.bl_idname)
    inner[PART_OWNER] = tree.name
    links = _PortLinks(inner)
    gout = inner.nodes.new("NodeGroupOutput")
    res = fn(inner.nodes, links)
    many = isinstance(res, (tuple, list))
    outs = list(res) if many else [res]
    keep = []                                          # results that are not sockets of this group pass straight out
    for k, s in enumerate(outs):
        if not hasattr(s, "is_output") or s.id_data != inner:
            keep.append(k)
            continue
        inner.interface.new_socket(s.name or f"Result {k + 1}", in_out="OUTPUT",
                                   socket_type=_SOCKET_TYPE.get(s.type, "NodeSocketFloat"))
        inner.links.new(s, gout.inputs[len([1 for j in range(k) if j not in keep])])
    arrange(inner)
    node = tree.nodes.new("GeometryNodeGroup" if tree.bl_idname == "GeometryNodeTree" else "ShaderNodeGroup")
    node.node_tree = inner
    node.label = label
    for s, i in links.ports:
        tree.links.new(s, node.inputs[i])
    back, o = [], 0
    for k, s in enumerate(outs):
        if k in keep:
            back.append(s)
        else:
            back.append(node.outputs[o])
            o += 1
    return tuple(back) if many else back[0]


def drop_parts(tree_name):
    """The node groups an earlier build of this tree made for its stages."""
    for g in [g for g in bpy.data.node_groups if g.get(PART_OWNER) == tree_name]:
        bpy.data.node_groups.remove(g)
