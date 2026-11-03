"""Backups and autosave. No Qt here.

Backups: every Save first copies the file as it was into a folder beside it,
"<name> backups", stamped with the time; the newest few are kept (KEEP).

Autosave: every few minutes, each project with unsaved changes is written to the recovery
folder (not over your file). Saving or closing it normally removes that copy, so a copy
still there at start-up means KanzonasCAD didn't close normally: it offers to recover it.
"""

import datetime
import glob
import hashlib
import json
import os
import shutil

KEEP = 10
SUFFIX = ".kzcad"


def backup_folder(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    return os.path.join(os.path.dirname(os.path.abspath(path)), stem + " backups")


def make_backup(path, keep=KEEP):
    """Copy the file at path (the last save) into its backups folder; keep the newest
    `keep`. Returns the copy's path, or None when there was nothing to copy."""
    if keep <= 0 or not os.path.exists(path):
        return None
    folder = backup_folder(path)
    os.makedirs(folder, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H%M%S")
    dest = os.path.join(folder, "%s %s%s" % (stem, stamp, SUFFIX))
    n = 2
    while os.path.exists(dest):                 # two saves in the same second
        dest = os.path.join(folder, "%s %s (%d)%s" % (stem, stamp, n, SUFFIX))
        n += 1
    shutil.copy2(path, dest)
    old = sorted(glob.glob(os.path.join(glob.escape(folder), glob.escape(stem) + " *" + SUFFIX)),
                 key=os.path.getmtime)
    for p in old[:-keep]:
        os.remove(p)
    return dest


def list_backups(path):
    folder = backup_folder(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    out = glob.glob(os.path.join(glob.escape(folder), glob.escape(stem) + " *" + SUFFIX))
    return sorted(out, key=os.path.getmtime, reverse=True)


# ---- autosave / recovery ----------------------------------------------------------------------
def recovery_folder():
    env = os.environ.get("KANZONASCAD_RECOVERY")
    if env:
        return env
    from PySide6.QtCore import QStandardPaths       # (only here: where the app keeps data)
    base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    return os.path.join(base or os.path.expanduser("~"), "recovery")


def autosave_path(key):
    """The recovery file of a project (key: its path, or an id for an unsaved one)."""
    h = hashlib.sha1(str(key).encode("utf-8")).hexdigest()[:16]
    return os.path.join(recovery_folder(), "autosave-%s%s" % (h, SUFFIX))


def write_autosave(project, key):
    os.makedirs(recovery_folder(), exist_ok=True)
    data = project.to_dict()
    data["autosave_of"] = project.path or ""
    path = autosave_path(key)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    os.replace(tmp, path)
    return path


def remove_autosave(key):
    path = autosave_path(key)
    if os.path.exists(path):
        os.remove(path)


def leftovers():
    """[(recovery file, original path or "", saved time)] of projects not closed normally."""
    folder = recovery_folder()
    out = []
    for p in sorted(glob.glob(os.path.join(glob.escape(folder), "autosave-*" + SUFFIX))):
        try:
            with open(p, encoding="utf-8") as f:
                orig = json.load(f).get("autosave_of", "")
        except (OSError, ValueError):
            orig = ""
        out.append((p, orig, os.path.getmtime(p)))
    return out
