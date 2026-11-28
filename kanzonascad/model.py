"""The drawing model: a project of sheets, each sheet a set of entities on layers.

No Qt here: the model can be loaded, edited, checked and exported in tests and the self-test
without a window.

Entities are treated as values: a change replaces the entity with a changed copy (same id)
through an Edit, which records before/after for Undo. Anything cached on an entity object
(its bounding box, snap points) therefore never goes stale.
"""

import re
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
    # the cross-references' text (a coil's contacts, a contact's coil, the other end of a
    # connector or arrow): a layer of its own, cyan (the owner, 0.18: "Cross reference labels
    # need to be a different layer by default. And a different color")
    ("XREFS", "#00e5ff"),
]
XREF_HEIGHT_BEFORE_018 = 0.08   # (see Project.from_dict: such projects take the new 0.065)
# (a project from before 0.18.1 has no fp_label_height: its footprints' labels were the tag
# height; they take the new, smaller one: the owner, "I also think the footprint font is too
# big")

# the project's own settings (Project properties); sheets that follow the project take the
# layout ones (size, zones) from here
DEFAULT_SETTINGS = {
    "text_height": 0.125,       # new text
    "tag_height": 0.1,          # device tags on symbols
    # the symbols Insert symbol offers: "jic" (JIC/NFPA, US) or "iec" (IEC 60617): a project's
    # own (Project properties, Schematic; 0.29); every project from before is JIC
    "symbol_standard": "jic",
    "fp_label_height": 0.08,    # what footprints show on them, paper inches (0.1 before 0.18.1)
    "fp_label_color": "",       # their color ("": the footprint's; the owner, 0.18.7: a
                                # footprint on layer 0 is white, "I want the tagname to be
                                # discernible")
    # devices without a footprint marked orange on the drawing (missing_fp.py; 0.25)
    "fp_missing_marks": True,
    # footprint terminals' wire labels (Terminal wire labels: panelwiring.py; 0.28), paper
    # inches
    "fp_wire_label_height": 0.05,
    "size": "ANSI B (17 x 11)",
    "cols": 10, "rows": 8, "col_start": 1, "row_start": 0,
    "xref_auto": True,          # cross-references follow every change (else: Update command)
    "wire_order_tags": True,    # wire numbers in the tags' numbering order (else across/down)
    "duct_hatch": False,        # wire duct drawn with a light hatch (Panel settings)
    "xref_height": 0.065,       # cross-reference text (0.08 before 0.18: "slightly smaller")
    "wire_numbers": True,       # wires numbered by themselves (wirenums.py)
    "wire_numbers_io": False,   # wires on PLC input/output points take the point's address
    # a wire tapped off another (its end on the other's middle): "same" its number, "suffix"
    # its number with -1, -2... in the numbering order (a tap off a tap: a, b...), "own" a
    # number of its own (the owner, 0.18.3: "all three wires tapping off the bus are still
    # the same wire number ... Those need to change where they tap off"; asked: -1, -2 per
    # tap in order, on to start; a project from before keeps "same")
    "tap_numbers": "suffix",
    "wire_number_height": 0.08,
    "dim_height": 0.1,          # dimension text, paper inches
    # the border with its zones and the title block drawn and printed on every sheet that
    # doesn't say otherwise (Sheet properties; the owner, 0.18.4: "turn the title block and/or
    # grid off and on, for the whole project and for individual sheets")
    "show_border": True,
    # how a device's place is given (cross-references, reports, the status bar): "grid" its
    # zone (6-D1), or "ladder" the rung it is on (603), a sheet can choose otherwise (Sheet
    # properties; the owner, 0.22: "Let's do ladder references as an option"); rung numbers
    # "hundreds" (the page times 100 on: 600, 601...) or "prefix" (the page, a dash, the rung:
    # 6-01, 6-02...); a new ladder's rungs this far apart (paper inches)
    "referencing": "grid",
    # a tap's suffix (tap_numbers "suffix"): "-1" (6001-1, 6001-2), "a" (6001a, 6001b) or "-a"
    # (6001-a, 6001-b); a tap off a tap the other kind (6001-1a, 6001a1, 6001-a1); a sheet and a
    # wire can choose otherwise (the owner, 0.22.4: "In addition to -1, can we add a, b, c, etc
    # for wire taps? Also -a, -b, -c, etc. This would be a project wide setting, able to be
    # overridden by sheet and by wire")
    "tap_style": "-1",
    # a wire layer's gauge label shows its insulation color too (14 AWG BLU) on every wire that
    # doesn't say otherwise (Wire color label; the owner, 0.22.4, "These wire colors aren't
    # showing. None of them have it in the whole project")
    "wire_color_shown": False,
    "ladder_numbers": "hundreds",
    "ladder_spacing": 0.5,
    # new dimensions read decimal (12.50") or fractional to the nearest 1/16 (1-9/16"): "decimal",
    # "1/8", "1/16", "1/32", "1/64"; each dimension keeps its own (Dimension units)
    "dim_units": "decimal",
    "show_title_block": True,
    # source and destination arrows show the device at their wire's other end under their
    # reference; a sheet (Sheet properties) or an arrow (its attributes) can say otherwise
    "xref_device": True,
    # the scale a new sheet starts at, by its kind (paper / real, its preset's name or ""):
    # panel sheets theirs, every other kind the schematic one; a sheet's own scale (Sheet
    # scale, Sheet properties) is its own afterward (the owner, 0.19.4: "a project default
    # for scale, which can be overridden on individual sheets"; new sheets only)
    "scale_schematic": [1.0, ""],
    "scale_panel": [1.0, ""],
    "tb_position": "corner",    # the title block: in the lower right corner, or a strip down
                                # the right ("right") or along the bottom ("bottom") that the
                                # zone grid stops at
    "wire_cleanup": True,       # wires cleaned up as they're drawn (wires.tidy_new)
    "wire_gauge_shown": True,   # a wire layer's gauge and color beside its wires
    # the layer new wires go on, on every sheet that hasn't one of its own (Sheet properties,
    # or picked on the Schematic tab); the owner, 0.21: "every time I reopen the project, the
    # layer I had selected reverts", for the project and per sheet
    "wire_layer": "WIRES",
    "wire_gauge_height": 0.06,  # gauge labels' text, paper inches (wire numbers: 0.08)
    "wire_gauge_each": "group",  # once for wires side by side alike ("group"), or "each" run
    "footprint_label": "tag",   # what a footprint placed shows to start (Footprint label)
    "wire_around": True,        # a wire goes round the symbols in its way (wires.route_around)
    "wire_clear": 0.125,        # ...that far from them, paper inches
    "wire_layer_auto": True,    # a wire started on a PLC point, a motor's or drive's terminal...
                                # goes on its voltage's wire layer (autolayer.py; the owner, 0.22.1)
    "wire_lead": False,         # a second wire on a pin leaves it on a 45-degree lead (the
                                # owner, 0.16: "a little bend... That needs to go away": off)
    "wire_label_ends": 6.0,     # a wire longer than this (paper inches) shows its number
                                # near both ends (wirenums.labels; 0: off; the owner, 0.17.2)
    "wire_crossing": "loop",    # wires crossing: plain, gap or loop (crossings.py; a loop to
                                # start since 0.17.1, the owner: "wire crossings are still not
                                # being created automatically"; projects saved keep theirs)
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
    __slots__ = ("id", "layer", "color", "_bbox", "_snaps", "fixed")

    def __init__(self, layer="0", color=BYLAYER, id=None):
        self.id = id
        self.layer = layer
        self.color = color
        self._bbox = None
        self._snaps = None
        # drawing-sized: a text, multi-line text, dimension or leader brought in with a DXF or
        # DWG, sized for the drawing by the program that drew it: a new sheet scale leaves its
        # height as it is (KanzonasCAD's own are paper-sized and follow the scale)
        self.fixed = False

    # ---- storing -------------------------------------------------------------------------
    def to_dict(self):
        d = {"kind": self.kind, "id": self.id, "layer": self.layer}
        if self.color is not None:
            d["color"] = self.color
        if self.fixed:
            d["fixed"] = True
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
        e = cls._from(d, blocks or {}) if cls is Insert else cls._from(d)
        e.fixed = bool(d.get("fixed", False))
        return e

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
        """Its corners, then the middle of each side (the owner, 0.16: "I need a middle
        grabber on rectangles also, so I can resize it longer or shorter"). A wire has only
        its corners (Wire.grips)."""
        return list(self.points) + [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                                    for a, b in self.segments()]

    def with_grip(self, i, p):
        pts = [list(q) for q in self.points]
        n = len(self.points)
        if i < n:
            pts[i] = list(p)
            return self.copy(points=pts)
        # a side's middle: the side moves straight out or in by as far as the grip went across
        # it (a rectangle stays one: longer or shorter)
        k = i - n
        j = (k + 1) % n
        a, b = self.points[k], self.points[j]
        L = G.dist(a, b)
        if L < 1e-12:
            return self.copy(points=pts)
        nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        d = (p[0] - m[0]) * nx + (p[1] - m[1]) * ny
        pts[k] = [a[0] + nx * d, a[1] + ny * d]
        pts[j] = [b[0] + nx * d, b[1] + ny * d]
        return self.copy(points=pts)

    def _map(self, fn, **_kw):
        return self.copy(points=[list(fn(p)) for p in self.points])


# a tap's suffix styles: 6001-1, 6001a, 6001-a (Project properties, Sheet properties, Wire number)
TAP_STYLES = ("-1", "a", "-a")


@_register
class Wire(Polyline):
    """A wire: a polyline on layer WIRES whose ends attach to symbol pins, wire ends or other
    wires. What it connects is worked out from where its ends are (wires.py), never stored, so
    it can't go stale; moving a symbol drags the ends that sat on its pins."""
    kind = "wire"
    __slots__ = ("num", "num_lock", "own_num", "labels", "awg", "same_num", "show_color",
                 "pin_tap", "tap_style")

    def __init__(self, points, closed=False, num=None, num_lock=False, own_num=False,
                 labels=(), awg="", same_num=False, show_color=None, pin_tap=False,
                 tap_style="", **kw):
        kw.setdefault("layer", "WIRES")
        super().__init__(points, False, **kw)
        # its wire number (every wire of a connected group has the same: wirenums.py) and
        # whether it was typed (locked: numbering leaves it alone)
        self.num = str(num) if num else None
        self.num_lock = bool(num_lock) and bool(num)
        # a wire tapped off another (its end on the other's middle) with a number of its own:
        # not one group with it for numbering (the owner, 0.17.2: "when I tap off a wire, I
        # can either change the wire number or leave as is")
        self.own_num = bool(own_num)
        # a tap that keeps the number of the wire it taps whatever the project's tap numbers
        # (0.18.3: S at the tap's question; a branch of a ladder rung, say)
        self.same_num = bool(same_num) and not self.own_num
        # its number shown again at these distances along it from its first point (Wire
        # number label: placed by hand; the number they show is never stored, so never stale)
        self.labels = sorted(round(float(t), 6) for t in (labels or ()) if float(t) >= 0)
        # its own gauge (Wire size: "10", "2/0"), or "" for its layer's (the owner, 0.18.2:
        # "per wire, with the layer as default")
        self.awg = str(awg or "").strip()
        # its insulation color written in its gauge label too (Wire color label: the owner,
        # 0.18.4, "I don't think we need to include the wire color. Maybe that can be a
        # toggle-able option on a per-wire basis?")
        # (None: as the project, Project properties, Schematic, "...and its color"; 0.22.4)
        self.show_color = None if show_color is None else bool(show_color)
        # a second wire on a pin (a double landing) numbered as a tap off the wire already
        # there: as the project numbers taps, or its own same_num / own_num (the owner, 0.18.5:
        # "Give me the option each time, and changeable")
        self.pin_tap = bool(pin_tap)
        # as a tap, its suffix's style: "-1", "a" or "-a", or "" for its sheet's (TAP_STYLES)
        self.tap_style = tap_style if tap_style in TAP_STYLES else ""

    def _data(self):
        d = super()._data()
        if self.num:
            d["num"] = self.num
            if self.num_lock:
                d["num_lock"] = True
        if self.own_num:
            d["own_num"] = True
        if self.same_num:
            d["same_num"] = True
        if self.labels:
            d["labels"] = list(self.labels)
        if self.awg:
            d["awg"] = self.awg
        if self.show_color is not None:
            d["show_color"] = self.show_color
        if self.pin_tap:
            d["pin_tap"] = True
        if self.tap_style:
            d["tap_style"] = self.tap_style
        return d

    @classmethod
    def _from(cls, d):
        return cls(d["points"], False, d.get("num"), d.get("num_lock", False),
                   d.get("own_num", False), d.get("labels") or (), d.get("awg", ""),
                   d.get("same_num", False), d.get("show_color"),
                   d.get("pin_tap", False), d.get("tap_style", ""),
                   layer=d.get("layer", "WIRES"), color=d.get("color"), id=d.get("id"))

    def length(self):
        return sum(G.dist(a, b) for a, b in zip(self.points, self.points[1:]))

    def at_length(self, t):
        """(point, piece index) at distance t along it from its first point (held to its
        ends)."""
        t = max(0.0, t)
        for k, (a, b) in enumerate(zip(self.points, self.points[1:])):
            L = G.dist(a, b)
            if t <= L or k == len(self.points) - 2:
                f = min(1.0, t / L) if L > 0 else 0.0
                return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f), k
            t -= L
        return self.points[0], 0

    def length_at(self, p):
        """The distance along it from its first point to the point of it nearest p."""
        best, run = None, 0.0
        for a, b in zip(self.points, self.points[1:]):
            q, _t = G.closest_on_segment(p, a, b)
            d = G.dist(p, q)
            if best is None or d < best[0]:
                best = (d, run + G.dist(a, q))
            run += G.dist(a, b)
        return best[1] if best else 0.0

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

    def with_grip(self, i, p):
        """A corner or end dragged: with no corner left where it turns straight back along
        itself (an end dragged onto the line of the leg before it ran back up that leg: a
        hidden fold, found by the long battery with Shift-picked grips, 0.18)."""
        got = super().with_grip(i, p)
        from .wires import straighten
        # (and no point twice: an end dropped on the corner before it, seed 4101)
        pts = _tidy(straighten(got.points))
        if len(pts) < 2:
            return self                 # (dragged onto its other end: no wire left; as it was)
        return got if len(pts) == len(got.points) else got.copy(points=[list(q) for q in pts])

    def grips(self):
        """Its corners and ends, then the middle of each straight run (dragged, the run moves
        sideways and the wires joined to it follow: wires.segment_drag, through GripCmd)."""
        return list(self.points) + [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                                    for a, b in zip(self.points, self.points[1:])]

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
            return self.copy(points=_unfolded(pts))
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
        return self.copy(points=_unfolded(pts))


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


def _unfolded(pts):
    """_tidy, and with no corner where the path turns straight back along itself (an end moved
    back along its own last leg: Stretch, seed 3272; a symbol moved with its wires, seed 3273,
    the long battery on GitHub)."""
    from .wires import straighten
    return _tidy(straighten(_tidy(pts)))


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
class Picture(Entity):
    """A picture kept in the project (a company logo, a drawing to trace over: the owner, Nov
    2026), never linked to its file, so the project travels whole: data is the PNG or JPEG file
    itself, base64. pos is its lower left corner as it stands upright, width and height its
    size on the sheet, angle its turn round pos. It is drawn under the lines, kept readable
    (a mirrored picture isn't flipped, as a text isn't)."""
    kind = "picture"
    __slots__ = ("pos", "width", "height", "angle", "data", "fmt")

    def __init__(self, pos, width, height, data, fmt="png", angle=0.0, **kw):
        super().__init__(**kw)
        self.pos = _pt(pos)
        self.width = max(1e-6, abs(float(width)))
        self.height = max(1e-6, abs(float(height)))
        self.angle = float(angle) % 360.0
        self.data = str(data)
        self.fmt = fmt if fmt in ("png", "jpeg") else "png"

    def _data(self):
        return {"pos": list(self.pos), "width": self.width, "height": self.height,
                "angle": self.angle, "data": self.data, "fmt": self.fmt}

    @classmethod
    def _from(cls, d):
        return cls(d["pos"], d["width"], d["height"], d["data"], d.get("fmt", "png"),
                   d.get("angle", 0.0), layer=d.get("layer", "0"), color=d.get("color"),
                   id=d.get("id"))

    def corners(self):
        """Its four corners: lower left (pos), lower right, upper right, upper left."""
        x, y = self.pos
        return [G.rotate_point((x + dx, y + dy), self.pos, self.angle)
                for dx, dy in ((0.0, 0.0), (self.width, 0.0), (self.width, self.height),
                               (0.0, self.height))]

    def center(self):
        c = self.corners()
        return ((c[0][0] + c[2][0]) / 2.0, (c[0][1] + c[2][1]) / 2.0)

    def _outline_entity(self):
        return Polyline(self.corners(), closed=True)

    def _compute_bbox(self):
        c = self.corners()
        xs, ys = [q[0] for q in c], [q[1] for q in c]
        return (min(xs), min(ys), max(xs), max(ys))

    def distance(self, p):
        return self._outline_entity().distance(p)

    def crosses(self, rect):
        if not G.bbox_overlaps(self.bbox(), rect):
            return False
        return self._outline_entity().crosses(rect)

    def pieces(self):
        return self._outline_entity().pieces()

    def outline(self):
        c = self.corners()
        return [c + [c[0]]]

    def _compute_snaps(self):
        return [("end", q) for q in self.corners()] + [("center", self.center())]

    def grips(self):
        return self.corners() + [self.center()]

    def with_grip(self, i, p):
        """A corner dragged: the picture grows or shrinks from the corner across from it,
        keeping its shape; the middle grip moves it."""
        if i == 4:
            c = self.center()
            return self.moved(p[0] - c[0], p[1] - c[1])
        c = self.corners()
        fixed = c[(i + 2) % 4]
        diag = G.dist(fixed, c[i])
        if diag < 1e-12:
            return self.copy()
        u = ((c[i][0] - fixed[0]) / diag, (c[i][1] - fixed[1]) / diag)
        along = (p[0] - fixed[0]) * u[0] + (p[1] - fixed[1]) * u[1]
        f = max(1e-3, along / diag)
        return self.scaled(fixed, f)

    def _map(self, fn, rot=0.0, factor=1.0, mirror=None):
        w, h = self.width * abs(factor), self.height * abs(factor)
        ang = self.angle + rot
        if mirror is not None:
            # (it lands where mirroring puts it but isn't flipped: a logo stays readable)
            ang = G.mirror_angle(self.angle, *mirror) + 180.0
            if 90.0 + 1e-6 < ang % 360.0 <= 270.0 + 1e-6:
                ang += 180.0
        nc = fn(self.center())
        half = G.rotate_point((w / 2.0, h / 2.0), (0.0, 0.0), ang)
        return self.copy(pos=[nc[0] - half[0], nc[1] - half[1]], width=w, height=h,
                         angle=ang % 360.0)


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
ALIGNS = ("left", "center", "right")
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
        self.align = align if align in ALIGNS else "left"
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


DIM_UNITS = ("decimal", "1/8", "1/16", "1/32", "1/64")


def dim_units(text):
    """A dimension format typed or kept ("decimal", "1/16"...; "" and anything else: decimal)."""
    t = str(text or "").strip().lower()
    return t if t in DIM_UNITS else "decimal"


def fmt_length(v, units="decimal"):
    """A length in a dimension's format: decimal (12.50\") or fractional to the nearest 1/8,
    1/16, 1/32 or 1/64, reduced, a dash between the whole inches and the fraction as US
    drawings write it (1-9/16\", 3/4\", 2\"; the owner, 0.18.4: "change dimensions to decimal
    or fractional")."""
    units = dim_units(units)
    if units == "decimal":
        return fmt_inches(v)
    den = int(units.split("/")[1])
    n = int(round(abs(v) * den))
    whole, num = divmod(n, den)
    sign = "-" if v < 0 and n else ""
    if not num:
        return "%s%d\"" % (sign, whole)
    g = math.gcd(num, den)
    frac = "%d/%d" % (num // g, den // g)
    return "%s%s%s\"" % (sign, ("%d-" % whole) if whole else "", frac)


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
    the measured length ("" measures; <> in it stands for the measured length). units: how
    the length reads, "decimal" (12.50\") or a fraction's precision ("1/16": 1-9/16\")."""
    kind = "dimension"
    __slots__ = ("p1", "p2", "loc", "mode", "height", "text", "units", "_parts")

    def __init__(self, p1, p2, loc, mode="linear", height=0.1, text="", units="decimal",
                 **kw):
        kw.setdefault("layer", "DIMENSIONS")
        super().__init__(**kw)
        self.p1, self.p2, self.loc = _pt(p1), _pt(p2), _pt(loc)
        self.mode = "aligned" if mode == "aligned" else "linear"
        self.height = float(height)
        self.text = str(text or "")
        self.units = dim_units(units)
        self._parts = None

    def _data(self):
        d = {"p1": list(self.p1), "p2": list(self.p2), "loc": list(self.loc), "mode": self.mode,
             "height": self.height}
        if self.text:
            d["text"] = self.text
        if self.units != "decimal":
            d["units"] = self.units
        return d

    @classmethod
    def _from(cls, d):
        return cls(d["p1"], d["p2"], d["loc"], d.get("mode", "linear"), d.get("height", 0.1),
                   d.get("text", ""), d.get("units", "decimal"),
                   layer=d.get("layer", "DIMENSIONS"), color=d.get("color"), id=d.get("id"))

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
        v = fmt_length(self.value(), self.units)
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
    __slots__ = ("loops", "pattern", "angle", "spacing", "_parts", "_lines")

    def __init__(self, loops, pattern="SOLID", angle=0.0, spacing=0.125, **kw):
        super().__init__(**kw)
        self.loops = [[_pt(q) for q in lp] for lp in loops if len(lp) >= 3]
        self.pattern = pattern if pattern in HATCH_PATTERNS else "ANSI31"
        self.angle = float(angle)
        self.spacing = float(spacing) if spacing and spacing > 0 else 0.125
        self._parts = None
        self._lines = None

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

    def pattern_lines(self):
        """Its pattern's lines, [(a, b)] (none for a solid fill): what the renderer draws, with
        no Line made for each (the self-test's notes sheet: 2,000 hatches, 57,000 lines)."""
        if self._lines is None:
            self._lines = [ab for ang, share in HATCH_PATTERNS[self.pattern][1]
                           for ab in _scan(self.loops, ang + self.angle, self.spacing * share)]
        return self._lines

    def _compute_bbox(self):
        # (its loops' box: the pattern's lines lie inside them, so they aren't worked out for
        # it; the self-test's notes sheet, 2,000 hatches added)
        return G.bbox_of([q for lp in self.loops for q in lp]) if self.loops else None

    def parts(self):
        """Its loops (closed polylines) and its pattern's lines (none for a solid fill: the
        renderer fills its loops)."""
        if self._parts is not None:
            return self._parts
        out = [Polyline(lp, True) for lp in self.loops]
        out += [Line(a, b) for a, b in self.pattern_lines()]
        for e in out:
            e.layer, e.color = self.layer, self.color
        self._parts = out
        return out

    def distance(self, p):
        """To its outline or, for a pattern, to its nearest pattern line: a press in the gaps
        between its lines is on nothing, so it starts a selection window there, as in AutoCAD
        (the owner: "I was clicking in a hatch. But on the same drawing in Autocad, it let me
        draw a select rectangle from the same spot"; up to 0.15.9 anywhere inside picked the
        hatch). A solid fill is on everything it covers."""
        if self.solid() and point_in_loops(p, self.loops):
            return 0.0
        return min(e.distance(p) for e in self.parts())

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


@_register
class DashBox(Composite):
    """A dashed box (the owner, 0.16: "I need to be able to add a dashed box and write whatever
    note I want inside of it and it not be attached to a child or parent"; and boxes that
    belong to a device, "a dashed box to assign to a parent"): a dashed outline through its
    four corners (points, in order), a note inside it (text, several lines), and, when it
    belongs to a device (attrs PARENT, the device's hidden id, and TAG, its tag, as a
    contact's), that tag above its first corner. height: the text height and the dashes'
    length come from it, in drawing units (paper-sized, as a leader's). note_at, tag_at: where
    the note and the tag were dragged to (None: their own places)."""
    kind = "dashbox"
    __slots__ = ("points", "text", "height", "attrs", "note_at", "tag_at", "_parts")

    def __init__(self, points, text="", height=0.1, attrs=None, note_at=None, tag_at=None,
                 **kw):
        kw.setdefault("layer", "NOTES")
        super().__init__(**kw)
        self.points = [_pt(q) for q in points]
        self.text = str(text or "")
        self.height = float(height)
        self.attrs = {k: str(v) for k, v in (attrs or {}).items() if v not in (None, "")}
        self.note_at = _pt(note_at) if note_at is not None else None
        self.tag_at = _pt(tag_at) if tag_at is not None else None
        self._parts = None

    @classmethod
    def from_corners(cls, a, b, **kw):
        """A box across and up and down between two opposite corners, its first corner at
        the top left."""
        x0, x1 = sorted((a[0], b[0]))
        y0, y1 = sorted((a[1], b[1]))
        return cls([(x0, y1), (x1, y1), (x1, y0), (x0, y0)], **kw)

    def _data(self):
        d = {"points": [list(q) for q in self.points], "height": self.height}
        if self.text:
            d["text"] = self.text
        if self.attrs:
            d["attrs"] = dict(self.attrs)
        if self.note_at is not None:
            d["note_at"] = list(self.note_at)
        if self.tag_at is not None:
            d["tag_at"] = list(self.tag_at)
        return d

    @classmethod
    def _from(cls, d):
        return cls(d["points"], d.get("text", ""), d.get("height", 0.1), d.get("attrs"),
                   d.get("note_at"), d.get("tag_at"), layer=d.get("layer", "NOTES"),
                   color=d.get("color"), id=d.get("id"))

    def tag(self):
        """What the box shows as its device's: its tag ("" when it belongs to none)."""
        return self.attrs.get("TAG", "")

    def note_point(self):
        """Where its note starts (the top left of its first line): dragged there, or inside
        its first corner, a little in."""
        if self.note_at is not None:
            return self.note_at
        a, b, d = self.points[0], self.points[1], self.points[-1]
        m = self.height * 0.6
        ux, uy = self._unit(a, b)
        vx, vy = self._unit(a, d)
        return (a[0] + (ux + vx) * m, a[1] + (uy + vy) * m)

    def tag_point(self):
        """Where its tag sits (its lower left): dragged there, or just above its first
        corner."""
        if self.tag_at is not None:
            return self.tag_at
        a = self.points[0]
        return (a[0], a[1] + self.height * 0.5)

    @staticmethod
    def _unit(a, b):
        L = G.dist(a, b)
        return ((b[0] - a[0]) / L, (b[1] - a[1]) / L) if L > 1e-12 else (0.0, 0.0)

    def dash_pieces(self):
        """The dashes of its outline, [(a, b)]: dashes and gaps of a size set by its height,
        each side starting and ending with a dash (corners drawn)."""
        dash, gap = self.height * 1.2, self.height * 0.6
        out = []
        n = len(self.points)
        for i in range(n):
            a, b = self.points[i], self.points[(i + 1) % n]
            L = G.dist(a, b)
            if L < 1e-12:
                continue
            k = max(1, int(round((L + gap) / (dash + gap))))
            # (stretched to fit the side exactly: k dashes, k - 1 gaps)
            d = (L - (k - 1) * gap) / k if k > 1 else L
            if d < gap * 0.25:
                k, d = 1, L
            ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
            t = 0.0
            for _j in range(k):
                out.append(((a[0] + ux * t, a[1] + uy * t),
                            (a[0] + ux * (t + d), a[1] + uy * (t + d))))
                t += d + gap
        return out

    def parts(self):
        if self._parts is not None:
            return self._parts
        h = self.height
        out = [Line(a, b) for a, b in self.dash_pieces()]
        if self.text:
            x, y = self.note_point()
            step = h * LINE_STEP
            for i, line in enumerate(self.text.splitlines()):
                if line.strip():
                    out.append(Text((x, y - i * step), line, h, 0.0, "left", "top"))
        if self.tag():
            out.append(Text(self.tag_point(), self.tag(), h, 0.0, "left", "baseline"))
        for e in out:
            e.layer, e.color = self.layer, self.color
        self._parts = out
        return out

    def _compute_bbox(self):
        bb = Composite._compute_bbox(self)
        for q in self.points:
            bb = G.bbox_union(bb, (q[0], q[1], q[0], q[1]))
        return bb

    def distance(self, p):
        n = len(self.points)
        d = min(G.dist_to_segment(p, self.points[i], self.points[(i + 1) % n])
                for i in range(n))
        for e in self.parts():
            if isinstance(e, Text):
                d = min(d, e.distance(p))
        return d

    def crosses(self, rect):
        n = len(self.points)
        if any(G.segment_hits_rect(self.points[i], self.points[(i + 1) % n], rect)
               for i in range(n)):
            return True
        return any(e.crosses(rect) for e in self.parts() if isinstance(e, Text))

    def outline(self):
        return [list(self.points) + [self.points[0]]]

    def pieces(self):
        n = len(self.points)
        return [("seg", self.points[i], self.points[(i + 1) % n]) for i in range(n)]

    def _compute_snaps(self):
        n = len(self.points)
        out = [("end", q) for q in self.points]
        out += [("mid", ((self.points[i][0] + self.points[(i + 1) % n][0]) / 2,
                         (self.points[i][1] + self.points[(i + 1) % n][1]) / 2)) for i in range(n)]
        return out

    def grips(self):
        """Its four corners, then its note's start (when it has a note) and its tag (when it
        belongs to a device)."""
        out = list(self.points)
        if self.text:
            out.append(self.note_point())
        if self.tag():
            out.append(self.tag_point())
        return out

    def with_grip(self, i, p):
        n = len(self.points)
        if i < n:
            # a corner: its two neighbors follow so the sides keep their directions (a
            # rectangle stays one)
            pts = [list(q) for q in self.points]
            a = self.points[i]
            prev, nxt = self.points[(i - 1) % n], self.points[(i + 1) % n]
            dx, dy = p[0] - a[0], p[1] - a[1]
            pts[i] = [p[0], p[1]]
            for j, o in (((i - 1) % n, prev), ((i + 1) % n, nxt)):
                ux, uy = self._unit(a, o)
                # (the neighbor moves across its side: the part of the move square to it)
                along = dx * ux + dy * uy
                pts[j] = [o[0] + dx - along * ux, o[1] + dy - along * uy]
            return self.copy(points=pts)
        k = i - n
        if self.text:
            if k == 0:
                return self.copy(note_at=list(p))
            k -= 1
        return self.copy(tag_at=list(p))

    def _map(self, fn, **_kw):
        # (scaled, its text and dashes keep their size: they are paper-sized)
        return self.copy(points=[list(fn(q)) for q in self.points],
                         note_at=list(fn(self.note_at)) if self.note_at is not None else None,
                         tag_at=list(fn(self.tag_at)) if self.tag_at is not None else None)

    def exploded(self):
        out = []
        for e in self.parts():
            c = e.copy()
            c.id = None
            out.append(c)
        return out


@_register
class DashPolygon(DashBox):
    """A dashed polygon (the owner, 0.26: "Dashed polygon in addition to the dashed box"): a
    dashed box of any shape, closed through its corners (points, three or more, picked one by
    one as a polyline's), round a device or a part of a drawing that isn't a rectangle. Its
    note, the device it belongs to, its height and its window are a dashed box's; dragging a
    corner moves that corner alone."""
    kind = "dashpoly"
    __slots__ = ()

    def _top(self):
        """Its top left corner (the highest, then the leftmost): always a corner turning in,
        where its note starts just inside and its tag sits above, as a box's first corner."""
        return max(range(len(self.points)),
                   key=lambda i: (self.points[i][1], -self.points[i][0]))

    def note_point(self):
        if self.note_at is not None:
            return self.note_at
        n = len(self.points)
        i = self._top()
        a, b, d = self.points[i], self.points[(i + 1) % n], self.points[i - 1]
        m = self.height * 0.6
        ux, uy = self._unit(a, b)
        vx, vy = self._unit(a, d)
        return (a[0] + (ux + vx) * m, a[1] + (uy + vy) * m)

    def tag_point(self):
        if self.tag_at is not None:
            return self.tag_at
        a = self.points[self._top()]
        return (a[0], a[1] + self.height * 0.5)

    def with_grip(self, i, p):
        if i < len(self.points):
            pts = [list(q) for q in self.points]
            pts[i] = [p[0], p[1]]
            return self.copy(points=pts)
        return DashBox.with_grip(self, i, p)


@_register
class Ladder(Composite):
    """A ladder (the owner, 0.22: ladder references): its two rails and its rungs' numbers down
    the left of the left rail. a and b: the tops of its left and right rails; the rails run
    down from them (square to a-b, to the right of the way a goes to b) through rungs rungs
    spacing apart, the first at a. first: its first rung's number as typed (None: worked out
    from the page and the ladders before it, ladders.sync, kept in start); prefix and pad:
    how its numbers read (ladder_numbers "prefix": "6-" and 2, so 6-01). height: the numbers'
    text height in drawing units (paper-sized)."""
    kind = "ladder"
    __slots__ = ("a", "b", "rungs", "spacing", "first", "start", "prefix", "pad", "height",
                 "_parts")

    def __init__(self, a, b, rungs=10, spacing=0.5, first=None, start=None, prefix="", pad=0,
                 height=0.1, **kw):
        kw.setdefault("layer", "LADDER")
        super().__init__(**kw)
        self.a, self.b = _pt(a), _pt(b)
        self.rungs = max(1, int(rungs))
        self.spacing = float(spacing)
        self.first = int(first) if first not in (None, "") else None
        self.start = int(start) if start not in (None, "") else None
        self.prefix = str(prefix or "")
        self.pad = int(pad or 0)
        self.height = float(height)
        self._parts = None

    def _data(self):
        d = {"a": list(self.a), "b": list(self.b), "rungs": self.rungs,
             "spacing": self.spacing, "height": self.height}
        for k in ("first", "start"):
            if getattr(self, k) is not None:
                d[k] = getattr(self, k)
        if self.prefix:
            d["prefix"] = self.prefix
        if self.pad:
            d["pad"] = self.pad
        return d

    @classmethod
    def _from(cls, d):
        return cls(d["a"], d["b"], d.get("rungs", 10), d.get("spacing", 0.5), d.get("first"),
                   d.get("start"), d.get("prefix", ""), d.get("pad", 0), d.get("height", 0.1),
                   layer=d.get("layer", "LADDER"), color=d.get("color"), id=d.get("id"))

    # ---- its frame: across (a to b) and down (the rails) ------------------------------------
    def width(self):
        return G.dist(self.a, self.b)

    def _axes(self):
        L = self.width()
        if L < 1e-12:
            return (1.0, 0.0), (0.0, -1.0)
        ux, uy = (self.b[0] - self.a[0]) / L, (self.b[1] - self.a[1]) / L
        return (ux, uy), (uy, -ux)

    def rung_point(self, i, right=False):
        """Where rung i (0 the first) meets the left rail (or the right one)."""
        _u, d = self._axes()
        o = self.b if right else self.a
        return (o[0] + d[0] * i * self.spacing, o[1] + d[1] * i * self.spacing)

    def bottom(self, right=False):
        return self.rung_point(self.rungs - 1, right)

    def number(self, i):
        """Rung i's number as shown (603, 6-03), or "" before its numbers are worked out."""
        if self.start is None and self.first is None:
            return ""
        n = (self.first if self.first is not None else self.start) + i
        return self.prefix + (str(n).zfill(self.pad) if self.pad else str(n))

    def numbers(self):
        return [self.number(i) for i in range(self.rungs)]

    def rung_at(self, p):
        """The rung a point is on (0 the first; nearest), or None when it is off the ladder: past
        the rails by more than a third of the ladder's width, or more than half a rung above
        the first or below the last."""
        (ux, uy), (dx, dy) = self._axes()
        rx, ry = p[0] - self.a[0], p[1] - self.a[1]
        t = rx * ux + ry * uy
        s = (rx * dx + ry * dy) / self.spacing if self.spacing > 0 else 0.0
        m = self.width() / 3.0
        if t < -m or t > self.width() + m or s < -0.5 or s > self.rungs - 0.5:
            return None
        # (exactly half a rung past the last rounds up, to even: a rung that isn't there, 763
        # past 762, which the PDF's links couldn't find; the battery, 0.25, seed 4902)
        return min(max(int(round(s)), 0), self.rungs - 1)

    def parts(self):
        if self._parts is not None:
            return self._parts
        (ux, uy), _d = self._axes()
        out = [Line(self.a, self.bottom()), Line(self.b, self.bottom(True))]
        gap = self.height * 1.5
        for i in range(self.rungs):
            label = self.number(i)
            if label:
                q = self.rung_point(i)
                out.append(Text((q[0] - ux * gap, q[1] - uy * gap), label, self.height, 0.0,
                                "right", "middle"))
        for e in out:
            e.layer, e.color = self.layer, self.color
        self._parts = out
        return out

    def outline(self):
        return [[self.a, self.bottom()], [self.b, self.bottom(True)]]

    def pieces(self):
        return [("seg", self.a, self.bottom()), ("seg", self.b, self.bottom(True))]

    def _compute_snaps(self):
        out = [("end", q) for q in (self.a, self.b, self.bottom(), self.bottom(True))]
        # (every rung's two ends: wires start and end on the rails there)
        for i in range(self.rungs):
            out.append(("node", self.rung_point(i)))
            out.append(("node", self.rung_point(i, True)))
        return out

    def grips(self):
        """The left rail's top (moves it), the right rail's top (its width) and the left rail's
        bottom (how many rungs)."""
        return [self.a, self.b, self.bottom()]

    def with_grip(self, i, p):
        if i == 0:
            dx, dy = p[0] - self.a[0], p[1] - self.a[1]
            return self.copy(a=list(p), b=[self.b[0] + dx, self.b[1] + dy])
        (ux, uy), (dx, dy) = self._axes()
        if i == 1:
            # (wider or narrower, square: along the rung)
            t = (p[0] - self.a[0]) * ux + (p[1] - self.a[1]) * uy
            if t <= 1e-9:
                return self
            return self.copy(b=[self.a[0] + ux * t, self.a[1] + uy * t])
        s = ((p[0] - self.a[0]) * dx + (p[1] - self.a[1]) * dy) / self.spacing
        return self.copy(rungs=max(1, int(round(s)) + 1))

    def _map(self, fn, **_kw):
        # (moved, turned, mirrored or scaled: the rails' tops follow; the rungs' spacing with
        # them, the numbers keep their size: they are paper-sized)
        a, b = fn(self.a), fn(self.b)
        w = self.width()
        f = G.dist(a, b) / w if w > 1e-12 else 1.0
        # (moved or turned, the width the same but floating point making it 0.9999999999999999
        # of it: the spacing kept exactly; the long battery, seed 4782)
        c = self.copy(a=list(a), b=list(b),
                      spacing=self.spacing if abs(f - 1.0) < 1e-9 else self.spacing * f)
        # (mirrored, the rails ran up: the ladder still runs down from a to b's right)
        if c.rung_point(1)[1] > c.a[1] + 1e-9 and abs(a[1] - b[1]) < 1e-9:
            c = c.copy(a=list(b), b=list(a))
        return c


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
    """Wire duct (wireway): its outline, the finger slots along both edges (notches cut in
    from each side, a finger between) with the base line under them, and mounting holes along
    its middle (the owner, 0.18: "I don't love the look of panduit on the drawing. I think it
    needs some basic mask and/or hole pattern"; asked: fingers and holes, a light hatch as an
    option: attribute HATCH "1", Panel settings). The depth isn't drawn (a plan view) but is
    part of its size."""
    kind = "duct"
    __slots__ = ()
    PITCH = 0.5             # finger slots, one every half inch
    SLOT = 0.25             # a slot's width
    HOLES = 3.0             # mounting holes along the middle, this far apart
    HOLE_R = 0.09
    HATCH = 0.35            # the light hatch's spacing (on: attribute HATCH)

    def name(self):
        return "Wire duct " + size_text(self.width, self.depth)

    def _details(self):
        L, h = self.length(), self.width / 2
        d = min(0.3, self.width / 5)                  # (how deep the slots are)
        out = [Line(self.at(0, -(h - d)), self.at(L, -(h - d))),
               Line(self.at(0, h - d), self.at(L, h - d))]
        s, n = self.PITCH / 2, 0
        while s + self.SLOT < L - 1e-9 and n < 4000:
            for side in (-1, 1):
                edge, base = side * h, side * (h - d)
                out.append(Polyline([self.at(s, edge), self.at(s, base),
                                     self.at(s + self.SLOT, base),
                                     self.at(s + self.SLOT, edge)]))
            s += self.PITCH
            n += 1
        # mounting holes along the middle, centered on its length
        if L > 2 * self.HOLE_R:
            k = max(0, int((L - 1.5) // self.HOLES))
            s0 = (L - k * self.HOLES) / 2.0
            for i in range(k + 1):
                if self.HOLE_R < s0 + i * self.HOLES < L - self.HOLE_R:
                    out.append(Circle(self.at(s0 + i * self.HOLES, 0.0), self.HOLE_R))
        if self.attrs.get("HATCH") == "1":
            # light diagonals between the slots' base lines (s - t = c, clipped)
            w = h - d
            c, n = -w, 0
            while c < L + w and n < 20000:
                a0, a1 = max(0.0, c - w), min(L, c + w)
                if a1 > a0 + 1e-9:
                    out.append(Line(self.at(a0, a0 - c), self.at(a1, a1 - c)))
                c += self.HATCH
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
WIRINGS = ("", "distribution", "link", "pdb")
ATTR_NAMES = ["TAG", "DESC", "MFR", "CAT"]       # what every block reference can carry
# a copy's own number for its block's pin n (1 the first): TERM01, TERM02... (Insert.pin_number)
PIN_NUMBER = "TERM%02d"
# a block's optional maker details: who makes it, and its catalog (part) number
MAKER_FIELDS = ("manufacturer", "family", "series", "catalog")


class BlockDef:
    """A block: entities drawn around the base point (0, 0), and for a schematic symbol its
    pins (where wires attach) and where its tag goes. Footprints are drawn at real size."""

    def __init__(self, name, kind="symbol", entities=(), pins=(), tag_pos=None, tag_height=0.1,
                 category="", description="", role="device", contact="", prefix="",
                 builtin=False, wiring="", attr_texts=(), manufacturer="", family="",
                 series="", catalog="", rail_pos=None, own_colors=False, show_pins=False,
                 phases="", label_sizes=None):
        self.name = str(name)
        self.kind = kind if kind in BLOCK_KINDS else "symbol"
        self.entities = list(entities)
        # (a pin's own wire layer, set in the block editor's Pins...: a wire started on it goes
        # on that layer, autolayer.py; "layer" left out: worked out from the block)
        # (and its name's justification as set in the block's tab, "align" and "valign",
        # left out when worked out from its side: the owner, 0.22.2, "when I edit text
        # justification for a block's pins, it just goes back to where it was after saving")
        self.pins = [{"name": str(p["name"]), "pos": _pt(p["pos"])} |
                     ({"layer": str(p["layer"])} if p.get("layer") else {}) |
                     ({"align": p["align"]} if p.get("align") in ALIGNS else {}) |
                     ({"valign": p["valign"]} if p.get("valign") in VALIGNS and
                      p["valign"] != "baseline" else {}) for p in pins]
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
        # (an imported one keeps AutoCAD's alignment and angle; the program's own are centered)
        self.attr_texts = []
        for a in attr_texts:
            t = {"attr": str(a["attr"]), "pos": _pt(a["pos"]),
                 "height": float(a.get("height", 0.08))}
            if a.get("align", "center") in ("left", "right"):
                t["align"] = a["align"]
            if a.get("valign", "baseline") in ("bottom", "middle", "top"):
                t["valign"] = a["valign"]
            if float(a.get("angle", 0.0) or 0.0) % 360.0:
                t["angle"] = float(a["angle"]) % 360.0
            if a.get("stack"):
                t["stack"] = True       # (a rating: see Insert.attr_spots)
            self.attr_texts.append(t)
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
        # its pins' names drawn beside them (a symbol's terminal numbers: the owner, 0.16: "when
        # making terminal numbers, will they show up?"); hidden on a copy as attribute PINS
        self.show_pins = bool(show_pins)
        # three-phase or not, for the Library's filter (the owner, 0.18: "Can symbols be
        # further filtered by whether they're 3ph or not?"): "3", "1" (single-phase or
        # control), or "" to be worked out from it (phases_of)
        self.phases = str(phases) if str(phases) in ("1", "3") else ""
        # a footprint's label lines' text sizes (Block properties, Label text sizes: the
        # owner, 0.24.1, "I need to be able to edit footprint rating font sizes"): {line's
        # key, as label_size_key makes it: paper inches}; a line not listed takes the
        # project's Footprint label height
        self.label_sizes = clean_label_sizes(label_sizes)
        # what a copy of it with no tag yet shows before its "?": "" its prefix (CR?), or the
        # letter its project's tags are made of (K? in a project of IEC 60617 symbols). Not
        # kept in the file: set by the project it is in (Project.sync_tag_letters)
        self.tag_letter = ""

    def to_dict(self):
        return {"name": self.name, "kind": self.kind, "category": self.category,
                "description": self.description, "role": self.role, "contact": self.contact,
                "prefix": self.prefix, "tag_height": self.tag_height,
                "tag_pos": list(self.tag_pos) if self.tag_pos is not None else None,
                "pins": [{"name": p["name"], "pos": list(p["pos"])} |
                         {k: p[k] for k in ("layer", "align", "valign") if p.get(k)}
                         for p in self.pins],
                "entities": [e.to_dict() for e in self.entities]} | (
                    {"wiring": self.wiring} if self.wiring else {}) | (
                    {"attr_texts": [dict(a, pos=list(a["pos"])) for a in self.attr_texts]}
                    if self.attr_texts else {}) | {
                    k: getattr(self, k) for k in MAKER_FIELDS if getattr(self, k)} | (
                    {"rail_pos": list(self.rail_pos)} if self.rail_pos is not None else {}) | (
                    {"own_colors": True} if self.own_colors else {}) | (
                    {"show_pins": True} if self.show_pins else {}) | (
                    {"phases": self.phases} if self.phases else {}) | (
                    {"label_sizes": dict(self.label_sizes)} if self.label_sizes else {})

    @classmethod
    def from_dict(cls, d, builtin=False):
        return cls(d["name"], d.get("kind", "symbol"),
                   [Entity.from_dict(e) for e in d.get("entities", [])], d.get("pins", []),
                   d.get("tag_pos"), d.get("tag_height", 0.1), d.get("category", ""),
                   d.get("description", ""), d.get("role", "device"), d.get("contact", ""),
                   d.get("prefix", ""), builtin, d.get("wiring", ""),
                   d.get("attr_texts", ()), d.get("manufacturer", ""), d.get("family", ""),
                   d.get("series", ""), d.get("catalog", ""), d.get("rail_pos"),
                   d.get("own_colors", False), d.get("show_pins", False),
                   d.get("phases", ""), d.get("label_sizes"))

    @property
    def shown_name(self):
        """Its name as the library and people know it: a footprint kept in a project as
        "Starter (footprint)" beside a symbol "Starter" is "Starter" (project_block_name)."""
        return library_block_name(self.name, self.kind)

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

    def pin_inward(self, name):
        """Which way from a pin its symbol lies (a vector in the block): along the lead line
        that ends on it, else in from the edge of the drawing nearest it. Its name goes that
        way (a pin near a corner, as a drive's PE2 on its bottom line beside T3, was taken by
        the middle of the drawing for one on the side, and its name drawn over T3's: the
        owner, 0.22.2)."""
        key = (len(self.entities), tuple((p["name"], p["pos"]) for p in self.pins))
        cached = getattr(self, "_inward", None)
        got = cached[1] if cached is not None and cached[0] == key else None
        if got is None:
            got = {}
            self._inward = (key, got)
            ends = {}
            for e in self.entities:
                if isinstance(e, Line) and G.dist(e.p1, e.p2) > 1e-9:
                    ends.setdefault(_pt(e.p1), []).append(e.p2)
                    ends.setdefault(_pt(e.p2), []).append(e.p1)
            bb = self.extents()
            for p in self.pins:
                x, y = p["pos"]
                far = ends.get(_pt((x, y)))
                if far and len(far) == 1:
                    got[p["name"]] = (far[0][0] - x, far[0][1] - y)
                elif bb is not None:
                    # (no lead line: in from the edge of the drawing it is nearest, a pin on
                    # the bottom line near a corner a bottom pin)
                    sides = [(x - bb[0], (1.0, 0.0)), (bb[2] - x, (-1.0, 0.0)),
                             (y - bb[1], (0.0, 1.0)), (bb[3] - y, (0.0, -1.0))]
                    got[p["name"]] = min(sides, key=lambda t: t[0])[1]
                else:
                    got[p["name"]] = (0.0, 0.0)
        return got.get(name, (0.0, 0.0))

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


_THREE = (("L1", "L2", "L3"), ("T1", "T2", "T3"), ("U", "V", "W"), ("U1", "V1", "W1"))


def phases_of(defn):
    """"3" when a block is three-phase, else "1" (single-phase or control): as set on it
    (BlockDef.phases), else worked out: pins L1-L3, T1-T3 or U, V, W, or "3-pole", "3-phase",
    "three-phase" or "3ph" in its name or description."""
    if defn.phases:
        return defn.phases
    names = {p["name"].upper() for p in defn.pins}
    if any(set(t) <= names for t in _THREE):
        return "3"
    words = (defn.name + " " + defn.description).lower()
    if any(w in words for w in ("3-pole", "3 pole", "3-phase", "three-phase", "three phase",
                                "3ph", "three poles")):
        return "3"
    return "1"


def pin_keys(pins):
    """{(pin name, which of that name: 0, 1...): point} of [(pin name, point)]: a symbol's
    pins told apart when two have one name (the owner's drive, 0.17.5: two GND, its line and
    load side; matched by name alone, the wire on one of them stayed behind when it moved)."""
    out, seen = {}, {}
    for n, q in pins:
        k = seen.get(n, 0)
        seen[n] = k + 1
        out[(n, k)] = q
    return out


# A device's ratings, one attribute each (the owner, 0.17.5: "Electrical symbols need to have
# voltage, amps, hp, etc (as applicable) for attributes. I'm working on a motor right now"):
# {name: (what the attributes window calls it, what a plain number gets after it)}. Typed as a
# plain number (5, 1/2, 7.6) it is shown with its unit (5HP); anything else as typed.
RATING_FIELDS = {
    "HP": ("Horsepower", "HP"),
    "VOLTS": ("Volts", "V"),
    "AMPS": ("Amps", "A"),
    "FLA": ("Full-load amps", "A FLA"),
    "VA": ("VA", "VA"),
    "PRI": ("Primary volts", "V PRI"),
    "SEC": ("Secondary volts", "V SEC"),
}
_PLAIN_NUMBER = re.compile(r"^\d+(\.\d+)?([- ]\d+)?(/\d+)?$")


def attr_display(name, value):
    """An attribute's value as the drawing shows it: a rating typed as a plain number with
    its unit after it (HP 5: 5HP; FLA 7.6: 7.6A FLA), anything else as typed."""
    got = RATING_FIELDS.get(name)
    v = value.strip()
    if got is not None and _PLAIN_NUMBER.match(v):
        return v + got[1]
    return value


def project_block_name(project, name, kind):
    """The name a library block of that kind goes by in project: its own, unless the project
    already has a block of that name of the other kind (a symbol and a footprint both named
    "VFD 10x15"): then "name (footprint)" or "name (symbol)" (the owner, 0.18: "I tried to
    insert a footprint with the same name as a schematic and it changed the footprint to the
    schematic in a panel drawing")."""
    got = project.blocks.get(name)
    if got is None or got.kind == kind:
        return name
    return "%s (%s)" % (name, kind)


def library_block_name(name, kind):
    """A project block's name in the library (project_block_name's other way)."""
    tail = " (%s)" % kind
    return name[:-len(tail)] if name.endswith(tail) else name


def project_block(project, name, kind):
    """The project's copy of the library block (kind, name), or None: under its own name, or
    "name (kind)" when a block of the other kind has that name (project_block_name)."""
    for n in (name, "%s (%s)" % (name, kind)):
        got = project.blocks.get(n)
        if got is not None and got.kind == kind and library_block_name(n, kind) == name:
            return got
    return None


def ensure_block(ed, project, defn):
    """In edit ed: a library block put in the project, as Insert puts it there (a block of its
    name and kind already in it stays as it is), under project_block_name. Returns the
    project's copy, the one to place."""
    got = project_block(project, defn.name, defn.kind)
    if got is not None:
        return got
    pname = project_block_name(project, defn.name, defn.kind)
    ed.block(renamed_block(defn, pname))
    return project.blocks[pname]


def renamed_block(defn, name):
    """A copy of a block definition under another name."""
    return defn if defn.name == name else BlockDef.from_dict(dict(defn.to_dict(), name=name))


# what a footprint's label shows (Footprint label): the attribute, or its block's name; and
# besides these, any attribute it has by its own name (a linked device's ratings: HP, VOLTS)
LABELS = {"tag": "TAG", "cat": "CAT", "desc": "DESC", "name": None}
LABEL_NAMES = {"tag": "Tag", "cat": "Part number", "desc": "Description", "name": "Block name"}
_LABEL_ATTR = re.compile(r"^[A-Z][A-Z0-9_]*$")
LABEL_LINE = 1.35               # a label's lines apart, in text heights


def label_keys(label):
    """The keys a footprint's label shows, in order: its label is them joined by commas ("tag",
    "tag,cat,HP"; a project from before 0.18.1 has one)."""
    out = []
    for k in str(label or "").split(","):
        k = k.strip()
        if (k in LABELS or _LABEL_ATTR.match(k)) and k not in out:
            out.append(k)
    return out


def _stack_offsets(heights):
    """How far down from the label spot each stacked line's middle goes (its text heights in
    order): each line LABEL_LINE times its own height tall, the stack centered on the spot.
    Lines of one size: (i - (n - 1) / 2) * LABEL_LINE * h, as before 0.24.1, to the bit."""
    n = len(heights)
    if not n:
        return []
    if all(h == heights[0] for h in heights):
        h = heights[0]
        return [(i - (n - 1) / 2.0) * LABEL_LINE * h for i in range(n)]
    # (two neighbors' middles apart by half of each one's line: a big rating under a small
    # tag stays clear of it, and the gap between texts follows the texts beside it)
    mids, at = [], 0.0
    for i, h in enumerate(heights):
        if i:
            at += LABEL_LINE * (heights[i - 1] + h) / 2.0
        mids.append(at)
    middle = (mids[0] - LABEL_LINE * heights[0] / 2.0 + mids[-1] +
              LABEL_LINE * heights[-1] / 2.0) / 2.0
    return [m - middle for m in mids]


def label_size_key(key):
    """The key a label line's text size is kept under (BlockDef.label_sizes,
    Insert.label_sizes): as its own place is (attr_at "@KEY"), "TAG", "CAT", "HP"."""
    return str(key).upper()


def clean_label_sizes(sizes):
    """{key: paper inches} as kept: keys upper case, sizes above zero (0 or blank: none)."""
    out = {}
    for k, v in (sizes or {}).items():
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        if v > 0 and math.isfinite(v):
            out[label_size_key(k)] = v
    return out


def label_sizes_to(others, before, after):
    """The footprints in others with the label sizes changed from before to after (a copy's
    attributes window, {key: paper inches} each): a size set or changed there is theirs too, one
    cleared there is cleared on them; their other sizes stay. The changed copies."""
    out = []
    for o in others:
        sizes = dict(o.label_sizes)
        for k in set(before) | set(after):
            if before.get(k) == after.get(k):
                continue
            if k in after:
                sizes[k] = after[k]
            else:
                sizes.pop(k, None)
        if sizes != o.label_sizes:
            out.append(o.copy(label_sizes=sizes))
    return out


def label_name(key):
    """A label key as the menus and windows name it (Tag, Part number, Horsepower)."""
    if key in LABEL_NAMES:
        return LABEL_NAMES[key]
    got = RATING_FIELDS.get(key)
    return got[0] if got else {"RATING": "Rating", "MFR": "Manufacturer"}.get(key, key)


@_register
class Insert(Entity):
    """A block placed on a sheet: at pos, turned by angle, sized by scale, optionally flipped
    (mirror: the block's own y turned over before turning), with its attributes (TAG, DESC,
    MFR, CAT and the part it is). defn is the BlockDef it shows (the project's copy). label:
    what a footprint shows on it ("" nothing; keys of LABELS or attribute names, joined by
    commas: label_keys)."""
    kind = "insert"
    __slots__ = ("block", "pos", "angle", "scale", "mirror", "attrs", "defn", "tag_h", "label",
                 "hidden", "attr_at", "attr_rot", "label_color", "label_sizes", "label_k",
                 "label_as_set", "_world", "_body")

    def __init__(self, block, pos, angle=0.0, scale=1.0, mirror=False, attrs=None, defn=None,
                 tag_h=None, label="", hidden=(), attr_at=None, attr_rot=None, label_color=None,
                 label_sizes=None, label_k=None, label_as_set=(), **kw):
        super().__init__(**kw)
        self.block = str(block)
        self.pos = _pt(pos)
        self.angle = float(angle) % 360.0
        self.scale = float(scale) or 1.0
        self.mirror = bool(mirror)
        self.attrs = {k: str(v) for k, v in (attrs or {}).items()}
        self.defn = defn
        self.tag_h = float(tag_h) if tag_h else None    # tag height (None: the block's)
        self.label = ",".join(label_keys(label))
        # this copy's own way of showing its attributes, as AutoCAD keeps it per copy (an
        # imported drawing: AutoCAD Electrical hides most attributes copy by copy and moves some
        # off their spot): the ones not shown here, and where some are shown instead of the
        # block's spot ({name: (x, y, angle)}, in the block's own coordinates)
        self.hidden = frozenset(str(h) for h in (hidden or ()))
        self.attr_at = {str(k): (float(v[0]), float(v[1]), float(v[2]) if len(v) > 2 else 0.0)
                        for k, v in (attr_at or {}).items()}
        # an attribute turned on this copy (the owner, 0.17.5: "I need to be able to rotate
        # attributes"): {name: degrees in the block's own coordinates}, so it turns with the
        # block afterward, as in AutoCAD; one not listed is drawn as its block says
        self.attr_rot = {str(k): float(v) % 360.0 for k, v in (attr_rot or {}).items()}
        # a footprint's label color (Panel settings: Footprint label color), None: its own
        self.label_color = str(label_color) if label_color else None
        # a footprint's label lines' own text sizes on this copy (its attributes window,
        # Size: the owner, 0.24.1, "the ability to override individually its instances"):
        # {key (label_size_key): paper inches}; a line not listed takes its block's
        self.label_sizes = clean_label_sizes(label_sizes)
        # drawing units per paper inch for those sizes: its sheet's when it was put there
        # (Sheet._put), grown with its tag_h when the sheet's scale changes (paper_scaled)
        self.label_k = float(label_k) if label_k else None
        # its label lines turned on their own (attr_rot "@KEY") and drawn exactly at that
        # angle, upside down included (the attributes window's Keep readable unticked: the
        # owner, 0.24.1, "Option 2, but overridable"); the others read from the bottom or the
        # right: {key (label_size_key)}
        self.label_as_set = frozenset(label_size_key(k) for k in (label_as_set or ()))
        self._world = None
        self._body = None                   # (its drawing's box: wires.body_box)

    def _data(self):
        d = {"block": self.block, "pos": list(self.pos), "angle": self.angle,
             "scale": self.scale, "attrs": dict(self.attrs)}
        if self.mirror:
            d["mirror"] = True
        if self.tag_h:
            d["tag_h"] = self.tag_h
        if self.label:
            d["label"] = self.label
        if self.hidden:
            d["hidden"] = sorted(self.hidden)
        if self.attr_at:
            d["attr_at"] = {k: list(v) for k, v in self.attr_at.items()}
        if self.attr_rot:
            d["attr_rot"] = dict(self.attr_rot)
        if self.label_color:
            d["label_color"] = self.label_color
        if self.label_sizes:
            d["label_sizes"] = dict(self.label_sizes)
        if self.label_k:
            # (kept with every line hidden too: shown again, a line is the size it was, not
            # its sheet's units taken afresh, 0.26: "Footprint tag sizing not consistent
            # when showing/hiding")
            d["label_k"] = self.label_k
        if self.label_as_set:
            d["label_as_set"] = sorted(self.label_as_set)
        return d

    @classmethod
    def _from(cls, d, blocks):
        return cls(d["block"], d["pos"], d.get("angle", 0.0), d.get("scale", 1.0),
                   d.get("mirror", False), d.get("attrs", {}), blocks.get(d["block"]),
                   d.get("tag_h"), d.get("label", ""), d.get("hidden", ()), d.get("attr_at"),
                   d.get("attr_rot"), d.get("label_color"), d.get("label_sizes"),
                   d.get("label_k"), d.get("label_as_set", ()), layer=d.get("layer", "0"),
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

    def to_local(self, q):
        """A world point in the block's own coordinates (to_world's inverse)."""
        x, y = G.rotate_point((q[0] - self.pos[0], q[1] - self.pos[1]), (0.0, 0.0), -self.angle)
        if self.mirror:
            y = -y
        return (x / self.scale, y / self.scale)

    def pin_points(self):
        """[(pin name, world point)]."""
        if self.defn is None:
            return []
        return [(p["name"], self.to_world(p["pos"])) for p in self.defn.pins]

    def pin_number(self, name):
        """The number this copy shows for its block's pin name: a contact numbered on its device
        (13 and 14 on its pins 1 and 2, 0.28: pinnumbers.py) keeps its own in attributes
        TERM01, TERM02... (AutoCAD Electrical's names: TERM01 the block's first pin), else the
        pin's own name. Wires, snaps and grips go by the block's names (pin_points); what
        people read (pin names on the drawing, the wiring list, terminal wire labels, cross-
        references, Trace) by these."""
        d = self.defn
        if d is None or d.kind != "symbol" or not self.attrs:
            return name
        for i, p in enumerate(d.pins):
            if p["name"] == name:
                return self.attrs.get(PIN_NUMBER % (i + 1)) or name
        return name

    def shown_names(self):
        """The attributes this block can show on the drawing, in its order: its tag (a symbol
        with a tag spot), then its block's attribute spots (Show or hide attributes)."""
        d = self.defn
        if d is None:
            return []
        out = ["TAG"] if d.kind == "symbol" and d.tag_pos is not None else []
        for a in d.attr_texts:
            if a["attr"] not in out:            # (a three-pole fuse's rating: once)
                out.append(a["attr"])
        if d.kind == "symbol" and d.show_pins and d.pins:
            out.append("PINS")              # (its pins' names: shown or hidden as one)
        return out

    def pin_texts(self):
        """Its pins' names beside them, read across however it is turned (Show pin names):
        just inside each pin, above the wire for a pin on a side, beside it for one at the
        top or bottom."""
        d = self.defn
        if d is None or not d.show_pins or "PINS" in self.hidden:
            return []
        h = 0.6 * (self.tag_h or d.tag_height) * self.scale
        g = 0.35 * h
        out = []
        for i, p in enumerate(d.pins):
            x, y = self.to_world(p["pos"])
            # (a contact's own numbers, 13 and 14, where it has them: pin_number)
            name = self.attrs.get(PIN_NUMBER % (i + 1)) or p["name"]
            if p.get("align") or p.get("valign"):
                # (justified in the block's tab: as set there, on the pin)
                out.append(Text((x, y), name, h, 0.0, p.get("align", "left"),
                                p.get("valign", "baseline")))
                continue
            ix, iy = d.pin_inward(p["name"])
            wx, wy = self.to_world((p["pos"][0] + ix, p["pos"][1] + iy))
            dx, dy = wx - x, wy - y
            if abs(dx) >= abs(dy):
                out.append(Text((x + (g if dx >= 0 else -g), y + g), name, h, 0.0,
                                "left" if dx >= 0 else "right", "bottom"))
            else:
                out.append(Text((x + g, y + (g if dy >= 0 else -g)), name, h, 0.0,
                                "left", "bottom" if dy >= 0 else "top"))
        return out

    def tag_text(self):
        """The tag shown on the sheet (None for a footprint or a symbol without a tag spot, or
        its tag hidden on this copy)."""
        d = self.defn
        if d is not None and d.kind == "footprint":
            return self.label_text()
        if d is None or d.kind != "symbol" or d.tag_pos is None or "TAG" in self.hidden:
            return None
        tag = self.attrs.get("TAG", "")
        at = self.attr_at.get("TAG")
        spot = at[:2] if at else d.tag_pos
        align, valign = "center", "baseline"
        a = self.angle % 180.0
        h = (self.tag_h or d.tag_height) * self.scale
        text = tag or ((d.tag_letter or d.prefix) + "?" if d.prefix else "?")
        if d.wiring == "pdb" and d.role == "child":
            # (an outlet of a power distribution block: its block's tag and its own number)
            text = "%s-%s" % (text, self.attrs.get("OUTLET") or "?")
        if "TAG" in self.attr_rot:
            return Text(self.to_world(spot), text, h, self._turned("TAG"), align, valign)
        if 45.0 <= a < 135.0:
            # turned sideways: the tag (still read across) beside the symbol, starting at its
            # spot and running away from it, not centered over the outer pole (the owner, 0.16:
            # "I don't like the location of the tag when rotated sideways")
            p, axis = self.to_world(spot), self.to_world((spot[0], 0.0))
            # (a tag dragged onto the symbol's own line: centered there, not left or right by
            # a rounding error that changed as the symbol moved, the sweep, 0.19.1, seed 3507:
            # a fuse block's tag jumped sides when it was moved)
            off = p[0] - axis[0]
            align = "center" if abs(off) <= 1e-9 else ("left" if off > 0 else "right")
            valign = "middle"
        return Text(self.to_world(spot), text, h, 0.0, align, valign)

    def _turned(self, name):
        """The angle on the drawing of an attribute turned on this copy (attr_rot)."""
        r = self.attr_rot[name]
        return (self.angle + (-r if self.mirror else r)) % 360.0

    def attr_spots(self):
        """[(attribute name, its text's world point, world angle, its spot)]: each attribute of
        the block's shown on this copy (a value, not hidden), the tag apart (tag_text). The
        ratings stack (a spot with "stack"): those shown take the stack's spots in order, so
        an empty one leaves no gap; one dragged to a place of its own (attr_at) keeps it."""
        d = self.defn
        if d is None:
            return []
        stack = [a["pos"] for a in d.attr_texts if a.get("stack")]
        # (turned sideways, the stack's lines would sit side by side, each over the next: the
        # motor-circuit UDT turned 90 degrees showed its motor's "5HP460V FLA" in one
        # blur. Then they go one under the other on the drawing from the stack's first spot,
        # read across, as the tag is, 0.30)
        across = None
        if len(stack) > 1:
            a0, a1 = self.to_world(stack[0]), self.to_world(stack[1])
            dx, dy = a1[0] - a0[0], a1[1] - a0[1]
            if abs(dx) > abs(dy):
                across = (a0, math.hypot(dx, dy))
        out, k = [], 0
        for a in d.attr_texts:
            name = a["attr"]
            if not self.attrs.get(name, "") or name in self.hidden:
                continue
            at = self.attr_at.get(name)
            if at:
                pos = at[:2]
            elif a.get("stack"):
                pos, k = stack[k], k + 1
            else:
                pos = a["pos"]
            if name in self.attr_rot:
                ang = self._turned(name)
            else:
                ang = at[2] if at else a.get("angle", 0.0)
                if at or "angle" in a:
                    ang = (ang + self.angle) % 360.0      # (turned with the block)
            if across is not None and not at and a.get("stack"):
                q = (across[0][0], across[0][1] - across[1] * (k - 1))
            else:
                q = self.to_world(pos)
            out.append((name, q, ang, a))
        return out

    def attr_angle(self, name):
        """The angle on the drawing an attribute's text is drawn at (the attributes window's
        Angle; an attribute not shown: where it would be). A footprint's label line ("@KEY"):
        the angle set, before Keep readable turns it to face the reader (label_angle)."""
        if name in self.attr_rot:
            return self._turned(name)
        if name.startswith("@") and self.defn is not None and self.defn.kind == "footprint":
            return self._label_auto_angle()         # (a label line not turned on its own)
        if name == "TAG":
            t = self.tag_text()
            return t.angle if t is not None else 0.0
        for a in (self.defn.attr_texts if self.defn is not None else []):
            if a["attr"] == name:
                at = self.attr_at.get(name)
                ang = at[2] if at else a.get("angle", 0.0)
                return (ang + self.angle) % 360.0 if at or "angle" in a else ang % 360.0
        return 0.0

    def with_attr_angle(self, name, angle):
        """A copy with that attribute's text drawn at angle (degrees on the drawing); from then
        on it turns with the block. Its block's own angle: back to as the block draws it."""
        rot = dict(self.attr_rot)
        rot.pop(name, None)
        plain = self.copy(attr_rot=rot).attr_angle(name)
        if abs((float(angle) - plain + 180.0) % 360.0 - 180.0) > 1e-9:
            r = (float(angle) - self.angle) % 360.0
            rot[name] = (-r if self.mirror else r) % 360.0
        return self.copy(attr_rot=rot)

    def text_grips(self):
        """[(attribute name, world point)]: the texts of this copy that can be dragged to a
        place of their own (Insert's grips after its insertion point): its tag, and each
        attribute shown at one spot (a 3-pole fuse's three ratings move with the block)."""
        d = self.defn
        if d is not None and d.kind == "footprint":
            # (each line of its label: the owner, 0.18.1, "I need to be able to move footprint
            # attributes")
            return [("@" + k.upper(), t.pos) for k, t in self.label_texts()]
        if d is None or d.kind != "symbol":
            return []
        out = []
        t = self.tag_text()
        if t is not None:
            out.append(("TAG", t.pos))
        count = {}
        for a in d.attr_texts:
            count[a["attr"]] = count.get(a["attr"], 0) + 1
        for name, q, _ang, _a in self.attr_spots():
            if count[name] == 1 and name != "TAG":
                out.append((name, q))
        if d.role == "child" and not any(a["attr"] == "TERM" for a in d.attr_texts):
            # where its cross-reference (its device's place, 2-E6) goes: dragged to a place of
            # its own, or under it (xrefs.live_all); the owner, 0.19.2, "is there a way to
            # edit the location of the cross reference ... I could put it inside of it"
            out.append(("@XREF", self.xref_point()))
        return out

    def xref_point(self):
        """Where a contact's cross-reference is centered when dragged to a place of its own
        (attr_at "@XREF", in the block's coordinates), else the middle of its underside."""
        at = self.attr_at.get("@XREF")
        if at:
            return self.to_world(at[:2])
        bb = self._compute_bbox()
        return ((bb[0] + bb[2]) / 2.0, bb[1])

    @property
    def block_name(self):
        """Its block's name as people know it (BlockDef.shown_name): what lists, reports and
        the Properties panel show; e.block is the project's key for it."""
        return self.defn.shown_name if self.defn is not None else self.block

    def label_value(self, key=None):
        """What a footprint's label line for key says (its first one when None): "?" for an
        empty tag, part number or description; None for an empty attribute (no line) or no
        label."""
        d = self.defn
        keys = label_keys(self.label)
        if key is None:
            key = keys[0] if keys else None
        if key is None or d is None:
            return None
        if key == "name":
            return d.shown_name             # (its own name, not "name (footprint)")
        if key in LABELS:
            v = self.attrs.get(LABELS[key], "")
            if not v:
                # (the footprint block's own, as the bill of materials takes it)
                v = {"cat": d.catalog, "desc": d.description}.get(key, "")
            if key == "tag" and v and self.attrs.get("TERM", "").strip():
                # (a terminal's footprint: its strip and number, TB1-4; 0.28)
                v = "%s-%s" % (v, self.attrs["TERM"].strip())
            return v or "?"
        v = self.attrs.get(key, "")
        return attr_display(key, v) if v.strip() else None

    def label_texts(self):
        """[(key, Text)]: what a footprint shows on it (Footprint label), a line for each key
        with a value: stacked in the middle of its block's label spot, or each where it was
        dragged (attr_at "@KEY", in the block's coordinates, as a symbol's attributes);
        centered, paper-sized (label_height: its own size, its block's, else tag_h), read from
        the bottom or the right as it is turned."""
        d = self.defn
        if d is None or d.kind != "footprint" or not self.label:
            return []
        lines = [(k, v) for k, v in ((k, self.label_value(k)) for k in label_keys(self.label))
                 if v is not None]
        if not lines:
            return []
        hs = [self.label_height(k) for k, _v in lines]
        ang = self._label_auto_angle()
        bx, by = self.to_world(d.label_point())
        # (down the lines: below on a part read across, to the right on one read upward)
        down = (math.sin(math.radians(ang)), -math.cos(math.radians(ang)))
        # (a line dragged to a place of its own keeps its place in the stack, as before)
        offs = _stack_offsets(hs)
        out = []
        for i, (k, v) in enumerate(lines):
            at = self.attr_at.get("@" + k.upper())
            if at:
                q = self.to_world(at[:2])
            else:
                off = offs[i]
                q = (bx + down[0] * off, by + down[1] * off)
            out.append((k, Text(q, v, hs[i], self.label_angle(k), "center", "middle")))
        return out

    def _label_auto_angle(self):
        """A footprint label line's angle when not turned on its own: read across, or upward
        on a part turned sideways."""
        a = self.angle % 180.0
        return 90.0 if 45.0 <= a < 135.0 else 0.0

    def label_angle(self, key):
        """The angle a footprint's label line is drawn at: turned on this copy (attr_rot
        "@KEY", the attributes window's Angle: it turns with the footprint afterward), else as
        the footprint is turned (_label_auto_angle); kept readable (from the bottom or the
        right: 180 drawn as 0, 270 as 90, about its own middle) unless Keep readable is
        unticked for it (label_as_set). (Up to 0.24 a line's Angle wasn't kept: the owner,
        0.24.1, "I also reoriented the label 90 degrees and it reverted back".)"""
        name = "@" + label_size_key(key)
        if name not in self.attr_rot:
            return self._label_auto_angle()
        ang = self._turned(name)
        if label_size_key(key) not in self.label_as_set and 90.0 + 1e-9 < ang <= 270.0 + 1e-9:
            ang = (ang - 180.0) % 360.0
        return ang

    def label_size(self, key):
        """A label line's text size in paper inches as set (this copy's, else its block's),
        and where from: (size, "copy" | "block"), or (None, "project"): the project's
        Footprint label height (tag_h)."""
        k = label_size_key(key)
        if k in self.label_sizes:
            return self.label_sizes[k], "copy"
        d = self.defn
        if d is not None and k in d.label_sizes:
            return d.label_sizes[k], "block"
        return None, "project"

    def label_height(self, key):
        """A label line's text height on the drawing: its size (label_size) times its sheet's
        drawing units per paper inch, else tag_h, the project's height on its sheet."""
        size, _from = self.label_size(key)
        if size is None:
            return self.tag_h or 0.125
        return size * (self.label_k or 1.0)

    def label_text(self):
        """A footprint's first label line (Footprint label), or None: no label."""
        got = self.label_texts()
        return got[0][1] if got else None

    def world_entities(self):
        """The block's content placed on the sheet, plus the tag text."""
        if self._world is None:
            out = []
            labels = []
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
                if d.kind == "footprint":
                    labels = [t for _k, t in self.label_texts()]
                    out += labels
                else:
                    t = self.tag_text()
                    if t is not None:
                        out.append(t)
                out += self.pin_texts()
                for name, q, ang, a in self.attr_spots():
                    out.append(Text(q, attr_display(name, self.attrs[name]),
                                    a["height"] * self.scale, ang, a.get("align", "center"),
                                    a.get("valign", "baseline")))
            own = d is not None and d.own_colors
            for w in out:
                keep = own and w.color is not None
                w.layer = self.layer
                if not keep:
                    w.color = self.color
            if self.label_color:
                for w in labels:
                    w.color = self.label_color
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

    def hold_point(self):
        """Where it is held and dragged: a symbol's first pin (where a wire joins it, as it is
        held when inserted: the owner, 0.17, "Base points need to be where one of the wires
        connects"), else its insertion point."""
        if self.defn is not None and self.defn.kind == "symbol" and self.defn.pins:
            return self.to_world(self.defn.pins[0]["pos"])
        return self.pos

    def grips(self):
        return [self.hold_point()] + [q for _n, q in self.text_grips()]

    def with_grip(self, i, p):
        if i == 0:
            h = self.hold_point()
            return self.moved(p[0] - h[0], p[1] - h[1])
        # a text dragged to a place of its own, kept in the block's coordinates (it follows
        # the block when it is moved or turned)
        name = self.text_grips()[i - 1][0]
        old = self.attr_at.get(name)
        at = dict(self.attr_at)
        at[name] = self.to_local(p) + ((old[2],) if old else (0.0,))
        return self.copy(attr_at={k: list(v) for k, v in at.items()})

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
def gauge_text(g):
    """A gauge as shown: "14 AWG", "1/0 AWG", "250 kcmil" (no AWG after kcmil), or ""."""
    g = str(g or "").strip()
    if not g:
        return ""
    return g if "KCMIL" in g.upper() or "MCM" in g.upper() else "%s AWG" % g


class Layer:
    def __init__(self, name, color=ADAPTIVE, visible=True, locked=False, awg="",
                 wire_color="", gauge_shown=True, wire=False):
        self.name = name
        self.color = color
        self.visible = bool(visible)
        self.locked = bool(locked)
        # a wire layer's wire: its gauge (14, 2/0...) and insulation color (BLK, BRN...),
        # shown beside its wires (the owner, 0.16: "set the awg and color of wire layers")
        self.awg = str(awg or "").strip()
        self.wire_color = str(wire_color or "").strip()
        # its gauge label shown beside its wires (Layers: Gauge shown; the owner, 0.18.5:
        # control power, all 16 AWG blue, "I don't need to announce this all over the place")
        self.gauge_shown = bool(gauge_shown)
        # a wire layer whatever its name, gauge or color (made one in Project properties:
        # Wire layers, New; wirelayers.is_wire_layer)
        self.wire = bool(wire)

    def wire_label(self):
        """What its wires show: "14 AWG BLK", "14 AWG", "BLK", or ""."""
        parts = ([gauge_text(self.awg)] if self.awg else []) + \
            ([self.wire_color] if self.wire_color else [])
        return " ".join(parts)

    def to_dict(self):
        d = {"name": self.name, "color": self.color, "visible": self.visible,
             "locked": self.locked}
        if self.awg:
            d["awg"] = self.awg
        if self.wire_color:
            d["wire_color"] = self.wire_color
        if not self.gauge_shown:
            d["gauge_shown"] = False
        if self.wire:
            d["wire"] = True
        return d

    @classmethod
    def from_dict(cls, d):
        return cls(d["name"], d.get("color", ADAPTIVE), d.get("visible", True),
                   d.get("locked", False), d.get("awg", ""), d.get("wire_color", ""),
                   d.get("gauge_shown", True), d.get("wire", False))


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


def paper_sized(e):
    """Does e keep its size on paper (a text, dimension, leader, multi-line text or a symbol's
    tag: their heights follow the sheet's scale), unlike the drawing, which is real size?
    Not when drawing-sized (fixed: brought in with a DXF or DWG)."""
    if e.fixed:
        return False
    return isinstance(e, (Text, Dimension, Leader, MText, DashBox)) or \
        (isinstance(e, Insert) and bool(e.tag_h))


def paper_scaled(e, f):
    """e as it is when the sheet's drawing units per paper inch grow f times (Edit.sheet_scale,
    and Fit working out the drawing's size at another scale), or None when e doesn't change."""
    if not paper_sized(e):
        return None
    if isinstance(e, MText):
        return e.copy(height=e.height * f, width=e.width * f)    # (it wraps where it did)
    if isinstance(e, Insert):
        # (its label lines with sizes of their own grow with it: label_k)
        return e.copy(tag_h=e.tag_h * f, label_k=e.label_k * f if e.label_k else None)
    return e.copy(height=e.height * f)


class SpatialIndex:
    """Entity ids in square buckets, for hit tests, snapping and window selection that don't
    walk every entity on the sheet. An entity too big for the buckets (an imported drawing's
    frame, a block the size of the sheet) is kept with its box in a short list of its own, and
    any query, however big, is answered whole: up to 0.15.5 both were cut to 64 x 64 buckets
    (32") from their lower left corner, so a window around an imported drawing found nothing
    outside that corner.

    Two sizes of bucket (0.30): an entity over FINE_MAX half-inch buckets goes in buckets of
    COARSE inches instead. On a sheet at 1/4" = 1'-0" a title's text is 48 times as big in
    drawing units and filled hundreds of half-inch buckets: a battery project of 33 such
    sheets took 480 MB to open (the long battery, seed 5211, ran out of memory)."""
    CELL = 0.5          # inches
    FINE_MAX = 64       # an entity over this many buckets goes in the coarse ones
    COARSE = 16.0       # inches
    MAX_CELLS = 4096    # an entity over this many coarse buckets goes in the list of big ones

    def __init__(self):
        self.cells = {}
        self.coarse = {}
        self.where = {}     # {id: (fine keys, coarse keys)}
        self.big = {}       # {id: box} of the entities too big for the buckets

    @staticmethod
    def _span_of(bb, c):
        return (int(math.floor(bb[0] / c)), int(math.floor(bb[1] / c)),
                int(math.floor(bb[2] / c)), int(math.floor(bb[3] / c)))

    def _span(self, bb):
        return self._span_of(bb, self.CELL)

    def add(self, ent):
        bb = ent.bbox()
        x0, y0, x1, y1 = self._span(bb)
        if (x1 - x0 + 1) * (y1 - y0 + 1) <= self.FINE_MAX:
            cells, keys = self.cells, [(i, j) for i in range(x0, x1 + 1)
                                       for j in range(y0, y1 + 1)]
            self.where[ent.id] = (keys, ())
        else:
            x0, y0, x1, y1 = self._span_of(bb, self.COARSE)
            if (x1 - x0 + 1) * (y1 - y0 + 1) > self.MAX_CELLS:
                self.where[ent.id] = ((), ())
                self.big[ent.id] = tuple(bb)
                return
            cells, keys = self.coarse, [(i, j) for i in range(x0, x1 + 1)
                                        for j in range(y0, y1 + 1)]
            self.where[ent.id] = ((), keys)
        for k in keys:
            cells.setdefault(k, set()).add(ent.id)

    def remove(self, eid):
        self.big.pop(eid, None)
        fine, coarse = self.where.pop(eid, ((), ()))
        for cells, keys in ((self.cells, fine), (self.coarse, coarse)):
            for k in keys:
                s = cells.get(k)
                if s is not None:
                    s.discard(eid)
                    if not s:
                        del cells[k]

    def _big_in(self, rect, out):
        x0, y0, x1, y1 = rect
        for eid, b in self.big.items():
            if b[0] <= x1 and b[2] >= x0 and b[1] <= y1 and b[3] >= y0:
                out.add(eid)
        return out

    @staticmethod
    def _cells_in(cells, span, out):
        x0, y0, x1, y1 = span
        if (x1 - x0 + 1) * (y1 - y0 + 1) > len(cells):
            # (a big window: the filled buckets, fewer than the ones it covers)
            for (i, j), s in cells.items():
                if x0 <= i <= x1 and y0 <= j <= y1:
                    out |= s
        else:
            for i in range(x0, x1 + 1):
                for j in range(y0, y1 + 1):
                    s = cells.get((i, j))
                    if s:
                        out |= s
        return out

    def query(self, rect):
        """Ids whose buckets meet rect (a big entity: whose box does)."""
        out = self._cells_in(self.cells, self._span(rect), set())
        if self.coarse:
            self._cells_in(self.coarse, self._span_of(rect, self.COARSE), out)
        if self.big:
            self._big_in(rect, out)
        return out

    def query_point(self, p, tol):
        """Ids whose box may hold a point within tol of p: the one cell p is in, unless p is
        within tol of a cell's edge (then the box's cells, as query)."""
        c = self.CELL
        fx, fy = p[0] / c, p[1] / c
        i, j = math.floor(fx), math.floor(fy)
        t = tol / c
        if fx - i > t and i + 1 - fx > t and fy - j > t and j + 1 - fy > t:
            got = self.cells.get((i, j), ())
            if not self.big and not self.coarse:
                return got
            out = set(got)
            rect = (p[0] - tol, p[1] - tol, p[0] + tol, p[1] + tol)
            if self.coarse:
                self._cells_in(self.coarse, self._span_of(rect, self.COARSE), out)
            if self.big:
                self._big_in(rect, out)
            return out
        return self.query((p[0] - tol, p[1] - tol, p[0] + tol, p[1] + tol))


# a panel sheet's scale presets: (name written on the drawing, paper / real); "" names 1:N
SCALE_PRESETS = [
    # (1:3, 1:6, 1:9 and 1:12: the owner's, Nov 2026; Fit tries them all, biggest first)
    ("", 1.0), ("", 1 / 2), ("", 1 / 3), ("", 1 / 4), ("", 1 / 5), ("", 1 / 6), ("", 1 / 8),
    ("", 1 / 9), ("", 1 / 10), ("", 1 / 12), ("", 1 / 16), ("", 1 / 20),
    ('3" = 1\'-0"', 1 / 4), ('1-1/2" = 1\'-0"', 1 / 8), ('1" = 1\'-0"', 1 / 12),
    ('3/4" = 1\'-0"', 1 / 16), ('1/2" = 1\'-0"', 1 / 24), ('1/4" = 1\'-0"', 1 / 48),
]

def _arrays(got):
    """A sheet's arrays as saved (arrays.py), those it can't read left out."""
    out = {}
    for k, a in (got or {}).items() if isinstance(got, dict) else ():
        try:
            out[str(k)] = {"mode": "P" if a.get("mode") == "P" else "R",
                           "vals": [float(v) for v in a.get("vals") or []],
                           "center": [float(a["center"][0]), float(a["center"][1])]
                           if a.get("center") else None,
                           "source": [int(i) for i in a.get("source") or []],
                           "items": {str(i): [int(j) for j in ids]
                                     for i, ids in (a.get("items") or {}).items()}}
        except (TypeError, ValueError, KeyError, IndexError, AttributeError):
            continue                    # (saved unreadably: its copies stay, on their own)
    return out


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
        self.location = ""                  # where what's drawn on it is: a panel or box (MCP,
                                            # JB-1, FIELD); a device's LOC wins (pull.py)
        self.number_order = "across"        # tags (and wire numbers): across/down then the other
        # ("wires": along the wires from this symbol, its id: the owner, 0.18, "Can it track my
        # bus?"; tags.wire_walk)
        self.number_from = None
        # wire numbers in the tags' order (True), across and down (False), or as the project
        # says (None: Project properties' "Wire numbers follow the tags' order"; the owner,
        # 0.18: "both a sheet and project setting")
        self.wire_order_tags = None
        # the border and zones, the title block: shown (True), not (False), or as the project
        # says (None: Project properties, Schematic)
        self.show_border = None
        self.show_title_block = None
        self.wire_layer = None              # the layer new wires go on here: None = the
                                            # project's (Project properties, Schematic)
        self.referencing = None             # "grid" or "ladder": None = as the project
        self.tap_style = None               # a tap's suffix here (TAP_STYLES): None = as the
                                            # project
        self.xref_device = None             # arrows show the device at the far end: None =
                                            # as the project, True/False this sheet's own
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
        # a panel sheet's footprint terminals labeled with their wires and where they go
        # (Terminal wire labels, panelwiring.py; 0.28: per sheet, decided there)
        self.terminal_labels = False
        self.no_dots = []                   # junction dots deleted (Delete dot): [(x, y)]
        # arrays that stay arrays (arrays.py): {id: {mode, vals, center, source, items}}
        self.arrays = {}
        # UDTs placed here (udts.py): {group id: the placed UDT (its UDT's key, where it was
        # put, its choices, values, ratings and which object is each of its members)}, and
        # the copies of the UDTs they were made from, {key: UDT dict}
        self.udts = {}
        self.udt_types = {}
        self.report = ""                    # (a report sheet: which report, report_sheets.py)
        self.pin_order = []                 # a block editor's sheet: its pin markers' ids in
                                            # the order set in Pins... (block_editor.to_block)
        self.pin_layers = {}                # a block editor's sheet: {pin marker id: the wire
                                            # layer set for that pin in Pins...}
        self.col_start = int(col_start)     # the first column's number (1 to start)
        self.row_start = int(row_start)     # the first row's letter: 0 = A, 1 = B...
        self.fields = dict(fields or {})
        self.entities = {}              # id -> Entity, in drawing order
        self._next = 1
        self.index = SpatialIndex()
        self.version = 0                # bumped on every change (render caches key on it)
        # bumped when a block reference or a wire is added, removed or replaced: what reads
        # only those (inserts(), wires(), duplicates) isn't worked out again for a line drawn
        self.net_version = 0
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

    def ladders(self):
        """Its ladders, left to right then top down (kept until the sheet changes: looked up for
        every place a cross-reference gives)."""
        got = getattr(self, "_ladders", None)
        if got is not None and got[0] == self.version:
            return got[1]
        out = sorted((e for e in self.entities.values() if isinstance(e, Ladder)),
                     key=lambda e: (round(e.a[0], 6), -e.a[1]))
        self._ladders = (self.version, out)
        return out

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
        if isinstance(ent, Insert) and ent.label_k is None and ent.label:
            # (a footprint's label lines' sizes are paper inches: this sheet's units for them,
            # once, as its tag_h took them; before it is drawn or indexed here)
            ent.label_k = self.k()
            ent._world = ent._bbox = ent._snaps = ent._body = None
        self.entities[ent.id] = ent
        self.index.add(ent)
        self.version += 1
        if isinstance(ent, (Insert, Wire)) or isinstance(old, (Insert, Wire)):
            self.net_version += 1
        self.touched.add(ent.id)

    def _drop(self, eid):
        if eid in self.entities:
            old = self.entities.pop(eid)
            self.index.remove(eid)
            self.version += 1
            if isinstance(old, (Insert, Wire)):
                self.net_version += 1
            self.touched.add(eid)

    def wires(self):
        """The wires on this sheet (kept per sheet version, as inserts())."""
        got = getattr(self, "_wires", None)
        if got is None or got[0] != self.net_version:
            got = self._wires = (self.net_version, [e for e in self.entities.values()
                                                    if isinstance(e, Wire)])
        return got[1]

    def inserts(self):
        """The block references on this sheet (kept per sheet version: tags, contacts and
        cross-references read them without walking every line)."""
        got = getattr(self, "_inserts", None)
        if got is None or got[0] != self.net_version:
            got = self._inserts = (self.net_version, [e for e in self.entities.values()
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
        d = {"id": self.id, "title": self.title, "size": self.size, "cols": self.cols,
             "rows": self.rows, "col_start": self.col_start, "row_start": self.row_start,
             "own_layout": self.own_layout, "kind": self.kind,
             "location": self.location,
             "number_order": self.number_order,
             "number_from": self.number_from,
             "wire_order_tags": self.wire_order_tags,
             "show_border": self.show_border,
             "show_title_block": self.show_title_block,
             "xref_device": self.xref_device,
             "referencing": self.referencing,
             "tap_style": self.tap_style,
             "wire_layer": self.wire_layer,
             "number": self.number, "fields": dict(self.fields),
             "scale": self.scale, "scale_name": self.scale_name,
             "rotation": self.rotation,
             "cabinet": list(self.cabinet) if self.cabinet else None,
             "xref_frozen": self.xref_frozen,
             "xref_shown": [list(t) for t in self.xref_shown]
             if self.xref_shown is not None else None,
             "no_dots": [list(q) for q in self.no_dots]}
        if self.arrays:
            d["arrays"] = {k: {"mode": a["mode"], "vals": list(a["vals"]),
                               "center": list(a["center"]) if a.get("center") else None,
                               "source": list(a["source"]),
                               "items": {i: list(ids) for i, ids in a["items"].items()}}
                           for k, a in self.arrays.items()}
        if self.udts:
            # (each placed UDT's dict, and each UDT's, is never changed once kept here: a
            # change puts a new one in its place, udts._keep; so they are shared, not copied,
            # as a step remembers the sheet before and after: copied, a value applied to 100
            # placed UDTs took 2 s)
            d["udts"] = dict(self.udts)
            d["udt_types"] = dict(self.udt_types)
        if self.report:
            d["report"] = self.report
        if self.terminal_labels:
            d["terminal_labels"] = True
        if self.pin_order:
            d["pin_order"] = list(self.pin_order)
        if self.pin_layers:
            d["pin_layers"] = {str(k): v for k, v in self.pin_layers.items()}
        return d

    def to_dict(self):
        d = self.meta_dict()
        d["entities"] = [e.to_dict() for e in self.entities.values()]
        if self.udts:
            # (a placed UDT's members gone from the sheet forgotten as it is kept: their ids
            # can be given again to other objects once it is opened)
            udts = {}
            for k, u in d["udts"].items():
                live = {r: i for r, i in u["members"].items() if i in self.entities}
                if live:
                    udts[k] = dict(u, members=live)
            used = {u["type"] for u in udts.values()}
            d["udts"] = udts
            d["udt_types"] = {k: v for k, v in d["udt_types"].items() if k in used}
            if not udts:
                d.pop("udts")
                d.pop("udt_types")
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
        self.location = str(d.get("location", "") or "").strip()
        self.number_order = d.get("number_order") if d.get("number_order") in (
            "down", "wires") else "across"
        self.number_from = d.get("number_from")
        self.wire_order_tags = d.get("wire_order_tags")
        self.show_border = d.get("show_border")
        self.show_title_block = d.get("show_title_block")
        self.xref_device = d.get("xref_device")
        self.referencing = d.get("referencing") if d.get("referencing") in ("grid",
                                                                              "ladder") else None
        self.tap_style = d.get("tap_style") if d.get("tap_style") in TAP_STYLES else None
        self.wire_layer = str(d.get("wire_layer") or "").strip() or None
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
        self.no_dots = [(round(float(q[0]), 6), round(float(q[1]), 6))
                        for q in (d.get("no_dots") or [])]
        self.pin_order = [int(i) for i in (d.get("pin_order") or [])]
        self.pin_layers = {int(k): str(v) for k, v in (d.get("pin_layers") or {}).items()
                           if v}
        self.arrays = _arrays(d.get("arrays"))
        self.udts = dict(d.get("udts") or {})
        self.udt_types = dict(d.get("udt_types") or {})
        self.report = str(d.get("report", "") or "")
        self.terminal_labels = bool(d.get("terminal_labels", False))
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
            self.pin_moves.append((sheet, pin_keys(old.pin_points()), pin_keys(ent.pin_points())))
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

    def sheet_scale(self, sheet, scale, name="", paper_text=True):
        """Give a sheet another scale. The drawing stays real size; texts, tags and
        dimensions are paper-sized, so their heights follow (they print the same size) -
        except those drawing-sized (fixed: brought in with a DXF or DWG), and none of them with
        paper_text False (Sheet scale: "Text and dimensions keep their size on paper" off)."""
        old_k = sheet.k()
        self.sheet_meta(sheet, scale=float(scale), scale_name=name)
        f = sheet.k() / old_k
        if abs(f - 1.0) < 1e-12 or not paper_text:
            return
        for e in list(sheet.entities.values()):
            c = paper_scaled(e, f)
            if c is not None:
                self.change(sheet, c)

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
        if after.get("fp_label_height") != before.get("fp_label_height"):
            for s in p.sheets:
                for e in list(s.entities.values()):
                    if isinstance(e, Insert) and (e.label or e.tag_h and e.defn is not None
                                                  and e.defn.kind == "footprint"):
                        # a footprint's label: paper-sized, its own height (0.18.1); one
                        # with its lines all hidden too, so they come back at this height
                        # (0.26: up to 0.25 they came back at the old one)
                        self.change(s, e.copy(tag_h=float(after["fp_label_height"]) * s.k(),
                                              label_k=s.k()))
        if after.get("fp_label_color", "") != before.get("fp_label_color", ""):
            for s in p.sheets:
                for e in list(s.entities.values()):
                    if isinstance(e, Insert) and e.defn is not None and \
                            e.defn.kind == "footprint":
                        self.change(s, e.copy(label_color=after["fp_label_color"] or None))

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
        # (open for editing elsewhere: Save refused, Save As makes your own copy; and this
        # copy's lock note when it is open for editing here: filelock.py, locking.py)
        self.read_only = False
        self.lock = None
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

    def make_sheet(self, title="", kind="schematic"):
        """A new sheet laid out as the project says (not yet in the project): its size, zones,
        and the scale for its kind."""
        st = self.settings
        s = Sheet(title=title, size=st["size"], cols=st["cols"], rows=st["rows"],
                  col_start=st["col_start"], row_start=st["row_start"])
        s.reserve = self.reserve()
        s.kind = kind if kind in SHEET_KINDS else "schematic"
        s.scale, s.scale_name = self.default_scale(s.kind)
        return s

    def kind_scale(self, sheet, kind):
        """The scale a sheet takes when its kind is changed to this one: the project's for
        that kind while nothing is drawn on it, else None (it keeps its own)."""
        if sheet.entities or sheet is self.title_block:
            return None
        return self.default_scale(kind)

    def default_scale(self, kind):
        """(paper / real, preset name) a new sheet of this kind starts at: panel sheets the
        panel one, every other kind the schematic one; 1:1 when the setting can't be read."""
        got = self.settings.get("scale_panel" if kind == "panel" else "scale_schematic")
        try:
            k = float(got[0])
            name = str(got[1] or "") if len(got) > 1 else ""
        except (TypeError, ValueError, IndexError):
            return 1.0, ""
        return (k, name) if k > 0 else (1.0, "")

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

    def tap_style(self, sheet=None, wire=None):
        """A tap's suffix style (TAP_STYLES): the wire's own, else its sheet's, else the
        project's."""
        for got in (getattr(wire, "tap_style", None), getattr(sheet, "tap_style", None),
                    self.settings.get("tap_style")):
            if got in TAP_STYLES:
                return got
        return "-1"

    def referencing(self, sheet):
        """How places on the sheet are given: "grid" or "ladder" (its own, else the
        project's)."""
        got = getattr(sheet, "referencing", None) or self.settings.get("referencing")
        return got if got in ("grid", "ladder") else "grid"

    def zone_text(self, sheet, x, y):
        if sheet is self.title_block:
            return ""
        if self.referencing(sheet) == "ladder":
            # (the rung of a ladder the point is on; off every ladder, the grid zone)
            for lad in sheet.ladders():
                i = lad.rung_at((x, y))
                if i is not None and lad.number(i):
                    return lad.number(i)
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
        self.sync_tag_letters()
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
        # (from the frame's edge to the title block's far side, but never more than the title
        # block is across: one drawn away from its corner, an imported drawing used as a title
        # block, made the strip take nearly the whole sheet and a report sheet's table a
        # sliver; the battery, 0.22.4, seed 41)
        size = min(x1 - bb[0], bb[2] - bb[0]) if pos == "right" else \
            min(bb[3] - y0, bb[3] - bb[1])
        return (pos, max(0.0, size)) if size > 1e-6 else None

    def sync_reserve(self):
        """Every sheet's zone grid stops at the title block strip (when there is one)."""
        r = self.reserve()
        for s in self.sheets:
            if s.reserve != r:
                s.reserve = r
                s.version += 1

    def sync_tag_letters(self):
        """Each block's tag_letter: what its copies with no tag yet show before their "?" (an
        IEC project's letter, K?; tags.prefix_for). The copies with no tag of a block whose
        letter changed are put again, so their drawing follows (otherwise only the blocks are
        looked at: this runs after every change)."""
        from .tags import prefix_for
        changed = set()
        for name, d in self.blocks.items():
            want = prefix_for(self, d) if d.prefix else ""
            want = "" if want == d.prefix else want
            if d.tag_letter != want:
                d.tag_letter = want
                changed.add(name)
        if not changed:
            return
        for s in self.sheets:
            for e in list(s.inserts()):
                if e.block in changed and not e.attrs.get("TAG"):
                    s._put(e.copy())

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
            if "XREFS" not in p.layers:
                # (a project from before 0.18: its cross-references get their layer, and
                # the old size for them the new one; a size set by hand stays)
                p.layers["XREFS"] = Layer("XREFS", dict(DEFAULT_LAYERS)["XREFS"])
                if float(p.settings.get("xref_height", 0)) == XREF_HEIGHT_BEFORE_018:
                    p.settings["xref_height"] = DEFAULT_SETTINGS["xref_height"]
        for bd in d.get("blocks", []) or []:
            b = BlockDef.from_dict(bd)
            p.blocks[b.name] = b
        if "tap_numbers" not in (d.get("settings") or {}):
            p.settings["tap_numbers"] = "same"      # (from before 0.18.3: numbers as they were)
        old_labels = "fp_label_height" not in (d.get("settings") or {})
        ratio = DEFAULT_SETTINGS["fp_label_height"] / float(p.settings.get("tag_height") or 0.1)
        for sd in d.get("sheets", []):
            if old_labels:
                # (from before 0.18.1: its footprints' labels were the tag height, kept on each
                # as paper height times the sheet's scale; they take the new height the same way)
                sd = dict(sd, entities=[
                    dict(ed_, tag_h=float(ed_["tag_h"]) * ratio)
                    if ed_.get("kind") == "insert" and ed_.get("label") and ed_.get("tag_h")
                    else ed_ for ed_ in sd.get("entities", [])])
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
        p.sync_tag_letters()
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


def _only_udts(op):
    """A sheet's meta change (Edit.sheet_meta) of nothing but its placed UDTs: its pages, tags
    and numbers stay as they were."""
    before, after = op[2], op[3]
    keys = (set(before) | set(after)) - {"udts", "udt_types"}
    return all(before.get(k) == after.get(k) for k in keys)


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
            sheets = any(op[0] in ("sheet", "order") or op[0] == "meta" and
                         not _only_udts(op) for op in self.ed.ops)
            if sheets:
                # sheets added, removed, moved or renumbered: device tags follow their pages
                from .tags import sync_pages
                sync_pages(self.ed, self.ed.project)
            kinds = set()
            for op in self.ed.ops:
                if op[0] == "ent":
                    kinds.add((op[3] or {}).get("kind"))
                    kinds.add((op[4] or {}).get("kind"))
            if "insert" in kinds:
                # footprints added or changed any way (placed, pasted, imported, updated
                # from the library): their labels in the color Panel settings gives (0.18.7)
                want = self.ed.project.settings.get("fp_label_color") or None
                seen = set()
                for op in list(self.ed.ops):
                    if op[0] != "ent" or (op[4] or {}).get("kind") != "insert" or \
                            (op[1], op[2]) in seen:
                        continue
                    seen.add((op[1], op[2]))
                    s = self.ed.project.sheet_by_id(op[1])
                    e = s.entities.get(op[2]) if s is not None else None
                    if e is not None and e.defn is not None and e.defn.kind == "footprint" \
                            and e.label_color != want:
                        self.ed.change(s, e.copy(label_color=want))
            if sheets or "insert" in kinds or "dashbox" in kinds or "dashpoly" in kinds:
                # a device added, removed or retagged: its contacts (and dashed boxes) show
                # its tag
                from .tags import sync_children
                sync_children(self.ed, self.ed.project)
                # contact blocks put on (or taken off) a pushbutton's dashed line: their tag
                # hidden (or shown again), 0.19.11
                from .xrefs import sync_block_tags
                touched = {op[1] for op in self.ed.ops if op[0] == "ent"}
                sync_block_tags(self.ed, [s for s in self.ed.project.sheets
                                          if sheets or s.id in touched])
            if sheets or "ladder" in kinds or any(op[0] == "settings" for op in self.ed.ops):
                # ladders drawn or changed, pages renumbered, the numbering style changed:
                # rung numbers (0.22)
                from .ladders import sync as number_rungs
                number_rungs(self.ed, self.ed.project)
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
