# SPDX-License-Identifier: GPL-3.0-or-later
"""The person's own Blender preferences, kept safe while Blenda mode changes some of them (Region Overlap, the corner
and region toggles, the render window, theme colours).

Blender can auto-save its preferences at any moment, so the values Blenda sets can be written to the person's
userpref.blend. Keeping the originals in memory only was not enough: after a restart Blenda took its own values for
the originals, and switching to Blender mode or removing the add-on left Region Overlap off (grey strips around the
viewport) and Blenda's colours in place. So the originals are written to a file the moment Blenda changes them, read
back instead of the current values on the next start, put back by Blender mode or by switching the add-on off, and
the file is deleted once they are back. Preferences are then marked changed so Blender's auto-save keeps them."""
import json
import os

import bpy

_disk = {}        # originals from the file (an earlier session that ended in Blenda mode)
_rec = {}         # originals recorded in this session
_paths = {}       # struct pointer -> its path from bpy.context.preferences


def _file():
    folder = bpy.utils.user_resource("CONFIG", path="blenda4d", create=True)
    return os.path.join(folder, "blender_preferences.json")


def _load():
    try:
        with open(_file()) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save():
    try:
        with open(_file(), "w") as f:
            json.dump({**_disk, **_rec}, f, indent=0)
    except (OSError, TypeError, ValueError) as e:
        print("Blenda 4D: could not keep Blender's preferences", e)


def _plain(value):
    if isinstance(value, (str, bool, int)):
        return value
    try:
        return [float(v) for v in value]
    except TypeError:
        return value


def _walk(struct, path, depth):
    _paths[struct.as_pointer()] = path
    if depth == 0:
        return
    for prop in struct.bl_rna.properties:
        if prop.type != "POINTER" or prop.identifier == "rna_type":
            continue
        try:
            sub = getattr(struct, prop.identifier)
        except AttributeError:
            continue
        if sub is not None and sub.as_pointer() not in _paths:
            _walk(sub, path + "." + prop.identifier, depth - 1)


def begin():
    """Before Blenda mode changes any preference."""
    _disk.clear()
    _disk.update(_load())
    _paths.clear()
    p = bpy.context.preferences
    for name in ("system", "apps", "view", "edit", "inputs"):
        s = getattr(p, name, None)
        if s is not None:
            _paths[s.as_pointer()] = name
    if len(p.themes):
        _walk(p.themes[0], "themes[0]", 4)


def _key(owner, attr):
    path = _paths.get(owner.as_pointer())
    return None if path is None else path + "::" + attr


def original(owner, attr, current, blenda_value=None):
    """The person's own value for owner.attr: the one kept on disk when there is one, else the current value. A
    preference that already holds Blenda's value with nothing on disk (saved by an older Blenda 4D) gets Blender's
    default instead, when Blender has one."""
    key = _key(owner, attr)
    if key is None:
        return current
    if key in _disk:
        value = _disk[key]
        value = tuple(value) if isinstance(value, list) else value
    else:
        value = current
        if blenda_value is not None and _same(current, blenda_value):
            prop = owner.bl_rna.properties.get(attr)
            if prop is not None and prop.type in {"BOOLEAN", "ENUM"}:
                value = prop.default
    _rec.setdefault(key, _plain(value))
    return value


def _same(a, b):
    if isinstance(a, str) or isinstance(b, str):
        return a == b
    try:
        return all(abs(float(x) - float(y)) < 1e-4 for x, y in zip(a, b)) and len(tuple(a)) == len(tuple(b))
    except TypeError:
        return a == b


def commit():
    """After Blenda mode has made its changes: the originals go to disk at once."""
    _save()


def finish():
    """The originals are back: forget them and let Blender's auto-save write the person's preferences."""
    _disk.clear()
    _rec.clear()
    try:
        os.remove(_file())
    except OSError:
        pass
    try:
        bpy.context.preferences.is_dirty = True
    except (AttributeError, TypeError):
        pass


def put_back_from_disk():
    """Put back whatever the file still holds (Blenda mode was never switched off cleanly). Used when the add-on is
    switched off or removed while Blender mode is showing."""
    data = _load()
    if not data:
        return
    p = bpy.context.preferences
    for key, value in data.items():
        path, _, attr = key.partition("::")
        try:
            owner = p.path_resolve(path)
            setattr(owner, attr, tuple(value) if isinstance(value, list) else value)
        except (ValueError, TypeError, AttributeError):
            pass
    finish()


def original_unknown(owner, attr):
    """Nothing is kept on disk for owner.attr."""
    key = _key(owner, attr)
    return key is not None and key not in _disk
