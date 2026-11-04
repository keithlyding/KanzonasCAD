"""Where wires cross without connecting, and how that is drawn (no Qt).

Two wires cross where a piece of one passes through the middle of a piece of the other
(neither wire ends there: an end on another wire is a connection, with its dot). The
project setting "wire_crossing" says how a crossing is drawn:
- "plain": the wires just cross (US practice: a dot means connected, none means not);
- "gap": the jumping wire is broken briefly where it crosses;
- "loop": the jumping wire hops over the other in a small half circle.
"wire_jump" says which wire jumps: "vertical" (to start, as AutoCAD Electrical) or
"horizontal"; for slanted pieces, the steeper (or flatter) one.

Marks placed by hand (model.WireCross, command Wire crossing) override what is worked out:
a mark on a crossing gives it its own style ("none" hides it); a mark anywhere else on a wire
makes that wire jump there (over a symbol's line, say, or a crossing that wasn't found).

The jumps are worked out per sheet version (never stored), so they follow wires as they move.
"""

import math

from .model import Wire, WireCross

TOL = 1e-6
SIZE = 0.0625               # half the jump's length, paper inches (1/8" wide on paper)


def style(project):
    s = project.settings.get("wire_crossing", "plain")
    return s if s in ("plain", "gap", "loop") else "plain"


def _segments(w):
    return list(zip(w.points, w.points[1:]))


def _hit(a, b, c, d):
    """The point where segment ab crosses segment cd strictly inside both, or None."""
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < 1e-12:
        return None                     # (parallel: no single crossing point)
    t = ((c[0] - a[0]) * s[1] - (c[1] - a[1]) * s[0]) / den
    u = ((c[0] - a[0]) * r[1] - (c[1] - a[1]) * r[0]) / den
    La, Lc = math.hypot(*r), math.hypot(*s)
    if La < TOL or Lc < TOL:
        return None
    ea, ec = TOL / La, TOL / Lc
    if ea < t < 1 - ea and ec < u < 1 - ec:
        return (a[0] + r[0] * t, a[1] + r[1] * t)
    return None


def _is_end(w, p):
    return any(abs(p[0] - q[0]) <= TOL and abs(p[1] - q[1]) <= TOL
               for q in (w.points[0], w.points[-1]))


def _steep(seg):
    (a, b) = seg
    return abs(b[1] - a[1]) - abs(b[0] - a[0])      # > 0: more up and down than across


def found(sheet, jump="vertical"):
    """[(point, jumping segment, crossed segment)] of the wires crossing on a sheet (kept per
    sheet version)."""
    key = (sheet.version, jump)
    got = getattr(sheet, "_crossings", None)
    if got is not None and got[0] == key:
        return got[1]
    out = []
    for w in sheet.wires():
        for seg in _segments(w):
            (a, b) = seg
            rect = (min(a[0], b[0]) - TOL, min(a[1], b[1]) - TOL,
                    max(a[0], b[0]) + TOL, max(a[1], b[1]) + TOL)
            for o in sheet.query(rect):
                # (each pair once: the lower id finds it)
                if not isinstance(o, Wire) or o.id <= w.id:
                    continue
                for oseg in _segments(o):
                    p = _hit(a, b, oseg[0], oseg[1])
                    if p is None or _is_end(w, p) or _is_end(o, p):
                        continue
                    first_jumps = _steep(seg) >= _steep(oseg)
                    if jump == "horizontal":
                        first_jumps = not first_jumps
                    out.append((p, seg, oseg) if first_jumps else (p, oseg, seg))
    sheet._crossings = (key, out)
    return out


def _wire_segment_at(sheet, p):
    """The wire piece passing through p, the steepest one when several do, or None."""
    best = None
    for o in sheet.query((p[0] - TOL, p[1] - TOL, p[0] + TOL, p[1] + TOL)):
        if not isinstance(o, Wire):
            continue
        for seg in _segments(o):
            if _dist_seg(p, seg) <= 1e-4 and (best is None or _steep(seg) > _steep(best)):
                best = seg
    return best


def _dist_seg(p, seg):
    (a, b) = seg
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    if L2 < 1e-24:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - a[0] - dx * t, p[1] - a[1] - dy * t)


def jumps(project, sheet):
    """[(point, direction (unit vector of the jumping wire), crossed direction or None,
    style "gap" | "loop")] to draw on a sheet: the crossings found in the project's style, then
    the marks placed by hand."""
    st = style(project)
    jump = project.settings.get("wire_jump", "vertical")
    key = (sheet.version, st, jump)
    got = getattr(sheet, "_jumps", None)
    if got is not None and got[0] == key:
        return got[1]                   # (worked out once per sheet change, not per paint)
    marks = [e for e in sheet.entities.values() if isinstance(e, WireCross)]
    out = []
    used = set()
    for p, seg, oseg in (found(sheet, jump) if (st != "plain" or marks) else []):
        mine = next((m for m in marks if math.hypot(m.pos[0] - p[0], m.pos[1] - p[1]) < 0.02),
                    None)
        s_ = mine.style if mine is not None else st
        if mine is not None:
            used.add(mine.id)
        if s_ in ("gap", "loop"):
            out.append((p, _unit(seg), _unit(oseg), s_))
    for m in marks:
        if m.id in used or m.style not in ("gap", "loop"):
            continue
        seg = _wire_segment_at(sheet, m.pos)
        if seg is not None:
            out.append((m.pos, _unit(seg), None, m.style))
    sheet._jumps = (key, out)
    return out


def _unit(seg):
    (a, b) = seg
    L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
    u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    # (pointing right, or up: so a loop always bulges the same way)
    if u[0] < -1e-9 or (abs(u[0]) <= 1e-9 and u[1] < 0):
        u = (-u[0], -u[1])
    return u


def loop_points(p, u, r, steps=12):
    """The half circle a jumping wire takes over p: from p - u*r to p + u*r, bulging to the
    left of u (up for an across wire, left for an up-and-down one)."""
    n = (-u[1], u[0])
    out = []
    for i in range(steps + 1):
        a = math.pi * (1 - i / steps)
        out.append((p[0] + u[0] * r * math.cos(a) + n[0] * r * math.sin(a),
                    p[1] + u[1] * r * math.cos(a) + n[1] * r * math.sin(a)))
    return out


def size(sheet):
    """Half a jump's length in drawing units (paper-sized: 1/16 inch on paper)."""
    return SIZE * sheet.k()


def cut_wire(w, jumps_, r):
    """A wire's points as the pieces left once its jumps are cut out (DXF export draws the
    gaps and loops as real gaps and arcs): [[points]]."""
    cuts = []                                   # (segment index, distance along it)
    for i, (a, b) in enumerate(_segments(w)):
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < TOL:
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        for p, u, _cu, _st in jumps_:
            if _dist_seg(p, (a, b)) > 1e-4 or abs(ux * u[1] - uy * u[0]) > 1e-6:
                continue
            t = (p[0] - a[0]) * ux + (p[1] - a[1]) * uy
            cuts.append((i, max(0.0, t - r), min(L, t + r)))
    if not cuts:
        return [list(w.points)]
    pieces, cur = [], [w.points[0]]
    for i, (a, b) in enumerate(_segments(w)):
        L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        for _i, t0, t1 in sorted(c for c in cuts if c[0] == i):
            cur.append((a[0] + ux * t0, a[1] + uy * t0))
            if len(cur) > 1:
                pieces.append(cur)
            cur = [(a[0] + ux * t1, a[1] + uy * t1)]
        cur.append(b)
    if len(cur) > 1:
        pieces.append(cur)
    return pieces


def place_at(project, sheet, p, tol):
    """Where a mark clicked at p goes: the crossing within tol (exactly on it), else the
    nearest point on a wire within tol, else None."""
    jump = project.settings.get("wire_jump", "vertical")
    best = None
    for q, _s, _o in found(sheet, jump):
        d = math.hypot(q[0] - p[0], q[1] - p[1])
        if d <= tol and (best is None or d < best[0]):
            best = (d, q)
    if best is not None:
        return best[1]
    for o in sheet.query((p[0] - tol, p[1] - tol, p[0] + tol, p[1] + tol)):
        if not isinstance(o, Wire):
            continue
        for (a, b) in _segments(o):
            dx, dy = b[0] - a[0], b[1] - a[1]
            L2 = dx * dx + dy * dy
            if L2 < 1e-24:
                continue
            t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
            q = (a[0] + dx * t, a[1] + dy * t)
            d = math.hypot(q[0] - p[0], q[1] - p[1])
            if d <= tol and (best is None or d < best[0]):
                best = (d, q)
    return best[1] if best else None
