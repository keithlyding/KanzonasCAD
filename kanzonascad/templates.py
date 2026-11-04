"""Project templates (no Qt).

A template is an ordinary KanzonasCAD project: a new project made from it starts with
everything in it (settings, layers and their colors, wire colors, the title block drawing and
its field values, zones, and its sheets with what is drawn on them). Templates are kept in the
library folder's Templates folder, so a shared library can share them too; one of them (any
.kzcad file, in fact) can be the default that File > New project starts from.
"""

import glob
import os

from . import model as M

FOLDER = "Templates"


def folder(library_root):
    """The templates folder of a library."""
    return os.path.join(library_root, FOLDER)


def available(library_root):
    """The templates in a library: [(name, path)], by name."""
    out = []
    for p in glob.glob(os.path.join(glob.escape(folder(library_root)), "*" + M.FILE_SUFFIX)):
        out.append((os.path.splitext(os.path.basename(p))[0], p))
    return sorted(out, key=lambda t: t[0].lower())


def new_from(path):
    """A new, untitled project with everything the template at path has. Raises OSError or
    ValueError when it can't be read."""
    p = M.Project.load(path)
    p.path = None                       # (a new project: Save asks where; never the template)
    p.undo_stack = []
    p.redo_stack = []
    p.saved_at = 0
    return p


def save(project, path):
    """Write the project as a template at path (the project itself stays as it is: its own
    file, name and undo). No backups are kept of a template."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    copy = M.Project.from_dict(project.to_dict())
    copy.save(path, backups=0)
    return path
