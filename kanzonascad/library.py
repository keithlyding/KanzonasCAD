"""Your library: schematic symbols, panel footprints and parts, kept in a folder of their own
(Documents/KanzonasCAD Library to start; in a portable copy, Library in its data folder),
outside the program and outside any project, so they last through updates and are there for
every project. No Qt here.

    <library>/symbols/<name>.kzblock      a schematic symbol (JSON: a BlockDef)
    <library>/footprints/<name>.kzblock   a panel footprint
    <library>/parts/<id>.json             a part (parts.json before 0.21)
    <library>/circuits/<name>.kzcircuit   a saved circuit (circuits.py)

A part ties a manufacturer's part number to its schematic symbol and its panel footprint:
placing the part's symbol fills in its manufacturer, catalog number and description.

The program's own JIC/NFPA symbols (symbols_jic.py), IEC 60617 symbols (symbols_iec.py),
generic footprints (footprints_generic.py) and Allen-Bradley parts and footprints
(allen_bradley.py) are listed too, read-only; a block or part of yours with the same name (or
id) takes their place.
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

    def __init__(self, id=None, builtin=False, **kw):
        self.id = id or uuid.uuid4().hex[:12]
        for f in self.FIELDS:
            setattr(self, f, str(kw.get(f, "") or ""))
        self.builtin = bool(builtin)    # one of the program's own (allen_bradley.py)

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
    def __init__(self, folder=None, second=None):
        self.folder = folder or default_folder()
        self._builtins = None
        self.part_problems = []         # (part files it couldn't read: parts)
        # a second library folder (the owner's two folders, Nov 2026: one shared, one personal,
        # each anything): searched with this one; save_second says new blocks and parts go there
        self.second = Library(second) if second else None
        self.save_second = False
        self.second_parts = set()       # (the parts listed from the second library: parts)

    def set_second(self, folder):
        self.second = Library(folder) if folder else None
        if self.second is None:
            self.save_second = False

    def where(self, kind, name):
        """Which library a block comes from: "first", "second", or "built in" (yours first)."""
        if self.has_own(kind, name):
            return "first"
        if self.second is not None and self.second.has_own(kind, name):
            return "second"
        return "built in" if name in self.builtins(kind) else None

    def _target(self):
        """The library new things are saved to."""
        return _writable(self.second if self.save_second and self.second is not None
                         else self)

    def _home(self, kind, name):
        """The library a block is saved to: the one it is in, else where new things go."""
        if self.has_own(kind, name):
            return _writable(self)
        if self.second is not None and self.second.has_own(kind, name):
            return _writable(self.second)
        return self._target()

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
            from .symbols_iec import iec_symbols
            from .footprints_generic import builtin_footprints
            from .allen_bradley import ab_footprints, ab_symbols
            self._builtins = {
                "symbol": {b.name: b for b in builtin_symbols() + ab_symbols() +
                           iec_symbols()},
                "footprint": {b.name: b for b in builtin_footprints() + ab_footprints()}}
        return self._builtins.get(kind, {})

    def builtin_parts(self):
        """The program's own parts (Allen-Bradley catalog numbers: allen_bradley.py), read
        only: {id: Part}."""
        if getattr(self, "_builtin_parts", None) is None:
            from .allen_bradley import ab_parts
            self._builtin_parts = {p.id: p for p in ab_parts()}
        return self._builtin_parts

    def blocks(self, kind):
        """{name: BlockDef} of one kind: the program's own, the second library's over them,
        this one's over those (a name in both libraries: this one's). Unreadable files are
        skipped and named in the second item returned."""
        out = dict(self.builtins(kind))
        bad = []
        if self.second is not None:
            got, bad2 = self.second._own_blocks(kind)
            out.update(got)
            bad += ["%s (second library)" % b for b in bad2]
        got, bad1 = self._own_blocks(kind)
        out.update(got)
        return out, bad1 + bad

    def _own_blocks(self, kind):
        out = {}
        bad = []
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
        """Write a block to the library (a block of the same name is replaced): where it
        already is, else where new things go (_target)."""
        lib = self._home(defn.kind, defn.name)
        if lib is not self:
            return lib.save_block(defn)
        self.ensure()
        path = self._path(defn.kind, defn.name)
        _write_json(path, defn.to_dict())
        return path

    def delete_block(self, kind, name):
        if not self.has_own(kind, name) and self.second is not None and \
                self.second.has_own(kind, name):
            return _writable(self.second).delete_block(kind, name)
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
            parts = self.parts(builtin=False)
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
    # copy). A library from before 0.21 kept them all in parts.json: still read, and moved to
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

    def parts(self, builtin=True):
        """Every part of both libraries (a part in both: this one's), and the program's own
        (builtin False: not those; a part of yours with a built-in part's id, or its maker
        and catalog number, takes its place), by maker and catalog number; the second
        library's ids in second_parts."""
        got = {p.id: p for p in self._own_parts()}
        problems = list(self.part_problems)
        self.second_parts = set()
        if self.second is not None:
            for p in self.second._own_parts():
                if p.id not in got:
                    got[p.id] = p
                    self.second_parts.add(p.id)
            problems += ["%s (second library)" % t for t in self.second.part_problems]
        self.part_problems = problems
        if builtin:
            # (a part of yours with a built-in one's maker and catalog number stands for it)
            mine = {(p.manufacturer.lower(), p.catalog.lower()) for p in got.values()}
            for p in self.builtin_parts().values():
                if p.id not in got and (not p.catalog or (p.manufacturer.lower(),
                                                          p.catalog.lower()) not in mine):
                    got[p.id] = p
        return sorted(got.values(), key=lambda p: (p.manufacturer.lower(), p.catalog.lower()))

    def _part_home(self, part_id):
        if part_id in {p.id for p in self._own_parts()}:
            return _writable(self)
        if self.second is not None and part_id in {p.id for p in self.second._own_parts()}:
            return _writable(self.second)
        return self._target()

    def _own_parts(self):
        """This library's own parts, by maker and catalog number. The files it couldn't read, and the
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
        parts = [p for p in parts if not p.builtin]     # (the program's own stay its own)
        for p in self.parts(builtin=False):
            if p.id not in keep:
                self.delete_part(p.id)
        for p in parts:
            self.save_part(p)

    def save_part(self, part):
        """Write a part (a built-in one changed: your copy, of its id, takes its place)."""
        if part.builtin:
            part = Part.from_dict(part.to_dict())
        lib = self._part_home(part.id)
        if lib is not self:
            return lib.save_part(part)
        self._move_legacy()
        os.makedirs(self._parts_dir(), exist_ok=True)
        _write_json(self._part_file(part.id), part.to_dict())

    def delete_part(self, part_id):
        lib = self._part_home(part_id)
        if lib is not self:
            return lib.delete_part(part_id)
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


    # ---- saved circuits (circuits.py) -------------------------------------------------------
    # One file a circuit, in either library folder, as blocks are kept: a circuit in both is
    # this one's.
    def _circuit_path(self, name):
        from .circuits import FOLDER, SUFFIX as CSUFFIX
        return os.path.join(self.folder, FOLDER, safe_name(name) + CSUFFIX)

    def _own_circuits(self):
        from .circuits import Circuit, FOLDER, SUFFIX as CSUFFIX
        out, bad = {}, []
        d = os.path.join(self.folder, FOLDER)
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                if not fn.endswith(CSUFFIX):
                    continue
                try:
                    with open(os.path.join(d, fn), encoding="utf-8") as f:
                        c = Circuit.from_dict(json.load(f))
                except (OSError, ValueError, KeyError, TypeError) as ex:
                    bad.append("%s (%s)" % (fn, ex))
                    continue
                out[c.name] = c
        return out, bad

    def circuits(self):
        """({name: Circuit} of both libraries (a name in both: this one's), [files it
        couldn't read])."""
        out, bad = {}, []
        if self.second is not None:
            got, bad2 = self.second._own_circuits()
            out.update(got)
            bad += ["%s (second library)" % b for b in bad2]
        got, bad1 = self._own_circuits()
        out.update(got)
        return out, bad1 + bad

    def circuit_where(self, name):
        """"first" or "second": the library a circuit is in (None: in neither)."""
        if os.path.exists(self._circuit_path(name)):
            return "first"
        if self.second is not None and os.path.exists(self.second._circuit_path(name)):
            return "second"
        return None

    def _circuit_home(self, name):
        where = self.circuit_where(name)
        if where == "first":
            return _writable(self)
        if where == "second":
            return _writable(self.second)
        return self._target()

    def save_circuit(self, circuit):
        """Write a circuit (one of the same name is replaced, in the library it is in; a new
        one goes where new things go). Returns the file written."""
        lib = self._circuit_home(circuit.name)
        path = lib._circuit_path(circuit.name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _write_json(path, circuit.to_dict())
        return path

    def delete_circuit(self, name):
        """Take a circuit out of the library it is in. True when one was."""
        where = self.circuit_where(name)
        if where is None:
            return False
        lib = _writable(self if where == "first" else self.second)
        os.remove(lib._circuit_path(name))
        return True

    def rename_circuit(self, old, circuit):
        """Write circuit (renamed, or its category or description changed) where old was,
        and take old's file away when the name changed. Returns the file written."""
        where = self.circuit_where(old)
        lib = _writable(self.second if where == "second" else self)
        path = lib._circuit_path(circuit.name)
        old_path = lib._circuit_path(old)
        if os.path.normcase(path) != os.path.normcase(old_path) and os.path.exists(path):
            raise OSError("a circuit named %s is already in the library" % circuit.name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _write_json(path, circuit.to_dict())
        if os.path.normcase(old_path) != os.path.normcase(path) and os.path.exists(old_path):
            os.remove(old_path)
        return path


def _writable(lib):
    """lib, or OSError when its folder can't be written to (a read-only share is used
    read-only: its blocks and parts listed and placed, never changed)."""
    if os.path.isdir(lib.folder) and not os.access(lib.folder, os.W_OK):
        raise OSError("%s is read-only: it can be used, not changed" % lib.folder)
    return lib


def _write_json(path, data):
    _write_text(path, json.dumps(data, indent=1))


def block_text(defn):
    """A block's file as save_block writes it (worked out apart from the writing: Import
    blocks makes it on the event loop and writes it on a thread, block_import.Importer)."""
    return json.dumps(defn.to_dict(), indent=1)


def _write_text(path, text):
    """A file written safely: to a file beside it, flushed to disk (fsync), then renamed
    over it."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
