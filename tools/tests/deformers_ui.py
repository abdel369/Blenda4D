# UI run of the deformers: the sample scene from tools/try_ui.py, then a Bend under the cube, a Twist under the torus
# and a Lattice under the sphere, each with its Attribute Manager Object page shown, screenshotted.
#   BLENDER_USER_CONFIG=<scratch> B4D_OUT=<scratch> Blender --factory-startup --window-geometry 100 60 1700 1000 \
#       --python tools/tests/deformers_ui.py
import math
import os
import runpy

import bpy

os.environ["B4D_STEPS"] = "wait"
HERE = os.path.dirname(os.path.abspath(__file__))
ns = runpy.run_path(os.path.join(HERE, "..", "try_ui.py"))
PLAN, shot, select = ns["PLAN"], ns["shot"], ns["select"]


def ctx():
    w = bpy.context.window_manager.windows[0]
    return bpy.context.temp_override(window=w, screen=w.screen)


def add(kind, under, **values):
    def run():
        select(under)
        with ctx():
            bpy.ops.blenda4d.add_kind(kind=kind)
        ob = bpy.context.view_layer.objects.active
        for k, v in values.items():
            ob[k] = v
        ob.update_tag()
        bpy.context.window_manager.b4d_am_tab = "OBJECT"
        print("B4D DEFORMER", ob.name, "under", ob.parent.name if ob.parent else None,
              [m.name for m in bpy.data.objects[under].modifiers], flush=True)
    return run


def page(name):
    def run():
        select(name)
        bpy.context.window_manager.b4d_am_tab = "OBJECT"
    return run


done = PLAN.pop()
PLAN += [add("bend", "Cube", b4d_def_angle=math.radians(70)), lambda: None, lambda: None, lambda: shot("deformer_bend"),
         add("twist", "Torus", b4d_def_angle=math.radians(90)), lambda: None, lambda: shot("deformer_twist"),
         add("lattice", "Sphere"), lambda: None, lambda: shot("deformer_lattice"),
         add("shrinkwrap", "Sphere"), lambda: None, lambda: shot("deformer_shrinkwrap"),
         add("displace", "Torus", b4d_def_height=8.0), lambda: None, lambda: shot("deformer_displace"),
         page("Bend"), lambda: None, lambda: shot("deformer_bend_again"), done]
