# SPDX-License-Identifier: GPL-3.0-or-later
"""Build Blenda's layouts (layouts.py) on the live screen at exact pixel sizes.

Areas are made with area_split / area_close (which work without window focus), one step per redraw, because an
area's size only updates on the next event loop:
  document tabs (full width, top) | managers column (right, full height: Objects over Attributes)
  command palette (top, left of the managers) | tools column (drawn at the viewport's left edge, toolcol.py)
  create column (drawn in the viewport's toolbar strip, strip.py)
  timeline (bottom, under the viewport) | optional Material Manager column (between viewport and create column)
  | optional Asset Browser column (left of the viewport).
A layout with editors under the viewport has the tools and create columns as two areas down its sides, so they stay
full height; what is drawn in them keeps its size, and they get their width back after the window is resized."""
import bpy

from . import roles

DOC_TABS_PX = 30
PALETTE_PX = 62
TIMELINE_PX = 64
TOOL_ZOOM = {"PALETTE": 7}   # zoom steps (as Ctrl+scroll): larger icons, boxes stay square
CREATE_PX = 57                # as wide as the viewport's own strip: the column stays put when it becomes an area
EDITORS = 0.46                # the share of the viewport's height the editors under it take
TRACKS = 0.6                  # the tracks' share of the editors' width
STRIP_ZOOM = 0               # the create column is drawn at its own size (strip.py): the strip needs no zoom
MANAGERS_PX = 330
MATERIALS_PX = 230
MM_BAR_PX = 30
OM_HEAD_PX = 88               # the Object Manager's title, menus and tool row (unzoomed; the Size slider zooms only the rows)
ASSETS_PX = 420
ATTRIBUTES = 0.56             # the Attribute Manager's share of the managers column
EDGE = 3

_active = [0]


def busy():
    return _active[0] > 0


def run_steps(gen, done=None):
    """Run a generator one step per redraw; a step that fails while the window is not ready is retried."""
    state = {"retries": 20}
    _active[0] += 1

    def tick():
        try:
            next(gen)
            return 0.0                                   # the next step as soon as Blender has laid out the last
        except StopIteration:
            _active[0] -= 1
            if done:
                done()
            return None
        except RuntimeError as ex:
            state["retries"] -= 1
            if state["retries"] > 0:
                return 0.25
            _active[0] -= 1
            print("Blenda 4D: layout step gave up:", ex)
            return None
        except Exception:
            _active[0] -= 1
            raise
    bpy.app.timers.register(tick)


def _scale():
    return bpy.context.preferences.system.ui_scale


def px(v):
    return int(round(v * _scale()))


def _region(area, kind):
    return next((r for r in area.regions if r.type == kind), None)


def _ov(window, area, region="WINDOW"):
    return bpy.context.temp_override(window=window, screen=window.screen, area=area, region=_region(area, region))


def biggest_view(screen):
    views = [a for a in screen.areas if a.type == "VIEW_3D"]
    if not views:
        big = max(screen.areas, key=lambda a: a.width * a.height)
        big.type = "VIEW_3D"
        views = [big]
    return max(views, key=lambda a: a.width * a.height)


def split(window, area, direction, size_px, side):
    size = area.height if direction == "HORIZONTAL" else area.width
    frac = size_px / max(size, 1)
    factor = {"TOP": 1 - frac, "BOTTOM": frac, "LEFT": frac, "RIGHT": 1 - frac}[side]
    before = {a.as_pointer() for a in window.screen.areas}
    with _ov(window, area):
        bpy.ops.screen.area_split(direction=direction, factor=factor)
    new = next(a for a in window.screen.areas if a.as_pointer() not in before)
    yield
    pair = (new, area)
    if direction == "HORIZONTAL":
        top, bottom = sorted(pair, key=lambda a: -a.y)
        return top if side == "TOP" else bottom
    left, right = sorted(pair, key=lambda a: a.x)
    return left if side == "LEFT" else right


def make_role(window, area, name):
    area.type = "PROPERTIES"
    yield
    for _ in range(20):
        if roles.set_role(area, name):
            break
        area.tag_redraw()
        yield
    roles.hide_nav(area)
    yield
    if name in TOOL_ZOOM:
        _zoom(window, area, TOOL_ZOOM[name])
        yield


def _zoom(window, area, n):
    """Blender's own area zoom (as Ctrl+scroll does): buttons and icons grow together."""
    region = next((r for r in area.regions if r.type == "WINDOW"), None)
    if region is None:
        return
    try:
        with bpy.context.temp_override(window=window, screen=window.screen, area=area, region=region):
            for _ in range(n):
                bpy.ops.view2d.zoom_in()
    except RuntimeError as ex:
        print("Blenda 4D: could not zoom", area.type, ex)


def split_now(window, area, direction, size_px, side, size=None):
    """Split off a strip and return it at once: Blender makes the smaller part the new area, which is the strip.
    `size` stands in for the area's size when Blender has not laid the area out yet."""
    size = size or (area.height if direction == "HORIZONTAL" else area.width)
    frac = size_px / max(size, 1)
    factor = {"TOP": 1 - frac, "BOTTOM": frac, "LEFT": frac, "RIGHT": 1 - frac}[side]
    before = {a.as_pointer() for a in window.screen.areas}
    with _ov(window, area):
        bpy.ops.screen.area_split(direction=direction, factor=factor)
    return next(a for a in window.screen.areas if a.as_pointer() not in before)


def role_now(area, name):
    """The area becomes its role's editor in the same step it appears (no frame shows a stray editor)."""
    area.type = "PROPERTIES"
    roles.set_role(area, name)
    try:
        roles.hide_nav(area)
    except RuntimeError:
        pass


def settle(window, *pairs):
    """After the frame: make sure each area has its role and no tab column (set at once where Blender allowed)."""
    for area, name in pairs:
        for _ in range(20):
            if roles.set_role(area, name):
                break
            yield
        roles.hide_nav(area, window)


def _add_column(window, width_px, side, main, bar):
    """A column beside the viewport with its bottom strip, each one its final editor from the frame it appears in."""
    view = biggest_view(window.screen)
    # Blender makes the smaller part the new area: the column stays the smaller one, or it would land on the other side
    col = split_now(window, view, "VERTICAL", min(px(width_px) + EDGE, round(view.width * 0.45)), side)
    role_now(col, main)
    yield                                                  # Blender lays the column out before it can be split
    strip = split_now(window, col, "HORIZONTAL", px(MM_BAR_PX) + EDGE, "BOTTOM")
    role_now(strip, bar)
    yield
    yield from settle(window, (col, main), (strip, bar))


def _width(window, key, usual):
    from . import layouts
    return max(60, layouts.spec_of(window.screen)["sizes"].get(key, usual))


def add_assets(window):
    """The Asset Browser column, left of the viewport, with its bottom strip."""
    from . import toolcol
    tools = 0 if roles.areas(window.screen, "MODES") else toolcol.WIDTH       # it hosts the tools column
    yield from _add_column(window, _width(window, "assets", ASSETS_PX + toolcol.WIDTH) - toolcol.WIDTH + tools, "LEFT", "ASSETS", "AB_BAR")


def add_materials(window):
    """The Material Manager column, right of the viewport, with its bottom strip."""
    yield from _add_column(window, _width(window, "materials", MATERIALS_PX), "RIGHT", "MATERIALS", "MM_BAR")


COLUMNS = {"MATERIALS": (add_materials, "MM_BAR"), "ASSETS": (add_assets, "AB_BAR")}
CORE = ("DOC_TABS", "PALETTE", "OBJECTS", "ATTRIBUTES", "OM_BAR", "OM_HEAD")


def is_timeline(area):
    return area.type == "DOPESHEET_EDITOR" and area.ui_type == "TIMELINE"


def timelines(screen):
    return [a for a in screen.areas if is_timeline(a)]


def tracks(screen):
    return [a for a in screen.areas if a.type == "DOPESHEET_EDITOR" and not is_timeline(a)]


def curves(screen):
    return [a for a in screen.areas if a.type == "GRAPH_EDITOR"]


def side_px():
    """The tools column's width as an area of its own."""
    from . import toolcol
    return px(toolcol.WIDTH) + EDGE


def view_top(window):
    """Pixels of header over the viewport: the columns beside it start below them, as they do in the viewport."""
    view = max((a for a in window.screen.areas if a.type == "VIEW_3D"), key=lambda a: (a.y + a.height, a.width), default=None)
    if view is None:
        return 0
    return sum(r.height for r in view.regions if r.type in {"HEADER", "TOOL_HEADER"} and r.height > 1 and r.alignment == "TOP")


def intact(screen):
    """The layout is all there (each strip once, a viewport, its timeline and editors): nothing to rebuild."""
    from . import layouts
    spec = layouts.spec_of(screen)
    if any(len(roles.areas(screen, r)) != 1 for r in CORE):
        return False
    stacked = bool(spec["editors"])
    if len(roles.areas(screen, "MODES")) != stacked:       # without editors a layout from before 0.1.22 has one
        return False
    if len(tracks(screen)) != stacked or len(curves(screen)) != stacked or (stacked and len(roles.areas(screen, "CREATE")) != 1):
        return False
    if not any(a.type == "VIEW_3D" for a in screen.areas) or len(timelines(screen)) != spec["timeline"]:
        return False
    for main, (_add, bar) in COLUMNS.items():
        if len(roles.areas(screen, main)) != len(roles.areas(screen, bar)) or len(roles.areas(screen, main)) > 1:
            return False
    return True


# --- the parts a layout adds under and beside the viewport ----------------------------------------------------------
def add_timeline(window):
    view = biggest_view(window.screen)
    hdr = _region(view, "HEADER").height if _region(view, "HEADER") else 26
    timeline = yield from split(window, view, "HORIZONTAL", px(TIMELINE_PX) + hdr + EDGE, "BOTTOM")
    timeline.type = "DOPESHEET_EDITOR"
    timeline.ui_type = "TIMELINE"
    yield


def dress_timeline(screen):
    for a in timelines(screen):
        st = a.spaces.active
        st.show_region_channels = False
        st.show_region_ui = False


def add_stack(window, sizes, materials=False, assets=False):
    """The tools and create columns down the sides, the optional columns full height where they always are (Material
    Manager right of the create column, Asset Browser right of the tools), and the editors under the viewport."""
    screen = window.screen
    if materials:
        yield from add_materials(window)
    tools = yield from split(window, biggest_view(screen), "VERTICAL", side_px(), "LEFT")
    yield from make_role(window, tools, "MODES")
    if assets:
        yield from add_assets(window)
    create = yield from split(window, biggest_view(screen), "VERTICAL", px(CREATE_PX) + EDGE, "RIGHT")
    yield from make_role(window, create, "CREATE")
    view = biggest_view(screen)
    dress_view(view)
    share = min(0.8, max(0.15, sizes.get("editors", EDITORS)))
    low = yield from split(window, view, "HORIZONTAL", round(view.height * share), "BOTTOM")
    low.type = "DOPESHEET_EDITOR"
    low.ui_type = "DOPESHEET"
    yield
    share = min(0.85, max(0.15, sizes.get("tracks", TRACKS)))
    right = yield from split(window, low, "VERTICAL", round(low.width * (1 - share)), "RIGHT")
    right.type = "GRAPH_EDITOR"
    right.ui_type = "FCURVES"
    yield
    for a in tracks(screen) + curves(screen):
        a.spaces.active.show_region_ui = False
        if hasattr(a.spaces.active, "show_region_footer"):
            a.spaces.active.show_region_footer = False     # its playback buttons: the timeline below has them
        a.spaces.active.show_region_header = True
        if hasattr(a.spaces.active, "show_region_channels"):   # a narrow editor is all keys, or all curves
            a.spaces.active.show_region_channels = a.width > px(340 if a.type == "GRAPH_EDITOR" else 300)
        header = _region(a, "HEADER")
        if header is not None and header.alignment != "TOP":
            try:
                with _ov(window, a, "HEADER"):
                    bpy.ops.screen.region_flip()
            except RuntimeError:
                pass
    yield
    for a, frame_all in [(a, bpy.ops.action.view_all) for a in tracks(screen)] + [(a, bpy.ops.graph.view_all) for a in curves(screen)]:
        try:                                               # the keys there are, all in view
            with _ov(window, a):
                frame_all()
        except RuntimeError:
            pass


def _into_view(window, area):
    from . import quadview
    view = biggest_view(window.screen)
    yield from quadview._join(window, area, view)


def remove_stack(window):
    """The editors and the two columns go back into the viewport, each one a join along a whole edge."""
    from . import quadview
    screen = window.screen
    for c in curves(screen):
        if tracks(screen):
            yield from quadview._join(window, c, tracks(screen)[0])
    for t in tracks(screen):
        yield from _into_view(window, t)
    for a in roles.areas(screen, "CREATE"):
        yield from _into_view(window, a)
    for n in COLUMNS:
        if roles.areas(screen, n):
            yield from remove_column(window, n)
    for a in roles.areas(screen, "MODES"):
        yield from _into_view(window, a)
    for a in screen.areas:
        if a.type == "VIEW_3D":
            dress_view(a)


def remove_column(window, name):
    for role in (COLUMNS[name][1], name):                  # the strip into its column, the column into the viewport,
        for a in roles.areas(window.screen, role):         # in one step: no frame shows the column without its strip
            with _ov(window, a):
                bpy.ops.screen.area_close()
    yield


def renew_steps(window):
    """The stack again at its own sizes (the window was resized); everything else stays where it is."""
    from . import layouts, quadview
    screen = window.screen
    spec = layouts.spec_of(screen)
    on = [n for n in COLUMNS if roles.areas(screen, n)]
    if len(quadview.views(screen)) > 1:
        return                                             # four views are left as they are
    yield from remove_stack(window)
    yield from add_stack(window, spec["sizes"], "MATERIALS" in on, "ASSETS" in on)
    if not intact(screen):
        yield from steps(window, materials="MATERIALS" in on, assets="ASSETS" in on)
    for a in screen.areas:
        a.tag_redraw()


def drifted(screen, sizes):
    """Are the managers, the command bar or the timeline another size than the layout's own?"""
    def one(role):
        return next(iter(roles.areas(screen, role)), None)
    attr, palette = one("ATTRIBUTES"), one("PALETTE")
    if abs(attr.width - px(sizes.get("managers", MANAGERS_PX))) > 8 or abs(palette.height - EDGE - px(PALETTE_PX)) > 6:
        return True
    whole = sum(one(r).height for r in ("OBJECTS", "OM_HEAD", "OM_BAR", "ATTRIBUTES"))
    if abs(attr.height / max(1, whole) - sizes.get("attributes", ATTRIBUTES)) > 0.02:
        return True
    return any(abs(a.height - px(TIMELINE_PX) - 26 * _scale()) > 14 for a in timelines(screen))


def switch_steps(window, name):
    """Bring a layout's saved arrangement up. What both layouts share stays where it is."""
    from . import layouts, quadview, render_settings
    screen, ws = window.screen, window.workspace
    old, new = layouts.spec_of(screen), layouts.spec(name)
    render_settings.show_view(screen)                     # Render Settings in the viewport's place: viewport back first
    yield
    whole = intact(screen) and not drifted(screen, new["sizes"])
    layouts.set_current(ws, name)
    views = quadview.views(screen)
    if whole and len(views) > 1:                           # four views: back to the Perspective one
        keep = next((a for a in views if quadview.corner_of(a, screen) == "PERSP"), views[0])
        yield from quadview.expand_steps(window, keep)
    if whole:
        moved = (old["timeline"], old["editors"]) != (new["timeline"], new["editors"]) or (bool(new["editors"]) and (
            old["sizes"] != new["sizes"] or any(bool(roles.areas(screen, n)) != new[n.lower()] for n in COLUMNS)))
        if moved:
            yield from remove_stack(window)
        for n in COLUMNS:
            if roles.areas(screen, n) and (not new[n.lower()] or old["sizes"].get(n.lower()) != new["sizes"].get(n.lower())):
                yield from remove_column(window, n)
        if moved:
            if old["timeline"] and not new["timeline"]:
                for a in timelines(screen):
                    yield from _into_view(window, a)
            elif new["timeline"] and not old["timeline"]:
                yield from add_timeline(window)
                dress_timeline(screen)
            if new["editors"]:
                yield from add_stack(window, new["sizes"], new["materials"], new["assets"])
        for n in ("ASSETS", "MATERIALS"):
            if new[n.lower()] and not roles.areas(screen, n):
                yield from COLUMNS[n][0](window)
    if not whole or not intact(screen) or len(quadview.views(screen)) > 1:
        yield from steps(window, materials=new["materials"], assets=new["assets"])
    for a in screen.areas:
        a.tag_redraw()


def column_steps(window, name, on):
    """Show or hide one optional column, leaving every other area where it is."""
    screen = window.screen
    from . import layouts, quadview
    add = COLUMNS[name][0]
    spec = layouts.spec_of(screen)
    if spec["editors"] and roles.areas(screen, "MODES"):  # beside the editors too: they are put in again after it
        want = {n: bool(roles.areas(screen, n)) for n in COLUMNS}
        want[name] = on
        if len(quadview.views(screen)) > 1:
            yield from quadview.expand_steps(window, quadview.views(screen)[0])
        yield from remove_stack(window)
        yield from add_stack(window, spec["sizes"], want["MATERIALS"], want["ASSETS"])
    elif on:
        yield from add(window)
    else:
        yield from remove_column(window, name)
    if not intact(screen):                                 # the change did not land as planned: build it all
        yield from steps(window, materials=bool(roles.areas(screen, "MATERIALS")) if name != "MATERIALS" else on,
                         assets=bool(roles.areas(screen, "ASSETS")) if name != "ASSETS" else on)
    for a in screen.areas:
        a.tag_redraw()


def steps(window, materials=False, assets=False, spec=None):
    screen = window.screen
    from . import layouts, render_settings
    spec = spec or layouts.spec_of(screen)
    sizes = spec["sizes"]
    render_settings.show_view(screen)                     # Render Settings in the viewport's place: viewport back first
    # 1. everything back into one viewport
    for _ in range(40):
        extra = [a for a in screen.areas if a.type != "VIEW_3D"] + \
                [a for a in screen.areas if a.type == "VIEW_3D" and a != biggest_view(screen)]
        if not extra:
            break
        with _ov(window, extra[0]):
            bpy.ops.screen.area_close()
        yield
    view = biggest_view(screen)
    # 2. strips at exact sizes, full-width ones first
    tabs = yield from split(window, view, "HORIZONTAL", px(DOC_TABS_PX) + EDGE, "TOP")
    yield from make_role(window, tabs, "DOC_TABS")
    managers = yield from split(window, biggest_view(screen), "VERTICAL", px(sizes.get("managers", MANAGERS_PX)) + EDGE, "RIGHT")
    yield from make_role(window, managers, "OBJECTS")
    palette = yield from split(window, biggest_view(screen), "HORIZONTAL", px(PALETTE_PX) + EDGE, "TOP")
    yield from make_role(window, palette, "PALETTE")
    # the create column is drawn in the viewport's own toolbar strip (bars.BLENDA4D_PT_view_tools), moved to the
    # viewport's right edge: the strip keeps its width when the window is resized; a separate area would stretch
    if spec["timeline"]:
        yield from add_timeline(window)
    if spec["editors"]:
        yield from add_stack(window, sizes, materials, assets)
        materials = assets = False                         # in already, beside the editors
    if assets:
        yield from add_assets(window)
    if materials:
        yield from add_materials(window)
    attributes = yield from split(window, managers, "HORIZONTAL", round(managers.height * min(0.85, max(0.15, sizes.get("attributes", ATTRIBUTES)))), "BOTTOM")
    yield from make_role(window, attributes, "ATTRIBUTES")
    objs = sorted(roles.areas(screen, "OBJECTS"), key=lambda a: a.y)
    if len(objs) > 1:                                      # the split can hand back the other half
        yield from make_role(window, objs[0], "ATTRIBUTES")
    objs = sorted(roles.areas(screen, "OBJECTS"), key=lambda a: a.y)
    if objs:                                               # the Object Manager's bottom strip: its Size slider
        om_bar = yield from split(window, objs[-1], "HORIZONTAL", px(MM_BAR_PX) + EDGE, "BOTTOM")
        yield from make_role(window, om_bar, "OM_BAR")
        objs = sorted(roles.areas(screen, "OBJECTS") + roles.areas(screen, "OM_BAR"), key=lambda a: a.y)
        if len(roles.areas(screen, "OBJECTS")) == 2:       # the split handed back the other half
            yield from make_role(window, min(roles.areas(screen, "OBJECTS"), key=lambda a: a.y), "OM_BAR")
    objs = roles.areas(screen, "OBJECTS")
    if objs:                                               # and its top strip: title, menus, search, tool row
        head = yield from split(window, objs[0], "HORIZONTAL", px(OM_HEAD_PX) + EDGE, "TOP")
        yield from make_role(window, head, "OM_HEAD")
        if len(roles.areas(screen, "OBJECTS")) == 2:       # the split handed back the other half
            yield from make_role(window, max(roles.areas(screen, "OBJECTS"), key=lambda a: a.y), "OM_HEAD")
    # 3. the viewport and timeline lose Blender's own chrome; the toolbar strip moves to the viewport's right edge
    for a in screen.areas:
        if a.type == "VIEW_3D":
            dress_view(a)
            tools = _region(a, "TOOLS")
            if tools is not None and tools.alignment != "RIGHT":
                try:
                    with _ov(window, a, "TOOLS"):
                        bpy.ops.screen.region_flip()
                except RuntimeError as ex:
                    print("Blenda 4D: could not move the toolbar strip", ex)
                yield
            if tools is not None:                          # start the strip's view fresh after the move, then zoom
                try:                                       # it so its buttons are as big as the tools column's
                    with _ov(window, a, "TOOLS"):
                        bpy.ops.view2d.reset()
                        for _ in range(STRIP_ZOOM):
                            bpy.ops.view2d.zoom_in()
                except RuntimeError:
                    pass
                yield
    dress_timeline(screen)
    for a in screen.areas:
        a.tag_redraw()


def dress_view(area):
    v3d = area.spaces.active
    # four views, or editors under the viewport: the create column is one separate column beside them, not a strip
    apart = sum(a.type == "VIEW_3D" for a in area.id_data.areas) > 1 or bool(roles.areas(area.id_data, "CREATE"))
    for attr, want in (("show_region_ui", False), ("show_region_toolbar", not apart), ("show_region_header", True),
                       ("show_region_tool_header", True), ("show_region_hud", False)):
        if getattr(v3d, attr) != want:
            setattr(v3d, attr, want)
    v3d.show_gizmo_navigate = False
    v3d.lock_camera = True          # looking through a camera, orbit / pan / zoom move the camera itself
    v3d.overlay.show_text = False
    v3d.overlay.show_stats = False


def toggle(window, name, on):
    """Show or hide an optional column (Material Manager, Asset Browser): only that column changes."""
    run_steps(column_steps(window, name, on))


def drop_modes(window, materials, assets):
    """A layout saved before 0.1.22 has the tools column as an area: close just that, keep everything else."""
    for a in roles.areas(window.screen, "MODES"):
        with _ov(window, a):
            bpy.ops.screen.area_close()
        yield
    if not intact(window.screen):
        yield from steps(window, materials=materials, assets=assets)
    for a in window.screen.areas:
        a.tag_redraw()


def rebuild(window, done=None, force=False, spec=None):
    """Build the window's layout; a layout that is already all there is only tidied (no area moves)."""
    if not force and intact(window.screen):
        for a in window.screen.areas:
            if a.type == "VIEW_3D":
                dress_view(a)
        if done:
            done()
        return
    opts = dict(materials=bool(roles.areas(window.screen, "MATERIALS")), assets=bool(roles.areas(window.screen, "ASSETS")))
    if spec is not None:                                   # the startup layout, for a new workspace
        run_steps(steps(window, materials=spec["materials"], assets=spec["assets"], spec=spec), done)
    elif not force and roles.areas(window.screen, "MODES") and not curves(window.screen):
        run_steps(drop_modes(window, **opts), done)
    else:
        run_steps(steps(window, **opts), done)
