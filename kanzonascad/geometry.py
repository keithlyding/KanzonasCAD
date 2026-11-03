"""Plane geometry used by the drawing model, snapping and Trim.

Drawing units are inches; y points up (as in AutoCAD), angles are in degrees counterclockwise
from the +x axis. Pure Python, no Qt, so tests and file conversion can use it on their own.
"""

import math

EPS = 1e-9


def dist(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def angle_of(a, b):
    """Angle of the direction a -> b, degrees in [0, 360)."""
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 360.0


def polar(p, length, angle_deg):
    a = math.radians(angle_deg)
    return (p[0] + length * math.cos(a), p[1] + length * math.sin(a))


def rotate_point(p, center, angle_deg):
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    x, y = p[0] - center[0], p[1] - center[1]
    return (center[0] + x * c - y * s, center[1] + x * s + y * c)


def scale_point(p, base, factor):
    return (base[0] + (p[0] - base[0]) * factor, base[1] + (p[1] - base[1]) * factor)


def mirror_point(p, a, b):
    """p reflected across the line through a and b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    d2 = dx * dx + dy * dy
    if d2 < EPS:
        return p
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / d2
    fx, fy = a[0] + t * dx, a[1] + t * dy
    return (2 * fx - p[0], 2 * fy - p[1])


def mirror_angle(angle_deg, a, b):
    """Direction angle after mirroring across the line a-b."""
    axis = angle_of(a, b)
    return (2 * axis - angle_deg) % 360.0


def norm_angle(a):
    return a % 360.0


def sweep(start, end):
    """Counterclockwise sweep from start to end, in (0, 360]."""
    s = (end - start) % 360.0
    return 360.0 if s < EPS else s


def angle_on_arc(a, start, end, eps=1e-7):
    """Is direction a within the counterclockwise arc start -> end?"""
    return (a - start) % 360.0 <= sweep(start, end) + eps


def closest_on_segment(p, a, b):
    """(point, t) of the point of segment a-b nearest to p (t in [0, 1])."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    d2 = dx * dx + dy * dy
    if d2 < EPS:
        return a, 0.0
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / d2
    t = max(0.0, min(1.0, t))
    return (a[0] + t * dx, a[1] + t * dy), t


def dist_to_segment(p, a, b):
    q, _t = closest_on_segment(p, a, b)
    return dist(p, q)


def segment_intersections(a, b, c, d):
    """Points where segments a-b and c-d cross (empty when parallel)."""
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < EPS:
        return []
    qp = (c[0] - a[0], c[1] - a[1])
    t = (qp[0] * s[1] - qp[1] * s[0]) / den
    u = (qp[0] * r[1] - qp[1] * r[0]) / den
    if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
        return [(a[0] + t * r[0], a[1] + t * r[1])]
    return []


def line_circle_intersections(a, b, center, radius, segment=True):
    """Points where the segment (or infinite line) a-b meets the circle."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    fx, fy = a[0] - center[0], a[1] - center[1]
    A = dx * dx + dy * dy
    if A < EPS:
        return []
    B = 2 * (fx * dx + fy * dy)
    C = fx * fx + fy * fy - radius * radius
    disc = B * B - 4 * A * C
    if disc < -1e-12:
        return []
    disc = math.sqrt(max(0.0, disc))
    out = []
    for t in sorted({(-B - disc) / (2 * A), (-B + disc) / (2 * A)}):
        if not segment or -1e-9 <= t <= 1 + 1e-9:
            out.append((a[0] + t * dx, a[1] + t * dy))
    return out


def circle_circle_intersections(c1, r1, c2, r2):
    d = dist(c1, c2)
    if d < EPS or d > r1 + r2 + 1e-9 or d < abs(r1 - r2) - 1e-9:
        return []
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, r1 * r1 - a * a))
    mx = c1[0] + a * (c2[0] - c1[0]) / d
    my = c1[1] + a * (c2[1] - c1[1]) / d
    ox, oy = h * (c2[1] - c1[1]) / d, -h * (c2[0] - c1[0]) / d
    if h < 1e-9:
        return [(mx, my)]
    return [(mx + ox, my + oy), (mx - ox, my - oy)]


def circle_from_3_points(p1, p2, p3):
    """(center, radius) of the circle through three points, or None when they are in line."""
    ax, ay = p1
    bx, by = p2
    cx, cy = p3
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < EPS:
        return None
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay)
          + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx)
          + (cx * cx + cy * cy) * (bx - ax)) / d
    return (ux, uy), dist((ux, uy), p1)


def arc_from_3_points(p1, p2, p3):
    """(center, radius, start angle, end angle) of the arc from p1 through p2 to p3, drawn
    counterclockwise from start to end (as DXF stores arcs), or None when in line."""
    c = circle_from_3_points(p1, p2, p3)
    if c is None:
        return None
    center, r = c
    a1, a2, a3 = angle_of(center, p1), angle_of(center, p2), angle_of(center, p3)
    if angle_on_arc(a2, a1, a3):
        return center, r, a1, a3
    return center, r, a3, a1


def arc_points(center, radius, start, end, max_step_deg=5.0):
    """Points along a counterclockwise arc (for drawing, hit tests and export)."""
    sw = sweep(start, end)
    n = max(2, int(math.ceil(sw / max_step_deg)) + 1)
    return [polar(center, radius, start + sw * i / (n - 1)) for i in range(n)]


def bbox_of(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def bbox_union(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def bbox_inside(inner, outer):
    return (inner[0] >= outer[0] - EPS and inner[1] >= outer[1] - EPS
            and inner[2] <= outer[2] + EPS and inner[3] <= outer[3] + EPS)


def bbox_overlaps(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def segment_hits_rect(a, b, rect):
    """Does segment a-b touch the rectangle (x0, y0, x1, y1)?"""
    x0, y0, x1, y1 = rect
    if x0 <= a[0] <= x1 and y0 <= a[1] <= y1:
        return True
    if x0 <= b[0] <= x1 and y0 <= b[1] <= y1:
        return True
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for i in range(4):
        if segment_intersections(a, b, corners[i], corners[(i + 1) % 4]):
            return True
    return False


def polyline_hits_rect(points, rect, closed=False):
    pts = list(points) + ([points[0]] if closed and points else [])
    return any(segment_hits_rect(pts[i], pts[i + 1], rect) for i in range(len(pts) - 1))


def point_in_polygon(p, poly):
    """Is p inside the closed polygon (a list of points)? Even-odd rule."""
    x, y = p
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            xc = xi + (y - yi) * (xj - xi) / (yj - yi)
            if x < xc:
                inside = not inside
        j = i
    return inside


def polyline_crosses_polygon(points, poly):
    """Does the open polyline cross an edge of the closed polygon?"""
    n = len(poly)
    edges = [(poly[i], poly[(i + 1) % n]) for i in range(n)]
    for k in range(len(points) - 1):
        a, b = points[k], points[k + 1]
        bx0, by0 = min(a[0], b[0]), min(a[1], b[1])
        bx1, by1 = max(a[0], b[0]), max(a[1], b[1])
        for c, d in edges:
            if max(c[0], d[0]) < bx0 or min(c[0], d[0]) > bx1 or \
                    max(c[1], d[1]) < by0 or min(c[1], d[1]) > by1:
                continue
            if segment_intersections(a, b, c, d):
                return True
    return False


def outline_in_polygon(outline, poly):
    """Every part of the outline (a list of polylines) wholly inside the polygon?"""
    for pts in outline:
        if not all(point_in_polygon(q, poly) for q in pts):
            return False
        if polyline_crosses_polygon(pts, poly):
            return False
    return True


def outline_touches_polygon(outline, poly):
    """Any part of the outline inside the polygon or crossing its edge?"""
    for pts in outline:
        if any(point_in_polygon(q, poly) for q in pts):
            return True
        if polyline_crosses_polygon(pts, poly):
            return True
    return False


def tangent_circles(a, b, r):
    """Centers of the circles of radius r tangent to both a and b. a, b: ("line", p, q) (the
    infinite line through p and q) or ("circle", center, radius)."""
    def offsets(s):
        if s[0] == "line":
            p, q = s[1], s[2]
            L = dist(p, q)
            if L < EPS:
                return []
            nx, ny = -(q[1] - p[1]) / L, (q[0] - p[0]) / L
            return [("line", (p[0] + k * nx * r, p[1] + k * ny * r),
                     (q[0] + k * nx * r, q[1] + k * ny * r)) for k in (1, -1)]
        c, R = s[1], s[2]
        out = [("circle", c, R + r)]
        if abs(R - r) > EPS:
            out.append(("circle", c, abs(R - r)))
        return out

    def meet(u, v):
        if u[0] == "line" and v[0] == "line":
            p1, p2, p3, p4 = u[1], u[2], v[1], v[2]
            d = (p1[0] - p2[0]) * (p3[1] - p4[1]) - (p1[1] - p2[1]) * (p3[0] - p4[0])
            if abs(d) < EPS:
                return []
            t = ((p1[0] - p3[0]) * (p3[1] - p4[1]) - (p1[1] - p3[1]) * (p3[0] - p4[0])) / d
            return [(p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))]
        if u[0] == "circle" and v[0] == "line":
            u, v = v, u
        if u[0] == "line":
            return line_circle_intersections(u[1], u[2], v[1], v[2], segment=False)
        return circle_circle_intersections(u[1], u[2], v[1], v[2])

    out = []
    for u in offsets(a):
        for v in offsets(b):
            for c in meet(u, v):
                if not any(dist(c, o) < 1e-7 for o in out):
                    out.append(c)
    return out


def tangent_point(shape, center):
    """Where a circle centered at center touches the shape."""
    if shape[0] == "line":
        p, q = shape[1], shape[2]
        dx, dy = q[0] - p[0], q[1] - p[1]
        d2 = dx * dx + dy * dy
        t = ((center[0] - p[0]) * dx + (center[1] - p[1]) * dy) / d2
        return (p[0] + t * dx, p[1] + t * dy)
    c, R = shape[1], shape[2]
    d = dist(c, center)
    if d < EPS:
        return (c[0] + R, c[1])
    return (c[0] + (center[0] - c[0]) * R / d, c[1] + (center[1] - c[1]) * R / d)
