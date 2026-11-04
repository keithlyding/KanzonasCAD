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

