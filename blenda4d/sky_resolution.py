# SPDX-License-Identifier: GPL-3.0-or-later
"""The Sky page's Resolution row: switch an HDRI between 1K, 2K, 4K, 8K and 16K.

Works for HDRIs named the Poly Haven way (name_2k.hdr / name_4k.exr). A size already on disk beside the file is used
at once; a missing one is downloaded from Poly Haven next to it, in the background, only when Blender's
Preferences > System > Allow Online Access is on. Downloads touch files only on their thread; Blender data changes
on the main thread through a timer."""
import json
import os
import re
import threading
import urllib.request

import bpy

SIZES = ("1k", "2k", "4k", "8k", "16k")
_NAMED = re.compile(r"^(.+)_(\d+k)\.(hdr|exr)$", re.I)
_jobs = {}            # target path -> {"res", "got", "size", "done", "error", "scene"}
_errors = {}          # scene name -> last error


def named(image):
    """(folder, name, extension) of a size-named file, or None when the name says nothing."""
    if image is None or not image.filepath:
        return None
    path = bpy.path.abspath(image.filepath)
    m = _NAMED.match(os.path.basename(path))
    return (os.path.dirname(path), m.group(1), m.group(3).lower()) if m else None


def _open(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Blenda4D"}), timeout=60)


def _fetch(job, name, res, ext, path):
    part = path + ".part"
    try:
        with _open(f"https://api.polyhaven.com/files/{name}") as r:
            files = json.load(r).get("hdri", {})
        entry = files.get(res, {}).get(ext)
        if entry is None:
            job["error"] = f"Poly Haven has no {res.upper()} of this HDRI"
            return
        job["size"] = entry.get("size", 0)
        with _open(entry["url"]) as r, open(part, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
                job["got"] += len(chunk)
        os.replace(part, path)
    except Exception as ex:
        job["error"] = f"Download failed: {ex}"
        if os.path.exists(part):
            os.remove(part)
    finally:
        job["done"] = True


def _use(scene, path):
    """Put the file in the Sky's HDRI slot; the old image goes when nothing else uses it."""
    old = scene.b4d_sky_image
    new = bpy.data.images.load(path, check_existing=True)
    if old is not None:
        new.colorspace_settings.name = old.colorspace_settings.name
    scene.b4d_sky_image = new
    if old is not None and old != new and old.users == 0:
        bpy.data.images.remove(old)


def _redraw():
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            a.tag_redraw()


def _watch():
    for path, job in list(_jobs.items()):
        if job["done"]:
            del _jobs[path]
            scene = bpy.data.scenes.get(job["scene"])
            if job["error"]:
                _errors[job["scene"]] = job["error"]
            elif scene is not None:
                _use(scene, path)
    _redraw()
    return 0.25 if _jobs else None


class BLENDA4D_OT_sky_resolution(bpy.types.Operator):
    """Use this size of the HDRI. A size not on disk yet is downloaded from Poly Haven beside the current file"""
    bl_idname = "blenda4d.sky_resolution"
    bl_label = "HDRI Resolution"
    bl_options = {"INTERNAL", "UNDO"}
    res: bpy.props.StringProperty()

    def execute(self, context):
        scene = context.scene
        where = named(scene.b4d_sky_image)
        if where is None or self.res not in SIZES:
            return {"CANCELLED"}
        folder, name, ext = where
        _errors.pop(scene.name, None)
        path = os.path.join(folder, f"{name}_{self.res}.{ext}")
        if os.path.exists(path):
            _use(scene, path)
            return {"FINISHED"}
        if not bpy.app.online_access:
            _errors[scene.name] = "Turn on Online Access in Preferences"
            return {"CANCELLED"}
        if path in _jobs:
            return {"CANCELLED"}
        job = _jobs[path] = {"res": self.res, "got": 0, "size": 0, "done": False, "error": "", "scene": scene.name}
        threading.Thread(target=_fetch, args=(job, name, self.res, ext, path), daemon=True).start()
        if not bpy.app.timers.is_registered(_watch):
            bpy.app.timers.register(_watch, first_interval=0.25)
        return {"FINISHED"}


def draw(col, scene):
    """The Resolution row, drawn under the HDRI slot on the Sky page."""
    image = scene.b4d_sky_image
    if image is None:
        return
    sp = col.split(factor=0.4)
    left = sp.row()
    left.alignment = "RIGHT"
    left.label(text="Resolution")
    where = named(image)
    if where is None:                                # the file name says nothing about other sizes
        sp.label(text=f"{image.size[0]} x {image.size[1]}")
        return
    now = f"{round(image.size[0] / 1024)}k" if image.size[0] else ""
    busy = [j for j in _jobs.values() if j["scene"] == scene.name]
    row = sp.row(align=True)
    row.enabled = not busy
    for res in SIZES:
        row.operator(BLENDA4D_OT_sky_resolution.bl_idname, text=res.upper(), depress=res == now).res = res
    if busy:
        j = busy[0]
        msg = (f"Downloading {j['res'].upper()}: {j['got'] / 1e6:.0f} of {j['size'] / 1e6:.0f} MB" if j["size"]
               else f"Downloading {j['res'].upper()}...")
        col.split(factor=0.4).row().label(text="")
        col.label(text=msg, icon="IMPORT")
    elif scene.name in _errors:
        col.label(text=_errors[scene.name], icon="ERROR")


def register():
    bpy.utils.register_class(BLENDA4D_OT_sky_resolution)


def unregister():
    if bpy.app.timers.is_registered(_watch):
        bpy.app.timers.unregister(_watch)
    bpy.utils.unregister_class(BLENDA4D_OT_sky_resolution)
