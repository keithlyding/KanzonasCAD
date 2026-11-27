"""Saved circuits (no Qt): part of a schematic kept in the library and dropped in whole, as
AutoCAD Electrical's circuit builder keeps them (the owner, Nov 2026: saved circuits "not a bad
idea"). A motor starter rung, a pilot light circuit, an E-stop string: drawn once, saved with
Library > Save circuit..., placed again with Library > Insert circuit....

A circuit keeps the objects as they were drawn (symbols, wires, text, lines, ladders...),
moved so that its base point is (0, 0), with its own copies of the blocks they use and the
layers they are on. Placed, it is one undoable step that:

- gives every device a new tag of the sheet's page (CR601 saved, CR701 on page 7, never a tag
  already taken: tags.retag_copies) and a new hidden id; a tag typed and locked is kept;
- links each contact (and footprint, dashed box) whose device is in the circuit to the new
  copy of that device (by its hidden id, or by its tag when it had only that), so its
  cross-references work at once; one whose device was left out is placed unlinked, its tag
  cleared (it isn't the device of that tag in this project);
- numbers its wires as the sheet's own (numbers typed and locked are kept: wirenums.py);
- gives its off-sheet connectors and source/destination arrows new names, the same within
  the circuit, so its pairs stay pairs and none joins a wire of the project by accident;
- gives its tags and footprint labels the project's heights for the sheet;
- cuts the sheet's wires under its symbols, as Paste does.

    <library>/circuits/<name>.kzcircuit    one file a circuit (JSON)
"""

import copy
import math

from . import geometry as G
from . import model as M

FORMAT = "kanzonascad-circuit"
VERSION = 1
SUFFIX = ".kzcircuit"
FOLDER = "circuits"


class Circuit:
    """A saved circuit: its name, category and description, and its objects (entity dicts)
    around its base point (0, 0), with the blocks (BlockDef dicts) and layers (Layer dicts)
    they use."""

    def __init__(self, name, category="", description="", entities=(), blocks=(), layers=()):
        self.name = str(name).strip()
        self.category = str(category or "").strip()
        self.description = str(description or "").strip()
        self.entities = [copy.deepcopy(d) for d in entities]
        self.blocks = [copy.deepcopy(d) for d in blocks]
        self.layers = [copy.deepcopy(d) for d in layers]
        self._defs = None

    def to_dict(self):
        return {"format": FORMAT, "version": VERSION, "name": self.name,
                "category": self.category, "description": self.description,
                "entities": self.entities, "blocks": self.blocks, "layers": self.layers}

    @classmethod
    def from_dict(cls, d):
        if d.get("format") != FORMAT:
            raise ValueError("not a KanzonasCAD circuit")
        if int(d.get("version", 1)) > VERSION:
            raise ValueError("saved by a newer KanzonasCAD")
        return cls(d["name"], d.get("category", ""), d.get("description", ""),
                   d.get("entities", []), d.get("blocks", []), d.get("layers", []))

    def renamed(self, name=None, category=None, description=None):
        """A copy under another name, category or description."""
        d = self.to_dict()
        for k, v in (("name", name), ("category", category), ("description", description)):
            if v is not None:
                d[k] = v
        return Circuit.from_dict(d)

    def defs(self):
        """{name: BlockDef} of its own blocks."""
        if self._defs is None:
            self._defs = {b["name"]: M.BlockDef.from_dict(b) for b in self.blocks}
        return self._defs

    def objects(self, blocks=None):
        """Its objects as entities around (0, 0), its blocks shown (blocks: {name: BlockDef}
        to show instead, a project's own)."""
        defs = dict(self.defs())
        defs.update(blocks or {})
        return [M.Entity.from_dict(d, defs) for d in self.entities]

    def extents(self):
        bb = None
        for e in self.objects():
            bb = G.bbox_union(bb, e.bbox())
        return bb or (0.0, 0.0, 0.0, 0.0)

    def counts(self):
        """(devices, wires, other objects): what the browser says it holds."""
        from .tags import is_device
        devs = wires = other = 0
        for e in self.objects():
            if isinstance(e, M.Wire):
                wires += 1
            elif is_device(e):
                devs += 1
            else:
                other += 1
        return devs, wires, other


def make(project, ents, base, name, category="", description=""):
    """A circuit of ents (a sheet's objects) with base as its base point."""
    bx, by = base
    out, blocks, used = [], {}, set()
    for e in ents:
        if isinstance(e, M.Insert) and e.defn is not None:
            blocks[e.block] = e.defn.to_dict()
            used.update(x.layer for x in e.defn.entities)
        used.add(e.layer)
        out.append(e.moved(-bx, -by).to_dict())
    layers = [project.layers[n].to_dict() for n in sorted(used) if n in project.layers]
    return Circuit(name, category, description, out, list(blocks.values()), layers)


def transformed(e, at, angle=0.0, scale=1.0):
    """An object of a circuit (around (0, 0)) scaled, turned by angle and moved to at."""
    c = e
    if abs(scale - 1.0) > 1e-12:
        c = c.scaled((0.0, 0.0), scale)
        if isinstance(c, M.Wire) and c.labels:
            c = c.copy(labels=[t * scale for t in c.labels])
    if angle % 360.0:
        c = c.rotated((0.0, 0.0), angle)
    c = c.moved(at[0], at[1])
    c.id = None
    return c


def _block_names(project, circuit):
    """{circuit block name: the name it goes by in project} (project_block_name: a footprint
    whose name a symbol of the project has is kept apart, as Paste does)."""
    return {n: M.project_block_name(project, n, d.kind) for n, d in circuit.defs().items()}


def preview(project, circuit, at, angle=0.0, scale=1.0):
    """What placing the circuit at at would put on the sheet (tags and numbers not yet
    given): the project's own blocks shown where it has them."""
    names = _block_names(project, circuit)
    shown = {}
    for n, d in circuit.defs().items():
        got = project.blocks.get(names[n])
        shown[n] = got if got is not None and got.kind == d.kind else d
    return [transformed(e, at, angle, scale) for e in circuit.objects(shown)]


def _link_names(project, taken_extra=()):
    """A maker of connector names nobody uses (A, B... Z, AA...), none given twice."""
    from .wirenums import connectors, letters
    taken = set(connectors(project)) | set(taken_extra)
    state = {"i": 0}

    def nxt():
        while letters(state["i"]) in taken:
            state["i"] += 1
        name = letters(state["i"])
        taken.add(name)
        return name
    return nxt


def place(ed, project, sheet, circuit, at, angle=0.0, scale=1.0):
    """In edit ed: the circuit put on sheet with its base point at at (see the module's
    notes). Returns the objects added."""
    from . import tags
    # (its layers the project doesn't have, as they were where it was saved; a layer the
    # project has keeps its own, as Paste does)
    lays = {d["name"]: d for d in circuit.layers if isinstance(d, dict) and d.get("name")}
    used = {d.get("layer", "0") for d in circuit.entities}
    for d in circuit.defs().values():
        used.update(x.layer for x in d.entities)
    for name in sorted(used):
        if name and name not in project.layers:
            d = lays.get(name)
            ed.layer(name, None, M.Layer.from_dict(d).to_dict() if d is not None
                     else M.Layer(name).to_dict())
    names = _block_names(project, circuit)
    for n, d in circuit.defs().items():
        if names[n] not in project.blocks:
            ed.block(M.renamed_block(d, names[n]))
    shown = {n: project.blocks[names[n]] for n in names}
    objs = []
    for e in circuit.objects(shown):
        c = transformed(e, at, angle, scale)
        if isinstance(c, M.Insert):
            c.block = names.get(c.block, c.block)
            c.defn = project.blocks.get(c.block, c.defn)
            c._world = None
            c = _sized(project, sheet, c)
        elif isinstance(c, M.Wire) and not c.num_lock and c.num:
            c = c.copy(num=None)              # (numbered as the sheet's own)
            c.id = None
        objs.append(c)
    # the devices' old hidden ids, before they get new ones
    old_dev = [e.attrs.get("DEV") if tags.is_device(e) else None for e in objs]
    # connectors: new names, the same within the circuit (a pair stays a pair)
    new_name = _link_names(project)
    renamed = {}
    for i, e in enumerate(objs):
        if isinstance(e, M.Insert) and e.defn is not None and e.defn.wiring == "link":
            attrs = dict(e.attrs)
            old = attrs.get("TAG", "").strip().upper()
            if old:
                if old not in renamed:
                    renamed[old] = new_name()
                attrs["TAG"] = renamed[old]
            attrs.pop("FROM", None)           # (paired by its new name instead)
            objs[i] = e.copy(attrs=attrs)
    old_tag = [e.attrs.get("TAG", "").strip().upper() if tags.is_device(e) else ""
               for e in objs]
    made = tags.retag_copies(project, sheet, objs)
    new_dev, by_tag = {}, {}
    for old, tag, e in zip(old_dev, old_tag, made):
        if old:
            new_dev[old] = e
        if tag:
            by_tag.setdefault(tag, e)
    out = []
    for e in made:
        got = _relinked(e, new_dev, by_tag)
        if got is not None:
            e = e.copy(attrs=got)
            e.id = None
        out.append(ed.add(sheet, e))
    return out


def _sized(project, sheet, e):
    """A symbol's tag, a footprint's label, at the heights this project gives them on this
    sheet (the circuit may have been saved when they were others, or from another project),
    as Insert places them."""
    st = project.settings
    if e.defn is not None and e.defn.kind == "symbol" and e.tag_h:
        out = e.copy(tag_h=float(st.get("tag_height", 0.1)) * sheet.k())
    elif e.defn is not None and e.defn.kind == "footprint" and (e.label or e.tag_h):
        out = e.copy(tag_h=float(st.get("fp_label_height", 0.08)) * sheet.k(),
                     label_k=sheet.k())
    else:
        return e
    out.id = None
    return out


def _belongs(e):
    """An object that belongs to a device: a contact (or a terminal, a module's continued
    piece), a footprint, a dashed box naming one."""
    from . import tags
    return tags.is_child(e) or tags.is_footprint(e) or tags.is_linked_box(e)


def _relinked(e, new_dev, by_tag):
    """The attributes of an object of a circuit that belongs to a device, linked to the new
    copy of its device ({old hidden id: device}; one linked by tag only, {old tag: device}),
    or with no link when its device stayed behind (its tag cleared too: kept, it would link
    to whatever device has that tag here; a footprint keeps a tag typed on its own). None:
    nothing to change."""
    from . import tags
    if not _belongs(e) or tags.is_device(e):
        return None
    attrs = dict(e.attrs)
    parent, tag = attrs.get("PARENT", ""), attrs.get("TAG", "").strip().upper()
    if not parent and not tag:
        return None
    dev = new_dev.get(parent) if parent else by_tag.get(tag)
    if dev is not None:
        attrs["PARENT"] = dev.attrs["DEV"]
        attrs["TAG"] = dev.attrs.get("TAG", "")
    elif not parent and tags.is_footprint(e):
        return None                             # (a name typed on a footprint of its own)
    else:
        attrs.pop("PARENT", None)
        attrs.pop("TAG", None)
    return attrs


def turned(angle):
    """angle (degrees) a quarter turn on."""
    return (angle + 90.0) % 360.0


def fits(scale):
    """A scale a circuit can be placed at."""
    return isinstance(scale, (int, float)) and math.isfinite(scale) and 1e-3 <= scale <= 1e3
