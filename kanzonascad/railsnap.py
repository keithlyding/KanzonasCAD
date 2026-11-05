"""Footprints onto DIN rail (no Qt): while a footprint is placed, moved, copied or dragged,
its rail point (the middle of its rail clip: BlockDef.rail_point) that comes over a DIN rail
locks onto the rail's centerline, the footprint still sliding freely along the rail; and its
end, near the end of a footprint already on that rail, butts against it (as devices sit side
by side on a real rail). The view turns it on with the object snaps (F3)."""

from . import model as M

LIMIT = 50              # footprints of a moved selection looked at (the nearest rail wins)


def is_footprint(e):
    return isinstance(e, M.Insert) and e.defn is not None and e.defn.kind == "footprint"


def rail_point(ins, dx=0.0, dy=0.0):
    """A placed footprint's rail point on the sheet (shifted by dx, dy)."""
    q = ins.to_world(ins.defn.rail_point())
    return (q[0] + dx, q[1] + dy)


def _across(rail, q):
    """(how far along the rail from p1, how far across its centerline) of a point."""
    (ux, uy), (nx, ny) = rail.axes()
    vx, vy = q[0] - rail.p1[0], q[1] - rail.p1[1]
    return vx * ux + vy * uy, vx * nx + vy * ny


def span(ins, rail, dx=0.0, dy=0.0):
    """(from, to) along the rail that a footprint's drawing covers."""
    bb = ins.defn.extents()
    out = []
    for x, y in ((bb[0], bb[1]), (bb[2], bb[1]), (bb[2], bb[3]), (bb[0], bb[3])):
        q = ins.to_world((x, y))
        out.append(_across(rail, (q[0] + dx, q[1] + dy))[0])
    return min(out), max(out)


def on_rail(sheet, ins, tol=1e-6):
    """The DIN rail a placed footprint sits on (its rail point on the centerline), or None."""
    q = rail_point(ins)
    for e in sheet.query((q[0] - tol, q[1] - tol, q[0] + tol, q[1] + tol)):
        if isinstance(e, M.Rail):
            s, t = _across(e, q)
            if -tol <= s <= e.length() + tol and abs(t) <= tol:
                return e
    return None


def magnet(sheet, moving, dx, dy, tol, copy=False):
    """Where moving objects go when shifted by (dx, dy) with the rail magnet: (dx, dy, hit);
    hit is None (no footprint over a rail: dx, dy as given) or {"rail", "point" (the rail
    point, on the centerline), "butted" (True: against a neighbor)}. tol: how near counts
    (about ten pixels, in drawing units). copy: the objects themselves stay (Copy, a
    Ctrl+drag), so they are neighbors to butt against too."""
    if not moving or any(isinstance(e, M.Run) for e in moving):
        return dx, dy, None             # (a rail moved with what is on it: they go together)
    fps = [e for e in moving if is_footprint(e)][:LIMIT]
    if not fps:
        return dx, dy, None
    ids = {e.id for e in moving if e.id is not None}
    stay = set() if copy else ids
    best = None
    for f in fps:
        q = rail_point(f, dx, dy)
        for e in sheet.query((q[0] - tol, q[1] - tol, q[0] + tol, q[1] + tol)):
            if not isinstance(e, M.Rail) or e.id in ids:
                continue
            s, t = _across(e, q)
            if s < -tol or s > e.length() + tol or abs(t) > e.width / 2 + tol:
                continue
            if best is None or abs(t) < best[0]:
                best = (abs(t), f, e, t)
    if best is None:
        return dx, dy, None
    _d, f, rail, t = best
    (ux, uy), (nx, ny) = rail.axes()
    dx, dy = dx - nx * t, dy - ny * t
    # butted against a neighbor on the same rail whose end is near
    a0, a1 = span(f, rail, dx, dy)
    x0, y0, x1, y1 = rail.bbox()
    shift = None
    for g in sheet.query((x0 - tol, y0 - tol, x1 + tol, y1 + tol)):
        if g.id in stay or not is_footprint(g):
            continue
        s, t2 = _across(rail, rail_point(g))
        if abs(t2) > rail.width / 2 or s < -tol or s > rail.length() + tol:
            continue                    # (not on this rail)
        b0, b1 = span(g, rail)
        for k in (b1 - a0, b0 - a1):
            if abs(k) <= tol and (shift is None or abs(k) < abs(shift)):
                shift = k
    if shift is not None:
        dx, dy = dx + ux * shift, dy + uy * shift
    return dx, dy, {"rail": rail, "point": rail_point(f, dx, dy), "butted": shift is not None}
