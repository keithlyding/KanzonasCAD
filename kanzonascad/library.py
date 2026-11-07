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
    def _parts_path(self):
        return os.path.join(self.folder, "parts.json")

    def parts(self):
        path = self._parts_path()
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return [Part.from_dict(d) for d in data.get("parts", [])]

    def save_parts(self, parts):
        os.makedirs(self.folder, exist_ok=True)
        _write_json(self._parts_path(), {"format": "kanzonascad-parts", "version": 1,
                                         "parts": [p.to_dict() for p in parts]})

    def save_part(self, part):
        parts = [p for p in self.parts() if p.id != part.id]
        parts.append(part)
        parts.sort(key=lambda p: (p.manufacturer.lower(), p.catalog.lower()))
        self.save_parts(parts)

    def delete_part(self, part_id):
        self.save_parts([p for p in self.parts() if p.id != part_id])

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
