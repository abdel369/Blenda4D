# SPDX-License-Identifier: GPL-3.0-or-later
"""The tools column, drawn by Blenda 4D at the viewport's left edge (the create column's mirror image).

An area of its own would shrink and grow with the window; what is drawn inside the viewport keeps its pixel size. No
Blender region is taken for it: the sidebar stays free for other add-ons' panels. A POST_PIXEL handler paints the
column under the viewport's header; while the pointer is over it a small modal operator takes hover, clicks and the
wheel (so no tool, gizmo or brush acts underneath) and hands everything else on. Four views: the column runs down the
left-hand views, the second one taking up where the first is full. Too tall for the viewport: it scrolls."""
import os
import struct
import time

import blf
import bpy
import gpu
from gpu_extras.batch import batch_for_shader

from . import bars, icons, roles, strip, switch

WIDTH = 70             # px at UI scale 1: the column, whatever the window size
CELL = 48
TOP = 6
GAP = 10
ICON = 0.62            # the icon's share of the cell
TIP_GAP = 6
HOSTS = ("ASSETS", "AB_BAR", "MODES")       # the Asset Browser and its bottom strip; the column's own area

_state = {"hover": None, "running": False, "scroll": 0.0, "max_scroll": 0.0, "hosts": 0}
_tip = {}
_geom = {}
_handles = []
_keymaps = []


# --- Blender's vector icon files (.dat: "VCO", version, size, offset, then triangles and their colours) ---------
def _icon_file(name):
    if not name:
        return None
    for f in os.listdir(icons.DIR):                       # Blenda's tinted copy first
        if f.startswith(name + "__") and f.endswith(".dat"):
            return os.path.join(icons.DIR, f)
    v = "%d.%d" % bpy.app.version[:2]
    p = os.path.join(os.path.dirname(bpy.app.binary_path), "..", "Resources", v, "datafiles", "icons", name + ".dat")
    return p if os.path.exists(p) else None


def _load_geom(name):
    if name in _geom:
        return _geom[name]
    path, g = _icon_file(name), None
    if path:
        b = open(path, "rb").read()
        if b[:3] == b"VCO":
            w, h = b[4] or 256, b[5] or 256
            n = (len(b) - 8) // 18
            co, col = b[8:8 + n * 6], b[8 + n * 6:8 + n * 18]
            pos = [(co[i * 2] / w, co[i * 2 + 1] / h) for i in range(n * 3)]
            cols = [tuple(c / 255 for c in col[i * 4:i * 4 + 4]) for i in range(n * 3)]
            g = (pos, cols)
    _geom[name] = g
    return g


_tex = {}
SUPER = 4                                                 # render 4x, then average: thin edges stay, as Blender's


def _raster(name, px):
    """The icon as an anti-aliased RGBA texture, px square (rendered on the CPU at SUPER x, then averaged)."""
    key = (name, px)
    if key in _tex:
        return _tex[key]
    g = _load_geom(name)
    tex = None
    if g is not None:
        import numpy as np
        n = px * SUPER
        img = np.zeros((n, n, 4), dtype=np.float32)
        ys, xs = np.mgrid[0:n, 0:n]
        fx, fy = (xs + 0.5) / n, (ys + 0.5) / n
        pos, cols = g
        for t in range(len(pos) // 3):
            (ax, ay), (bx, by), (cx, cy) = pos[t * 3:t * 3 + 3]
            d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(d) < 1e-12:
                continue
            x0, x1 = int(max(0, min(ax, bx, cx) * n - 1)), int(min(n, max(ax, bx, cx) * n + 2))
            y0, y1 = int(max(0, min(ay, by, cy) * n - 1)), int(min(n, max(ay, by, cy) * n + 2))
            if x1 <= x0 or y1 <= y0:
                continue
            px_, py_ = fx[y0:y1, x0:x1], fy[y0:y1, x0:x1]
            l1 = ((by - cy) * (px_ - cx) + (cx - bx) * (py_ - cy)) / d
            l2 = ((cy - ay) * (px_ - cx) + (ax - cx) * (py_ - cy)) / d
            inside = (l1 >= 0) & (l2 >= 0) & (l1 + l2 <= 1)
            img[y0:y1, x0:x1][inside] = cols[t * 3]
        a = img.reshape(px, SUPER, px, SUPER, 4)
        rgb = (a[..., :3] * a[..., 3:4]).mean(axis=(1, 3))
        al = a[..., 3].mean(axis=(1, 3))[..., None]
        out = np.concatenate([np.where(al > 0, rgb / np.maximum(al, 1e-6), 0), al], axis=-1).astype(np.float32)
        tex = gpu.types.GPUTexture((px, px), format="RGBA32F", data=gpu.types.Buffer("FLOAT", px * px * 4, out.ravel().tolist()))
    _tex[key] = tex
    return tex


def _draw_icon(name, x, y, size, alpha=1.0):
    if name == "magnifier":
        return _draw_magnifier(x, y, size, alpha)
    tex = _raster(name, max(8, int(round(size))))
    if tex is None:
        return
    sh = gpu.shader.from_builtin("IMAGE_COLOR")
    x, y = round(x), round(y)                             # whole pixels: the icon stays sharp
    s = max(8, int(round(size)))
    batch = batch_for_shader(sh, "TRI_FAN", {"pos": [(x, y), (x + s, y), (x + s, y + s), (x, y + s)],
                                             "texCoord": [(0, 0), (1, 0), (1, 1), (0, 1)]})
    gpu.state.blend_set("ALPHA")
    sh.bind()
    sh.uniform_sampler("image", tex)
    sh.uniform_float("color", (1.0, 1.0, 1.0, alpha))
    batch.draw(sh)
    gpu.state.blend_set("NONE")


def _draw_magnifier(x, y, size, alpha=1.0):
    """Zoom to Border has no vector icon file: a lens and handle in the tool icons' light grey."""
    import math
    c = (0.898, 0.898, 0.898, alpha)
    cx, cy, ro = x + size * 0.42, y + size * 0.58, size * 0.30
    ri = ro - max(1.5, size * 0.08)
    pts = []
    for i in range(41):
        a = 2 * math.pi * i / 40
        pts += [(cx + ro * math.cos(a), cy + ro * math.sin(a)), (cx + ri * math.cos(a), cy + ri * math.sin(a))]
    sh = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.blend_set("ALPHA")
    gpu.state.face_culling_set("NONE")
    sh.bind()
    sh.uniform_float("color", c)
    batch_for_shader(sh, "TRI_STRIP", {"pos": pts}).draw(sh)
    d, t = math.sqrt(0.5), max(1.5, size * 0.07)        # the handle, down to the right
    x0, y0 = cx + ro * d, cy - ro * d
    x1, y1 = x + size * 0.92, y + size * 0.08
    nx, ny = t * d, t * d
    batch_for_shader(sh, "TRI_FAN", {"pos": [(x0 - nx, y0 - ny), (x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
                                             (x1 - nx, y1 - ny)]}).draw(sh)
    gpu.state.blend_set("NONE")


# --- the column ------------------------------------------------------------------------------------------------
def _items():
    out = [{"tool": None, "icon": "magnifier", "label": "Zoom to Border"}]
    for t in bars.MODES_TOOLS:
        if t is None:
            out.append(None)
            continue
        out.append({"tool": t, "icon": bars.TOOL_ICONS.get(t, ""), "label": t.split(".", 1)[-1].replace("_", " ").title()})
    return out


def _scale():
    return bpy.context.preferences.system.ui_scale


def _window_region(area):
    return next((r for r in area.regions if r.type == "WINDOW"), None)


def columns(window):
    """[(area, region, width, top)]: the areas the column runs down, top first, in region pixels. The column is always
    the outermost one on the left: in the viewports, or in the Asset Browser when that is open beside them."""
    if not switch.is_on() or window is None or window.workspace.name != switch.WORKSPACE:
        return []
    areas = window.screen.areas
    views = [a for a in areas if a.type == "VIEW_3D"]
    if not views:
        return []
    left = min(a.x for a in views)
    out = []
    hosts = [a for a in areas if roles.role(a) in HOSTS and a.x < left]
    own = [a for a in hosts if roles.role(a) == "MODES"]  # editors under the viewport: an area of its own, full height
    hosts = own or hosts
    if not hosts:
        hosts = [a for a in views if a.x - left <= 4]
    for a in sorted(hosts, key=lambda a: -a.y):
        r = _window_region(a)
        if r is None or r.width <= 1:
            continue
        top = r.y + r.height                              # the header rows lie over the viewport's top
        for h in a.regions:
            if h.type in {"HEADER", "TOOL_HEADER"} and h.height > 1 and h.alignment == "TOP":
                top = min(top, h.y)
        if own:                                           # beside the viewport: level with its first row
            from . import build
            top -= build.view_top(window)
        out.append((a, r, WIDTH * _scale(), top - r.y))
    return out


def inset(context):
    """Pixels the column takes from the left of this area (0: none)."""
    if context.area is None or context.area.type != "PROPERTIES":
        return 0
    return next((c[2] for c in columns(context.window) if c[0] == context.area), 0)


def beside(layout, context):
    """The layout to draw a manager's content in, clear of the column when it runs down that manager's left edge."""
    w = inset(context)
    if not w:
        return layout
    pad = 10 * _scale()
    s = layout.split(factor=min(0.6, max(0.01, (w - pad) / max(1.0, context.region.width - 2 * pad))), align=True)
    s.column()
    return s.column()


def _layout(window):
    """{area pointer: [(x0, y0, x1, y1, item)]} for the whole column, filling each left-hand view in turn."""
    s, cols = _scale(), columns(window)
    cell, boxes = CELL * s, {}
    if not cols:
        return boxes
    items = _items()
    tall = [c for c in cols if c[3] > 2 * cell]           # a bottom strip only carries the column's background
    if len(tall) != _state["hosts"]:
        _state.update(hosts=len(tall), scroll=0.0)
    for n, (a, r, width, top) in enumerate(tall):
        last = n == len(tall) - 1
        y = top - TOP * s
        if last:                                          # what does not fit any more scrolls here
            need = sum(cell if it else GAP * s for it in items) + 2 * TOP * s
            _state["max_scroll"] = max(0.0, need - top)
            _state["scroll"] = min(max(_state["scroll"], 0.0), _state["max_scroll"])
            y += _state["scroll"]
        here, x0 = [], (width - cell) / 2
        while items:
            it = items[0]
            if it is None:
                items.pop(0)
                y -= GAP * s if here else 0
                continue
            if not last and y - cell < TOP * s:
                break
            here.append((x0, y - cell, x0 + cell, y, items.pop(0)))
            y -= cell
        boxes[a.as_pointer()] = here
    return boxes


def _draw():
    context = bpy.context
    region, area = context.region, context.area
    if region is None or region.type != "WINDOW" or area is None:
        return
    mine = next((c for c in columns(context.window) if c[0] == area), None)
    if mine is None:
        return
    s, width, top = _scale(), mine[2], mine[3]
    boxes = _layout(context.window).get(area.as_pointer(), [])
    strip._rect(0, 0, width, region.height, strip.BG)
    active = bars.active_tool(context)
    runs = []
    for b in boxes:                                       # touching cells share one rounded button
        if runs and abs(runs[-1][-1][1] - b[3]) < 0.5:
            runs[-1].append(b)
        else:
            runs.append([b])
    for run in runs:
        strip._round_rect(run[0][0], run[-1][1], run[0][2], run[0][3], strip.RADIUS * s, strip.CELL_BG)
        for b in run[1:]:
            strip._rect(b[0], b[3] - 0.5, b[2], b[3] + 0.5, strip.DIVIDER)
    for x0, y0, x1, y1, it in boxes:
        if it["tool"] and it["tool"] == active:
            strip._round_rect(x0, y0, x1, y1, strip.RADIUS * s, strip.PRESSED)
        elif it["label"] == _state["hover"]:
            strip._round_rect(x0, y0, x1, y1, strip.RADIUS * s, strip.HOVER)
        size = (x1 - x0) * ICON
        _draw_icon(it["icon"], x0 + (x1 - x0 - size) / 2, y0 + (y1 - y0 - size) / 2, size)
    if _state["scroll"] > 0:                              # scrolled cells do not show through above the column
        strip._rect(0, top, width, region.height, strip.BG)


def _under(window, mx, my):
    """(column, box) under a window position; column None when the pointer is not over the column."""
    for c in columns(window):
        a, r, width, top = c
        x, y = mx - r.x, my - r.y
        if 0 <= x < width and 0 <= y < top:
            for over in a.regions:                        # a region lying over the viewport (asset shelf ...) wins
                if over.type != "WINDOW" and over.width > 1 and over.height > 1 and \
                        over.x <= mx < over.x + over.width and over.y <= my < over.y + over.height:
                    return None, None
            for b in _layout(window).get(a.as_pointer(), []):
                if b[0] <= x <= b[2] and b[1] <= y <= b[3]:
                    return c, b
            return c, None
    return None, None


def _shows(area):
    """Does the column, or its tooltip, show in this area?"""
    return area.type == "VIEW_3D" or roles.role(area) in HOSTS or roles.role(area) == "TL_EDIT"


def _redraw(window):
    for a in window.screen.areas:
        if _shows(a):
            a.tag_redraw()


# --- tooltip: to the right of the column, over the viewport ---------------------------------------------------
def _tip_set(col, box):
    _tip.clear()
    if box is None:
        return
    r = col[1]
    _tip.update(text=box[4]["label"], x=r.x + col[2], y=r.y + (box[1] + box[3]) / 2, t=time.time(), shown=False)
    if not bpy.app.timers.is_registered(_tip_tick):
        bpy.app.timers.register(_tip_tick, first_interval=strip.TIP_DELAY)


def _tip_tick():
    if not _tip or _tip.get("shown"):
        return None
    if time.time() - _tip["t"] < strip.TIP_DELAY:
        return 0.05
    _tip["shown"] = True
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            if _shows(a):
                a.tag_redraw()
    return None


def _draw_tip():
    if not _tip.get("shown"):
        return
    region = bpy.context.region
    if region is None or region.type != "WINDOW":
        return
    s = bpy.context.preferences.system.ui_scale
    blf.size(0, strip.TIP_TEXT * s)
    tw = blf.dimensions(0, _tip["text"])[0]
    w, h = tw + 14 * s, strip.TIP_TEXT * s + 10 * s
    rx, ry = _tip["x"] + TIP_GAP * s - region.x, _tip["y"] - h / 2 - region.y
    if rx > region.width or rx + w < 0 or ry > region.height or ry + h < 0:
        return
    strip._round_rect(rx, ry, rx + w, ry + h, 3 * s, strip.TIP_BORDER)
    strip._round_rect(rx + 1, ry + 1, rx + w - 1, ry + h - 1, 2.5 * s, strip.TIP_BG)
    gpu.state.blend_set("ALPHA")
    blf.color(0, *strip.TIP_COLOR)
    blf.position(0, rx + 7 * s, ry + 7 * s, 0)
    blf.draw(0, _tip["text"])
    gpu.state.blend_set("NONE")


# --- input ----------------------------------------------------------------------------------------------------
class BLENDA4D_OT_toolcol(bpy.types.Operator):
    bl_idname = "blenda4d.toolcol"
    bl_label = "Tools column"
    bl_description = "Takes the pointer while it is over the tools column"
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        if _state["running"] or _under(context.window, event.mouse_x, event.mouse_y)[0] is None:
            return {"PASS_THROUGH"}
        self._window = context.window
        _state["running"] = True
        context.window_manager.modal_handler_add(self)
        self._hover(event)
        return {"RUNNING_MODAL"}

    def _hover(self, event):
        col, box = _under(self._window, event.mouse_x, event.mouse_y)
        name = box[4]["label"] if box else None
        if name != _state["hover"]:
            _state["hover"] = name
            _tip_set(col, box)
            _redraw(self._window)
        return col, box

    def _end(self):
        _state.update(running=False, hover=None)
        _tip.clear()
        _redraw(self._window)

    def modal(self, context, event):
        col, box = self._hover(event)
        if col is None or event.type == "WINDOW_DEACTIVATE":
            self._end()
            return {"CANCELLED", "PASS_THROUGH"}
        if event.type in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE", "RIGHTMOUSE", "MIDDLEMOUSE"}:
            return {"RUNNING_MODAL"}
        if event.type in {"WHEELUPMOUSE", "WHEELDOWNMOUSE", "TRACKPADPAN"}:
            if event.type == "TRACKPADPAN":
                step = event.mouse_y - event.mouse_prev_y
            else:
                step = (-1 if event.type == "WHEELUPMOUSE" else 1) * CELL * _scale()
            _state["scroll"] = min(max(_state["scroll"] + step, 0.0), _state["max_scroll"])
            _redraw(self._window)
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE":
            if event.value not in {"PRESS", "DOUBLE_CLICK"} or box is None:
                return {"RUNNING_MODAL"}
            it = box[4]
            view = max((a for a in self._window.screen.areas if a.type == "VIEW_3D"),
                       key=lambda a: (a == col[0], a.width * a.height))
            with context.temp_override(window=self._window, area=view, region=_window_region(view)):
                if it["tool"]:
                    _tip.clear()
                    bpy.ops.wm.tool_set_by_id(name=it["tool"])
                    _redraw(self._window)
                    return {"RUNNING_MODAL"}
                self._end()
                bpy.ops.view3d.zoom_border("INVOKE_DEFAULT")
            return {"FINISHED"}
        return {"PASS_THROUGH"}

    def cancel(self, context):
        _state.update(running=False, hover=None)


classes = (BLENDA4D_OT_toolcol,)


@bpy.app.handlers.persistent
def _loaded(_file):
    _state.update(running=False, hover=None, scroll=0.0)     # opening a file ends modal operators
    _tip.clear()


def register():
    _state.update(running=False, hover=None, scroll=0.0)
    for c in classes:
        bpy.utils.register_class(c)
    for space in (bpy.types.SpaceView3D, bpy.types.SpaceProperties):
        for fn in (_draw, _draw_tip):
            _handles.append((space, space.draw_handler_add(fn, (), "WINDOW", "POST_PIXEL")))
    if _loaded not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_loaded)
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        for name, space in (("3D View Generic", "VIEW_3D"), ("Property Editor", "PROPERTIES")):
            km = kc.keymaps.new(name=name, space_type=space, region_type="WINDOW")
            _keymaps.append((km, km.keymap_items.new(BLENDA4D_OT_toolcol.bl_idname, "MOUSEMOVE", "ANY", head=True)))


def unregister():
    if _loaded in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_loaded)
    for km, kmi in _keymaps:
        try:
            km.keymap_items.remove(kmi)
        except (ReferenceError, RuntimeError):
            pass
    _keymaps.clear()
    for space, h in _handles:
        try:
            space.draw_handler_remove(h, "WINDOW")
        except ValueError:
            pass
    _handles.clear()
    _tip.clear()
    _tex.clear()
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
