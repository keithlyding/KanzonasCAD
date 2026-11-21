"""PLC I/O from a spreadsheet (the owner's list, #14 "PLC I/O from a spreadsheet"; the owner chose
it): an I/O list (CSV, or an Excel workbook's first sheet) brought in as the modules it names,
each on a sheet of its own after the sheet shown, with every point's address, tag and
description written beside its terminal, where the field wire comes in.

The list's first row names its columns (any order, any case; the first that fits each):
- Slot (or Rack, Module slot): rows of one slot are one module;
- Catalog (Catalog number, Cat, Module, Part): a library symbol of that catalog number (its
  catalog, or its name: "1734-IB8 module"), or one of the generic modules by name;
- Point (Channel, Bit, I/O point): its point number on the module (0, 1, ... 15);
- Address (Addr), Tag (Device), Description (Desc): what is written beside the point.

A module the library hasn't got, or a point it hasn't got, is left out and named in the
report: nothing is guessed. No Qt (the windows ask and say)."""

import csv
import os
import re

from . import model as M

COLUMNS = {
    "slot": ("slot", "rack", "module slot"),
    "catalog": ("catalog", "catalog number", "cat", "module", "part"),
    "point": ("point", "channel", "bit", "i/o point", "io point"),
    "address": ("address", "addr"),
    "tag": ("tag", "device"),
    "desc": ("description", "desc"),
}
LAYER = "PLC I/O"
TEXT_H = 0.08               # (paper inches)


def read_rows(path):
    """The list's rows as {slot, catalog, point, address, tag, desc} (strings), in order;
    ValueError when it has no Catalog or Point column."""
    if path.lower().endswith(".xlsx"):
        from openpyxl import load_workbook
        ws = load_workbook(path, read_only=True, data_only=True).worksheets[0]
        table = [["" if v is None else str(v).strip() for v in r]
                 for r in ws.iter_rows(values_only=True)]
    else:
        with open(path, newline="", encoding="utf-8-sig") as f:
            table = [[c.strip() for c in r] for r in csv.reader(f)]
    table = [r for r in table if any(r)]
    if not table:
        raise ValueError("the list is empty")
    head = [h.strip().lower() for h in table[0]]
    where = {}
    for key, names in COLUMNS.items():
        for n in names:
            if n in head:
                where[key] = head.index(n)
                break
    missing = [k for k in ("catalog", "point") if k not in where]
    if missing:
        raise ValueError("its first row names no %s column (the columns it reads: Slot, "
                         "Catalog, Point, Address, Tag, Description)" % " or ".join(missing))
    out = []
    for r in table[1:]:
        row = {k: (r[i].strip() if i < len(r) else "") for k, i in where.items()}
        for k in COLUMNS:
            row.setdefault(k, "")
        if row["catalog"] or row["point"]:
            out.append(row)
    return out


def _block_for(library, catalog):
    want = catalog.strip().lower()
    blocks, _bad = library.blocks("symbol")
    for name, d in sorted(blocks.items()):
        if (d.catalog or "").strip().lower() == want or name.lower() in (want, want + " module"):
            return d
    return None


def _point_pins(defn):
    """{point number: pin name} of a module: the terminal whose text is IN n, OUT n, IN-n
    (an input before its return, RTN-n)."""
    texts = [e.text for e in defn.entities if isinstance(e, M.Text)]
    out = {}
    for t in texts:
        m = re.match(r"^(\S+)\s+(IN|OUT)[ -](\d+)$", t.strip())
        if m:
            out.setdefault(int(m.group(3)), m.group(1))
    return out


def plan(library, rows):
    """([(slot, catalog, block, [(pin, text)])], [problems]): the modules the list names, in
    the order it names them, each point's text ("I:2/0  PB101  START") for its pin."""
    mods, order, problems = {}, [], []
    for r in rows:
        key = (r["slot"], r["catalog"])
        if key not in mods:
            mods[key] = []
            order.append(key)
        mods[key].append(r)
    out = []
    for slot, cat in order:
        d = _block_for(library, cat)
        if d is None:
            problems.append("slot %s: no %s in the library" % (slot or "?", cat or "module"))
            continue
        pins = _point_pins(d)
        points = []
        for r in mods[(slot, cat)]:
            try:
                n = int(float(r["point"]))
            except ValueError:
                problems.append("slot %s: point %r isn't a number" % (slot or "?", r["point"]))
                continue
            if n not in pins:
                problems.append("slot %s: %s has no point %d" % (slot or "?", cat, n))
                continue
            text = "  ".join(t for t in (r["address"], r["tag"], r["desc"]) if t)
            if text:
                points.append((pins[n], text))
        out.append((slot, cat, d, points))
    return out, problems


def place(ed, project, modules, after=None):
    """Each module on a new sheet after the sheet after (or at the end): the module near the
    top of the room its frame leaves, its slot shown, each point's text beside its terminal,
    right-aligned, on layer PLC I/O. Returns the sheets made."""
    from .scalefit import room
    from .tags import retag_copies
    if LAYER not in project.layers:
        ed.layer(LAYER, None, M.Layer(LAYER).to_dict())
    at = project.sheets.index(after) + 1 if after in project.sheets else len(project.sheets)
    made = []
    for slot, cat, d, points in modules:
        s = project.make_sheet(("Slot %s - %s" % (slot, cat)) if slot else cat, "schematic")
        ed.add_sheet(s, at + len(made))
        k = s.k()
        area, _tb = room(project, s)
        # (its terminals down the left: the texts go to their left, so the module sits a
        # third of the way across, its first terminal an inch under the top)
        x = area[0] + (area[2] - area[0]) / 3.0
        y = area[3] - 1.0
        # (as Insert places a symbol: its own size, its tag paper-sized, on layer SYMBOLS)
        ins = M.Insert(d.name, (x * k, y * k), 0.0, 1.0, False,
                       {"SLOT": slot} if slot else {}, d,
                       project.settings.get("tag_height") * k, layer="SYMBOLS")
        ins = retag_copies(project, s, [ins])[0]
        ins = ed.add(s, ins)
        pins = dict(ins.pin_points())
        for pin, text in points:
            q = pins[pin]
            ed.add(s, M.Text((q[0] - 0.15, q[1] + 0.03), text, TEXT_H * k, 0.0, "right",
                             layer=LAYER))
        made.append(s)
    return made


def import_list(ed, project, library, path, after=None):
    """Read, plan and place an I/O list: (sheets made, problems)."""
    if not os.path.isfile(path):
        raise ValueError("%s isn't there" % path)
    modules, problems = plan(library, read_rows(path))
    return place(ed, project, modules, after), problems
