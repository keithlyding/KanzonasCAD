"""Sliding devices along their own wires (no Qt): AutoCAD Electrical's Scoot and Align.

A device's wire runs the way its pins face each other: across for a horizontal rung (pins on
the left and right), up and down for a vertical wire. Sliding it that way, the wires on its
pins stretch on one side and shorten on the other (wires.follow_pins, at the end of the edit),
staying straight. It can slide only as far as the wire on each pin reaches before a corner or
its far end, less a little (it never folds a wire back on itself).
"""

import math

from .model import Insert, Wire

TOL = 1e-6
MARGIN = 0.0625                 # left of a wire's piece between a pin and the next corner


def axis(ins):
    """(1, 0) when the device's wire runs across, (0, 1) up and down, None without two pins."""
    pins = [p for _n, p in ins.pin_points()]
    if len(pins) < 2:
        return None
    dx = max(p[0] for p in pins) - min(p[0] for p in pins)
    dy = max(p[1] for p in pins) - min(p[1] for p in pins)
    return (1.0, 0.0) if dx >= dy else (0.0, 1.0)


def limits(sheet, ins, ax):
    """(how far back, how far forward) the device can slide along ax: each pin's wire piece
    running away from it limits the slide toward that piece's far end; a wire piece running
    toward the device limits nothing (it gets longer). Infinite when nothing limits."""
    back = fwd = math.inf
    for _n, p in ins.pin_points():
        for e in sheet.query((p[0] - TOL, p[1] - TOL, p[0] + TOL, p[1] + TOL)):
            if not isinstance(e, Wire):
                continue
            pts = e.points
            for i in (0, -1):
                if abs(pts[i][0] - p[0]) > TOL or abs(pts[i][1] - p[1]) > TOL:
                    continue
                q = pts[1] if i == 0 else pts[-2]           # the next corner or the far end
                along = (q[0] - p[0]) * ax[0] + (q[1] - p[1]) * ax[1]
                across = abs((q[0] - p[0]) * ax[1] - (q[1] - p[1]) * ax[0])
                if across > TOL:
                    continue            # (a piece leaving at a right angle: no limit along)
                room = max(0.0, abs(along) - MARGIN)
                if along > 0:
                    fwd = min(fwd, room)
                elif along < 0:
                    back = min(back, room)
    return back, fwd


def clamp(sheet, ins, ax, d):
    """The slide d (signed distance along ax) cut to what the wires allow."""
    back, fwd = limits(sheet, ins, ax)
    return max(-back, min(fwd, d))


def devices(ents):
    """The block references among ents that have a wire direction."""
    return [e for e in ents if isinstance(e, Insert) and axis(e) is not None]


# ---- a whole branch (the owner, 0.17.3: "I need to be able to scoot a motor and everything
# attached to it gets scooted with it. Same thing if I scoot a vfd") ------------------------
def _pins_at(sheet, q):
    return [e for e in sheet.query((q[0] - TOL, q[1] - TOL, q[0] + TOL, q[1] + TOL))
            if isinstance(e, Insert) and any(abs(r[0] - q[0]) <= TOL and abs(r[1] - q[1]) <= TOL
                                             for _n, r in e.pin_points())]


def _wires_at(sheet, q):
    return [e for e in sheet.query((q[0] - TOL, q[1] - TOL, q[0] + TOL, q[1] + TOL))
            if isinstance(e, Wire) and e.touches(q, TOL)]


def _is_end(w, q):
    return any(abs(p[0] - q[0]) <= TOL and abs(p[1] - q[1]) <= TOL
               for p in (w.points[0], w.points[-1]))


def branch(sheet, devs):
    """What moves with these devices: (symbols, wires moved whole, [(wire, its end on the
    branch: 0 or -1)] the wires leaving it). From each symbol's pins along its wires: a wire
    from a pin to another symbol's pin brings that symbol (and so on: a motor, its drive, its
    contactor); one carried on end to end by a single wire continues; a wire whose far end
    taps another wire's middle (a bus), or meets a junction of several, leaves the branch
    there (its end on the branch moves, the other stays on what it meets). A symbol with a pin
    along a wire that moves whole comes too."""
    syms = {e.id: e for e in devs}
    whole, leaving = {}, {}
    todo = list(devs)

    def moves_whole(path):
        # (a symbol with a pin along a wire that moves whole is attached to it too: it comes
        # along, else its pin would come off the wire, the battery, 0.17.5, seed 12)
        for x in path:
            whole[x.id] = x
            for o in sheet.query(x.bbox()):
                if isinstance(o, Insert) and o.id not in syms and \
                        any(x.touches(q, TOL) for _n, q in o.pin_points()):
                    syms[o.id] = o
                    todo.append(o)
    while todo:
        e = todo.pop()
        for _n, p in e.pin_points():
            for w in _wires_at(sheet, p):
                if w.id in whole or w.id in leaving or not _is_end(w, p):
                    continue
                path = [w]
                at = p
                while True:
                    cur = path[-1]
                    i = 0 if abs(cur.points[0][0] - at[0]) <= TOL and \
                        abs(cur.points[0][1] - at[1]) <= TOL else -1
                    far = cur.points[-1 if i == 0 else 0]
                    others = [x for x in _wires_at(sheet, far) if x.id != cur.id]
                    pins = _pins_at(sheet, far)
                    if pins:
                        for s in pins:
                            if s.id not in syms:
                                syms[s.id] = s
                                todo.append(s)
                        moves_whole(path)
                        break
                    ends = [x for x in others if _is_end(x, far)]
                    if not others:
                        moves_whole(path)               # (a loose end: moves with it)
                        break
                    if len(others) == 1 and ends and others[0].id not in whole and \
                            others[0].id not in leaving and others[0] not in path:
                        path.append(others[0])          # (carried on end to end)
                        at = far
                        continue
                    # (taps a bus, or a junction: the last wire leaves the branch here)
                    moves_whole(path[:-1])
                    leaving[cur.id] = (cur, i)    # (i: its end on the branch, which moves)
                    break
    return list(syms.values()), list(whole.values()), list(leaving.values())


def branch_moved(sheet, devs, dx, dy):
    """The changed copies for the branch of devs moved by dx, dy (across or up and down), or
    None when a wire runs uncut through one of its pins across the move: its
    symbols and inner wires moved whole; each wire leaving it moved whole when the move runs
    along what its far end is on (a drop sliding along a bus) and stays on it, else its end on
    the branch moved with a jog where needed (Wire.end_moved; it stretches or shortens)."""
    syms, whole, leaving = branch(sheet, devs)
    # (a wire running through a pin, uncut, across the way it moves: its pins would come off
    # it; None, and nothing moves: the battery, seed 12)
    moving = {w.id for w in whole} | {w.id for w, _i in leaving}
    for e in syms:
        for _n, q in e.pin_points():
            for w in _wires_at(sheet, q):
                # (along it is fine only while the pin stays on it: a wire turning a corner
                # at the pin runs along the move on one side only, the battery, seed 21)
                if w.id not in moving and not _is_end(w, q) and not (
                        _runs_along(w, q, dx, dy) and w.touches((q[0] + dx, q[1] + dy), TOL)):
                    return None
    out = [e.moved(dx, dy) for e in syms] + [w.moved(dx, dy) for w in whole]
    # (a wire tapping the middle of one that moves whole, a drop off a bus the disconnect's
    # wires make: its end there goes with it, unless the move runs along that wire)
    inside = {w.id for w in whole} | {w.id for w, _i in leaving} | {e.id for e in syms}
    for W in whole:
        for x in sheet.query(W.bbox()):
            if not isinstance(x, Wire) or x.id in inside:
                continue
            for i in (0, -1):
                q = x.points[i]
                if W.touches(q, TOL) and not _is_end(W, q) and not _runs_along(W, q, dx, dy):
                    x = x.end_moved(i, (q[0] + dx, q[1] + dy))
            if x is not sheet.entities.get(x.id):
                out.append(x)
                inside.add(x.id)
    for w, i in leaving:
        far = w.points[-1 if i == 0 else 0]
        slid = (far[0] + dx, far[1] + dy)
        on = [x for x in _wires_at(sheet, far) if x.id != w.id]
        # (moved whole only when no other symbol's pin is on it: a pushbutton's pin on its
        # middle would come off it, the battery, 0.17.5, seed 12)
        if on and all(x.touches(slid, TOL) and _runs_along(x, far, dx, dy) for x in on) and \
                not _others_pins_on(sheet, w, inside):
            out.append(w.moved(dx, dy))
        else:
            q = w.points[i]
            out.append(w.end_moved(i, (q[0] + dx, q[1] + dy)))
    return out


def strands(sheet, got, d=(0.0, 0.0)):
    """Would the changed copies got (branch_moved, everything moved by d) leave a pin with
    no wire that had one? A pin of a symbol that stays, a wire of the branch running on
    through it (the sweep, 0.18.2, seed 406: a wire back along a row of breakers' line pins);
    or a pin of one that moves, a wire leaving the branch running through it and staying
    where it was (seed 901: a long wire through a moved breaker's two pins to its far end)."""
    moved = {e.id: e for e in got if isinstance(e, Insert)}
    new = {e.id: e for e in got if isinstance(e, Wire)}
    old = [sheet.entities[i] for i in new if isinstance(sheet.entities.get(i), Wire)]

    def wired_after(q):
        if any(x.touches(q, TOL) for x in new.values()):
            return True
        box = (q[0] - TOL, q[1] - TOL, q[0] + TOL, q[1] + TOL)
        return any(isinstance(x, Wire) and x.id not in new and x.touches(q, TOL)
                   for x in sheet.query(box))
    for w in old:
        for e in sheet.query(w.bbox()):
            if not isinstance(e, Insert):
                continue
            for _n, q in e.pin_points():
                if not w.touches(q, TOL):
                    continue
                if e.id in moved:
                    q = (q[0] + d[0], q[1] + d[1])      # (where that pin goes)
                if not wired_after(q):
                    return True
    return False


def _others_pins_on(sheet, w, inside):
    """Is a pin of a symbol not moving (not in inside) on wire w, anywhere along it?"""
    for x in sheet.query(w.bbox()):
        if isinstance(x, Insert) and x.id not in inside:
            if any(w.touches(q, TOL) for _n, q in x.pin_points()):
                return True
    return False


def _runs_along(x, q, dx, dy):
    """Does wire x run the way of the move where q is on it?"""
    for a, b in zip(x.points, x.points[1:]):
        lo_x, hi_x = sorted((a[0], b[0]))
        lo_y, hi_y = sorted((a[1], b[1]))
        if lo_x - TOL <= q[0] <= hi_x + TOL and lo_y - TOL <= q[1] <= hi_y + TOL:
            if (abs(a[1] - b[1]) <= TOL and abs(dy) <= TOL) or \
                    (abs(a[0] - b[0]) <= TOL and abs(dx) <= TOL):
                return True
    return False
