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
]

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
    def from_dict(d):
        cls = _KINDS.get(d.get("kind"))
        if cls is None:
            raise ValueError("unknown entity kind %r" % d.get("kind"))
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

    def _compute_snaps(self):
        out = [("end", p) for p in self.points]
        for a, b in self.segments():
            out.append(("mid", ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)))
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


@_register
class Text(Entity):
    """One line of text. pos is the insertion point on the baseline; align: left, center or
    right of pos."""
    kind = "text"
    __slots__ = ("pos", "text", "height", "angle", "align")

    def __init__(self, pos, text, height=0.125, angle=0.0, align="left", **kw):
        super().__init__(**kw)
        self.pos = _pt(pos)
        self.text = str(text)
        self.height = float(height)
        self.angle = float(angle) % 360.0
        self.align = align if align in ("left", "center", "right") else "left"

    def _data(self):
        return {"pos": list(self.pos), "text": self.text, "height": self.height,
                "angle": self.angle, "align": self.align}

    @classmethod
    def _from(cls, d):
        return cls(d["pos"], d.get("text", ""), d.get("height", 0.125), d.get("angle", 0.0),
                   d.get("align", "left"), layer=d.get("layer", "0"), color=d.get("color"),
                   id=d.get("id"))

    def width(self):
        return text_width(self.text, self.height)

    def corners(self):
        """The text's box (baseline to cap height), rotated."""
        w, h = self.width(), self.height
        x0 = {"left": 0.0, "center": -w / 2, "right": -w}[self.align]
        local = [(x0, 0.0), (x0 + w, 0.0), (x0 + w, h), (x0, h)]
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


def row_letters(n):
    """A, B, ... Z, AA, AB ... for n rows."""
    out = []
    for i in range(n):
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


TITLE_BLOCK_ID = 0          # the project's title block is kept as a sheet with this id


class Sheet:
    def __init__(self, title="", size=DEFAULT_SIZE, cols=10, rows=6, number=None, id=None,
                 fields=None):
        self.id = id
        self.title = title
        self.size = size if size in SHEET_SIZES else DEFAULT_SIZE
        self.cols = int(cols)
        self.rows = int(rows)
        self.number = number            # None: its position in the project
        self.fields = dict(fields or {})
        self.entities = {}              # id -> Entity, in drawing order
        self._next = 1
        self.index = SpatialIndex()
        self.version = 0                # bumped on every change (render caches key on it)
        self.touched = set()            # ids changed since the screen renderer last looked

    # ---- size, border, zones -------------------------------------------------------------
    def paper(self):
        return SHEET_SIZES[self.size]

    MARGIN = 0.375                      # paper edge to the border
    STRIP = 0.25                        # height/width of the zone label strips (top, left)

    def frame(self):
        """(x0, y0, x1, y1) of the drawing area: inside the border, below the column strip
        along the top and right of the row strip down the left (none on the right or
        bottom: they would only take room)."""
        w, h = self.paper()
        m, s = self.MARGIN, self.STRIP
        return (m + s, m, w - m, h - m - s)

    def zone_at(self, x, y):
        """(row letter, column number) of a point, or None outside the drawing area. Columns
        count left to right from 1, rows top to bottom from A."""
        x0, y0, x1, y1 = self.frame()
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            return None
        col = min(self.cols, int((x - x0) / ((x1 - x0) / self.cols)) + 1)
        row = min(self.rows - 1, int((y1 - y) / ((y1 - y0) / self.rows)))
        return row_letters(self.rows)[row], col

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

    def query(self, rect):
        """Entities whose box may touch rect."""
        ents = self.entities
        return [ents[i] for i in self.index.query(rect) if i in ents]

    def extents(self):
        bb = None
        for e in self.entities.values():
            bb = G.bbox_union(bb, e.bbox())
        return bb

    # ---- storing ---------------------------------------------------------------------------
    def meta_dict(self):
        return {"id": self.id, "title": self.title, "size": self.size, "cols": self.cols,
                "rows": self.rows, "number": self.number, "fields": dict(self.fields)}

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
        self.rows = int(d.get("rows", 6))
        self.number = d.get("number")
        self.fields = dict(d.get("fields", {}) or {})
        self.version += 1

    @classmethod
    def from_dict(cls, d):
        s = cls(id=d.get("id"))
        s.set_meta(d)
        for ed in d.get("entities", []):
            s._put(Entity.from_dict(ed))
        return s


PROJECT_FIELDS = ["Customer", "Project", "Drawing number", "Drawn by", "Checked by", "Date",
                  "Revision"]


class Edit:
    """One undoable step: what each touched entity (or sheet) was before and after."""

    def __init__(self, project, name):
        self.project = project
        self.name = name
        self.ops = []           # ("ent", sheet_id, eid, before, after) | ("sheet", ...)
        self._seen = {}

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
        self.layers = {}
        for name, color in DEFAULT_LAYERS:
            self.layers[name] = Layer(name, color)
        self.sheets = []
        self._next_sheet = 1
        # the title block: a drawing of its own (lines and texts, edited like any sheet with
        # Edit title block), drawn on every sheet with its {fields} filled in
        self.title_block = Sheet(title="Title block", id=TITLE_BLOCK_ID)
        self.undo_stack = []
        self.redo_stack = []
        self.saved_at = 0           # len(undo_stack) when last saved (or -1: never matches)
        self.listeners = []         # called with no arguments after each change

    @classmethod
    def new(cls):
        p = cls()
        s = Sheet(title="Sheet 1", id=p.new_sheet_id())
        p.sheets.append(s)
        p._default_title_block()
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
        for f in list(self.listeners):
            f()

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
                    s._put(Entity.from_dict(d))
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
                    self.sheets.insert(index, Sheet.from_dict(d))
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
                "zone_format": self.zone_format,
                "layers": [lay.to_dict() for lay in self.layers.values()],
                "title_block": [e.to_dict() for e in self.title_block.entities.values()],
                "sheets": [s.to_dict() for s in self.sheets]}

    @classmethod
    def from_dict(cls, d):
        if d.get("format") != FORMAT:
            raise ValueError("not a KanzonasCAD project")
        if int(d.get("version", 1)) > FORMAT_VERSION:
            raise ValueError("this project was saved by a newer KanzonasCAD")
        p = cls()
        p.fields.update(d.get("fields", {}) or {})
        p.zone_format = d.get("zone_format", p.zone_format)
        if d.get("layers"):
            p.layers = {}
            for ld in d["layers"]:
                lay = Layer.from_dict(ld)
                p.layers[lay.name] = lay
        for sd in d.get("sheets", []):
            s = Sheet.from_dict(sd)
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
                e = Entity.from_dict(ed)
                p.title_block._put(e)
                p.ensure_layer(e.layer)
            p.title_block.touched = set()
        else:
            p._default_title_block()
        return p

    def save(self, path):
        data = json.dumps(self.to_dict(), separators=(",", ":"))
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
        self.ed.project._commit(self.ed)
        return False
