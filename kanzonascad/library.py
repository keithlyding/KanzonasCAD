"""Your library: schematic symbols, panel footprints and parts, kept in a folder of their own
(Documents/KanzonasCAD Library to start; in a portable copy, Library in its data folder),
outside the program and outside any project, so they last through updates and are there for
every project. No Qt here.

    <library>/symbols/<name>.kzblock      a schematic symbol (JSON: a BlockDef)
    <library>/footprints/<name>.kzblock   a panel footprint
    <library>/parts.json                  the parts catalog

A part ties a manufacturer's part number to its schematic symbol and its panel footprint:
placing the part's symbol fills in its manufacturer, catalog number and description.

The program's own JIC/NFPA symbols (symbols_jic.py) are listed too, read-only; a symbol of
yours with the same name takes their place.
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
    def builtins(self):
        if self._builtins is None:
            from .symbols_jic import builtin_symbols
            self._builtins = {b.name: b for b in builtin_symbols()}
        return self._builtins

    def blocks(self, kind):
        """{name: BlockDef} of one kind: the program's own (symbols) with yours over them.
        Unreadable files are skipped and named in the second item returned."""
        out = {}
        bad = []
        if kind == "symbol":
            out.update(self.builtins())
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
