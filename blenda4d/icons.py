# SPDX-License-Identifier: GPL-3.0-or-later
"""Colour-tinted copies of Blender's own icons for Blenda 4D's columns (the colour hierarchy: cyan for shapes,
splines and text, green for generators, violet for deformers, pink for cloning, pale lavender for scene objects,
orange accents on spline tools). The images are made by tools/tint_icons.py into blenda4d/icons/ as
<icon name>__<group>.png; see icons/NOTICE.md. Anything without a tinted copy falls back to Blender's plain icon."""
import os

import bpy

DIR = os.path.join(os.path.dirname(__file__), "icons")
_pcoll = None
_tools = {}          # tool icon name -> icon_value of its recoloured triangle copy
_strip = {}          # "<icon>__<group>" -> icon_value of the triangle copy that fills a button (tools/make_strip_icons.py)


def _load():
    global _pcoll
    if _pcoll is not None:
        return _pcoll
    import bpy.utils.previews
    _pcoll = bpy.utils.previews.new()
    try:
        names = os.listdir(DIR)
    except OSError:
        names = []
    for f in names:
        if f.endswith(".dat"):
            try:
                _tools[f[:-4].split("__")[0]] = bpy.app.icons.new_triangles_from_file(os.path.join(DIR, f))
            except Exception:
                pass
        if f.endswith(".png"):
            try:
                _pcoll.load(f[:-4], os.path.join(DIR, f), "IMAGE")
            except Exception:
                pass
    _load_strip()
    return _pcoll


def _load_strip():
    if _strip:
        return
    folder = os.path.join(DIR, "strip")
    try:
        names = os.listdir(folder)
    except OSError:
        return
    for f in names:
        if f.endswith(".dat"):
            try:
                _strip[f[:-4]] = bpy.app.icons.new_triangles_from_file(os.path.join(folder, f))
            except Exception:
                pass


def strip_kw(name, group):
    """Like kw(), but the triangle copy that fills its button (the create column in the viewport strip)."""
    _load()
    iv = _strip.get(f"{(name or '').lower()}__{group}")
    return {"icon_value": iv} if iv else kw(name, group)


def icon(name, group):
    """icon_value of the tinted copy of Blender icon `name` ("MESH_CUBE" or a tool icon "ops.curve.pen") for
    `group` (a create-column group name), or None when there is none."""
    if not name or not group:
        return None
    pc = _load()
    p = pc.get(f"{name.lower()}__{group}")
    return p.icon_id if p is not None else None


def any_icon(name):
    """icon_value of a tinted copy of `name` in whichever group it was made for (tool icons have one), or None."""
    pc = _load()
    if name in _tools:
        return _tools[name]
    pre = name.lower() + "__"
    for key, p in pc.items():
        if key.startswith(pre):
            return p.icon_id
    return None


def kw(name, group):
    """Keyword arguments for a layout call: icon_value=<tinted> if a copy exists, else icon=<name>."""
    iv = icon(name, group)
    return {"icon_value": iv} if iv else {"icon": name or "NONE"}


# --- which group an object belongs to (Object Manager and Attribute Manager headers) ------------------------------
_TYPE_GROUP = {"CURVE": "splines", "FONT": "text", "EMPTY": "null", "LIGHT": "lights", "CAMERA": "camera",
               "META": "generators", "VOLUME": "volume"}


_kind_group = {}


def group_of(ob):
    from . import bars, kinds
    k = kinds.kind_of(ob) or ob.get("b4d_type")
    if k:
        n = sum(len(m) for m in bars.GROUPS.values())
        if _kind_group.get(None) != n:                 # modules add buttons at register time: rebuild when it grows
            _kind_group.clear()
            for g, members in bars.GROUPS.items():
                for m in members:
                    if isinstance(m[3], dict) and m[3].get("kind"):
                        _kind_group.setdefault(m[3]["kind"], g)
            _kind_group[None] = n
        if k in _kind_group:
            return _kind_group[k]
    return _TYPE_GROUP.get(ob.type)


def object_icon(ob, name):
    """Layout keywords for object `ob` shown with Blender icon `name`, tinted by the object's group."""
    try:
        return kw(name, group_of(ob))
    except Exception:
        return {"icon": name}


def register():
    _load()


def unregister():
    global _pcoll
    if _pcoll is not None:
        import bpy.utils.previews
        bpy.utils.previews.remove(_pcoll)
        _pcoll = None
    for iv in _tools.values():
        try:
            bpy.app.icons.release(iv)
        except Exception:
            pass
    _tools.clear()
    for iv in _strip.values():
        try:
            bpy.app.icons.release(iv)
        except Exception:
            pass
    _strip.clear()
_tools = {}          # tool icon name -> icon_value of its recoloured triangle copy
