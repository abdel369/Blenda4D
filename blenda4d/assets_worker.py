# SPDX-License-Identifier: GPL-3.0-or-later
"""Background work for the Asset Browser, in a hidden Blender so the open scene is never touched.

  Blender -b --factory-startup --python assets_worker.py -- index <library folder> <cache folder>
      Reads the assets of every .blend in the library that changed since the last time (linked, never appended) and
      writes <cache folder>/index.json with each asset's name, type, folder, tags and a preview picture.
  Blender -b --factory-startup --python assets_worker.py -- add <job.json>
      Turns one file into an asset: models are read with Blender's importers, pictures become a material (.hdr/.exr a
      world), .blend files give their assets (or their objects), OpenVDB files a volume object with a plain volume
      material. The asset is marked, put in its folder, given a preview (a same-named picture beside the file, else a
      small render) and written as its own .blend into the library. Pictures are packed into it; volume grids are
      copied beside it.
This file uses only Blender's own Python API; it does not load the add-on."""
import hashlib
import json
import math
import os
import shutil
import sys
import traceback

import bpy
from mathutils import Vector

PICTURES = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp", ".tga")
SKIES = (".hdr", ".exr")
PREVIEW = 256
KINDS = ("objects", "collections", "materials", "node_groups", "worlds", "scenes", "actions", "brushes")


# --- index ----------------------------------------------------------------------------------------------------------

def _blends(root):
    for d, dirs, names in os.walk(root):
        dirs[:] = sorted(x for x in dirs if not x.startswith("."))
        for n in sorted(names):
            if n.lower().endswith(".blend") and not n.startswith("."):
                yield os.path.join(d, n)


def _save_preview(pv, png):
    w, h = pv.image_size
    if w <= 0 or h <= 0:
        return False
    img = bpy.data.images.new("b4d preview", w, h, alpha=True)
    img.pixels.foreach_set(pv.image_pixels_float[:])
    img.filepath_raw = png
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    return True


def _read_blend(path, cache):
    out = []
    before = set(bpy.data.libraries)
    with bpy.data.libraries.load(path, link=True, assets_only=True) as (src, dst):
        for kind in KINDS:
            setattr(dst, kind, list(getattr(src, kind)))
    for kind in KINDS:
        for b in getattr(dst, kind):
            if b is None or b.asset_data is None:
                continue
            ad = b.asset_data
            png = os.path.join(cache, hashlib.sha1(f"{path}|{kind}|{b.name}".encode("utf-8")).hexdigest()[:16] + ".png")
            pv = b.preview
            has = bool(pv is not None and _save_preview(pv, png))
            out.append({"name": b.name, "type": kind, "catalog": ad.catalog_id, "tags": [t.name for t in ad.tags],
                        "description": ad.description, "preview": png if has else ""})
    for lib in set(bpy.data.libraries) - before:     # let go of what was read before the next file
        bpy.data.libraries.remove(lib)
    return out


def index(root, cache):
    file = os.path.join(cache, "index.json")
    try:
        with open(file, encoding="utf-8") as f:
            old = json.load(f).get("blends", {})
    except (OSError, ValueError):
        old = {}
    blends = {}
    for path in _blends(root):
        mt = os.path.getmtime(path)
        rec = old.get(path)
        if rec and rec.get("mtime") == mt and all(not a["preview"] or os.path.exists(a["preview"]) for a in rec["assets"]):
            blends[path] = rec
            continue
        try:
            blends[path] = {"mtime": mt, "assets": _read_blend(path, cache)}
        except Exception as ex:                       # one unreadable file never stops the rest
            print("could not read", path, ex)
            blends[path] = {"mtime": mt, "assets": [], "error": str(ex)}
    keep = {a["preview"] for rec in blends.values() for a in rec["assets"] if a["preview"]}
    for n in os.listdir(cache):
        p = os.path.join(cache, n)
        if n.endswith(".png") and p not in keep:
            os.remove(p)
    tmp = file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"library": root, "blends": blends}, f)
    os.replace(tmp, file)
    return len(blends)


# --- add: what the file becomes -------------------------------------------------------------------------------------

def _unique(folder, stem, ext):
    path = os.path.join(folder, stem + ext)
    n = 2
    while os.path.exists(path):
        path = os.path.join(folder, f"{stem} {n}{ext}")
        n += 1
    return path


def _picture_beside(path):
    """A preview the file came with: a same-named picture in its folder, or in a sibling previews folder."""
    folder, name = os.path.split(path)
    stem = os.path.splitext(name)[0]
    parent = os.path.dirname(folder)
    places = [folder]
    try:
        places += [os.path.join(parent, d) for d in sorted(os.listdir(parent)) if os.path.isdir(os.path.join(parent, d))
                   and d.lower() in ("png", "jpg", "preview", "previews", "thumbnails", "renders", "images")]
    except OSError:
        pass
    for place in places:
        for ext in PICTURES:
            for p in (os.path.join(place, stem + ext), os.path.join(place, stem + ext.upper())):
                if os.path.exists(p) and not os.path.samefile(p, path):   # not the file itself (any letter case)
                    return p
    return None


def _set_preview(block, image_path):
    """The picture, centre square, as the asset's preview."""
    img = bpy.data.images.load(image_path, check_existing=False)
    w, h = img.size
    if w <= 0 or h <= 0:
        raise ValueError("the preview picture is empty")
    k = PREVIEW / min(w, h)                          # scale first, so only a small picture is cropped
    sw, sh = max(PREVIEW, round(w * k)), max(PREVIEW, round(h * k))
    img.scale(sw, sh)
    px = img.pixels[:]
    x0, y0 = (sw - PREVIEW) // 2, (sh - PREVIEW) // 2
    sq = []
    for y in range(y0, y0 + PREVIEW):
        row = (y * sw + x0) * 4
        sq.extend(px[row:row + PREVIEW * 4])
    pv = block.preview_ensure()
    pv.image_size = (PREVIEW, PREVIEW)
    pv.image_pixels_float.foreach_set(sq)
    bpy.data.images.remove(img)


def _material(name):
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except AttributeError:
        pass
    return mat


def _from_picture(path, stem, ext):
    img = bpy.data.images.load(path)
    img.pack()
    if ext in SKIES:
        w = bpy.data.worlds.new(stem)
        try:
            w.use_nodes = True
        except AttributeError:
            pass
        nt = w.node_tree
        bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = img
        env.location = (bg.location.x - 300, bg.location.y)
        nt.links.new(env.outputs["Color"], bg.inputs["Color"])
        return w, "HDRI"
    mat = _material(stem)
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.location = (bsdf.location.x - 320, bsdf.location.y)
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return mat, "Texture"


def _from_volume(path, stem, out_dir, scene):
    grids = os.path.join(out_dir, stem + ".vdb")
    same = os.path.exists(grids) and os.path.getsize(grids) == os.path.getsize(path)
    if os.path.abspath(grids) != os.path.abspath(path) and not same:   # the same file already there is reused
        grids = _unique(out_dir, stem, ".vdb")
        shutil.copy2(path, grids)
    vol = bpy.data.volumes.new(stem)
    vol.filepath = grids
    ob = bpy.data.objects.new(stem, vol)
    scene.collection.objects.link(ob)
    mat = _material(stem + " Volume")
    nt = mat.node_tree
    for n in list(nt.nodes):
        if n.type == "BSDF_PRINCIPLED":
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    pv = nt.nodes.new("ShaderNodeVolumePrincipled")
    pv.location = (out.location.x - 300, out.location.y)
    nt.links.new(pv.outputs[0], out.inputs["Volume"])
    vol.materials.append(mat)
    try:
        vol.grids.load()
    except RuntimeError:
        pass
    if len(vol.grids) == 0:
        raise ValueError("the file holds no volume grids")
    return ob, "Volume"


_IMPORTERS = {".obj": ("wm", "obj_import"), ".fbx": ("import_scene", "fbx"), ".glb": ("import_scene", "gltf"),
              ".gltf": ("import_scene", "gltf"), ".stl": ("wm", "stl_import"), ".ply": ("wm", "ply_import"),
              ".usd": ("wm", "usd_import"), ".usda": ("wm", "usd_import"), ".usdc": ("wm", "usd_import"),
              ".usdz": ("wm", "usd_import"), ".abc": ("wm", "alembic_import"), ".svg": ("import_curve", "svg")}


def _group(objs, stem, scene):
    """One object becomes the asset; several become one collection asset that brings them all."""
    objs = [o for o in objs if o.type not in ("CAMERA", "LIGHT") or o.children]
    if not objs:
        raise ValueError("the file holds no objects")
    if len(objs) == 1:
        if objs[0].name not in scene.collection.all_objects:
            scene.collection.objects.link(objs[0])
        return objs[0]
    coll = bpy.data.collections.new(stem)
    for o in objs:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
    scene.collection.children.link(coll)
    return coll


def _from_model(path, stem, ext, scene):
    mod, name = _IMPORTERS[ext]
    before = set(bpy.data.objects)
    getattr(getattr(bpy.ops, mod), name)(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:                                    # a model asset: no cameras or lights riding along
        if o.type in ("CAMERA", "LIGHT") and not o.children:
            bpy.data.objects.remove(o)
    return _group([o for o in bpy.data.objects if o not in before], stem, scene), "Model"


def _from_blend(path, stem, scene):
    with bpy.data.libraries.load(path, link=False, assets_only=True) as (src, dst):
        for kind in ("objects", "collections", "materials", "worlds", "node_groups"):
            setattr(dst, kind, list(getattr(src, kind)))
    marked = [b for kind in ("objects", "collections", "materials", "worlds", "node_groups")
              for b in getattr(dst, kind) if b is not None]
    if marked:                                       # the file's own assets keep their names and previews
        return marked, "Blend"
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = list(src.objects)
        dst.materials = list(src.materials)
    obs = [o for o in dst.objects if o is not None and o.type not in ("CAMERA", "LIGHT")]
    if obs:
        roots = [o for o in obs if o.parent is None or o.parent not in obs]
        if len(roots) == 1:
            for o in obs:
                scene.collection.objects.link(o)
            return roots[0], "Model"
        return _group(obs, stem, scene), "Model"
    mats = [m for m in dst.materials if m is not None]
    if mats:
        return mats, "Material"
    raise ValueError("the file holds no objects or materials")


# --- a preview render when the file brought no picture --------------------------------------------------------------

def _bounds(objs):
    pts = []
    dg = bpy.context.evaluated_depsgraph_get()
    for o in objs:
        e = o.evaluated_get(dg)
        pts += [e.matrix_world @ Vector(c) for c in e.bound_box]
    if not pts:
        return Vector((0, 0, 0)), 1.0
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return (lo + hi) / 2, max((hi - lo).length / 2, 1e-3)


def _ball(scene, mat):
    mesh = bpy.data.meshes.new("preview ball")
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=1.0, calc_uvs=True)
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new("preview ball", mesh)
    scene.collection.objects.link(ob)
    mesh.materials.append(mat)
    return ob


def _engine(scene, cycles):
    names = ("CYCLES",) if cycles else ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES")
    for n in names:
        try:
            scene.render.engine = n
            break
        except TypeError:
            continue
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = 24 if cycles else 32
        scene.cycles.use_denoising = False
    else:
        try:
            scene.eevee.taa_render_samples = 16
        except AttributeError:
            pass


def _render_preview(block, scene, out_png):
    before = set(bpy.data.objects)
    try:
        _render(block, scene, out_png)
    finally:                                         # the preview's ball, sun and camera are not part of the asset
        for ob in set(bpy.data.objects) - before:
            bpy.data.objects.remove(ob)


def _render(block, scene, out_png):
    volume = isinstance(block, bpy.types.Object) and block.type == "VOLUME"
    _engine(scene, volume)
    r = scene.render
    r.resolution_x = r.resolution_y = PREVIEW
    r.resolution_percentage = 100
    r.film_transparent = not isinstance(block, bpy.types.World)
    r.image_settings.file_format = "PNG"
    r.filepath = out_png
    world = bpy.data.worlds.new("preview light")
    try:
        world.use_nodes = True
    except AttributeError:
        pass
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.35, 0.37, 0.4, 1)
    scene.world = world
    if isinstance(block, bpy.types.Material):
        show = [_ball(scene, block)]
    elif isinstance(block, bpy.types.World):
        scene.world = block
        chrome = _material("chrome")
        b = next(n for n in chrome.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        b.inputs["Metallic"].default_value = 1.0
        b.inputs["Roughness"].default_value = 0.05
        show = [_ball(scene, chrome)]
    elif isinstance(block, bpy.types.Collection):
        show = list(block.all_objects)
    else:
        show = [block] + list(block.children_recursive)
    sun = bpy.data.objects.new("preview sun", bpy.data.lights.new("preview sun", "SUN"))
    sun.data.energy = 4.0
    sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(-35))
    scene.collection.objects.link(sun)
    centre, radius = _bounds(show)
    cam = bpy.data.objects.new("preview camera", bpy.data.cameras.new("preview camera"))
    cam.data.lens = 50
    scene.collection.objects.link(cam)
    d = radius / math.sin(cam.data.angle / 2) * 1.05
    direction = Vector((1, -1.4, 0.8)).normalized()
    cam.location = centre + direction * d
    cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    cam.data.clip_start = max(d * 0.001, 0.001)
    cam.data.clip_end = d * 4
    scene.camera = cam
    bpy.ops.render.render(write_still=True)
    _set_preview(block, out_png)


def _empty_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    for coll in (bpy.data.meshes, bpy.data.cameras, bpy.data.lights, bpy.data.materials, bpy.data.collections):
        for block in list(coll):
            if block.users == 0:
                coll.remove(block)


def add(job):
    path = job["file"]
    stem, ext = os.path.splitext(os.path.basename(path))
    ext = ext.lower()
    out_dir = job["out_dir"]
    os.makedirs(out_dir, exist_ok=True)
    _empty_scene()
    scene = bpy.context.scene
    if ext == ".vdb":
        block, tag = _from_volume(path, stem, out_dir, scene)
    elif ext in PICTURES or ext in SKIES:
        block, tag = _from_picture(path, stem, ext)
    elif ext == ".blend":
        block, tag = _from_blend(path, stem, scene)
    elif ext in _IMPORTERS:
        block, tag = _from_model(path, stem, ext, scene)
    else:
        raise ValueError(f"{ext} files cannot become assets")
    blocks = block if isinstance(block, list) else [block]
    picture = _picture_beside(path)
    for b in blocks:
        if b.asset_data is None:
            b.asset_mark()
        if job.get("catalog_id"):
            b.asset_data.catalog_id = job["catalog_id"]
        if tag not in [t.name for t in b.asset_data.tags]:
            b.asset_data.tags.new(tag)
        if not b.asset_data.description:
            b.asset_data.description = f"Added from {os.path.basename(path)}"
    preview = "own"
    if len(blocks) == 1 or not all(b.preview and b.preview.image_size[0] for b in blocks):
        for b in blocks:
            if picture:
                _set_preview(b, picture)
                preview = "picture"
            elif not (b.preview and b.preview.image_size[0] and ext == ".blend"):
                _render_preview(b, scene, os.path.join(job["tmp"], os.path.basename(job["job"])[:-5] + "_preview.png"))
                preview = "render"
    for img in bpy.data.images:                      # pictures travel inside the asset; volume grids stay beside it
        if img.source == "FILE" and not img.packed_file and img.filepath:
            try:
                img.pack()
            except RuntimeError:
                pass
    blend = _unique(out_dir, stem, ".blend")
    bpy.data.libraries.write(blend, set(blocks), path_remap="RELATIVE_ALL", fake_user=True, compress=True)
    return {"ok": True, "blend": blend, "names": [b.name for b in blocks], "preview": preview}


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:]
    if argv[0] == "index":
        try:
            print("indexed", index(argv[1], argv[2]), "files")
        except Exception:
            traceback.print_exc()
            sys.exit(1)
    elif argv[0] == "add":
        with open(argv[1], encoding="utf-8") as f:
            job = json.load(f)
        try:
            res = add(job)
        except Exception as ex:
            traceback.print_exc()
            res = {"ok": False, "error": f"{type(ex).__name__}: {ex}"}
        with open(job["result"], "w", encoding="utf-8") as f:
            json.dump(res, f)
