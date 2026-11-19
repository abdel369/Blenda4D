# SPDX-License-Identifier: GPL-3.0-or-later
"""The Asset Browser's data: asset libraries, their folders (Blender asset catalogs) and a cached index of their assets.

Folders are Blender's own asset catalogs, kept in each library's blender_assets.cats.txt, so they belong to the library
and show in Blender's own Asset Browser as well. What a library holds is read by a background Blender
(assets_worker.py index) into an index file with one preview picture per asset; nothing is read into the open scene.
Files added to a library are turned into assets by the same worker (assets_worker.py add), a few at a time."""
import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid

import bpy

CATS = "blender_assets.cats.txt"
HEADER = ("# This is an Asset Catalog Definition file for Blender.\n#\n"
          "# Empty lines and lines starting with `#` will be ignored.\n"
          "# The first non-ignored line should be the version indicator.\n"
          '# Other lines are of the format "UUID:catalog/path/for/assets:simple catalog name"\n\nVERSION 1\n\n')
WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets_worker.py")
USER_LIBRARY = "User Library"
ESSENTIALS = "Essentials"
NO_CATALOG = "00000000-0000-0000-0000-000000000000"
PARALLEL = 2

MODELS = (".obj", ".fbx", ".glb", ".gltf", ".stl", ".ply", ".usd", ".usda", ".usdc", ".usdz", ".abc", ".svg")
PICTURES = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp", ".tga")
SKIES = (".hdr", ".exr")
EXTENSIONS = MODELS + PICTURES + SKIES + (".blend", ".vdb")

# What each tab shows, by the bpy.data collection the asset lives in.
TAB_TYPES = {"MODELS": ("objects", "collections"), "MATERIALS": ("materials",), "NODES": ("node_groups",),
             "SCENES": ("scenes",), "HDRIS": ("worlds",), "POSES": ("actions",), "BRUSHES": ("brushes",)}
TYPE_ICON = {"objects": "OBJECT_DATA", "collections": "OUTLINER_COLLECTION", "materials": "MATERIAL",
             "node_groups": "NODETREE", "scenes": "SCENE_DATA", "worlds": "WORLD", "actions": "ACTION",
             "brushes": "BRUSH_DATA"}


# --- libraries ------------------------------------------------------------------------------------------------------

def _writable(path):
    """A folder files may be added to: never one inside Blender's own installation."""
    if not (os.path.isdir(path) and os.access(path, os.W_OK)):
        return False
    real = os.path.realpath(path)
    for root in (bpy.utils.resource_path("LOCAL"), bpy.utils.resource_path("SYSTEM"),
                 os.path.dirname(os.path.dirname(bpy.app.binary_path))):
        if root and (real + os.sep).startswith(os.path.realpath(root) + os.sep):
            return False
    return True


def libraries():
    """[(name, path, writable)]: the person's asset libraries (Preferences > File Paths), then Blender's Essentials."""
    out = []
    for lib in bpy.context.preferences.filepaths.asset_libraries:
        path = bpy.path.abspath(lib.path)
        if lib.name and path:
            out.append((lib.name, path, _writable(path)))
    ess = bpy.utils.system_resource("DATAFILES", path="assets")
    if ess and os.path.isdir(ess):
        out.append((ESSENTIALS, ess, False))
    return out


def library(name):
    return next((lib for lib in libraries() if lib[0] == name), None)


def import_method(name):
    lib = bpy.context.preferences.filepaths.asset_libraries.get(name)
    return lib.import_method if lib is not None else "APPEND_REUSE"


def target_library(shown):
    """(name, path) that new folders and added files go to: the library shown when it can be written to, else the
    first one that can, else a new User Library in the usual place."""
    lib = library(shown)
    if lib and lib[2]:
        return lib[0], lib[1]
    for name, path, ok in libraries():
        if ok:
            return name, path
    libs = bpy.context.preferences.filepaths.asset_libraries
    path = os.path.join(os.path.expanduser("~"), "Documents", "Blender", "Assets")
    os.makedirs(path, exist_ok=True)
    lib = libs.get(USER_LIBRARY)
    if lib is None:
        try:
            lib = libs.new(name=USER_LIBRARY, directory=path)
        except (AttributeError, TypeError):
            bpy.ops.preferences.asset_library_add(directory=path)
            lib = libs[-1]
            lib.name = USER_LIBRARY
    if not os.path.isdir(bpy.path.abspath(lib.path)):
        lib.path = path
    return lib.name, bpy.path.abspath(lib.path)


# --- folders (asset catalogs) ---------------------------------------------------------------------------------------

def read_catalogs(lib_path):
    """[(uuid, path, simple name)] of a library's folders."""
    out = []
    try:
        with open(os.path.join(lib_path, CATS), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("VERSION"):
                    continue
                parts = line.split(":")
                if len(parts) >= 2 and parts[1]:
                    out.append((parts[0], parts[1], parts[2] if len(parts) > 2 else ""))
    except OSError:
        pass
    return out


def _write_catalogs(lib_path, rows):
    file = os.path.join(lib_path, CATS)
    if os.path.exists(file):
        shutil.copy2(file, file + ".bak")                # one step back, should an edit go wrong
    tmp = file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(HEADER)
        for cid, path, simple in rows:
            f.write(f"{cid}:{path}:{simple}\n")
    os.replace(tmp, file)


def add_catalog(lib_path, path):
    """A folder at path ("Materials/Metal"), with any parent folders it needs; returns its id."""
    rows = read_catalogs(lib_path)
    have = {p: u for u, p, _s in rows}
    parts = [p.strip() for p in path.split("/") if p.strip()]
    cid = None
    for i in range(len(parts)):
        sub = "/".join(parts[:i + 1])
        cid = have.get(sub)
        if cid is None:
            cid = str(uuid.uuid4())
            rows.append((cid, sub, sub.replace("/", "-")))
            have[sub] = cid
    if cid is not None:
        _write_catalogs(lib_path, rows)
    return cid


def rename_catalog(lib_path, old, new_name):
    """Rename the last part of a folder's path; its sub-folders move with it. Returns the new path."""
    new_name = new_name.replace("/", "-").replace(":", "-").strip()
    if not new_name:
        return old
    parent = old.rsplit("/", 1)[0] if "/" in old else ""
    new = f"{parent}/{new_name}" if parent else new_name
    rows = []
    for u, p, s in read_catalogs(lib_path):
        if p == old or p.startswith(old + "/"):
            p = new + p[len(old):]
            s = p.replace("/", "-")
        rows.append((u, p, s))
    _write_catalogs(lib_path, rows)
    return new


def delete_catalog(lib_path, path):
    """Remove a folder and its sub-folders from the list. The assets in them stay in the library (as Uncategorized)."""
    rows = [r for r in read_catalogs(lib_path) if not (r[1] == path or r[1].startswith(path + "/"))]
    _write_catalogs(lib_path, rows)


def unique_folder(lib_path, base="New Folder", parent=""):
    taken = {p for _u, p, _s in read_catalogs(lib_path)}
    name, n = base, 2
    while (f"{parent}/{name}" if parent else name) in taken:
        name, n = f"{base} {n}", n + 1
    return f"{parent}/{name}" if parent else name


# --- index ----------------------------------------------------------------------------------------------------------

def cache_root():
    return bpy.utils.user_resource("CONFIG", path=os.path.join("blenda4d", "assets"), create=True)


def cache_dir(lib_path):
    key = hashlib.sha1(os.path.normpath(lib_path).encode("utf-8")).hexdigest()[:12]
    d = os.path.join(cache_root(), key)
    os.makedirs(d, exist_ok=True)
    return d


_index = {}          # library path -> (index file mtime, [asset entries])


def assets(lib_path):
    """The assets of a library as the last index read them: dicts with name, type (bpy.data collection), blend,
    catalog, tags, description, preview (a picture file or ""), mtime."""
    file = os.path.join(cache_dir(lib_path), "index.json")
    try:
        mt = os.path.getmtime(file)
    except OSError:
        return []
    have = _index.get(lib_path)
    if have and have[0] == mt:
        return have[1]
    try:
        with open(file, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return have[1] if have else []
    rows = []
    for blend, rec in data.get("blends", {}).items():
        for a in rec.get("assets", []):
            a = dict(a)
            a["blend"] = blend
            a["mtime"] = rec.get("mtime", 0)
            a["library"] = lib_path
            rows.append(a)
    rows.sort(key=lambda a: a["name"].lower())
    _index[lib_path] = (mt, rows)
    return rows


def key_of(a):
    return f"{a['blend']}|{a['type']}|{a['name']}"


def find(key):
    blend, typ, name = key.split("|", 2)
    for _n, path, _w in libraries():
        for a in assets(path):
            if a["blend"] == blend and a["type"] == typ and a["name"] == name:
                return a
    return None


# --- background Blenders -------------------------------------------------------------------------------------------

_jobs = []           # add jobs waiting: dicts
_running = []        # (process, job or None, log file, library path)
_wanted_index = []   # library paths to read again once nothing is adding to them
_progress = {"ok": 0, "failed": [], "total": 0}
_listeners = []      # called after any index or add finishes


def _blender(args, log_path):
    log = open(log_path, "w")
    proc = subprocess.Popen([bpy.app.binary_path, "-b", "--factory-startup", "--python", WORKER, "--", *args],
                            stdout=log, stderr=subprocess.STDOUT)
    return proc, log


def index_library(lib_path):
    """Read the library again in the background (only .blend files that changed are opened)."""
    if lib_path not in _wanted_index:
        _wanted_index.append(lib_path)
    _wake()


def indexing(lib_path=None):
    return any(job is None and (lib_path is None or lp == lib_path) for _p, job, _l, lp in _running)


def add_files(files, lib_path, out_dir, catalog_id):
    if not _jobs and not any(j for _p, j, _l, _lp in _running if j):
        _progress.update(ok=0, failed=[], total=0)
    tmp = os.path.join(cache_root(), "jobs")
    os.makedirs(tmp, exist_ok=True)
    for f in files:
        stamp = f"{int(time.time() * 1000)}_{len(_jobs)}_{uuid.uuid4().hex[:6]}"
        job = {"file": f, "out_dir": out_dir, "catalog_id": catalog_id or "", "tmp": tmp, "library": lib_path,
               "job": os.path.join(tmp, stamp + ".json"), "result": os.path.join(tmp, stamp + "_result.json")}
        with open(job["job"], "w", encoding="utf-8") as fh:
            json.dump(job, fh)
        _jobs.append(job)
        _progress["total"] += 1
    _wake()


def _wake():
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=0.05)


def _tick():
    changed = False
    for item in list(_running):
        proc, job, log, lib_path = item
        if proc.poll() is None:
            continue
        _running.remove(item)
        log.close()
        changed = True
        if job is None:
            continue
        try:
            with open(job["result"], encoding="utf-8") as f:
                res = json.load(f)
        except (OSError, ValueError):
            res = {"ok": False, "error": "the background Blender stopped"}
        if res.get("ok"):
            _progress["ok"] += 1
        else:
            _progress["failed"].append(f"{os.path.basename(job['file'])}: {res.get('error')}")
            print("Blenda 4D: could not add", job["file"], "-", res.get("error"))
        if lib_path not in _wanted_index:
            _wanted_index.append(lib_path)
    adds = [j for _p, j, _l, _lp in _running if j]
    while _jobs and len(adds) < PARALLEL:
        job = _jobs.pop(0)
        proc, log = _blender(["add", job["job"]], job["job"][:-5] + ".log")
        _running.append((proc, job, log, job["library"]))
        adds.append(job)
    for lib_path in list(_wanted_index):
        busy = indexing(lib_path) or any(j["library"] == lib_path for j in _jobs)
        if busy:
            continue
        _wanted_index.remove(lib_path)
        d = cache_dir(lib_path)
        proc, log = _blender(["index", lib_path, d], os.path.join(d, "index.log"))
        _running.append((proc, None, log, lib_path))
    if changed:
        for fn in list(_listeners):
            try:
                fn()
            except Exception as ex:
                print("Blenda 4D:", ex)
    if _running or _jobs or _wanted_index:
        return 0.3
    if _progress["failed"]:
        print("Blenda 4D: assets not added:", "; ".join(_progress["failed"]))
    return None


def busy():
    return bool(_running or _jobs or _wanted_index)


def status():
    """A line for the browser while files are being added, else ''."""
    total = _progress["total"]
    if not (_jobs or any(j for _p, j, _l, _lp in _running if j)) or not total:
        return ""
    at = _progress["ok"] + len(_progress["failed"]) + 1
    return f"Adding assets: {min(at, total)} of {total}"


def failures():
    return list(_progress["failed"])


def pause():
    """Blenda mode going off: stop watching. Background Blenders already running finish their file (nothing is cut off
    half-written); waiting files stay queued and start when the browser is back."""
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)


def resume():
    if busy():
        _wake()
