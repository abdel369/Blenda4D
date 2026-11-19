# Headless test of the Asset Browser engine (blenda4d/assets.py, assets_library.py, assets_worker.py):
#   BLENDER_USER_CONFIG=<scratch> Blender -b --factory-startup --python tools/tests/assets_engine.py -- <scratch> [vdb]
# Makes sample files (an OBJ with a picture beside it, a glTF, a PNG, an HDR, a .blend, optionally a VDB), creates a
# folder in a scratch User Library, adds every file through the background worker, reads the library index and checks
# each asset's type, folder and preview, then adds each to the scene and checks what arrived.
import os
import shutil
import subprocess
import sys
import time

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = args[0] if args else "/tmp/b4d_assets"
VDB = args[1] if len(args) > 1 else ""
import blenda4d  # noqa: E402
from blenda4d import switch  # noqa: E402

switch._register_mode()
from blenda4d import assets, assets_library as lib  # noqa: E402

fails = []


def check(ok, what):
    print(("PASS " if ok else "FAIL ") + what, flush=True)
    if not ok:
        fails.append(what)


LIB = os.path.join(OUT, "library")
SRC = os.path.join(OUT, "inputs")
for d in (LIB, SRC, lib.cache_root()):
    shutil.rmtree(d, ignore_errors=True)
os.makedirs(LIB)
os.makedirs(SRC)
prefs_lib = bpy.context.preferences.filepaths.asset_libraries.get("User Library")
if prefs_lib is None:                                      # a fresh setup (e.g. Linux) may have no User Library yet
    prefs_lib = bpy.context.preferences.filepaths.asset_libraries.new(name="User Library", directory=LIB)
prefs_lib.path = LIB                                       # never the person's own library
bpy.context.preferences.filepaths.asset_libraries.new(name="Read Only", directory=bpy.utils.system_resource("DATAFILES", path="assets"))

# --- sample inputs -------------------------------------------------------------------------------------------------
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob)
bpy.ops.mesh.primitive_cube_add(size=2)
bpy.context.object.name = "Crate"
bpy.ops.wm.obj_export(filepath=os.path.join(SRC, "Crate.obj"), export_selected_objects=True)
pic = bpy.data.images.new("pic", 64, 32)
pic.pixels.foreach_set([0.9, 0.2, 0.1, 1.0] * 64 * 32)
pic.filepath_raw = os.path.join(SRC, "Crate.png")                 # the preview picture beside the model
pic.file_format = "PNG"
pic.save()
bpy.data.objects.remove(bpy.context.object)
bpy.ops.mesh.primitive_torus_add()
bpy.context.object.name = "Ring"
bpy.ops.export_scene.gltf(filepath=os.path.join(SRC, "Ring.glb"), use_selection=True)
bpy.data.objects.remove(bpy.context.object)
tex = bpy.data.images.new("Bricks", 128, 128)
tex.pixels.foreach_set([0.6, 0.3, 0.2, 1.0, 0.8, 0.8, 0.8, 1.0] * (64 * 128))
tex.filepath_raw = os.path.join(SRC, "Bricks.jpg")
tex.file_format = "JPEG"
tex.save()
sky = bpy.data.images.new("Sky", 128, 64, float_buffer=True)
sky.pixels.foreach_set([0.4, 0.6, 1.5, 1.0] * (128 * 64))
sky.filepath_raw = os.path.join(SRC, "Sky.hdr")
sky.file_format = "HDR"
sky.save()
for name, loc in (("Left", (-2, 0, 0)), ("Right", (2, 0, 0))):
    bpy.ops.mesh.primitive_uv_sphere_add(location=loc)
    bpy.context.object.name = name
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SRC, "Pair.blend"), copy=True)
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob)
inputs = ["Crate.obj", "Ring.glb", "Bricks.jpg", "Sky.hdr", "Pair.blend", "notes.txt"]
open(os.path.join(SRC, "notes.txt"), "w").write("not an asset")
files = [os.path.join(SRC, f) for f in inputs]
if VDB and os.path.exists(VDB):
    files.append(VDB)

# --- folders --------------------------------------------------------------------------------------------------------
cid = lib.add_catalog(LIB, "Props")
check(any(p == "Props" for _u, p, _s in lib.read_catalogs(LIB)), "a folder is written to the library's catalog file")
check(lib.unique_folder(LIB) == "New Folder", "first new folder is called New Folder")
lib.add_catalog(LIB, "New Folder")
check(lib.unique_folder(LIB) == "New Folder 2", "the next one is New Folder 2")
sub = lib.add_catalog(LIB, "Props/Metal")
check(sub and lib.rename_catalog(LIB, "Props/Metal", "Steel") == "Props/Steel"
      and any(p == "Props/Steel" for _u, p, _s in lib.read_catalogs(LIB)), "rename keeps the folder under its parent")
lib.delete_catalog(LIB, "New Folder")
check(not any(p == "New Folder" for _u, p, _s in lib.read_catalogs(LIB)), "delete takes the folder out")
print("LIBS", lib.libraries())
check(lib.target_library("Read Only") == ("User Library", LIB), "a read-only library sends new files to the User Library")

# --- adding through the worker (the same queue the drop uses) ------------------------------------------------------
assets._st.update(folder="Props", home=False)
bpy.context.window_manager.b4d_ab_library = "User Library"
with bpy.context.temp_override():
    n, where = assets.add_paths(bpy.context, files)
check(n == len(files) - 1 and where == "Props", f"{n} files queued into {where}; the .txt is left out")
t0 = time.time()
while lib.busy() and time.time() - t0 < 400:
    lib._tick()
    time.sleep(0.3)
check(not lib.busy(), f"queue finished in {time.time() - t0:.0f} s")
check(not lib.failures(), "no file failed: " + "; ".join(lib.failures()))
rows = lib.assets(LIB)
by = {a["name"]: a for a in rows}
print("ASSETS", [(a["name"], a["type"], bool(a["preview"])) for a in rows])
expect = {"Crate": "objects", "Ring": "objects", "Bricks": "materials", "Sky": "worlds", "Pair": "collections"}
if VDB:
    expect[os.path.splitext(os.path.basename(VDB))[0]] = "objects"
for name, typ in expect.items():
    a = by.get(name)
    check(a is not None and a["type"] == typ, f"{name} is a {typ} asset")
    check(a is not None and a["catalog"] == cid, f"{name} is in the Props folder")
    check(a is not None and a["preview"] and os.path.exists(a["preview"]), f"{name} has a preview picture")
    if a is not None:
        check(os.path.dirname(a["blend"]) == os.path.join(LIB, "Props"), f"{name}.blend is in the Props disk folder")
if by.get("Crate") and by["Crate"]["preview"]:
    im = bpy.data.images.load(by["Crate"]["preview"])
    px = im.pixels[:4]
    check(px[0] > 0.7 and px[1] < 0.4, f"Crate's preview is the picture beside it ({px[:3]})")
if by.get("Ring") and by["Ring"]["preview"]:
    im = bpy.data.images.load(by["Ring"]["preview"])
    alpha = sum(1 for v in im.pixels[3::4] if v > 0.5)
    check(0 < alpha < im.size[0] * im.size[1], f"Ring's preview is a render of it ({alpha} opaque pixels)")

# --- tab filter ------------------------------------------------------------------------------------------------------
wm = bpy.context.window_manager
wm.b4d_ab_tab = "MATERIALS"
check([a["name"] for a in assets.shown_assets(bpy.context)] == ["Bricks"], "Materials tab shows only the material")
wm.b4d_ab_tab = "ALL"
wm.b4d_ab_search = "cra"
check([a["name"] for a in assets.shown_assets(bpy.context)] == ["Crate"], "search finds Crate")
wm.b4d_ab_search = ""
assets._st["folder"] = assets.UNCAT
check(assets.shown_assets(bpy.context) == [], "nothing is Uncategorized")
assets._st["folder"] = "Props"

# --- into the scene --------------------------------------------------------------------------------------------------
bpy.ops.mesh.primitive_plane_add(size=4)
plane = bpy.context.object
ob = assets.place(bpy.context, by["Crate"], location=(3, 1, 0))
check(ob.name.startswith("Crate") and ob.type == "MESH" and len(ob.data.vertices) == 8 and tuple(round(v, 4) for v in ob.location) == (3, 1, 1),
      "Crate arrives as an 8-vertex mesh standing where it was dropped")
check(ob.asset_data is None, "the scene's copy is not marked as an asset")
assets.place(bpy.context, by["Bricks"], target=plane)
check(plane.active_material and plane.active_material.name.startswith("Bricks"), "Bricks goes onto the object it was dropped on")
n_mats = len(bpy.data.materials)
assets.place(bpy.context, by["Bricks"], target=plane)
check(len(bpy.data.materials) == n_mats, "a second drop reuses the material")
assets.place(bpy.context, by["Sky"])
check(bpy.context.scene.world.name.startswith("Sky"), "Sky becomes the scene's world")
before = len(bpy.data.objects)
coll = assets.place(bpy.context, by["Pair"], location=(0, 5, 0))
check(len(bpy.data.objects) == before + 2, "Pair brings its two objects")
check(abs(bpy.data.objects["Left"].location.y - 5) < 1e-4 if "Left" in bpy.data.objects else False, "Pair moves to the drop point")
if VDB:
    v = assets.place(bpy.context, by[os.path.splitext(os.path.basename(VDB))[0]])
    v.data.grids.load()
    check(v.type == "VOLUME" and len(v.data.grids) > 0 and v.active_material is not None,
          f"the VDB arrives as a volume with {len(v.data.grids)} grids and a material")
assets._st["folder"] = "@USED"
check(len(assets.shown_assets(bpy.context)) >= 4, "Recently Used lists what was added")

print("RESULT", "OK" if not fails else f"{len(fails)} FAILED: {fails}", flush=True)
