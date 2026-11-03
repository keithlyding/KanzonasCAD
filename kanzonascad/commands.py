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
    name, title = "TEXT", "Text"

    JUSTIFY_PROMPT = "Justification: L, C, R (on the baseline); TL, TC, TR (top); ML, MC, MR " \
                     "(middle); BL, BC, BR (bottom)"

    def begin(self):
        self.pos = None
        self._start_prompt()

    def _start_prompt(self):
        self.step = "pos"
        code = M.justify_code(*self.ctx.text_justify)
        self.ctx.prompt("Specify %s point of text (justification %s)" % (
            "start" if code in ("L", "BL") else "insertion", code), [("Justify", "J")])

    def point(self, p):
        if self.step == "justify":
            return
        if self.step == "pos":
            self.pos = self.base = self.last = p
            self.step = "height"
            self.ctx.prompt("Specify height <%s>" % _fmt(self.ctx.text_height()))
        elif self.step == "height":
            self.number(G.dist(self.pos, p))
        elif self.step == "angle":
            self.number(G.angle_of(self.pos, p))

    def number(self, v):
        if self.step == "height" and v > 0:
            self.ctx.set_text_height(v)
            self.step = "angle"
            self.ctx.prompt("Specify rotation angle <0>")
            return True
        if self.step == "angle":
            self.angle = v
            self.step = "text"
            self.ctx.prompt("Enter text (Enter on an empty line ends)", typing=True)
            return True
        return False

    def wants_raw_text(self):
        return self.step == "text"

    def text(self, s):
        k = s.strip().upper()
        if self.step == "pos" and k == "J":
            self.step = "justify"
            self.ctx.prompt(self.JUSTIFY_PROMPT,
                            [(code, code) for code in ("TL", "TC", "TR", "ML", "MC", "MR",
                                                       "BL", "BC", "BR", "L", "C", "R")])
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
        if self.step == "height":
            self.number(self.ctx.text_height())
        elif self.step == "angle":
            self.number(0.0)
        elif self.step == "text":
            self.finish()
        else:
            self.finish()

    def preview(self, p):
        if self.step == "pos":
            return [M.Text(p, "Text", self.ctx.text_height(), 0.0, *self.ctx.text_justify)]
        if self.step in ("height", "angle"):
            return [M.Line(self.pos, p)]
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
        sheet = self.ctx.sheet()
        with self.ctx.edit("Copy") as ed:
            for e in self.result(p):
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
            for e in self.result(self.to_pt):
                if not erase:
                    e.id = None
                    ed.add(sheet, e)
                else:
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
            for e in self.result(p):
                if isinstance(e, M.Insert):
                    e.defn = self.ctx.project.blocks.get(e.block, e.defn)
                    e._world = None
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
        a = self.points[-1]
        h = self.hfirst
        if h is None:
            h = abs(p[0] - a[0]) >= abs(p[1] - a[1])
        from .wires import route
        return route(a, p, h)

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
            with self.ctx.edit("Wire") as ed:
                ed.add(self.ctx.sheet(), M.Wire(pts))
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
            with self.ctx.edit("Bus") as ed:
                for pts in paths:
                    ed.add(self.ctx.sheet(), M.Wire(pts))
                    made += 1
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
                          d.get("contact", ""), d.get("prefix", ""))
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
    degrees, F flips it."""
    name, title = "INSERT", "Insert"
    repeatable = False

    def __init__(self, ctx, defn, attrs=None):
        super().__init__(ctx)
        self.defn, self.attrs = defn, dict(attrs or {})
        self.angle, self.mirror = 0.0, False

    def begin(self):
        self.ctx.prompt("Specify insertion point for %s" % self.defn.name,
                        [("Rotate 90", "R"), ("Flip", "F")])

    def text(self, s):
        k = s.strip().upper()
        if k == "R":
            self.angle = (self.angle + 90.0) % 360.0
            return True
        if k == "F":
            self.mirror = not self.mirror
            return True
        return False

    def _make(self, p, defn):
        layer = "SYMBOLS" if self.defn.kind == "symbol" else "PANEL"
        tag_h = self.ctx.project.settings.get("tag_height") if self.defn.kind == "symbol" \
            else None
        return M.Insert(self.defn.name, p, self.angle, 1.0, self.mirror, self.attrs, defn,
                        tag_h, layer=layer)

    def preview(self, p):
        return [self._make(p, self.defn)]

    def point(self, p):
        project = self.ctx.project
        sheet = self.ctx.sheet()
        with self.ctx.edit("Insert %s" % self.defn.name) as ed:
            if self.defn.name not in project.blocks:
                # the project keeps its own copy (a block already in it stays as it was)
                ed.block(self.defn)
            ins = self._make(p, project.blocks[self.defn.name])
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
