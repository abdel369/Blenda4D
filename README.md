# Blenda 4D

A free, open-source add-on that gives Blender a motion-design layout and workflow.

Blenda 4D replaces Blender's editor layout with its own: a command bar, tool columns, an **Object Manager**, an
**Attribute Manager** that always shows what is selected, a **Material Manager**, an **Asset Browser**, a timeline
and saved layouts. Everything is drawn with Blender's own buttons, fields and menus, and one switch at the top right,
**Blenda 4D | Blender**, takes you back to standard Blender and returns.

It is a plain Python add-on: no patched Blender, nothing to compile. It runs wherever Blender 5.2 LTS or later runs
(Mac, Windows, Linux).

## This project is yours

Blenda 4D was started by Joseph Fagan as a tool for his own work and is now handed to the community. There is no
company behind it, no beta programme and no support desk. Use it, change it, fork it and ship your own builds under
the licence below. [ROADMAP.md](ROADMAP.md) lists what isn't built yet; pull requests are how it gets better.

## What's in version 0.1

- **Layout**: command bar, modes, tool and create columns with colour-coded icons, viewport tabs and menus, four views
  (the expand button splits a view into Perspective, Top, Right and Front and back), timeline transport, saved layouts.
- **Object Manager**: scene tree with alternating rows; select, rename, drag to re-parent; visibility and enable
  switches; scroll to the active object; solo; a size slider.
- **Attribute Manager**: tabbed pages for whatever is selected.
- **Parametric objects**: 17 primitives that stay editable.
- **Splines**: 12 parametric spline shapes (circle, rectangle, arc, star, helix, cogwheel, profile and more) and a
  page for Blender's own curves.
- **Generators**: Extrude, Lathe, Sweep, Loft, Subdivision Surface, Symmetry, Boolean, Connect, Instance, Array,
  Remesh, Reduce Polygons and Metaball, built live from their children.
- **Deformers**: Bend, Twist, Taper, Bulge, Shear, Lattice, Shrinkwrap, Smooth, Displace and Wave, placed under the
  object they change.
- **Lights**: point, spot, aimed spot, area, physically based area, IES profile, directional and sun lights, with
  General, Details and Shadow pages.
- **Sky**: one Sky object for an HDRI or a sun-and-atmosphere sky, and a floor.
- **Asset Browser**: your own folders; drag files in from the desktop and they become assets with previews; drag
  assets into the scene.
- **Render Settings**: named settings you can switch between, one section at a time, with frame-range modes.
- **Material Manager**: materials as swatches with apply, pick and clean-up tools.
- **Material tags**: click a material's swatch in the Object Manager for its Tag page: tiling, offset, length, projection,
  and **Seamless**, which breaks up a texture's repeat. Each object keeps its own values, even with a shared material.
- **Top bar**: axis, snapping, workplane, soft selection, symmetry, solo and render buttons wired to Blender's own
  features.
- **Add-ons**: other add-ons' Add and Object menu items, their sidebar panels, and a Blender Properties window.
- **Keymap**: a "Blenda 4D" keymap, selectable in Preferences > Keymap.

## Install

1. Install [Blender 5.2 LTS](https://www.blender.org/download/) or later.
2. Download `blenda4d-0.1.0.zip` from the [latest release](https://github.com/recon007jf/Blenda4D/releases/latest).
3. In Blender: **Edit > Preferences > Add-ons**, menu at the top right, **Install from Disk**, pick the zip.
4. The Blenda 4D layout opens. Use the **Blenda 4D | Blender** switch at the top right to go back and forth.

To run from a checkout instead, link or copy the `blenda4d/` folder into your Blender extensions or add-ons folder.

## Recommended plugins

None of these plugins are required, but we recommend them to enhance your experience. Each is a separate product
with its own licence; nothing of theirs is included here.

- [Poly Haven](https://extensions.blender.org/add-ons/polyhaven-assets/): free HDRIs, textures and models in your
  Asset Browser.
- [Quixel Megascans](https://www.fab.com/): scanned surfaces and objects.
- [Quad Remesher](https://exoside.com/quadremesher/): clean quad topology from any mesh.
- [Sand3D](https://sand3d.ai/): AI-generated 3D models.

## Contributing

Read [AGENTS.md](AGENTS.md) first: the rules, how the add-on is built, how to test and the approved look. It doubles as
the brief for AI coding assistants; `CLAUDE.md`, `.cursor/rules` and `.github/copilot-instructions.md` point to it, so
Claude Code, Cursor and GitHub Copilot read it on their own.

### Building it with an AI assistant

Open this repository in Claude Code, Cursor, Copilot or another coding agent and start with a prompt like this, with
the item you want from [ROADMAP.md](ROADMAP.md):

```text
Read AGENTS.md and ROADMAP.md in this repository. I want to work on: <roadmap item>.
First look at how the existing modules do similar things (kinds.py and one finished module such as
deformers.py or generators.py), then tell me your plan in a few lines before writing code.
Follow every rule in AGENTS.md: Blender's own UI elements only, everything written in your own words,
and the Blenda 4D | Blender switch must restore everything.
Put the feature in its own file under blenda4d/ and plug it in through kinds.py.
Test it in a separate plain Blender with a scratch BLENDER_USER_CONFIG: a headless test under
tools/tests/ that checks every setting changes the result, and a screenshot of the UI that you look at.
When it works, update ROADMAP.md and open a pull request that says what you tested.
```

## Licence

GNU General Public License v3.0 or later, see [LICENSE](LICENSE), the same licence as Blender.

Blenda 4D is an independent project. It is not affiliated with, endorsed by or sponsored by the Blender Foundation
or any software company. Blender is a trademark of the Blender Foundation. All other trademarks are the property of
their respective owners.
