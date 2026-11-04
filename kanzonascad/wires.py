"""How wires connect, worked out from the drawing (never stored, so it can't go stale). No Qt.

- A wire end connects to whatever sits at that point: a symbol pin, another wire's end, or
  the middle of another wire (a T, drawn with a dot).
- Moving a symbol drags the wire ends that sat on its pins (follow_pins, run at the end of
  every edit that moved a symbol), keeping the wires straight across / up and down.
- Placing a symbol on a wire cuts the wire between the symbol's pins (break_under).
"""

from .model import Wire, Insert
from .trim import _poly_cum, _poly_param, _poly_piece

TOL = 1e-6


def _near(sheet, p, tol=TOL):
    return sheet.query((p[0] - tol, p[1] - tol, p[0] + tol, p[1] + tol))


def _same(a, b, tol=TOL):
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


def follow_pins(ed):
    """Stretch the wires whose ends sat on the pins of symbols this edit moved. Wires the
    edit changed itself (moved along with the symbol, say) are left as they are."""
    changed_by_user = {(sid, eid) for (sid, eid) in ed._seen}
    for sheet, old_pins, new_pins in ed.pin_moves:
        for name, old in old_pins.items():
            new = new_pins.get(name)
            if new is None or _same(old, new):
                continue
            for e in _near(sheet, old):
                if not isinstance(e, Wire) or (sheet.id, e.id) in changed_by_user:
                    continue
                cur = sheet.entities.get(e.id)
                if cur is None:
                    continue
                for i in (0, -1):
                    if _same(cur.points[i], old):
                        cur = cur.end_moved(i, new)
                ed.change(sheet, cur)


def pins_on(sheet, p, tol=TOL):
    """Symbols with a pin at p: [(insert, pin name)]."""
    out = []
    for e in _near(sheet, p, tol):
        if isinstance(e, Insert):
            for name, q in e.pin_points():
                if _same(q, p, tol):
                    out.append((e, name))
    return out


def connects_at(sheet, p, exclude=None, tol=TOL):
    """Is there something a wire end at p attaches to: a pin, or another wire (its end or its
    middle)? exclude: a wire id to ignore (the wire being drawn)."""
    if pins_on(sheet, p, tol):
        return True
    for e in _near(sheet, p, tol):
        if isinstance(e, Wire) and e.id != exclude and e.distance(p) <= tol:
            return True
    return False


def junctions(sheet):
    """Points where wires join and a dot belongs: a wire end on the middle of another wire,
    or three or more wire ends at one point."""
    wires = [e for e in sheet.entities.values() if isinstance(e, Wire)]
    dots = []
    ends = {}
    for w in wires:
        for p in (w.points[0], w.points[-1]):
            key = (round(p[0], 6), round(p[1], 6))
            ends[key] = ends.get(key, 0) + 1
    for key, n in ends.items():
        if n >= 3:
            dots.append(key)
    for w in wires:
        for p in (w.points[0], w.points[-1]):
            for other in _near(sheet, p):
                if other is w or not isinstance(other, Wire):
                    continue
                if other.distance(p) <= TOL and not any(_same(p, q) for q in
                                                        (other.points[0], other.points[-1])):
                    key = (round(p[0], 6), round(p[1], 6))
                    if key not in dots:
                        dots.append(key)
    return dots


def break_under(ed, sheet, ins):
    """Cut the wires the symbol was placed on, between its pins (as AutoCAD Electrical does):
    a wire with two or more of the pins on it loses the part between the outermost two."""
    pins = [q for _n, q in ins.pin_points()]
    if len(pins) < 2:
        return 0
    cut = 0
    bb = ins.bbox()
    for w in sheet.query(bb):
        if not isinstance(w, Wire):
            continue
        pts, cum = _poly_cum(w.points, False)
        on = [_poly_param(pts, cum, q) for q in pins if w.distance(q) <= TOL]
        if len(on) < 2:
            continue
        lo, hi = min(on), max(on)
        total = cum[-1]
        # (both pieces keep its number to start: numbering gives the second its own)
        keep = dict(layer=w.layer, color=w.color, num=w.num, num_lock=w.num_lock)
        ed.remove(sheet, w.id)
        if lo > TOL:
            ed.add(sheet, Wire(_poly_piece(pts, cum, 0.0, lo), **keep))
        if total - hi > TOL:
            ed.add(sheet, Wire(_poly_piece(pts, cum, hi, total), **keep))
        cut += 1
    return cut


def route(a, b, horizontal_first=True):
    """The corner points of a straight-across / up-and-down path from a to b."""
    if abs(a[0] - b[0]) < 1e-9 or abs(a[1] - b[1]) < 1e-9:
        return [b]
    corner = (b[0], a[1]) if horizontal_first else (a[0], b[1])
    return [corner, b]



# ---- trim, delete and clean up (Trim wire, Delete wire, Clean up wires) ---------------------
def _hits(sheet, w):
    """Distances along w where it meets something: another wire (crossing it, ending on it,
    or it ending on the other), or a symbol pin on it. (pts, cum, sorted distances)"""
    from .trim import entity_intersections
    pts, cum = _poly_cum(w.points, False)
    x0, y0, x1, y1 = w.bbox()
    out = set()
    for o in sheet.query((x0 - TOL, y0 - TOL, x1 + TOL, y1 + TOL)):
        if o.id == w.id:
            continue
        if isinstance(o, Wire):
            qs = entity_intersections(w, o)
            qs += [q for q in (o.points[0], o.points[-1]) if w.distance(q) <= TOL]
        elif isinstance(o, Insert):
            qs = [q for _n, q in o.pin_points() if w.distance(q) <= TOL]
        else:
            continue
        for q in qs:
            out.add(round(_poly_param(pts, cum, q), 9))
    return pts, cum, sorted(out)


def trim_wire(sheet, w, click):
    """Trim wire at click: the part of w between the nearest points on either side where it
    meets another wire or a pin goes (to the wire's end when nothing is met on that side).
    Returns (the pieces left, as new wires keeping its layer, color and number; the points
    where the cut part met the rest)."""
    pts, cum, cuts = _hits(sheet, w)
    total = cum[-1]
    s0 = _poly_param(pts, cum, click)
    lo = max([s for s in cuts if TOL < s < s0 - TOL], default=0.0)
    hi = min([s for s in cuts if s0 + TOL < s < total - TOL], default=total)
    keep = dict(layer=w.layer, color=w.color, num=w.num, num_lock=w.num_lock)
    out, ends = [], []
    if lo > TOL:
        piece = _poly_piece(pts, cum, 0.0, lo)
        out.append(Wire(piece, **keep))
        ends.append(tuple(piece[-1]))
    else:
        ends.append(tuple(pts[0]))
    if total - hi > TOL:
        piece = _poly_piece(pts, cum, hi, total)
        out.append(Wire(piece, **keep))
        ends.append(tuple(piece[0]))
    else:
        ends.append(tuple(pts[-1]))
    return out, ends


def covered(w, o):
    """Does wire w lie entirely on wire o (drawn over it)?"""
    for a, b in zip(w.points, w.points[1:]):
        for q in (a, b, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)):
            if o.distance(q) > TOL:
                return False
    return True


def _drop_if_covered(ed, sheet, w):
    """Remove w when another wire already runs everywhere it does. True if removed."""
    x0, y0, x1, y1 = w.bbox()
    for o in sheet.query((x0 - TOL, y0 - TOL, x1 + TOL, y1 + TOL)):
        if o.id == w.id or not isinstance(o, Wire):
            continue
        # (two identical wires: the one with its own number, else the older, stays)
        if covered(w, o) and (not covered(o, w) or (w.num_lock, -_order(w.id)) <=
                              (o.num_lock, -_order(o.id))):
            ed.remove(sheet, w.id)
            return True
    return False


def _order(eid):
    return eid if isinstance(eid, (int, float)) else 0


def join_at(ed, sheet, points):
    """Join the two wires meeting end to end at each point, into one, where nothing else
    meets them there (no pin, no third wire): a wire carried on from another's end is one
    wire. Returns how many joins."""
    from .model import _tidy
    n = 0
    for p in points:
        near = _near(sheet, p)
        ends, through = [], False
        for e in near:
            if not isinstance(e, Wire):
                continue
            at = [i for i in (0, -1) if _same(e.points[i], p)]
            if at:
                ends.extend((e, i) for i in at)
            elif e.distance(p) <= TOL:
                through = True
        if len(ends) != 2 or through or ends[0][0].id == ends[1][0].id or pins_on(sheet, p):
            continue
        (a, ia), (b, ib) = sorted(ends, key=lambda t: (not t[0].num_lock, _order(t[0].id)))
        pa = list(a.points) if ia == -1 else list(reversed(a.points))
        pb = list(b.points) if ib == 0 else list(reversed(b.points))
        merged = _tidy(pa + pb[1:])
        if len(merged) < 2:
            continue
        ed.remove(sheet, b.id)
        ed.change(sheet, a.copy(points=merged))
        n += 1
    return n


def _ends(ws):
    seen, out = set(), []
    for w in ws:
        for p in (w.points[0], w.points[-1]):
            k = (round(p[0], 9), round(p[1], 9))
            if k not in seen:
                seen.add(k)
                out.append(tuple(p))
    return out


def tidy_new(ed, sheet, w):
    """Cleanup as a wire is drawn: a wire drawn where one already runs isn't added twice, and
    one carried on from another wire's end joins it. Returns "duplicate", "joined" or None."""
    if _drop_if_covered(ed, sheet, w):
        return "duplicate"
    return "joined" if join_at(ed, sheet, _ends([w])) else None


def cleanup(ed, sheet, ws=None):
    """Clean up wires (the given ones, or every wire on the sheet): wires of no length go,
    repeated and in-line points go, a wire drawn over another goes, and wires meeting end to
    end with nothing else there become one. Returns the counts, with the wire ends left
    connected to nothing ("loose")."""
    from .model import _tidy
    ws = list(sheet.wires() if ws is None else ws)
    got = {"empty": 0, "tidied": 0, "duplicates": 0, "joined": 0, "loose": 0}
    for w in ws:
        cur = sheet.entities.get(w.id)
        if not isinstance(cur, Wire):
            continue
        pts = _tidy(cur.points)
        if len(pts) < 2:
            ed.remove(sheet, cur.id)
            got["empty"] += 1
            continue
        if [list(q) for q in cur.points] != pts:
            ed.change(sheet, cur.copy(points=pts))
            got["tidied"] += 1
    for w in ws:
        cur = sheet.entities.get(w.id)
        if isinstance(cur, Wire) and _drop_if_covered(ed, sheet, cur):
            got["duplicates"] += 1
    left = [sheet.entities[w.id] for w in ws if isinstance(sheet.entities.get(w.id), Wire)]
    got["joined"] = join_at(ed, sheet, _ends(left))
    for w in sheet.wires() if ws is None else [sheet.entities.get(w.id) for w in ws]:
        if not isinstance(w, Wire):
            continue
        for p in (w.points[0], w.points[-1]):
            if not connects_at(sheet, p, exclude=w.id):
                got["loose"] += 1
    return got
