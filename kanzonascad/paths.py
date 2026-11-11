r"""Where KanzonasCAD keeps its settings and your files (as KanzonasPDF's paths.py).

Installed / normal: settings in the Windows registry (on Linux ~/.config/KanzonasCAD), the
recovery copies in the user's AppData folder (~/.local/share on Linux), the library in
Documents/KanzonasCAD Library.

Portable: when a file named portable.txt sits next to KanzonasCAD.exe, everything goes in a
"data" folder beside the program instead (settings.ini, Library, recovery), so it travels
with a USB stick and leaves nothing on the computer.

portable.txt can hold settings, one per line (the PortableApps.com package uses them):
  data=..\..\Data    keep the data somewhere else (relative to the program's folder)
  updates=off        the program doesn't update itself (the PortableApps.com Platform does)

No Qt at import (library.py and backup.py, which have no Qt, ask where things go): only
settings() and the installed copy's data folder use it.
"""

import os
import sys

APP = "KanzonasCAD"
MARKER = "portable.txt"
DATA = "data"                   # the portable data folder's name beside the program


def app_dir():
    """Folder of KanzonasCAD.exe (or of the source checkout when run from Python)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_portable():
    return os.path.exists(os.path.join(app_dir(), MARKER))


def portable_options():
    """key=value settings in portable.txt (keys lowercased); {} when there are none or it
    can't be read (then the defaults apply: data beside the program, updates on)."""
    out = {}
    try:
        with open(os.path.join(app_dir(), MARKER), encoding="utf-8", errors="replace") as f:
            for line in f:
                key, eq, value = line.partition("=")
                if eq and key.strip() and " " not in key.strip():
                    out[key.strip().lower()] = value.strip()
    except OSError:
        pass                    # (no marker: not portable, nothing to read)
    return out


def platform_updates():
    """True when something else (the PortableApps.com Platform) updates this copy."""
    return is_portable() and portable_options().get("updates", "").lower() == "off"


def portable_data_dir():
    """The portable copy's data folder (not created here), or None when not portable."""
    if not is_portable():
        return None
    where = portable_options().get("data")
    if where:
        return os.path.normpath(os.path.join(app_dir(), where))
    return os.path.join(app_dir(), DATA)


def data_dir(sub=""):
    """Folder for the program's own files (created if missing): the portable data folder, or
    the user's AppData folder."""
    base = portable_data_dir()
    if base is None:
        from PySide6.QtCore import QStandardPaths
        base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) or \
            os.path.join(os.path.expanduser("~"), "." + APP)
    d = os.path.join(base, sub) if sub else base
    os.makedirs(d, exist_ok=True)
    return d


def follow_drive(path, exists=os.path.exists, splitdrive=os.path.splitdrive):
    """Portable copies move between PCs and the stick's drive letter changes (E: here, F:
    there): a remembered file or folder that's gone from its old drive but is on the drive
    the program now runs from is found there. Other paths come back unchanged."""
    if not path or not is_portable() or exists(path):
        return path
    old, rest = splitdrive(path)
    here = splitdrive(app_dir())[0]
    if old and here and old.lower() != here.lower() and exists(here + rest):
        return here + rest
    return path


def path_key(path, pathmod=os.path):
    """What makes two names of a file the same file: on Windows C:/A/b.kzcad, C:\\A\\b.kzcad
    and c:\\a\\B.KZCAD are one (a Save window gives forward slashes, Explorer backslashes)."""
    return pathmod.normcase(pathmod.normpath(pathmod.abspath(path)))


def recent_list(recent, path=None, limit=None, pathmod=os.path):
    """The recent files with `path` (when given) first, each file once (by path_key: the
    first one wins), written as the system writes them (normpath: backslashes on Windows)."""
    out, seen = [], set()
    first = [path] if path else []
    for p in first + list(recent):
        k = path_key(p, pathmod)
        if k not in seen:
            seen.add(k)
            out.append(pathmod.normpath(pathmod.abspath(p)))
    return out[:limit] if limit else out


def settings():
    """The program's settings store: settings.ini in the data folder when portable, else
    the system's own (the registry on Windows)."""
    from PySide6.QtCore import QSettings
    if is_portable():
        return QSettings(os.path.join(data_dir(), "settings.ini"), QSettings.IniFormat)
    return QSettings(APP, APP)
