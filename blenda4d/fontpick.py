# SPDX-License-Identifier: GPL-3.0-or-later
"""Pick a font by name from every font installed on the computer, as C4D's Font field does.

Blender's own font field lists only the fonts already loaded into the .blend, so on a new scene it offers nothing but
its built-in font. This list reads the installed font files once (their family and style names from each file's own
name table), shows them in a search menu, and loads the chosen file when it is picked."""
import os
import struct
import sys

import bpy

EXTS = (".ttf", ".otf", ".ttc", ".pfb")


def _dirs():
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        return ["/System/Library/Fonts", "/System/Library/Fonts/Supplemental", "/Library/Fonts",
                os.path.join(home, "Library/Fonts")]
    if sys.platform == "win32":
        win = os.environ.get("WINDIR", r"C:\Windows")
        return [os.path.join(win, "Fonts"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts")]
    return ["/usr/share/fonts", "/usr/local/share/fonts", os.path.join(home, ".fonts"),
            os.path.join(home, ".local/share/fonts")]


def _names(path):
    """(family, style) from the font's name table; None when the file can't be read."""
    try:
        with open(path, "rb") as f:
            data = f.read(1 << 16)
            if b"name" in data[:4096]:                      # the name table often sits past the first 64 KB
                i = data.find(b"name", 0, 4096)
                toff = struct.unpack(">I", data[i + 8:i + 12])[0]
                tlen = struct.unpack(">I", data[i + 12:i + 16])[0]
                if toff + tlen > len(data):
                    f.seek(0)
                    data = f.read(toff + tlen)
        off = 0
        if data[:4] == b"ttcf":
            off = struct.unpack(">I", data[12:16])[0]
        num = struct.unpack(">H", data[off + 4:off + 6])[0]
        for i in range(num):
            rec = off + 12 + 16 * i
            if data[rec:rec + 4] != b"name":
                continue
            toff = struct.unpack(">I", data[rec + 8:rec + 12])[0]
            count, sbase = struct.unpack(">HH", data[toff + 2:toff + 6])
            found = {}
            for k in range(count):
                r = toff + 6 + 12 * k
                pid, eid, lang, nid, ln, so = struct.unpack(">HHHHHH", data[r:r + 12])
                if nid not in (1, 2, 16, 17):
                    continue
                raw = data[toff + sbase + so:toff + sbase + so + ln]
                if pid == 3 or pid == 0:
                    if pid == 3 and lang not in (0x409, 0):
                        continue
                    s = raw.decode("utf-16-be", "ignore")
                else:
                    s = raw.decode("latin-1", "ignore")
                found.setdefault(nid, s)
            fam = found.get(16) or found.get(1)
            sty = found.get(17) or found.get(2) or "Regular"
            return (fam, sty) if fam else None
    except (OSError, struct.error, IndexError):
        return None
    return None


_cache = {"items": None}


def font_files():
    """[(path, label)] of every installed font, sorted by family then style; read once per session."""
    if _cache["items"] is None:
        seen, out = set(), []
        for d in _dirs():
            if not os.path.isdir(d):
                continue
            for root, _dirs_, files in os.walk(d):
                for fn in files:
                    if not fn.lower().endswith(EXTS):
                        continue
                    p = os.path.join(root, fn)
                    n = _names(p) if not fn.lower().endswith(".pfb") else None
                    label = f"{n[0]} {n[1]}" if n else os.path.splitext(fn)[0]
                    if n and n[1].lower() == "regular":
                        label = n[0]
                    if label.startswith(".") or label in seen:     # ".SF NS" etc. are macOS's hidden UI fonts
                        continue
                    seen.add(label)
                    out.append((p, label))
        out.sort(key=lambda x: x[1].lower())
        _cache["items"] = out
    return _cache["items"]


_enum = []


def _items(self, context):
    _enum.clear()
    _enum.append(("<builtin>", "Bfont (Blender's own)", ""))
    for f in bpy.data.fonts:
        if not f.filepath or f.filepath == "<builtin>":
            continue
        path = bpy.path.abspath(f.filepath)
        if not any(path == p for p, _l in font_files()):
            _enum.append((path, f"{f.name}  (in this file)", ""))
    for p, label in font_files():
        _enum.append((p, label, p))
    return _enum


def load(path):
    """The VectorFont for a font file (loaded once) or Blender's built-in font."""
    if path == "<builtin>":
        for f in bpy.data.fonts:
            if f.filepath == "<builtin>":
                return f
        return bpy.data.fonts.load("<builtin>", check_existing=True)
    for f in bpy.data.fonts:
        if f.filepath and os.path.normpath(bpy.path.abspath(f.filepath)) == os.path.normpath(path):
            return f
    return bpy.data.fonts.load(path, check_existing=True)


def label(font):
    """What the field shows for the font in use."""
    if font is None:
        return "Choose a font"
    if font.filepath and font.filepath != "<builtin>":
        n = _names(bpy.path.abspath(font.filepath))
        if n:
            return n[0] if n[1].lower() == "regular" else f"{n[0]} {n[1]}"
    return font.name


def _targets(context, owner):
    """The selected objects the font goes to: MoTexts (owner 'motext') or Text splines (owner 'text')."""
    act = context.view_layer.objects.active
    sel = [o for o in context.view_layer.objects if o.select_get()]
    if act is not None and act not in sel:
        sel.append(act)
    if owner == "motext":
        return [o for o in sel if o.get("b4d_type") == "motext"]
    return [o for o in sel if o.type == "FONT"]


def apply(context, owner, font):
    for o in _targets(context, owner):
        if owner == "motext":
            if o.b4d_motext_font != font:
                o.b4d_motext_font = font
        elif o.data.font != font:
            o.data.font = font


class BLENDA4D_OT_font_pick(bpy.types.Operator):
    """Choose the font from every font installed on this computer"""
    bl_idname = "blenda4d.font_pick"
    bl_label = "Font"
    bl_property = "font"
    bl_options = {"REGISTER", "UNDO"}

    font: bpy.props.EnumProperty(name="Font", items=_items)
    owner: bpy.props.StringProperty(default="motext", options={"HIDDEN", "SKIP_SAVE"})

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        try:
            f = load(self.font)
        except (RuntimeError, OSError) as e:
            self.report({"WARNING"}, f"Could not load that font: {e}")
            return {"CANCELLED"}
        apply(context, self.owner, f)
        return {"FINISHED"}


class BLENDA4D_OT_font_file(bpy.types.Operator):
    """Load a font file that is not installed (a .ttf, .otf or .pfb anywhere on disk)"""
    bl_idname = "blenda4d.font_file"
    bl_label = "Load Font File"
    bl_options = {"REGISTER", "UNDO"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.ttf;*.otf;*.ttc;*.pfb", options={"HIDDEN"})
    filter_font: bpy.props.BoolProperty(default=True, options={"HIDDEN"})
    filter_folder: bpy.props.BoolProperty(default=True, options={"HIDDEN"})
    owner: bpy.props.StringProperty(default="motext", options={"HIDDEN", "SKIP_SAVE"})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        try:
            f = bpy.data.fonts.load(self.filepath, check_existing=True)
        except (RuntimeError, OSError) as e:
            self.report({"WARNING"}, f"Could not load that font: {e}")
            return {"CANCELLED"}
        apply(context, self.owner, f)
        return {"FINISHED"}


def draw(layout, font, owner):
    """The Font field: the font's name as a drop-down of installed fonts, and a folder button for a font file."""
    r = layout.row(align=True)
    op = r.operator(BLENDA4D_OT_font_pick.bl_idname, text=label(font), icon="FONT_DATA")
    op.owner = owner
    r.operator(BLENDA4D_OT_font_file.bl_idname, text="", icon="FILEBROWSER").owner = owner


CLASSES = (BLENDA4D_OT_font_pick, BLENDA4D_OT_font_file)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
