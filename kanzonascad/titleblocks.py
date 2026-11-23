"""Title blocks kept in your library: the ready-made ones (in the lower right corner, a right-hand
strip or a bottom strip) and those you save (the owner, 0.22.5: "I don't want to lose the
default title block as an option though. I think I should be able to save as a new title block
and then select default ones or different variations I've made. I also want to be able to put
my company's logo in the title block"). One file each in the library folder's "Title blocks"
folder (both library folders are read; a new one goes where new blocks go), with the title
block's pieces (texts, lines, a logo picture...), where it sits on the sheet, and the layers and
blocks it uses, so any project can use it."""

import json
import os

from . import model as M
from .library import _BAD, _writable

FOLDER = "Title blocks"
SUFFIX = ".kztitle"
FORMAT = "kanzonascad-title-block"
POSITIONS = ("corner", "right", "bottom")
# the ready-made ones: (name, position)
BUILT_IN = (("Standard, lower right corner", "corner"),
            ("Standard, right-hand strip", "right"),
            ("Standard, bottom strip", "bottom"))


def _dir(lib):
    return os.path.join(lib.folder, FOLDER)


def _path(lib, name):
    return os.path.join(_dir(lib), (_BAD.sub("_", name).strip().rstrip(".") or "title block")
                        + SUFFIX)


def _libraries(lib):
    return [x for x in (lib, getattr(lib, "second", None)) if x is not None]


def saved(lib):
    """{name: path} of the title blocks saved in the library folders (the first one's win)."""
    out = {}
    for x in reversed(_libraries(lib)):
        d = _dir(x)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.lower().endswith(SUFFIX):
                p = os.path.join(d, f)
                try:
                    with open(p, encoding="utf-8") as fh:
                        name = json.load(fh).get("name") or f[:-len(SUFFIX)]
                except (OSError, ValueError):
                    continue                # (not one of ours, or damaged: not listed)
                out[name] = p
    return out


def names(lib):
    """[(name, built in?)]: the ready-made ones, then yours by name."""
    return [(n, True) for n, _pos in BUILT_IN] + [(n, False) for n in
                                                  sorted(saved(lib), key=str.lower)]


def save(lib, name, project, position):
    """Save project's title block to the library under name (an existing one of that name is
    replaced). Returns the file's path."""
    name = name.strip()
    if not name:
        raise ValueError("a title block needs a name")
    if name in dict(BUILT_IN):
        raise ValueError("%s is a ready-made title block's name" % name)
    tb = project.title_block
    ents = list(tb.entities.values())
    used_layers = {e.layer for e in ents}
    used_blocks = {e.block for e in ents if isinstance(e, M.Insert)}
    d = {"format": FORMAT, "name": name,
         "position": position if position in POSITIONS else "corner",
         "entities": [e.to_dict() for e in ents],
         "layers": [lay.to_dict() for n, lay in project.layers.items() if n in used_layers],
         "blocks": [b.to_dict() for n, b in project.blocks.items() if n in used_blocks]}
    target = _writable(lib._target() if hasattr(lib, "_target") else lib)
    os.makedirs(_dir(target), exist_ok=True)
    path = _path(target, name)
    old = saved(lib).get(name)
    if old and os.path.dirname(old) != _dir(target):
        path = old                          # (kept where it is)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(d, fh)
    return path


def delete(lib, name):
    path = saved(lib).get(name)
    if path is None:
        raise ValueError("%s isn't one of your title blocks" % name)
    os.remove(path)


def load(lib, name, project):
    """(position, [entities], [layers], [blocks]) of a title block for project: a ready-made
    one made for its title block sheet, or one of yours."""
    built = dict(BUILT_IN)
    if name in built:
        from .sheetframe import default_title_block, strip_title_block
        pos = built[name]
        tb = project.title_block
        return pos, (strip_title_block(tb, pos) if pos in ("right", "bottom")
                     else default_title_block(tb)), [], []
    path = saved(lib).get(name)
    if path is None:
        raise ValueError("%s isn't in your library" % name)
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    if d.get("format") != FORMAT:
        raise ValueError("%s isn't a KanzonasCAD title block" % os.path.basename(path))
    blocks = [M.BlockDef.from_dict(b) for b in d.get("blocks") or []]
    known = dict(project.blocks)
    known.update({b.name: b for b in blocks if b.name not in known})
    ents = []
    for e in d.get("entities") or []:
        e = dict(e)
        e.pop("id", None)
        ents.append(M.Entity.from_dict(e, known))
    return (d.get("position") if d.get("position") in POSITIONS else "corner", ents,
            [M.Layer.from_dict(x) for x in d.get("layers") or []], blocks)


def use(ed, project, lib, name):
    """In edit ed: project's title block replaced by the named one, and the title block placed
    where that one sits (Undo puts both back). Layers and blocks it uses that the project
    hasn't got are brought in."""
    pos, ents, layers, blocks = load(lib, name, project)
    for lay in layers:
        if lay.name not in project.layers:
            ed.layer(lay.name, None, lay.to_dict())
    for b in blocks:
        if b.name not in project.blocks:
            ed.block(b)
    tb = project.title_block
    for eid in list(tb.entities):
        ed.remove(tb, eid)
    for e in ents:
        ed.add(tb, e)
    if project.settings.get("tb_position", "corner") != pos:
        ed.project_settings({"tb_position": pos})
