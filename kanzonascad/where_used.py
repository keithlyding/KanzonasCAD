"""Trace (no Qt): every place in the project a device, a wire or a PLC point appears, as
Studio 5000's Cross Reference tab lists a tag's uses (the owner, Nov 2026: "I click on a tag
and then use control E to go to a cross-references tab which shows all the places that tag is
used and shows whether it's an output or input, and some other metadata").

- A device (a symbol with a tag): itself, its contacts (NO, NC), terminals, outlets and
  continued pieces, its footprints and dashed boxes, any other symbol showing its tag, and a
  PLC module's points that have a wire on them.
- A wire: every wire of its number on every sheet (its group, joined by off-sheet arrows, and
  any other wire given the same number), the arrows on it, and the pins, terminals and PLC
  points it lands on.
- A PLC point (a PLC input or output symbol, or one point of a module): the point, its
  module, and all of its wire.

What is found comes from an index kept with each sheet (index_steps), made again only for a
sheet that changed since and only when someone asks; a lookup (Trace) goes in small steps, so
the window can work them in between its other work (the owner, Nov 2026: "make sure that the
loading of the cross-references doesn't prevent any interaction with the sheet itself"). The
name the window gives it is NAME, kept here only."""

import math
from collections import namedtuple

from . import tags
from . import wirenums
from .model import DashBox, Insert, Text, Wire
from .xrefs import MARK

NAME = "Trace"          # (the owner's name for it, Nov 2026: the one place it is set)

TOL = wirenums.TOL

# one place: the sheet's id, the ids selected there when it is gone to, the point to center
# on and the box to show, and the columns: where (6-D1, or the rung), sheet, role, name,
# description
Row = namedtuple("Row", "sheet_id ids point box where sheet role name desc")


class SheetIndex:
    """One sheet's part of the index: its devices and children by hidden id, its symbols by
    tag, its off-sheet connectors by name and its wires by number."""

    def __init__(self):
        self.by_dev = {}        # DEV -> [entity]: the device, its children, footprints, boxes
        self.by_tag = {}        # TAG (upper case) -> [entity]
        self.links = {}         # off-sheet connector name -> [connector]
        self.by_num = {}        # wire number -> [wire]

    def add(self, e):
        dev = e.attrs.get("DEV") if isinstance(e, Insert) and tags.is_device(e) else None
        if dev:
            self.by_dev.setdefault(dev, []).append(e)
        par = e.attrs.get("PARENT")
        if par and par != dev:
            self.by_dev.setdefault(par, []).append(e)
        tag = (e.attrs.get("TAG", "") or "").strip().upper()
        if tag:
            self.by_tag.setdefault(tag, []).append(e)


SLICE = 2000            # objects looked at between two looks at the clock (index_steps)


def index_steps(sheet):
    """A generator making the sheet's SheetIndex in pieces (it yields every SLICE objects, for
    the caller to give the event loop its turn) and returning it; kept with the sheet until
    the sheet changes, so only the sheets an edit touched are looked at again. A change to the
    sheet between two pieces starts it again."""
    while True:
        got = getattr(sheet, "_trace_index", None)
        if got is not None and got[0] == sheet.version:
            return got[1]
        ver, idx = sheet.version, SheetIndex()
        n = 0
        for e in list(sheet.inserts()):
            d = e.defn
            if d is not None and d.wiring == "link":
                name = (e.attrs.get("TAG", "") or "").strip().upper()
                if name:
                    idx.links.setdefault(name, []).append(e)
            elif d is not None:
                idx.add(e)
            n += 1
            if n % SLICE == 0:
                yield
                if sheet.version != ver:
                    break
        else:
            for w in list(sheet.wires()):
                if w.num:
                    idx.by_num.setdefault(w.num, []).append(w)
                n += 1
                if n % SLICE == 0:
                    yield
                    if sheet.version != ver:
                        break
            else:
                for e in list(sheet.entities.values()):
                    if isinstance(e, DashBox) and tags.is_linked_box(e):
                        idx.add(e)
                    n += 1
                    if n % SLICE == 0:
                        yield
                        if sheet.version != ver:
                            break
                else:
                    sheet._trace_index = (ver, idx)
                    return idx


class Index:
    """The sheets' indexes read as one: by_dev.get(DEV), by_tag.get(TAG), links.get(name) and
    by_num.get(number) give [(sheet, object)] in sheet order."""

    def __init__(self, parts):
        self.parts = parts                      # [(sheet, SheetIndex)]
        self.by_dev = _Across(parts, "by_dev")
        self.by_tag = _Across(parts, "by_tag")
        self.links = _Across(parts, "links")
        self.by_num = _Across(parts, "by_num")

    def device(self, dev):
        """(sheet, device) of a hidden id, or None."""
        for s, e in self.by_dev.get(dev, ()):
            if e.attrs.get("DEV") == dev and isinstance(e, Insert) and tags.is_device(e):
                return s, e
        return None


class _Across:
    def __init__(self, parts, attr):
        self.parts, self.attr = parts, attr

    def get(self, key, default=()):
        out = [(s, e) for s, ix in self.parts for e in getattr(ix, self.attr).get(key, ())]
        return out or default


# ---- what was picked --------------------------------------------------------------------------
def subject_of(project, sheet, ent, at=None, tol=0.0):
    """What a picked object stands for, as a key Trace takes, or None (a line, a text...):
    ("device", DEV, tag), ("tag", TAG), ("wire", number, sheet id, wire id) or ("point",
    sheet id, symbol id, pin). at: the point the cursor is on (an object under the cursor):
    a PLC module's point within tol of it stands for that point."""
    if isinstance(ent, Wire):
        return ("wire", ent.num or "", sheet.id, ent.id)
    if not isinstance(ent, (Insert, DashBox)):
        return None
    d = getattr(ent, "defn", None)
    if isinstance(ent, Insert):
        if d is None:
            return None
        if d.wiring == "link":
            w = _wire_on(sheet, ent)
            return ("wire", w.num or "", sheet.id, w.id) if w is not None else None
        if wirenums.is_io_point_symbol(d) and d.pins:
            return ("point", sheet.id, ent.id, d.pins[0]["name"])
        if at is not None:
            pts = wirenums.io_points(d)
            for name, q in ent.pin_points():
                if name in pts and math.hypot(q[0] - at[0], q[1] - at[1]) <= tol:
                    return ("point", sheet.id, ent.id, name)
        if tags.is_device(ent) and ent.attrs.get("DEV"):
            return ("device", ent.attrs["DEV"], ent.attrs.get("TAG", ""))
    par = ent.attrs.get("PARENT")
    if par:
        return ("device", par, ent.attrs.get("TAG", ""))
    tag = (ent.attrs.get("TAG", "") or "").strip()
    return ("tag", tag.upper()) if tag else None


def _wire_on(sheet, ins):
    """The wire on one of a symbol's pins, or None."""
    for _n, q in ins.pin_points():
        for w in sheet.query_point(q, TOL):
            if isinstance(w, Wire) and w.touches(q, TOL):
                return w
    return None


# ---- the places -------------------------------------------------------------------------------
BATCH = 50              # rows made between two looks at the clock


class Trace:
    """Looking a subject (subject_of) up, a small step at a time (step()): first the sheets'
    indexes brought up to date, then the rows. rows: those found so far, then all of them in
    sheet order and, on a sheet, across then down, the subject's own object first on its
    sheet; header: "Tracing..." until done, then what is listed and how many places
    ("CR101 - 5 places"), or that it is gone (no rows)."""

    def __init__(self, project, subject):
        self.project, self.subject = project, subject
        self.revision = project.revision
        self.rows = []
        self.header = "Tracing..."
        self.done = False
        self._gen = self._run()

    def step(self):
        """One small step; False once done."""
        if self.done:
            return False
        try:
            next(self._gen)
            return True
        except StopIteration:
            self.done = True
            return False

    def _run(self):
        project, sub = self.project, self.subject
        sheets = list(project.sheets)
        parts = []
        for i, s in enumerate(sheets):
            self.header = "Tracing... (sheet %d of %d)" % (i + 1, len(sheets))
            ix = yield from index_steps(s)
            parts.append((s, ix))
        idx = Index(parts)
        self.header = "Tracing..."
        kind, out = sub[0], self.rows
        if kind == "device":
            title, rows = yield from _device(project, idx, out, sub[1], sub[2])
        elif kind == "tag":
            title, rows = yield from _tagged(project, idx, out, sub[1])
        elif kind == "wire":
            title, rows = yield from _wire(project, idx, out, sub[1], sub[2], sub[3])
        else:
            title, rows = yield from _point(project, idx, out, sub[1], sub[2], sub[3])
        self.rows = rows
        n = len(rows)
        self.header = ("%s \u2014 %d place%s" % (title, n, "" if n == 1 else "s") if rows
                       else "%s: no longer in the project" % title)


def _found(out, row):
    """A row found: kept in out; True every BATCH rows (time to yield)."""
    out.append(row)
    return len(out) % BATCH == 0


def _sheet_text(project, s):
    n = project.sheet_number(s)
    return ("%s  %s" % (n, s.title)).strip() if s.title else n


def _row(project, s, ids, point, box, role, name, desc):
    where = project.zone_text(s, point[0], point[1]) or project.sheet_number(s)
    return Row(s.id, tuple(ids), (point[0], point[1]), box, where, _sheet_text(project, s),
               role, name, desc)


def _point_of(e):
    return e.pos if isinstance(e, Insert) else e.points[0]


def _sorted(project, rows, first=()):
    """Rows in sheet order, then across and down; rows whose ids are in first lead on their
    sheet."""
    pos = {s.id: i for i, s in enumerate(project.sheets)}
    keys = {}

    def key(r):
        k = keys.get(r.sheet_id)
        if k is None:
            k = keys[r.sheet_id] = tags.order_key(project.sheet_by_id(r.sheet_id), "across")
        return (pos.get(r.sheet_id, 0), 0 if set(r.ids) & set(first) else 1, k(r.point),
                r.name)
    seen, out = set(), []
    for r in sorted(rows, key=key):
        sig = (r.sheet_id, r.ids, r.name, r.role)
        if sig not in seen:
            seen.add(sig)
            out.append(r)
    return out


def role(e):
    """What a symbol is, in a word or two: Coil, NO contact, Terminal, Footprint..."""
    if isinstance(e, DashBox):
        return "Dashed box"
    d = e.defn
    if d is None:
        return "Block"
    if d.kind == "footprint":
        return "Footprint"
    if d.role == "child":
        if wirenums.is_io_point_symbol(d):
            return "PLC output" if any(p["name"] == "OUT" for p in d.pins) else "PLC input"
        attr = tags.number_attr(e)
        if attr == "TERM":
            return "Terminal"
        if attr == "OUTLET":
            return "Outlet"
        if d.contact:
            mark = MARK.get(d.contact, "")
            return "%s contact%s" % (mark, ", timed" if d.contact[2:] else "")
        if d.prefix == "PLC":
            return "PLC module, continued"
        return "Contact"
    if d.prefix == "PLC":
        return "PLC module" if wirenums.io_points(d) else "PLC card"
    if d.prefix == "TB":
        return "Terminal strip"
    if "coil" in d.name.lower():
        return "Coil"
    return "Device"


def _desc(e, device=None):
    """A symbol's description: its own (DESC), its device's, else its block's name."""
    for a in (e.attrs, device.attrs if device is not None else {}):
        got = (a.get("DESC", "") or "").strip()
        if got:
            return got
    return e.block if isinstance(e, Insert) else (e.text or "")


def _name(e, tag):
    attr = tags.number_attr(e) if isinstance(e, Insert) else None
    num = (e.attrs.get(attr, "") or "").strip() if attr else ""
    return "%s-%s" % (tag, num) if num else tag


def _symbol_row(project, s, e, device=None, note=""):
    tag = (e.attrs.get("TAG", "") or "").strip() or (
        e.block if isinstance(e, Insert) else "")
    desc = _desc(e, device)
    if note:
        desc = "%s (%s)" % (desc, note) if desc else note
    return _row(project, s, [e.id], _point_of(e), e.bbox(), role(e), _name(e, tag), desc)


def _device(project, idx, out, dev, tag):
    got = idx.device(dev)
    dev_ent = got[1] if got else None
    tag = (dev_ent.attrs.get("TAG", "") if dev_ent is not None else tag) or ""
    title = tag or (dev_ent.block if dev_ent is not None else "Device")
    rows, linked = out, set()
    for s, e in idx.by_dev.get(dev, ()):
        linked.add((s.id, e.id))
        if isinstance(e, Insert) and wirenums.is_io_point_symbol(e.defn) and e.defn.pins:
            row = _point_row(project, s, e, e.defn.pins[0]["name"], dev_ent)
        else:
            row = _symbol_row(project, s, e, dev_ent)
            if isinstance(e, Insert) and e.defn is not None and e.defn.prefix == "PLC":
                rows += _module_points(project, s, e, dev_ent)
        if _found(rows, row):
            yield
    if dev_ent is not None or tag:
        for s, e in idx.by_tag.get(tag.strip().upper(), ()):
            if (s.id, e.id) not in linked:
                if _found(rows, _symbol_row(project, s, e, dev_ent, "not linked")):
                    yield
    return title, _sorted(project, rows, [dev_ent.id] if dev_ent is not None else ())


def _tagged(project, idx, out, tag):
    for s, e in idx.by_tag.get(tag, ()):
        if _found(out, _symbol_row(project, s, e)):
            yield
    return tag, _sorted(project, out)


# ---- PLC points -------------------------------------------------------------------------------
def _io_text(sheet, q):
    """The I/O list's text beside a module's terminal (Import I/O list), or ""."""
    from .io_list import LAYER
    k = sheet.k()
    best = None
    for t in sheet.query((q[0] - 0.6 * k, q[1] - 0.12 * k, q[0] + 0.6 * k, q[1] + 0.12 * k)):
        if isinstance(t, Text) and t.layer == LAYER and abs(t.pos[1] - q[1]) <= 0.12 * k:
            d = abs(t.pos[0] - q[0]) + abs(t.pos[1] - q[1])
            if best is None or d < best[0]:
                best = (d, t.text.strip())
    return best[1] if best else ""


def _point_info(sheet, ins, pin, module):
    """(role, address, I/O text) of a PLC point: a module's terminal pin, or a PLC input or
    output symbol (module: the device it belongs to, for a continued piece's addresses)."""
    d = ins.defn
    if wirenums.is_io_point_symbol(d):
        return role(ins), (ins.attrs.get("ADDR", "") or "").strip(), \
            (ins.attrs.get("DESC", "") or "").strip()
    kind, n = wirenums.io_points(d)[pin]
    addr = wirenums.io_address(kind, n, ins.attrs,
                               module.attrs if module is not None and module is not ins
                               else None)
    q = dict(ins.pin_points())[pin]
    return ("PLC input" if kind == "I" else "PLC output"), addr, _io_text(sheet, q)


def _wires_at(sheet, q):
    return [w for w in sheet.query_point(q, TOL) if isinstance(w, Wire) and w.touches(q, TOL)]


def _point_row(project, s, ins, pin, module, nums=None):
    rl, addr, text = _point_info(s, ins, pin, module)
    q = dict(ins.pin_points())[pin]
    tag = (ins.attrs.get("TAG", "") or "").strip() or ins.block
    if nums is None:
        nums = sorted({w.num for w in _wires_at(s, q) if w.num})
    parts = [text or addr]
    if text and addr and addr not in text:
        parts.insert(0, addr)
    if nums:
        parts.append("wire " + ", ".join(nums))
    name = tag if wirenums.is_io_point_symbol(ins.defn) else "%s pin %s" % (tag, pin)
    return _row(project, s, [ins.id], q, (q[0], q[1], q[0], q[1]), rl, name,
                "  ".join(p for p in parts if p))


def _module_points(project, s, ins, module):
    """A PLC module's (or a continued piece's) points with a wire on them."""
    pts = wirenums.io_points(ins.defn)
    out = []
    for name, q in ins.pin_points():
        if name in pts:
            ws = _wires_at(s, q)
            if ws:
                out.append(_point_row(project, s, ins, name, module,
                                      sorted({w.num for w in ws if w.num})))
    return out


def _point(project, idx, out, sid, iid, pin):
    s = project.sheet_by_id(sid)
    ins = s.entities.get(iid) if s is not None else None
    if not isinstance(ins, Insert) or ins.defn is None or \
            pin not in {n for n, _q in ins.pin_points()}:
        return "PLC point", []
    par = ins.attrs.get("PARENT")
    module = idx.device(par)[1] if par and idx.device(par) else ins
    rl, addr, _t = _point_info(s, ins, pin, module)
    tag = (ins.attrs.get("TAG", "") or "").strip()
    title = "%s %s" % (rl, addr or ("%s pin %s" % (tag, pin)))
    out.append(_point_row(project, s, ins, pin, module))
    if par and idx.device(par) is not None:
        ms, m = idx.device(par)
        out.append(_symbol_row(project, ms, m))
    q = dict(ins.pin_points())[pin]
    for w in _wires_at(s, q)[:1]:
        _t, got = yield from _wire(project, idx, [], w.num or "", s.id, w.id)
        out += [r for r in got
                if not (r.sheet_id == s.id and r.ids == (ins.id,) and r.role == rl)]
    return title, _sorted(project, out, [ins.id])


# ---- wires ------------------------------------------------------------------------------------
def _wire(project, idx, out, num, sid, wid):
    """Every wire of the number on every sheet; a wire with no number (wire numbers turned
    off), the wires joined to it (its group, carried on by arrows: wirenums.groups)."""
    if num:
        found = idx.by_num.get(num, ())
    else:
        found = []
        # (each sheet's part worked out first, one sheet a step, as it is kept until the sheet
        # changes: the whole project's groups are then put together from them without
        # holding up the drawing; the owner, 0.23)
        mode = wirenums.tap_mode(project)
        for s in project.sheets:
            wirenums._summary(s, wirenums.wire_order(project, s), mode)
            yield
        for nodes in wirenums.groups(project)[0].values():
            if any(s.id == sid and w.id == wid for s, w in nodes):
                found = nodes
                break
    title = "Wire %s" % num if num else "Wire (no number)"
    split = wirenums.tap_mode(project) != "same"
    by_sheet = {}
    for s, w in found:
        by_sheet.setdefault(s.id, (s, []))[1].append(w)
    for s, ws in by_sheet.values():
        roots = wirenums._sheet_groups(s, split)
        pieces = {}
        for w in ws:
            pieces.setdefault(roots.get(w.id, w.id), []).append(w)
        for piece in pieces.values():
            n = len(out)
            out += _piece_rows(project, idx, s, piece)
            if len(out) // BATCH != n // BATCH:
                yield
    return title, _sorted(project, out, {w.id for _s, w in found})


def _longest_middle(ws):
    best = None
    for w in ws:
        for a, b in zip(w.points, w.points[1:]):
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if best is None or L > best[0]:
                best = (L, ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0))
    return best[1]


def _piece_rows(project, idx, s, ws):
    """One joined run of a wire on a sheet: the wire, and what is on it (arrows, pins)."""
    box = None
    for w in ws:
        bb = w.bbox()
        box = bb if box is None else (min(box[0], bb[0]), min(box[1], bb[1]),
                                      max(box[2], bb[2]), max(box[3], bb[3]))
    nums = sorted({w.num for w in ws if w.num})
    lay = ws[0].layer
    awg = next((w.awg for w in ws if w.awg), "")
    rows = [_row(project, s, [w.id for w in ws], _longest_middle(ws), box, "Wire",
                 ", ".join(nums) or "(no number)",
                 ("%s, %s AWG" % (lay, awg)) if awg else lay)]
    seen = set()
    for w in ws:
        for e in s.query(w.bbox()):
            if not isinstance(e, Insert) or e.defn is None or not e.defn.pins or \
                    e.defn.kind != "symbol":
                continue
            for pin, q in e.pin_points():
                if (e.id, pin) in seen or not w.touches(q, TOL):
                    continue
                seen.add((e.id, pin))
                rows.append(_landing_row(project, idx, s, e, pin, q))
    return rows


def _landing_row(project, idx, s, e, pin, q):
    d = e.defn
    tag = (e.attrs.get("TAG", "") or "").strip()
    box = (q[0], q[1], q[0], q[1])
    if d.wiring == "link":
        name = tag.upper()
        others = [project.zone_text(os_, oc.pos[0], oc.pos[1]) or project.sheet_number(os_)
                  for os_, oc in idx.links.get(name, ()) if oc is not e]
        rl = e.block if e.block in wirenums.ARROWS else "Off-sheet connector"
        return _row(project, s, [e.id], q, box, rl, name,
                    ("to " + ", ".join(others)) if others else "no other end yet")
    par = e.attrs.get("PARENT")
    dev = idx.device(par) if par else None
    module = dev[1] if dev is not None else e
    if wirenums.is_io_point_symbol(d) or pin in wirenums.io_points(d):
        return _point_row(project, s, e, pin, module)
    if tags.number_attr(e) == "TERM":
        from .pull import landing_name
        return _row(project, s, [e.id], q, box, "Terminal", landing_name(e, pin),
                    _desc(e, dev[1] if dev else None))
    return _row(project, s, [e.id], q, box, role(e), "%s pin %s" % (tag or e.block, pin),
                _desc(e, dev[1] if dev else None))
