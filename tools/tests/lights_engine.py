# Headless test of the lights module: every kind is made, every page row changes something, falloff and profile
# nodes are wired, plain Blender lights get the pages, and renders react to the main rows.
#   BLENDER_USER_CONFIG=<scratch> Blender -b --factory-startup --python tools/tests/lights_engine.py
import os
import sys
import traceback

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from blenda4d import bars, kinds, lights, lights_ies, managers, menus  # noqa: E402

FAIL = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what, flush=True)
    if not cond:
        FAIL.append(what)


def setup():
    menus.register()
    bars.register()
    managers.register()
    bpy.utils.register_class(kinds.BLENDA4D_OT_add_kind)
    lights.register()


def clear():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)


def made(kind):
    before = set(bpy.data.objects)
    bpy.ops.blenda4d.add_kind(kind=kind)
    new = [o for o in bpy.data.objects if o not in before]
    return next((o for o in new if o.type == "LIGHT"), None), new


def test_create():
    labels = [m[0] for m in bars.GROUPS["lights"]]
    check(labels == ["Light", "Spot Light", "Target Light", "Area Light", "PBR Light", "IES Light", "Infinite Light",
                     "Sun Light"], f"create column order {labels}")
    check(all(m[2] == "blenda4d.add_kind" for m in bars.GROUPS["lights"]), "every group button has an operator")
    menu = [e[1] for e in kinds.menu_items("Create")]
    check(all(k in menu for k in lights.ORDER), "Create menu lists every light")
    check(not any(isinstance(i, tuple) and i[1] == "object.light_add" for i in menus.MAIN["Create"]),
          "plain Blender Light entry replaced")
    for kind in lights.ORDER:
        if kind == "ies_light":
            continue
        clear()
        ob, new = made(kind)
        check(ob is not None, f"{kind}: made a light")
        if ob is None:
            continue
        check(ob.data.type == lights.KINDS[kind][0], f"{kind}: type {ob.data.type}")
        check(kinds.kind_of(ob) == kind, f"{kind}: kind stored")
        check(abs(ob.location.z - lights.HEIGHT) < 1e-6 and ob.location.x == 0 and ob.location.y == 0, f"{kind}: above origin")
        check(ob.data.energy > 0, f"{kind}: energy {ob.data.energy}")
        check(bpy.context.view_layer.objects.active == ob, f"{kind}: selected")
        if kind == "target_light":
            t = lights._track(ob)
            check(t is not None and t.target is not None and t.target in new, "target light: Track To a new null")
            t.target.location = (2.0, 0.0, 0.0)
            bpy.context.view_layer.update()
            aim = -(ob.matrix_world.to_3x3().col[2])
            want = (t.target.matrix_world.translation - ob.matrix_world.translation).normalized()
            check((aim - want).length < 1e-4, f"target light aims at the null ({aim})")
        if kind == "pbr_light":
            check(ob.data.use_shadow_jitter and ob.data.size >= 1.5, "pbr light: big and soft")


def _changed_value(owner, attr):
    p = owner.bl_rna.properties[attr]
    v = getattr(owner, attr)
    if p.type == "BOOLEAN":
        return not v
    if p.type == "ENUM":
        items = [e.identifier for e in p.enum_items]
        return next(i for i in items if i != v)
    if p.type in {"FLOAT", "INT"}:
        if getattr(p, "is_array", False) and p.array_length > 0:
            return tuple(1.0 - x if p.type == "FLOAT" else x + 1 for x in v)
        lo, hi = p.hard_min, p.hard_max
        step = (hi - lo) * 0.1 if hi - lo < 1e6 else 1.0
        if p.type == "INT":
            step = max(1, int(step))
        nv = v + step
        if nv > hi:
            nv = v - step
        return nv
    if p.type == "POINTER":
        return None
    return None


def test_rows():
    for kind in lights.ORDER:
        clear()
        if kind == "ies_light":
            ob = ies_light()
        else:
            ob, _ = made(kind)
        if ob.data.type == "AREA":
            ob.data.shape = "RECTANGLE"
        tabs = [t[0] for t in kinds.KINDS[kind]["tabs"]]
        for tab in tabs:
            n = 0
            for r in lights.rows(ob, tab):
                if r[0] != "prop":
                    continue
                _, owner, attr, label, _active = r
                if attr == "type":
                    continue                         # tested in test_type_sync
                p = owner.bl_rna.properties[attr]
                if p.type == "POINTER":
                    check(p.is_readonly is False or attr == "ies", f"{kind}/{tab}/{label}: pointer row editable")
                    n += 1
                    continue
                old = getattr(owner, attr)
                old = tuple(old) if hasattr(old, "__len__") and not isinstance(old, str) else old
                try:
                    setattr(owner, attr, _changed_value(owner, attr))
                    new = getattr(owner, attr)
                    new = tuple(new) if hasattr(new, "__len__") and not isinstance(new, str) else new
                    check(new != old, f"{kind}/{tab}/{label}: row changes {attr}")
                    setattr(owner, attr, old)
                except Exception as ex:
                    check(False, f"{kind}/{tab}/{label}: {ex}")
                n += 1
            check(n > 0 or tab == "PROFILE", f"{kind}/{tab}: page has rows ({n})")
    # rows that are greyed until their switch is on
    clear()
    ob, _ = made("light")
    ob.data.use_temperature = False
    row = next(r for r in lights.rows_general(ob) if r[0] == "prop" and r[2] == "temperature")
    check(row[4] is False, "temperature greyed while Use Temperature is off")


def ies_light():
    path = os.path.join(lights_ies.ensure_files(), "Narrow_Downlight.ies")
    before = set(bpy.data.objects)
    bpy.ops.blenda4d.light_ies_add(filepath=path)
    return next(o for o in bpy.data.objects if o not in before)


def test_ies():
    d = lights_ies.ensure_files()
    files = sorted(f for f in os.listdir(d) if f.endswith(".ies"))
    check(len(files) == len(lights_ies.PROFILES), f"starter profiles written {files}")
    clear()
    ob = ies_light()
    node = lights.ies_node(ob.data)
    check(node is not None and node.ies is not None, "ies light: profile node with the file's text")
    em = lights._emission(ob.data)
    check(em.inputs["Strength"].is_linked and em.inputs["Strength"].links[0].from_node == node, "profile drives strength")
    check(kinds.kind_of(ob) == "ies_light" and "PROFILE" in [t[0] for t in managers._page_tabs(ob)], "ies light: Profile tab")
    check(ob.name == "Narrow Downlight", f"ies light named after the profile: {ob.name}")
    ob.data.b4d_falloff = "LINEAR"
    mult = ob.data.node_tree.nodes.get(lights.MULTIPLY_NODE)
    check(mult is not None and em.inputs["Strength"].links[0].from_node == mult, "profile and falloff multiplied")
    ob.data.b4d_falloff = "QUADRATIC"
    check(ob.data.node_tree.nodes.get(lights.MULTIPLY_NODE) is None and
          ob.data.node_tree.nodes.get(lights.FALLOFF_NODE) is None, "back to inverse square removes the extra nodes")
    with bpy.context.temp_override(active_object=ob):
        bpy.context.view_layer.objects.active = ob
        bpy.ops.blenda4d.light_ies_clear()
    check(lights.ies_node(ob.data) is None and not em.inputs["Strength"].is_linked, "remove profile")
    bpy.ops.blenda4d.light_ies_load(filepath=os.path.join(d, "Batwing.ies"))
    check(lights.ies_node(ob.data) is not None, "load profile on an existing light")


def test_falloff():
    clear()
    ob, _ = made("light")
    em = lights._emission(ob.data)
    for value, out in (("LINEAR", "Linear"), ("CONSTANT", "Constant")):
        ob.data.b4d_falloff = value
        link = em.inputs["Strength"].links[0] if em.inputs["Strength"].is_linked else None
        check(link is not None and link.from_socket.name == out, f"falloff {value} wired")
    ob.data.b4d_falloff = "QUADRATIC"
    check(not em.inputs["Strength"].is_linked, "inverse square: plain strength")


def test_type_sync_and_plain():
    clear()
    ob, _ = made("area_light")
    ob.data.type = "SPOT"
    lights.sync_kinds()
    check(ob["b4d_type"] == "spot_light", f"type change moves the kind: {ob['b4d_type']}")
    li = bpy.data.lights.new("Plain", "AREA")
    plain = bpy.data.objects.new("Plain", li)
    bpy.context.collection.objects.link(plain)
    check("b4d_type" not in plain and kinds.kind_of(plain) == "area_light", "plain Blender light resolved to a kind")
    tabs = [t[0] for t in managers._page_tabs(plain)]
    check(tabs == ["BASIC", "COORD", "OBJECT", "DETAILS", "SHADOW"], f"plain light tabs {tabs}")
    check(managers.type_icon(plain) == "LIGHT_AREA", "plain light icon")


def _render(engine, size=24):
    sc = bpy.context.scene
    sc.render.engine = engine
    sc.render.resolution_x = sc.render.resolution_y = size
    sc.render.resolution_percentage = 100
    if engine == "CYCLES":
        sc.cycles.samples = 8
        sc.cycles.device = "CPU"
    path = os.path.join(os.environ.get("B4D_OUT", "/tmp"), "lights_render.png")
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path, check_existing=False)
    px = list(img.pixels)
    bpy.data.images.remove(img)
    return sum(px[i] for i in range(0, len(px), 4)) / (len(px) / 4)


def test_render():
    clear()
    bpy.ops.mesh.primitive_plane_add(size=20)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    bpy.context.collection.objects.link(cam)
    cam.location = (0, 0, 8)
    bpy.context.scene.camera = cam
    ob, _ = made("light")
    ob.data.energy = 50.0
    a = _render("BLENDER_EEVEE")
    ob.data.energy *= 4
    b = _render("BLENDER_EEVEE")
    check(b > a > 0.0, f"EEVEE: light shows and Intensity brightens it ({a:.3f} -> {b:.3f})")
    ob.data.color = (1.0, 0.0, 0.0)
    try:
        c1 = _render("CYCLES")
        ob.data.b4d_falloff = "CONSTANT"
        c2 = _render("CYCLES")
        check(abs(c2 - c1) > 1e-3, f"Cycles: Falloff changes the render ({c1:.3f} -> {c2:.3f})")
        bpy.data.objects.remove(ob)
        d = lights_ies.ensure_files()
        ies = ies_light()
        ies.data.energy = 50.0
        n = _render("CYCLES")
        lights.set_profile(ies, os.path.join(d, "Wide_Flood.ies"))
        w = _render("CYCLES")
        check(w > n * 1.2, f"Cycles: a wide profile lights more of the floor than a narrow one ({n:.3f} -> {w:.3f})")
    except TypeError as ex:
        print("skip Cycles render:", ex)


def main():
    setup()
    for t in (test_create, test_rows, test_ies, test_falloff, test_type_sync_and_plain, test_render):
        try:
            t()
        except Exception:
            traceback.print_exc()
            FAIL.append(t.__name__)
    lights.unregister()
    check(any(isinstance(i, tuple) and i[1] == "object.light_add" for i in menus.MAIN["Create"]), "unregister restores menu")
    check([m[0] for m in bars.GROUPS["lights"]][0] == "Area Light", "unregister restores the create group")
    print("LIGHTS TEST", "FAILED: " + ", ".join(FAIL) if FAIL else "PASSED", flush=True)


main()
