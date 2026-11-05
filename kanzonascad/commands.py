"""AutoCAD-style commands: each is a small state machine the view feeds with picked points,
typed values and Enter. Commands talk to the view only through its context methods (prompt,
selection, pick, edit), so the self-test can drive them without a mouse.

Typed input (see parse_point): "3,4" absolute, "@1,0" relative to the last point, "@2<45"
relative polar, a plain number = that distance toward the cursor (direct distance entry).
"""

import math
import re

from . import geometry as G
from . import model as M
from .trim import trim as trim_entity

_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
_RE_ABS = re.compile(r"^\s*(%s)\s*,\s*(%s)\s*$" % (_NUM, _NUM))
_RE_REL = re.compile(r"^\s*@\s*(%s)\s*,\s*(%s)\s*$" % (_NUM, _NUM))
_RE_POLAR = re.compile(r"^\s*(@?)\s*(%s)\s*<\s*(%s)\s*$" % (_NUM, _NUM))
_RE_NUM = re.compile(r"^\s*(%s)\s*$" % _NUM)


_RE_UNIT = re.compile(r"(%s)\s*(mm|cm|in|\")(?![a-z])" % _NUM, re.I)
_PER_INCH = {"mm": 1 / 25.4, "cm": 1 / 2.54, "in": 1.0, '"': 1.0}


def to_inches(text):
    """Numbers written with a unit become inches: "45mm" -> "1.7716...", 2" -> 2."""
    return _RE_UNIT.sub(lambda m: repr(float(m.group(1)) * _PER_INCH[m.group(2).lower()]),
                        text or "")


def parse_number(text):
    m = _RE_NUM.match(to_inches(text))
    return float(m.group(1)) if m else None


def parse_point(text, last=None):
    """A typed point, or None. last: the point "@" is relative to."""
    t = to_inches(text).strip()
    m = _RE_ABS.match(t)
    if m:
        return (float(m.group(1)), float(m.group(2)))
    base = last or (0.0, 0.0)
    m = _RE_REL.match(t)
    if m:
        return (base[0] + float(m.group(1)), base[1] + float(m.group(2)))
    m = _RE_POLAR.match(t)
    if m:
        origin = base if m.group(1) else (0.0, 0.0)
        return G.polar(origin, float(m.group(2)), float(m.group(3)))
    if t == "@":
        return base
    return None


class Command:
    name = ""
    title = ""
    selects = False         # asks "Select objects" first when nothing is selected
    repeatable = True

    def __init__(self, ctx):
        self.ctx = ctx
        self.base = None    # rubber-band / ortho origin
        self.last = None    # the point "@" is relative to
        self.picking = False    # clicks pick objects (Trim) instead of points

    # ---- life ----------------------------------------------------------------------------
    def start(self):
        if self.selects and not self.ctx.selection():
            self.phase = "select"
            self.ctx.prompt("Select objects (Enter when done)")
            return
        self.phase = None
        self.begin()

    def begin(self):
        pass

    def finish(self):
        self.ctx.done(self)

    # ---- input ---------------------------------------------------------------------------
    def selecting(self):
        return getattr(self, "phase", None) == "select"

    def point(self, p):
        pass

    def text(self, s):
        """Typed input that isn't a point. True when used."""
        return False

    def number(self, v):
        """A typed plain number. True when used (otherwise it is a direct distance)."""
        return False

    def enter(self):
        if self.selecting():
            if self.ctx.selection():
                self.phase = None
                self.begin()
            else:
                self.finish()
            return
        self.finish()

    def cancel(self):
        self.finish()

    def preview(self, p):
        """Entities drawn while the cursor is at p."""
        return []

    def pick(self, p):
        """An object picked at p while self.picking."""


def _cleanup_on(ctx):
    """Wires cleaned up as they're drawn (Project properties, Schematic)?"""
    return bool(ctx.project.settings.get("wire_cleanup", True))


def _selected(ctx):
    sheet = ctx.sheet()
    return [sheet.entities[i] for i in ctx.selection() if i in sheet.entities]


# ============================================================================================
# Draw
# ============================================================================================
class LineCmd(Command):
    name, title = "LINE", "Line"

    def begin(self):
        self.points = []
        self.made = []          # ids, for Undo inside the command
        self.ctx.prompt("Specify first point")

    def _prompt(self):
        opts = [("Undo", "U")]
        if len(self.points) >= 3:
            opts.insert(0, ("Close", "C"))
        self.ctx.prompt("Specify next point (Enter to finish)", opts)

    def point(self, p):
        if self.points:
            a = self.points[-1]
            if G.dist(a, p) < 1e-9:
                return
            with self.ctx.edit("Line") as ed:
                e = ed.add(self.ctx.sheet(), M.Line(a, p, layer=self.ctx.layer()))
            self.made.append(e.id)
        self.points.append(p)
        self.base = self.last = p
        self._prompt()

    def text(self, s):
        k = s.strip().upper()
        if k == "C" and len(self.points) >= 3:
            self.point(self.points[0])
            self.finish()
            return True
        if k == "U" and self.points:
            if self.made:
                eid = self.made.pop()
                with self.ctx.edit("Undo line") as ed:
                    ed.remove(self.ctx.sheet(), eid)
            self.points.pop()
            self.base = self.last = self.points[-1] if self.points else None
            if self.points:
                self._prompt()
            else:
                self.ctx.prompt("Specify first point")
            return True
        return False

    def preview(self, p):
        if self.points:
            return [M.Line(self.points[-1], p)]
        return []


class PolylineCmd(Command):
    name, title = "PLINE", "Polyline"

    def begin(self):
        self.points = []
        self.ctx.prompt("Specify start point")

    def point(self, p):
        if self.points and G.dist(self.points[-1], p) < 1e-9:
            return
        self.points.append(p)
        self.base = self.last = p
        opts = [("Undo", "U")] + ([("Close", "C")] if len(self.points) >= 3 else [])
        self.ctx.prompt("Specify next point (Enter to finish)", opts)

    def _make(self, closed):
        if len(self.points) >= 2:
            with self.ctx.edit("Polyline") as ed:
                ed.add(self.ctx.sheet(), M.Polyline(self.points, closed, layer=self.ctx.layer()))
        self.finish()

    def text(self, s):
        k = s.strip().upper()
        if k == "C" and len(self.points) >= 3:
            self._make(True)
            return True
        if k == "U" and self.points:
            self.points.pop()
            self.base = self.last = self.points[-1] if self.points else None
            return True
        return False

    def enter(self):
        self._make(False)

    def cancel(self):
        self._make(False)           # keeps what is drawn so far, as AutoCAD's PLINE

    def preview(self, p):
        if self.points:
            return [M.Polyline(self.points + [p], False)]
        return []


class RectangleCmd(Command):
    name, title = "RECTANG", "Rectangle"

    def begin(self):
        self.first = None
        self.ctx.prompt("Specify first corner")

    @staticmethod
    def _rect(a, b):
        return M.Polyline([a, (b[0], a[1]), b, (a[0], b[1])], True)

    def point(self, p):
        if self.first is None:
            self.first = self.last = p
            self.ctx.prompt("Specify other corner (or @width,height)")
            return
        if abs(p[0] - self.first[0]) < 1e-9 or abs(p[1] - self.first[1]) < 1e-9:
            return
        r = self._rect(self.first, p)
        r.layer = self.ctx.layer()
        with self.ctx.edit("Rectangle") as ed:
            ed.add(self.ctx.sheet(), r)
        self.finish()

    def preview(self, p):
        return [self._rect(self.first, p)] if self.first else []


class CircleCmd(Command):
    """CIRCLE: center, then radius (D for a diameter). At the first prompt 3P, 2P and TTR
    switch to those ways, as AutoCAD's CIRCLE does."""
    name, title = "CIRCLE", "Circle"
    diameter_first = False

    def begin(self):
        self.center = None
        self.diameter = self.diameter_first
        self.ctx.prompt("Specify center point", [("3P", "3P"), ("2P", "2P"),
                                                 ("Tan, tan, radius", "TTR")])

    def _make(self, center, r):
        if r <= 1e-9:
            return
        with self.ctx.edit("Circle") as ed:
            ed.add(self.ctx.sheet(), M.Circle(center, r, layer=self.ctx.layer()))
        self.finish()

    def point(self, p):
        if self.center is None:
            self.center = self.base = self.last = p
            if self.diameter:
                self.ctx.prompt("Specify diameter (point or number)", [("Radius", "R")])
            else:
                self.ctx.prompt("Specify radius (point or number)", [("Diameter", "D")])
            return
        d = G.dist(self.center, p)
        self._make(self.center, d / 2 if self.diameter else d)

    def number(self, v):
        if self.center is None:
            return False
        self._make(self.center, v / 2 if self.diameter else v)
        return True

    def text(self, s):
        k = s.strip().upper()
        if self.center is None:
            other = {"3P": Circle3PCmd, "2P": Circle2PCmd, "TTR": CircleTTRCmd,
                     "T": CircleTTRCmd}.get(k)
            if other is not None:
                self.ctx.switch_to(other)
                return True
            return False
        if k in ("D", "R"):
            self.diameter = k == "D"
            self.ctx.prompt("Specify diameter" if self.diameter else "Specify radius")
            return True
        return False

    def preview(self, p):
        if self.center is None:
            return []
        d = G.dist(self.center, p)
        return [M.Circle(self.center, d / 2 if self.diameter else d), M.Line(self.center, p)]


class CircleDiameterCmd(CircleCmd):
    name, title = "CIRCLE", "Circle (center, diameter)"
    diameter_first = True


class Circle2PCmd(Command):
    """2-Point: the two ends of a diameter."""
    name, title = "CIRCLE", "Circle (2-point)"

    def begin(self):
        self.first = None
        self.ctx.prompt("Specify first end point of circle's diameter")

    def point(self, p):
        if self.first is None:
            self.first = self.base = self.last = p
            self.ctx.prompt("Specify second end point of circle's diameter")
            return
        if G.dist(self.first, p) < 1e-9:
            return
        c = ((self.first[0] + p[0]) / 2, (self.first[1] + p[1]) / 2)
        with self.ctx.edit("Circle") as ed:
            ed.add(self.ctx.sheet(), M.Circle(c, G.dist(self.first, p) / 2,
                                              layer=self.ctx.layer()))
        self.finish()

    def preview(self, p):
        if self.first is None or G.dist(self.first, p) < 1e-9:
            return []
        c = ((self.first[0] + p[0]) / 2, (self.first[1] + p[1]) / 2)
        return [M.Circle(c, G.dist(self.first, p) / 2), M.Line(self.first, p)]


class Circle3PCmd(Command):
    """3-Point: three points on the circle."""
    name, title = "CIRCLE", "Circle (3-point)"

    def begin(self):
        self.points = []
        self.ctx.prompt("Specify first point on circle")

    def point(self, p):
        self.points.append(p)
        self.base = self.last = p
        if len(self.points) == 1:
            self.ctx.prompt("Specify second point on circle")
        elif len(self.points) == 2:
            self.ctx.prompt("Specify third point on circle")
        else:
            r = G.circle_from_3_points(*self.points)
            if r is None:
                self.points.pop()
                self.ctx.message("The three points are in line: pick another.")
                return
            with self.ctx.edit("Circle") as ed:
                ed.add(self.ctx.sheet(), M.Circle(r[0], r[1], layer=self.ctx.layer()))
            self.finish()

    def preview(self, p):
        if len(self.points) == 2:
            r = G.circle_from_3_points(self.points[0], self.points[1], p)
            if r:
                return [M.Circle(r[0], r[1])]
        if self.points:
            return [M.Line(self.points[-1], p)]
        return []


def _tangent_shape(ent):
    """A line, circle or arc as the shape a tangent circle can touch, or None."""
    if isinstance(ent, M.Line):
        return ("line", ent.p1, ent.p2)
    if isinstance(ent, (M.Circle, M.Arc)):
        return ("circle", ent.center, ent.radius)
    if isinstance(ent, M.Polyline):
        return None
    return None


class CircleTTRCmd(Command):
    """Tan, tan, radius: pick two lines, circles or arcs near where the circle should touch
    them, then its radius. Of the circles that fit, the one touching nearest the picks."""
    name, title = "CIRCLE", "Circle (tan, tan, radius)"

    def begin(self):
        self.picks = []
        self.picking = True
        self.ctx.prompt("Specify point on object for first tangent of circle")

    def pick(self, p):
        ent = self.ctx.pick_entity(p)
        if ent is None:
            return
        if isinstance(ent, M.Polyline):
            # the segment of a polyline nearest the pick
            seg = min(ent.segments(), key=lambda s: G.dist_to_segment(p, *s))
            shape = ("line", seg[0], seg[1])
        else:
            shape = _tangent_shape(ent)
        if shape is None:
            self.ctx.message("Pick a line, polyline, circle or arc.")
            return
        self.picks.append((shape, p))
        if len(self.picks) == 1:
            self.ctx.prompt("Specify point on object for second tangent of circle")
        else:
            self.picking = False
            self.ctx.prompt("Specify radius of circle <%s>" % _fmt(
                getattr(self.ctx, "_last_ttr", 0.25)))

    def number(self, v):
        if len(self.picks) < 2 or v <= 0:
            return False
        return self._make(v)

    def point(self, p):
        # a picked radius: from the last point picked to this one
        if len(self.picks) == 2:
            self._make(G.dist(self.picks[1][1], p))

    def enter(self):
        if len(self.picks) == 2:
            self._make(getattr(self.ctx, "_last_ttr", 0.25))
        else:
            self.finish()

    def _make(self, r):
        (a, pa), (b, pb) = self.picks
        cands = G.tangent_circles(a, b, r)
        if not cands:
            self.ctx.message("Circle does not exist: no circle of that radius touches both.")
            return True
        best = min(cands, key=lambda c: G.dist(G.tangent_point(a, c), pa)
                   + G.dist(G.tangent_point(b, c), pb))
        self.ctx._last_ttr = r
        with self.ctx.edit("Circle") as ed:
            ed.add(self.ctx.sheet(), M.Circle(best, r, layer=self.ctx.layer()))
        self.finish()
        return True


class ArcCmd(Command):
    name, title = "ARC", "Arc"

    def begin(self):
        self.points = []
        self.ctx.prompt("Specify start point of arc")

    def point(self, p):
        self.points.append(p)
        self.base = self.last = p
        if len(self.points) == 1:
            self.ctx.prompt("Specify second point of arc")
        elif len(self.points) == 2:
            self.ctx.prompt("Specify end point of arc")
        else:
            r = G.arc_from_3_points(*self.points)
            if r is None:
                self.points.pop()
                self.ctx.message("The three points are in line: pick another end point.")
                return
            c, rad, s, e = r
            with self.ctx.edit("Arc") as ed:
                ed.add(self.ctx.sheet(), M.Arc(c, rad, s, e, layer=self.ctx.layer()))
            self.finish()

    def preview(self, p):
        if len(self.points) == 1:
            return [M.Line(self.points[0], p)]
        if len(self.points) == 2:
            r = G.arc_from_3_points(self.points[0], self.points[1], p)
            if r:
                return [M.Arc(*r)]
            return [M.Line(self.points[0], p)]
        return []


class TextCmd(Command):
    """TEXT: click where the text goes, type it, Enter (each Enter starts the next line below;
    an empty line ends). Its height (H), rotation (R) and justification (J) are typed before
    the click, never taken from clicks: a stray click can't make text inches high (AutoCAD's
    TEXT takes the second click as the height, a trap this avoids)."""
    name, title = "TEXT", "Text"

    JUSTIFY_PROMPT = "Justification: L, C, R (on the baseline); TL, TC, TR (top); ML, MC, MR " \
                     "(middle); BL, BC, BR (bottom)"
    MAX_PAPER = 1.0                 # a remembered height over this (paper inches) is a mistake

    def begin(self):
        self.pos = None
        self.angle = 0.0
        # a height left absurd (from an older version's click) goes back to 1/8 inch
        k = self.ctx.sheet().k()
        if self.ctx.text_height() / k > self.MAX_PAPER:
            self.ctx.set_text_height(0.125 * k)
            self.ctx.message("Text height was over %g inch on paper: set back to 1/8 inch "
                             "(type H to change it)" % self.MAX_PAPER)
        self._start_prompt()

    def _start_prompt(self):
        self.step = "pos"
        code = M.justify_code(*self.ctx.text_justify)
        self.ctx.prompt("Specify %s point of text (height %s, rotation %s, justification %s)" % (
            "start" if code in ("L", "BL") else "insertion",
            _fmt(self.ctx.text_height() / self.ctx.sheet().k()), _fmt(self.angle), code),
            [("Height", "H"), ("Rotation", "R"), ("Justify", "J")])

    def point(self, p):
        if self.step != "pos":
            return                      # (height, rotation: typed; a click changes nothing)
        self.pos = self.base = self.last = p
        self.step = "text"
        self.ctx.prompt("Enter text (Enter on an empty line ends)", typing=True)

    def number(self, v):
        if self.step == "height":
            if v <= 0:
                return False
            self.ctx.set_text_height(v * self.ctx.sheet().k())     # (typed: paper inches)
            self._start_prompt()
            return True
        if self.step == "angle":
            self.angle = v
            self._start_prompt()
            return True
        return False

    def wants_raw_text(self):
        return self.step == "text"

    def text(self, s):
        k = s.strip().upper()
        if self.step == "pos" and k in ("J", "H", "R"):
            if k == "J":
                self.step = "justify"
                self.ctx.prompt(self.JUSTIFY_PROMPT,
                                [(code, code) for code in ("TL", "TC", "TR", "ML", "MC", "MR",
                                                           "BL", "BC", "BR", "L", "C", "R")])
            elif k == "H":
                self.step = "height"
                self.ctx.prompt("Text height, in inches on paper <%s>" % _fmt(
                    self.ctx.text_height() / self.ctx.sheet().k()))
            else:
                self.step = "angle"
                self.ctx.prompt("Rotation angle, degrees <%s>" % _fmt(self.angle))
            return True
        if self.step == "justify":
            if k in M.JUSTIFY:
                self.ctx.text_justify = M.JUSTIFY[k]
                self._start_prompt()
                return True
            return False
        if self.step != "text":
            return False
        if not s:
            self.finish()
            return True
        align, valign = self.ctx.text_justify
        t = M.Text(self.pos, s, self.ctx.text_height(), self.angle, align, valign,
                   layer=self.ctx.layer())
        with self.ctx.edit("Text") as ed:
            ed.add(self.ctx.sheet(), t)
        # the next line goes below, as AutoCAD's TEXT does
        self.pos = G.polar(self.pos, self.ctx.text_height() * 1.6667, self.angle - 90)
        self.ctx.prompt("Enter text (Enter on an empty line ends)", typing=True)
        return True

    def enter(self):
        if self.step in ("height", "angle", "justify"):
            self._start_prompt()                # (Enter keeps what it was)
        else:
            self.finish()

    def preview(self, p):
        if self.step == "pos":
            return [M.Text(p, "Text", self.ctx.text_height(), self.angle,
                           *self.ctx.text_justify)]
        return []


# ============================================================================================
# Modify
# ============================================================================================
class _TwoPoint(Command):
    """Select objects, a base point, then a second point (Move, Copy) or value."""
    selects = True
    verb = ""

    def begin(self):
        self.ents = _selected(self.ctx)
        self.from_pt = None
        self.ctx.prompt("Specify base point")

    def point(self, p):
        if self.from_pt is None:
            self.from_pt = self.base = self.last = p
            self.second_prompt()
            return
        self.apply(p)

    def second_prompt(self):
        self.ctx.prompt("Specify second point")

    def preview(self, p):
        if self.from_pt is None:
            return []
        return self.result(p) + [M.Line(self.from_pt, p)]


class MoveCmd(_TwoPoint):
    name, title = "MOVE", "Move"

    def shift(self, p):
        """(objects, dx, dy): the preview is the objects shifted (the view draws them once
        and slides the drawing, instead of rebuilding big blocks on every mouse move)."""
        if self.from_pt is None:
            return None
        return self.ents, p[0] - self.from_pt[0], p[1] - self.from_pt[1]

    def result(self, p):
        dx, dy = p[0] - self.from_pt[0], p[1] - self.from_pt[1]
        return [e.moved(dx, dy) for e in self.ents]

    def apply(self, p):
        sheet = self.ctx.sheet()
        with self.ctx.edit("Move") as ed:
            for e in self.result(p):
                ed.change(sheet, e)
        self.finish()


class CopyCmd(_TwoPoint):
    name, title = "COPY", "Copy"
    shift = MoveCmd.shift

    def second_prompt(self):
        self.ctx.prompt("Specify second point (Enter to finish)")

    def result(self, p):
        dx, dy = p[0] - self.from_pt[0], p[1] - self.from_pt[1]
        out = []
        for e in self.ents:
            c = e.moved(dx, dy)
            c.id = None
            out.append(c)
        return out

    def apply(self, p):
        from .tags import retag_copies
        sheet = self.ctx.sheet()
        with self.ctx.edit("Copy") as ed:
            for e in retag_copies(self.ctx.project, sheet, self.result(p)):
                ed.add(sheet, e)
        self.last = p


class RotateCmd(_TwoPoint):
    name, title = "ROTATE", "Rotate"

    def second_prompt(self):
        self.ctx.prompt("Specify rotation angle (point or degrees)")

    def result(self, p, angle=None):
        if angle is None:
            angle = G.angle_of(self.from_pt, p)
        return [e.rotated(self.from_pt, angle) for e in self.ents]

    def number(self, v):
        if self.from_pt is None:
            return False
        self._do(self.result(None, v))
        return True

    def apply(self, p):
        if G.dist(p, self.from_pt) < 1e-9:
            return
        self._do(self.result(p))

    def _do(self, ents):
        sheet = self.ctx.sheet()
        with self.ctx.edit("Rotate") as ed:
            for e in ents:
                ed.change(sheet, e)
        self.finish()


class ScaleCmd(_TwoPoint):
    """Scale by a factor, or by Reference (AutoCAD's SCALE R): pick or type a length on the
    drawing as it is, then the length it should be (inches, or with mm: 45mm). This is how a
    manufacturer's drawing is brought to its real size."""
    name, title = "SCALE", "Scale"

    def begin(self):
        _TwoPoint.begin(self)
        self.step = None            # None (factor) | ref1 | ref2 | new
        if self.ctx.sheet().kind == "panel":
            # footprints are real size: scaling one by hand would make it a different part
            locked = [e for e in self.ents if isinstance(e, M.Insert) and e.defn is not None
                      and e.defn.kind == "footprint"]
            if locked:
                self.ents = [e for e in self.ents if e not in locked]
                self.ctx.message("%d footprint(s) left out: footprints are real size on a "
                                 "panel sheet and aren't scaled (the sheet's scale sets how "
                                 "big it prints)" % len(locked))
                if not self.ents:
                    self.finish()

    def second_prompt(self):
        self.step = None
        self.ctx.prompt("Specify scale factor (number, or a point: its distance in inches)",
                        [("Reference", "R")])

    def result(self, p, factor=None):
        if factor is None:
            if self.step == "new":
                factor = G.dist(self.from_pt, p) / self.ref
            else:
                factor = G.dist(self.from_pt, p)
        if factor <= 1e-9:
            return list(self.ents)
        return [e.scaled(self.from_pt, factor) for e in self.ents]

    def text(self, s):
        if self.from_pt is not None and self.step is None and s.strip().upper() == "R":
            self.step = "ref1"
            self.ctx.prompt("Specify reference length: pick its first point, or type the "
                            "length as drawn")
            return True
        return False

    def number(self, v):
        if self.from_pt is None or v <= 0:
            return False
        if self.step == "ref1":
            self._ref(v)
            return True
        if self.step == "ref2":
            return False
        if self.step == "new":
            self._do(self.result(None, v / self.ref))
            return True
        self._do(self.result(None, v))
        return True

    def _ref(self, length):
        if length <= 1e-12:
            self.ctx.message("The reference length can't be zero.")
            return
        self.ref = length
        self.step = "new"
        self.base = self.last = self.from_pt
        self.ctx.prompt("Specify new length (inches, or 45mm; or pick a point: its distance "
                        "from the base point)")

    def point(self, p):
        if self.step == "ref1":
            self.ref_a = self.base = self.last = p
            self.step = "ref2"
            self.ctx.prompt("Specify second point of the reference length")
            return
        if self.step == "ref2":
            self._ref(G.dist(self.ref_a, p))
            return
        _TwoPoint.point(self, p)

    def preview(self, p):
        if self.step in ("ref1", "ref2"):
            return [M.Line(self.ref_a, p)] if self.step == "ref2" else []
        return _TwoPoint.preview(self, p)

    def apply(self, p):
        if G.dist(p, self.from_pt) < 1e-9:
            return
        self._do(self.result(p))

    def _do(self, ents):
        sheet = self.ctx.sheet()
        with self.ctx.edit("Scale") as ed:
            for e in ents:
                ed.change(sheet, e)
        self.finish()


class MirrorCmd(_TwoPoint):
    name, title = "MIRROR", "Mirror"

    def begin(self):
        self.ents = _selected(self.ctx)
        self.from_pt = None
        self.to_pt = None
        self.ctx.prompt("Specify first point of mirror line")

    def second_prompt(self):
        self.ctx.prompt("Specify second point of mirror line")

    def result(self, p):
        if G.dist(p, self.from_pt) < 1e-9:
            return []
        out = []
        for e in self.ents:
            c = e.mirrored(self.from_pt, p)
            out.append(c)
        return out

    def apply(self, p):
        if G.dist(p, self.from_pt) < 1e-9:
            return
        self.to_pt = p
        self.ctx.prompt("Erase source objects?", [("Yes", "Y"), ("No", "N")])

    def point(self, p):
        if self.to_pt is not None:
            return
        _TwoPoint.point(self, p)

    def _do(self, erase):
        sheet = self.ctx.sheet()
        with self.ctx.edit("Mirror") as ed:
            from .tags import retag_copies
            mirrored = self.result(self.to_pt)
            if not erase:
                for e in retag_copies(self.ctx.project, sheet, mirrored):
                    ed.add(sheet, e)
            else:
                for e in mirrored:
                    ed.change(sheet, e)
        self.finish()

    def text(self, s):
        if self.to_pt is None:
            return False
        k = s.strip().upper()[:1]
        if k in ("Y", "N"):
            self._do(k == "Y")
            return True
        return False

    def enter(self):
        if self.to_pt is not None:
            self._do(False)
        else:
            _TwoPoint.enter(self)

    def preview(self, p):
        if self.from_pt is None or self.to_pt is not None:
            return []
        return self.result(p) + [M.Line(self.from_pt, p)]


class EraseCmd(Command):
    name, title = "ERASE", "Erase"
    selects = True

    def begin(self):
        sheet = self.ctx.sheet()
        ids = [i for i in self.ctx.selection() if i in sheet.entities]
        with self.ctx.edit("Erase") as ed:
            for i in ids:
                ed.remove(sheet, i)
        self.ctx.set_selection(set())
        self.ctx.message("Erased %d object(s)" % len(ids))
        self.finish()


class TrimCmd(Command):
    name, title = "TRIM", "Trim"

    def begin(self):
        self.picking = True
        self.ctx.set_selection(set())
        self.ctx.prompt("Select object to trim (Enter to finish)", [("Undo", "U")])
        self.done = 0

    def pick(self, p):
        ent = self.ctx.pick_entity(p)
        if ent is None:
            return
        sheet = self.ctx.sheet()
        bb = ent.bbox()
        cutters = [c for c in sheet.query(bb) if c.id != ent.id
                   and self.ctx.layer_visible(c.layer)]
        res = trim_entity(ent, p, cutters)
        if res is None:
            self.ctx.message("That object can't be trimmed.")
            return
        with self.ctx.edit("Trim") as ed:
            ed.remove(sheet, ent.id)
            for e in res:
                ed.add(sheet, e)
        self.done += 1

    def text(self, s):
        if s.strip().upper() == "U":
            if self.done:
                self.ctx.undo()
                self.done -= 1
            return True
        return False


class GripCmd(Command):
    """Dragging a grip of a selected object (click it, then click where it goes)."""
    name, title = "GRIP", "Stretch"
    repeatable = False

    def __init__(self, ctx, ent, index):
        super().__init__(ctx)
        self.ent, self.index = ent, index
        self.base = self.last = ent.grips()[index]

    def begin(self):
        self.ctx.prompt("Specify stretch point")

    def point(self, p):
        with self.ctx.edit("Stretch") as ed:
            ed.change(self.ctx.sheet(), self.ent.with_grip(self.index, p))
        self.finish()

    def preview(self, p):
        return [self.ent.with_grip(self.index, p)]


class PasteCmd(Command):
    name, title = "PASTE", "Paste"
    repeatable = False

    def __init__(self, ctx, ents, base, blocks=None):
        super().__init__(ctx)
        self.ents, self.base_pt = ents, base
        self.blocks = blocks or {}

    def begin(self):
        self.ctx.prompt("Specify insertion point")

    def result(self, p):
        dx, dy = p[0] - self.base_pt[0], p[1] - self.base_pt[1]
        out = []
        for e in self.ents:
            c = e.moved(dx, dy)
            c.id = None
            out.append(c)
        return out

    def point(self, p):
        sheet = self.ctx.sheet()
        ids = set()
        with self.ctx.edit("Paste") as ed:
            for e in self.ents:
                if isinstance(e, M.Insert) and e.block not in self.ctx.project.blocks \
                        and e.block in self.blocks:
                    ed.block(self.blocks[e.block])
            from .tags import retag_copies
            placed = []
            for e in self.result(p):
                if isinstance(e, M.Insert):
                    e.defn = self.ctx.project.blocks.get(e.block, e.defn)
                    e._world = None
                placed.append(e)
            for e in retag_copies(self.ctx.project, sheet, placed):
                ids.add(ed.add(sheet, e).id)
        self.ctx.set_selection(ids)
        self.finish()

    def preview(self, p):
        return self.result(p)


class ZoomCmd(Command):
    name, title = "ZOOM", "Zoom"
    repeatable = False

    def begin(self):
        self.ctx.prompt("Zoom", [("Extents", "E"), ("Sheet", "S"), ("In", "I"), ("Out", "O")])

    def text(self, s):
        k = s.strip().upper()[:1]
        act = {"E": "extents", "A": "sheet", "S": "sheet", "I": "in", "O": "out"}.get(k)
        if act is None:
            return False
        self.ctx.zoom(act)
        self.finish()
        return True


class WireCmd(Command):
    """WIRE: click where it starts (a pin, a wire, or anywhere), then where it goes: it runs
    straight across and up or down, turning one corner per click (F flips which way the
    corner goes). It ends by itself on a pin or another wire; Enter ends it anywhere."""
    name, title = "WIRE", "Wire"

    def begin(self):
        self.points = []
        self.hfirst = None              # None: the corner follows the cursor
        self.ctx.prompt("Specify start of wire (a pin, a wire, or a point)")

    def _route(self, p):
        """The points the next click at p adds: straight across and up or down, through an
        angled lead where the wire leaves (or lands on) a pin that already has a wire."""
        from .wires import route, lead
        sheet = self.ctx.sheet()
        a = self.points[-1]
        start = []
        if len(self.points) == 1:
            got = lead(sheet, a, p)
            if got is not None:
                a, out = got
                start = [a]
                if self.hfirst is None:
                    # (carry on the way the lead heads, unless the cursor is well off it)
                    h = abs(out[0]) > 0
                    return start + route(a, p, h)
        end = lead(sheet, p, a)
        if end is not None and G.dist(a, p) > 1e-9:
            c, out = end
            h = self.hfirst
            if h is None:
                h = not (abs(out[0]) > 0)  # (arrive along the way out of the pin)
            return start + route(a, c, h) + [p]
        h = self.hfirst
        if h is None:
            h = abs(p[0] - a[0]) >= abs(p[1] - a[1])
        return start + route(a, p, h)

    def point(self, p):
        from .wires import connects_at
        if not self.points:
            self.points = [p]
            self.base = self.last = p
            self.ctx.prompt("Specify next point (ends by itself on a pin or wire; Enter "
                            "ends here)", [("Flip corner", "F"), ("Undo", "U")])
            return
        if G.dist(self.points[-1], p) < 1e-9:
            return
        self.points += self._route(p)
        self.base = self.last = p
        if connects_at(self.ctx.sheet(), p):
            self._make()

    def text(self, s):
        k = s.strip().upper()
        if k == "F" and self.points:
            last = self.ctx.cursor_point() if hasattr(self.ctx, "cursor_point") else None
            if self.hfirst is None and last is not None:
                a = self.points[-1]
                self.hfirst = not (abs(last[0] - a[0]) >= abs(last[1] - a[1]))
            else:
                self.hfirst = not bool(self.hfirst)
            return True
        if k == "U" and len(self.points) > 1:
            self.points.pop()
            self.base = self.last = self.points[-1]
            return True
        return False

    def _make(self):
        pts = M._tidy(self.points)
        if len(pts) >= 2:
            sheet = self.ctx.sheet()
            with self.ctx.edit("Wire") as ed:
                w = ed.add(sheet, M.Wire(pts))
                if _cleanup_on(self.ctx):
                    from .wires import tidy_new
                    if tidy_new(ed, sheet, w) == "duplicate":
                        self.ctx.message("That wire is already there: not drawn twice")
        self.finish()

    def enter(self):
        self._make()

    def cancel(self):
        # Esc, or starting another command, keeps what is drawn so far (as AutoCAD's PLINE)
        self._make()

    def preview(self, p):
        if not self.points:
            return []
        return [M.Wire(self.points + self._route(p))]


def bus_paths(points, count, spacing, flip=False):
    """The wires of a bus following the path `points` (straight across / up and down):
    the first runs along the path, the others beside it, each `spacing` further to the right
    of the direction of travel (to the left with flip); corners stay square, so every wire
    turns with the path and the spacing holds through each turn."""
    pts = M._tidy([list(p) for p in points])
    if len(pts) < 2:
        return []
    side = -1.0 if flip else 1.0
    normals = []
    for a, b in zip(pts, pts[1:]):
        L = G.dist(a, b)
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        normals.append((uy * side, -ux * side))       # right of travel
    out = []
    for k in range(count):
        d = k * spacing
        line = [(pts[0][0] + d * normals[0][0], pts[0][1] + d * normals[0][1])]
        for j in range(1, len(pts) - 1):
            n1, n2 = normals[j - 1], normals[j]
            line.append((pts[j][0] + d * (n1[0] + n2[0]), pts[j][1] + d * (n1[1] + n2[1])))
        line.append((pts[-1][0] + d * normals[-1][0], pts[-1][1] + d * normals[-1][1]))
        out.append(line)
    return out


class BusCmd(Command):
    """BUS: several wires side by side (three phases, say). How many and how far apart, then
    click the path as for a wire: it runs straight across and up or down, turning 90 degrees
    at each click as many times as needed, all the wires turning together. F puts the other
    wires on the other side; Enter (or Esc) ends it."""
    name, title = "BUS", "Bus"

    def begin(self):
        self.count = int(getattr(self.ctx, "_bus_count", 3))
        self.spacing = float(getattr(self.ctx, "_bus_spacing", 0.5))
        self.flip = False
        self.points = []
        self.hfirst = None
        self.step = "count"
        self.ctx.prompt("Number of wires <%d>" % self.count)

    def number(self, v):
        if self.step == "count":
            if v < 2 or v != int(v) or v > 50:
                self.ctx.message("A bus has 2 to 50 wires.")
                return True
            self.count = int(v)
            self._ask_spacing()
            return True
        if self.step == "spacing":
            if v <= 0:
                return False
            self.spacing = v
            self._ask_start()
            return True
        return False

    def _ask_spacing(self):
        self.step = "spacing"
        self.ctx.prompt("Spacing between wires <%s> (inches, or 12mm)" % _fmt(self.spacing))

    def _ask_start(self):
        self.step = "path"
        self.ctx._bus_count, self.ctx._bus_spacing = self.count, self.spacing
        self.ctx.prompt("Specify start of the first wire (%d wires, %s apart)"
                        % (self.count, _fmt(self.spacing)), [("Other side", "F")])

    def enter(self):
        if self.step == "count":
            self._ask_spacing()
        elif self.step == "spacing":
            self._ask_start()
        else:
            self._make()

    def cancel(self):
        self._make()

    def _route(self, p):
        a = self.points[-1]
        h = self.hfirst
        if h is None:
            h = abs(p[0] - a[0]) >= abs(p[1] - a[1])
        from .wires import route
        return route(a, p, h)

    def point(self, p):
        if self.step != "path":
            return
        if not self.points:
            self.points = [p]
            self.base = self.last = p
            self.ctx.prompt("Specify next corner (Enter ends the bus)",
                            [("Other side", "F"), ("Undo", "U")])
            return
        if G.dist(self.points[-1], p) < 1e-9:
            return
        self.points += self._route(p)
        self.base = self.last = p

    def text(self, s):
        k = s.strip().upper()
        if self.step == "path" and k == "F":
            self.flip = not self.flip
            return True
        if self.step == "path" and k == "U" and len(self.points) > 1:
            self.points.pop()
            self.base = self.last = self.points[-1]
            return True
        return False

    def _make(self):
        made = 0
        if self.step == "path" and len(self.points) >= 2:
            paths = bus_paths(self.points, self.count, self.spacing, self.flip)
            sheet = self.ctx.sheet()
            with self.ctx.edit("Bus") as ed:
                for pts in paths:
                    w = ed.add(sheet, M.Wire(pts))
                    made += 1
                    if _cleanup_on(self.ctx):
                        from .wires import tidy_new
                        tidy_new(ed, sheet, w)
        if made:
            self.ctx.message("Bus of %d wires" % made)
        self.finish()

    def preview(self, p):
        if self.step != "path":
            return []
        if not self.points:
            return [M.Wire(q) for q in bus_paths([p, (p[0] + 0.25, p[1])], self.count,
                                                 self.spacing, self.flip)]
        return [M.Wire(q) for q in bus_paths(self.points + self._route(p), self.count,
                                             self.spacing, self.flip)]


class MakeBlockCmd(Command):
    """BLOCK: selected objects become a symbol or footprint in your library: base point, the
    details (name, kind...), then for a symbol its pins in order and where its tag goes."""
    name, title = "BLOCK", "Make block"
    selects = True
    repeatable = False

    def begin(self):
        self.ents = [e for e in _selected(self.ctx)]
        self.step = "base"
        self.ctx.prompt("Specify base point (the point the block is placed by)")

    def point(self, p):
        if self.step == "base":
            self.base_pt = self.base = self.last = p
            details = self.ctx.host.ask_block_details(self.ents)
            if details is None:
                self.finish()
                return
            self.details = details
            if details["kind"] == "symbol":
                self.pins = []
                self.step = "pins"
                self._pin_prompt()
            else:
                self._make(None)
        elif self.step == "pins":
            self.pins.append(p)
            self._pin_prompt()
        elif self.step == "tag":
            self._make(p)

    def _pin_prompt(self):
        names = self.details.get("pin_names") or []
        n = len(self.pins)
        nxt = names[n] if n < len(names) else str(n + 1)
        self.ctx.prompt("Pick pin %s, where a wire attaches (Enter when all are picked)" % nxt)

    def enter(self):
        if self.selecting():
            return Command.enter(self)
        if self.step == "pins":
            self.step = "tag"
            self.ctx.prompt("Pick where the tag goes (Enter: above the symbol)")
        elif self.step == "tag":
            self._make(None)
        else:
            self.finish()

    def _make(self, tag_pt):
        d = self.details
        bx, by = self.base_pt
        ents = []
        for e in self.ents:
            if isinstance(e, M.Insert):
                parts = e.exploded()
            else:
                parts = [e]
            for q in parts:
                c = q.moved(-bx, -by)
                c.id = None
                c.layer, c.color = "0", None
                ents.append(c)
        names = d.get("pin_names") or []
        pins = []
        for i, p in enumerate(getattr(self, "pins", [])):
            pins.append({"name": names[i] if i < len(names) else str(i + 1),
                         "pos": (p[0] - bx, p[1] - by)})
        defn = M.BlockDef(d["name"], d["kind"], ents, pins, None, 0.1, d.get("category", ""),
                          d.get("description", ""), d.get("role", "device"),
                          d.get("contact", ""), d.get("prefix", ""),
                          wiring=d.get("wiring", ""))
        if d["kind"] == "symbol":
            if tag_pt is not None:
                defn.tag_pos = (tag_pt[0] - bx, tag_pt[1] - by)
            else:
                x0, _y0, x1, y1 = defn.extents()
                defn.tag_pos = ((x0 + x1) / 2, y1 + 0.06)
        if not self.ctx.host.save_block_to_library(defn):
            self.finish()
            return
        if d.get("replace", True):
            sheet = self.ctx.sheet()
            with self.ctx.edit("Make block") as ed:
                ed.block(defn)
                for e in self.ents:
                    ed.remove(sheet, e.id)
                ins = ed.add(sheet, M.Insert(defn.name, self.base_pt,
                                             defn=self.ctx.project.blocks[defn.name],
                                             layer=self.ents[0].layer if self.ents else "0"))
            self.ctx.set_selection({ins.id})
        self.ctx.message("Saved %s %s to your library" % (
            "symbol" if d["kind"] == "symbol" else "footprint", defn.name))
        self.finish()


class InsertCmd(Command):
    """Place a symbol or footprint (from the Library panel): pick where; R turns it 90
    degrees, F flips it. A contact then asks which device it belongs to: Enter takes the one
    offered (the nearest coil with its prefix), a typed tag takes that device, L lists them."""
    name, title = "INSERT", "Insert"
    repeatable = False

    def __init__(self, ctx, defn, attrs=None):
        super().__init__(ctx)
        self.defn, self.attrs = defn, dict(attrs or {})
        self.angle, self.mirror = 0.0, False
        self.pending = None             # a contact's point, waiting for its device
        self.cands = []
        self.link_name = None           # an off-sheet connector's name offered

    def begin(self):
        self.ctx.prompt("Specify insertion point for %s" % self.defn.name,
                        [("Rotate 90", "R"), ("Flip", "F")])

    def text(self, s):
        k = s.strip().upper()
        if self.pending is not None and self.link_name is not None:
            self._place(self.pending, dict(self.attrs, TAG=k))
            return True
        if self.pending is not None:
            from . import tags
            if k == "L":
                pick = getattr(self.ctx.host, "pick_parent", None)
                got = pick(self.cands) if pick is not None else None
                if got is not None:
                    self._place(self.pending, tags.link_attrs(self.attrs, got[1]))
                return True
            got = tags.find_tag(self.ctx.project, k)
            if got is not None:
                self._place(self.pending, tags.link_attrs(self.attrs, got[1]))
            else:
                # no device has that tag yet: the contact keeps it and links itself to the
                # device that gets it
                self._place(self.pending, dict(self.attrs, TAG=k))
                self.ctx.message("No device is tagged %s yet: the contact links to it once "
                                 "one is" % k)
            return True
        if k == "R":
            self.angle = (self.angle + 90.0) % 360.0
            return True
        if k == "F":
            self.mirror = not self.mirror
            return True
        return False

    def enter(self):
        if self.pending is not None and self.link_name is not None:
            self._place(self.pending, dict(self.attrs, TAG=self.link_name))
            return
        if self.pending is not None and self.cands:
            from . import tags
            self._place(self.pending, tags.link_attrs(self.attrs, self.cands[0][1]))
            return
        super().enter()

    def _make(self, p, defn):
        layer = "SYMBOLS" if self.defn.kind == "symbol" else "PANEL"
        tag_h = self.ctx.project.settings.get("tag_height") * self.ctx.sheet().k() \
            if self.defn.kind == "symbol" else None
        return M.Insert(self.defn.name, p, self.angle, 1.0, self.mirror, self.attrs, defn,
                        tag_h, layer=layer)

    def preview(self, p):
        return [self._make(self.pending if self.pending is not None else p, self.defn)]

    def point(self, p):
        if self.pending is not None:
            return                      # (waiting for the contact's device)
        d = self.defn
        if d.wiring == "link" and not self.attrs.get("TAG"):
            # an off-sheet connector: its name pairs it with the other end
            from .wirenums import next_name, connectors
            self.pending = p
            self.link_name = next_name(self.ctx.project, self.ctx.sheet())
            waiting = self.link_name in connectors(self.ctx.project)
            self.ctx.prompt("Connector name: Enter for %s (%s), or type a name"
                            % (self.link_name, "continues the wire from another sheet"
                               if waiting else "a new one"))
            return
        if d.kind == "symbol" and d.role == "child" and not self.attrs.get("PARENT") \
                and not self.attrs.get("TAG"):
            from . import tags
            project = self.ctx.project
            self.cands = tags.candidates(project, self.ctx.sheet(), d.prefix, p)
            if self.cands:
                self.pending = p
                s, e = self.cands[0]
                self.ctx.prompt("Belongs to: Enter for %s (%s), or type a tag"
                                % (e.attrs.get("TAG", "?"),
                                   project.zone_text(s, e.pos[0], e.pos[1]) or "?"),
                                [("List", "L")])
                return
            self.ctx.message("Nothing to link this %s to yet (a %s device): placed unlinked "
                             "(double-click it to link it later)"
                             % (d.name.lower(), d.prefix or "parent"))
        self._place(p, self.attrs)

    def _place(self, p, attrs):
        project = self.ctx.project
        sheet = self.ctx.sheet()
        with self.ctx.edit("Insert %s" % self.defn.name) as ed:
            if self.defn.name not in project.blocks:
                # the project keeps its own copy (a block already in it stays as it was)
                ed.block(self.defn)
            from . import tags
            defn = project.blocks[self.defn.name]
            ins = self._make(p, defn).copy(attrs=attrs)
            ins = ins.copy(attrs=tags.new_attrs(project, sheet, defn, ins.attrs))
            if ins.layer not in project.layers:
                ed.layer(ins.layer, None, M.Layer(ins.layer, M.ADAPTIVE).to_dict())
            ed.add(sheet, ins)
            if self.defn.kind == "symbol":
                # placed on a wire: the wire is cut between its pins
                from .wires import break_under
                if break_under(ed, sheet, ins):
                    self.ctx.message("Wire cut to fit %s" % self.defn.name)
        self.ctx.set_selection(set())
        self.finish()


class ExplodeCmd(Command):
    """EXPLODE: block references become their lines, arcs and texts."""
    name, title = "EXPLODE", "Explode"
    selects = True

    def begin(self):
        sheet = self.ctx.sheet()
        n = 0
        new = set()
        with self.ctx.edit("Explode") as ed:
            for e in _selected(self.ctx):
                if isinstance(e, M.Insert):
                    ed.remove(sheet, e.id)
                    for q in e.exploded():
                        new.add(ed.add(sheet, q).id)
                    n += 1
        self.ctx.set_selection(new)
        self.ctx.message("Exploded %d block(s)" % n if n else "Nothing to explode: select "
                         "symbols or footprints")
        self.finish()


def _fmt(v):
    return ("%.4f" % v).rstrip("0").rstrip(".")


# name -> (class, aliases); the command line accepts the name or any alias
class DimLinearCmd(Command):
    """DIMLINEAR: a dimension across or up and down. Pick the two points it measures, then
    where its line goes: it reads the true distance (real size on a panel sheet), and its text
    is paper-sized (it prints the same at any scale)."""
    name, title = "DIMLINEAR", "Linear dimension"
    mode = "linear"

    def begin(self):
        self.pts = []
        self.ctx.prompt("Specify first extension line origin")

    def _height(self):
        return float(self.ctx.project.settings.get("dim_height", 0.1)) * self.ctx.sheet().k()

    def point(self, p):
        self.pts.append(p)
        self.base = self.last = p
        if len(self.pts) == 1:
            self.ctx.prompt("Specify second extension line origin")
        elif len(self.pts) == 2:
            self.ctx.prompt("Specify dimension line location")
        else:
            d = M.Dimension(self.pts[0], self.pts[1], p, self.mode, self._height())
            with self.ctx.edit(self.title) as ed:
                if d.layer not in self.ctx.project.layers:
                    ed.layer(d.layer, None, M.Layer(d.layer, "#00c8c8").to_dict())
                ed.add(self.ctx.sheet(), d)
            self.ctx.message("%s %s" % (self.title, d.label()))
            self.finish()

    def preview(self, p):
        if len(self.pts) == 1:
            return [M.Line(self.pts[0], p)]
        if len(self.pts) == 2:
            return [M.Dimension(self.pts[0], self.pts[1], p, self.mode, self._height())]
        return []


class DimAlignedCmd(DimLinearCmd):
    """DIMALIGNED: a dimension along the line between the two points (slanted ones too)."""
    name, title = "DIMALIGNED", "Aligned dimension"
    mode = "aligned"


def parse_duct_size(text):
    """2x3, 2 x 3, 1.5x3 (inches) or 50x75mm -> (width, depth) in inches, or None."""
    import re
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*[xX*]\s*(\d+(?:\.\d+)?)\s*(mm)?\s*", text or "")
    if not m:
        return None
    w, d = float(m.group(1)), float(m.group(2))
    if m.group(3):
        w, d = w / 25.4, d / 25.4
    return (w, d) if w > 0 and d > 0 else None


class _RunCmd(Command):
    """Draw a straight real-size piece: its start, then its end (or a typed length toward
    the cursor). Size options before the first click."""
    kind = None

    def begin(self):
        self.p1 = None
        self._prompt_start()

    def point(self, p):
        if self.p1 is None:
            self.p1 = self.base = self.last = p
            self.ctx.prompt("Specify end point, or type the length (toward the cursor)")
            return
        if G.dist(self.p1, p) < 1e-6:
            return
        e = self.make(self.p1, p)
        with self.ctx.edit(self.title) as ed:
            if e.layer not in self.ctx.project.layers:
                ed.layer(e.layer, None, M.Layer(e.layer).to_dict())
            ed.add(self.ctx.sheet(), e)
        self.ctx.message("%s, %s long" % (e.name(), M.fmt_inches(e.length())))
        self.finish()

    def preview(self, p):
        if self.p1 is None or G.dist(self.p1, p) < 1e-6:
            return []
        return [self.make(self.p1, p)]


class RailCmd(_RunCmd):
    """DINRAIL: DIN rail at real size, from one end to the other. Profiles: 7.5 (TS35 x 7.5
    mm, to start), 15 (TS35 x 15 mm), MINI (TS15)."""
    name, title = "DINRAIL", "DIN rail"
    PICK = {"7.5": "TS35x7.5", "TS35X7.5": "TS35x7.5", "15": "TS35x15", "TS35X15": "TS35x15",
            "MINI": "TS15", "TS15": "TS15"}

    def _profile(self):
        key = self.ctx.project.settings.get("rail_profile", "TS35x7.5")
        return key if key in M.RAIL_PROFILES else "TS35x7.5"

    def _prompt_start(self):
        self.ctx.prompt("Specify start point (%s)" % M.RAIL_PROFILES[self._profile()][0],
                        [("TS35 x 7.5", "7.5"), ("TS35 x 15", "15"), ("TS15 mini", "MINI")])

    def text(self, s):
        key = self.PICK.get(s.strip().upper())
        if key is None or self.p1 is not None:
            return False
        self.ctx.project.settings["rail_profile"] = key
        self._prompt_start()
        return True

    def make(self, a, b):
        key = self._profile()
        _n, w, d = M.RAIL_PROFILES[key]
        return M.Rail(a, b, key, w, d)


class DuctCmd(_RunCmd):
    """DUCT: wire duct at real size, from one end to the other. Type its size first: width x
    depth, 2x3 (inches) or 50x75mm."""
    name, title = "DUCT", "Wire duct"

    def _size(self):
        got = self.ctx.project.settings.get("duct_size", [2.0, 3.0])
        return float(got[0]), float(got[1])

    def _prompt_start(self):
        self.ctx.prompt("Specify start point (%s; type another size: 2x3, 1.5x3, 50x75mm)"
                        % M.size_text(*self._size()))

    def text(self, s):
        got = parse_duct_size(s)
        if got is None or self.p1 is not None:
            return False
        self.ctx.project.settings["duct_size"] = [got[0], got[1]]
        self._prompt_start()
        return True

    def make(self, a, b):
        w, d = self._size()
        return M.Duct(a, b, "", w, d)


class ScootCmd(_TwoPoint):
    """SCOOT (AutoCAD Electrical's): slide devices along their own wire. Select them, a base
    point, then where to: they move only along their wire (across a rung, or up and down a
    vertical wire), and the wires on their pins stretch and shorten with them, staying
    straight. They stop short of a wire's far end or corner."""
    name, title = "SCOOT", "Scoot"

    def begin(self):
        from . import scoot
        self.devs = scoot.devices(_selected(self.ctx))
        if not self.devs:
            self.ctx.message("Scoot: select symbols on a wire (devices, contacts, terminals...)")
            self.finish()
            return
        self.ax = scoot.axis(self.devs[0])
        self.ents = self.devs
        self.from_pt = None
        self.ctx.prompt("Specify base point")

    def _slide(self, p):
        from . import scoot
        d = (p[0] - self.from_pt[0]) * self.ax[0] + (p[1] - self.from_pt[1]) * self.ax[1]
        sheet = self.ctx.sheet()
        for e in self.devs:                 # (all together: as far as the tightest allows)
            if scoot.axis(e) == self.ax:
                d = scoot.clamp(sheet, e, self.ax, d)
        return d

    def result(self, p):
        from . import scoot
        d = self._slide(p)
        return [e.moved(self.ax[0] * d, self.ax[1] * d) if scoot.axis(e) == self.ax else e
                for e in self.devs]

    def apply(self, p):
        d = self._slide(p)
        sheet = self.ctx.sheet()
        with self.ctx.edit(self.title) as ed:
            for e in self.result(p):
                ed.change(sheet, e)
        self.ctx.message("Scooted %s" % M.fmt_inches(abs(d)))
        self.finish()


class AlignDevicesCmd(Command):
    """AEALIGN (AutoCAD Electrical's Align): click the device to line up with, then the
    devices to line up; Enter. Each slides along its own wire (as Scoot) until it is in line:
    in the same column on rungs across, in the same row on wires up and down."""
    name, title = "AEALIGN", "Align devices"
    repeatable = True

    def begin(self):
        self.picking = True
        self.ref = None
        self.targets = []
        self.ctx.prompt("Click the device to line up with")

    def pick(self, p):
        from . import scoot
        e = self.ctx.pick_entity(p)
        if not (isinstance(e, M.Insert) and scoot.axis(e) is not None):
            self.ctx.message("Click a symbol on a wire")
            return
        if self.ref is None:
            self.ref = e
            self.ctx.prompt("Click the devices to line up (Enter when done)")
            self.ctx.set_selection({e.id})
            return
        if e.id != self.ref.id and all(t.id != e.id for t in self.targets):
            self.targets.append(e)
            self.ctx.set_selection({self.ref.id} | {t.id for t in self.targets})

    def enter(self):
        from . import scoot
        if self.ref is None or not self.targets:
            self.finish()
            return
        sheet = self.ctx.sheet()
        short = 0
        with self.ctx.edit(self.title) as ed:
            for t in self.targets:
                cur = sheet.entities.get(t.id, t)
                ax = scoot.axis(cur)
                want = (self.ref.pos[0] - cur.pos[0]) * ax[0] + \
                    (self.ref.pos[1] - cur.pos[1]) * ax[1]
                d = scoot.clamp(sheet, cur, ax, want)
                if abs(d - want) > 1e-9:
                    short += 1
                if abs(d) > 1e-12:
                    ed.change(sheet, cur.moved(ax[0] * d, ax[1] * d))
        self.ctx.set_selection(set())
        self.ctx.message("Lined up %d device(s)%s" % (
            len(self.targets) - short, "; %d stopped where their wire ends" % short
            if short else ""))
        self.finish()

    def cancel(self):
        self.ctx.set_selection(set())


class TrimWireCmd(Command):
    """TRIMWIRE (AutoCAD Electrical's Trim Wire): click a wire and the piece clicked goes, up
    to the nearest wire or pin on either side (to its end when there is none). No cutting
    edges to choose; only wires are trimmed."""
    name, title = "TRIMWIRE", "Trim wire"

    def begin(self):
        self.picking = True
        self.done = 0
        self.ctx.set_selection(set())
        self.ctx.prompt("Click the piece of wire to trim (Enter to finish)", [("Undo", "U")])

    def pick(self, p):
        from . import wires
        sheet = self.ctx.sheet()
        w = _pick_wire(self.ctx, p)
        if w is None:
            self.ctx.message("Click a wire")
            return
        pieces, ends = wires.trim_wire(sheet, w, p)
        with self.ctx.edit(self.title) as ed:
            ed.remove(sheet, w.id)
            for e in pieces:
                ed.add(sheet, e)
            if _cleanup_on(self.ctx):
                wires.join_at(ed, sheet, ends)
        self.done += 1

    def text(self, s):
        if s.strip().upper() == "U":
            if self.done:
                self.ctx.undo()
                self.done -= 1
            return True
        return False


def _pick_wire(ctx, p):
    """The wire under p (a wire even where a symbol's line is nearer), or None."""
    return ctx.pick_entity(p, M.Wire)


class DeleteWireCmd(Command):
    """DELWIRE (AutoCAD Electrical's Delete Wires): the selected wires go (anything else
    selected stays), or click wires one by one. Wires left meeting end to end become one."""
    name, title = "DELWIRE", "Delete wire"

    def begin(self):
        sel = [e for e in _selected(self.ctx) if isinstance(e, M.Wire)]
        if sel:
            self._delete(sel)
            self.ctx.set_selection(set())
            self.finish()
            return
        self.picking = True
        self.ctx.prompt("Click the wires to delete (Enter to finish)")

    def pick(self, p):
        w = _pick_wire(self.ctx, p)
        if w is None:
            self.ctx.message("Click a wire")
            return
        self._delete([w])

    def _delete(self, ws):
        from . import wires
        sheet = self.ctx.sheet()
        with self.ctx.edit(self.title) as ed:
            for w in ws:
                ed.remove(sheet, w.id)
            if _cleanup_on(self.ctx):
                wires.join_at(ed, sheet, wires._ends(ws))
        self.ctx.message("Deleted %d wire(s)" % len(ws))


class DeleteComponentCmd(Command):
    """DELCOMP (AutoCAD Electrical's Delete Component): the selected symbols go (anything
    else selected stays), or click them one by one, and the wire each sat on is joined back
    up through where it was. Erase (the Delete key) leaves the gap."""
    name, title = "DELCOMP", "Delete component"

    def begin(self):
        sel = [e for e in _selected(self.ctx) if isinstance(e, M.Insert)]
        if sel:
            self._delete(sel)
            self.ctx.set_selection(set())
            self.finish()
            return
        self.picking = True
        self.ctx.prompt("Click the components to delete (Enter to finish)")

    def pick(self, p):
        e = self.ctx.pick_entity(p, M.Insert)
        if e is None:
            self.ctx.message("Click a symbol")
            return
        self._delete([e])

    def _delete(self, items):
        from . import wires
        sheet = self.ctx.sheet()
        joined = 0
        with self.ctx.edit(self.title) as ed:
            for e in items:
                ed.remove(sheet, e.id)
            for e in items:
                joined += wires.heal(ed, sheet, e)
        self.ctx.message("Deleted %d component(s)%s" % (
            len(items), "; %d wire(s) joined back up" % joined if joined else ""))


class CleanWiresCmd(Command):
    """WIRECLEAN: clean up the selected wires, or every wire on the sheet: wires of no length,
    repeated or in-line points, a wire drawn over another, and wires meeting end to end (made
    one). Then says how many wire ends connect to nothing."""
    name, title = "WIRECLEAN", "Clean up wires"
    repeatable = False

    def begin(self):
        from . import wires
        sheet = self.ctx.sheet()
        sel = [e for e in _selected(self.ctx) if isinstance(e, M.Wire)]
        with self.ctx.edit(self.title) as ed:
            got = wires.cleanup(ed, sheet, sel or None)
        self.ctx.set_selection(set())
        done = ["%d %s" % (got[k], label) for k, label in (
            ("joined", "joined end to end"), ("duplicates", "drawn twice, removed"),
            ("empty", "of no length, removed"), ("tidied", "with extra points, tidied"))
            if got[k]]
        self.ctx.message("Clean up wires (%s): %s. %s" % (
            "selected wires" if sel else "this sheet", ", ".join(done) if done else
            "nothing to clean up",
            "%d wire end(s) connect to nothing." % got["loose"] if got["loose"]
            else "Every wire end connects to something."))
        self.finish()


class WireCrossCmd(Command):
    """WIRECROSS: a wire crossing placed by hand. Click a wire where it should jump (on a
    crossing, or anywhere else on it); G, L or N first for a gap, a loop or none (none hides a
    crossing found by itself). Erase the mark to take it away."""
    name, title = "WIRECROSS", "Wire crossing"
    NAMES = {"G": "gap", "L": "loop", "N": "none"}

    def begin(self):
        st = self.ctx.project.settings.get("wire_crossing", "plain")
        self.style = st if st in ("gap", "loop") else "loop"
        self._prompt()

    def _prompt(self):
        self.ctx.prompt("Click a wire where it should jump (%s)" % {
            "gap": "a gap", "loop": "a loop", "none": "none: hides a crossing"}[self.style],
            [("Gap", "G"), ("Loop", "L"), ("None", "N")])

    def text(self, s):
        k = self.NAMES.get(s.strip().upper())
        if k is None:
            return False
        self.style = k
        self._prompt()
        return True

    def point(self, p):
        from . import crossings
        sheet = self.ctx.sheet()
        tol = 0.1 * sheet.k()
        at = crossings.place_at(self.ctx.project, sheet, p, tol)
        if at is None:
            self.ctx.message("No wire there: click on a wire (or where two cross)")
            return
        with self.ctx.edit(self.title) as ed:
            # (one mark per spot: a new one replaces the old)
            for e in sheet.query((at[0] - 1e-3, at[1] - 1e-3, at[0] + 1e-3, at[1] + 1e-3)):
                if isinstance(e, M.WireCross) and G.dist(e.pos, at) < 1e-3:
                    ed.remove(sheet, e.id)
            ed.add(sheet, M.WireCross(at, self.style))
        self.ctx.message("Wire crossing: %s" % self.style)
        self._prompt()


# ---- layers, quickly (AutoCAD's LAYOFF, LAYISO, LAYON, LAYLCK, LAYULK) --------------------------
def set_layers(ctx, name, changes):
    """One undoable step: {layer name: {"visible": ..., "locked": ...}}. Returns how many
    changed."""
    p = ctx.project
    n = 0
    with ctx.edit(name) as ed:
        for lname, ch in changes.items():
            lay = p.layers.get(lname)
            if lay is None:
                continue
            before = lay.to_dict()
            after = dict(before, **ch)
            if after != before:
                ed.layer(lname, before, after)
                n += 1
    return n


class _LayerPickCmd(Command):
    """Acts on the layers of the selected objects, or of an object clicked."""
    verb = ""

    def begin(self):
        sel = _selected(self.ctx)
        if sel:
            self.act({e.layer for e in sel})
            self.ctx.set_selection(set())
            self.finish()
            return
        self.picking = True
        self.ctx.prompt("Select an object on the layer to %s" % self.verb)

    def pick(self, p):
        e = self.ctx.pick_entity(p)
        if e is None:
            self.ctx.message("Nothing there: click an object")
            return
        self.act({e.layer})
        self.finish()


class LayerOffCmd(_LayerPickCmd):
    """LAYOFF: hide the layer of an object (clicked, or selected)."""
    name, title, verb = "LAYOFF", "Hide layer", "hide"

    def act(self, names):
        n = set_layers(self.ctx, self.title, {k: {"visible": False} for k in names})
        self.ctx.message("Hidden: %s (Show all layers brings it back)" % ", ".join(sorted(names))
                         if n else "Already hidden")


class LayerIsoCmd(_LayerPickCmd):
    """LAYISO: show only the layer of an object (clicked, or the selected objects' layers)."""
    name, title, verb = "LAYISO", "Show only this layer", "show alone"

    def act(self, names):
        ch = {k: {"visible": k in names} for k in self.ctx.project.layers}
        set_layers(self.ctx, self.title, ch)
        self.ctx.message("Showing only: %s (Show all layers brings the others back)"
                         % ", ".join(sorted(names)))


class LayerLockCmd(_LayerPickCmd):
    """LAYLCK: lock the layer of an object (clicked, or selected)."""
    name, title, verb = "LAYLCK", "Lock layer", "lock"

    def act(self, names):
        set_layers(self.ctx, self.title, {k: {"locked": True} for k in names})
        self.ctx.message("Locked: %s (Unlock all layers frees it)" % ", ".join(sorted(names)))


class LayerOnCmd(Command):
    """LAYON: show every layer."""
    name, title = "LAYON", "Show all layers"
    repeatable = False

    def begin(self):
        n = set_layers(self.ctx, self.title, {k: {"visible": True}
                                              for k in self.ctx.project.layers})
        self.ctx.message("All layers shown" if n else "Every layer was already shown")
        self.finish()


class LayerUnlockAllCmd(Command):
    """LAYULK: unlock every layer."""
    name, title = "LAYULK", "Unlock all layers"
    repeatable = False

    def begin(self):
        n = set_layers(self.ctx, self.title, {k: {"locked": False}
                                              for k in self.ctx.project.layers})
        self.ctx.message("All layers unlocked" if n else "No layer was locked")
        self.finish()


COMMANDS = {
    "LINE": (LineCmd, ["L"]),
    "PLINE": (PolylineCmd, ["PL"]),
    "RECTANG": (RectangleCmd, ["REC", "RECTANGLE"]),
    "CIRCLE": (CircleCmd, ["C"]),
    "ARC": (ArcCmd, ["A"]),
    "TEXT": (TextCmd, ["T", "DT", "DTEXT"]),
    "MOVE": (MoveCmd, ["M"]),
    "COPY": (CopyCmd, ["CO", "CP"]),
    "ROTATE": (RotateCmd, ["RO"]),
    "SCALE": (ScaleCmd, ["SC"]),
    "MIRROR": (MirrorCmd, ["MI"]),
    "ERASE": (EraseCmd, ["E"]),
    "TRIM": (TrimCmd, ["TR"]),
    "ZOOM": (ZoomCmd, ["Z"]),
    "BLOCK": (MakeBlockCmd, ["B"]),
    "WIRE": (WireCmd, ["W"]),
    "BUS": (BusCmd, ["BU"]),
    "EXPLODE": (ExplodeCmd, ["X"]),
    "DIMLINEAR": (DimLinearCmd, ["DLI", "DIM"]),
    "DIMALIGNED": (DimAlignedCmd, ["DAL"]),
    "DINRAIL": (RailCmd, ["RAIL", "DR"]),
    "DUCT": (DuctCmd, ["WIREWAY", "WD"]),
    "SCOOT": (ScootCmd, ["AESCOOT"]),
    "AEALIGN": (AlignDevicesCmd, ["ALIGNDEV"]),
    "LAYOFF": (LayerOffCmd, []),
    "LAYISO": (LayerIsoCmd, []),
    "LAYON": (LayerOnCmd, []),
    "LAYLCK": (LayerLockCmd, []),
    "LAYULK": (LayerUnlockAllCmd, []),
    "WIRECROSS": (WireCrossCmd, ["WX"]),
    "TRIMWIRE": (TrimWireCmd, ["AETRIM", "TW"]),
    "DELWIRE": (DeleteWireCmd, ["DW"]),
    "WIRECLEAN": (CleanWiresCmd, ["CLEANWIRES"]),
    "DELCOMP": (DeleteComponentCmd, ["AEERASECOMP"]),
}

# commands the command line runs that aren't drawing commands (the window handles them)
OTHER = {"U": "undo", "UNDO": "undo", "REDO": "redo", "QSAVE": "save", "SAVE": "save",
         "OPEN": "open", "NEW": "new", "QUIT": "quit", "EXIT": "quit"}


def lookup(text):
    """The command class for a typed name or alias, or None."""
    t = (text or "").strip().upper()
    for name, (cls, aliases) in COMMANDS.items():
        if t == name or t in aliases:
            return cls
    return None
