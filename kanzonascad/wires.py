"""How wires connect, worked out from the drawing (never stored, so it can't go stale). No Qt.

- A wire end connects to whatever sits at that point: a symbol pin, another wire's end, or
  the middle of another wire (a T, drawn with a dot).
- Moving a symbol drags the wire ends that sat on its pins (follow_pins, run at the end of
  every edit that moved a symbol), keeping the wires straight across / up and down.
- Placing a symbol on a wire cuts the wire between the symbol's pins (break_under).
"""

import math

from . import geometry as G
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


def _ways_out(e, p):
    """The directions (rounded unit vectors) wire e leaves p by: one from an end, two from a
    point along it, none where it doesn't pass."""
    out = set()
    pts = e.points
    for a, b in zip(pts, pts[1:]):
        L = G.dist(a, b)
        if L <= TOL or G.dist_to_segment(p, a, b) > TOL:
            continue
        for q, r in ((a, b), (b, a)):
            if G.dist(p, r) > TOL:              # (a way out toward r, unless p is r)
                out.add((round((r[0] - q[0]) / L, 6), round((r[1] - q[1]) / L, 6)))
    return out


def _dot_at(sheet, p):
    """Does a junction dot belong at p: a wire end where wires go off three or more ways (an
    end on another wire's middle or corner: a tap; three or more ends), with no pin there
    when it is only wire ends (on a pin, the pin is the connection)? Two ways is no tap (the
    owner, 0.17.5: "Connection markers on wires should only show if another wire taps off of
    it"): two wires end to end, or the corner where a wire doubles back over itself, a wire
    end meeting it carried straight on."""
    ends, middle, ways = 0, False, set()
    for e in sheet.query_point(p, TOL):
        if not isinstance(e, Wire):
            continue
        n = _same(e.points[0], p) + _same(e.points[-1], p)
        if n:
            ends += n
        elif e.touches(p, TOL):
            middle = True
        ways |= _ways_out(e, p)
    if not ends or len(ways) < 3:
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
    hidden = set(getattr(sheet, "no_dots", ()) or ())
    out = sorted(k for k in dots if k not in hidden)    # (Delete dot: the wires still join)
    sheet._junctions = (sheet.version, out)
    return out



def break_under(ed, sheet, ins, skip=()):
    """Cut the wires the symbol was placed on, between its pins (as AutoCAD Electrical does):
    a wire with two or more of the pins on it loses the part between the outermost two. skip:
    ids of wires left alone (a moved symbol's own wires, which follow it)."""
    pins = [q for _n, q in ins.pin_points()]
    if len(pins) < 2:
        return 0
    cut = 0
    bb = ins.bbox()
    for w in sheet.query(bb):
        if not isinstance(w, Wire) or w.id in skip:
            continue
        pts, cum = _poly_cum(w.points, False)
        on = [_poly_param(pts, cum, q) for q in pins if w.distance(q) <= TOL]
        if len(on) < 2:
            continue
        lo, hi = min(on), max(on)
        total = cum[-1]
        # (both pieces keep its number to start: numbering gives the second its own)
        keep = dict(layer=w.layer, color=w.color, num=w.num, num_lock=w.num_lock,
                    own_num=w.own_num, same_num=w.same_num, awg=w.awg,
                    show_color=w.show_color, pin_tap=w.pin_tap)
        ed.remove(sheet, w.id)
        if lo > TOL:
            ed.add(sheet, Wire(_poly_piece(pts, cum, 0.0, lo),
                               labels=_labels_between(w, 0.0, lo), **keep))
        if total - hi > TOL:
            ed.add(sheet, Wire(_poly_piece(pts, cum, hi, total),
                               labels=_labels_between(w, hi, total), **keep))
        cut += 1
    return cut


LEAD = 0.25         # the angled lead of a second wire on a pin: 1/4 inch along, on paper
                    # (the owner, 0.19.9: "Let's do 1/4 inch and see how it does"; was 1/8)


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
    L = LEAD * sheet.k()

    def at(sd, length):
        m = used.get(sd, 0) + 1
        return (pin[0] + out[0] * length * m + n[0] * sd * length * m,
                pin[1] + out[1] * length * m + n[1] * sd * length * m)

    # (the lead's corner, and the diagonal to it, clear of every other wire and pin: on pins
    # 1/4 inch apart a 1/4 inch lead's corner would sit on the next pin's wire and tie the two
    # together; the other side then, else a shorter lead)
    for length in (L, L / 2.0, L / 4.0):
        for sd in (side, -side):
            corner = at(sd, length)
            if _lead_clear(sheet, pin, corner, exclude):
                return corner, out
    return at(side, L / 4.0), out


def _lead_clear(sheet, pin, corner, exclude=None):
    """Does a lead from pin to corner touch nothing but the pin's own wires at the pin?"""
    bb = (min(pin[0], corner[0]) - TOL, min(pin[1], corner[1]) - TOL,
          max(pin[0], corner[0]) + TOL, max(pin[1], corner[1]) + TOL)
    for e in sheet.query(bb):
        if isinstance(e, Wire):
            if e.id == exclude:
                continue
            if e.touches(corner, TOL):
                return False
            for a, b in zip(e.points, e.points[1:]):
                hit = _segment_meet(pin, corner, a, b)
                if hit is not None and not _same(hit, pin):
                    return False
        elif isinstance(e, Insert):
            for _n, q in e.pin_points():
                if not _same(q, pin) and _on_segment(q, pin, corner):
                    return False
    return True


def _on_segment(q, a, b):
    """Is q on the segment a-b (within TOL)?"""
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    if L <= TOL:
        return math.hypot(q[0] - a[0], q[1] - a[1]) <= TOL
    t = ((q[0] - a[0]) * (b[0] - a[0]) + (q[1] - a[1]) * (b[1] - a[1])) / (L * L)
    if t < -TOL / L or t > 1 + TOL / L:
        return False
    px, py = a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])
    return math.hypot(q[0] - px, q[1] - py) <= TOL


def _segment_meet(a, b, c, d):
    """Where segments a-b and c-d meet (a point; one of the ends of an overlap), or None."""
    for q in (c, d):
        if _on_segment(q, a, b):
            return q
    for q in (a, b):
        if _on_segment(q, c, d):
            return q
    r = (b[0] - a[0], b[1] - a[1])
    s_ = (d[0] - c[0], d[1] - c[1])
    den = r[0] * s_[1] - r[1] * s_[0]
    if abs(den) <= 1e-12:
        return None
    t = ((c[0] - a[0]) * s_[1] - (c[1] - a[1]) * s_[0]) / den
    u = ((c[0] - a[0]) * r[1] - (c[1] - a[1]) * r[0]) / den
    if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
        return (a[0] + t * r[0], a[1] + t * r[1])
    return None


def route(a, b, horizontal_first=True):
    """The corner points of a straight-across / up-and-down path from a to b."""
    if abs(a[0] - b[0]) < 1e-9 or abs(a[1] - b[1]) < 1e-9:
        return [b]
    corner = (b[0], a[1]) if horizontal_first else (a[0], b[1])
    return [corner, b]



# ---- a run of a wire dragged sideways (its middle grip; Scoot on a wire) --------------------
def segment_drag(sheet, w, k, to, _seen=None):
    """A straight run of wire w (from its point k to k + 1) moved square to itself to pass
    through to (the owner, 0.16: "drag a wire left or right if it's vertical or up-and-down if
    it's horizontal, and then the rest of the wires will automatically reconnect to it in its
    new location"): {wire id: new points} for w and the wires joined to it. Its neighbours stretch
    (they are square to it); an end of w that is joined to something (a pin, a wire) stays,
    with a short jog to the run's new place; a wire ending on the run (a T) or at one of its
    corners moves its end with it, or gets a jog when its last leg isn't square to the run.
    {} when the run isn't straight across or up and down; None when a symbol's pin sits on
    the run itself (its middle, or a corner of it): moved, the wire would leave that pin (the
    battery, seeds 11 and 23: a run through a starter's T1)."""
    pts = list(w.points)
    if not 0 <= k < len(pts) - 1:
        return {}
    a, b = pts[k], pts[k + 1]
    if abs(a[1] - b[1]) < TOL:
        d = (0.0, to[1] - a[1])
    elif abs(a[0] - b[0]) < TOL:
        d = (to[0] - a[0], 0.0)
    else:
        return {}
    if abs(d[0]) < TOL and abs(d[1]) < TOL:
        return {}

    last = len(pts) - 1
    x0, x1 = sorted((a[0], b[0]))
    y0, y1 = sorted((a[1], b[1]))
    for e in sheet.query((x0 - TOL, y0 - TOL, x1 + TOL, y1 + TOL)):
        if isinstance(e, Insert):
            for _n, q in e.pin_points():
                if G.dist_to_segment(q, a, b) > TOL:
                    continue
                if (k == 0 and G.dist(q, a) <= TOL) or (k + 1 == last and G.dist(q, b) <= TOL):
                    continue            # (w's own end on it: it stays, with a jog)
                return None

    def mv(q):
        return (q[0] + d[0], q[1] + d[1])
    # a neighbour run shortened by the move: what was on the part it loses (a pin, a wire's
    # end) would come off the wire (the battery, seed 31: a short run dragged far past the end
    # of the long run beside it, which had two pins on it)
    for j, c in ((k - 1, k), (k + 2, k + 1)):
        if not 0 <= j <= last:
            continue
        f, old = pts[j], pts[c]
        nw = mv(old)
        nx0, nx1 = sorted((f[0], old[0]))
        ny0, ny1 = sorted((f[1], old[1]))
        for e in sheet.query((nx0 - TOL, ny0 - TOL, nx1 + TOL, ny1 + TOL)):
            if isinstance(e, Insert):
                spots = [q for _n, q in e.pin_points()]
            elif isinstance(e, Wire) and e.id != w.id:
                spots = [e.points[0], e.points[-1]]
            else:
                continue
            for q in spots:
                # (at the corner itself it moves with it: a wire's end there follows, and a pin
                # there is one on the run, refused above)
                if G.dist(q, old) > TOL and G.dist_to_segment(q, f, old) <= TOL and \
                        G.dist_to_segment(q, f, nw) > TOL:
                    return None
    new = list(pts)
    new[k], new[k + 1] = mv(a), mv(b)

    moving = (_seen or set()) | {w.id}

    def joined(q):
        # (to something staying: a pin, or a wire not moving in this drag)
        if pins_on(sheet, q):
            return True
        return any(o.id not in moving and o.distance(q) <= TOL
                   for o in sheet.query((q[0] - TOL, q[1] - TOL, q[0] + TOL, q[1] + TOL))
                   if isinstance(o, Wire))
    # (an end of w that is joined stays put: a jog to the run's new place)
    if k == 0 and joined(a):
        new = [a] + new
        off = 1
    else:
        off = 0
    if k + 1 == last and joined(b):
        new = new + [b]
    out = {w.id: [tuple(q) for q in _tidy_pts(new)]}

    def moved_end(o, i):
        """o's end i (0 or -1) moved with the run: stretched along its last leg when that is
        square to the run, else a jog added."""
        ps = list(o.points)
        e = ps[i]
        nb = ps[1] if i == 0 else ps[-2]
        along = (abs(e[0] - nb[0]) < TOL) if d[0] == 0.0 else (abs(e[1] - nb[1]) < TOL)
        if along:
            ps[i] = mv(e)
        elif i == 0:
            ps = [mv(e)] + ps
        else:
            ps = ps + [mv(e)]
        return [tuple(q) for q in _tidy_pts(ps)]
    seen = (_seen or set()) | {w.id}
    for o in sheet.query((x0 - TOL, y0 - TOL, x1 + TOL, y1 + TOL)):
        if not isinstance(o, Wire) or o.id in seen:
            continue
        for i in (0, -1):
            e = o.points[i]
            if G.dist_to_segment(e, a, b) > TOL:
                continue
            nb = o.points[1] if i == 0 else o.points[-2]
            straight_on = (G.dist(e, a) <= TOL or G.dist(e, b) <= TOL) and \
                G.dist_to_segment(nb, a, b) > TOL and (
                    (abs(nb[0] - e[0]) < TOL) if d[0] != 0.0 else (abs(nb[1] - e[1]) < TOL))
            if straight_on and len(o.points) >= 2:
                # (it carries the run straight on: its own end run moves sideways with it)
                more = segment_drag(sheet, o, 0 if i == 0 else len(o.points) - 2, to,
                                    seen | set(out))
                if more is None:
                    return None             # (a pin on the run it carries on: no move)
                for oid, q in more.items():
                    if oid not in out:
                        out[oid] = q
                seen |= set(more)
                break
            # (at a corner of w that is w's own joined end, w keeps its place: o stays)
            if (G.dist(e, a) <= TOL and k == 0 and off) or \
                    (G.dist(e, b) <= TOL and k + 1 == last and len(new) > len(pts) + off):
                continue
            out[o.id] = moved_end(o if o.id not in out else Wire(out[o.id]), i)
    return out


def _tidy_pts(pts):
    from .model import _tidy
    return _tidy([list(q) for q in pts])


# ---- going around symbols -----------------------------------------------------------------
# (the owner, 0.16: "When inserting wires, they are not going around the object": a wire from
# an overload's T3 to a drive's L3 on the drive's bottom edge ran straight through the drive)
CLEAR = 0.125       # paper inches a wire keeps from a symbol's drawing
BEND = 0.75         # what a corner costs, in inches of wire (fewer corners over a bit shorter)


def body_box(e):
    """The box of a placed symbol's drawing, its tag and attribute texts left out (kept per
    copy: a copy is a value)."""
    got = getattr(e, "_body", None)
    if got is not None:
        return got
    bb = None
    d = e.defn
    if d is not None:
        for x in d.entities:
            bb = G.bbox_union(bb, x._map(e.to_world, rot=e.angle, factor=e.scale,
                                         mirror=None).bbox())
    e._body = bb
    return bb


def _boxes(sheet, region, k):
    out = []
    for e in sheet.query(region):
        if isinstance(e, Insert) and e.defn is not None and e.defn.kind == "symbol":
            bb = body_box(e)
            if bb is not None and bb[2] - bb[0] > 1e-9 and bb[3] - bb[1] > 1e-9:
                out.append((e, bb))
    return out


def _crosses(pts, boxes):
    """Does the path run through the inside of any box?"""
    for a, b in zip(pts, pts[1:]):
        x0, x1 = sorted((a[0], b[0]))
        y0, y1 = sorted((a[1], b[1]))
        for _e, bb in boxes:
            if x0 < bb[2] - TOL and x1 > bb[0] + TOL and y0 < bb[3] - TOL and \
                    y1 > bb[1] + TOL:
                return True
    return False


def _out_of(sheet, p, boxes):
    """The way out of the symbol whose pin p is (dx, dy, a unit along x or y), or None."""
    for e, bb in boxes:
        if any(G.dist(q, p) <= TOL for _n, q in e.pin_points()):
            cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
            dx, dy = p[0] - cx, p[1] - cy
            # (the side it is on: nearest the box's edge)
            near = min((abs(p[0] - bb[0]), (-1, 0)), (abs(p[0] - bb[2]), (1, 0)),
                       (abs(p[1] - bb[1]), (0, -1)), (abs(p[1] - bb[3]), (0, 1)))
            if near[0] <= TOL * 10 or not (bb[0] < p[0] < bb[2] and bb[1] < p[1] < bb[3]):
                return near[1]
            return (1 if dx >= 0 else -1, 0) if abs(dx) >= abs(dy) else (0, 1 if dy >= 0 else -1)
    return None


def route_around(sheet, a, b, plain, clear=CLEAR, extra=0.0, side=None):
    """The corner points from a to b (plain: the usual one-corner path's) going around the
    symbols in the way, straight across and up and down, leaving a pin (and arriving at one)
    straight out of its side, the fewest corners and then the shortest; plain when nothing is in
    the way or no way round is found. clear: how far (paper inches) it keeps from a symbol
    (project setting wire_clear); extra: more, in drawing units (a bus: the width of its other
    wires), all round, or with side (1: right of the way it goes, -1: left) only on that side:
    the band each leg sweeps that far over is kept clear too (a bus's other wires, beside its
    first one: the battery, seed 19, a bus 4.75" wide past a tall terminal strip)."""
    import heapq
    k = sheet.k()
    band = extra if side else 0.0
    extra = 0.0 if side else extra
    c = clear * k + extra
    pad = 3.0 * k + extra + band
    region = (min(a[0], b[0]) - pad, min(a[1], b[1]) - pad, max(a[0], b[0]) + pad,
              max(a[1], b[1]) + pad)
    boxes = _boxes(sheet, region, k)
    # (with extra, the box grown by it: a bus whose first wire just misses a symbol while the
    # others run through it, the battery, seed 8 on a 1:6 sheet)
    grow = extra + band
    if not boxes or not _crosses([a] + plain, [(e, (bb[0] - grow, bb[1] - grow,
                                                    bb[2] + grow, bb[3] + grow))
                                               for e, bb in boxes]):
        return plain
    g = 0.125 * k                               # (corners on the 1/8" grid)

    def out_pt(p):
        d = _out_of(sheet, p, boxes)
        if d is None:
            return p, None
        return (p[0] + d[0] * (c + g), p[1] + d[1] * (c + g)), d
    a2, _da = out_pt(a)
    b2, _db = out_pt(b)
    import math
    grown = []
    for e, bb in boxes:
        grown.append((math.floor((bb[0] - c) / g) * g, math.floor((bb[1] - c) / g) * g,
                      math.ceil((bb[2] + c) / g) * g, math.ceil((bb[3] + c) / g) * g))

    def inside(q):
        return any(x0 + TOL < q[0] < x1 - TOL and y0 + TOL < q[1] < y1 - TOL
                   for x0, y0, x1, y1 in grown)

    def blocked(p, q):
        x0, x1 = sorted((p[0], q[0]))
        y0, y1 = sorted((p[1], q[1]))
        for bx0, by0, bx1, by1 in grown:
            if x0 < bx1 - TOL and x1 > bx0 + TOL and y0 < by1 - TOL and y1 > by0 + TOL:
                return True
            if abs(y0 - y1) < TOL and by0 + TOL < y0 < by1 - TOL and x0 < bx1 - TOL and \
                    x1 > bx0 + TOL:
                return True
            if abs(x0 - x1) < TOL and bx0 + TOL < x0 < bx1 - TOL and y0 < by1 - TOL and \
                    y1 > by0 + TOL:
                return True
        return False

    def swept(p, q):
        # (the band beside the leg, band wide on side: inside no grown box)
        L = G.dist(p, q)
        if not band or L < TOL:
            return False
        nx, ny = (q[1] - p[1]) / L * side, -(q[0] - p[0]) / L * side      # (right: side 1)
        bx = (p[0], q[0], p[0] + nx * band, q[0] + nx * band)
        by = (p[1], q[1], p[1] + ny * band, q[1] + ny * band)
        x0, x1, y0, y1 = min(bx), max(bx), min(by), max(by)
        return any(x0 < gx1 - TOL and x1 > gx0 + TOL and y0 < gy1 - TOL and y1 > gy0 + TOL
                   for gx0, gy0, gx1, gy1 in grown)
    if inside(a2) or inside(b2):
        return plain
    xs = sorted({round(v, 9) for v in [a2[0], b2[0]] + [q for bx in grown for q in (bx[0], bx[2])]})
    ys = sorted({round(v, 9) for v in [a2[1], b2[1]] + [q for bx in grown for q in (bx[1], bx[3])]})
    xi, yi = {x: i for i, x in enumerate(xs)}, {y: i for i, y in enumerate(ys)}
    start = (xi[round(a2[0], 9)], yi[round(a2[1], 9)])
    goal = (xi[round(b2[0], 9)], yi[round(b2[1], 9)])
    # (Dijkstra over the grid's crossings: the state is the crossing and the way it came)
    best = {(start, None): 0.0}
    heap = [(0.0, start, None)]
    came = {}
    end = None
    while heap:
        cost, node, way = heapq.heappop(heap)
        if best.get((node, way), 1e300) < cost - 1e-12:
            continue
        if node == goal:
            end = (node, way)
            break
        i, j = node
        for di, dj, w in ((1, 0, "x"), (-1, 0, "x"), (0, 1, "y"), (0, -1, "y")):
            ni, nj = i + di, j + dj
            if not (0 <= ni < len(xs) and 0 <= nj < len(ys)):
                continue
            p, q = (xs[i], ys[j]), (xs[ni], ys[nj])
            if inside(q) or blocked(p, q) or swept(p, q):
                continue
            nc = cost + G.dist(p, q) + (BEND * k if way is not None and way != w else 0.0)
            if nc < best.get(((ni, nj), w), 1e300) - 1e-12:
                best[((ni, nj), w)] = nc
                came[((ni, nj), w)] = (node, way)
                heapq.heappush(heap, (nc, (ni, nj), w))
    if end is None:
        return plain
    pts = []
    st = end
    while st[0] != start or st[1] is not None:
        pts.append((xs[st[0][0]], ys[st[0][1]]))
        st = came.get(st)
        if st is None:
            break
    pts.append((xs[start[0]], ys[start[1]]))
    pts.reverse()
    path = [a] + ([a2] if G.dist(a, a2) > TOL else []) + pts[1:]
    if G.dist(pts[-1], b) > TOL:
        path.append(b)
    # (straight runs as one: no corner where it doesn't turn)
    out = [path[0]]
    for q in path[1:]:
        if G.dist(q, out[-1]) < TOL:
            continue
        if len(out) >= 2:
            p0, p1 = out[-2], out[-1]
            if (abs(p0[0] - p1[0]) < TOL and abs(p1[0] - q[0]) < TOL) or \
                    (abs(p0[1] - p1[1]) < TOL and abs(p1[1] - q[1]) < TOL):
                out[-1] = q
                continue
        out.append(q)
    return out[1:]


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
    meets another wire or a pin, or bends, goes (to the wire's end when there is none on that
    side: the owner, 0.16: a bent wire crossing nothing went whole, "Trim wire should not
    function as delete wire in those instances"). Returns (the pieces left, as new wires
    keeping its layer, color and number; the points where the cut part met the rest)."""
    pts, cum, cuts = _hits(sheet, w)
    cuts = sorted(set(cuts) | {round(c, 9) for c in cum[1:-1]})     # (its bends)
    total = cum[-1]
    s0 = _poly_param(pts, cum, click)
    lo = max([s for s in cuts if TOL < s < s0 - TOL], default=0.0)
    hi = min([s for s in cuts if s0 + TOL < s < total - TOL], default=total)
    keep = dict(layer=w.layer, color=w.color, num=w.num, num_lock=w.num_lock,
                own_num=w.own_num, same_num=w.same_num, awg=w.awg,
                    show_color=w.show_color, pin_tap=w.pin_tap)
    out, ends = [], []
    if lo > TOL:
        piece = _poly_piece(pts, cum, 0.0, lo)
        out.append(Wire(piece, labels=_labels_between(w, 0.0, lo), **keep))
        ends.append(tuple(piece[-1]))
    else:
        ends.append(tuple(pts[0]))
    if total - hi > TOL:
        piece = _poly_piece(pts, cum, hi, total)
        out.append(Wire(piece, labels=_labels_between(w, hi, total), **keep))
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


def _labels_between(w, lo, hi):
    """The labels (Wire number label) of w between lo and hi along it, measured from lo: what
    a piece of it cut from lo to hi keeps."""
    return [t - lo for t in w.labels if lo - TOL <= t <= hi + TOL]


def _joined_labels(a, a_reversed, b, b_reversed, gap=0.0):
    """The labels of a and b on the wire made of a then b (a reversed when its first point is
    where they meet, b reversed when its last is; gap: the piece between them, when they
    don't meet), measured along it."""
    la, lb = a.length(), b.length()
    out = [(la - t) if a_reversed else t for t in a.labels]
    out += [la + gap + ((lb - t) if b_reversed else t) for t in b.labels]
    return out


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
        if a.layer != b.layer or a.awg != b.awg:
            # (a 480 V wire meeting a 120 V one, or a 10 AWG one a 12: they stay two wires,
            # each keeping its layer and size, 0.18.2)
            continue
        pa = list(a.points) if ia == -1 else list(reversed(a.points))
        pb = list(b.points) if ib == 0 else list(reversed(b.points))
        # (not when b goes back along a: joined, the wire would fold back over itself, the
        # battery, seed 306: a bus wire laid on another wire the other way, and a pin left in
        # the middle of the fold)
        # (by the angle between them, as doubles_back measures: an end a hair off the other's
        # line, 52455.999999999985 for 52456 far from the origin, passed a fixed tolerance and
        # was joined into a fold, the long battery on GitHub, seed 3283)
        if doubles_back([pa[-2], p, pb[1]]):
            continue
        merged = _tidy(pa + pb[1:])
        if len(merged) < 2 or doubles_back(merged):
            continue
        ed.remove(sheet, b.id)
        ed.change(sheet, a.copy(points=merged, show_color=a.show_color or b.show_color,
                                labels=_joined_labels(a, ia != -1, b, ib != 0)))
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


def doubles_back(pts):
    """Does the path turn straight back along itself anywhere (a leg running back over the one
    before it)? Such a wire looks like one straight wire but has a hidden corner, and a dot
    showed there (the owner's bus wires, 0.17.5: out past the last drive, then a click back)."""
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        u = (b[0] - a[0], b[1] - a[1])
        v = (c[0] - b[0], c[1] - b[1])
        if abs(u[0] * v[1] - u[1] * v[0]) <= 1e-9 * max(1.0, G.dist(a, b) * G.dist(b, c)) \
                and u[0] * v[0] + u[1] * v[1] < 0:
            return True
    return False


def straighten(pts):
    """A route's points without the corners where it turns straight back along itself (a jog
    over and straight back: a dead end of no use, it goes on from there along the same line)."""
    out = [tuple(q) for q in pts]
    i = 1
    while 0 < i < len(out) - 1:
        if doubles_back(out[i - 1:i + 2]):
            del out[i]
            i = max(1, i - 1)
        else:
            i += 1
    return out


def unfold(sheet, pts):
    """A wire's points without a last (or first) leg running straight back over the one
    before it and ending on it: that end goes, the wire keeps its length (the owner's bus
    wires, 0.17.5, drawn out past the last drive and then back: a hidden corner with a dot).
    An end on a pin stays (the pin is connected there)."""
    pts = [tuple(q) for q in pts]
    for _side in (0, 1):
        while len(pts) >= 3:
            a, b, c = pts[-3], pts[-2], pts[-1]
            if not doubles_back([a, b, c]) or G.dist_to_segment(c, a, b) > TOL or \
                    pins_on(sheet, c):
                break
            pts.pop()
        pts.reverse()
    return pts


def cleanup(ed, sheet, ws=None):
    """Clean up wires (the given ones, or every wire on the sheet): wires of no length go,
    repeated and in-line points go, a wire drawn over another goes, and wires meeting end to
    end with nothing else there become one. Returns the counts, with the wire ends left
    connected to nothing ("loose"). A wire that doubles back over itself at an end loses the
    doubled piece (unfold)."""
    from .model import _tidy
    ws = list(sheet.wires() if ws is None else ws)
    got = {"empty": 0, "tidied": 0, "duplicates": 0, "joined": 0, "loose": 0}
    for w in ws:
        cur = sheet.entities.get(w.id)
        if not isinstance(cur, Wire):
            continue
        pts = _tidy(unfold(sheet, cur.points))
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
        if not isinstance(wa, Wire) or not isinstance(wb, Wire) or wa.id == wb.id or \
                wa.layer != wb.layer or wa.awg != wb.awg:
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
        labels = _joined_labels(wa, ia != -1, wb, ib != 0, G.dist(a, b))
        if wb.num_lock and not wa.num_lock:
            wa, wb = wb, wa
            merged = merged[::-1]
            total = sum(G.dist(x, y) for x, y in zip(merged, merged[1:]))
            labels = [total - t for t in labels]
        ed.remove(sheet, wb.id)
        ed.change(sheet, wa.copy(points=merged, labels=labels))
        used.update((a, b))
        n += 1
    return n


MISS = 0.03125      # paper inches: a wire end this near a pin or wire without joining it


PULL = 0.01         # real inches: a moved wire end this near a pin or wire is put on it


def moved_ends(sheet, changed):
    """[(wire id, 0 or -1)] of the wire ends the changed copies (not yet written) move."""
    out = []
    for e in changed:
        old = sheet.entities.get(e.id)
        if not isinstance(e, Wire) or not isinstance(old, Wire) or len(e.points) < 2:
            continue
        for i in (0, -1):
            if G.dist(e.points[i], old.points[i]) > TOL:
                out.append((e.id, i))
    return out


def pull_on(ed, sheet, ends, hi=PULL):
    """Wire ends an edit moved (Stretch, a grip) that stop less than hi from a pin or another
    wire without joining it are put exactly on it: the nearest pin, or the nearest point of
    the nearest run (the owner's choice, 0.18.3, "pull close ends on": a gap of a few
    thousandths is never meant; the battery, seed 1803, a tap end on a nearly flat slanted
    wire stretched sideways stopped 0.0021" under a wire). Returns how many."""
    n = 0
    for wid, i in ends:
        w = sheet.entities.get(wid)
        if not isinstance(w, Wire) or len(w.points) < 2:
            continue
        p = w.points[i]
        if near_misses(sheet, [p], hi) == []:
            continue                    # (joined, or nothing that near)
        best = None
        box = (p[0] - hi, p[1] - hi, p[0] + hi, p[1] + hi)
        for o in sheet.query(box):
            if isinstance(o, Wire) and o.id != w.id:
                for a, b in zip(o.points, o.points[1:]):
                    q, _t = G.closest_on_segment(p, a, b)
                    d = G.dist(p, q)
                    if TOL < d < hi and (best is None or d < best[0]):
                        best = (d, q)
            elif isinstance(o, Insert) and o.defn is not None and o.defn.pins:
                for _n, q in o.pin_points():
                    d = G.dist(p, q)
                    if TOL < d < hi and (best is None or d < best[0] + TOL):
                        best = (d, q)       # (a pin wins over a wire as near)
        if best is None:
            continue
        got = w.end_moved(i, best[1])
        if len(got.points) >= 2:
            ed.change(sheet, got)
            n += 1
    return n


def near_misses(sheet, points, hi=None):
    """Wire ends (points) that stop just short of a pin or another wire without joining it
    (the owner, 0.16: wires that look connected and aren't; the battery has found them in the
    program's own drawing, a user drawing with snaps off makes them): [(point, what it nearly
    meets: "pin 2 of CR101" or "a wire", how far)], nearer than hi (MISS on paper) but farther
    than TOL."""
    hi = MISS * sheet.k() if hi is None else hi
    out = []
    for p in points:
        box = (p[0] - hi, p[1] - hi, p[0] + hi, p[1] + hi)
        best = None
        joined = False
        touching = 0                    # (wires at p: its own wire is one)
        for o in sheet.query(box):
            if isinstance(o, Wire):
                own = G.dist(p, o.points[0]) <= TOL or G.dist(p, o.points[-1]) <= TOL
                if own:
                    touching += 1
                    continue            # (the wire this end belongs to, or one joined end on)
                for a, b in zip(o.points, o.points[1:]):
                    d = G.dist_to_segment(p, a, b)
                    if d <= TOL:
                        joined = True   # (on another wire's middle: a T)
                    elif d < hi and (best is None or d < best[2]):
                        best = (p, "a wire", d)
            elif isinstance(o, Insert) and o.defn is not None and o.defn.pins:
                for n, q in o.pin_points():
                    d = G.dist(p, q)
                    if d <= TOL:
                        joined = True
                    elif d < hi and (best is None or d < best[2]):
                        best = (p, "pin %s of %s" % (n, o.attrs.get("TAG") or o.block), d)
        if touching >= 2:
            joined = True               # (another wire's end here: joined end to end)
        if best is not None and not joined:
            out.append(best)
    return out
