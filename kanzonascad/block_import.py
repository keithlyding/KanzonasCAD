"""Library > Import blocks from folder...: the blocks you made in AutoCAD or AutoCAD Electrical
(DWG and DXF files: a folder of them, or one drawing) read as KanzonasCAD blocks, then put in
your library in one go. No Qt here (import_blocks_window.py is the window); ezdxf and ezdwg are
imported only when a file is read.

What is read from a file:
- a file that is itself one block (WBLOCK, the usual way to keep a block: its model space
  holds the block's drawing and its attribute definitions): one block, named after the file;
- a drawing of named blocks (its model space holds only block references, or nothing): each
  named block (not one only used inside another), with no anonymous, external reference,
  layout or dimension-arrowhead ("_" names) blocks; with a drawing of its own beside them, the
  whole drawing too, as one block, unticked to start.

AutoCAD Electrical's wire connection attributes (X?TERMnn) become pins, its TAG1 the tag
spot (fileio.layout_defn)."""

import os

from . import fileio
from . import model as M
from .library import Library, _writable

EXTENSIONS = (".dwg", ".dxf")
CHOICES = ("skip", "replace", "both")      # (a name already in the library: default skip)


class Found:
    """One block found in a file: its name, the file, its BlockDef (None when it couldn't be
    read: error says why), the kind it is to be imported as, whether it is ticked, and what
    to do when its name is taken (CHOICES)."""

    def __init__(self, name, path, defn=None, error=None, whole=False):
        self.name = name
        self.path = path
        self.defn = defn
        self.error = error
        self.whole = whole              # (the whole drawing of a file of named blocks)
        self.kind = defn.kind if defn is not None else "symbol"
        self.ticked = defn is not None and not whole
        self.choice = "skip"

    def pins(self):
        return len(self.defn.pins) if self.defn is not None else 0


def drawing_files(folder, subfolders=False):
    """The DWG and DXF files in a folder (and its subfolders, when asked), by name."""
    out = []
    if subfolders:
        for root, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            out += [os.path.join(root, f) for f in files
                    if os.path.splitext(f)[1].lower() in EXTENSIONS]
    else:
        out = [os.path.join(folder, f) for f in os.listdir(folder)
               if os.path.splitext(f)[1].lower() in EXTENSIONS and
               os.path.isfile(os.path.join(folder, f))]
    return sorted(out, key=lambda p: os.path.relpath(p, folder).lower())


def read_blocks(path):
    """Every block of one file, as Found rows; a file that can't be read is one row with the
    reason (never raised: one damaged file among many is listed, the others still come in)."""
    stem = os.path.splitext(os.path.basename(path))[0]
    try:
        if path.lower().endswith(".dwg"):
            doc, units, _left, _reader = fileio.dwg_document(path)
        else:
            doc, units = fileio.dxf_document(path), None
        got = blocks_of(doc, path, units)
    except Exception as ex:     # (whatever the reader raised on a damaged file: listed, with why)
        return [Found(stem, path, error=reason(ex))]
    return got or [Found(stem, path, error="no block or drawing in it")]


def reason(ex):
    text = str(ex).strip() or type(ex).__name__
    return text if len(text) < 200 else text[:197] + "..."


def _listable(blk):
    name = str(blk.name)
    from .dwgread import ANON_PREFIX
    if not name or name.startswith(("*", "_", ANON_PREFIX)) or blk.is_any_layout:
        return False
    rec = blk.block
    return not (rec.is_xref or rec.is_xref_overlay)


def blocks_of(doc, path, units=None):
    """The Found rows of an ezdxf document (see the module's docstring). units: the
    drawing's $INSUNITS when the document's own can't be trusted (a converted DWG)."""
    if units is None:
        units = int(doc.header.get("$INSUNITS", 0) or 0)
    k = fileio._UNITS.get(units, 1.0)
    layers = {dl.dxf.name: fileio._dxf_layer_color(dl) for dl in doc.layers}
    cache = {"__layers__": layers}
    msp = doc.modelspace()
    attdefs = loose = False
    top = set()
    for e in msp:
        t = e.dxftype()
        if t == "ATTDEF":
            attdefs = True
        elif t == "INSERT":
            top.add(str(e.dxf.name))
        elif t != "VIEWPORT":
            loose = True
    named = [b for b in doc.blocks if _listable(b)]
    inner = set()
    for b in named:
        inner |= {str(e.dxf.name) for e in b if e.dxftype() == "INSERT"}
    stem = os.path.splitext(os.path.basename(path))[0]
    out = []
    if attdefs or not named:
        if attdefs or loose or top:
            base = doc.header.get("$INSBASE", (0.0, 0.0, 0.0))
            out.append(_one(stem, path, msp, (base[0] * k, base[1] * k), k, cache, None))
        return out
    for b in named:
        if b.name in top or b.name not in inner:
            base = b.block.dxf.base_point
            row = _one(str(b.name), path, b, (base[0] * k, base[1] * k), k, cache,
                       fileio._kz_block(b))
            if row is not None:
                out.append(row)
    if loose:
        base = doc.header.get("$INSBASE", (0.0, 0.0, 0.0))
        row = _one(stem, path, msp, (base[0] * k, base[1] * k), k, cache, None, whole=True)
        if row is not None:
            out.append(row)
    return out


def _one(name, path, layout, base, k, cache, own, whole=False):
    """One block's Found row (None: nothing to draw, as AutoCAD Electrical's hidden WD_M)."""
    try:
        parts = [e for e, _on0 in fileio.layout_parts(layout, base, k, 0, cache)[0]]
        defn = fileio.layout_defn(name, layout, base, k, parts, cache["__layers__"], own,
                                  ace=True)
    except Exception as ex:     # (a block the reader can't take: listed, with why)
        return Found(name, path, error=reason(ex))
    if defn is None:
        return None
    return Found(name, path, defn, whole=whole)


def read_all(paths):
    """Every block of several files (read_blocks of each: a generator, one file a step, so
    the window can show its progress and stay responsive)."""
    for p in paths:
        yield p, read_blocks(p)


def taken_names(lib):
    """{kind: names of the blocks your libraries and the program already have}."""
    return {kind: set(lib.blocks(kind)[0]) for kind in ("symbol", "footprint")}


def statuses(lib, rows, taken=None):
    """Each row's status: "error", "taken" (a block of its name and kind is in the library, or
    on a row before it) or "new"."""
    taken = taken if taken is not None else taken_names(lib)
    seen = {"symbol": set(), "footprint": set()}
    out = []
    for r in rows:
        if r.defn is None:
            out.append("error")
            continue
        out.append("taken" if r.name in taken[r.kind] or r.name in seen[r.kind] else "new")
        seen[r.kind].add(r.name)
    return out


def libraries(lib):
    """The libraries blocks can go to: [(key, Library, writable)], your first library and the
    second when there is one."""
    out = []
    for key, one in (("first", lib), ("second", lib.second)):
        if one is None:
            continue
        try:
            _writable(one)
            ok = True
        except OSError:
            ok = False
        out.append((key, one, ok))
    return out


class Write:
    """One block file to write: the row, the name it goes in under, its file, the block."""

    def __init__(self, row, name, path, defn):
        self.row, self.name, self.path, self.defn = row, name, path, defn


class Importer:
    """The ticked rows put in a library, one block a step (step()); rollback() puts back the
    files as they were (Cancel). target: "first" or "second"."""

    def __init__(self, lib, rows, category="Imported", target="first"):
        dest = lib.second if target == "second" and lib.second is not None else lib
        _writable(dest)                 # (OSError: a read-only library, told before any write)
        self.lib = lib
        self.dest = Library(dest.folder)    # (written there, whichever library has the name)
        self.category = (category or "").strip() or "Imported"
        self.todo = [r for r in rows if r.ticked and r.defn is not None]
        self.taken = taken_names(lib)
        self.written = []               # [(file, what it held before, or None)]
        self.imported, self.skipped, self.failed = [], [], []
        self.at = 0

    def total(self):
        return len(self.todo)

    def _taken(self, kind, name):
        return name in self.taken[kind] or self.dest.has_own(kind, name)

    def next_write(self):
        """The next ticked row decided (its name: skipped, replaced or kept both) and what
        it was before noted for rollback, without writing it: a Write to hand to write(),
        None when the row is skipped, False when all rows are done. On the program's own
        thread (the names taken so far change here only)."""
        if self.at >= len(self.todo):
            return False
        r = self.todo[self.at]
        self.at += 1
        name = r.name
        if self._taken(r.kind, name):
            if r.choice == "skip":
                self.skipped.append((r, "a block named %s is in the library" % name))
                return None
            if r.choice == "both":
                n = 2
                while self._taken(r.kind, "%s (%d)" % (r.name, n)):
                    n += 1
                name = "%s (%d)" % (r.name, n)
        d = dict(r.defn.to_dict(), name=name, kind=r.kind, category=self.category)
        if r.kind == "symbol" and d.get("tag_pos") is None:
            # (made a symbol: its tag above its drawing, as Make block puts it)
            bb = r.defn.extents()
            if bb is not None:
                d["tag_pos"] = [(bb[0] + bb[2]) / 2, bb[3] + 0.1]
        w = Write(r, name, self.dest._path(r.kind, name), M.BlockDef.from_dict(d))
        try:
            old = None
            if os.path.exists(w.path):
                with open(w.path, "rb") as f:
                    old = f.read()
        except OSError as ex:
            self.failed.append((r, str(ex)))
            return None
        self.written.append((w.path, old))
        self.taken[r.kind].add(name)
        return w

    def write(self, w):
        """The block's file written (flushed to disk: it takes a disk's own time, so the
        window can run several of these at once on threads of their own; only the
        library's file is touched). OSError when it can't be."""
        self.dest.save_block(w.defn)

    def wrote(self, w, error=None):
        """A write() finished (error: its OSError, or None): counted, in the rows' order."""
        if error is not None:
            self.failed.append((w.row, str(error)))
        else:
            self.imported.append((w.row, w.name))

    def step(self):
        """Put the next block in, written before it returns; False when all are done."""
        w = self.next_write()
        if w is False:
            return False
        if w is not None:
            try:
                self.write(w)
            except OSError as ex:
                self.wrote(w, ex)
            else:
                self.wrote(w)
        return True

    def run(self):
        while self.step():
            pass

    def rollback(self):
        """Every file written put back as it was (a new one deleted)."""
        for path, old in reversed(self.written):
            if old is None:
                if os.path.exists(path):
                    os.remove(path)
            else:
                with open(path, "wb") as f:
                    f.write(old)
        self.written = []
        self.imported = []

    def summary(self, unread=()):
        """What was done, in words (unread: rows that couldn't be read)."""
        lines = ["%d imported, %d skipped, %d failed." % (
            len(self.imported), len(self.skipped), len(self.failed) + len(unread))]
        renamed = [(r, n) for r, n in self.imported if n != r.name]
        if renamed:
            lines.append("Kept both, under new names: " + ", ".join(
                "%s as %s" % (r.name, n) for r, n in renamed[:10]) +
                (" ..." if len(renamed) > 10 else ""))
        for what, items in (("Skipped", self.skipped), ("Failed", self.failed),
                            ("Couldn't be read", [(r, r.error) for r in unread])):
            if items:
                lines.append("%s:" % what)
                lines += ["  %s (%s): %s" % (r.name, os.path.basename(r.path), why)
                          for r, why in items[:20]]
                if len(items) > 20:
                    lines.append("  ... and %d more" % (len(items) - 20))
        return "\n".join(lines)
