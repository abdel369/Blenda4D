# SPDX-License-Identifier: GPL-3.0-or-later
"""Edit several objects at once, as in C4D: with more than one object selected, a setting changed on the active
object (the one the Attribute Manager shows) is given to every other selected object of the same kind.

Only what was changed is copied, so selected objects keep their own values for everything else. Transforms are not
copied here: moving, turning or scaling in the viewport already acts on every selected object."""
import bpy

SKIP_PROPS = {"b4d_om_closed"}           # the Object Manager's fold state belongs to each row


def _own_mod(ob):
    """The Blenda node modifier that makes the object (a primitive, a generator, MoText...)."""
    for m in ob.modifiers:
        if m.type == "NODES" and m.node_group is not None and m.node_group.name.startswith("Blenda "):
            return m
    return None


def _skip_sockets():
    from .primitives import MATERIAL_SOCKET, USE_MATERIAL_SOCKET
    return {"Geometry", MATERIAL_SOCKET, USE_MATERIAL_SOCKET}       # materials come from each object's own tags


def _plain(v):
    if isinstance(v, (str, bytes, bool, int, float)) or v is None or isinstance(v, bpy.types.ID):
        return v
    try:
        return tuple(v)
    except TypeError:
        return v


def _values(ob):
    """Every setting that can be shared: Blenda's own object settings and the inputs of its node modifier."""
    out = {}
    for p in ob.bl_rna.properties:
        k = p.identifier
        if not k.startswith("b4d_") or k in SKIP_PROPS or p.type == "COLLECTION" or p.is_readonly:
            continue
        try:
            out[("prop", k)] = _plain(getattr(ob, k))
        except Exception:
            pass
    mod = _own_mod(ob)
    if mod is not None:
        from .primitives import input_slot
        skip = _skip_sockets()
        for it in mod.node_group.interface.items_tree:
            if it.item_type != "SOCKET" or it.in_out != "INPUT" or it.name in skip:
                continue
            try:
                owner, attr = input_slot(mod, it.identifier)
                out[("in", it.name)] = _plain(getattr(owner, attr) if attr == "value" else mod.get(it.identifier))
            except Exception:
                pass
    return out


def _set(ob, key, value):
    kind, name = key
    if kind == "prop":
        if _plain(getattr(ob, name, None)) != value:
            setattr(ob, name, value)
        return
    mod = _own_mod(ob)
    if mod is None or name not in mod.node_group.interface.items_tree:
        return
    from .primitives import input_slot, set_input
    ident = mod.node_group.interface.items_tree[name].identifier
    owner, attr = input_slot(mod, ident)
    now = getattr(owner, attr) if attr == "value" else mod.get(ident)
    if _plain(now) != value:
        set_input(mod, ident, value)
        ob.update_tag()                 # a value set through properties.inputs does not tag the object


def _kind(ob):
    return ob.get("b4d_type") or ob.type


_seen = {"ob": None, "vals": {}}
_busy = [False]


@bpy.app.handlers.persistent
def _on_update(scene, _depsgraph=None):
    if _busy[0]:
        return
    try:
        layer = bpy.context.view_layer
        act = layer.objects.active
    except AttributeError:
        return
    if act is None:
        _seen["ob"], _seen["vals"] = None, {}
        return
    try:
        vals = _values(act)
    except ReferenceError:
        return
    if _seen["ob"] != act.name:                        # another object became active: just remember its values
        _seen["ob"], _seen["vals"] = act.name, vals
        return
    changed = {k: v for k, v in vals.items() if k in _seen["vals"] and _seen["vals"][k] != v}
    _seen["vals"] = vals
    if not changed:
        return
    kind = _kind(act)
    others = [o for o in layer.objects if o != act and o.select_get() and _kind(o) == kind]
    if not others:
        return
    _busy[0] = True
    try:
        for o in others:
            for k, v in changed.items():
                try:
                    _set(o, k, v)
                except Exception:
                    pass
    finally:
        _busy[0] = False


@bpy.app.handlers.persistent
def _loaded(*_args):
    _seen["ob"], _seen["vals"] = None, {}


def register():
    if _on_update not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_update)
    if _loaded not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_loaded)


def unregister():
    if _on_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_update)
    if _loaded in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_loaded)
