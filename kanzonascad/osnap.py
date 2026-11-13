"""Object snaps, as AutoCAD's (no Qt): which ones there are, which are on to start, and the
ones worked out from the cursor rather than stored on objects (perpendicular, tangent,
nearest).

Running snaps are the ones ticked in Drafting settings (F3 turns them all off and on). A snap
typed at a point prompt (END, PER, TAN, NEA... or NON for none) is used for the next point
only, whatever is ticked, as AutoCAD's overrides; Shift + right-click lists them.
"""

import math

from . import geometry as G

# (key, name shown, what AutoCAD types for it)
MODES = [
    ("end", "Endpoint", "END"),
    ("mid", "Midpoint", "MID"),
    ("center", "Center", "CEN"),
    ("gcen", "Geometric center", "GCE"),
    ("node", "Node", "NOD"),
    ("quad", "Quadrant", "QUA"),
    ("int", "Intersection", "INT"),
    ("insert", "Insertion", "INS"),
    ("perp", "Perpendicular", "PER"),
    ("tan", "Tangent", "TAN"),
    ("near", "Nearest", "NEA"),
    ("ext", "Extension", "EXT"),
    ("app", "Apparent intersection", "APP"),
    ("par", "Parallel", "PAR"),
]
NAMES = {k: n for k, n, _t in MODES}
TYPED = {t: k for k, _n, t in MODES}
TYPED.update({"ENDP": "end", "ENDPOINT": "end", "MIDPOINT": "mid", "CENTER": "center",
              "NODE": "node", "QUAD": "quad", "QUADRANT": "quad", "INTERSECTION": "int",
              "INSERT": "insert", "PERP": "perp", "TANGENT": "tan", "NEAR": "near",
              "NEAREST": "near", "GCEN": "gcen", "NON": "none", "NONE": "none",
              "EXTENSION": "ext", "APPINT": "app", "PARALLEL": "par"})
# on to start: the ones KanzonasCAD always had, and Node (symbol pins)
DEFAULT = {"end", "mid", "center", "node", "quad", "int", "insert"}
# when several are in reach, the first of these wins (then the nearest)
PRIORITY = {"end": 0, "int": 0, "insert": 0, "node": 0, "center": 1, "quad": 1, "gcen": 1,
            "perp": 1, "tan": 1, "app": 1, "mid": 2, "ext": 3, "par": 3, "near": 4}


def _segments_and_curves(e):
    """An object's pieces (segments, arcs, circles), a block's placed ones included."""
    sub = getattr(e, "world_entities", None) or getattr(e, "parts", None)
    if sub is not None and e.kind in ("insert", "dimension", "rail", "duct"):
        out = []
        for w in sub():
            if w.kind != "text":
                out.extend(_segments_and_curves(w))
        return out
    try:
        return e.pieces()
    except NotImplementedError:
        return []


def nearest(e, p):
    """The point of e nearest p, or None."""
    best = None
    for piece in _segments_and_curves(e):
        q = _nearest_on(piece, p)
        if q is not None:
            d = G.dist(p, q)
            if best is None or d < best[0]:
                best = (d, q)
    return best[1] if best else None


def _nearest_on(piece, p):
    kind = piece[0]
    if kind == "seg":
        _k, a, b = piece
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        if L2 < 1e-24:
            return a
        t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
        return (a[0] + dx * t, a[1] + dy * t)
    if kind == "circle":
        _k, c, r = piece
        return _on_circle(c, r, p)
    if kind == "arc":
        _k, c, r, s, e_ = piece
        q = _on_circle(c, r, p)
        if q is not None and _on_arc(c, s, e_, q):
            return q
        ends = [G.polar(c, r, s), G.polar(c, r, e_)]
        return min(ends, key=lambda x: G.dist(p, x))
    return None


def _on_circle(c, r, p):
    d = G.dist(c, p)
    if d < 1e-12:
        return (c[0] + r, c[1])
    return (c[0] + (p[0] - c[0]) * r / d, c[1] + (p[1] - c[1]) * r / d)


def _on_arc(c, s, e, q):
    a = G.angle_of(c, q)
    sweep = (e - s) % 360.0
    return (a - s) % 360.0 <= sweep + 1e-9


def perpendicular(e, base, p):
    """Points of e where a line from base meets it at a right angle, nearest the cursor p
    first (lines: the foot on the line itself; circles and arcs: on the line through the
    center)."""
    out = []
    for piece in _segments_and_curves(e):
        kind = piece[0]
        if kind == "seg":
            _k, a, b = piece
            dx, dy = b[0] - a[0], b[1] - a[1]
            L2 = dx * dx + dy * dy
            if L2 < 1e-24:
                continue
            t = ((base[0] - a[0]) * dx + (base[1] - a[1]) * dy) / L2
            if -1e-9 <= t <= 1 + 1e-9:
                out.append((a[0] + dx * t, a[1] + dy * t))
        elif kind in ("circle", "arc"):
            c, r = piece[1], piece[2]
            d = G.dist(c, base)
            if d < 1e-12:
                continue
            for sgn in (1, -1):
                q = (c[0] + (base[0] - c[0]) * r / d * sgn, c[1] + (base[1] - c[1]) * r / d * sgn)
                if kind == "circle" or _on_arc(c, piece[3], piece[4], q):
                    out.append(q)
    return sorted(out, key=lambda q: G.dist(q, p))


def tangent(e, base, p):
    """Points of e's circles and arcs where a line from base touches them, nearest p first."""
    out = []
    for piece in _segments_and_curves(e):
        if piece[0] not in ("circle", "arc"):
            continue
        c, r = piece[1], piece[2]
        d = G.dist(c, base)
        if d <= r + 1e-9:
            continue                    # (base inside: no tangent)
        a0 = G.angle_of(c, base)
        da = math.degrees(math.acos(r / d))
        for a in (a0 + da, a0 - da):
            q = G.polar(c, r, a)
            if piece[0] == "circle" or _on_arc(c, piece[3], piece[4], q):
                out.append(q)
    return sorted(out, key=lambda q: G.dist(q, p))


def centroid(points):
    """The geometric center of a closed outline (its area's center), or None. Worked out
    from its first point (found by the battery's drawing-slop check: from the origin, the
    products of coordinates thousands of inches out swamped a small shape's area, and the GCE
    snap of a half-inch square 5,000" out landed 0.000024" off its center)."""
    n = len(points)
    if n < 3:
        return None
    ox, oy = points[0]
    a = cx = cy = 0.0
    for i in range(n):
        x0, y0 = points[i][0] - ox, points[i][1] - oy
        x1, y1 = points[(i + 1) % n][0] - ox, points[(i + 1) % n][1] - oy
        cr = x0 * y1 - x1 * y0
        a += cr
        cx += (x0 + x1) * cr
        cy += (y0 + y1) * cr
    if abs(a) < 1e-12:
        return None
    return (ox + cx / (3 * a), oy + cy / (3 * a))


# ---- tracking: Extension and Parallel follow lines acquired by hovering (AutoCAD's tracking)
def segments(e):
    """An object's straight pieces, (a, b)."""
    return [(pc[1], pc[2]) for pc in _segments_and_curves(e) if pc[0] == "seg"]


def ends_at(e, q, tol=1e-9):
    """[(end point, outward direction)] of e's straight pieces ending at q: where an
    Extension continues past q."""
    out = []
    for a, b in segments(e):
        for end, other in ((a, b), (b, a)):
            if G.dist(end, q) <= tol:
                L = G.dist(end, other)
                if L > 1e-12:
                    out.append((end, ((end[0] - other[0]) / L, (end[1] - other[1]) / L)))
    return out


def extension(acquired, p, r):
    """[(point, from)] on the extensions past acquired ends [(end, direction)], within r of p."""
    out = []
    for q0, u in acquired:
        t = (p[0] - q0[0]) * u[0] + (p[1] - q0[1]) * u[1]
        if t <= 0:
            continue
        q = (q0[0] + u[0] * t, q0[1] + u[1] * t)
        if G.dist(q, p) <= r:
            out.append((q, q0))
    return out


def parallel(base, dirs, p, r):
    """[point] on a line from base parallel to one of dirs, within r of p (and away from
    base)."""
    out = []
    for u in dirs:
        t = (p[0] - base[0]) * u[0] + (p[1] - base[1]) * u[1]
        q = (base[0] + u[0] * t, base[1] + u[1] * t)
        if abs(t) > r and G.dist(q, p) <= r:
            out.append(q)
    return out


def apparent(segs, p, r):
    """Where two straight pieces would meet if extended (not where they actually cross: that
    is Intersection), within r of p."""
    out = []
    n = len(segs)
    for i in range(n):
        a, b = segs[i]
        for j in range(i + 1, n):
            c, d = segs[j]
            rx, ry = b[0] - a[0], b[1] - a[1]
            sx, sy = d[0] - c[0], d[1] - c[1]
            den = rx * sy - ry * sx
            if abs(den) < 1e-12:
                continue
            t = ((c[0] - a[0]) * sy - (c[1] - a[1]) * sx) / den
            u = ((c[0] - a[0]) * ry - (c[1] - a[1]) * rx) / den
            if 0 <= t <= 1 and 0 <= u <= 1:
                continue
            q = (a[0] + rx * t, a[1] + ry * t)
            if G.dist(q, p) <= r:
                out.append(q)
    return out
