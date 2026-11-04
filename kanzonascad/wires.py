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
    edit changed itself (moved along with the symbol, say) are left as they are. Every end
    of a wire that moves is moved together (two symbols moved with a wire between them): a
    wire whose two ends move the same way just moves along, and one left with no length
    goes."""
    changed_by_user = {(sid, eid) for (sid, eid) in ed._seen}
    moves = {}                                  # (sheet id, wire id) -> (sheet, {end: point})
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
                        moves.setdefault((sheet.id, e.id), (sheet, {}))[1].setdefault(i, new)
    for (_sid, eid), (sheet, ends) in moves.items():
        cur = sheet.entities.get(eid)
        if cur is None:
            continue
        if len(ends) == 2:
            d0 = (ends[0][0] - cur.points[0][0], ends[0][1] - cur.points[0][1])
            d1 = (ends[-1][0] - cur.points[-1][0], ends[-1][1] - cur.points[-1][1])
            if abs(d0[0] - d1[0]) <= TOL and abs(d0[1] - d1[1]) <= TOL:
                ed.change(sheet, cur.moved(d0[0], d0[1]))
                continue
        for i, q in ends.items():
            if len(cur.points) < 2:
                break
            cur = cur.end_moved(i, q)
        if len(cur.points) < 2:
            ed.remove(sheet, eid)               # (both ends on one point: no wire left)
        else:
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


def _dot_at(sheet, p):
    """Does a junction dot belong at p: a wire end on the middle (or a corner) of another
    wire, or three or more wire ends with no pin there (on a pin, the pin is the
    connection)?"""
    ends, middle = 0, False
    for e in sheet.query_point(p, TOL):
        if not isinstance(e, Wire):
            continue
        n = _same(e.points[0], p) + _same(e.points[-1], p)
        if n:
            ends += n
        elif e.touches(p, TOL):
            middle = True
    if not ends:
        return False
    return middle or (ends >= 3 and not pins_on(sheet, p))


def _key(p):
    return (round(p[0], 6), round(p[1], 6))


def junctions(sheet):
    """Points where wires join and a dot belongs (see _dot_at), kept per sheet version. After
    an edit only the points near what it changed are looked at again (entities are values:
    a changed wire or symbol is a new object), so a big sheet isn't measured whole."""
    got = getattr(sheet, "_junctions", None)
    if got is not None and got[0] == sheet.version:
        return got[1]
    cur = {e.id: e for e in sheet.wires()}
    cur.update((e.id, e) for e in sheet.inserts())
    st = getattr(sheet, "_junction_state", None)
    if st is None:
        dots = set()
        for w in sheet.wires():
            for p in (w.points[0], w.points[-1]):
                k = _key(p)
                if k not in dots and _dot_at(sheet, p):
                    dots.add(k)
    else:
        old, dots = st
        def moved(a, b):
            # (only where a wire or a symbol's pins are matters: not its number or tag)
            if b is None or type(a) is not type(b):
                return True
            if isinstance(a, Wire):
                return a.points != b.points
            return a.pin_points() != b.pin_points()
        stale = [old[i] for i in old if cur.get(i) is not old[i] and moved(old[i], cur.get(i))]
        stale += [e for i, e in cur.items() if old.get(i) is not e and moved(e, old.get(i))]
        look = set()
        for e in stale:
            if isinstance(e, Wire):
                look.add(_key(e.points[0]))
                look.add(_key(e.points[-1]))
                x0, y0, x1, y1 = e.bbox()
                for o in sheet.query((x0 - TOL, y0 - TOL, x1 + TOL, y1 + TOL)):
                    if isinstance(o, Wire):
                        for q in (o.points[0], o.points[-1]):
                            if e.touches(q, TOL):
                                look.add(_key(q))
            else:
                look.update(_key(q) for _n, q in e.pin_points())
        for k in look:
            if _dot_at(sheet, k):
                dots.add(k)
            else:
                dots.discard(k)
    sheet._junction_state = (cur, dots)
    out = sorted(dots)
    sheet._junctions = (sheet.version, out)
    return out


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


LEAD = 0.125        # the angled lead of a second wire on a pin: 1/8 inch along, on paper


def _sign(v):
    return 1.0 if v >= 0 else -1.0


def lead(sheet, pin, toward, exclude=None):
    """A pin that already has a wire on it takes another (double landing) through a short
    angled lead, as drawn by hand: the new wire leaves the pin at 45 degrees, then runs
    straight beside the first. Returns (the lead's corner, the way out of the pin as a unit
    vector), or None when pin isn't a pin with a wire end on it. toward: where the new wire
    heads (the cursor), which picks the side; a third wire takes the other side, then
    further out."""
    if not pins_on(sheet, pin):
        return None
    dirs = []
    for e in _near(sheet, pin):
        if not isinstance(e, Wire) or e.id == exclude:
            continue
        for i in (0, -1):
            if _same(e.points[i], pin):
                q = e.points[1] if i == 0 else e.points[-2]
                dirs.append((q[0] - pin[0], q[1] - pin[1]))
    if not dirs:
        return None
    straight = [d for d in dirs if abs(d[0]) < 1e-9 or abs(d[1]) < 1e-9]
    d = straight[0] if straight else (toward[0] - pin[0], toward[1] - pin[1])
    out = (_sign(d[0]), 0.0) if abs(d[0]) >= abs(d[1]) else (0.0, _sign(d[1]))
    n = (-out[1], out[0])
    side = _sign((toward[0] - pin[0]) * n[0] + (toward[1] - pin[1]) * n[1])
    used = {}
    for dx, dy in dirs:
        s = dx * n[0] + dy * n[1]
        if abs(s) > 1e-9:
            used[_sign(s)] = used.get(_sign(s), 0) + 1
    if used.get(side, 0) > used.get(-side, 0):
        side = -side                    # (the side the cursor is on is taken: the other one)
    k = used.get(side, 0) + 1
    L = LEAD * sheet.k()
    corner = (pin[0] + out[0] * L * k + n[0] * side * L * k,
              pin[1] + out[1] * L * k + n[1] * side * L * k)
    return corner, out


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


# ---- Delete component: the wire it sat on is joined back up ---------------------------------
def _ahead(p, q, d):
    """Is q straight ahead of p in direction d (on the line, past p)?"""
    v = (q[0] - p[0], q[1] - p[1])
    L = (d[0] * d[0] + d[1] * d[1]) ** 0.5
    return abs(v[0] * d[1] - v[1] * d[0]) <= TOL * L and v[0] * d[0] + v[1] * d[1] > TOL


def heal(ed, sheet, ins):
    """After the symbol ins is taken away: join back up the wires that ran into it, pin to
    pin, where two of its pins face each other in line (straight across or up and down) with
    one wire each, leaving away from each other: a contact on a rung leaves the rung whole, a
    3-pole breaker its three wires. Returns how many wires were joined."""
    from .model import _tidy
    pins = [tuple(q) for _n, q in ins.pin_points()]
    ends = {}
    for q in pins:
        got = [(e, i) for e in _near(sheet, q) if isinstance(e, Wire)
               for i in (0, -1) if _same(e.points[i], q)]
        if len(got) == 1 and not pins_on(sheet, q):     # (one wire, no other symbol there)
            ends[q] = got[0]
    pairs = []
    for x, a in enumerate(pins):
        for b in pins[x + 1:]:
            if a not in ends or b not in ends:
                continue
            if abs(a[1] - b[1]) > TOL and abs(a[0] - b[0]) > TOL:
                continue                                # (not in line)
            pairs.append((abs(a[0] - b[0]) + abs(a[1] - b[1]), a, b))
    used, n = set(), 0
    for _d, a, b in sorted(pairs):
        if a in used or b in used:
            continue
        (wa, ia), (wb, ib) = ends[a], ends[b]
        wa, wb = sheet.entities.get(wa.id), sheet.entities.get(wb.id)
        if not isinstance(wa, Wire) or not isinstance(wb, Wire) or wa.id == wb.id:
            continue
        pa = list(wa.points) if ia == -1 else list(reversed(wa.points))   # ... to a
        pb = list(wb.points) if ib == 0 else list(reversed(wb.points))    # b to ...
        ab = (b[0] - a[0], b[1] - a[1])
        qa, qb = pa[-2], pb[1]
        # both wires must carry on the line through the two pins, away from each other (the
        # pins of one side of a 3-pole device line up too, but their wires run across it)
        if not (_ahead(a, qa, (-ab[0], -ab[1])) and _ahead(b, qb, ab)):
            continue
        merged = _tidy(pa + pb)
        if len(merged) < 2:
            continue
        if wb.num_lock and not wa.num_lock:
            wa, wb = wb, wa
            merged = merged[::-1]
        ed.remove(sheet, wb.id)
        ed.change(sheet, wa.copy(points=merged))
        used.update((a, b))
        n += 1
    return n
