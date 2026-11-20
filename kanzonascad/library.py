"""Your library: schematic symbols, panel footprints and parts, kept in a folder of their own
(Documents/KanzonasCAD Library to start; in a portable copy, Library in its data folder),
outside the program and outside any project, so they last through updates and are there for
every project. No Qt here.

    <library>/symbols/<name>.kzblock      a schematic symbol (JSON: a BlockDef)
    <library>/footprints/<name>.kzblock   a panel footprint
    <library>/parts.json                  the parts catalog

A part ties a manufacturer's part number to its schematic symbol and its panel footprint:
placing the part's symbol fills in its manufacturer, catalog number and description.

The program's own JIC/NFPA symbols (symbols_jic.py) and generic footprints
(footprints_generic.py) are listed too, read-only; a block of yours with the same name takes
their place.
"""

import json
import os
import re
import uuid

from .model import BlockDef

FOLDERS = {"symbol": "symbols", "footprint": "footprints"}
SUFFIX = ".kzblock"
_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def default_folder():
    # (the tests and the self-test point this at a scratch folder, never at your library)
    env = os.environ.get("KANZONASCAD_LIBRARY")
    if env:
        return env
    from . import paths
    portable = paths.portable_data_dir()
    if portable:                        # (a portable copy: the library travels with it)
        return os.path.join(portable, "Library")
    docs = os.path.join(os.path.expanduser("~"), "Documents")
    if not os.path.isdir(docs):
        docs = os.path.expanduser("~")
    return os.path.join(docs, "KanzonasCAD Library")


def safe_name(name):
    """A block name usable as a file name (the name itself is kept inside the file)."""
    s = _BAD.sub("_", name).strip().rstrip(".")
    return s or "block"


class Part:
    FIELDS = ("manufacturer", "catalog", "description", "symbol", "footprint", "notes")

    def __init__(self, id=None, **kw):
        self.id = id or uuid.uuid4().hex[:12]
        for f in self.FIELDS:
            setattr(self, f, str(kw.get(f, "") or ""))

    def to_dict(self):
        d = {"id": self.id}
        d.update({f: getattr(self, f) for f in self.FIELDS})
        return d

    @classmethod
    def from_dict(cls, d):
        return cls(**d)

    def label(self):
        bits = [b for b in (self.manufacturer, self.catalog) if b]
        out = " ".join(bits) or "(no part number)"
        if self.description:
            out += " - " + self.description
        return out

    def attrs(self):
        """What a block reference of this part carries."""
        return {"MFR": self.manufacturer, "CAT": self.catalog, "DESC": self.description,
                "PART": self.id}


class Library:
    def __init__(self, folder=None):
        self.folder = folder or default_folder()
        self._builtins = None
        self.part_problems = []         # (part files it couldn't read: parts)

    # ---- folders ---------------------------------------------------------------------------
    def _dir(self, kind):
        return os.path.join(self.folder, FOLDERS[kind])

    def _path(self, kind, name):
        return os.path.join(self._dir(kind), safe_name(name) + SUFFIX)

    def ensure(self):
        for kind in FOLDERS:
            os.makedirs(self._dir(kind), exist_ok=True)

    # ---- blocks ----------------------------------------------------------------------------
    def builtins(self, kind="symbol"):
        """The program's own blocks of one kind: {name: BlockDef}."""
        if self._builtins is None:
            from .symbols_jic import builtin_symbols
            from .footprints_generic import builtin_footprints
            self._builtins = {"symbol": {b.name: b for b in builtin_symbols()},
                              "footprint": {b.name: b for b in builtin_footprints()}}
        return self._builtins.get(kind, {})

    def blocks(self, kind):
        """{name: BlockDef} of one kind: the program's own with yours over them.
        Unreadable files are skipped and named in the second item returned."""
        out = {}
        bad = []
        out.update(self.builtins(kind))
        d = self._dir(kind)
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                if not fn.endswith(SUFFIX):
                    continue
                path = os.path.join(d, fn)
                try:
                    with open(path, encoding="utf-8") as f:
                        b = BlockDef.from_dict(json.load(f))
                except (OSError, ValueError, KeyError, TypeError) as ex:
                    bad.append("%s (%s)" % (fn, ex))
                    continue
                b.kind = kind
                out[b.name] = b
        return out, bad

    def get(self, kind, name):
        blocks, _bad = self.blocks(kind)
        return blocks.get(name)

    def save_block(self, defn):
        """Write a block to the library (a block of the same name is replaced)."""
        self.ensure()
        path = self._path(defn.kind, defn.name)
        _write_json(path, defn.to_dict())
        return path

    def delete_block(self, kind, name):
        path = self._path(kind, name)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def has_own(self, kind, name):
        return os.path.exists(self._path(kind, name))

    def save_block_as(self, defn, old_name=None):
        """Write a changed block (Properties..., Edit block...). Renamed (old_name given and
        different) from one of your own: your file under the old name goes, and the parts
        that linked to it link to the new name. A built-in symbol is never changed (yours, of
        the same name, takes its place; renamed, it stays, with the parts linking to it).
        Returns (the file written, how many parts were relinked)."""
        renamed = bool(old_name) and old_name != defn.name
        own_old = renamed and self.has_own(defn.kind, old_name)
        old_path = self._path(defn.kind, old_name) if renamed else None
        path = self.save_block(defn)
        moved = 0
        if own_old:
            field = "symbol" if defn.kind == "symbol" else "footprint"
            parts = self.parts()
            for p in parts:
                if getattr(p, field) == old_name:
                    setattr(p, field, defn.name)
                    moved += 1
            if moved:
                self.save_parts(parts)
            # (on Windows "Coil" and "coil" are one file: the one just written)
            if os.path.normcase(old_path) != os.path.normcase(path):
                os.remove(old_path)
        return path, moved

    # ---- manufacturer, family, series ------------------------------------------------------
    def maker_values(self, field, manufacturer=None, family=None):
        """The values of a block field ("manufacturer", "family" or "series") already in the
        library, sorted (case-insensitively, each spelled as first met): only the families of
        a manufacturer and the series of a manufacturer's family when those are given (""
        or None: any). Manufacturers also come from your parts."""
        if field not in ("manufacturer", "family", "series"):
            raise ValueError(field)
        seen = {}

        def take(v):
            v = (v or "").strip()
            if v and v.lower() not in seen:
                seen[v.lower()] = v

        def same(a, b):
            return not b or (a or "").strip().lower() == b.strip().lower()
        for kind in FOLDERS:
            blocks, _bad = self.blocks(kind)
            for b in blocks.values():
                if field != "manufacturer" and not same(b.manufacturer, manufacturer):
                    continue
                if field == "series" and not same(b.family, family):
                    continue
                take(getattr(b, field))
        if field == "manufacturer":
            try:
                for p in self.parts():
                    take(p.manufacturer)
            except (OSError, ValueError):
                pass                # (an unreadable parts.json: the Library panel says so)
        return sorted(seen.values(), key=str.lower)

    # ---- parts -----------------------------------------------------------------------------
    # One file a part, in the library's parts folder (the owner's two library folders, Nov
    # 2026: a shared library in a synced folder; two people adding parts at once each write a
    # file of their own, never one file both change, which a sync app turns into a conflict
    # copy). A library from before 0.20.1 kept them all in parts.json: still read, and moved to
    # files of their own the first time a part is saved or deleted.
    PARTS_DIR = "parts"

    def _parts_path(self):
        return os.path.join(self.folder, "parts.json")

    def _parts_dir(self):
        return os.path.join(self.folder, self.PARTS_DIR)

    def _part_file(self, part_id):
        return os.path.join(self._parts_dir(), safe_name(part_id) + ".json")

    def _legacy_parts(self):
        path = self._parts_path()
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return [Part.from_dict(d) for d in data.get("parts", [])]

    def parts(self):
        """Every part, by maker and catalog number. The files it couldn't read, and the
        conflict copies a sync app left ("1a2b3c (Keith's PC).json": a file not named by the
        part in it), are in part_problems, not among the parts."""
        self.part_problems = []
        got = {p.id: p for p in self._legacy_parts()}
        d = self._parts_dir()
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                if not fn.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(d, fn), encoding="utf-8") as f:
                        part = Part.from_dict(json.load(f))
                except (OSError, ValueError, TypeError) as ex:
                    self.part_problems.append("%s (%s)" % (fn, ex))
                    continue
                if fn[:-5] != safe_name(part.id):
                    self.part_problems.append("%s (a copy a sync app left: %s is %s)" % (
                        fn, part.label(), safe_name(part.id) + ".json"))
                    continue
                got[part.id] = part
        return sorted(got.values(), key=lambda p: (p.manufacturer.lower(), p.catalog.lower()))

    def _move_legacy(self):
        """parts.json's parts into files of their own, then parts.json gone."""
        legacy = self._legacy_parts()
        if not legacy:
            return
        os.makedirs(self._parts_dir(), exist_ok=True)
        for p in legacy:
            if not os.path.exists(self._part_file(p.id)):
                _write_json(self._part_file(p.id), p.to_dict())
        os.remove(self._parts_path())

    def save_parts(self, parts):
        """The library's parts made these (each written to its own file; the others deleted)."""
        self._move_legacy()
        keep = {p.id for p in parts}
        for p in self.parts():
            if p.id not in keep:
                self.delete_part(p.id)
        for p in parts:
            self.save_part(p)

    def save_part(self, part):
        self._move_legacy()
        os.makedirs(self._parts_dir(), exist_ok=True)
        _write_json(self._part_file(part.id), part.to_dict())

    def delete_part(self, part_id):
        self._move_legacy()
        path = self._part_file(part_id)
        if os.path.exists(path):
            os.remove(path)

    def part(self, part_id):
        for p in self.parts():
            if p.id == part_id:
                return p
        return None

    def parts_using(self, kind, name):
        field = "symbol" if kind == "symbol" else "footprint"
        return [p for p in self.parts() if getattr(p, field) == name]


def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
