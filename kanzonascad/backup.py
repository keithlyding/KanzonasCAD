"""Backups and autosave. No Qt here.

Backups: every Save first copies the file as it was into a folder beside it,
"<name> backups", stamped with the time; the newest few are kept (KEEP).

Autosave: every few minutes, each project with unsaved changes is written to the recovery
folder (not over your file; in a portable copy, recovery in its data folder). Saving or closing it normally removes that copy, so a copy
still there at start-up means KanzonasCAD didn't close normally: it offers to recover it.
"""

import datetime
import glob
import hashlib
import json
import os
import re
import shutil

KEEP = 10
SUFFIX = ".kzcad"


def backup_folder(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    return os.path.join(os.path.dirname(os.path.abspath(path)), stem + " backups")


_STAMP = re.compile(r" (\d{4}-\d\d-\d\d \d{6})(?: \((\d+)\))?" + re.escape(SUFFIX) + "$")


def _age(p):
    """Sort key, oldest first: the time in the backup's name and its (2), (3) counter. Not the
    file's time alone: a backup keeps the time of the save it copies, and saves a moment
    apart can carry the same time."""
    m = _STAMP.search(os.path.basename(p))
    if m is None:
        return ("", 0, os.path.getmtime(p))
    return (m.group(1), int(m.group(2) or 1), os.path.getmtime(p))


def make_backup(path, keep=KEEP):
    """Copy the file at path (the last save) into its backups folder; keep the newest
    `keep`. Returns the copy's path, or None when there was nothing to copy."""
    if keep <= 0 or not os.path.exists(path):
        return None
    folder = backup_folder(path)
    os.makedirs(folder, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H%M%S")
    # Two saves in the same second: (2), (3)... above any already there (a pruned name is
    # never taken again, or the newest backup would sort as the oldest).
    same = glob.glob(os.path.join(glob.escape(folder), glob.escape("%s %s" % (stem, stamp))
                                  + "*" + SUFFIX))
    n = max((_age(f)[1] for f in same if _age(f)[0] == stamp), default=0)
    dest = os.path.join(folder, "%s %s%s" % (stem, stamp, SUFFIX)) if n == 0 else \
        os.path.join(folder, "%s %s (%d)%s" % (stem, stamp, n + 1, SUFFIX))
    shutil.copy2(path, dest)
    old = sorted(glob.glob(os.path.join(glob.escape(folder), glob.escape(stem) + " *" + SUFFIX)),
                 key=_age)
    for p in old[:-keep]:
        os.remove(p)
    return dest


def list_backups(path):
    folder = backup_folder(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    out = glob.glob(os.path.join(glob.escape(folder), glob.escape(stem) + " *" + SUFFIX))
    return sorted(out, key=_age, reverse=True)


# ---- autosave / recovery ----------------------------------------------------------------------
def recovery_folder():
    env = os.environ.get("KANZONASCAD_RECOVERY")
    if env:
        return env
    from . import paths
    portable = paths.portable_data_dir()
    if portable:                        # (a portable copy: beside the program, in data)
        return os.path.join(portable, "recovery")
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
