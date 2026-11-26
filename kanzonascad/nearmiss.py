"""Wire ends and pins that almost touch a wire, a wire end or a pin without being joined to it
(the owner's decision, Nov 26 2026, "Warn on the drawing"): marked red on the drawing until
fixed and said on the command line when one appears, as duplicate tags are (dupes.py).

A symbol turned to an odd angle (45 degrees) has its pins at irrational coordinates, so a pin,
or a wire routed from one, can stop a few thousandths of an inch from an unrelated wire.
Joining them would wire two circuits together; leaving them unmarked would look joined and
not be. The program doesn't guess: it marks the spot and the user moves it away or onto it.

"Almost" is nearer than NEAR (real inches, as Move, Copy, Stretch and grips pull an end on:
wires.PULL) but farther than the program's own tolerance TOL (wires.TOL). It is the drawing-
slop check of the battery (tests/battery_checks.near_misses), which accepts a near miss only
when this finds it:
- a wire end (one whose last run is straight across or up and down: an end at the end of a
  slanted run is wherever that run was cut) near another wire's straight run or straight end,
  or near a pin, other than one its own wire's other end is on;
- a symbol's pin near another symbol's pin, or near a straight run of a wire with no end
  near it (a wire end near a pin is found from the wire end);
- not where it sits on a slanted run of another wire (where a slanted run crosses is chance).

Worked out per sheet version, and after an edit only round what it changed (entities are
values: a changed wire or symbol is a new object), through the sheet's spatial index; never
on a paint or a mouse move."""

from . import geometry as G
from .model import Insert, Wire

TOL = 1e-6                  # (wires.TOL: ends this close are joined)
NEAR = 0.01                 # real inches (wires.PULL)
FAR = NEAR * 2              # (no distance found)


def _slanted(a, b):
    return abs(a[0] - b[0]) >= 1e-9 and abs(a[1] - b[1]) >= 1e-9


def _straight_ends(w):
    return [q for q, r in ((w.points[0], w.points[1]), (w.points[-1], w.points[-2]))
            if not _slanted(q, r)]


def _has_pins(o):
    return isinstance(o, Insert) and o.defn is not None and bool(o.defn.pins)


def _box(p, r):
    return (p[0] - r, p[1] - r, p[0] + r, p[1] + r)


def _near(sheet, p, own):
    """The wires and symbols with pins (but own) whose box comes within NEAR of p, or None
    when p is on a slanted run of one of those wires (where that crosses is chance)."""
    out = []
    x, y = p
    for o in sheet.query((x - NEAR, y - NEAR, x + NEAR, y + NEAR)):
        if o.id == own:
            continue
        x0, y0, x1, y1 = o.bbox()
        if x < x0 - NEAR or x > x1 + NEAR or y < y0 - NEAR or y > y1 + NEAR:
            continue
        if isinstance(o, Wire):
            for a, b in zip(o.points, o.points[1:]):
                if _slanted(a, b) and G.dist_to_segment(p, a, b) <= TOL:
                    return None
            out.append(o)
        elif _has_pins(o):
            out.append(o)
    return out


def _run_dist(p, o, d):
    """The least of d and how far p is from wire o's runs straight across or up and down."""
    for a, b in zip(o.points, o.points[1:]):
        if a[0] == b[0] or a[1] == b[1] or not _slanted(a, b):
            d = min(d, G.dist_to_segment(p, a, b))
    return d


def _pin_name(o, n):
    return "pin %s of %s" % (n, o.attrs.get("TAG") or o.block_name)


def _end_miss(sheet, w, i):
    """(point, what it almost meets, how far, "a wire end") for wire w's end i (0 or -1), or
    None."""
    p = w.points[i]
    if _slanted(p, w.points[1] if i == 0 else w.points[-2]):
        return None
    other = w.points[-1] if i == 0 else w.points[0]
    near = _near(sheet, p, w.id)
    best = None
    for o in near or ():
        if isinstance(o, Wire):
            d = min([G.dist(p, q) for q in _straight_ends(o)] or [FAR])
            if d <= TOL:
                continue                # (joined end to end)
            d = _run_dist(p, o, d)
            if d <= TOL or d >= NEAR or o.distance(other) <= TOL:
                continue                # (on it; not near it; its other end on it: a sliver)
            what = "a wire"
        else:
            d, what = FAR, None
            for n, q in o.pin_points():
                if G.dist(other, q) > TOL and G.dist(p, q) < d:
                    d, what = G.dist(p, q), _pin_name(o, n)
        if TOL < d < NEAR and (best is None or d < best[2]):
            best = (p, what, d, "a wire end")
    return best


def _pin_miss(sheet, ins, q, name):
    """(point, what it almost meets, how far, "pin 2 of CR1") for the pin name of ins at q,
    or None."""
    near = _near(sheet, q, ins.id)
    best = None
    for o in near or ():
        if isinstance(o, Wire):
            if G.dist(q, o.points[0]) < NEAR or G.dist(q, o.points[-1]) < NEAR:
                continue                # (on its end, or found from its end)
            d = _run_dist(q, o, FAR)
            what = "a wire"
        else:
            d, what = FAR, None
            for n, r in o.pin_points():
                if G.dist(q, r) < d:
                    d, what = G.dist(q, r), _pin_name(o, n)
        if TOL < d < NEAR and (best is None or d < best[2]):
            best = (q, what, d, _pin_name(ins, name))
    return best


def _subjects_in(sheet, box):
    """[(key, entity, end index or pin point)] of the wire ends and pins inside box."""
    out = []
    x0, y0, x1, y1 = box

    def inside(p):
        return x0 <= p[0] <= x1 and y0 <= p[1] <= y1
    for o in sheet.query(box):
        if isinstance(o, Wire) and len(o.points) >= 2:
            for i in (0, -1):
                if inside(o.points[i]):
                    out.append((("end", o.id, i), o, i))
        elif _has_pins(o):
            for n, q in o.pin_points():
                if inside(q):
                    out.append((("pin", o.id, n), o, q))
    return out


def _work_out(sheet, key, o, where):
    if key[0] == "end":
        return _end_miss(sheet, o, where)
    return _pin_miss(sheet, o, where, key[2])


def _spots(e):
    """Boxes round what of e a near miss depends on: a wire's runs, a symbol's pins."""
    r = NEAR + TOL
    if isinstance(e, Wire):
        return [(min(a[0], b[0]) - r, min(a[1], b[1]) - r, max(a[0], b[0]) + r,
                 max(a[1], b[1]) + r) for a, b in zip(e.points, e.points[1:])]
    if _has_pins(e):
        return [_box(q, r) for _n, q in e.pin_points()]
    return []


def _moved(a, b):
    """Whether what a near miss reads of a differs in b: where a wire is; where a symbol's
    pins are, and its tag (named in the message)."""
    if b is None or type(a) is not type(b):
        return True
    if isinstance(a, Wire):
        return a.points != b.points
    return a.pin_points() != b.pin_points() or a.attrs.get("TAG") != b.attrs.get("TAG") or \
        a.block_name != b.block_name


def found_keyed(sheet):
    """{("end", wire id, 0 or -1) or ("pin", symbol id, pin name): (point, what it almost
    meets, how far, what does)} on sheet (kept per sheet version, worked out again only round what an
    edit changed)."""
    got = getattr(sheet, "_near", None)
    if got is not None and got[0] == sheet.version:
        return got[1]
    cur = {e.id: e for e in sheet.wires()}
    cur.update((e.id, e) for e in sheet.inserts() if _has_pins(e))
    st = getattr(sheet, "_near_state", None)
    if st is None:
        res = {}
        for e in cur.values():
            subs = ([(("end", e.id, i), e, i) for i in (0, -1)] if isinstance(e, Wire)
                    else [(("pin", e.id, n), e, q) for n, q in e.pin_points()])
            for key, o, where in subs:
                m = _work_out(sheet, key, o, where)
                if m is not None:
                    res[key] = m
    else:
        old, res = st
        stale = [old[i] for i in old if cur.get(i) is not old[i] and _moved(old[i], cur.get(i))]
        stale += [e for i, e in cur.items() if old.get(i) is not e and _moved(e, old.get(i))]
        if stale:
            # (a new dict: the one handed out before stays as it was)
            ids = {e.id for e in stale}
            res = {k: v for k, v in res.items() if k[1] not in ids}
            done = set()
            for e in stale:
                for box in _spots(e):
                    for key, o, where in _subjects_in(sheet, box):
                        if key in done:
                            continue
                        done.add(key)
                        m = _work_out(sheet, key, o, where)
                        if m is None:
                            res.pop(key, None)
                        else:
                            res[key] = m
    sheet._near_state = (cur, res)
    sheet._near = (sheet.version, res)
    return res


def found(sheet):
    """[(point, what it almost meets, how far, what does)] on sheet, one per spot (a wire end on a pin
    near a passing wire is the end's and the pin's: said once), left to right."""
    got = getattr(sheet, "_near_list", None)
    if got is not None and got[0] == sheet.version:
        return got[1]
    out, seen = [], {}
    got = found_keyed(sheet)
    for _key, m in sorted(got.items(), key=lambda kv: (kv[1][0][0], kv[1][0][1], str(kv[0]))):
        p = m[0]
        cx, cy = int(p[0] // NEAR), int(p[1] // NEAR)
        if any(G.dist(p, q) <= TOL * 10 for i in (-1, 0, 1) for j in (-1, 0, 1)
               for q in seen.get((cx + i, cy + j), ())):
            continue
        seen.setdefault((cx, cy), []).append(p)
        out.append(m)
    sheet._near_list = (sheet.version, out)
    return out


def in_project(project):
    """{sheet: found(sheet)} for the sheets with any."""
    out = {}
    for s in project.sheets:
        got = found(s)
        if got:
            out[s] = got
    return out
