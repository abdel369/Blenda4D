# SPDX-License-Identifier: GPL-3.0-or-later
"""Swap only a Blender header's *own* draw function, as the Maya Workflow Kit does (GPL, src/allset/ui/own_draw.py).

Once anything is appended or prepended to a header, Blender keeps its draw functions in a list
(bpy_types._GenericUI._dyn_ui_initialize). Blenda replaces only Blender's own entry in that list, never the class's
draw attribute, so other add-ons' appended or prepended header items keep drawing; restore() puts Blender's function
back where it was, even if other add-ons extended the header after Blenda did."""
import bpy

_saved = {}   # (class name, Blenda function) -> Blender's own draw


def _funcs(cls_name):
    return getattr(bpy.types, cls_name)._dyn_ui_initialize()


def _own_index(cls_name, funcs):
    """Index of the class's own draw (something may have been prepended before it)."""
    for i, f in enumerate(funcs):
        if getattr(f, "__qualname__", "") == f"{cls_name}.draw":
            return i
    return 0


def swap(cls_name, fn):
    """Put fn where cls_name's own draw is; returns Blender's own draw."""
    key = (cls_name, fn)
    funcs = _funcs(cls_name)
    if key in _saved and fn in funcs:
        return _saved[key]
    i = _own_index(cls_name, funcs)
    _saved[key] = funcs[i]
    funcs[i] = fn
    return _saved[key]


def restore(cls_name, fn):
    """Blender's own draw back in place of fn (wherever fn is now)."""
    own = _saved.pop((cls_name, fn), None)
    if own is None:
        return
    funcs = _funcs(cls_name)
    if fn in funcs:
        funcs[funcs.index(fn)] = own
