# Blenda 4D — the brief for AI coding assistants and contributors

Blenda 4D is a Blender add-on (folder `blenda4d/`, GPL-3.0-or-later) that gives plain Blender 5.2 LTS and later a
motion-design layout: a command bar, tool and create columns, an Object Manager, an Attribute Manager that always shows
what is selected, a Material Manager, an Asset Browser, a timeline and saved layouts, all drawn with Blender's own UI
elements. Its original author handed it to the community; there is no maintainer team. Read this whole file before
changing anything, then pick an item from `ROADMAP.md`.

## Rules

- Use only Blender's UI elements and icons (rows, fields, buttons, menus, lists). Never draw custom widgets or new icon
  artwork. Blender's own icons recoloured by group (`blenda4d/icons/`, made by `tools/tint_icons.py`, see its NOTICE.md)
  are the one exception: cyan shapes and splines, green generators, violet deformers, pink cloners, pale lavender scene
  objects.
- None of Blender's own editor layout shows while Blenda mode is on; everything is a Blenda panel in a role area
  (`roles.py`).
- The Blenda 4D | Blender switch must restore everything it changes (tool settings, theme, keymap, layout).
- Plain Blender only: no patched builds, no compiled code.
- Write everything in your own words: names, tooltips, comments and docs. Use plain, common 3D terms (Sweep, Lathe,
  Extrude, Bend, Null, Spline) and describe features by what they do. Never copy wording, data, ids, icons or other
  assets from any other software, and keep other products and companies out of the code, docs and interface. Where a
  Blender feature does the work, name it in parentheses in the tooltip only:
  "Soft Selection (Proportional Editing in Blender): ...".
- Never lose the user's work: test every file-load or file-replace path on a copy; anything a list lets the user order
  must keep that order after saving and reopening.
- Never write into the user's real asset library while testing (Blender's default User Library is
  `~/Documents/Blender/Assets` even with a scratch config): point the library at a scratch folder in tests.
- An extension may go online only when `bpy.app.online_access` is on (see `sky_resolution.py`).

## How the add-on is built

- `__init__.py` registers `settings` and `switch`. `switch.py` turns Blenda mode on and off: it registers the modules in
  `switch.MODE`, builds the "Blenda 4D" workspace (`build.py`) and restores everything on the way out.
- **Role areas** (`roles.py`): every manager is a Properties editor whose hidden tab flags say which manager it is.
  Panels subclass `roles.RolePanel` and set `role = "OBJECTS"` (etc.). `build.py` splits the window into these areas.
- **Feature modules plug in through `kinds.py`** and are listed in `kinds.FEATURES`; each lives in its own file, so most
  work touches one file. From a module's `register()`:
  - `kinds.add(kind, label, icon, create=fn, tabs=[...], pages={...})`: an object kind (stored as `ob["b4d_type"]`)
    with its Attribute Manager tabs and pages and the function that makes one;
  - `kinds.create_button(group, label, kind)`: a button in the create column (`bars.CREATE_GROUPS`);
  - `kinds.menu_item("Create", label, kind)`: a main menu entry;
  - `kinds.panel(role, fn)`, `kinds.view_page(name, fn)`, `kinds.resolver(fn)`: take over a manager, a viewport page,
    or give plain Blender objects a kind.
- `managers.py`: Object Manager (rows, stripes, drag to re-parent, tag buttons), Attribute Manager (tabs and pages),
  Material Manager and Asset Browser panels. `bars.py`: command bar, tool and create columns, viewport header.
  `menus.py`: the main menus. `theme.py`: Blenda's theme. `layouts.py`: saved layouts.
- Engines are Geometry Nodes groups named "Blenda ..." (`primitives.py`, `generators_nodes.py`, `deformers_nodes.py`);
  settings live on the object, so files keep working with the add-on switched off.
- Property names start with `b4d_`, operators with `blenda4d.`, classes with `BLENDA4D_`.

## Testing

- Always in a separate plain Blender (never someone's working session), with `BLENDER_USER_CONFIG` pointing at a
  scratch folder:
  - `tools/try_ui.py` builds a sample scene, switches the layout off and on and takes screenshots
    (`B4D_OUT=<folder> B4D_STEPS=shot Blender --factory-startup --window-geometry 100 60 1700 1000 --python tools/try_ui.py`);
  - `tools/tests/<module>_engine.py` are headless checks (`Blender -b --factory-startup --python ...`),
    `tools/tests/<module>_ui.py` drive the real UI in a window.
- Every row on a page must change something; check it in the evaluated geometry or a small render.
- Look at a screenshot of every UI change before calling it done, and compare it with the approved look below.
  `bpy.ops.screen.screenshot` shows the frame before the latest change: call
  `bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=2)` first. Pop-up menus never appear in it.
- Build the release zip with Blender's extension builder:
  `Blender --command extension build --source-dir blenda4d --output-dir dist`, and test installing it into a fresh config.

## The approved look

Compare every screenshot against these before calling UI work done:
- `docs/mockups/drawn_cube.png`: Standard layout, a cube selected, Material Manager open between the viewport and the
  create column.
- `docs/mockups/drawn_cloner.png`, `docs/mockups/drawn_light.png`: the Attribute Manager follows the selection.
- `docs/mockups/drawn_ab_home.png`, `docs/mockups/drawn_ab_mats.png`: Asset Browser, Home page and Materials tab.
- `docs/mockups/drawn_layout_menu.png`: the Layout dropdown.
- `docs/mockups/drawn_ui.html`: the page that draws them (open with `?sel=cube|cloner|light` and `&ab=home|mats`).
