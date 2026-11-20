# SPDX-License-Identifier: GPL-3.0-or-later
"""Make the create column's icons as Blender triangle icons (a developer tool, not part of the add-on).

    python3 tools/make_strip_icons.py

The create column lives in the viewport's toolbar strip, where a picture icon stays at 16 px but a triangle icon
(Blender's own tool-icon format, loaded with bpy.app.icons.new_triangles_from_file) fills its button, as the tool
icons do. Each tinted picture blenda4d/icons/<icon>__<group>.png of a create-column group is turned into
blenda4d/icons/strip/<icon>__<group>.dat: every run of same-coloured pixels in a row becomes a rectangle of two
triangles on Blender's 256 x 256 icon grid. Re-runnable; needs Pillow.
"""
import os
import struct

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "blenda4d", "icons")
OUT = os.path.join(SRC, "strip")
GROUPS = ("null", "splines", "shapes", "text", "generators", "volume", "moclone", "deformers", "effectors", "fields",
          "environment", "camera", "lights")
GRID = 256
FILL = 0.70           # the picture covers this share of the grid, as Blender's tool icons do (about 39..216 of 256)
CENTRE_X = 68.5       # Blender draws toolbar icons pushed toward the strip's outer (right) edge: centring the shape
                      # here, left of the grid's middle (127.5), puts it in the middle of its button (measured)


def convert(png, dat):
    im = Image.open(png).convert("RGBA")
    w, h = im.size
    px = im.load()
    cell = (GRID - 1) * FILL / w
    off = (GRID - 1) * (1 - FILL) / 2
    off_x = CENTRE_X - (GRID - 1) * FILL / 2
    coords, cols = bytearray(), bytearray()

    def q(v):
        return max(0, min(GRID - 1, int(round(v))))

    for y in range(h):
        x = 0
        while x < w:
            c = px[x, y]
            if c[3] == 0:
                x += 1
                continue
            x1 = x
            while x1 + 1 < w and px[x1 + 1, y] == c:
                x1 += 1
            l, r = q(off_x + x * cell), q(off_x + (x1 + 1) * cell)
            top, bot = q(off + (h - y) * cell), q(off + (h - y - 1) * cell)       # the icon grid's y goes up
            for tri in (((l, bot), (r, bot), (r, top)), ((l, bot), (r, top), (l, top))):
                for vx, vy in tri:
                    coords += bytes((vx, vy))
                cols += bytes(c) * 3
            x = x1 + 1
    with open(dat, "wb") as f:
        f.write(b"VCO\x00" + struct.pack("BBBB", 255, 255, 0, 0) + coords + cols)
    return len(coords) // 6


def main():
    os.makedirs(OUT, exist_ok=True)
    made = set()
    for f in sorted(os.listdir(SRC)):
        if f.endswith(".png") and f[:-4].rsplit("__", 1)[-1] in GROUPS:
            n = convert(os.path.join(SRC, f), os.path.join(OUT, f[:-4] + ".dat"))
            made.add(f[:-4] + ".dat")
            print(f"{f}: {n} triangles")
    for f in os.listdir(OUT):
        if f.endswith(".dat") and f not in made:
            os.remove(os.path.join(OUT, f))


if __name__ == "__main__":
    main()
