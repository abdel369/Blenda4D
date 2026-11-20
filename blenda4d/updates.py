# SPDX-License-Identifier: GPL-3.0-or-later
"""Tells you when a newer Blenda 4D is on the update list, with a button in the top bar that installs it.

Blender's own extension system does the work: when Blenda 4D starts it asks Blender to refresh the update list it was
installed from (only when Preferences > System > Network > Allow Online Access is on), then compares the version
there with the installed one. The button runs Blender's own installer for Blenda 4D alone. Blender's status-bar
notice is not used: Blenda 4D's layout has no status bar. Installed from a file instead of the update list, there is
nothing to compare against and no button shows."""
import json
import os

import bpy

_state = {"latest": None, "synced": False, "tries": 0, "mtime": 0.0}


def _repo():
    """(index, repository) of the update list Blenda 4D was installed from, or (None, None)."""
    parts = (__package__ or "").split(".")
    if len(parts) < 3 or parts[0] != "bl_ext":
        return None, None
    for i, r in enumerate(bpy.context.preferences.extensions.repos):
        if r.module == parts[1]:
            return (i, r) if r.use_remote_url and r.remote_url else (None, None)
    return None, None


def _pkg_id():
    return (__package__ or "blenda4d").split(".")[-1]


def _version(text):
    out = []
    for part in str(text).split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out)


def installed():
    try:
        with open(os.path.join(os.path.dirname(__file__), "blender_manifest.toml")) as f:
            for line in f:
                if line.startswith("version"):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return ""


def _index_file(repo):
    return os.path.join(repo.directory, ".blender_ext", "index.json")


def _read_latest(repo):
    try:
        with open(_index_file(repo)) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    for pkg in data.get("data", []):
        if pkg.get("id") == _pkg_id():
            return pkg.get("version")
    return None


def available():
    """The newer version on the update list, or None."""
    latest = _state["latest"]
    return latest if latest and _version(latest) > _version(installed()) else None


def _redraw():
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            if a.type == "TOPBAR":
                a.tag_redraw()


def _check():
    """Once per session: refresh the update list (Blender's own job, in the background), then read what it found."""
    index, repo = _repo()
    if repo is None:
        return None
    if not _state["synced"]:
        _state["synced"] = True
        try:
            _state["mtime"] = os.path.getmtime(_index_file(repo))
        except OSError:
            _state["mtime"] = 0.0
        if bpy.app.online_access:
            wm = bpy.context.window_manager
            window = wm.windows[0] if wm.windows else None
            if window is not None:
                try:
                    with bpy.context.temp_override(window=window):
                        bpy.ops.extensions.repo_sync(repo_index=index)
                except (RuntimeError, AttributeError, TypeError):
                    pass
    _state["latest"] = _read_latest(repo)
    _redraw()
    try:
        fresh = os.path.getmtime(_index_file(repo)) > _state["mtime"]
    except OSError:
        fresh = False
    _state["tries"] += 1
    if fresh or _state["tries"] > 30 or not bpy.app.online_access:
        return None
    return 2.0                                          # the refresh runs in the background: look again shortly


def draw(layout):
    """The top bar's update button, when there is a newer version."""
    new = available()
    if new:
        layout.operator("blenda4d.update", text=f"Update to {new}", icon="IMPORT")
        layout.separator(factor=1.0)


class BLENDA4D_OT_update(bpy.types.Operator):
    bl_idname = "blenda4d.update"
    bl_label = "Update Blenda 4D"
    bl_description = "Install the newer Blenda 4D from the update list (Blender's own installer); restart Blender after"

    def execute(self, context):
        index, repo = _repo()
        if repo is None:
            self.report({"WARNING"}, "Blenda 4D was not installed from the update list")
            return {"CANCELLED"}
        # Blender's installer replaces Blenda 4D, this button included: it runs a moment later, once nothing of
        # Blenda 4D is running (installing from inside this button crashed Blender as the button was swapped out)
        bpy.app.timers.register(lambda: _install(index, _pkg_id()), first_interval=0.1)
        self.report({"INFO"}, "Updating Blenda 4D: restart Blender when it says it is installed")
        return {"FINISHED"}


def _install(index, pkg_id):
    wm = bpy.context.window_manager
    window = wm.windows[0] if wm and wm.windows else None
    try:
        if window is not None:
            with bpy.context.temp_override(window=window):
                bpy.ops.extensions.package_install(repo_index=index, pkg_id=pkg_id, enable_on_install=True)
        else:
            bpy.ops.extensions.package_install(repo_index=index, pkg_id=pkg_id, enable_on_install=True)
    except RuntimeError as ex:
        print("Blenda 4D: update failed:", ex)
    return None


def register():
    bpy.utils.register_class(BLENDA4D_OT_update)
    _state.update(synced=False, tries=0)
    if not bpy.app.background and not bpy.app.timers.is_registered(_check):
        bpy.app.timers.register(_check, first_interval=3.0)


def unregister():
    if bpy.app.timers.is_registered(_check):
        bpy.app.timers.unregister(_check)
    bpy.utils.unregister_class(BLENDA4D_OT_update)
