"""Intersections between entities, and Trim (AutoCAD's quick mode: every other object is a
cutting edge; the part of the picked object between the nearest crossings on either side of
the pick is removed; an object nothing crosses is deleted)."""

import math

from . import geometry as G
from .model import Line, Polyline, Circle, Arc

EPS = 1e-7


def _on_arc(p, piece):
    _k, c, _r, s, e = piece
    return G.angle_on_arc(G.angle_of(c, p), s, e)


def intersect(pa, pb):
    """Points where two pieces (see Entity.pieces) meet."""
    ka, kb = pa[0], pb[0]
    if ka == "seg" and kb == "seg":
        return G.segment_intersections(pa[1], pa[2], pb[1], pb[2])
    if ka != "seg" and kb == "seg":
        return intersect(pb, pa)
    if ka == "seg":
        pts = G.line_circle_intersections(pa[1], pa[2], pb[1], pb[2])
        return [p for p in pts if kb == "circle" or _on_arc(p, pb)]
    pts = G.circle_circle_intersections(pa[1], pa[2], pb[1], pb[2])
    return [p for p in pts if (ka == "circle" or _on_arc(p, pa))
            and (kb == "circle" or _on_arc(p, pb))]


def entity_intersections(a, b):
    out = []
    for pa in a.pieces():
        for pb in b.pieces():
            out.extend(intersect(pa, pb))
    return out


# ---- parameter along an entity -------------------------------------------------------------
def _poly_cum(points, closed):
    pts = list(points) + ([points[0]] if closed else [])
    cum = [0.0]
    for i in range(len(pts) - 1):
        cum.append(cum[-1] + G.dist(pts[i], pts[i + 1]))
    return pts, cum


def _poly_param(pts, cum, p):
    """Distance along the polyline of its point nearest to p."""
    best, bs = None, 0.0
    for i in range(len(pts) - 1):
        q, t = G.closest_on_segment(p, pts[i], pts[i + 1])
        d = G.dist(p, q)
        if best is None or d < best:
            best, bs = d, cum[i] + t * (cum[i + 1] - cum[i])
    return bs


def _poly_piece(pts, cum, s0, s1):
    """The polyline's points from distance s0 to s1 (s0 < s1)."""
    def at(s):
        for i in range(len(pts) - 1):
            if s <= cum[i + 1] + 1e-12 or i == len(pts) - 2:
                seg = cum[i + 1] - cum[i]
                t = 0.0 if seg < 1e-12 else (s - cum[i]) / seg
                return (pts[i][0] + t * (pts[i + 1][0] - pts[i][0]),
                        pts[i][1] + t * (pts[i + 1][1] - pts[i][1]))
        return pts[-1]
    out = [at(s0)]
    for i in range(1, len(pts) - 1):
        if s0 + 1e-9 < cum[i] < s1 - 1e-9:
            out.append(pts[i])
    out.append(at(s1))
    return out


def trim(ent, click, cutters):
    """What replaces ent when it is trimmed at the point click: a list of new entities (empty:
    the object goes). cutters: the other entities that may cross it. None when the pick
    doesn't remove anything (it can't happen today: kept for the caller's clarity)."""
    crossings = []
    for c in cutters:
        if c.id == ent.id:
            continue
        crossings.extend(entity_intersections(ent, c))
    keep = dict(layer=ent.layer, color=ent.color)

    if isinstance(ent, Line):
        L = ent.length()
        if L < EPS:
            return []
        ts = sorted({round(G.closest_on_segment(p, ent.p1, ent.p2)[1], 12) for p in crossings})
        t0 = G.closest_on_segment(click, ent.p1, ent.p2)[1]
        lo = max([t for t in ts if t < t0 - EPS / L], default=None)
        hi = min([t for t in ts if t > t0 + EPS / L], default=None)
        out = []

        def pt(t):
            return (ent.p1[0] + t * (ent.p2[0] - ent.p1[0]), ent.p1[1] + t * (ent.p2[1] - ent.p1[1]))
        if lo is not None and lo * L > EPS:
            out.append(Line(ent.p1, pt(lo), **keep))
        if hi is not None and (1 - hi) * L > EPS:
            out.append(Line(pt(hi), ent.p2, **keep))
        return out

    if isinstance(ent, Polyline):
        pts, cum = _poly_cum(ent.points, ent.closed)
        total = cum[-1]
        if total < EPS:
            return []
        ss = sorted({round(_poly_param(pts, cum, p), 10) for p in crossings})
        s0 = _poly_param(pts, cum, click)
        if not ent.closed:
            lo = max([s for s in ss if s < s0 - EPS], default=None)
            hi = min([s for s in ss if s > s0 + EPS], default=None)
            out = []
            if lo is not None and lo > EPS:
                out.append(_mk_poly(_poly_piece(pts, cum, 0.0, lo), keep))
            if hi is not None and total - hi > EPS:
                out.append(_mk_poly(_poly_piece(pts, cum, hi, total), keep))
            return out
        ss = [s for s in ss if s < total - EPS] or ss
        ss = sorted({0.0 if abs(s - total) < EPS else s for s in ss})
        if len(ss) < 2:
            return []
        lo = max([s for s in ss if s < s0 - EPS], default=ss[-1])
        hi = min([s for s in ss if s > s0 + EPS], default=ss[0])
        # keep from hi around to lo (it may pass the start)
        if hi < lo:
            piece = _poly_piece(pts, cum, hi, lo)
        else:
            a = _poly_piece(pts, cum, hi, total)
            b = _poly_piece(pts, cum, 0.0, lo)
            piece = a + b[1:]
        return [_mk_poly(piece, keep)]

    if isinstance(ent, Circle):
        angs = sorted({round(G.angle_of(ent.center, p), 9) % 360.0 for p in crossings})
        if len(angs) < 2:
            return []
        a0 = G.angle_of(ent.center, click)
        # the crossings before and after the pick, going counterclockwise
        after = min(angs, key=lambda a: (a - a0) % 360.0)
        before = min(angs, key=lambda a: (a0 - a) % 360.0)
        return [Arc(ent.center, ent.radius, after, before, **keep)]

    if isinstance(ent, Arc):
        sw = G.sweep(ent.start, ent.end)
        rel = sorted({round((G.angle_of(ent.center, p) - ent.start) % 360.0, 9)
                      for p in crossings})
        rel = [r for r in rel if r <= sw + 1e-7]
        r0 = (G.angle_of(ent.center, click) - ent.start) % 360.0
        if r0 > sw:     # picked past an end: nearest end
            r0 = sw if (r0 - sw) < (360.0 - r0) else 0.0
        tol = math.degrees(EPS / max(ent.radius, EPS))
        lo = max([r for r in rel if r < r0 - tol], default=None)
        hi = min([r for r in rel if r > r0 + tol], default=None)
        out = []
        if lo is not None and lo > tol:
            out.append(Arc(ent.center, ent.radius, ent.start, ent.start + lo, **keep))
        if hi is not None and sw - hi > tol:
            out.append(Arc(ent.center, ent.radius, ent.start + hi, ent.end, **keep))
        return out

    return None


def _mk_poly(points, keep):
    if len(points) == 2:
        return Line(points[0], points[1], **keep)
    return Polyline(points, False, **keep)
