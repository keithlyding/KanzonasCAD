"""The drawing model: a project of sheets, each sheet a set of entities on layers.

No Qt here: the model can be loaded, edited, checked and exported in tests and the self-test
without a window.

Entities are treated as values: a change replaces the entity with a changed copy (same id)
through an Edit, which records before/after for Undo. Anything cached on an entity object
(its bounding box, snap points) therefore never goes stale.
"""

import json
import math
import os
import string

from . import geometry as G

FORMAT = "kanzonascad"
FORMAT_VERSION = 1
FILE_SUFFIX = ".kzcad"

# ANSI sheet sizes, inches (landscape)
SHEET_SIZES = {
    "ANSI A (11 x 8.5)": (11.0, 8.5),
    "ANSI B (17 x 11)": (17.0, 11.0),
    "ANSI C (22 x 17)": (22.0, 17.0),
    "ANSI D (34 x 22)": (34.0, 22.0),
}
DEFAULT_SIZE = "ANSI B (17 x 11)"

# "7" is AutoCAD's color 7: black on a white sheet, white on a dark one
BYLAYER = None
ADAPTIVE = "7"

DEFAULT_LAYERS = [
    ("0", ADAPTIVE),
    ("WIRES", "#ff3030"),
    ("SYMBOLS", ADAPTIVE),
    ("TEXT", ADAPTIVE),
    ("NOTES", "#00a0ff"),
    ("PANEL", ADAPTIVE),
    ("DIMENSIONS", "#00c8c8"),
]

# the project's own settings (Project properties); sheets that follow the project take the
# layout ones (size, zones) from here
DEFAULT_SETTINGS = {
    "text_height": 0.125,       # new text
    "tag_height": 0.1,          # device tags on symbols
    "size": "ANSI B (17 x 11)",
    "cols": 10, "rows": 8, "col_start": 1, "row_start": 0,
    "xref_auto": True,          # cross-references follow every change (else: Update command)
    "xref_height": 0.08,        # cross-reference text
    "wire_numbers": True,       # wires numbered by themselves (wirenums.py)
    "wire_number_height": 0.08,
    "dim_height": 0.1,          # dimension text, paper inches
    "tb_position": "corner",    # the title block: in the lower right corner, or a strip down
                                # the right ("right") or along the bottom ("bottom") that the
                                # zone grid stops at
    "wire_cleanup": True,       # wires cleaned up as they're drawn (wires.tidy_new)
    "wire_crossing": "plain",   # wires crossing: plain, gap or loop (crossings.py)
    "wire_jump": "vertical",    # which one jumps: vertical or horizontal
    "rail_profile": "TS35x7.5",             # DIN rail and wire duct drawn next
    "duct_size": [2.0, 3.0],
    "rail_stock": 1000 / 25.4,              # bought in 1 m lengths
    "duct_stock": 72.0,                     # bought in 6 ft lengths
}
LAYOUT_KEYS = ("size", "cols", "rows", "col_start", "row_start")

# text width per character as a share of the text height, used for hit tests and boxes when
# no font measure is set (the app sets TEXT_MEASURE from the font it draws with)
TEXT_WIDTH_FACTOR = 0.72
TEXT_MEASURE = None


def text_width(text, height):
    if TEXT_MEASURE is not None:
        return TEXT_MEASURE(text, height)
    return len(text) * height * TEXT_WIDTH_FACTOR


def _pt(p):
    return (float(p[0]), float(p[1]))


# ============================================================================================
# Entities
# ============================================================================================
_KINDS = {}


def _register(cls):
    _KINDS[cls.kind] = cls
    return cls


class Entity:
    kind = "entity"
    __slots__ = ("id", "layer", "color", "_bbox", "_snaps")

    def __init__(self, layer="0", color=BYLAYER, id=None):
        self.id = id
        self.layer = layer
        self.color = color
        self._bbox = None
        self._snaps = None

    # ---- storing -------------------------------------------------------------------------
    def to_dict(self):
        d = {"kind": self.kind, "id": self.id, "layer": self.layer}
        if self.color is not None:
            d["color"] = self.color
        d.update(self._data())
        return d

    def _data(self):
        return {}

    @staticmethod
    def from_dict(d, blocks=None):
        """blocks: {name: BlockDef} the block references among them point to."""
        cls = _KINDS.get(d.get("kind"))
        if cls is None:
            raise ValueError("unknown entity kind %r" % d.get("kind"))
        if cls is Insert:
            return cls._from(d, blocks or {})
        return cls._from(d)

    def copy(self, **changes):
        d = self.to_dict()
        d.update(changes)
        return Entity.from_dict(d)

    # ---- shape ---------------------------------------------------------------------------
    def bbox(self):
        if self._bbox is None:
            self._bbox = self._compute_bbox()
        return self._bbox

    def _compute_bbox(self):
        raise NotImplementedError

    def distance(self, p):
        """Distance from p to the entity's outline."""
        raise NotImplementedError

    def inside(self, rect):
        """Wholly inside the window rect (x0, y0, x1, y1)?"""
        return G.bbox_inside(self.bbox(), rect)

    def crosses(self, rect):
        """Touches the crossing window rect?"""
        raise NotImplementedError

    def pieces(self):
        """Primitive pieces for intersections: ("seg", a, b), ("arc", c, r, s, e), ("circle", c, r)."""
        raise NotImplementedError

    def outline(self):
        """The shape as polylines (lists of points; curves as short segments), for lasso
        selection."""
        raise NotImplementedError

    def snap_points(self):
        """[(kind, point)]; kind: end, mid, center, quad, insert."""
        if self._snaps is None:
            self._snaps = self._compute_snaps()
        return self._snaps

    def _compute_snaps(self):
        return []

    def grips(self):
        return []

    def with_grip(self, i, p):
        """A copy with grip i moved to p."""
        return self.moved(p[0] - self.grips()[i][0], p[1] - self.grips()[i][1])

    # ---- transforms (each returns a changed copy) ----------------------------------------
    def moved(self, dx, dy):
        return self._map(lambda q: (q[0] + dx, q[1] + dy), rot=0.0)

    def rotated(self, center, angle):
        return self._map(lambda q: G.rotate_point(q, center, angle), rot=angle)

    def scaled(self, base, factor):
        return self._map(lambda q: G.scale_point(q, base, factor), factor=factor)

    def mirrored(self, a, b):
        return self._map(lambda q: G.mirror_point(q, a, b), mirror=(a, b))

    def _map(self, fn, rot=0.0, factor=1.0, mirror=None):
        raise NotImplementedError


@_register
class Line(Entity):
    kind = "line"
    __slots__ = ("p1", "p2")

    def __init__(self, p1, p2, **kw):
        super().__init__(**kw)
        self.p1, self.p2 = _pt(p1), _pt(p2)

    def _data(self):
        return {"p1": list(self.p1), "p2": list(self.p2)}

    @classmethod
    def _from(cls, d):
        return cls(d["p1"], d["p2"], layer=d.get("layer", "0"), color=d.get("color"),
                   id=d.get("id"))

    def _compute_bbox(self):
        return G.bbox_of([self.p1, self.p2])

    def distance(self, p):
        return G.dist_to_segment(p, self.p1, self.p2)

    def crosses(self, rect):
        return G.segment_hits_rect(self.p1, self.p2, rect)

    def pieces(self):
        return [("seg", self.p1, self.p2)]

    def outline(self):
        return [[self.p1, self.p2]]

    def _compute_snaps(self):
        mid = ((self.p1[0] + self.p2[0]) / 2, (self.p1[1] + self.p2[1]) / 2)
        return [("end", self.p1), ("end", self.p2), ("mid", mid)]

    def grips(self):
        mid = ((self.p1[0] + self.p2[0]) / 2, (self.p1[1] + self.p2[1]) / 2)
        return [self.p1, mid, self.p2]

    def with_grip(self, i, p):
        if i == 0:
            return self.copy(p1=list(p))
        if i == 2:
            return self.copy(p2=list(p))
        return Entity.with_grip(self, i, p)

    def _map(self, fn, **_kw):
        return self.copy(p1=list(fn(self.p1)), p2=list(fn(self.p2)))

    def length(self):
        return G.dist(self.p1, self.p2)


@_register
class Polyline(Entity):
    kind = "polyline"
    __slots__ = ("points", "closed")

    def __init__(self, points, closed=False, **kw):
        super().__init__(**kw)
        self.points = [_pt(p) for p in points]
        self.closed = bool(closed)

    def _data(self):
        return {"points": [list(p) for p in self.points], "closed": self.closed}

    @classmethod
    def _from(cls, d):
        return cls(d["points"], d.get("closed", False), layer=d.get("layer", "0"),
                   color=d.get("color"), id=d.get("id"))

    def segments(self):
        pts = self.points
        segs = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        if self.closed and len(pts) > 2:
            segs.append((pts[-1], pts[0]))
        return segs

    def _compute_bbox(self):
        return G.bbox_of(self.points)

    def distance(self, p):
        segs = self.segments()
        if not segs:
            return G.dist(p, self.points[0])
        return min(G.dist_to_segment(p, a, b) for a, b in segs)

    def crosses(self, rect):
        return G.polyline_hits_rect(self.points, rect, self.closed)

    def pieces(self):
        return [("seg", a, b) for a, b in self.segments()]

    def outline(self):
        pts = list(self.points)
        if self.closed and len(pts) > 2:
            pts.append(pts[0])
        return [pts]

    def _compute_snaps(self):
        out = [("end", p) for p in self.points]
        for a, b in self.segments():
            out.append(("mid", ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)))
        if self.closed and len(self.points) >= 3:
            from .osnap import centroid
            c = centroid(self.points)
            if c is not None:
                out.append(("gcen", c))
        return out

    def grips(self):
        return list(self.points)

    def with_grip(self, i, p):
        pts = [list(q) for q in self.points]
        pts[i] = list(p)
        return self.copy(points=pts)

    def _map(self, fn, **_kw):
        return self.copy(points=[list(fn(p)) for p in self.points])


@_register
class Wire(Polyline):
    """A wire: a polyline on layer WIRES whose ends attach to symbol pins, wire ends or other
    wires. What it connects is worked out from where its ends are (wires.py), never stored, so
    it can't go stale; moving a symbol drags the ends that sat on its pins."""
    kind = "wire"
    __slots__ = ("num", "num_lock")

    def __init__(self, points, closed=False, num=None, num_lock=False, **kw):
        kw.setdefault("layer", "WIRES")
        super().__init__(points, False, **kw)
        # its wire number (every wire of a connected group has the same: wirenums.py) and
        # whether it was typed (locked: numbering leaves it alone)
        self.num = str(num) if num else None
        self.num_lock = bool(num_lock) and bool(num)

    def _data(self):
        d = super()._data()
        if self.num:
            d["num"] = self.num
            if self.num_lock:
                d["num_lock"] = True
        return d

    @classmethod
    def _from(cls, d):
        return cls(d["points"], False, d.get("num"), d.get("num_lock", False),
                   layer=d.get("layer", "WIRES"), color=d.get("color"), id=d.get("id"))

    def touches(self, p, tol=1e-6):
        """Does the wire pass within tol of p (an end, a corner or the middle of a piece)?
        Pieces whose box is far from p are skipped without measuring."""
        x, y = p
        pts = self.points
        for k in range(len(pts) - 1):
            a, b = pts[k], pts[k + 1]
            if x < min(a[0], b[0]) - tol or x > max(a[0], b[0]) + tol or \
                    y < min(a[1], b[1]) - tol or y > max(a[1], b[1]) + tol:
                continue
            if G.dist_to_segment(p, a, b) <= tol:
                return True
        return False

    def end_moved(self, i, p):
        """A copy with end i (0 or -1) at p, kept straight across / up and down: the next
        corner slides along with it, or a jog is added to a two-point wire."""
        pts = [list(q) for q in self.points]
        n = len(pts)
        if n < 2:
            return self.copy(points=[list(p)])      # (no length: nothing to keep straight)
        j = 0 if i == 0 else n - 1
        k = 1 if j == 0 else n - 2
        old = pts[j]
        dx, dy = p[0] - old[0], p[1] - old[1]
        horiz = abs(pts[k][1] - old[1]) < 1e-9
        vert = abs(pts[k][0] - old[0]) < 1e-9
        if n >= 3 and not horiz and not vert:
            # an angled lead (a second wire on a pin): it moves whole with its end, and the
            # piece after it stays straight (its far corner slides, or a jog is added)
            pts[j] = list(p)
            pts[k] = [pts[k][0] + dx, pts[k][1] + dy]
            m = k + 1 if j == 0 else k - 1
            seg_h = abs(pts[m][1] - (pts[k][1] - dy)) < 1e-9
            seg_v = abs(pts[m][0] - (pts[k][0] - dx)) < 1e-9
            far_end = m in (0, n - 1)
            if seg_h and abs(dy) > 1e-12:
                if far_end:
                    xm = (pts[k][0] + pts[m][0]) / 2
                    jog = [[xm, pts[k][1]], [xm, pts[m][1]]]
                    at = k + 1 if j == 0 else k
                    pts[at:at] = jog if j == 0 else jog[::-1]
                else:
                    pts[m][1] += dy
            elif seg_v and abs(dx) > 1e-12:
                if far_end:
                    ym = (pts[k][1] + pts[m][1]) / 2
                    jog = [[pts[k][0], ym], [pts[m][0], ym]]
                    at = k + 1 if j == 0 else k
                    pts[at:at] = jog if j == 0 else jog[::-1]
                else:
                    pts[m][0] += dx
            return self.copy(points=_tidy(pts))
        if n >= 3:
            if horiz and not vert:
                pts[k][1] += dy
            elif vert and not horiz:
                pts[k][0] += dx
            pts[j] = list(p)
        else:
            a, b = (list(p), pts[1]) if j == 0 else (pts[0], list(p))
            if abs(a[0] - b[0]) < 1e-9 or abs(a[1] - b[1]) < 1e-9:
                pts = [a, b]
            elif horiz or not vert:
                xm = (a[0] + b[0]) / 2
                pts = [a, [xm, a[1]], [xm, b[1]], b]
            else:
                ym = (a[1] + b[1]) / 2
                pts = [a, [a[0], ym], [b[0], ym], b]
        return self.copy(points=_tidy(pts))


@_register
class WireCross(Entity):
    """A wire crossing placed by hand (command Wire crossing): the wire under pos jumps there
    ("gap" or "loop"), or, on a crossing found by itself, its style ("none" hides it). Drawn
    only through the jump it makes (crossings.py); selected and erased like any object."""
    kind = "wirecross"
    __slots__ = ("pos", "style")
    R = 0.0625

    def __init__(self, pos, style="loop", **kw):
        kw.setdefault("layer", "WIRES")
        super().__init__(**kw)
        self.pos = _pt(pos)
        self.style = style if style in ("gap", "loop", "none") else "loop"

    def _data(self):
        return {"pos": list(self.pos), "style": self.style}

    @classmethod
    def _from(cls, d):
        return cls(d["pos"], d.get("style", "loop"), layer=d.get("layer", "WIRES"),
                   color=d.get("color"), id=d.get("id"))

    def _compute_bbox(self):
        r = self.R
        return (self.pos[0] - r, self.pos[1] - r, self.pos[0] + r, self.pos[1] + r)

    def distance(self, p):
        return max(0.0, G.dist(p, self.pos) - self.R)

    def crosses(self, rect):
        return G.bbox_overlaps(self.bbox(), rect)

    def pieces(self):
        return []

    def outline(self):
        r = self.R
        x, y = self.pos
        return [[(x - r, y - r), (x + r, y - r), (x + r, y + r), (x - r, y + r), (x - r, y - r)]]

    def grips(self):
        return [self.pos]

    def with_grip(self, i, p):
        return self.copy(pos=list(p))

    def _map(self, fn, **_kw):
        return self.copy(pos=list(fn(self.pos)))


def _tidy(pts):
    """Points without repeats, and without middle points of straight runs."""
    out = []
    for q in pts:
        if out and abs(out[-1][0] - q[0]) < 1e-9 and abs(out[-1][1] - q[1]) < 1e-9:
            continue
        out.append(list(q))
    i = 1
    while 0 < i < len(out) - 1:
        a, b, c = out[i - 1], out[i], out[i + 1]
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        dot = (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1])
        if abs(cross) < 1e-12 and dot >= 0:
            del out[i]
        else:
            i += 1
    return out


@_register
class Circle(Entity):
    kind = "circle"
    __slots__ = ("center", "radius")

    def __init__(self, center, radius, **kw):
        super().__init__(**kw)
        self.center = _pt(center)
        self.radius = abs(float(radius))

    def _data(self):
        return {"center": list(self.center), "radius": self.radius}

    @classmethod
    def _from(cls, d):
        return cls(d["center"], d["radius"], layer=d.get("layer", "0"), color=d.get("color"),
                   id=d.get("id"))

    def _compute_bbox(self):
        c, r = self.center, self.radius
        return (c[0] - r, c[1] - r, c[0] + r, c[1] + r)

    def distance(self, p):
        return abs(G.dist(p, self.center) - self.radius)

    def crosses(self, rect):
        if not G.bbox_overlaps(self.bbox(), rect):
            return False
        x0, y0, x1, y1 = rect
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        far = max(G.dist(self.center, q) for q in corners)
        # the outline crosses the window unless the window is wholly inside the circle
        if far < self.radius:
            return False
        if x0 <= self.center[0] <= x1 and y0 <= self.center[1] <= y1:
            return True
        return any(G.line_circle_intersections(corners[i], corners[(i + 1) % 4],
                                               self.center, self.radius)
                   for i in range(4)) or G.bbox_inside(self.bbox(), rect)

    def pieces(self):
        return [("circle", self.center, self.radius)]

    def outline(self):
        return [G.arc_points(self.center, self.radius, 0.0, 360.0, 10.0)]

    def _compute_snaps(self):
        c, r = self.center, self.radius
        return [("center", c), ("quad", (c[0] + r, c[1])), ("quad", (c[0], c[1] + r)),
                ("quad", (c[0] - r, c[1])), ("quad", (c[0], c[1] - r))]

    def grips(self):
        c, r = self.center, self.radius
        return [c, (c[0] + r, c[1]), (c[0], c[1] + r), (c[0] - r, c[1]), (c[0], c[1] - r)]

    def with_grip(self, i, p):
        if i == 0:
            return self.copy(center=list(p))
        return self.copy(radius=max(1e-6, G.dist(self.center, p)))

    def _map(self, fn, factor=1.0, **_kw):
        return self.copy(center=list(fn(self.center)), radius=self.radius * abs(factor))


@_register
class Arc(Entity):
    """Counterclockwise from start to end angle (degrees), as DXF stores arcs."""
    kind = "arc"
    __slots__ = ("center", "radius", "start", "end")

    def __init__(self, center, radius, start, end, **kw):
        super().__init__(**kw)
        self.center = _pt(center)
        self.radius = abs(float(radius))
        self.start = float(start) % 360.0
        self.end = float(end) % 360.0

    def _data(self):
        return {"center": list(self.center), "radius": self.radius, "start": self.start,
                "end": self.end}

    @classmethod
    def _from(cls, d):
        return cls(d["center"], d["radius"], d["start"], d["end"], layer=d.get("layer", "0"),
                   color=d.get("color"), id=d.get("id"))

    def start_point(self):
        return G.polar(self.center, self.radius, self.start)

    def end_point(self):
        return G.polar(self.center, self.radius, self.end)

    def mid_point(self):
        return G.polar(self.center, self.radius, self.start + G.sweep(self.start, self.end) / 2)

    def points(self):
        return G.arc_points(self.center, self.radius, self.start, self.end)

    def _compute_bbox(self):
        pts = [self.start_point(), self.end_point()]
        for a in (0, 90, 180, 270):
            if G.angle_on_arc(a, self.start, self.end):
                pts.append(G.polar(self.center, self.radius, a))
        return G.bbox_of(pts)

    def distance(self, p):
        if G.dist(p, self.center) > 1e-12 and G.angle_on_arc(G.angle_of(self.center, p),
                                                             self.start, self.end):
            return abs(G.dist(p, self.center) - self.radius)
        return min(G.dist(p, self.start_point()), G.dist(p, self.end_point()))

    def crosses(self, rect):
        if not G.bbox_overlaps(self.bbox(), rect):
            return False
        return G.polyline_hits_rect(self.points(), rect)

    def pieces(self):
        return [("arc", self.center, self.radius, self.start, self.end)]

    def outline(self):
        return [G.arc_points(self.center, self.radius, self.start, self.end, 10.0)]

    def _compute_snaps(self):
        out = [("end", self.start_point()), ("end", self.end_point()),
               ("mid", self.mid_point()), ("center", self.center)]
        for a in (0, 90, 180, 270):
            if G.angle_on_arc(a, self.start, self.end):
                out.append(("quad", G.polar(self.center, self.radius, a)))
        return out

    def grips(self):
        return [self.start_point(), self.mid_point(), self.end_point(), self.center]

    def with_grip(self, i, p):
        if i == 3:
            return self.moved(p[0] - self.center[0], p[1] - self.center[1])
        pts = [self.start_point(), self.mid_point(), self.end_point()]
        pts[i] = _pt(p)
        r = G.arc_from_3_points(*pts)
        if r is None:
            return self
        c, rad, s, e = r
        return self.copy(center=list(c), radius=rad, start=s, end=e)

    def _map(self, fn, rot=0.0, factor=1.0, mirror=None):
        c = fn(self.center)
        if mirror is not None:
            s = G.mirror_angle(self.end, *mirror)
            e = G.mirror_angle(self.start, *mirror)
        else:
            s, e = self.start + rot, self.end + rot
        return self.copy(center=list(c), radius=self.radius * abs(factor), start=s % 360.0,
                         end=e % 360.0)


# where a text's insertion point sits, as AutoCAD's justifications (TEXT, Justify):
# align: left, center, right; valign: baseline, bottom (under the descenders), middle (half
# the capital height), top (the capitals' top)
VALIGNS = ("baseline", "bottom", "middle", "top")
DESCENT = 0.3           # descenders reach this share of the text height under the baseline
JUSTIFY = {             # AutoCAD's letters -> (align, valign)
    "L": ("left", "baseline"), "C": ("center", "baseline"), "R": ("right", "baseline"),
    "TL": ("left", "top"), "TC": ("center", "top"), "TR": ("right", "top"),
    "ML": ("left", "middle"), "MC": ("center", "middle"), "MR": ("right", "middle"),
    "BL": ("left", "bottom"), "BC": ("center", "bottom"), "BR": ("right", "bottom"),
}


def justify_code(align, valign):
    for k, v in JUSTIFY.items():
        if v == (align, valign):
            return k
    return "L"


@_register
class Text(Entity):
    """One line of text. pos is the insertion point; align (left, center, right) and valign
    (baseline, bottom, middle, top) say where the text sits around it."""
    kind = "text"
    __slots__ = ("pos", "text", "height", "angle", "align", "valign")

    def __init__(self, pos, text, height=0.125, angle=0.0, align="left", valign="baseline",
                 **kw):
        super().__init__(**kw)
        self.pos = _pt(pos)
        self.text = str(text)
        self.height = float(height)
        self.angle = float(angle) % 360.0
        self.align = align if align in ("left", "center", "right") else "left"
        self.valign = valign if valign in VALIGNS else "baseline"

    def _data(self):
        d = {"pos": list(self.pos), "text": self.text, "height": self.height,
             "angle": self.angle, "align": self.align}
        if self.valign != "baseline":
            d["valign"] = self.valign
        return d

    @classmethod
    def _from(cls, d):
        return cls(d["pos"], d.get("text", ""), d.get("height", 0.125), d.get("angle", 0.0),
                   d.get("align", "left"), d.get("valign", "baseline"),
                   layer=d.get("layer", "0"), color=d.get("color"), id=d.get("id"))

    def width(self):
        return text_width(self.text, self.height)

    def offset(self):
        """(dx, dy) from the insertion point to the start of the baseline, before turning."""
        w, h = self.width(), self.height
        dx = {"left": 0.0, "center": -w / 2, "right": -w}[self.align]
        dy = {"baseline": 0.0, "bottom": DESCENT * h, "middle": -h / 2, "top": -h}[self.valign]
        return dx, dy

    def corners(self):
        """The text's box (baseline to cap height), rotated."""
        w, h = self.width(), self.height
        x0, y0 = self.offset()
        local = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
        return [G.rotate_point((self.pos[0] + x, self.pos[1] + y), self.pos, self.angle)
                for x, y in local]

    def _compute_bbox(self):
        return G.bbox_of(self.corners())

    def distance(self, p):
        c = self.corners()
        # inside the box counts as on the text
        local = G.rotate_point(p, self.pos, -self.angle)
        lc = [G.rotate_point(q, self.pos, -self.angle) for q in c]
        if lc[0][0] - 1e-9 <= local[0] <= lc[1][0] + 1e-9 and \
                lc[0][1] - 1e-9 <= local[1] <= lc[2][1] + 1e-9:
            return 0.0
        return min(G.dist_to_segment(p, c[i], c[(i + 1) % 4]) for i in range(4))

    def crosses(self, rect):
        return G.polyline_hits_rect(self.corners(), rect, closed=True)

    def pieces(self):
        return []

    def outline(self):
        c = self.corners()
        return [c + [c[0]]]

    def _compute_snaps(self):
        return [("insert", self.pos)]

    def grips(self):
        return [self.pos]

    def with_grip(self, i, p):
        return self.copy(pos=list(p))

    def _map(self, fn, rot=0.0, factor=1.0, mirror=None):
        pos = fn(self.pos)
        if mirror is not None:
            # the text lands where mirroring puts it but stays readable (AutoCAD's MIRRTEXT 0):
            # its baseline runs along the mirrored direction, turned upright if that points
            # backwards, with the alignment swapped so it covers the same place
            ang = G.mirror_angle(self.angle, *mirror)
            align = self.align
            if 90.0 + 1e-6 < ang <= 270.0 + 1e-6:
                ang = (ang + 180.0) % 360.0
                align = {"left": "right", "right": "left", "center": "center"}[align]
            return self.copy(pos=list(pos), angle=ang, align=align)
        return self.copy(pos=list(pos), angle=(self.angle + rot) % 360.0,
                         height=self.height * abs(factor))


def fmt_inches(v, places=2):
    """A length as a panel builder reads it: 12.50\"."""
    return "%.*f\"" % (places, v)


class Composite(Entity):
    """An object drawn as several plain pieces (lines, texts) worked out from a few values:
    dimensions, DIN rail, wire duct. Subclasses give parts(); hit tests, boxes and export
    follow from them."""
    __slots__ = ()

    def parts(self):
        raise NotImplementedError

    def _compute_bbox(self):
        bb = None
        for e in self.parts():
            bb = G.bbox_union(bb, e.bbox())
        return bb

    def distance(self, p):
        return min(e.distance(p) for e in self.parts())

    def crosses(self, rect):
        return any(e.crosses(rect) for e in self.parts())

    def pieces(self):
        return []                           # (trim and intersections pass them by)

    def outline(self):
        out = []
        for e in self.parts():
            out.extend(e.outline())
        return out

    def exploded(self):
        out = []
        for e in self.parts():
            c = e.copy()
            c.id = None
            out.append(c)
        return out


@_register
class Dimension(Composite):
    """A dimension: the true distance between p1 and p2, its line through loc. mode "linear"
    (across or up and down, whichever loc points to) or "aligned" (along p1-p2). height: its
    text height, in drawing units (on a scaled panel sheet, the paper height times the
    scale's factor: it reads the same on paper at any scale). text: what to show instead of
    the measured length ("" measures; <> in it stands for the measured length)."""
    kind = "dimension"
    __slots__ = ("p1", "p2", "loc", "mode", "height", "text", "_parts")

    def __init__(self, p1, p2, loc, mode="linear", height=0.1, text="", **kw):
        kw.setdefault("layer", "DIMENSIONS")
        super().__init__(**kw)
        self.p1, self.p2, self.loc = _pt(p1), _pt(p2), _pt(loc)
        self.mode = "aligned" if mode == "aligned" else "linear"
        self.height = float(height)
        self.text = str(text or "")
        self._parts = None

    def _data(self):
        d = {"p1": list(self.p1), "p2": list(self.p2), "loc": list(self.loc), "mode": self.mode,
             "height": self.height}
        if self.text:
            d["text"] = self.text
        return d

    @classmethod
    def _from(cls, d):
        return cls(d["p1"], d["p2"], d["loc"], d.get("mode", "linear"), d.get("height", 0.1),
                   d.get("text", ""), layer=d.get("layer", "DIMENSIONS"), color=d.get("color"),
                   id=d.get("id"))

    # ---- geometry --------------------------------------------------------------------------
    def direction(self):
        """(unit vector along the measurement, measured value)."""
        a, b = self.p1, self.p2
        if self.mode == "aligned":
            L = G.dist(a, b)
            if L < 1e-12:
                return (1.0, 0.0), 0.0
            return ((b[0] - a[0]) / L, (b[1] - a[1]) / L), L
        x0, x1 = sorted((a[0], b[0]))
        y0, y1 = sorted((a[1], b[1]))
        out_x = max(x0 - self.loc[0], self.loc[0] - x1, 0.0)
        out_y = max(y0 - self.loc[1], self.loc[1] - y1, 0.0)
        if out_y >= out_x:
            return (1.0, 0.0), abs(b[0] - a[0])             # across
        return (0.0, 1.0), abs(b[1] - a[1])                 # up and down

    def value(self):
        return self.direction()[1]

    def label(self):
        v = fmt_inches(self.value())
        if not self.text:
            return v
        return self.text.replace("<>", v)

    def parts(self):
        """Its lines, arrows and text, placed (kept until it changes)."""
        if self._parts is not None:
            return self._parts
        h = self.height
        (ux, uy), _v = self.direction()
        nx, ny = -uy, ux
        a, b, loc = self.p1, self.p2, self.loc
        # the dimension line: through loc, along u; its ends square off a and b
        d = (loc[0] - a[0]) * nx + (loc[1] - a[1]) * ny
        if self.mode == "linear":
            if ux:                          # across: ends at the points' x, at loc's y
                da, db = (a[0], loc[1]), (b[0], loc[1])
            else:
                da, db = (loc[0], a[1]), (loc[0], b[1])
        else:
            da = (a[0] + nx * d, a[1] + ny * d)
            db = (b[0] + nx * d, b[1] + ny * d)
        out = [Line(da, db)]
        gap, ext = h * 0.5, h * 0.75
        for p, q in ((a, da), (b, db)):
            L = G.dist(p, q)
            if L > 1e-9:
                vx, vy = (q[0] - p[0]) / L, (q[1] - p[1]) / L
                out.append(Line((p[0] + vx * min(gap, L), p[1] + vy * min(gap, L)),
                                (q[0] + vx * ext, q[1] + vy * ext)))
        # open arrowheads pointing out to the extension lines
        s = h * 1.0
        L = G.dist(da, db)
        if L > 1e-9:
            ex, ey = (db[0] - da[0]) / L, (db[1] - da[1]) / L
            for tip, sx, sy in ((da, ex, ey), (db, -ex, -ey)):
                for side in (1, -1):
                    out.append(Line(tip, (tip[0] + sx * s - ey * s * 0.33 * side,
                                          tip[1] + sy * s + ex * s * 0.33 * side)))
        # the text, above the middle of the line, reading left to right or bottom to top
        ang = math.degrees(math.atan2(db[1] - da[1], db[0] - da[0])) % 360.0
        if 90.0 < ang <= 270.0:
            ang = (ang + 180.0) % 360.0
        r = math.radians(ang)
        off = h * 0.4
        mid = ((da[0] + db[0]) / 2 - math.sin(r) * off, (da[1] + db[1]) / 2 + math.cos(r) * off)
        out.append(Text(mid, self.label(), h, ang, "center"))
        for e in out:
            e.layer, e.color = self.layer, self.color
        self._parts = out
        return out

    def _compute_snaps(self):
        return [("node", self.p1), ("node", self.p2)]               # (definition points)

    def grips(self):
        return [self.p1, self.p2, self.loc]

    def with_grip(self, i, p):
        key = ("p1", "p2", "loc")[i]
        return self.copy(**{key: list(p)})

    def _map(self, fn, **_kw):
        # (scaled, its text keeps its height: it is paper-sized, and the number follows)
        return self.copy(p1=list(fn(self.p1)), p2=list(fn(self.p2)), loc=list(fn(self.loc)))


MTEXT_ATTACH = ("TL", "TC", "TR", "ML", "MC", "MR", "BL", "BC", "BR")     # (DXF's 1-9)
LINE_STEP = 1.6667          # a line of text's step, as a share of its height (AutoCAD's)


def wrap_lines(text, height, width):
    """Text cut into lines: at its newlines, and (width over 0) where a word would pass the
    width."""
    out = []
    for para in str(text).split("\n"):
        if width <= 0:
            out.append(para)
            continue
        line = ""
        for word in para.split(" "):
            trial = word if not line else line + " " + word
            if line and text_width(trial, height) > width:
                out.append(line)
                line = word
            else:
                line = trial
        out.append(line)
    return out


@_register
class MText(Composite):
    """Multi-line text (AutoCAD's MTEXT): its lines one under the other (at its newlines, and
    wrapped to width when width is over 0), placed by attach (TL top left ... BR bottom right)
    at pos, turned by angle."""
    kind = "mtext"
    __slots__ = ("pos", "text", "height", "angle", "attach", "width", "_parts")

    def __init__(self, pos, text, height=0.125, angle=0.0, attach="TL", width=0.0, **kw):
        super().__init__(**kw)
        self.pos = _pt(pos)
        self.text = str(text or "")
        self.height = float(height)
        self.angle = float(angle) % 360.0
        self.attach = attach if attach in MTEXT_ATTACH else "TL"
        self.width = max(0.0, float(width or 0.0))
        self._parts = None

    def _data(self):
        d = {"pos": list(self.pos), "text": self.text, "height": self.height,
             "attach": self.attach}
        if self.angle:
            d["angle"] = self.angle
        if self.width:
            d["width"] = self.width
        return d

    @classmethod
    def _from(cls, d):
        return cls(d["pos"], d.get("text", ""), d.get("height", 0.125), d.get("angle", 0.0),
                   d.get("attach", "TL"), d.get("width", 0.0), layer=d.get("layer", "0"),
                   color=d.get("color"), id=d.get("id"))

    def lines(self):
        return wrap_lines(self.text, self.height, self.width)

    def parts(self):
        """Its lines as texts, one under the other, the block of them placed by attach."""
        if self._parts is not None:
            return self._parts
        lines = self.lines()
        h = self.height
        step = h * LINE_STEP
        total = h + (len(lines) - 1) * step
        row, col = self.attach[0], self.attach[1]
        top = {"T": 0.0, "M": total / 2, "B": total}[row]      # its top above pos
        align = {"L": "left", "C": "center", "R": "right"}[col]
        out = []
        for i, line in enumerate(lines):
            if line.strip():
                q = G.polar(self.pos, top - i * step, self.angle + 90)
                out.append(Text(q, line, h, self.angle, align, "top"))
        for e in out:
            e.layer, e.color = self.layer, self.color
        self._parts = out
        return out

    def _compute_bbox(self):
        bb = Composite._compute_bbox(self)
        return bb or (self.pos[0], self.pos[1], self.pos[0], self.pos[1])

    def distance(self, p):
        ps = self.parts()
        return min(e.distance(p) for e in ps) if ps else G.dist(p, self.pos)

    def _compute_snaps(self):
        return [("node", self.pos)]

    def grips(self):
        return [self.pos]

    def with_grip(self, i, p):
        return self.copy(pos=list(p))

    def exploded(self):
        c = self.copy()
        c.id = None
        return [c]                  # (it goes out as one MTEXT: DXF export writes it)

    def _map(self, fn, rot=0.0, factor=1.0, mirror=None, **_kw):
        pos = fn(self.pos)
        if mirror is not None:
            ang = G.mirror_angle(self.angle, *mirror)
            if 90.0 + 1e-6 < ang <= 270.0 + 1e-6:
                ang = (ang + 180.0) % 360.0
            return self.copy(pos=list(pos), angle=ang)
        return self.copy(pos=list(pos), angle=(self.angle + rot) % 360.0,
                         height=self.height * abs(factor), width=self.width * abs(factor))


HATCH_PATTERNS = {
    # name -> (what it is, [(line angle, spacing as a share of the hatch's spacing)])
    "SOLID": ("Solid fill", []),
    "ANSI31": ("Lines at 45 degrees (ANSI31)", [(45.0, 1.0)]),
    "ANSI37": ("Crosshatch (ANSI37)", [(45.0, 1.0), (135.0, 1.0)]),
    "LINES": ("Horizontal lines", [(0.0, 1.0)]),
}
HATCH_LINE_LIMIT = 4000         # pattern lines worked out at most (a tiny spacing on a big area)


def _scan(loops, ang, step, origin=(0.0, 0.0)):
    """The pieces of the lines at ang degrees, step apart (through origin), inside the loops
    (even-odd: a loop inside another is a hole). [((x0, y0), (x1, y1))]."""
    if step <= 0:
        return []
    a = math.radians(ang)
    ux, uy = math.cos(a), math.sin(a)          # along the lines
    nx, ny = -uy, ux                           # across them
    pts = [q for lp in loops for q in lp]
    if not pts:
        return []
    ds = [(q[0] - origin[0]) * nx + (q[1] - origin[1]) * ny for q in pts]
    lo, hi = math.floor(min(ds) / step), math.ceil(max(ds) / step)
    if hi - lo > HATCH_LINE_LIMIT:
        step = (max(ds) - min(ds)) / HATCH_LINE_LIMIT
        lo, hi = math.floor(min(ds) / step), math.ceil(max(ds) / step)
    edges = []
    for lp in loops:
        for i in range(len(lp)):
            p, q = lp[i], lp[(i + 1) % len(lp)]
            edges.append((p, q))
    out = []
    for k in range(int(lo), int(hi) + 1):
        d = k * step
        hits = []
        for p, q in edges:
            dp = (p[0] - origin[0]) * nx + (p[1] - origin[1]) * ny - d
            dq = (q[0] - origin[0]) * nx + (q[1] - origin[1]) * ny - d
            if (dp > 0) == (dq > 0) or dp == dq:
                continue
            t = dp / (dp - dq)
            x, y = p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
            hits.append(((x - origin[0]) * ux + (y - origin[1]) * uy, x, y))
        hits.sort()
        for i in range(0, len(hits) - 1, 2):
            a0, b0 = hits[i], hits[i + 1]
            if b0[0] - a0[0] > 1e-12:
                out.append(((a0[1], a0[2]), (b0[1], b0[2])))
    return out


def point_in_loops(p, loops):
    """Is p inside the loops (even-odd)?"""
    inside = False
    x, y = p
    for lp in loops:
        n = len(lp)
        for i in range(n):
            (x0, y0), (x1, y1) = lp[i], lp[(i + 1) % n]
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                inside = not inside
    return inside


@_register
class Hatch(Composite):
    """A hatch or fill: closed loops (a loop inside another is a hole: even-odd) filled solid
    or with a pattern of lines (HATCH_PATTERNS) spacing apart, turned by angle. Not tied to
    the shapes it was made from: it moves, copies and scales on its own."""
    kind = "hatch"
    __slots__ = ("loops", "pattern", "angle", "spacing", "_parts")

    def __init__(self, loops, pattern="SOLID", angle=0.0, spacing=0.125, **kw):
        super().__init__(**kw)
        self.loops = [[_pt(q) for q in lp] for lp in loops if len(lp) >= 3]
        self.pattern = pattern if pattern in HATCH_PATTERNS else "ANSI31"
        self.angle = float(angle)
        self.spacing = float(spacing) if spacing and spacing > 0 else 0.125
        self._parts = None

    def _data(self):
        d = {"loops": [[list(q) for q in lp] for lp in self.loops], "pattern": self.pattern}
        if self.angle:
            d["angle"] = self.angle
        if self.pattern != "SOLID":
            d["spacing"] = self.spacing
        return d

    @classmethod
    def _from(cls, d):
        return cls(d.get("loops", []), d.get("pattern", "SOLID"), d.get("angle", 0.0),
                   d.get("spacing", 0.125), layer=d.get("layer", "0"), color=d.get("color"),
                   id=d.get("id"))

    def solid(self):
        return self.pattern == "SOLID"

    def parts(self):
        """Its loops (closed polylines) and its pattern's lines (none for a solid fill: the
        renderer fills its loops)."""
        if self._parts is not None:
            return self._parts
        out = [Polyline(lp, True) for lp in self.loops]
        for ang, share in HATCH_PATTERNS[self.pattern][1]:
            for a, b in _scan(self.loops, ang + self.angle, self.spacing * share):
                out.append(Line(a, b))
        for e in out:
            e.layer, e.color = self.layer, self.color
        self._parts = out
        return out

    def distance(self, p):
        # (anywhere on it picks it, not only its lines)
        if point_in_loops(p, self.loops):
            return 0.0
        return min(e.distance(p) for e in self.parts()[:len(self.loops)])

    def _compute_snaps(self):
        return [("end", q) for lp in self.loops for q in lp]

    def grips(self):
        return []

    def exploded(self):
        c = self.copy()
        c.id = None
        return [c]                  # (it goes out as a hatch: DXF export writes a HATCH)

    def _map(self, fn, factor=1.0, rot=0.0, mirror=None, **_kw):
        ang = G.mirror_angle(self.angle, *mirror) if mirror is not None else self.angle + rot
        return self.copy(loops=[[list(fn(q)) for q in lp] for lp in self.loops],
                         spacing=self.spacing * abs(factor), angle=ang % 180.0)


@_register
class Leader(Composite):
    """A leader (AutoCAD's LEADER and MLEADER in one): an arrow at points[0] pointing at
    something, a line through the other points, and at its end a note (text, several lines
    split by newlines) or a balloon (a circle with an item number, as a bill of materials
    uses). height: its text height in drawing units (paper-sized, as a dimension's)."""
    kind = "leader"
    __slots__ = ("points", "text", "balloon", "height", "_parts")

    def __init__(self, points, text="", balloon=False, height=0.1, **kw):
        kw.setdefault("layer", "DIMENSIONS")
        super().__init__(**kw)
        self.points = [_pt(q) for q in points]
        self.text = str(text or "")
        self.balloon = bool(balloon)
        self.height = float(height)
        self._parts = None

    def _data(self):
        d = {"points": [list(q) for q in self.points], "height": self.height}
        if self.text:
            d["text"] = self.text
        if self.balloon:
            d["balloon"] = True
        return d

    @classmethod
    def _from(cls, d):
        return cls(d["points"], d.get("text", ""), d.get("balloon", False),
                   d.get("height", 0.1), layer=d.get("layer", "DIMENSIONS"),
                   color=d.get("color"), id=d.get("id"))

    def side(self):
        """+1: the note goes to the right of the end; -1: to the left (as the last bend
        points)."""
        if len(self.points) < 2:
            return 1
        a, b = self.points[-2], self.points[-1]
        return 1 if b[0] >= a[0] else -1

    def parts(self):
        """Its arrowhead, line, landing and note or balloon, placed (kept until it changes)."""
        if self._parts is not None:
            return self._parts
        h, pts = self.height, self.points
        out = []
        if len(pts) >= 2:
            out.append(Polyline(pts, False))
            # a closed arrowhead at the first point, along the first segment
            tip, nxt = pts[0], pts[1]
            L = G.dist(tip, nxt)
            if L > 1e-9:
                ux, uy = (nxt[0] - tip[0]) / L, (nxt[1] - tip[1]) / L
                s = min(h * 1.2, L * 0.5)
                bx, by = tip[0] + ux * s, tip[1] + uy * s
                w = s * 0.3
                out.append(Hatch([[tip, (bx - uy * w, by + ux * w),
                                   (bx + uy * w, by - ux * w)]], "SOLID"))
            end, sd = pts[-1], self.side()
            land = (end[0] + sd * h, end[1])          # (a short level landing)
            out.append(Line(end, land))
            if self.balloon:
                r = h * 1.1
                c = (land[0] + sd * r, land[1])
                out.append(Circle(c, r))
                if self.text:
                    out.append(Text(c, self.text.splitlines()[0], h, 0.0, "center", "middle"))
            elif self.text:
                lines = self.text.splitlines() or [""]
                x = land[0] + sd * h * 0.3
                step = h * 1.6667
                y0 = land[1] + (len(lines) - 1) * step / 2
                for i, line in enumerate(lines):
                    if line.strip():
                        out.append(Text((x, y0 - i * step), line, h, 0.0,
                                        "left" if sd > 0 else "right", "middle"))
        for e in out:
            e.layer, e.color = self.layer, self.color
        self._parts = out
        return out

    def _compute_snaps(self):
        out = [("end", self.points[0])] if self.points else []
        out += [("node", q) for q in self.points[1:]]
        return out

    def grips(self):
        return list(self.points)

    def with_grip(self, i, p):
        pts = [list(q) for q in self.points]
        pts[i] = list(p)
        return self.copy(points=pts)

    def _map(self, fn, **_kw):
        # (scaled, its text keeps its height: it is paper-sized)
        return self.copy(points=[list(fn(q)) for q in self.points])


# ---- DIN rail and wire duct: real-size pieces from one end to the other ---------------------
MM_IN = 1 / 25.4
# rail profiles: key -> (name, width, depth) in inches
RAIL_PROFILES = {
    "TS35x7.5": ("TS35 x 7.5 mm", 35 * MM_IN, 7.5 * MM_IN),
    "TS35x15": ("TS35 x 15 mm", 35 * MM_IN, 15 * MM_IN),
    "TS15": ("TS15 x 5.5 mm (mini)", 15 * MM_IN, 5.5 * MM_IN),
}
# wire duct sizes offered (width x depth, inches); any other can be typed
DUCT_SIZES = [(1, 2), (1, 3), (1.5, 3), (2, 2), (2, 3), (2, 4), (3, 3), (3, 4), (4, 4)]


def size_text(width, depth):
    """2 x 3 (inches), or 50 x 75 mm when it is a whole number of millimeters and not of
    eighths of an inch."""
    def nice(v):
        return ("%.3f" % v).rstrip("0").rstrip(".")
    if all(abs(v * 8 - round(v * 8)) < 1e-6 for v in (width, depth)):
        return "%s x %s" % (nice(width), nice(depth))
    return "%s x %s mm" % (nice(width * 25.4), nice(depth * 25.4))


class Run(Composite):
    """A straight piece cut to length, drawn at real size from p1 to p2 (its centerline):
    DIN rail or wire duct. width is drawn; depth isn't (a plan view) but goes on the bill of
    materials. attrs: MFR, CAT, DESC of its part; stock: the length it is bought in (0: the
    project's)."""
    __slots__ = ("p1", "p2", "size", "width", "depth", "attrs", "stock", "_parts")

    def __init__(self, p1, p2, size="", width=1.0, depth=1.0, attrs=None, stock=0.0, **kw):
        kw.setdefault("layer", "PANEL")
        super().__init__(**kw)
        self.p1, self.p2 = _pt(p1), _pt(p2)
        self.size = str(size or "")
        self.width, self.depth = float(width), float(depth)
        self.attrs = {k: str(v) for k, v in (attrs or {}).items()}
        self.stock = float(stock or 0.0)
        self._parts = None

    def _data(self):
        d = {"p1": list(self.p1), "p2": list(self.p2), "size": self.size, "width": self.width,
             "depth": self.depth}
        if self.attrs:
            d["attrs"] = dict(self.attrs)
        if self.stock:
            d["stock"] = self.stock
        return d

    @classmethod
    def _from(cls, d):
        return cls(d["p1"], d["p2"], d.get("size", ""), d.get("width", 1.0), d.get("depth", 1.0),
                   d.get("attrs"), d.get("stock", 0.0), layer=d.get("layer", "PANEL"),
                   color=d.get("color"), id=d.get("id"))

    def length(self):
        return G.dist(self.p1, self.p2)

    def axes(self):
        """(unit vector along, unit normal)."""
        L = self.length()
        if L < 1e-12:
            return (1.0, 0.0), (0.0, 1.0)
        ux, uy = (self.p2[0] - self.p1[0]) / L, (self.p2[1] - self.p1[1]) / L
        return (ux, uy), (-uy, ux)

    def at(self, s, t):
        """The point s along from p1 and t across the centerline."""
        (ux, uy), (nx, ny) = self.axes()
        return (self.p1[0] + ux * s + nx * t, self.p1[1] + uy * s + ny * t)

    def corners(self):
        L, h = self.length(), self.width / 2
        return [self.at(0, -h), self.at(L, -h), self.at(L, h), self.at(0, h)]

    def name(self):
        return self.size

    def parts(self):
        if self._parts is None:
            c = self.corners()
            out = [Polyline(c, True)] + self._details()
            for e in out:
                e.layer, e.color = self.layer, self.color
            self._parts = out
        return self._parts

    def _details(self):
        return []

    def _compute_snaps(self):
        mid = ((self.p1[0] + self.p2[0]) / 2, (self.p1[1] + self.p2[1]) / 2)
        L, h = self.length(), self.width / 2
        # its ends and middle, its corners, and the middles of its long edges (to center
        # something on it)
        return [("end", self.p1), ("end", self.p2), ("mid", mid)] + \
            [("end", q) for q in self.corners()] + \
            [("mid", self.at(L / 2, -h)), ("mid", self.at(L / 2, h))] + self._more_snaps()

    def _more_snaps(self):
        return []

    def centerline(self):
        """Its centerline, as a line (for snapping along it: not drawn)."""
        return Line(self.p1, self.p2, layer=self.layer)

    def grips(self):
        mid = ((self.p1[0] + self.p2[0]) / 2, (self.p1[1] + self.p2[1]) / 2)
        return [self.p1, mid, self.p2]

    def with_grip(self, i, p):
        # an end grip stretches it along its own line: it stays straight
        if i in (0, 2):
            (ux, uy), _n = self.axes()
            other = self.p2 if i == 0 else self.p1
            s = (p[0] - other[0]) * ux + (p[1] - other[1]) * uy
            q = [other[0] + ux * s, other[1] + uy * s]
            if G.dist(q, other) < 1e-9:
                return self.copy()
            return self.copy(p1=q) if i == 0 else self.copy(p2=q)
        return Entity.with_grip(self, i, p)

    def _map(self, fn, **_kw):
        # (scaled, it gets longer or shorter: its profile stays the real one)
        return self.copy(p1=list(fn(self.p1)), p2=list(fn(self.p2)))

    def with_length(self, L):
        """A copy L long, p1 staying where it is."""
        (ux, uy), _n = self.axes()
        return self.copy(p2=[self.p1[0] + ux * L, self.p1[1] + uy * L])


@_register
class Rail(Run):
    """DIN rail: its outline, the edges of its lips and its mounting slots."""
    kind = "rail"
    __slots__ = ()

    def name(self):
        prof = RAIL_PROFILES.get(self.size)
        return "DIN rail " + (prof[0] if prof else self.size)

    def _slots(self):
        """[(start, end)] along it of its mounting slots: 15 x 5.2 mm every 25 mm on a 35 mm
        rail (in proportion on others), and their size (length, width)."""
        L = self.length()
        f = self.width / (35 * MM_IN)
        sl, sw, pitch = 15 * MM_IN * f, 5.2 * MM_IN * f, 25 * MM_IN * f
        s = pitch / 2 - sl / 2
        out = []
        while s + sl <= L and len(out) < 2000:
            out.append((s, s + sl))
            s += pitch
        return out, (sl, sw)

    def _more_snaps(self):
        # each mounting slot's center: things are centered on the rail's holes
        slots, _size = self._slots()
        return [("center", self.at((a + b) / 2, 0.0)) for a, b in slots]

    def _details(self):
        L, h = self.length(), self.width / 2
        lip = 5 * MM_IN * self.width / (35 * MM_IN)
        out = [Line(self.at(0, -(h - lip)), self.at(L, -(h - lip))),
               Line(self.at(0, h - lip), self.at(L, h - lip))]
        slots, (_sl, sw) = self._slots()
        for a, b in slots:
            out.append(Polyline([self.at(a, -sw / 2), self.at(b, -sw / 2),
                                 self.at(b, sw / 2), self.at(a, sw / 2)], True))
        return out


@_register
class Duct(Run):
    """Wire duct (wireway): its outline, its walls and their finger slots. The depth isn't
    drawn (a plan view) but is part of its size."""
    kind = "duct"
    __slots__ = ()
    WALL = 0.08
    PITCH = 0.5

    def name(self):
        return "Wire duct " + size_text(self.width, self.depth)

    def _details(self):
        L, h, t = self.length(), self.width / 2, min(self.WALL, self.width / 6)
        out = [Line(self.at(0, -(h - t)), self.at(L, -(h - t))),
               Line(self.at(0, h - t), self.at(L, h - t))]
        s = self.PITCH
        n = 0
        while s < L - 1e-9 and n < 4000:
            out.append(Line(self.at(s, -h), self.at(s, -(h - t))))
            out.append(Line(self.at(s, h), self.at(s, h - t)))
            s += self.PITCH
            n += 1
        return out


# ============================================================================================
# Blocks: symbols (schematic, with pins and a tag) and footprints (panel outlines)
# ============================================================================================
BLOCK_KINDS = ("symbol", "footprint")
# a symbol's part in cross-references (worked out in a later version):
#   device - stands alone (fuse, pilot light, motor...)
#   parent - has contacts elsewhere (relay/contactor coil, pushbutton or switch operator)
#   child  - a contact of a parent (takes the parent's tag)
ROLES = ("device", "parent", "child")
CONTACTS = ("", "NO", "NC", "NOTC", "NCTO", "NOTO", "NCTC")
# what wires do through a symbol (wirenums.py): "" nothing (each side its own number),
# "distribution" (a distribution block: its first pin's number goes on, with A, B, C... added,
# to the wires on its other pins), "link" (an off-sheet connector: wires at connectors with
# the same name are one wire, whatever sheet they're on)
WIRINGS = ("", "distribution", "link")
ATTR_NAMES = ["TAG", "DESC", "MFR", "CAT"]       # what every block reference can carry
# a block's optional maker details: who makes it, and its catalog (part) number
MAKER_FIELDS = ("manufacturer", "family", "series", "catalog")


class BlockDef:
    """A block: entities drawn around the base point (0, 0), and for a schematic symbol its
    pins (where wires attach) and where its tag goes. Footprints are drawn at real size."""

    def __init__(self, name, kind="symbol", entities=(), pins=(), tag_pos=None, tag_height=0.1,
                 category="", description="", role="device", contact="", prefix="",
                 builtin=False, wiring="", attr_texts=(), manufacturer="", family="",
                 series="", catalog="", rail_pos=None, own_colors=False):
        self.name = str(name)
        self.kind = kind if kind in BLOCK_KINDS else "symbol"
        self.entities = list(entities)
        self.pins = [{"name": str(p["name"]), "pos": _pt(p["pos"])} for p in pins]
        self.tag_pos = _pt(tag_pos) if tag_pos is not None else None
        self.tag_height = float(tag_height)
        self.category = category
        self.description = description
        self.role = role if role in ROLES else "device"
        self.contact = contact if contact in CONTACTS else ""
        self.prefix = prefix            # tag prefix: CR, M, PB... (page-number tags, later)
        self.builtin = bool(builtin)    # one of the program's own (not in your library folder)
        self.wiring = wiring if wiring in WIRINGS else ""
        # attributes shown on the symbol besides its tag: [{"attr": "TERM", "pos": (x, y),
        # "height": h}] (a terminal's number, a PLC point's address...)
        self.attr_texts = [{"attr": str(a["attr"]), "pos": _pt(a["pos"]),
                            "height": float(a.get("height", 0.08))} for a in attr_texts]
        # who makes it, for finding and grouping blocks (optional; see the manual's
        # "Manufacturer, family and series"): Allen-Bradley / ControlLogix / B...
        self.manufacturer = str(manufacturer or "")
        self.family = str(family or "")
        self.series = str(series or "")
        self.catalog = str(catalog or "")   # its part number (1756-A10...): placed, its CAT
        # a footprint's DIN rail point: the middle of its rail clip, which lines up with the
        # rail's centerline (None: the middle of its drawing; see rail_point)
        self.rail_pos = _pt(rail_pos) if rail_pos is not None else None
        # its pieces keep their own colors (a block from another program's drawing, as
        # AutoCAD shows it: a manufacturer's colored parts); else all in the copy's color
        self.own_colors = bool(own_colors)

    def to_dict(self):
        return {"name": self.name, "kind": self.kind, "category": self.category,
                "description": self.description, "role": self.role, "contact": self.contact,
                "prefix": self.prefix, "tag_height": self.tag_height,
                "tag_pos": list(self.tag_pos) if self.tag_pos is not None else None,
                "pins": [{"name": p["name"], "pos": list(p["pos"])} for p in self.pins],
                "entities": [e.to_dict() for e in self.entities]} | (
                    {"wiring": self.wiring} if self.wiring else {}) | (
                    {"attr_texts": [{"attr": a["attr"], "pos": list(a["pos"]),
                                     "height": a["height"]} for a in self.attr_texts]}
                    if self.attr_texts else {}) | {
                    k: getattr(self, k) for k in MAKER_FIELDS if getattr(self, k)} | (
                    {"rail_pos": list(self.rail_pos)} if self.rail_pos is not None else {}) | (
                    {"own_colors": True} if self.own_colors else {})

    @classmethod
    def from_dict(cls, d, builtin=False):
        return cls(d["name"], d.get("kind", "symbol"),
                   [Entity.from_dict(e) for e in d.get("entities", [])], d.get("pins", []),
                   d.get("tag_pos"), d.get("tag_height", 0.1), d.get("category", ""),
                   d.get("description", ""), d.get("role", "device"), d.get("contact", ""),
                   d.get("prefix", ""), builtin, d.get("wiring", ""),
                   d.get("attr_texts", ()), d.get("manufacturer", ""), d.get("family", ""),
                   d.get("series", ""), d.get("catalog", ""), d.get("rail_pos"),
                   d.get("own_colors", False))

    def same_as(self, other):
        a, b = self.to_dict(), other.to_dict()
        return a == b

    def rail_point(self):
        """Where a footprint sits on a DIN rail: its rail point when one is set (Edit block),
        else the middle of its drawing."""
        if self.rail_pos is not None:
            return self.rail_pos
        return self.middle()

    def label_point(self):
        """Where a footprint's label goes: its label spot when one is set (Edit block: the
        tag spot), else the middle of its drawing."""
        return self.tag_pos if self.tag_pos is not None else self.middle()

    def middle(self):
        """The middle of its drawing (pins left out)."""
        bb = None
        for e in self.entities:
            bb = G.bbox_union(bb, e.bbox())
        if bb is None:
            return (0.0, 0.0)
        return ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)

    def extents(self):
        bb = None
        for e in self.entities:
            bb = G.bbox_union(bb, e.bbox())
        for p in self.pins:
            bb = G.bbox_union(bb, (p["pos"][0], p["pos"][1], p["pos"][0], p["pos"][1]))
        return bb or (0.0, 0.0, 0.0, 0.0)


# what a footprint's label shows (Footprint label): the attribute, or its block's name
LABELS = {"tag": "TAG", "cat": "CAT", "desc": "DESC", "name": None}
LABEL_NAMES = {"tag": "Tag", "cat": "Part number", "desc": "Description", "name": "Block name"}


@_register
class Insert(Entity):
    """A block placed on a sheet: at pos, turned by angle, sized by scale, optionally flipped
    (mirror: the block's own y turned over before turning), with its attributes (TAG, DESC,
    MFR, CAT and the part it is). defn is the BlockDef it shows (the project's copy). label:
    what a footprint shows on it ("" nothing, or a key of LABELS)."""
    kind = "insert"
    __slots__ = ("block", "pos", "angle", "scale", "mirror", "attrs", "defn", "tag_h", "label",
                 "_world")

    def __init__(self, block, pos, angle=0.0, scale=1.0, mirror=False, attrs=None, defn=None,
                 tag_h=None, label="", **kw):
        super().__init__(**kw)
        self.block = str(block)
        self.pos = _pt(pos)
        self.angle = float(angle) % 360.0
        self.scale = float(scale) or 1.0
        self.mirror = bool(mirror)
        self.attrs = {k: str(v) for k, v in (attrs or {}).items()}
        self.defn = defn
        self.tag_h = float(tag_h) if tag_h else None    # tag height (None: the block's)
        self.label = label if label in LABELS else ""
        self._world = None

    def _data(self):
        d = {"block": self.block, "pos": list(self.pos), "angle": self.angle,
             "scale": self.scale, "attrs": dict(self.attrs)}
        if self.mirror:
            d["mirror"] = True
        if self.tag_h:
            d["tag_h"] = self.tag_h
        if self.label:
            d["label"] = self.label
        return d

    @classmethod
    def _from(cls, d, blocks):
        return cls(d["block"], d["pos"], d.get("angle", 0.0), d.get("scale", 1.0),
                   d.get("mirror", False), d.get("attrs", {}), blocks.get(d["block"]),
                   d.get("tag_h"), d.get("label", ""), layer=d.get("layer", "0"),
                   color=d.get("color"), id=d.get("id"))

    def copy(self, **changes):
        d = self.to_dict()
        d.update(changes)
        e = Insert._from(d, {self.block: self.defn} if self.defn is not None else {})
        return e

    # ---- placing the block's content -----------------------------------------------------
    def to_world(self, q):
        x, y = q[0] * self.scale, q[1] * self.scale
        if self.mirror:
            y = -y
        x, y = G.rotate_point((x, y), (0.0, 0.0), self.angle)
        return (x + self.pos[0], y + self.pos[1])

    def pin_points(self):
        """[(pin name, world point)]."""
        if self.defn is None:
            return []
        return [(p["name"], self.to_world(p["pos"])) for p in self.defn.pins]

    def tag_text(self):
        """The tag shown on the sheet (None for a footprint or a symbol without a tag spot)."""
        d = self.defn
        if d is not None and d.kind == "footprint":
            return self.label_text()
        if d is None or d.kind != "symbol" or d.tag_pos is None:
            return None
        tag = self.attrs.get("TAG", "")
        return Text(self.to_world(d.tag_pos), tag or (d.prefix + "?" if d.prefix else "?"),
                    (self.tag_h or d.tag_height) * self.scale, 0.0, "center")

    def label_value(self):
        """What a footprint's label says ("?" when that attribute is empty), or None."""
        d = self.defn
        if not self.label or d is None:
            return None
        if self.label == "name":
            return d.name
        v = self.attrs.get(LABELS[self.label], "")
        if not v and self.label == "cat":
            v = d.catalog
        return v or "?"

    def label_text(self):
        """A footprint's label (Footprint label): at its block's label spot, centered, paper-
        sized (tag_h), read from the bottom or the right as it is turned. None: no label."""
        v = self.label_value()
        if v is None:
            return None
        a = self.angle % 180.0
        ang = 90.0 if 45.0 <= a < 135.0 else 0.0
        return Text(self.to_world(self.defn.label_point()), v, self.tag_h or 0.125, ang,
                    "center", "middle")

    def world_entities(self):
        """The block's content placed on the sheet, plus the tag text."""
        if self._world is None:
            out = []
            d = self.defn
            if d is None:
                # its block is missing from the project: show an X where it sits
                r = 0.1
                out = [Line((self.pos[0] - r, self.pos[1] - r), (self.pos[0] + r, self.pos[1] + r)),
                       Line((self.pos[0] - r, self.pos[1] + r), (self.pos[0] + r, self.pos[1] - r))]
            else:
                for e in d.entities:
                    w = e._map(self.to_world, rot=self.angle, factor=self.scale,
                               mirror=None)
                    if self.mirror:
                        w = _mirror_fix(e, w, self)
                    out.append(w)
                t = self.tag_text()
                if t is not None:
                    out.append(t)
                for a in d.attr_texts:
                    v = self.attrs.get(a["attr"], "")
                    if v:
                        out.append(Text(self.to_world(a["pos"]), v, a["height"] * self.scale,
                                        0.0, "center"))
            own = d is not None and d.own_colors
            for w in out:
                keep = own and w.color is not None
                w.layer = self.layer
                if not keep:
                    w.color = self.color
            self._world = out
        return self._world

    def _compute_bbox(self):
        bb = None
        for e in self.world_entities():
            bb = G.bbox_union(bb, e.bbox())
        for _n, p in self.pin_points():
            bb = G.bbox_union(bb, (p[0], p[1], p[0], p[1]))
        return bb or (self.pos[0], self.pos[1], self.pos[0], self.pos[1])

    def distance(self, p):
        ds = [e.distance(p) for e in self.world_entities()]
        return min(ds) if ds else G.dist(p, self.pos)

    def crosses(self, rect):
        return any(e.crosses(rect) for e in self.world_entities())

    def pieces(self):
        out = []
        for e in self.world_entities():
            out.extend(e.pieces())
        return out

    def outline(self):
        out = []
        for e in self.world_entities():
            out.extend(e.outline())
        return out

    def _compute_snaps(self):
        out = [("insert", self.pos)]
        out += [("node", p) for _n, p in self.pin_points()]         # (pins: AutoCAD's nodes)
        return out

    def grips(self):
        return [self.pos]

    def with_grip(self, i, p):
        return self.copy(pos=list(p))

    def moved(self, dx, dy):
        return self.copy(pos=[self.pos[0] + dx, self.pos[1] + dy])

    def rotated(self, center, angle):
        return self.copy(pos=list(G.rotate_point(self.pos, center, angle)),
                         angle=(self.angle + angle) % 360.0)

    def scaled(self, base, factor):
        return self.copy(pos=list(G.scale_point(self.pos, base, factor)),
                         scale=self.scale * abs(factor))

    def mirrored(self, a, b):
        # reflecting across a line at angle phi: turned to 2*phi - angle, flip toggled
        phi = G.angle_of(a, b)
        return self.copy(pos=list(G.mirror_point(self.pos, a, b)),
                         angle=(2 * phi - self.angle) % 360.0, mirror=not self.mirror)

    def exploded(self):
        """Its content as plain lines, arcs and texts (EXPLODE)."""
        out = []
        for w in self.world_entities():
            c = w.copy()
            c.id = None
            out.append(c)
        return out


def _mirror_fix(src, mapped, ins):
    """A block entity placed by a flipped reference: points were mapped through to_world
    (which flips), but arcs need their angles and texts their readability fixed."""
    if isinstance(src, Arc):
        # the arc's ends, flipped, swap order (counterclockwise becomes clockwise)
        a = ins.to_world(G.polar(src.center, src.radius, src.start))
        b = ins.to_world(G.polar(src.center, src.radius, src.end))
        c = mapped.center
        return mapped.copy(start=G.angle_of(c, b), end=G.angle_of(c, a))
    if isinstance(src, Text):
        ang = (-src.angle + ins.angle) % 360.0
        align = src.align
        if 90.0 + 1e-6 < ang <= 270.0 + 1e-6:
            ang = (ang + 180.0) % 360.0
            align = {"left": "right", "right": "left", "center": "center"}[align]
        return mapped.copy(angle=ang, align=align)
    return mapped


# ============================================================================================
# Layers, sheets, project
# ============================================================================================
class Layer:
    def __init__(self, name, color=ADAPTIVE, visible=True, locked=False):
        self.name = name
        self.color = color
        self.visible = bool(visible)
        self.locked = bool(locked)

    def to_dict(self):
        return {"name": self.name, "color": self.color, "visible": self.visible,
                "locked": self.locked}

    @classmethod
    def from_dict(cls, d):
        return cls(d["name"], d.get("color", ADAPTIVE), d.get("visible", True),
                   d.get("locked", False))


def row_letters(n, start=0):
    """A, B, ... Z, AA, AB ... for n rows, the first being letter number start (0 = A)."""
    out = []
    for i in range(start, start + n):
        s, k = "", i
        while True:
            s = string.ascii_uppercase[k % 26] + s
            k = k // 26 - 1
            if k < 0:
                break
        out.append(s)
    return out


class SpatialIndex:
    """Entity ids in square buckets, for hit tests, snapping and window selection that don't
    walk every entity on the sheet."""
    CELL = 0.5          # inches

    def __init__(self):
        self.cells = {}
        self.where = {}

    def _keys(self, bb):
        c = self.CELL
        x0, y0 = int(math.floor(bb[0] / c)), int(math.floor(bb[1] / c))
        x1, y1 = int(math.floor(bb[2] / c)), int(math.floor(bb[3] / c))
        if (x1 - x0 + 1) * (y1 - y0 + 1) > 4096:          # a huge entity: clamp
            x1, y1 = min(x1, x0 + 63), min(y1, y0 + 63)
        return [(i, j) for i in range(x0, x1 + 1) for j in range(y0, y1 + 1)]

    def add(self, ent):
        keys = self._keys(ent.bbox())
        self.where[ent.id] = keys
        for k in keys:
            self.cells.setdefault(k, set()).add(ent.id)

    def remove(self, eid):
        for k in self.where.pop(eid, ()):
            s = self.cells.get(k)
            if s is not None:
                s.discard(eid)
                if not s:
                    del self.cells[k]

    def query(self, rect):
        out = set()
        for k in self._keys(rect):
            s = self.cells.get(k)
            if s:
                out |= s
        return out

    def query_point(self, p, tol):
        """Ids whose box may hold a point within tol of p: the one cell p is in, unless p is
        within tol of a cell's edge (then the box's cells, as query)."""
        c = self.CELL
        fx, fy = p[0] / c, p[1] / c
        i, j = math.floor(fx), math.floor(fy)
        t = tol / c
        if fx - i > t and i + 1 - fx > t and fy - j > t and j + 1 - fy > t:
            return self.cells.get((i, j), ())
        return self.query((p[0] - tol, p[1] - tol, p[0] + tol, p[1] + tol))


# a panel sheet's scale presets: (name written on the drawing, paper / real); "" names 1:N
SCALE_PRESETS = [
    ("", 1.0), ("", 1 / 2), ("", 1 / 4), ("", 1 / 5), ("", 1 / 8), ("", 1 / 10), ("", 1 / 16),
    ("", 1 / 20),
    ('3" = 1\'-0"', 1 / 4), ('1-1/2" = 1\'-0"', 1 / 8), ('1" = 1\'-0"', 1 / 12),
    ('3/4" = 1\'-0"', 1 / 16), ('1/2" = 1\'-0"', 1 / 24), ('1/4" = 1\'-0"', 1 / 48),
]

def _cabinet(v):
    """A stored cabinet size as [width, height, depth] (real inches), or None."""
    try:
        w, h = float(v[0]), float(v[1])
        d = float(v[2]) if len(v) > 2 and v[2] else 0.0
    except (TypeError, ValueError, IndexError):
        return None
    return [w, h, max(d, 0.0)] if w > 0 and h > 0 else None


SHEET_KINDS = {"schematic": "Schematic", "panel": "Panel", "report": "Report", "other": "Other"}
TITLE_BLOCK_ID = 0          # the project's title block is kept as a sheet with this id


class Sheet:
    def __init__(self, title="", size=DEFAULT_SIZE, cols=10, rows=8, number=None, id=None,
                 fields=None, col_start=1, row_start=0):
        self.id = id
        self.title = title
        self.size = size if size in SHEET_SIZES else DEFAULT_SIZE
        self.cols = int(cols)
        self.rows = int(rows)
        self.number = number            # None: its position in the project
        self.own_layout = False             # True: its size and zones aren't the project's
        self.kind = "schematic"             # schematic, panel, report or other (defaults only)
        self.number_order = "across"        # tags (and wire numbers): across/down then the other
        self.scale = 1.0                    # paper / real (a panel sheet at 1:4: 0.25): the
                                            # drawing is real size, the border and paper-sized
                                            # text around it are drawn 1/scale larger
        self.scale_name = ""                # its preset's name (1/4" = 1'-0"...), "" for 1:N
        self.rotation = 0                   # the sheet turned, degrees counterclockwise: 0, 90,
                                            # 180 or 270 (a quarter turn clockwise). Its border,
                                            # zones and title block turn with it; the drawing
                                            # stays upright (a tall cabinet on a tall sheet)
        self.cabinet = None                 # a panel sheet's cabinet [width, height, depth]
                                            # (real inches, depth 0 when not given), or None:
                                            # what Sheet scale fits while nothing is drawn
        self.reserve = None                 # ("right" | "bottom", paper inches): the title
                                            # block's strip, the zones stop at it (set by the
                                            # project: Project.sync_reserve)
        self.xref_frozen = False            # cross-references kept as they were (issued sheet)
        self.xref_shown = None              # the cross-references shown while frozen (or while
                                            # the project's aren't automatic): xrefs.py
        self.col_start = int(col_start)     # the first column's number (1 to start)
        self.row_start = int(row_start)     # the first row's letter: 0 = A, 1 = B...
        self.fields = dict(fields or {})
        self.entities = {}              # id -> Entity, in drawing order
        self._next = 1
        self.index = SpatialIndex()
        self.version = 0                # bumped on every change (render caches key on it)
        self.touched = set()            # ids changed since the screen renderer last looked

    # ---- size, border, zones -------------------------------------------------------------
    def paper(self):
        """The sheet's size in drawing units (its paper size at 1:1; 1/scale larger on a
        scaled panel sheet), as turned."""
        w, h = self.paper_inches()
        k = self.k()
        return w * k, h * k

    def paper_inches(self):
        """The real paper size (what prints): tall on a sheet turned a quarter turn."""
        w, h = SHEET_SIZES[self.size]
        return (h, w) if self.rotation in (90, 270) else (w, h)

    @property
    def orientation(self):
        return "portrait" if self.rotation in (90, 270) else "landscape"

    # The border, zones and title block are laid out on the paper unturned (landscape, its
    # lower left corner at 0, 0) and then turned with the sheet: turn() takes a point of that
    # layout to the sheet, unturn() back
    def landscape_paper(self):
        w, h = SHEET_SIZES[self.size]
        k = self.k()
        return w * k, h * k

    def turn(self, x, y):
        r = self.rotation
        if not r:
            return x, y
        w, h = self.landscape_paper()
        if r == 90:
            return h - y, x
        if r == 180:
            return w - x, h - y
        return y, w - x

    def unturn(self, x, y):
        r = self.rotation
        if not r:
            return x, y
        w, h = self.landscape_paper()
        if r == 90:
            return y, h - x
        if r == 180:
            return w - x, h - y
        return w - y, x

    def turn_rect(self, rect):
        (ax, ay), (bx, by) = self.turn(rect[0], rect[1]), self.turn(rect[2], rect[3])
        return min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)

    def turn_offset(self):
        """(dx, dy): turning by `rotation` about (0, 0), then moving by this, is turn()."""
        w, h = self.landscape_paper()
        return {0: (0.0, 0.0), 90: (h, 0.0), 180: (w, h), 270: (0.0, w)}[self.rotation]

    def k(self):
        """Drawing units per paper inch: 1 on a 1:1 sheet, 4 on a 1:4 one."""
        return 1.0 / self.scale if self.scale > 0 else 1.0

    def scale_text(self):
        """The scale as written on the drawing: its preset's name, or 1:4."""
        if self.scale_name:
            return self.scale_name
        if abs(self.scale - 1.0) < 1e-12:
            return "1:1"
        inv = 1.0 / self.scale
        if abs(inv - round(inv)) < 1e-9:
            return "1:%d" % round(inv)
        return "%g:1" % self.scale if self.scale > 1 else "1:%g" % inv

    MARGIN = 0.375                      # paper edge to the border
    STRIP = 0.25                        # height/width of the zone label strips (top, left)

    def frame(self):
        """(x0, y0, x1, y1) of the drawing area, as turned."""
        return self.turn_rect(self.layout_frame())

    def zone_frame(self):
        """The part of the drawing area the zone grid covers, as turned."""
        return self.turn_rect(self.layout_zone_frame())

    def layout_frame(self):
        """(x0, y0, x1, y1) of the drawing area on the unturned layout: inside the border,
        below the column strip along the top and right of the row strip down the left (none
        on the right or bottom: they would only take room)."""
        w, h = self.landscape_paper()
        k = self.k()
        m, s = self.MARGIN * k, self.STRIP * k
        return (m + s, m, w - m, h - m - s)

    def layout_zone_frame(self):
        """The part of the drawing area the zone grid covers on the unturned layout: all of
        it, or what a title block strip down the right or along the bottom leaves."""
        x0, y0, x1, y1 = self.layout_frame()
        if self.reserve:
            side, size = self.reserve
            size *= self.k()
            if side == "right":
                x1 = max(x0 + (x1 - x0) * 0.2, x1 - size)
            elif side == "bottom":
                y0 = min(y1 - (y1 - y0) * 0.2, y0 + size)
        return x0, y0, x1, y1

    def zone_at(self, x, y):
        """(row letter, column number) of a point, or None outside the zone grid. Columns
        count left to right from col_start, rows top to bottom from the row_start letter
        (on the sheet as it is laid out: turned, they turn with it)."""
        x, y = self.unturn(x, y)
        x0, y0, x1, y1 = self.layout_zone_frame()
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            return None
        col = min(self.cols - 1, int((x - x0) / ((x1 - x0) / self.cols)))
        row = min(self.rows - 1, int((y1 - y) / ((y1 - y0) / self.rows)))
        return self.row_labels()[row], self.col_labels()[col]

    def col_labels(self):
        return [self.col_start + i for i in range(self.cols)]

    def row_labels(self):
        return row_letters(self.rows, self.row_start)

    # ---- entities --------------------------------------------------------------------------
    def new_id(self):
        eid = self._next
        self._next += 1
        return eid

    def _put(self, ent):
        if ent.id is None:
            ent.id = self.new_id()
        else:
            self._next = max(self._next, int(ent.id) + 1)
        old = self.entities.get(ent.id)
        if old is not None:
            self.index.remove(ent.id)
        self.entities[ent.id] = ent
        self.index.add(ent)
        self.version += 1
        self.touched.add(ent.id)

    def _drop(self, eid):
        if eid in self.entities:
            del self.entities[eid]
            self.index.remove(eid)
            self.version += 1
            self.touched.add(eid)

    def wires(self):
        """The wires on this sheet (kept per sheet version, as inserts())."""
        got = getattr(self, "_wires", None)
        if got is None or got[0] != self.version:
            got = self._wires = (self.version, [e for e in self.entities.values()
                                                if isinstance(e, Wire)])
        return got[1]

    def inserts(self):
        """The block references on this sheet (kept per sheet version: tags, contacts and
        cross-references read them without walking every line)."""
        got = getattr(self, "_inserts", None)
        if got is None or got[0] != self.version:
            got = self._inserts = (self.version, [e for e in self.entities.values()
                                                  if isinstance(e, Insert)])
        return got[1]

    def query(self, rect):
        """Entities whose box may touch rect."""
        ents = self.entities
        return [ents[i] for i in self.index.query(rect) if i in ents]

    def query_point(self, p, tol=1e-6):
        """Entities whose box may hold a point within tol of p (faster than query for a
        point: usually one cell)."""
        ents = self.entities
        return [ents[i] for i in self.index.query_point(p, tol) if i in ents]

    def extents(self):
        bb = None
        for e in self.entities.values():
            bb = G.bbox_union(bb, e.bbox())
        return bb

    # ---- storing ---------------------------------------------------------------------------
    def meta_dict(self):
        return {"id": self.id, "title": self.title, "size": self.size, "cols": self.cols,
                "rows": self.rows, "col_start": self.col_start, "row_start": self.row_start,
                "own_layout": self.own_layout, "kind": self.kind,
                "number_order": self.number_order,
                "number": self.number, "fields": dict(self.fields),
                "scale": self.scale, "scale_name": self.scale_name,
                "rotation": self.rotation,
                "cabinet": list(self.cabinet) if self.cabinet else None,
                "xref_frozen": self.xref_frozen,
                "xref_shown": [list(t) for t in self.xref_shown]
                if self.xref_shown is not None else None}

    def to_dict(self):
        d = self.meta_dict()
        d["entities"] = [e.to_dict() for e in self.entities.values()]
        return d

    def set_meta(self, d):
        self.title = d.get("title", "")
        self.size = d.get("size", DEFAULT_SIZE)
        if self.size not in SHEET_SIZES:
            self.size = DEFAULT_SIZE
        self.cols = int(d.get("cols", 10))
        self.rows = int(d.get("rows", 8))
        self.col_start = int(d.get("col_start", 1))
        self.row_start = int(d.get("row_start", 0))
        self.own_layout = bool(d.get("own_layout", False))
        self.kind = d.get("kind", "schematic") if d.get("kind") in SHEET_KINDS else "schematic"
        self.number_order = "down" if d.get("number_order") == "down" else "across"
        self.number = d.get("number")
        self.fields = dict(d.get("fields", {}) or {})
        try:
            self.scale = float(d.get("scale", 1.0)) or 1.0
        except (TypeError, ValueError):
            self.scale = 1.0
        self.scale = self.scale if self.scale > 0 else 1.0
        self.scale_name = str(d.get("scale_name", "") or "")
        try:
            r = int(round(float(d.get("rotation", 0) or 0))) % 360
        except (TypeError, ValueError):
            r = 0
        self.rotation = r if r in (0, 90, 180, 270) else 0
        self.cabinet = _cabinet(d.get("cabinet"))
        self.xref_frozen = bool(d.get("xref_frozen", False))
        shown = d.get("xref_shown")
        self.xref_shown = [tuple(t) for t in shown] if shown is not None else None
        self.version += 1

    @classmethod
    def from_dict(cls, d, blocks=None):
        s = cls(id=d.get("id"))
        s.set_meta(d)
        for ed in d.get("entities", []):
            s._put(Entity.from_dict(ed, blocks))
        return s


def today_text():
    """Today's date as US drawings write it: 11/05/2026."""
    import datetime
    return datetime.date.today().strftime("%m/%d/%Y")


def next_revision(revisions):
    """The number the next revision gets: 0 for the first, then one more than the highest
    number so far (a revision typed as a letter is skipped over)."""
    nums = []
    for r in revisions:
        try:
            nums.append(int(str(r.get("rev", "")).strip()))
        except ValueError:
            pass
    return str(max(nums) + 1) if nums else ("0" if not revisions else str(len(revisions)))


def clean_revision(r):
    """A revision as stored: rev, date, desc, by, and sheets (None: every sheet, else the
    ids of the sheets it revised)."""
    sheets = r.get("sheets")
    return {"rev": str(r.get("rev", "")), "date": str(r.get("date", "")),
            "desc": str(r.get("desc", "")), "by": str(r.get("by", "")),
            "sheets": None if sheets is None else [int(i) for i in sheets]}


PROJECT_FIELDS = ["Customer", "Project", "Drawing number", "Drawn by", "Drawn date",
                  "Checked by", "Date",
                  "Revision"]


class Edit:
    """One undoable step: what each touched entity (or sheet) was before and after."""

    def __init__(self, project, name):
        self.project = project
        self.name = name
        self.ops = []           # ("ent", sheet_id, eid, before, after) | ("sheet", ...)
        self._seen = {}
        self.pin_moves = []     # (sheet, {pin: old point}, {pin: new point}) of moved symbols

    def _remember(self, sheet, eid):
        key = (sheet.id, eid)
        if key not in self._seen:
            old = sheet.entities.get(eid)
            op = ["ent", sheet.id, eid, old.to_dict() if old else None, None]
            self._seen[key] = op
            self.ops.append(op)
        return self._seen[key]

    def add(self, sheet, ent):
        if ent.id is None:
            ent.id = sheet.new_id()
        old = sheet.entities.get(ent.id)
        if isinstance(old, Insert) and isinstance(ent, Insert):
            self.pin_moves.append((sheet, dict(old.pin_points()), dict(ent.pin_points())))
        op = self._remember(sheet, ent.id)
        sheet._put(ent)
        op[4] = ent.to_dict()
        return ent

    def change(self, sheet, ent):
        """Replace the entity with the same id."""
        return self.add(sheet, ent)

    def remove(self, sheet, eid):
        if eid not in sheet.entities:
            return
        op = self._remember(sheet, eid)
        sheet._drop(eid)
        op[4] = None

    def sheet_meta(self, sheet, **changes):
        before = sheet.meta_dict()
        after = dict(before)
        after.update(changes)
        sheet.set_meta(after)
        self.ops.append(["meta", sheet.id, before, after])

    def sheet_scale(self, sheet, scale, name=""):
        """Give a sheet another scale. The drawing stays real size; texts, tags and
        dimensions are paper-sized, so their heights follow (they print the same size)."""
        old_k = sheet.k()
        self.sheet_meta(sheet, scale=float(scale), scale_name=name)
        f = sheet.k() / old_k
        if abs(f - 1.0) < 1e-12:
            return
        for e in list(sheet.entities.values()):
            if isinstance(e, Text):
                self.change(sheet, e.copy(height=e.height * f))
            elif isinstance(e, (Dimension, Leader)):
                self.change(sheet, e.copy(height=e.height * f))
            elif isinstance(e, Insert) and e.tag_h:
                self.change(sheet, e.copy(tag_h=e.tag_h * f))

    def add_sheet(self, sheet, index=None):
        p = self.project
        if sheet.id is None:
            sheet.id = p.new_sheet_id()
        index = len(p.sheets) if index is None else index
        p.sheets.insert(index, sheet)
        self.ops.append(["sheet", index, None, sheet.to_dict()])
        return sheet

    def remove_sheet(self, sheet):
        p = self.project
        index = p.sheets.index(sheet)
        self.ops.append(["sheet", index, sheet.to_dict(), None])
        p.sheets.pop(index)

    def move_sheet(self, old, new):
        p = self.project
        s = p.sheets.pop(old)
        p.sheets.insert(new, s)
        self.ops.append(["order", old, new])

    def project_fields(self, fields, zone_format=None):
        p = self.project
        before = (dict(p.fields), p.zone_format)
        after = (dict(fields), zone_format or p.zone_format)
        p.fields, p.zone_format = dict(after[0]), after[1]
        for s in p.sheets:
            s.version += 1
        self.ops.append(["fields", before, after])

    def project_revisions(self, revisions):
        """Replace the project's revision history (Revisions...): the title blocks follow."""
        p = self.project
        before = [dict(r) for r in p.revisions]
        after = [clean_revision(r) for r in revisions]
        p.revisions = [dict(r) for r in after]
        for s in p.sheets:
            s.version += 1
        self.ops.append(["revisions", before, after])

    def project_settings(self, settings):
        """Change the project's settings. Sheets that follow the project take its new size
        and zones, and tags take its new tag height (each change undoable with this step)."""
        p = self.project
        before, after = dict(p.settings), dict(p.settings)
        after.update(settings)
        p.settings = dict(after)
        self.ops.append(["settings", before, after])
        layout = {k: after[k] for k in LAYOUT_KEYS}
        for s in p.sheets:
            if not s.own_layout and any(s.meta_dict().get(k) != v for k, v in layout.items()):
                self.sheet_meta(s, **layout)
        if after["tag_height"] != before["tag_height"]:
            for s in p.sheets:
                for e in list(s.entities.values()):
                    if isinstance(e, Insert) and e.defn is not None and e.defn.kind == "symbol":
                        self.change(s, e.copy(tag_h=after["tag_height"]))
                    elif isinstance(e, Insert) and e.label:
                        # a footprint's label: paper-sized, as the tags
                        self.change(s, e.copy(tag_h=after["tag_height"] * s.k()))

    def block(self, defn):
        """Put a block definition in the project (or replace the one of that name); block
        references to it then show it."""
        p = self.project
        old = p.blocks.get(defn.name)
        self.ops.append(["block", defn.name, old.to_dict() if old else None, defn.to_dict()])
        p._set_block(defn.name, defn.to_dict())

    def drop_block(self, name):
        """Take a block definition out of the project (its references, if any are left, show
        an X where they sit)."""
        p = self.project
        old = p.blocks.get(name)
        if old is None:
            return
        self.ops.append(["block", name, old.to_dict(), None])
        p._set_block(name, None)

    def layer(self, name, before, after):
        """before/after: a Layer's dict, or None (added / removed)."""
        self.project._set_layer(name, after)
        self.ops.append(["layer", name, before, after])

    def __bool__(self):
        return bool(self.ops)


class Project:
    def __init__(self):
        self.path = None
        self.fields = {k: "" for k in PROJECT_FIELDS}
        self.zone_format = "{sheet}-{row}{col}"
        self.settings = dict(DEFAULT_SETTINGS)
        # the revision history (Revisions...), oldest first: [{rev, date, desc, by, sheets}]
        self.revisions = []
        self.layers = {}
        for name, color in DEFAULT_LAYERS:
            self.layers[name] = Layer(name, color)
        self.sheets = []
        self._next_sheet = 1
        # the title block: a drawing of its own (lines and texts, edited like any sheet with
        # Edit title block), drawn on every sheet with its {fields} filled in
        self.title_block = Sheet(title="Title block", id=TITLE_BLOCK_ID)
        # the blocks (symbols, footprints) this project uses: its own copies, so it opens the
        # same anywhere, whatever happens to the library later
        self.blocks = {}
        self.undo_stack = []
        self.redo_stack = []
        self.saved_at = 0           # len(undo_stack) when last saved (or -1: never matches)
        self.listeners = []         # called with no arguments after each change
        self.revision = 0           # counts the changes (edits, undo, redo): the views keep a
                                    # picture of the drawing until it moves on

    def make_sheet(self, title=""):
        """A new sheet laid out as the project says (not yet in the project)."""
        st = self.settings
        s = Sheet(title=title, size=st["size"], cols=st["cols"], rows=st["rows"],
                  col_start=st["col_start"], row_start=st["row_start"])
        s.reserve = self.reserve()
        return s

    @classmethod
    def new(cls):
        p = cls()
        s = p.make_sheet("Sheet 1")
        s.id = p.new_sheet_id()
        p.sheets.append(s)
        p._default_title_block()
        p.fields["Drawn date"] = today_text()     # (started today; Project properties changes it)
        return p

    def _default_title_block(self):
        from .sheetframe import default_title_block
        tb = self.title_block
        for e in default_title_block(tb):
            tb._put(e)
        tb.touched = set()

    def new_sheet_id(self):
        n = self._next_sheet
        self._next_sheet += 1
        return n

    # ---- sheets ----------------------------------------------------------------------------
    def sheet_by_id(self, sid):
        if sid == TITLE_BLOCK_ID:
            return self.title_block
        for s in self.sheets:
            if s.id == sid:
                return s
        return None

    def sheet_number(self, sheet):
        """The sheet's page number: its own if set, else its position (1, 2, ...)."""
        if sheet is self.title_block:
            return ""
        if sheet.number not in (None, ""):
            return str(sheet.number)
        return str(self.sheets.index(sheet) + 1)

    def zone_text(self, sheet, x, y):
        if sheet is self.title_block:
            return ""
        z = sheet.zone_at(x, y)
        if z is None:
            return ""
        return self.zone_format.format(sheet=self.sheet_number(sheet), row=z[0], col=z[1])

    # ---- layers ----------------------------------------------------------------------------
    def layer_color(self, name):
        lay = self.layers.get(name)
        return lay.color if lay else ADAPTIVE

    def ensure_layer(self, name):
        if name not in self.layers:
            self.layers[name] = Layer(name)
        return self.layers[name]

    def _set_block(self, name, d):
        """Set (d a BlockDef dict) or remove (None) a block, and re-point every reference to
        it (their drawing changes: they are put again so caches and indexes follow)."""
        if d is None:
            self.blocks.pop(name, None)
            defn = None
        else:
            defn = BlockDef.from_dict(d)
            self.blocks[name] = defn
        for s in self.sheets + [self.title_block]:
            for e in list(s.entities.values()):
                if isinstance(e, Insert) and e.block == name:
                    c = e.copy()
                    c.defn = defn
                    s._put(c)

    def _set_layer(self, name, d):
        if d is None:
            self.layers.pop(name, None)
        else:
            lay = Layer.from_dict(d)
            if name != lay.name:
                self.layers.pop(name, None)
            self.layers[lay.name] = lay
        for s in self.sheets + [self.title_block]:
            s.version += 1

    # ---- editing ---------------------------------------------------------------------------
    def edit(self, name):
        return _EditContext(self, name)

    def _commit(self, ed):
        if not ed:
            return
        self.undo_stack.append(ed)
        if self.saved_at > len(self.undo_stack) - 1:
            self.saved_at = -1              # the saved state can't be reached by redo anymore
        self.redo_stack.clear()
        self._changed()

    def _changed(self):
        self.revision += 1
        self.sync_reserve()
        for f in list(self.listeners):
            f()

    def reserve(self):
        """The title block strip the zones stop at, ("right" | "bottom", paper inches), or None
        (title block in the corner)."""
        pos = self.settings.get("tb_position", "corner")
        if pos not in ("right", "bottom"):
            return None
        bb = self.title_block.extents()
        if bb is None:
            return None
        x0, y0, x1, _y1 = self.title_block.frame()
        size = (x1 - bb[0]) if pos == "right" else (bb[3] - y0)
        return (pos, max(0.0, size)) if size > 1e-6 else None

    def sync_reserve(self):
        """Every sheet's zone grid stops at the title block strip (when there is one)."""
        r = self.reserve()
        for s in self.sheets:
            if s.reserve != r:
                s.reserve = r
                s.version += 1

    def is_modified(self):
        return self.saved_at != len(self.undo_stack)

    def _apply(self, ops, undo):
        seq = reversed(ops) if undo else ops
        for op in seq:
            kind = op[0]
            if kind == "ent":
                _k, sid, eid, before, after = op
                s = self.sheet_by_id(sid)
                d = before if undo else after
                if s is None:
                    continue
                if d is None:
                    s._drop(eid)
                else:
                    s._put(Entity.from_dict(d, self.blocks))
            elif kind == "meta":
                _k, sid, before, after = op
                s = self.sheet_by_id(sid)
                if s is not None:
                    s.set_meta(before if undo else after)
            elif kind == "sheet":
                _k, index, before, after = op
                d = before if undo else after
                if d is None:
                    s = self.sheet_by_id((after if undo else before)["id"])
                    if s is not None:
                        self.sheets.remove(s)
                else:
                    self.sheets.insert(index, Sheet.from_dict(d, self.blocks))
            elif kind == "order":
                _k, old, new = op
                a, b = (new, old) if undo else (old, new)
                s = self.sheets.pop(a)
                self.sheets.insert(b, s)
            elif kind == "fields":
                f, z = op[1] if undo else op[2]
                self.fields, self.zone_format = dict(f), z
                for s in self.sheets:
                    s.version += 1
            elif kind == "settings":
                self.settings = dict(op[1] if undo else op[2])
            elif kind == "revisions":
                self.revisions = [dict(r) for r in (op[1] if undo else op[2])]
                for s in self.sheets:
                    s.version += 1
            elif kind == "block":
                _k, name, before, after = op
                self._set_block(name, before if undo else after)
            elif kind == "layer":
                _k, name, before, after = op
                d = before if undo else after
                other = after if undo else before
                if d is None:
                    self._set_layer(other["name"] if other else name, None)
                else:
                    if other is not None and other["name"] != d["name"]:
                        self.layers.pop(other["name"], None)
                    self._set_layer(d["name"], d)

    def undo(self):
        if not self.undo_stack:
            return None
        ed = self.undo_stack.pop()
        self._apply(ed.ops, undo=True)
        self.redo_stack.append(ed)
        self._changed()
        return ed.name

    def redo(self):
        if not self.redo_stack:
            return None
        ed = self.redo_stack.pop()
        self._apply(ed.ops, undo=False)
        self.undo_stack.append(ed)
        self._changed()
        return ed.name

    # ---- storing ---------------------------------------------------------------------------
    def to_dict(self):
        return {"format": FORMAT, "version": FORMAT_VERSION, "fields": dict(self.fields),
                "zone_format": self.zone_format, "settings": dict(self.settings),
                "layers": [lay.to_dict() for lay in self.layers.values()],
                "title_block": [e.to_dict() for e in self.title_block.entities.values()],
                "blocks": [b.to_dict() for b in self.blocks.values()],
                "sheets": [s.to_dict() for s in self.sheets]} | (
                    {"revisions": [dict(r) for r in self.revisions]} if self.revisions else {})

    @classmethod
    def from_dict(cls, d):
        if d.get("format") != FORMAT:
            raise ValueError("not a KanzonasCAD project")
        if int(d.get("version", 1)) > FORMAT_VERSION:
            raise ValueError("this project was saved by a newer KanzonasCAD")
        p = cls()
        p.fields.update(d.get("fields", {}) or {})
        p.revisions = [clean_revision(r) for r in d.get("revisions", []) or []]
        p.zone_format = d.get("zone_format", p.zone_format)
        p.settings.update(d.get("settings", {}) or {})
        if d.get("layers"):
            p.layers = {}
            for ld in d["layers"]:
                lay = Layer.from_dict(ld)
                p.layers[lay.name] = lay
        for bd in d.get("blocks", []) or []:
            b = BlockDef.from_dict(bd)
            p.blocks[b.name] = b
        for sd in d.get("sheets", []):
            s = Sheet.from_dict(sd, p.blocks)
            if s.id is None:
                s.id = p.new_sheet_id()
            p._next_sheet = max(p._next_sheet, int(s.id) + 1)
            p.sheets.append(s)
            for e in s.entities.values():
                p.ensure_layer(e.layer)
        if not p.sheets:
            p.sheets.append(Sheet(title="Sheet 1", id=p.new_sheet_id()))
        if "title_block" in d:
            for ed in d["title_block"]:
                e = Entity.from_dict(ed, p.blocks)
                p.title_block._put(e)
                p.ensure_layer(e.layer)
            p.title_block.touched = set()
        else:
            p._default_title_block()
        p.sync_reserve()
        return p

    def save(self, path, backups=None):
        """Write the project to path (a whole new file swapped in, so a crash can't leave
        half a file). backups: how many earlier saves to keep beside it (backup.KEEP)."""
        from . import backup
        data = json.dumps(self.to_dict(), separators=(",", ":"))
        backup.make_backup(path, backup.KEEP if backups is None else backups)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        self.path = path
        self.saved_at = len(self.undo_stack)

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            p = cls.from_dict(json.load(f))
        p.path = path
        return p


class _EditContext:
    def __init__(self, project, name):
        self.ed = Edit(project, name)

    def __enter__(self):
        return self.ed

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            # put back what this failed step had already changed
            self.ed.project._apply(self.ed.ops, undo=True)
            return False
        try:
            if self.ed.pin_moves:
                from .wires import follow_pins
                follow_pins(self.ed)
            sheets = any(op[0] in ("sheet", "order", "meta") for op in self.ed.ops)
            if sheets:
                # sheets added, removed, moved or renumbered: device tags follow their pages
                from .tags import sync_pages
                sync_pages(self.ed, self.ed.project)
            kinds = set()
            for op in self.ed.ops:
                if op[0] == "ent":
                    kinds.add((op[3] or {}).get("kind"))
                    kinds.add((op[4] or {}).get("kind"))
            if sheets or "insert" in kinds:
                # a device added, removed or retagged: its contacts show its tag
                from .tags import sync_children
                sync_children(self.ed, self.ed.project)
            if sheets or "insert" in kinds or "wire" in kinds or any(
                    op[0] == "settings" for op in self.ed.ops):
                # wires drawn, cut, joined or moved, symbols placed on them: wire numbers
                from .wirenums import sync as number_wires
                number_wires(self.ed, self.ed.project)
        except Exception:
            self.ed.project._apply(self.ed.ops, undo=True)
            raise
        self.ed.project._commit(self.ed)
        return False
