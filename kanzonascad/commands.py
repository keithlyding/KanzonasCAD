"""AutoCAD-style commands: each is a small state machine the view feeds with picked points,
typed values and Enter. Commands talk to the view only through its context methods (prompt,
selection, pick, edit), so the self-test can drive them without a mouse.

Typed input (see parse_point): "3,4" absolute, "@1,0" relative to the last point, "@2<45"
relative polar, a plain number = that distance toward the cursor (direct distance entry).
"""

import re

from . import geometry as G
from . import model as M
from .wires import doubles_back, straighten
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
    """A typed point, or None. last: the point "@" is relative to. "#x,y" is x,y itself
    (AutoCAD's absolute mark), where a command takes a plain x,y as a size."""
    t = to_inches(text).strip()
    if t.startswith("#"):
        t = t[1:].strip()
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


def size_typed(cmd, text):
    """A plain "x,y" typed for a box's second corner is its size from the first corner (as
    AutoCAD's dynamic input takes it; the owner: "I'm trying to make a rectangle that is
    0.19x0.15" and it's coming out as 8.76x3.76"": typed as a size, it was taken as the corner
    0.19,0.15 of the sheet). "#x,y" is that point itself; "@x,y" as always. A size typed
    without a sign goes the way the cursor is from the first corner (the owner, 0.18.2: "I set
    it to 72,72. It built the rectangle to the right dimensions but in a different direction
    than my mouse was moving"); a sign typed (-72, +72) says which way. The point, or None
    when it isn't a plain x,y."""
    t = to_inches(text).strip()
    m = _RE_ABS.match(t)
    if m is None or cmd.last is None:
        return None
    a = cmd.last
    cur = cmd.ctx.cursor_point() if hasattr(cmd.ctx, "cursor_point") else None
    out = []
    for k, raw in ((0, m.group(1)), (1, m.group(2))):
        v = float(raw)
        if raw.strip()[:1] not in "+-" and cur is not None and cur[k] < a[k] - 1e-9:
            v = -v                      # (toward the cursor)
        out.append(a[k] + v)
    return tuple(out)


class RectangleCmd(Command):
    """RECTANG: two corners; after the first, a typed width,height is its size (#x,y: a
    point), and D asks its length and width, then a click says which way it goes."""
    name, title = "RECTANG", "Rectangle"

    def begin(self):
        self.first = None
        self.dims = None                # (D: [length, width] typed so far)
        self.ctx.prompt("Specify first corner")

    @staticmethod
    def _rect(a, b):
        return M.Polyline([a, (b[0], a[1]), b, (a[0], b[1])], True)

    def _corner(self, p):
        """The other corner for the cursor at p: with both sizes typed (D), that size,
        toward p."""
        if self.dims is not None and len(self.dims) == 2:
            a = self.first
            return (a[0] + self.dims[0] * (1 if p[0] >= a[0] else -1),
                    a[1] + self.dims[1] * (1 if p[1] >= a[1] else -1))
        return p

    def text(self, s):
        if self.first is None:
            return False
        k = s.strip().upper()
        if k == "D":
            self.dims = []
            self.ctx.prompt("Specify length (across)")
            return True
        if self.dims is None:
            q = size_typed(self, s)
            if q is not None:
                self.point(q)
                return True
        return False

    def number(self, v):
        if self.dims is None or len(self.dims) >= 2 or v <= 0:
            return False
        self.dims.append(v)
        self.ctx.prompt("Specify width (up and down)" if len(self.dims) == 1 else
                        "Click on the side it goes (or Enter: up and right)")
        return True

    def enter(self):
        if self.dims is not None and len(self.dims) == 2:
            self.point((self.first[0] + 1.0, self.first[1] + 1.0))
            return
        Command.enter(self)

    def point(self, p):
        if self.first is None:
            self.first = self.last = p
            self.ctx.prompt("Specify other corner (or width,height; D for dimensions)",
                            [("Dimensions", "D")])
            return
        if self.dims is not None and len(self.dims) < 2:
            return                      # (waiting for the length and width)
        p = self._corner(p)
        if abs(p[0] - self.first[0]) < 1e-9 or abs(p[1] - self.first[1]) < 1e-9:
            return
        r = self._rect(self.first, p)
        r.layer = self.ctx.layer()
        with self.ctx.edit("Rectangle") as ed:
            ed.add(self.ctx.sheet(), r)
        self.ctx.message("Rectangle %s x %s" % (_fmt(abs(p[0] - self.first[0])),
                                                _fmt(abs(p[1] - self.first[1]))))
        self.finish()

    def preview(self, p):
        if not self.first or (self.dims is not None and len(self.dims) < 2):
            return []
        return [self._rect(self.first, self._corner(p))]


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
    copies = False                      # (Copy: the objects stay, neighbors on a rail)

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

    def delta(self, p):
        """How far the objects go for the second point p: a footprint coming over a DIN rail
        locks onto it (CadView.rail_magnet; the same for the preview and the click)."""
        dx, dy = p[0] - self.from_pt[0], p[1] - self.from_pt[1]
        mag = getattr(self.ctx, "rail_magnet", None)
        return mag(self.ents, dx, dy, self.copies) if mag is not None else (dx, dy)

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
        dx, dy = self.delta(p)
        return self.ents, dx, dy

    def result(self, p):
        dx, dy = self.delta(p)
        return [e.moved(dx, dy) for e in self.ents]

    def apply(self, p):
        sheet = self.ctx.sheet()
        with self.ctx.edit("Move") as ed:
            for e in self.result(p):
                ed.change(sheet, e)
        self.finish()


class CopyCmd(_TwoPoint):
    name, title = "COPY", "Copy"
    copies = True
    shift = MoveCmd.shift

    def second_prompt(self):
        self.ctx.prompt("Specify second point (Enter to finish)")

    def result(self, p):
        dx, dy = self.delta(p)
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
        if self.from_pt is None:
            return []
        if self.to_pt is not None:
            # (asked whether to erase the originals: the mirrored objects shown where they'll
            # be meanwhile; the owner, 0.16: they didn't show until the question was answered)
            return self.result(self.to_pt) + [M.Line(self.from_pt, self.to_pt)]
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

    def _cutters(self, ent):
        sheet = self.ctx.sheet()
        return [c for c in sheet.query(ent.bbox()) if c.id != ent.id
                and self.ctx.layer_visible(c.layer)]

    def hover_parts(self, ent, p):
        """What a click at p on ent would cut away, lit as the cursor goes over it (CadView),
        not the whole object; [] when it can't be trimmed."""
        from .trim import trimmed_away
        return trimmed_away(ent, p, self._cutters(ent)) or []

    def pick(self, p):
        ent = self.ctx.pick_entity(p)
        if ent is None:
            return
        sheet = self.ctx.sheet()
        cutters = self._cutters(ent)
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

    def __init__(self, ctx, ent, index, others=()):
        super().__init__(ctx)
        self.ent, self.index = ent, index
        self.base = self.last = ent.grips()[index]
        # (several grips picked with Shift: they all move the same way, the owner, 0.18;
        # [(entity, grip index)] besides this one)
        self.others = [(e, k) for e, k in others if (e.id, k) != (ent.id, index)]

    def begin(self):
        self.ctx.prompt("Specify stretch point")

    def _run(self):
        """A wire's run (the middle grip of segment k), or None."""
        e = self.ent
        if isinstance(e, M.Wire) and self.index >= len(e.points):
            return self.index - len(e.points)
        return None

    def _dragged(self, p):
        """{id: new entity} a drag of the grip to p gives (a wire's run: the wires joined to
        it too)."""
        k = self._run()
        if self.others:
            dx, dy = p[0] - self.base[0], p[1] - self.base[1]
            out = {}
            for e, i in [(self.ent, self.index)] + self.others:
                cur = out.get(e.id, e)
                g = e.grips()[i]
                out[e.id] = cur.with_grip(i, (g[0] + dx, g[1] + dy))
            return out
        if k is None:
            return {self.ent.id: self.ent.with_grip(self.index, p)}
        return _run_drag(self.ctx, self.ent, k, p)

    def point(self, p):
        sheet = self.ctx.sheet()
        got = self._dragged(p)
        if not got and self._run() is not None:
            _run_drag(self.ctx, self.ent, self._run(), p, say=True)
        if got:
            from .wires import moved_ends, pull_on
            ends = moved_ends(sheet, list(got.values()))
            with self.ctx.edit("Stretch") as ed:
                for e in got.values():
                    ed.change(sheet, e)
                pull_on(ed, sheet, ends)
        self.finish()

    def preview(self, p):
        return list(self._dragged(p).values())


def put_changed(ed, sheet, got):
    """Write changed copies; a wire squeezed to nothing (fewer than two points: an end moved
    onto its other end) goes instead, as Clean up wires takes wires of no length (the long
    battery: Scoot, seed 4101; Stretch, seed 3252)."""
    for e in got:
        if isinstance(e, M.Wire) and len(e.points) < 2:
            ed.remove(sheet, e.id)
        else:
            ed.change(sheet, e)


def stretched(sheet, rect, dx, dy):
    """STRETCH (as AutoCAD's): what a crossing window rect (x0, y0, x1, y1) moved by dx, dy
    does: an object wholly inside moves; a wire's ends inside move, its next corner sliding
    along so it stays square (Wire.end_moved: a bus's three ends stretched together, the owner,
    0.18); a line's ends and a polyline's corners inside move; a symbol, text, circle... whose
    insertion point or center is inside moves (wires on a symbol's pins follow it). Returns
    the changed copies."""
    x0, y0, x1, y1 = rect

    def inside(q):
        return x0 - 1e-9 <= q[0] <= x1 + 1e-9 and y0 - 1e-9 <= q[1] <= y1 + 1e-9

    out = []
    for e in sheet.query(rect):
        bb = e.bbox()
        if inside(bb[:2]) and inside(bb[2:]):
            out.append(e.moved(dx, dy))
            continue
        if isinstance(e, M.Wire):
            w = e
            for i in (0, -1):
                q = w.points[i]
                if inside(e.points[i]) and len(w.points) >= 2:
                    w = w.end_moved(i, (q[0] + dx, q[1] + dy))
            if w is not e:
                out.append(w)
        elif isinstance(e, M.Line):
            p1 = (e.p1[0] + dx, e.p1[1] + dy) if inside(e.p1) else e.p1
            p2 = (e.p2[0] + dx, e.p2[1] + dy) if inside(e.p2) else e.p2
            if (p1, p2) != (e.p1, e.p2):
                out.append(e.copy(p1=list(p1), p2=list(p2)))
        elif isinstance(e, M.Polyline):
            pts = [[q[0] + dx, q[1] + dy] if inside(q) else list(q) for q in e.points]
            if pts != [list(q) for q in e.points]:
                out.append(e.copy(points=pts))
        else:
            anchor = getattr(e, "pos", None) or getattr(e, "center", None)
            if anchor is not None and inside(anchor):
                out.append(e.moved(dx, dy))
    return out


class StretchCmd(Command):
    """STRETCH (S): a crossing window over the ends to move (two corners), then the base point
    and where it goes: what stretched() says, in one step (the owner, 0.18: "Is there a way to
    stretch a bus of wires at the same time, so I don't have to do all three individually?")."""
    name, title = "STRETCH", "Stretch"

    def begin(self):
        self.corner = self.rect = self.base = None
        self.ctx.set_selection(set())
        self.ctx.prompt("Stretch: first corner of the crossing window (around the ends to "
                        "move)")

    def point(self, p):
        if self.corner is None:
            self.corner = p
            self.ctx.prompt("Other corner")
        elif self.rect is None:
            a = self.corner
            self.rect = (min(a[0], p[0]), min(a[1], p[1]), max(a[0], p[0]), max(a[1], p[1]))
            if not self.ctx.sheet().query(self.rect):
                self.ctx.message("Nothing in that window")
                self.corner = self.rect = None
                self.ctx.prompt("Stretch: first corner of the crossing window")
                return
            self.ctx.prompt("Base point")
        elif self.base is None:
            self.base = self.last = p
            self.ctx.prompt("Second point")
        else:
            sheet = self.ctx.sheet()
            got = stretched(sheet, self.rect, p[0] - self.base[0], p[1] - self.base[1])
            if got:
                from .wires import moved_ends, pull_on
                ends = moved_ends(sheet, got)
                with self.ctx.edit(self.title) as ed:
                    put_changed(ed, sheet, got)
                    pull_on(ed, sheet, ends)
            self.finish()

    def preview(self, p):
        if self.corner is not None and self.rect is None:
            a = self.corner
            return [M.Polyline([a, (p[0], a[1]), p, (a[0], p[1])], True)]
        if self.base is not None:
            return stretched(self.ctx.sheet(), self.rect, p[0] - self.base[0],
                             p[1] - self.base[1])
        return []


class PasteCmd(Command):
    name, title = "PASTE", "Paste"
    repeatable = False

    def __init__(self, ctx, ents, base, blocks=None, layers=None):
        super().__init__(ctx)
        self.ents, self.base_pt = ents, base
        self.blocks = blocks or {}
        self.layers = layers or {}          # {name: Layer dict} copied with them

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
            project = self.ctx.project
            # (their layers the project doesn't have, as they were where they were copied:
            # color, line type, wire size...; a layer it has keeps its own, the owner, 0.18.4)
            used = {e.layer for e in self.ents}
            for e in self.ents:
                if isinstance(e, M.Insert) and e.block in self.blocks:
                    used.update(x.layer for x in self.blocks[e.block].entities)
            for name in sorted(used):
                if name and name not in project.layers:
                    d = self.layers.get(name)
                    ed.layer(name, None, M.Layer.from_dict(d).to_dict() if d is not None
                             else M.Layer(name).to_dict())
            names = {}
            for e in self.ents:
                if isinstance(e, M.Insert) and e.block in self.blocks:
                    # (a footprint pasted where a symbol has its name: kept apart, 0.18)
                    d = self.blocks[e.block]
                    pname = M.project_block_name(project, e.block, d.kind)
                    names[e.block] = pname
                    if pname not in project.blocks:
                        ed.block(M.renamed_block(d, pname))
            from .tags import retag_copies
            placed = []
            for e in self.result(p):
                if isinstance(e, M.Insert):
                    e.block = names.get(e.block, e.block)
                    e.defn = project.blocks.get(e.block, e.defn)
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


def wire_layer(ctx):
    """The layer a wire goes on: the current layer when it is a wire layer (WIRES, one named
    WIRE..., or one with a gauge or wire color: Layers), else WIRES (the owner, 0.16: picking
    WIRE BROWN and drawing a wire put it on WIRES; picking 0 for drafting leaves wires on
    WIRES; a layer of the wire layer preset, Layers > Wire layers, ETHERNET too)."""
    from . import wirelayers
    name = ctx.layer()
    lay = ctx.project.layers.get(name)
    if name.upper().startswith("WIRE") or (lay is not None and (lay.awg or lay.wire_color)) \
            or (lay is not None and wirelayers.is_preset(name)):
        return name
    return "WIRES"


BACK_OVER = ("That goes straight back over the wire just drawn: click on past it or off to "
             "the side, U takes the last point back, Enter ends the wire here")


class WireCmd(Command):
    """WIRE: click where it starts (a pin, a wire, or anywhere), then where it goes: it runs
    straight across and up or down, turning one corner per click (F flips which way the
    corner goes). It ends by itself on a pin or another wire; Enter ends it anywhere."""
    name, title = "WIRE", "Wire"
    wire_snaps = True       # (pins and wire ends always pull the point: CadView.snap_modes)

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
        leads = bool(self.ctx.project.settings.get("wire_lead", False))
        if len(self.points) == 1 and leads:
            got = lead(sheet, a, p)
            if got is not None:
                a, out = got
                start = [a]
                if self.hfirst is None:
                    # (carry on the way the lead heads, unless the cursor is well off it)
                    h = abs(out[0]) > 0
                    return start + route(a, p, h)
        end = lead(sheet, p, a) if leads else None
        if end is not None and G.dist(a, p) > 1e-9:
            c, out = end
            h = self.hfirst
            if h is None:
                h = not (abs(out[0]) > 0)  # (arrive along the way out of the pin)
            return start + route(a, c, h) + [p]
        h = self.hfirst
        if h is None:
            h = abs(p[0] - a[0]) >= abs(p[1] - a[1])
        plain = route(a, p, h)
        if not start and self.ctx.project.settings.get("wire_around", True):
            # (round the symbols in the way: the owner, 0.16, a wire run through a drive)
            from .wires import route_around
            return route_around(sheet, a, p, plain, wire_clear(self.ctx))
        return start + plain

    def point(self, p):
        if self.tapped is not None:
            self.ctx.message(self._tap_choices())
            return
        from .wires import connects_at
        if not self.points:
            self.points = [p]
            self.base = self.last = p
            self.ctx.prompt("Specify next point (ends by itself on a pin or wire; Enter "
                            "ends here)", [("Flip corner", "F"), ("Undo", "U")])
            return
        if G.dist(self.points[-1], p) < 1e-9:
            return
        new = self._route(p)
        if doubles_back(self.points[-2:] + list(new)):
            self.ctx.message(BACK_OVER)
            return
        self.points += new
        self.base = self.last = p
        if connects_at(self.ctx.sheet(), p):
            self._make()

    def text(self, s):
        k = s.strip().upper()
        if self.tapped is not None:
            if k in ("N", "S"):
                from . import wirenums
                sheet = self.ctx.sheet()
                w = sheet.entities.get(self.tapped)
                mode = wirenums.tap_mode(self.ctx.project)
                if w is not None and k == "N" and mode != "own":
                    with self.ctx.edit("Wire number of its own") as ed:
                        ed.change(sheet, w.copy(own_num=True))
                    self.ctx.message("The tap takes a number of its own")
                elif w is not None and k == "S" and mode != "same":
                    # (the wire's number whatever the project's tap numbers: a ladder branch)
                    with self.ctx.edit("Same wire number") as ed:
                        ed.change(sheet, w.copy(same_num=True))
                    self.ctx.message("The tap keeps the number of the wire it taps")
                self.finish()
                return True
            return False
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

    tapped = None           # (the wire just drawn, when it taps off another: asking)

    def _make(self):
        pts = M._tidy(self.points)
        if len(pts) >= 2:
            sheet = self.ctx.sheet()
            with self.ctx.edit("Wire") as ed:
                w = ed.add(sheet, M.Wire(pts, layer=wire_layer(self.ctx)))
                if _cleanup_on(self.ctx):
                    from .wires import tidy_new
                    if tidy_new(ed, sheet, w) == "duplicate":
                        self.ctx.message("That wire is already there: not drawn twice")
            _flag_misses(self.ctx, [pts[0], pts[-1]])
            if self._ask_tap(sheet, pts):
                return
        self.finish()

    def _ask_tap(self, sheet, pts):
        """Drawn off the middle of another wire (a tap) with wire numbers on: ask whether it
        keeps that wire's number (Enter) or takes a new one (N) (the owner, 0.17.2: "when I tap
        off a wire, I can either change the wire number or leave as is"). True when asking."""
        from . import wirenums
        if not wirenums.enabled(self.ctx.project):
            return False
        ends = [tuple(pts[0]), tuple(pts[-1])]
        for e in sheet.wires():
            if any(G.dist(q, r) <= 1e-9 for q in (e.points[0], e.points[-1]) for r in ends):
                other = wirenums.taps(sheet, e)
                if other is not None:
                    self.tapped = e.id
                    self.points = []
                    self.ctx.prompt("Tapped off wire %s: %s" % (other.num or "?",
                                                              self._tap_choices()),
                                    [("Same number", "S"), ("New number", "N")])
                    return True
        return False

    def _tap_choices(self):
        """What Enter, S and N do at a tap: Enter, the project's tap numbers (0.18.3)."""
        from . import wirenums
        mode = wirenums.tap_mode(self.ctx.project)
        if mode == "suffix":
            return "Enter gives it the wire's number with -1, -2..., S the same number, N a new one"
        if mode == "own":
            return "Enter gives it a new number, S the wire's number"
        return "Enter keeps its number, or N for a new number"

    def enter(self):
        if self.tapped is not None:
            self.finish()
            return
        self._make()

    def cancel(self):
        # Esc, or starting another command, keeps what is drawn so far (as AutoCAD's PLINE)
        if self.tapped is not None:
            self.finish()
            return
        self._make()

    def preview(self, p):
        if not self.points:
            return []
        return [M.Wire(self.points + self._route(p), layer=wire_layer(self.ctx))]


def _strands_a_pin(sheet, got):
    """Would wires changed to got ({id: points}) leave a pin that one of them was on with no
    wire? (A wire tapping the dragged run, a pin on its middle, followed the run past its other
    end and left that pin behind: the battery, seed 6006.)"""
    old = [sheet.entities[i] for i in got if i in sheet.entities]
    if not old:
        return False
    new = {i: M.Wire(pts) for i, pts in got.items()}
    bb = None
    for e in old:
        bb = G.bbox_union(bb, e.bbox())
    for e in sheet.query(bb):
        if not isinstance(e, M.Insert):
            continue
        for _n, q in e.pin_points():
            if not any(x.touches(q) for x in old):
                continue
            near = [x for x in sheet.query((q[0] - 1e-6, q[1] - 1e-6, q[0] + 1e-6, q[1] + 1e-6))
                    if isinstance(x, M.Wire) and x.id not in got]
            if not any(x.touches(q) for x in list(new.values()) + near):
                return True
    return False


def _run_drag(ctx, w, k, p, say=False):
    """{id: new wire} for wire w's run k dragged to p (wires.segment_drag); {} when it can't
    move, saying why when say."""
    from .wires import doubles_back, segment_drag
    sheet = ctx.sheet()
    got = segment_drag(sheet, w, k, p)
    if got is not None and any(doubles_back(pts) for pts in got.values()):
        # (onto the wire's own run beside it, the other way: the wire would run back over
        # itself, a corner hidden in what looks like one straight wire; the sweep, 0.18.2,
        # seed 704)
        if say:
            ctx.message("Moved there, the wire would run back over itself: drag the run less "
                        "far, or delete the jog and draw it again")
        return {}
    if got is not None and _strands_a_pin(sheet, got):
        got = None
    if got is None:
        if say:
            ctx.message("Moved there, the wire would leave a symbol's pin or a wire joined to "
                        "it (a pin on that run, or on the part of the run beside it that would "
                        "get shorter): move the symbol first, or drag the run less far")
        return {}
    return {i: sheet.entities[i].copy(points=[list(q) for q in pts])
            for i, pts in got.items() if i in sheet.entities}


def wire_clear(ctx):
    """How far wires keep from symbols going round them (paper inches; Schematic settings)."""
    from .wires import CLEAR
    try:
        v = float(ctx.project.settings.get("wire_clear", CLEAR))
    except (TypeError, ValueError):
        v = CLEAR
    return v if v > 0 else CLEAR


def _flag_misses(ctx, points):
    """Mark the wire ends just drawn that stop short of a pin or wire (CadView)."""
    flag = getattr(ctx, "flag_near_misses", None)
    if flag is not None:
        flag(points)


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
        # (a leg no longer than the wire's offset leaves it a point twice: a leg of nothing)
        line = [tuple(q) for q in M._tidy(line)]
        if len(line) >= 2:
            out.append(line)
    return out


def _same_way(a, b, c):
    """Do a-b and a-c leave a the same way (across or up and down, and the same direction)?"""
    u = (b[0] - a[0], b[1] - a[1])
    w = (c[0] - a[0], c[1] - a[1])
    return u[0] * w[0] + u[1] * w[1] > 0 and abs(u[0] * w[1] - u[1] * w[0]) <= 1e-9 * max(
        1.0, abs(u[0]) + abs(u[1])) * max(1.0, abs(w[0]) + abs(w[1]))


def _apart(paths):
    """Do a bus's wires (their points) keep apart: none turns straight back along itself, and
    no two touch or cross? (A bus carried on from its open ends round a symbol had a wire's
    way round run onto another's end: joined there with a dot, the battery, seed 77.)"""
    from .wires import doubles_back
    from .trim import intersect
    if any(doubles_back(q) for q in paths):
        return False
    segs = [[("seg", a, b) for a, b in zip(q, q[1:])] for q in paths]
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            for sa in segs[i]:
                for sb in segs[j]:
                    if intersect(sa, sb):
                        return False
    return True


def _paths_cross(paths):
    """Does any piece of one of these wires cross or overlap a piece of another, other than
    meeting it end to end?"""
    segs = [(i, a, b) for i, q in enumerate(paths) for a, b in zip(q, q[1:])]
    for x in range(len(segs)):
        i, a, b = segs[x]
        for y in range(x + 1, len(segs)):
            j, c, d = segs[y]
            if i == j:
                continue
            for q in G.segment_intersections(a, b, c, d):
                if not any(G.dist(q, e) <= 1e-9 for e in (a, b, c, d)):
                    return True
            # (along each other: the same line, overlapping)
            if G.dist_to_segment(c, a, b) <= 1e-9 and G.dist_to_segment(d, a, b) <= 1e-9 or \
                    G.dist_to_segment(a, c, d) <= 1e-9 and G.dist_to_segment(b, c, d) <= 1e-9:
                return True
    return False


def pin_side(sheet, p, tol=1e-6):
    """The pins of a symbol on one side of it, in a line through the pin at p and evenly
    spaced (a 3-pole device's L1, L2, L3; a VFD's T1-T3): ([world points] in the block's pin
    order, spacing), or None. A line whose pins have the symbol's drawing on both sides of it
    (a contact's 1 and 2: its in and out) is not a side."""
    for e in sheet.query_point(p, tol):
        if not isinstance(e, M.Insert) or e.defn is None or len(e.defn.pins) < 2:
            continue
        d = e.defn
        pins = [(q["name"], q["pos"]) for q in d.pins]
        hit = [n for n, q in pins if G.dist(e.to_world(q), p) <= tol]
        if not hit:
            continue
        at = dict(pins)[hit[0]]
        boxes = [x.bbox() for x in d.entities]
        best = None
        for axis in (0, 1):             # the same x (a column of pins), the same y (a row)
            line = [(n, q) for n, q in pins if abs(q[axis] - at[axis]) <= 1e-6]
            if len(line) < 2:
                continue
            # (the evenly spaced run the pin is in, the longest when it is in two: a drive's
            # L1-L3 with its ground PE1 farther on are a side of three, 0.17.4)
            line.sort(key=lambda t: t[1][1 - axis])
            runs, cur = [], [line[0]]
            for prev, nxt in zip(line, line[1:]):
                gap = nxt[1][1 - axis] - prev[1][1 - axis]
                if len(cur) >= 2 and abs(gap - (cur[1][1][1 - axis] - cur[0][1][1 - axis])) > \
                        1e-6:
                    runs.append(cur)
                    cur = [prev]
                cur.append(nxt)
            runs.append(cur)
            mine = [r for r in runs if any(n == hit[0] for n, _q in r) and len(r) >= 2]
            if not mine:
                continue
            line = max(mine, key=len)
            line.sort(key=lambda t: [n for n, _q in pins].index(t[0]))  # (the block's order)
            along = sorted(q[1 - axis] for _n, q in line)
            gaps = [b - a for a, b in zip(along, along[1:])]
            if min(gaps) <= 1e-9 or max(gaps) - min(gaps) > 1e-6:
                continue
            c = at[axis]
            lo = min((bb[axis] for bb in boxes), default=c)
            hi = max((bb[axis + 2] for bb in boxes), default=c)
            if lo < c - 1e-6 and hi > c + 1e-6:
                continue                # (the drawing on both sides: in and out, not a side)
            world = [e.to_world(q) for _n, q in line]
            # (on the drawing too, straight across or up and down: a symbol turned at a slant
            # has no side a bus can leave square from, the battery, seed 3101: its wires were
            # laid square from the first pin, the others on no pin)
            if not any(all(abs(q[k] - world[0][k]) <= 1e-6 for q in world) for k in (0, 1)):
                continue
            if best is None or len(line) > len(best[0]):
                best = (world, gaps[0] * e.scale)
        if best is not None:
            return best
    return None


def end_side(sheet, p, tol=1e-6):
    """A bus's open end: the free ends of wires in a line through the free end at p, evenly
    spaced, the wires running out of them the same way: ([points] top to bottom or left to
    right, spacing, [their wires]), or None (the owner, 0.16: "I need to be able to extend a
    bus of wires")."""
    def free_end(q):
        got = []
        for e in sheet.query_point(q, tol):
            if isinstance(e, M.Wire):
                for i in (0, -1):
                    if G.dist(e.points[i], q) <= tol:
                        got.append((e, i))
                    elif i == 0 and e.touches(q, tol) and G.dist(e.points[-1], q) > tol:
                        got.append((e, None))           # (a wire through it: not free)
        if len(got) != 1 or got[0][1] is None:
            return None
        from .wires import pins_on
        if pins_on(sheet, q):
            return None
        w, i = got[0]
        a, b = (w.points[1], w.points[0]) if i == 0 else (w.points[-2], w.points[-1])
        L = G.dist(a, b)
        return (w, ((b[0] - a[0]) / L, (b[1] - a[1]) / L)) if L > 1e-9 else None
    me = free_end(p)
    if me is None:
        return None
    w0, out = me
    if abs(out[0]) > 1e-9 and abs(out[1]) > 1e-9:
        return None                     # (a slanted end)
    axis = 0 if abs(out[0]) > 0.5 else 1          # (ends one above another: the same x)
    reach = 12.0 * sheet.k()
    rect = (p[0] - tol, p[1] - reach, p[0] + tol, p[1] + reach) if axis == 0 else \
        (p[0] - reach, p[1] - tol, p[0] + reach, p[1] + tol)
    found = {}
    for e in sheet.query(rect):
        if not isinstance(e, M.Wire):
            continue
        for q in (e.points[0], e.points[-1]):
            if abs(q[axis] - p[axis]) > tol:
                continue
            got = free_end(q)
            if got is not None and got[0].id == e.id and \
                    abs(got[1][0] - out[0]) < 1e-9 and abs(got[1][1] - out[1]) < 1e-9:
                found[round(q[1 - axis], 9)] = (tuple(q), e)
    run = _even_run(sorted(found), round(p[1 - axis], 9))
    if run is None:
        return None
    coords, gap = run
    if axis == 0:
        coords = coords[::-1]                       # (top to bottom)
    return [found[c][0] for c in coords], gap, [found[c][1] for c in coords]


def _even_run(coords, c0):
    """The evenly spaced run of sorted coords containing c0 (its nearest neighbours' gap):
    ([coords], gap), or None when fewer than two."""
    if c0 not in coords or len(coords) < 2:
        return None
    i = coords.index(c0)
    gaps = [abs(coords[j] - c0) for j in (i - 1, i + 1) if 0 <= j < len(coords)]
    gap = min(gaps)
    if gap <= 1e-9:
        return None
    lo = hi = i
    while lo > 0 and abs((coords[lo] - coords[lo - 1]) - gap) < 1e-6:
        lo -= 1
    while hi < len(coords) - 1 and abs((coords[hi + 1] - coords[hi]) - gap) < 1e-6:
        hi += 1
    run = coords[lo:hi + 1]
    return (run, gap) if len(run) >= 2 else None


def tap_lines(sheet, p, tol=1e-6):
    """Wires running side by side through a point on the middle of one (three phases across
    a sheet): straight runs parallel to the one at p, evenly spaced, all going past p's place
    along them: (across, [their y, or x when they run up and down], spacing), or None. A bus
    started or ended there takes or lands on one each (the owner, 0.16: "add a vertical 3ph
    wire bus to horizontal 3 ph wires")."""
    seg = None
    for e in sheet.query_point(p, tol):
        if not isinstance(e, M.Wire):
            continue
        if G.dist(e.points[0], p) <= tol or G.dist(e.points[-1], p) <= tol:
            return None                 # (an end: that's carrying a wire on)
        for a, b in zip(e.points, e.points[1:]):
            if G.dist_to_segment(p, a, b) <= tol and G.dist(p, a) > tol and \
                    G.dist(p, b) > tol:
                if abs(a[1] - b[1]) < 1e-9:
                    seg = (True, a[1])
                elif abs(a[0] - b[0]) < 1e-9:
                    seg = (False, a[0])
    if seg is None:
        return None
    across = seg[0]
    reach = 12.0 * sheet.k()
    rect = (p[0] - tol, p[1] - reach, p[0] + tol, p[1] + reach) if across else \
        (p[0] - reach, p[1] - tol, p[0] + reach, p[1] + tol)
    found = set()
    for e in sheet.query(rect):
        if not isinstance(e, M.Wire):
            continue
        for a, b in zip(e.points, e.points[1:]):
            if across and abs(a[1] - b[1]) < 1e-9 and min(a[0], b[0]) < p[0] - tol and \
                    max(a[0], b[0]) > p[0] + tol:
                found.add(round(a[1], 9))
            elif not across and abs(a[0] - b[0]) < 1e-9 and min(a[1], b[1]) < p[1] - tol \
                    and max(a[1], b[1]) > p[1] + tol:
                found.add(round(a[0], 9))
    run = _even_run(sorted(found), round(seg[1], 9))
    if run is None:
        return None
    return across, run[0], run[1]


# the Bus command's layer choices (the wires in order; past the list's end, its last layer)
BUS_LAYERS = [
    ("Wires (the WIRES layer)", ["WIRES"]),
    ("Brown, orange, yellow (480 V)", ["WIRE BROWN", "WIRE ORANGE", "WIRE YELLOW", "WIRE GRAY"]),
    ("Black, red, blue (208/240 V)", ["WIRE BLACK", "WIRE RED", "WIRE BLUE", "WIRE WHITE"]),
    ("All black", ["WIRE BLACK"]),
]
# their colors, for layers the project hasn't got yet ("7": black on paper, white on screen)
WIRE_LAYER_COLORS = {"WIRE BROWN": "#a0522d", "WIRE ORANGE": "#ff8c00", "WIRE YELLOW": "#ffd700",
                     "WIRE GRAY": "#909090", "WIRE BLACK": "7", "WIRE RED": "#ff3030",
                     "WIRE BLUE": "#3070ff", "WIRE WHITE": "#e0e0e0"}


# the insulation color each of them stands for (the wire color the layer's wires show)
WIRE_COLOR_NAMES = {"WIRE BROWN": "BRN", "WIRE ORANGE": "ORG", "WIRE YELLOW": "YEL",
                    "WIRE GRAY": "GRY", "WIRE BLACK": "BLK", "WIRE RED": "RED",
                    "WIRE BLUE": "BLU", "WIRE WHITE": "WHT"}


def bus_layer_list(layers, count):
    """A layer for each of count wires from a choice (its last one again past its end)."""
    layers = list(layers) or ["WIRES"]
    return [layers[min(i, len(layers) - 1)] for i in range(count)]


class BusCmd(Command):
    """BUS: several wires side by side (three phases, say). Start it on a symbol's pin and it
    takes that side's pins (a disconnect's L1, L2, L3: how many and how far apart, the others
    landing on their pins whichever way it goes); anywhere else, the last count and spacing (N,
    D to change them). Then click the path as for a wire: across and up or down, turning 90
    degrees at each click, all the wires turning together; S runs it straight instead (each
    click straight across or straight up or down from the last, no corner). L picks each
    wire's layer (brown, orange, yellow...). F puts the other wires on the other side; Enter
    (or Esc) ends it."""
    name, title = "BUS", "Bus"
    wire_snaps = True       # (pins and wire ends always pull the point: CadView.snap_modes)

    def begin(self):
        self.count = int(getattr(self.ctx, "_bus_count", 3))
        self.spacing = float(getattr(self.ctx, "_bus_spacing", 0.5))
        self.layers = list(getattr(self.ctx, "_bus_layers", ["WIRES"]))
        self.straight = bool(getattr(self.ctx, "_bus_straight", False))
        self.flip = False
        self.toward = None              # started on a symbol's pins: where its others are
        self.side_pins = []             # ...and those pins, each wire starting exactly on one
        self.tap_start = None           # started on wires side by side: (across, [lines])
        self.tap_end = None             # ...ended on them
        self.offset = (0.0, 0.0)        # started on a pin or end not the first: from it to
                                        # the first (later clicks are where the one clicked goes)
        self.points = []
        self.hfirst = None
        self._ask_start()

    def _options(self):
        opts = [("Straight" if not self.straight else "Corners", "S"), ("Layers", "L"),
                ("Other side", "F")]
        if self.points:
            return opts + [("Undo", "U")]
        return [("Wires", "N"), ("Spacing", "D")] + opts

    def _ask_start(self):
        self.step = "path"
        self.ctx._bus_count, self.ctx._bus_spacing = self.count, self.spacing
        if self.points:
            self.ctx.prompt("Specify next %s (Enter ends the bus)" % (
                "point" if self.straight else "corner"), self._options())
        else:
            self.ctx.prompt("Specify start of the bus: a symbol's pin takes its poles (else %d "
                            "wires, %s apart)" % (self.count, _fmt(self.spacing)),
                            self._options())

    def number(self, v):
        if self.step in ("count", "path") and not self.points and \
                (self.step == "count" or v == int(v)):
            if v < 2 or v != int(v) or v > 50:
                self.ctx.message("A bus has 2 to 50 wires.")
                return True
            self.count = int(v)
            self._ask_spacing()          # (typed: how far apart next, as it always asked)
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

    def enter(self):
        if self.step in ("count", "spacing"):
            self._ask_start()
        else:
            self._make()

    def cancel(self):
        self._make()

    def _route(self, p):
        """The points the next click at p adds (none repeating the one before)."""
        out, last = [], self.points[-1]
        for q in self._route_raw(p):
            if G.dist(q, last) > 1e-9:
                out.append(q)
                last = q
        return out

    def _route_raw(self, p):
        a = self.points[-1]
        if self.tap_start is not None and len(self.points) == 1:
            # (off wires side by side: square off them, each wire from its own)
            across = not self.tap_start[0]
            if abs(p[0] - a[0] if across else p[1] - a[1]) < 1e-9:
                return []
            if self.straight:
                return [(p[0], a[1])] if across else [(a[0], p[1])]
            from .wires import route
            return route(a, p, across)
        if self.toward is not None and len(self.points) == 1:
            # (off a symbol's pins: the first leg leaves them square, each wire from its pin;
            # a click in line with the pins can't be reached so: nothing)
            across = abs(self.toward[1]) >= abs(self.toward[0])     # (pins one above another)
            if abs(p[0] - a[0] if across else p[1] - a[1]) < 1e-9:
                return []
            if self.straight:
                return [(p[0], a[1])] if across else [(a[0], p[1])]
            from .wires import route
            return route(a, p, across)
        if self.straight:
            # straight across or straight up or down from the last point: no corner
            return [(p[0], a[1])] if abs(p[0] - a[0]) >= abs(p[1] - a[1]) else [(a[0], p[1])]
        h = self.hfirst
        if h is None:
            h = abs(p[0] - a[0]) >= abs(p[1] - a[1])
        from .wires import route
        return route(a, p, h)

    def _flip_for(self, pts):
        """Which side the other wires go: started on a symbol's pins, the side its other pins
        are on, whichever way the bus heads off; started off wires side by side, at its first
        corner the side it came from the far ones on, so no wire turns back across another
        (F turns it the other way)."""
        if self.tap_start is not None and len(pts) >= 3:
            def unit(a, b):
                L = G.dist(a, b)
                return ((b[0] - a[0]) / L, (b[1] - a[1]) / L) if L > 1e-9 else (0.0, 0.0)
            t1, t2 = unit(pts[0], pts[1]), unit(pts[1], pts[2])
            right = t2[1] * t1[0] - t2[0] * t1[1]
            if abs(right) > 1e-9:
                return (right < 0) != self.flip
            return self.flip
        if self.toward is not None and len(pts) >= 2:
            a, b = pts[0], pts[1]
            L = G.dist(a, b)
            if L > 1e-9:
                ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
                right = uy * self.toward[0] - ux * self.toward[1]
                if abs(right) > 1e-9:
                    return (right < 0) != self.flip
        return self.flip

    def point(self, p):
        if self.step != "path":
            return
        if not self.points:
            sheet = self.ctx.sheet()
            got = pin_side(sheet, p)
            what = "the symbol's pins"
            if got is None:
                ends = end_side(sheet, p)
                if ends is not None:
                    # (a bus's open end: carried on, each wire on its own layer)
                    got = ends[:2]
                    self.layers = [w.layer for w in ends[2]]
                    what = "the bus's ends"
            if got is not None:
                line, gap = got
                self.count, self.spacing = len(line), gap
                a, z = line[0], line[-1]
                L = G.dist(a, z)
                self.toward = ((z[0] - a[0]) / L, (z[1] - a[1]) / L)
                self.side_pins = list(line)
                self.offset = (a[0] - p[0], a[1] - p[1])
                p = a                   # (the first wire from the first of its pins)
                self.ctx.message("%d wires, %s apart, from %s" % (
                    self.count, _fmt(self.spacing), what))
            else:
                tap = tap_lines(sheet, p)
                if tap is not None:
                    self.tap_start = (tap[0], tap[1])
                    self.count, self.spacing = len(tap[1]), tap[2]
                    self.ctx.message("%d wires, %s apart, one off each wire" % (
                        self.count, _fmt(self.spacing)))
            self.points = [p]
            self.base = self.last = p
            self._ask_start()
            return
        sheet = self.ctx.sheet()
        land = self._landing(sheet, p)
        clicked = p
        if land is None:
            # (on or near a device: its nearest pins, wire for wire, jogging in when they are
            # spaced otherwise; the owner, 0.17.1)
            fan = self._fan(sheet, p)
            if fan is not None:
                self._make(fan)
                return
        why = self._why_not_landed(sheet, p)
        if why:
            self.ctx.message(why)
        tap = tap_lines(sheet, p) if land is None and (self.tap_start is None or
                                                       len(self.points) > 1) else None
        p = land if land is not None else (p[0] + self.offset[0], p[1] + self.offset[1])
        if G.dist(self.points[-1], p) < 1e-9:
            return
        if tap is not None:
            # (ended on wires side by side: the last leg square onto them, each wire landing
            # on its own, and the bus is done)
            a = self.points[-1]
            if len(self.points) == 1 and (self.toward is not None or
                                          self.tap_start is not None):
                new = self._route(p)            # (still leaving its pins or wires square)
            elif self.straight:
                new = [(a[0], p[1])] if tap[0] else [(p[0], a[1])]
            else:
                from .wires import route
                new = route(a, p, tap[0])
            new = [q for q in new if G.dist(q, a) > 1e-9]
            last = ([a] + new)[-2:] if new else None
            if last is not None and abs(last[0][0 if tap[0] else 1] -
                                        last[1][0 if tap[0] else 1]) > 1e-9:
                new = []                        # (it can't land square on them: a plain click)
            if new and doubles_back(self.points[-2:] + new):
                self.ctx.message(BACK_OVER)
                return
            if new:
                self.points += new
                self.tap_end = (tap[0], tap[1])
                self._make()
                return
        new = self._route(p)
        if land is not None:
            # (onto a symbol's pins as many and as far apart: wire for wire, then done; the side
            # the clicked pin is on, not the first pin's: two symbols overlapping share a pin,
            # and the first pin's side was the other symbol's, the bus landing one pin over:
            # the quick battery, seed 12)
            # (routed for the pin clicked, as _landing did: from the side's first pin, shared
            # with the overlapping symbol, the route was taken as coming at that one through
            # it and dropped, and the bus went on without landing; the sweep, 0.18.2, seed
            # 708)
            got = pin_side(sheet, clicked)
            new = self._land_route(sheet, clicked, got[0]) if got is not None else None
            if new and not doubles_back(self.points[-2:] + list(new)):
                self.points += new
                self._make()
                return
            new = self._route(p)
        new = self._around(new)
        if new and doubles_back(self.points[-2:] + list(new)):
            self.ctx.message(BACK_OVER)
            return
        if not new:
            if self.toward is not None and len(self.points) == 1:
                self.ctx.message("Click off the line of the symbol's pins: the bus leaves them "
                                 "square")
            return
        self.points += new
        self.base = self.last = self.points[-1]

    def text(self, s):
        k = s.strip().upper()
        if self.step != "path":
            return False
        if k == "F":
            self.flip = not self.flip
            return True
        if k == "S":
            self.straight = self.ctx._bus_straight = not self.straight
            self._ask_start()
            return True
        if k == "L":
            ask = getattr(self.ctx.host, "ask_bus_layers", None)
            got = ask(self.count, self.layers) if ask is not None else None
            if got:
                self.layers = self.ctx._bus_layers = list(got)
            self._ask_start()
            return True
        if k == "N" and not self.points:
            self.step = "count"
            self.ctx.prompt("Number of wires <%d>" % self.count)
            return True
        if k == "D" and not self.points:
            self._ask_spacing()
            return True
        if k == "U" and len(self.points) > 1:
            self.points.pop()
            self.base = self.last = self.points[-1]
            return True
        return False

    def _on_pins(self, paths):
        """Started on a symbol's pins: each wire starts exactly on its pin (its first leg kept
        straight), not where the spacing puts it, a hair off on a turned symbol."""
        if not self.side_pins:
            return paths
        out = []
        for pts in paths:
            pin = min(self.side_pins, key=lambda q: G.dist(q, pts[0]))
            if G.dist(pin, pts[0]) <= 1e-6 and len(pts) >= 2:
                a, b = pts[0], pts[1]
                b = (b[0], pin[1]) if abs(a[1] - b[1]) < 1e-6 else (pin[0], b[1])
                pts = [pin, b] + list(pts[2:])
            out.append(pts)
        return out

    def _landing(self, sheet, p):
        """A click on a pin of a symbol's side with as many pins as the bus has wires, as far
        apart: where the first wire goes (onto the side's first pin: T1 lands on L1, whichever
        of its pins was clicked), or None."""
        got = pin_side(sheet, p)
        if got is None or len(got[0]) != self.count or abs(got[1] - self.spacing) > 1e-6:
            return None
        if self._land_route(sheet, p, got[0]) is None:
            return None
        return got[0][0]

    def _around(self, new):
        """The points a click adds, going round the symbols in the bus's way (the owner,
        0.16: "Bus needs to go around objects as well"): its first wire routed with room for
        the others beside it (wires.route_around, the clearance plus the bus's width), kept
        only when then none of its wires runs through a symbol; new as it is otherwise."""
        if not new or not self.points or \
                not self.ctx.project.settings.get("wire_around", True) or \
                (len(self.points) == 1 and self.tap_start is not None):
            return new
        from .wires import route_around, _boxes, _crosses
        sheet = self.ctx.sheet()
        paths = self._paths(self.points + new)
        if not paths:
            return new
        bb = None
        for q in paths:
            bb = G.bbox_union(bb, G.bbox_of(q))
        k = sheet.k()
        width = max(0, self.count - 1) * self.spacing
        pad = 3.0 * k + width
        boxes = _boxes(sheet, (bb[0] - pad, bb[1] - pad, bb[2] + pad, bb[3] + pad), k)
        # (only the leg being added counts: what is drawn so far stays as it is)
        tail = [q[len(self.points) - 1:] for q in paths]
        if not boxes or not any(_crosses(q, boxes) for q in tail):
            return new
        # (tight first: the other wires may be on the outside of every turn; then the bus's
        # width kept clear on the side its other wires are on, the right of the way it goes
        # unless flipped; then all round)
        side = -1 if self._flip_for(self.points + new) else 1
        for extra, on in (((0.0, None), (width, side), (width, None)) if width > 0
                          else ((0.0, None),)):
            got = route_around(sheet, self.points[-1], new[-1], new, wire_clear(self.ctx),
                               extra, on)
            if got is new:
                continue
            if len(self.points) == 1 and getattr(self, "side_pins", None) and \
                    not _same_way(self.points[0], new[0], got[0]):
                # (a bus leaving pins or carried on from its ends leaves them square, the way
                # it was clicked: a way round turning across them ran onto its own ends,
                # the battery, seed 77)
                continue
            paths = self._paths(self.points + got)
            tail = [q[len(self.points) - 1:] for q in paths]
            if not any(_crosses(q, boxes) for q in tail) and _apart(tail):
                return got
        return new

    def _near_sides(self, sheet, p):
        """[(distance, pins, k, s)]: on a symbol the click is on or near (its drawing's box, a
        quarter inch out on paper), each run of as many pins as the bus has wires on one of its
        sides (every k-th coordinate the same; s: the side's way out, away from the drawing),
        nearest the click first (the owner, 0.17.1: "These need to connect to the nearest 3
        points on the device")."""
        from .wires import body_box
        near = 0.25 * sheet.k()
        out = []
        seen = set()
        for e in sheet.query((p[0] - near, p[1] - near, p[0] + near, p[1] + near)):
            if not isinstance(e, M.Insert) or e.defn is None or e.defn.kind != "symbol" or \
                    len(e.defn.pins) < self.count:
                continue
            bb = body_box(e)
            if bb is None or not (bb[0] - near <= p[0] <= bb[2] + near and
                                  bb[1] - near <= p[1] <= bb[3] + near):
                continue
            c = ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)
            for _n, q in e.pin_points():
                got = pin_side(sheet, q)
                if got is None:
                    continue
                line = got[0]
                key = tuple(sorted((round(x[0], 9), round(x[1], 9)) for x in line))
                if key in seen or len(line) < self.count:
                    continue
                seen.add(key)
                k = 0 if all(abs(x[0] - line[0][0]) <= 1e-6 for x in line) else 1
                s = 1.0 if line[0][k] >= c[k] else -1.0
                along = sorted(line, key=lambda x: x[1 - k])
                for i in range(len(along) - self.count + 1):
                    win = along[i:i + self.count]
                    mid = (sum(x[0] for x in win) / len(win), sum(x[1] for x in win) / len(win))
                    out.append((G.dist(p, mid), win, k, s))
        out.sort(key=lambda t: t[0])
        return out

    def _fan(self, sheet, p):
        """Every wire's points (the whole bus) landing on the run of pins nearest the click p
        on a side facing the bus, each wire on its own pin, wires and pins in the same order
        across: the bus comes square at the side, and where the pins are closer together or
        farther apart than its wires, each wire jogs over to its pin, nearer the pins the
        farther along they go (so none crosses another); or None. When the plain landing
        (_landing: a side of exactly the bus's pins, as far apart) can't."""
        if not self.points or self.count < 1:
            return None
        a = self.points[-1]
        g = 0.125 * sheet.k()
        n = self.count
        for _d, win, k, s in self._near_sides(sheet, p)[:12]:
            m = 1 - k
            side = win[0][k]
            h0 = 2 * g
            far = h0 + (n + 1) * g
            if (a[k] - side) * s < far - 1e-9:
                continue                # (the bus must come at the side from out in front)
            pins = sorted(win, key=lambda q: q[m])
            # the bus's first wire comes in at S; where its others come in, across, is
            # measured (they lie to one side or the other however it turned), and S moved so
            # the bus is centered on the pins: the fewest jogs
            # (started from in line with where the bus is, or with the pins' middle: whichever
            # has a way there; then centered from how its wires lie, and each way there tried)
            for start in (a[m], sum(q[m] for q in pins) / n):
                stage = [None, None]
                stage[k], stage[m] = side + s * far, start
                for _try in range(3):
                    S = tuple(stage)
                    paths = next(self._fan_mains(S, k, m), None)
                    if paths is None:
                        break
                    offs = [q[-1][m] - S[m] for q in paths]
                    want = sum(q[m] for q in pins) / n - sum(offs) / n
                    want = round(want / g) * g if g > 0 else want
                    if abs(want - stage[m]) <= 1e-9:
                        break
                    stage[m] = want
                got = self._fan_onto(sheet, tuple(stage), pins, k, s, h0)
                if got is not None:
                    return got
        return None

    def _fan_onto(self, sheet, S, pins, k, s, h0):
        """The first way to S that, with each wire's jog onto its pin, crosses neither another
        wire of the bus nor a symbol: every wire's points, or None."""
        from .wires import _boxes, _crosses
        m = 1 - k
        n = self.count
        g = 0.125 * sheet.k()
        side = pins[0][k]
        for paths in self._fan_mains(S, k, m):
            if any(abs(q[-1][k] - S[k]) > 1e-6 for q in paths):
                continue
            order = sorted(range(n), key=lambda i: paths[i][-1][m])
            right_movers = [i for i in order if pins[order.index(i)][m] > paths[i][-1][m] + 1e-9]
            left_movers = [i for i in reversed(order)
                           if pins[order.index(i)][m] < paths[i][-1][m] - 1e-9]
            height = {}
            for rank, i in enumerate(right_movers):
                height[i] = h0 + rank * g
            for rank, i in enumerate(left_movers):
                height[i] = h0 + rank * g
            out = []
            for i in range(n):
                pin = pins[order.index(i)]
                pts = list(paths[i])
                w = pts[-1]
                if i in height:
                    v = side + s * height[i]
                    j1, j2 = [None, None], [None, None]
                    j1[m], j1[k] = w[m], v
                    j2[m], j2[k] = pin[m], v
                    pts += [tuple(j1), tuple(j2)]
                pts.append(tuple(pin))
                # (no jog that goes over and straight back along the same line: a hidden
                # corner, a dot with nothing tapped off; the battery, 0.17.5, seed 12, and a
                # 3/4" bus onto 1/2" poles)
                out.append([tuple(q) for q in M._tidy(straighten(pts))])
            if _paths_cross(out):
                continue
            bb = None
            for q in out:
                bb = G.bbox_union(bb, G.bbox_of(q))
            boxes = _boxes(sheet, (bb[0] - 1, bb[1] - 1, bb[2] + 1, bb[3] + 1), sheet.k())
            tails = [q[len(self.points) - 1:] for q in out]
            if any(_crosses(q, boxes) for q in tails):
                continue
            return out
        return None

    def _fan_mains(self, S, k, m):
        """Every wire's points from the bus's start to S, its last leg coming square at the
        side (along k), for each way there in turn: the usual route, a Z (square on, across
        halfway, square in), across first, and the way round the symbols in between; leaving
        pins or wires it started on square, as the usual route does."""
        from .wires import route_around
        a = self.points[-1]
        sheet = self.ctx.sheet()
        first = self._route(S)
        c1 = [None, None]
        c1[m], c1[k] = S[m], a[k]
        n = self.count
        g = 0.125 * sheet.k()
        mid = (a[k] + S[k]) / 2
        mid = round(mid / g) * g if g > 0 else mid
        z1, z2 = [None, None], [None, None]
        z1[k], z1[m] = mid, a[m]
        z2[k], z2[m] = mid, S[m]
        width = max(0, n - 1) * self.spacing
        tries = [first, [tuple(z1), tuple(z2), S], [tuple(c1), S]]
        for t in list(tries):
            if not t:
                continue
            side = -1 if self._flip_for(self.points + t) else 1
            for extra, on in ((0.0, None), (width, side)):
                got = route_around(sheet, a, S, t, wire_clear(self.ctx), extra, on)
                if got is not t:
                    tries.append(got)
        for new in tries:
            new = [q for i, q in enumerate(new) if G.dist(q, ([a] + new)[i]) > 1e-9]
            if not new:
                continue
            if len(self.points) == 1 and (self.toward is not None or
                                          self.tap_start is not None):
                # (still leaving its pins or wires square: the first leg as the usual one)
                if not first or (abs(new[0][1] - a[1]) < 1e-9) != \
                        (abs(first[0][1] - a[1]) < 1e-9):
                    continue
            last = ([a] + new)[-2]
            if abs(last[m] - S[m]) > 1e-9:
                continue                # (its last leg isn't square at the side)
            paths = self._paths(self.points + new)
            if len(paths) == n:
                yield paths

    def _land_route(self, sheet, p, pins):
        """The points that take the bus onto a side of pins wire for wire (each wire on its
        own pin, arriving square from outside the symbol): the usual route, else one with a
        corner more (a Z: leaving square and arriving square, the owner, 0.16: "will wires
        automatically snap to the correct location?"), or None."""
        for new, fault in self._land_tries(sheet, p, pins):
            if fault is None:
                return new
        return None

    def _land_tries(self, sheet, p, pins):
        """[(route, why it doesn't land or None)] for the routes onto a side of pins: the usual
        one, then the Zs. Every one that doesn't land says why (_why_not_landed shows the
        first: a bus that neither landed nor said why, seed 289 on CI)."""
        if not self.points:
            return []
        a, b = self.points[-1], pins[0]
        first = self._route(b)
        cands = [first]
        for across in (True, False):
            m = (a[0] + b[0]) / 2 if across else (a[1] + b[1]) / 2
            k = 0.125 * sheet.k()
            if k > 0 and abs(round(m / k) * k - m) < abs((b[0] - a[0]) if across
                                                         else (b[1] - a[1])) / 2:
                m = round(m / k) * k
            z = [(m, a[1]), (m, b[1]), b] if across else [(a[0], m), (b[0], m), b]
            z = [q for i, q in enumerate(z) if G.dist(q, ([a] + z)[i]) > 1e-9]
            cands.append(z)
        out = []
        square = "leaving its pins square, the bus can't come at that side square: click a " \
            "point on the way first"
        for new in cands:
            if not new:
                out.append((new, square))
                continue
            if len(self.points) == 1 and (self.toward is not None or
                                          self.tap_start is not None):
                # (still leaving its pins or wires square: the first leg as the usual one)
                if not first or (abs(new[0][1] - a[1]) < 1e-9) != \
                        (abs(first[0][1] - a[1]) < 1e-9):
                    out.append((new, square))
                    continue
            out.append((new, self._landing_fault(sheet, p, pins, new)))
        return out

    def _landing_fault(self, sheet, p, pins, new=None):
        """Why the bus, ended on a side of pins as many and as far apart as its wires, would
        still not land wire for wire, or None: its wires arrive in the other order (the symbol
        turned the other way: only the first would land, the others on nothing), or it comes
        at that side through the symbol (the side faces away). Found by hand on a 3-pole fuse
        block turned round (0.16.3)."""
        if not self.points:
            return None
        main = self.points + (self._route(pins[0]) if new is None else new)
        if len(main) < 2:
            return None
        paths = self._paths(main)
        ends = [q[-1] for q in paths]
        if len(ends) != len(pins) or any(G.dist(a, b) > 1e-6 for a, b in zip(ends, pins)):
            return "its poles run the other way from the bus's wires (wire 1 would land on " \
                "its first pin, the others on nothing): turn or flip it (Rotate, Mirror) or " \
                "come at it from its other end"
        # every wire runs the way the bus does on every leg: a turn closer to the pins than
        # the wires are apart sends the others backward, across each other (the battery, seed
        # 292: a bus landed with wire 2 crossing wire 3)
        for q in paths:
            if len(q) != len(main):
                return "the bus turns too close to the pins for its spacing: click a point " \
                    "farther out first"
            for j in range(len(q) - 1):
                u = (q[j + 1][0] - q[j][0], q[j + 1][1] - q[j][1])
                w = (main[j + 1][0] - main[j][0], main[j + 1][1] - main[j][1])
                if u[0] * w[0] + u[1] * w[1] <= 1e-9:
                    return "the bus turns too close to the pins for its spacing: click a " \
                        "point farther out first"
        a, b = main[-2], main[-1]
        travel = (b[0] - a[0], b[1] - a[1])
        for e in sheet.query_point(p, 1e-6):
            if isinstance(e, M.Insert) and e.defn is not None and \
                    any(G.dist(q, p) <= 1e-6 for _n, q in e.pin_points()):
                bb = None
                for x in e.defn.entities:
                    bb = G.bbox_union(bb, x._map(e.to_world, rot=e.angle, factor=e.scale,
                                                 mirror=None).bbox())
                if bb is None:
                    break
                c = ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)
                inward = (c[0] - pins[0][0], c[1] - pins[0][1])
                if inward[0] * travel[0] + inward[1] * travel[1] < -1e-9:
                    return "that side of it faces away from the bus (the wires would run " \
                        "through it): come at it from the other side"
                break
        return None

    def _why_not_landed(self, sheet, p):
        """A click on a symbol's side of pins that the bus can't land on wire for wire: why
        (the owner, 0.16: "the bus says why it can't land"), or None."""
        got = pin_side(sheet, p)
        if got is None or self._landing(sheet, p) is not None:
            return None
        pins, gap = got
        if len(pins) == self.count and abs(gap - self.spacing) <= 1e-6:
            tries = self._land_tries(sheet, p, pins)
            # (the usual route's reason first, else a Z's)
            faults = [f for _r, f in tries if f]
            if not faults:
                return None
            return "Not landed wire for wire: %s" % faults[0]
        what = []
        if len(pins) != self.count:
            what.append("that side has %d pins, the bus %d wires" % (len(pins), self.count))
        if abs(gap - self.spacing) > 1e-6:
            what.append("its pins are %s\" apart, the bus's wires %s\"" % (
                _fmt(gap), _fmt(self.spacing)))
        return "Not landed wire for wire: %s (N and D change the bus's count and spacing)" % \
            " and ".join(what)

    @staticmethod
    def _onto(paths, tap, at_start, main):
        """Wires side by side at the bus's start (or end): each wire's first (or last) point
        moved along its leg onto its own wire, in the order they are met along the bus's path
        (main: its points)."""
        if tap is None or len(main) < 2:
            return paths
        across, lines = tap
        k = 1 if across else 0          # (the coordinate the lines differ in)
        # (from the start: the farthest back first; at the end: the first met)
        going = main[1][k] - main[0][k] if at_start else main[-1][k] - main[-2][k]
        order = sorted(lines, reverse=going < 0)
        out = []
        for i, pts in enumerate(paths):
            pts = list(pts)
            if len(pts) >= 2:
                a, b = (pts[0], pts[1]) if at_start else (pts[-1], pts[-2])
                if abs(a[1 - k] - b[1 - k]) < 1e-9:            # (a leg square to them)
                    if i < len(order):
                        q = list(a)
                        q[k] = order[i]
                        if at_start:
                            pts[0] = tuple(q)
                        else:
                            pts[-1] = tuple(q)
            out.append([tuple(q) for q in M._tidy(pts)])
        return [p for p in out if len(p) >= 2]

    def _paths(self, pts):
        paths = self._on_pins(bus_paths(pts, self.count, self.spacing, self._flip_for(pts)))
        return self._onto(self._onto(paths, self.tap_start, True, pts), self.tap_end, False,
                          pts)

    def _make(self, fan=None):
        made = 0
        if self.step == "path" and (len(self.points) >= 2 or fan):
            paths = fan if fan else self._paths(self.points)
            sheet = self.ctx.sheet()
            project = self.ctx.project
            # (left at the WIRES layer: the current wire layer, as a wire's)
            chosen = self.layers if self.layers != ["WIRES"] else [wire_layer(self.ctx)]
            layers = bus_layer_list(chosen, len(paths))
            with self.ctx.edit("Bus") as ed:
                for pts, layer in zip(paths, layers):
                    if layer not in project.layers:
                        ed.layer(layer, None, M.Layer(
                            layer, WIRE_LAYER_COLORS.get(layer, "#ff3030"),
                            wire_color=WIRE_COLOR_NAMES.get(layer, "")).to_dict())
                    w = ed.add(sheet, M.Wire(pts, layer=layer))
                    made += 1
                    if _cleanup_on(self.ctx):
                        from .wires import tidy_new
                        tidy_new(ed, sheet, w)
        if made:
            self.ctx.message("Bus of %d wires" % made)
            _flag_misses(self.ctx, [q for pts in paths for q in (pts[0], pts[-1])])
        self.finish()

    def preview(self, p):
        if self.step != "path":
            return []
        if not self.points:
            got = pin_side(self.ctx.sheet(), p)
            if got is not None:
                return [M.Wire([q, (q[0] - 0.25, q[1])]) for q in got[0]]
            return [M.Wire(q) for q in bus_paths([p, (p[0] + 0.25, p[1])], self.count,
                                                 self.spacing, self.flip)]
        sheet = self.ctx.sheet()
        land = self._landing(sheet, p)
        if land is not None:
            # (the side of the pin pointed at, as the click takes it; near one, the first's)
            at = p if pin_side(sheet, p) is not None else land
            got = pin_side(sheet, at)
            new = self._land_route(sheet, at, got[0]) if got is not None else None
            if new:
                return [M.Wire(q) for q in self._paths(self.points + new)]
        else:
            fan = self._fan(sheet, p)
            if fan is not None:
                return [M.Wire(q) for q in fan]
        p = land if land is not None else (p[0] + self.offset[0], p[1] + self.offset[1])
        pts = self.points + self._around(self._route(p))
        return [M.Wire(q) for q in self._paths(pts)]


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
                          wiring=d.get("wiring", ""), manufacturer=d.get("manufacturer", ""),
                          family=d.get("family", ""), series=d.get("series", ""),
                          catalog=d.get("catalog", ""),
                          show_pins=bool(d.get("show_pins", False)),
                          phases=d.get("phases", ""))
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


PAIR_LIST, PAIR_PICK = "*LIST", "*PICK"     # (an arrow's pairing buttons: no name is either)


class InsertCmd(Command):
    """Place a symbol or footprint (from the Library panel): pick where; R turns it 90
    degrees, F flips it side to side, V upside down. A symbol with pins is held by its first pin (L1, 1, A1...), so the
    point picked is where that pin lands, on the pin or wire it is to join (the owner: a 3-pole
    fuse grabbed by its middle met the disconnect's pins with its middle); B moves the hold to
    the next pin, then the block's own base point. A contact then asks which device it belongs
    to: a typed tag takes that device (the nearest one with its prefix is offered as a
    button), L lists them, P picks it on the drawing; Enter places it on its own."""
    name, title = "INSERT", "Insert"
    repeatable = True       # (Enter: the same symbol again, the owner, 0.16)

    def __init__(self, ctx, defn, attrs=None):
        super().__init__(ctx)
        # (as given: a repeat starts from these again, its tag and links worked out anew)
        self.repeat_args = (defn, dict(attrs or {}))
        self.defn, self.attrs = defn, dict(attrs or {})
        if getattr(defn, "manufacturer", "") and not self.attrs.get("MFR"):
            # the block says who makes it: the copy's MFR, as a part's would (a part's own
            # manufacturer, given in attrs, wins)
            self.attrs["MFR"] = defn.manufacturer
        if getattr(defn, "catalog", "") and not self.attrs.get("CAT"):
            self.attrs["CAT"] = defn.catalog         # (its catalog number, as a part's)
        self.angle, self.mirror = 0.0, False
        # where the block is held: its pins in order, then its own base point (None)
        self.holds = [(p["name"], p["pos"]) for p in defn.pins] + [(None, (0.0, 0.0))] \
            if defn.kind == "symbol" and defn.pins else [(None, (0.0, 0.0))]
        self.hold = 0
        self.pending = None             # a contact's point, waiting for its device
        self.cands = []
        self.footprint_of = False       # (the device asked for is a footprint's)
        self.link_name = None           # an off-sheet connector's name offered
        self.placed_mirror = None       # flipped as placed (_fit), once a point is picked

    def begin(self):
        self._ask()

    def _ask(self):
        name = self.holds[self.hold][0]
        opts = [("Rotate 90", "R"), ("Flip horizontal", "F"), ("Flip vertical", "V")]
        if len(self.holds) > 1:
            nxt = self.holds[(self.hold + 1) % len(self.holds)][0]
            opts.append(("Base point: %s" % ("pin " + nxt if nxt else "center"), "B"))
        self.ctx.prompt("Specify insertion point for %s%s" % (
            self.defn.name, " (where pin %s goes)" % name if name else ""), opts)

    def origin(self, p, mirror=None):
        """The block's insertion point for its hold (a pin, or its base point) at p, as it is
        turned and flipped now (or flipped as mirror says)."""
        q = self.holds[self.hold][1]
        if q == (0.0, 0.0):
            return p
        w = M.Insert(self.defn.name, (0.0, 0.0), self.angle, 1.0,
                     self.mirror if mirror is None else mirror, {}, self.defn).to_world(q)
        return (p[0] - w[0], p[1] - w[1])

    def _landed(self, sheet, q, tol=1e-6):
        """A pin at q would join something: a wire through or ending at q, or a pin there."""
        for e in sheet.query_point(q, tol):
            if isinstance(e, M.Wire):
                if any(G.dist_to_segment(q, a, b) <= tol
                       for a, b in zip(e.points, e.points[1:])):
                    return True
            elif isinstance(e, M.Insert) and any(G.dist(q, r) <= tol
                                                 for _n, r in e.pin_points()):
                return True
        return False

    def _fit(self, p):
        """Where it goes for a point picked (the insertion point) and whether it is flipped:
        as turned and flipped, unless flipped the other way more of its pins land on wires
        or pins (the owner, 0.16: "I want to be able to orient it either direction and still
        connect to wires or devices properly": a 3-pole symbol turned to run down a vertical
        bus had its poles off the bus, only L1 on it)."""
        here = self.mirror
        d = self.defn
        if d.kind != "symbol" or len(d.pins) < 3 or self.holds[self.hold][0] is None:
            return self.origin(p), here
        sheet = self.ctx.sheet()

        def count(m):
            ins = M.Insert(d.name, self.origin(p, m), self.angle, 1.0, m, {}, d)
            return sum(1 for _n, q in ins.pin_points() if self._landed(sheet, q))
        if count(not here) > count(here):
            here = not here
        return self.origin(p, here), here

    def text(self, s):
        k = s.strip().upper()
        if self.pending is not None and self.link_name is not None:
            # (paired with a chosen one, from a list or clicked on any sheet: the owner,
            # 0.18.5, "AutoCAD allows for specific ones, but I have to tell it where it is, by
            # either selecting it from a drop down or navigating to the sheet and clicking")
            host = getattr(self.ctx, "host", None)
            if k == PAIR_LIST:
                pick = getattr(host, "pick_connector", None)
                got = pick(self._pair_candidates()) if pick is not None else None
                if got is not None:
                    self._pair_with(got[1])
                return True
            if k == PAIR_PICK and host is not None and hasattr(host, "pick_device_for"):
                return self._pick_pair_on_drawing(host)
            self._place(self.pending, dict(self.attrs, TAG=k))
            return True
        if self.pending is not None:
            from . import tags
            host = getattr(self.ctx, "host", None)
            if k == "P" and host is not None and hasattr(host, "pick_device_for"):
                # (picked on the drawing, on any sheet: placed once it is)
                return self._pick_on_drawing(host)
            if k == "L":
                pick = getattr(self.ctx.host, "pick_parent", None)
                got = pick(self.cands) if pick is not None else None
                if got is not None:
                    self._place(self.pending, self._link(got[1]))
                return True
            if self.footprint_of and k == "N":
                self._place(self.pending, self.attrs)       # (none: a footprint of its own)
                return True
            got = tags.find_tag(self.ctx.project, k)
            if got is not None:
                self._place(self.pending, self._link(got[1]))
            elif self.footprint_of:
                self._place(self.pending, dict(self.attrs, TAG=k))
                self.ctx.message("No device is tagged %s: the footprint shows it, linked to "
                                 "none" % k)
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
        if k in ("F", "V"):
            # flipped as it is on the drawing, however turned (the owner, 0.17: "Symbols need
            # to be able to flip horizontally and vertically when inserting"). A copy's mirror
            # turns it upside down before its angle turns it: turned a, upside down again is
            # turned -a; left and right swapped is turned 180 - a (until 0.17, F was only the
            # mirror: upside down when not turned)
            self.mirror = not self.mirror
            self.angle = ((180.0 if k == "F" else 0.0) - self.angle) % 360.0
            return True
        if k == "B" and len(self.holds) > 1:
            self.hold = (self.hold + 1) % len(self.holds)
            self._ask()
            return True
        return False

    def _pair_candidates(self):
        """[(sheet, connector)] this one may pair with: of the other kind (a destination for a
        source arrow, a source for a destination), or any for an off-sheet connector; those
        still waiting for their other half first, then in sheet order."""
        from .wirenums import ARROWS, connectors
        want = {ARROWS[0]: ARROWS[1], ARROWS[1]: ARROWS[0]}.get(self.defn.name)
        ends = connectors(self.ctx.project)
        out = []
        for name, es in ends.items():
            for s, c in es:
                if want is None or c.block == want:
                    waiting = not any(oc is not c and (want is None or oc.block != want)
                                      for _os, oc in es)
                    out.append((not waiting, self.ctx.project.sheets.index(s)
                                if s in self.ctx.project.sheets else 0, name, s, c))
        out.sort(key=lambda t: t[:3])
        return [(s, c) for _w, _i, _n, s, c in out]

    def _pair_with(self, other):
        name = other.attrs.get("TAG", "").strip().upper()
        if not name:
            self.ctx.message("That one has no name yet: give it one first")
            return
        self._place(self.pending, dict(self.attrs, TAG=name))
        self.ctx.message("Paired with %s %s" % (other.block.lower(), name))

    def _pick_pair_on_drawing(self, host):
        """The arrow (or connector) this one pairs with, clicked on any sheet: back on this
        sheet, it is placed with that one's name."""
        ctx, at, defn, attrs = self.ctx, self.pending, self.defn, dict(self.attrs)
        angle, mirror = self.angle, self.placed_mirror

        def done(other):
            if other is None:
                return
            cmd = ctx.run(InsertCmd, defn, attrs)
            cmd.angle, cmd.placed_mirror = angle, mirror
            cmd.pending = at
            cmd._pair_with(other)
        host.pick_device_for(done, kind="connector")
        return True

    def _pick_on_drawing(self, host):
        """The device this contact (or footprint) belongs to, clicked on the drawing: back on
        this sheet, it is placed as it was going to be, linked to it."""
        ctx, at, defn, attrs = self.ctx, self.pending, self.defn, dict(self.attrs)
        angle, mirror, footprint = self.angle, self.placed_mirror, self.footprint_of

        def done(dev):
            if dev is None:
                return
            cmd = ctx.run(InsertCmd, defn, attrs)
            cmd.angle, cmd.placed_mirror, cmd.footprint_of = angle, mirror, footprint
            cmd._place(at, cmd._link(dev))
        host.pick_device_for(done)
        return True

    def enter(self):
        if self.pending is not None and self.link_name is not None:
            self._place(self.pending, dict(self.attrs, TAG=self.link_name))
            return
        if self.pending is not None and self.cands and self.footprint_of:
            self._place(self.pending, self._link(self.cands[0][1]))
            return
        if self.pending is not None and self.cands:
            self._place(self.pending, self.attrs)
            self.ctx.message("%s placed on its own, linked to no device (double-click it to "
                             "link it later)" % self.defn.name)
            return
        super().enter()

    def _link(self, device):
        """Its attributes as device's contact (or, a footprint, as device's footprint)."""
        from . import tags
        if self.footprint_of:
            return tags.link_footprint(self.attrs, device)
        return tags.link_attrs(self.attrs, device)

    def _make(self, p, defn, mirror=None):
        layer = "SYMBOLS" if self.defn.kind == "symbol" else "PANEL"
        tag_h = self.ctx.project.settings.get("tag_height") * self.ctx.sheet().k() \
            if self.defn.kind == "symbol" else None
        return M.Insert(defn.name, p, self.angle, 1.0,
                        self.mirror if mirror is None else mirror, self.attrs, defn,
                        tag_h, layer=layer)

    def _on_rail(self, p):
        """A footprint's insertion point, its rail point locked onto a DIN rail it comes
        over (CadView.rail_magnet)."""
        mag = getattr(self.ctx, "rail_magnet", None)
        if self.defn.kind != "footprint" or mag is None:
            return p
        dx, dy = mag([self._make(p, self.defn)], 0.0, 0.0)
        return (p[0] + dx, p[1] + dy)

    def preview(self, p):
        if self.pending is not None:
            return [self._make(self.pending, self.defn, self.placed_mirror)]
        at, m = self._fit(p)
        return [self._make(self._on_rail(at), self.defn, m)]

    def point(self, p):
        if self.pending is not None:
            return                      # (waiting for the contact's device)
        at, self.placed_mirror = self._fit(p)
        p = self._on_rail(at)
        d = self.defn
        if d.wiring == "link" and not self.attrs.get("TAG") and d.name == "Source arrow":
            # (a source arrow on a numbered wire is named by the wire's number, unless another
            # source has it: the owner, 0.18.4, "I have to type in the wire name for source
            # symbols. That should intuitively grab the wire number of what I attach it to")
            from .wirenums import number_at, connectors
            num = number_at(self.ctx.sheet(), self._make(p, d, self.placed_mirror))
            taken = any(c.block == d.name for _s, c in
                        connectors(self.ctx.project).get(num.upper(), []))
            if num and not taken:
                self.ctx.message("Source arrow %s: a destination arrow named %s continues it"
                                 % (num, num))
                self._place(p, dict(self.attrs, TAG=num.upper()))
                return
        if d.wiring == "link" and not self.attrs.get("TAG"):
            # an off-sheet connector: its name pairs it with the other end
            from .wirenums import next_name, connectors
            self.pending = p
            self.link_name = next_name(self.ctx.project, self.ctx.sheet())
            waiting = self.link_name in connectors(self.ctx.project)
            self.ctx.prompt("Connector name: Enter for %s (%s), type a name, or pick the one "
                            "it pairs with" % (self.link_name, "continues the wire from "
                                               "another sheet" if waiting else "a new one"),
                            [("List...", PAIR_LIST), ("Pick on drawing", PAIR_PICK)])
            return
        if d.kind == "symbol" and d.role == "child" and not self.attrs.get("PARENT") \
                and not self.attrs.get("TAG"):
            from . import tags
            project = self.ctx.project
            self.cands = tags.candidates(project, self.ctx.sheet(), d.prefix, p)
            if self.cands:
                # (Enter places it on its own: linking is a choice, the owner, 0.17: "I don't
                # want parent symbols to try to be children by default"; the nearest device is
                # offered as a button)
                self.pending = p
                s, e = self.cands[0]
                tag = e.attrs.get("TAG", "?")
                self.ctx.prompt("Belongs to: type a tag, or pick %s (%s, the nearest); Enter: "
                                "on its own" % (tag, project.zone_text(s, e.pos[0], e.pos[1])
                                                or "?"),
                                [("%s (nearest)" % tag, tag), ("List", "L"),
                                 ("Pick on drawing", "P")])
                return
            self.ctx.message("Nothing to link this %s to yet (a %s device): placed unlinked "
                             "(double-click it to link it later)"
                             % (d.name.lower(), d.prefix or "parent"))
        if d.kind == "footprint" and not self.attrs.get("TAG") and \
                not self.attrs.get("PARENT"):
            # which schematic device it is: its tag shows on it, and follows it
            from . import tags
            project = self.ctx.project
            self.cands = tags.footprint_candidates(project, self.attrs.get("CAT") or d.catalog)
            if self.cands:
                self.pending, self.footprint_of = p, True
                s, e = self.cands[0]
                desc = e.attrs.get("DESC", "") or e.defn.description or e.defn.name
                self.ctx.prompt("Which device is it: Enter for %s (%s, %s), type a tag, or N for "
                                "none" % (e.attrs.get("TAG", "?"), desc,
                                          project.zone_text(s, e.pos[0], e.pos[1]) or "?"),
                                [("List", "L"), ("None", "N")])
                return
        self._place(p, self.attrs)

    def _place(self, p, attrs):
        project = self.ctx.project
        sheet = self.ctx.sheet()
        with self.ctx.edit("Insert %s" % self.defn.name) as ed:
            # the project keeps its own copy (a block already in it stays as it was), under
            # its name, or "name (footprint)" when a symbol already has that name (0.18)
            pname = M.project_block_name(project, self.defn.name, self.defn.kind)
            if pname not in project.blocks:
                ed.block(M.renamed_block(self.defn, pname))
            from . import tags
            defn = project.blocks[pname]
            ins = self._make(p, defn, self.placed_mirror).copy(attrs=attrs)
            ins = ins.copy(attrs=tags.new_attrs(project, sheet, defn, ins.attrs))
            if defn.kind == "footprint":
                # its label to start (Panel settings): its tag, or with none its part number,
                # or its block's name
                show = project.settings.get("footprint_label", "tag")
                if show == "tag" and not ins.attrs.get("TAG"):
                    show = "cat" if (ins.attrs.get("CAT") or defn.catalog) else "name"
                if show:
                    ins = ins.copy(label=show, tag_h=float(project.settings.get(
                        "fp_label_height", 0.08)) * sheet.k())
            if ins.layer not in project.layers:
                ed.layer(ins.layer, None, M.Layer(ins.layer, M.ADAPTIVE).to_dict())
            ed.add(sheet, ins)
            if defn.wiring == "link" and ins.attrs.get("TAG"):
                # (a destination arrow's wire takes its source's layer, 0.18.4)
                from .wirenums import match_arrow_layers
                match_arrow_layers(ed, project, ins.attrs["TAG"].strip().upper())
            if self.defn.kind == "symbol":
                # placed on a wire: the wire is cut between its pins
                from .wires import break_under
                if break_under(ed, sheet, ins):
                    self.ctx.message("Wire cut to fit %s" % self.defn.name)
        self.ctx.set_selection(set())
        self.finish()


class DashBoxCmd(Command):
    """DASHBOX: a dashed box (the owner, 0.16): two opposite corners, then its window: a note
    to write in it (several lines, or none) and the device it belongs to (none; typed or
    picked from the project's devices; or Pick on drawing..., on any sheet)."""
    name, title = "DASHBOX", "Dashed box"

    def begin(self):
        self.first = None
        self.ctx.prompt("Specify first corner of the dashed box")

    def text(self, s):
        q = size_typed(self, s) if self.first is not None else None
        if q is not None:
            self.point(q)
            return True
        return False

    def point(self, p):
        if self.first is None:
            self.first = self.base = self.last = p
            self.ctx.prompt("Specify opposite corner (or width,height)")
            return
        if abs(p[0] - self.first[0]) < 1e-9 or abs(p[1] - self.first[1]) < 1e-9:
            self.ctx.message("A box needs width and height: pick a corner across from the first")
            return
        box = M.DashBox.from_corners(self.first, p, height=self._height())
        host = self.ctx.host
        got = host.ask_dash_box(box) if host is not None else {"text": "", "device": None}
        self.finish()
        if got is None:
            return
        if got.get("pick"):
            # (the device picked on the drawing, on any sheet: the box is made after)
            sheet_id = self.ctx.sheet().id
            # (Esc while picking: no box)
            host.pick_device_for(lambda dev: dev is not None and _add_box(
                self.ctx, sheet_id, box, got["text"], dev))
            return
        _add_box(self.ctx, self.ctx.sheet().id, box, got["text"], got.get("device"))

    def _height(self):
        return float(self.ctx.project.settings.get("tag_height", 0.1)) * self.ctx.sheet().k()

    def preview(self, p):
        if self.first is None or abs(p[0] - self.first[0]) < 1e-9 or \
                abs(p[1] - self.first[1]) < 1e-9:
            return []
        return [M.DashBox.from_corners(self.first, p, height=self._height())]


def _add_box(ctx, sheet_id, box, text, device):
    """Add a dashed box (with its note, belonging to device or to none) to its sheet."""
    from . import tags
    project = ctx.project
    sheet = next((s for s in project.sheets if s.id == sheet_id), None)
    if sheet is None:
        return None
    attrs = tags.link_attrs({}, device) if device is not None else {}
    b = box.copy(text=text or "", attrs=attrs)
    with ctx.edit("Dashed box") as ed:
        if b.layer not in project.layers:
            ed.layer(b.layer, None, M.Layer(b.layer, M.ADAPTIVE).to_dict())
        b = ed.add(sheet, b)
    ctx.message("Dashed box%s" % (" belonging to %s" % device.attrs.get("TAG", "?")
                                  if device is not None else ""))
    return b


class PickDeviceCmd(Command):
    """Pick a device on the drawing, on any sheet (go to another sheet and click it): then
    got(device), or got(None) when Esc stops it. Run by MainWindow.pick_device_for, which
    starts it again on the sheet shown when the sheet changes."""
    name, title = "PICKDEVICE", "Pick device"
    repeatable = False

    def __init__(self, ctx, got, kind="device"):
        super().__init__(ctx)
        self.got = got
        self.kind = kind                # "device", or "connector" (an arrow, off-sheet)

    def begin(self):
        if self.kind == "connector":
            self.ctx.prompt("Click the arrow or off-sheet connector to pair it with (go to any "
                            "sheet first if it's on another; Esc stops)")
        else:
            self.ctx.prompt("Click the device it belongs to (go to any sheet first if it's on "
                            "another; Esc stops)")

    def point(self, p):
        from . import tags
        e = self.ctx.pick_entity(p, M.Insert) if hasattr(self.ctx, "pick_entity") else None
        if self.kind == "connector":
            if e is None or e.defn is None or e.defn.wiring != "link":
                self.ctx.message("That isn't an arrow or off-sheet connector: click one")
                return
        elif e is None or not tags.is_device(e) or not e.attrs.get("DEV"):
            self.ctx.message("That isn't a device with a tag: click a coil, a breaker, a "
                             "distribution block...")
            return
        got, self.got = self.got, None
        self.finish()
        got(e)

    def cancel(self):
        got, self.got = self.got, None
        Command.cancel(self)
        if got is not None:
            got(None)


class ArrayCmd(Command):
    """ARRAY: copies of the selected objects in rows and columns (R, to start) or round a
    center (P), as AutoCAD's ARRAY. Rectangular: rows, columns, then the distance between
    rows (up; negative: down) and between columns (across; negative: left). Polar: the
    center, how many in all, and the angle they fill (360 to start), each turned with it.
    Copies are new objects: devices get tags of their own, as Copy gives them."""
    name, title = "ARRAY", "Array"
    selects = True

    def begin(self):
        self.ents = _selected(self.ctx)
        self.mode = None
        self.vals = []
        self.center = None
        self.ctx.prompt("Rectangular or Polar? (Enter: Rectangular)",
                        [("Rectangular", "R"), ("Polar", "P")])

    QUESTIONS = {"R": ["Number of rows (up and down)", "Number of columns (across)",
                       "Distance between rows (up; negative: down)",
                       "Distance between columns (across; negative: left)"],
                 "P": ["Number of items in all", "Angle to fill (degrees; Enter: 360)"]}

    def _ask(self):
        q = self.QUESTIONS[self.mode]
        if self.mode == "P" and self.center is None:
            self.ctx.prompt("Specify center point of the array")
            return
        if len(self.vals) < len(q):
            self.ctx.prompt(q[len(self.vals)])

    def text(self, s):
        k = s.strip().upper()
        if self.mode is None and k in ("R", "P"):
            self.mode = k
            self._ask()
            return True
        return False

    def enter(self):
        if self.selecting():
            return Command.enter(self)
        if self.mode is None:
            self.mode = "R"
            self._ask()
            return
        if self.mode == "P" and len(self.vals) == 1:
            self.number(360.0)
            return
        self.finish()

    def point(self, p):
        if self.mode is None:
            self.mode = "R"
        if self.mode == "P" and self.center is None:
            self.center = self.base = self.last = p
            self._ask()

    def number(self, v):
        if self.mode is None:
            return False
        if self.mode == "P" and self.center is None:
            return False
        i = len(self.vals)
        if i < 2 and self.mode == "R" or i == 0 and self.mode == "P":
            if v < 1 or abs(v - round(v)) > 1e-9 or v > 1000:
                self.ctx.message("A whole number from 1 to 1000")
                return True
            v = int(round(v))
        self.vals.append(v)
        need = len(self.QUESTIONS[self.mode])
        if len(self.vals) >= need:
            self._make()
        else:
            self._ask()
        return True

    def copies(self, vals=None):
        """[(dx, dy, angle)] of the copies (not the original)."""
        vals = self.vals if vals is None else vals
        out = []
        if self.mode == "R":
            rows, cols, dr, dc = (list(vals) + [0, 0, 0, 0])[:4]
            for r in range(int(rows)):
                for c in range(int(cols)):
                    if r or c:
                        out.append((c * dc, r * dr, 0.0))
        elif self.mode == "P" and vals:
            n = int(vals[0])
            fill = vals[1] if len(vals) > 1 else 360.0
            step = fill / n if abs(abs(fill) - 360.0) < 1e-9 else \
                (fill / (n - 1) if n > 1 else 0.0)
            for i in range(1, n):
                out.append((0.0, 0.0, step * i))
        return out

    def _placed(self, e, dx, dy, ang):
        c = e.rotated(self.center, ang) if ang else e.moved(dx, dy)
        c.id = None
        return c

    def _make(self):
        from .tags import retag_copies
        made = [self._placed(e, dx, dy, a) for dx, dy, a in self.copies() for e in self.ents]
        if not made:
            self.ctx.message("One row and one column: nothing to copy")
            self.finish()
            return
        sheet = self.ctx.sheet()
        with self.ctx.edit("Array") as ed:
            for e in retag_copies(self.ctx.project, sheet, made):
                ed.add(sheet, e)
        self.ctx.message("Array: %d copies" % (len(made) // max(1, len(self.ents))))
        self.finish()

    def preview(self, p):
        if self.mode == "R" and len(self.vals) == 3:
            # (the column spacing still to type: shown toward the cursor)
            got = self.copies(self.vals + [p[0] - self._origin()[0]])
        elif self.mode == "R" and len(self.vals) == 2:
            got = self.copies(self.vals + [p[1] - self._origin()[1], 0.0])
        else:
            return []
        if len(got) * len(self.ents) > 2000:
            return []
        return [self._placed(e, dx, dy, a) for dx, dy, a in got for e in self.ents]

    def _origin(self):
        bb = None
        for e in self.ents:
            bb = G.bbox_union(bb, e.bbox())
        return (bb[0], bb[1]) if bb else (0.0, 0.0)


def offset_entity(e, d, side):
    """A copy of e d away on the side of the point side (OFFSET), or (None, why)."""
    if isinstance(e, M.Wire) or not isinstance(e, (M.Line, M.Polyline, M.Circle, M.Arc)):
        return None, "Offset works on lines, polylines and rectangles, circles and arcs"
    if isinstance(e, M.Line):
        a, b = e.p1, e.p2
        L = G.dist(a, b)
        if L < 1e-12:
            return None, "That line has no length"
        nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
        sgn = 1.0 if (side[0] - a[0]) * nx + (side[1] - a[1]) * ny >= 0 else -1.0
        c = e.copy(p1=[a[0] + nx * d * sgn, a[1] + ny * d * sgn],
                   p2=[b[0] + nx * d * sgn, b[1] + ny * d * sgn])
        c.id = None
        return c, None
    if isinstance(e, (M.Circle, M.Arc)):
        inside = G.dist(side, e.center) < e.radius
        r = e.radius - d if inside else e.radius + d
        if r <= 1e-9:
            return None, "Too far inside: the %s would vanish" % e.kind
        c = e.copy(radius=r)
        c.id = None
        return c, None
    pts = list(e.points)
    if len(pts) < 2:
        return None, "That polyline has one point"
    segs = e.segments()
    # the side: left or right of the side nearest the point picked
    best = min(range(len(segs)), key=lambda i: G.dist_to_segment(side, *segs[i]))
    a, b = segs[best]
    cross = (b[0] - a[0]) * (side[1] - a[1]) - (b[1] - a[1]) * (side[0] - a[0])
    s = d if cross >= 0 else -d                 # (left of travel: positive)
    lines = []
    for a, b in segs:
        L = G.dist(a, b)
        if L < 1e-12:
            continue
        nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
        lines.append(((a[0] + nx * s, a[1] + ny * s), (b[0] + nx * s, b[1] + ny * s)))
    if not lines:
        return None, "That polyline has no length"

    def meet(l1, l2):
        (p1, p2), (p3, p4) = l1, l2
        d1 = (p2[0] - p1[0], p2[1] - p1[1])
        d2 = (p4[0] - p3[0], p4[1] - p3[1])
        den = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(den) < 1e-12:
            return p2                           # (straight on: the shared point)
        t = ((p3[0] - p1[0]) * d2[1] - (p3[1] - p1[1]) * d2[0]) / den
        return (p1[0] + d1[0] * t, p1[1] + d1[1] * t)
    if e.closed:
        new = [meet(lines[i - 1], lines[i]) for i in range(len(lines))]
    else:
        new = [lines[0][0]] + [meet(lines[i - 1], lines[i]) for i in range(1, len(lines))] + \
            [lines[-1][1]]
    # each side must still run the way it did (else it was offset past its own width)
    sides = list(zip(new, new[1:] + ([new[0]] if e.closed else [])))
    for (p, q), (a, b) in zip(sides, lines):
        if (q[0] - p[0]) * (b[0] - a[0]) + (q[1] - p[1]) * (b[1] - a[1]) <= 1e-12:
            return None, "Too far: the shape would turn inside out"
    c = e.copy(points=[list(q) for q in new])
    c.id = None
    return c, None


class OffsetCmd(Command):
    """OFFSET: a copy of a line, polyline (a rectangle), circle or arc, a set distance away on
    the side you click, as AutoCAD's OFFSET (the owner, 0.16: "duplicate a shape either
    larger or smaller than the one selected"): type the distance (or T: through a point),
    then pick the object and click the side; it goes on with the same distance until
    Enter."""
    name, title = "OFFSET", "Offset"

    def begin(self):
        self.dist = getattr(self.ctx, "_offset_dist", None)
        self.through = False
        self.ent = None
        self.ctx.set_selection(set())
        self._ask_dist()

    def _ask_dist(self):
        self.picking = False
        last = " (Enter: %s)" % _fmt(self.dist) if self.dist else ""
        self.ctx.prompt("Specify offset distance%s" % last, [("Through", "T")])

    def _ask_object(self):
        self.picking = True
        self.ent = None
        self.ctx.prompt("Select object to offset (Enter to finish)")

    def text(self, s):
        if s.strip().upper() == "T" and not self.picking and self.ent is None:
            self.through = True
            self._ask_object()
            return True
        return False

    def number(self, v):
        if self.picking or self.ent is not None:
            return False
        if v <= 0:
            self.ctx.message("The distance must be more than 0")
            return True
        self.dist = v
        self.ctx._offset_dist = v
        self._ask_object()
        return True

    def enter(self):
        if not self.picking and self.ent is None and self.dist:
            self._ask_object()
            return
        self.finish()

    def pick(self, p):
        e = self.ctx.pick_entity(p)
        if e is None:
            return
        got, why = offset_entity(e, 1e-6, p)       # (can it be offset at all)
        if got is None:
            self.ctx.message(why)
            return
        self.ent = e
        self.picking = False
        self.ctx.prompt("Specify point %s" % ("to offset through" if self.through else
                                              "on side to offset"))

    def _distance(self, p):
        if not self.through:
            return self.dist
        e = self.ent
        if isinstance(e, (M.Circle, M.Arc)):
            return abs(G.dist(p, e.center) - e.radius)
        return e.distance(p)

    def point(self, p):
        if self.ent is None:
            return
        d = self._distance(p)
        got, why = offset_entity(self.ent, d, p) if d > 1e-9 else (None, "That's on it")
        if got is None:
            self.ctx.message(why)
            return
        sheet = self.ctx.sheet()
        with self.ctx.edit("Offset") as ed:
            ed.add(sheet, got)
        self._ask_object()

    def preview(self, p):
        if self.ent is None:
            return []
        d = self._distance(p)
        got, _why = offset_entity(self.ent, d, p) if d > 1e-9 else (None, None)
        return [got] if got is not None else []


class NumberCmd(Command):
    """NUMBER: the selected texts numbered in order (numbering.py; the owner, 0.16: "select
    whatever text boxes and then choose 1,2,3...; A,B,C...; S1, S2, S3...; A1, B2,C3..."): a
    window says how (the sequence, its start and step, a prefix and suffix, top to bottom or
    left to right, replacing the text or put before or after it); one edit, one Undo."""
    name, title = "NUMBER", "Number texts"
    selects = True

    def begin(self):
        from . import numbering as N
        texts = [e for e in _selected(self.ctx) if isinstance(e, (M.Text, M.MText))]
        if not texts:
            self.ctx.message("Select texts to number (single-line or multi-line texts)")
            self.finish()
            return
        host = self.ctx.host
        how = host.ask_numbering(len(texts)) if host is not None else None
        if how is None:
            self.finish()
            return
        texts = N.ordered(texts, how.get("order", "down"))
        names = N.labels(len(texts), how.get("sequence", "number"), how.get("start", "1"),
                         int(how.get("step", 1)), int(how.get("digits", 0)),
                         how.get("prefix", ""), how.get("suffix", ""),
                         how.get("letter_start", "A"))
        sheet = self.ctx.sheet()
        with self.ctx.edit("Number texts") as ed:
            for e, label in zip(texts, names):
                ed.change(sheet, e.copy(text=N.apply_to(e.text, label, how.get("mode",
                                                                               "replace"))))
        self.ctx.message("Numbered %d texts: %s ... %s" % (len(texts), names[0], names[-1]))
        self.finish()


class PickWindowCmd(Command):
    """Two corners picked on the drawing (the Print window's Window): then got(rect), the
    rectangle (x0, y0, x1, y1) in drawing units, or got(None) when cancelled."""
    name, title = "PRINTWINDOW", "Print window"
    repeatable = False

    def __init__(self, ctx, got):
        super().__init__(ctx)
        self.got = got
        self.first = None
        self.rect = None

    def begin(self):
        self.ctx.prompt("Specify first corner of the area to print")

    def point(self, p):
        if self.first is None:
            self.first = self.base = self.last = p
            self.ctx.prompt("Specify opposite corner")
            return
        a = self.first
        if abs(p[0] - a[0]) < 1e-9 or abs(p[1] - a[1]) < 1e-9:
            return                      # (no area: pick another corner)
        self.rect = (min(a[0], p[0]), min(a[1], p[1]), max(a[0], p[0]), max(a[1], p[1]))
        self.finish()

    def preview(self, p):
        if self.first is None:
            return []
        a = self.first
        return [M.Polyline([a, (p[0], a[1]), p, (a[0], p[1])], True)]

    def finish(self):
        got, self.got = self.got, None
        super().finish()
        if got is not None:
            got(self.rect)


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

    def _units(self):
        return M.dim_units(self.ctx.project.settings.get("dim_units", "decimal"))

    # (its two points follow Ortho and Polar as any point does, an object snap near the mouse
    # first: the owner, 0.17.4, "Linear measurement is not following polar or ortho"; until
    # then they went where picked)
    snap_at_mouse = True

    def point(self, p):
        self.pts.append(p)
        self.base = self.last = p
        if len(self.pts) == 1:
            self.ctx.prompt("Specify second extension line origin")
        elif len(self.pts) == 2:
            self.ctx.prompt("Specify dimension line location")
        else:
            d = M.Dimension(self.pts[0], self.pts[1], p, self.mode, self._height(),
                            units=self._units())
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
            return [M.Dimension(self.pts[0], self.pts[1], p, self.mode, self._height(),
                                units=self._units())]
        return []


class DimAlignedCmd(DimLinearCmd):
    """DIMALIGNED: a dimension along the line between the two points (slanted ones too)."""
    name, title = "DIMALIGNED", "Aligned dimension"
    mode = "aligned"


class UseTitleBlockCmd(Command):
    """Use as title block: the selected objects (a title block from another program's
    drawing: a block with attributes, or its lines and texts) become the project's title
    block, where they are; their attributes become fields. One step: Undo puts the old one
    back."""
    name, title = "USETITLEBLOCK", "Use as title block"
    selects = True

    def begin(self):
        from .sheetframe import use_as_title_block
        ents = _selected(self.ctx)
        sheet = self.ctx.sheet()
        if not ents or sheet is self.ctx.project.title_block:
            self.ctx.message("Use as title block: select the title block's objects on a sheet "
                             "first")
            self.finish()
            return
        try:
            with self.ctx.edit(self.title) as ed:
                made = use_as_title_block(ed, self.ctx.project, sheet, ents)
        except ValueError as ex:
            self.ctx.message("Use as title block: %s" % ex)
            self.finish()
            return
        self.ctx.set_selection(set())
        fields = sorted({f for _t, f in made})
        self.ctx.message("The project's title block now: %d object(s)%s. Undo puts the old one "
                         "back; Project properties fills its fields."
                         % (len(ents), ", fields " + ", ".join(fields) if fields else ""))
        self.finish()


class MTextCmd(Command):
    """MTEXT: click a corner of the text's box, then the opposite corner (its width: lines
    wrap there), or Enter after the first for no wrapping; then type the text, several lines,
    in a box. Its height is the text height (H types another first)."""
    name, title = "MTEXT", "Multiline text"

    def begin(self):
        self.p1 = None
        self.height = None
        self.ctx.prompt("Specify the first corner of the text (H: height)", [("Height", "H")])

    def _height(self):
        return self.height or self.ctx.text_height()

    def text(self, s):
        if s.strip().upper() == "H" and self.p1 is None:
            self.asking = True
            self.ctx.prompt("Text height (paper inches: it reads that high on paper)",
                            typing=True)
            return True
        return False

    def number(self, v):
        if getattr(self, "asking", False) and v > 0:
            self.height = float(v) * self.ctx.sheet().k()
            self.asking = False
            self.begin_again()
            return True
        return False

    def begin_again(self):
        self.ctx.prompt("Specify the first corner of the text (H: height)", [("Height", "H")])

    def point(self, p):
        if self.p1 is None:
            self.p1 = self.base = self.last = p
            self.ctx.prompt("Specify the opposite corner (lines wrap at its width), or Enter "
                            "for no wrapping")
            return
        self._ask(p)

    def enter(self):
        if self.p1 is not None:
            self._ask(None)
        else:
            self.finish()

    def _ask(self, p2):
        x0, y0 = self.p1
        if p2 is not None:
            left, top = min(x0, p2[0]), max(y0, p2[1])
            width = abs(p2[0] - x0)
        else:
            left, top, width = x0, y0, 0.0
        host = getattr(self.ctx, "host", None)
        ask = getattr(host, "ask_mtext", None)
        text = ask("") if ask is not None else None
        if text:
            mt = M.MText((left, top), text, self._height(), 0.0, "TL", width,
                         layer=self.ctx.layer())
            with self.ctx.edit(self.title) as ed:
                ed.add(self.ctx.sheet(), mt)
            self.ctx.message("Multiline text: %d line(s)" % len(mt.lines()))
        self.finish()

    def preview(self, p):
        if self.p1 is None:
            return []
        x0, y0 = self.p1
        return [M.Polyline([(x0, y0), (p[0], y0), (p[0], p[1]), (x0, p[1])], True)]


def closed_loop(e):
    """A closed shape's outline as points (a closed polyline or rectangle, a circle as 72
    sides), or None."""
    if isinstance(e, M.Polyline) and e.closed and len(e.points) >= 3:
        return [tuple(q) for q in e.points]
    if isinstance(e, M.Circle):
        return [G.polar(e.center, e.radius, i * 5.0) for i in range(72)]
    return None


def _loop_area(lp):
    a = 0.0
    for i in range(len(lp)):
        (x0, y0), (x1, y1) = lp[i], lp[(i + 1) % len(lp)]
        a += x0 * y1 - x1 * y0
    return abs(a) / 2


def boundary_at(sheet, p, visible=lambda e: True):
    """The loops of the area around p: the smallest closed shape around it, and the closed
    shapes inside that one (holes: islands), or None."""
    best = None
    for e in sheet.query((p[0], p[1], p[0], p[1])):
        lp = closed_loop(e) if visible(e) else None
        if lp is not None and M.point_in_loops(p, [lp]):
            a = _loop_area(lp)
            if best is None or a < best[0]:
                best = (a, e, lp)
    if best is None:
        return None
    _a, outer, lp = best
    loops = [lp]
    bb = outer.bbox()
    for e in sheet.query(bb):
        if e.id == outer.id or not visible(e):
            continue
        inner = closed_loop(e)
        if inner is not None and all(M.point_in_loops(q, [lp]) for q in inner) and \
                not M.point_in_loops(p, [inner]):
            loops.append(inner)
    return loops


class HatchCmd(Command):
    """HATCH: click inside a closed shape (a closed polyline, a rectangle, a circle) to fill
    it: solid, lines at 45 degrees (ANSI31), crosshatch (ANSI37) or level lines; closed
    shapes inside it stay open (islands). Click more areas, Enter to finish. The pattern, its
    spacing and angle are remembered."""
    name, title = "HATCH", "Hatch"
    OPTIONS = [("Solid", "SOLID"), ("45 lines", "ANSI31"), ("Crosshatch", "ANSI37"),
               ("Level lines", "LINES"), ("Spacing", "SP"), ("Angle", "AN")]

    def begin(self):
        v = self.ctx
        self.pattern = getattr(v, "hatch_pattern", "ANSI31")
        self.angle = getattr(v, "hatch_angle", 0.0)
        self.spacing = getattr(v, "hatch_spacing", None) or 0.125 * v.sheet().k()
        self.asking = None
        self.made = 0
        self._prompt()

    def _prompt(self):
        what = M.HATCH_PATTERNS[self.pattern][0]
        extra = "" if self.pattern == "SOLID" else ", %s in apart, at %g degrees" % (
            _fmt(self.spacing), self.angle)
        self.ctx.prompt("Click inside a closed shape to hatch it (%s%s); Enter to finish"
                        % (what, extra), self.OPTIONS)

    def _remember(self):
        self.ctx.hatch_pattern, self.ctx.hatch_angle = self.pattern, self.angle
        self.ctx.hatch_spacing = self.spacing

    def text(self, s):
        k = s.strip().upper()
        if k in M.HATCH_PATTERNS:
            self.pattern = k
            self._remember()
            self._prompt()
            return True
        if k == "SP":
            self.asking = "spacing"
            self.ctx.prompt("Space between the lines (inches, real size)", typing=True)
            return True
        if k == "AN":
            self.asking = "angle"
            self.ctx.prompt("Angle of the pattern (degrees)", typing=True)
            return True
        return False

    def number(self, v):
        if self.asking == "spacing" and v > 0:
            self.spacing = float(v)
        elif self.asking == "angle":
            self.angle = float(v) % 180.0
        else:
            return False
        self.asking = None
        self._remember()
        self._prompt()
        return True

    def point(self, p):
        sheet = self.ctx.sheet()
        loops = boundary_at(sheet, p, lambda e: self.ctx.layer_visible(e.layer))
        if loops is None:
            self.ctx.message("No closed shape around that point: hatch fills a closed "
                             "polyline, rectangle or circle")
            return
        h = M.Hatch(loops, self.pattern, self.angle, self.spacing, layer=self.ctx.layer())
        with self.ctx.edit(self.title) as ed:
            ed.add(sheet, h)
        self.made += 1
        self.ctx.message("Hatched (%s)%s" % (M.HATCH_PATTERNS[self.pattern][0],
                                             ", %d island(s) left open" % (len(loops) - 1)
                                             if len(loops) > 1 else ""))

    def enter(self):
        if self.asking:
            self.asking = None
            self._prompt()
            return
        self.finish()


def next_balloon(project):
    """The next item number for a balloon: one more than the highest on any sheet."""
    n = 0
    for sh in project.sheets:
        for e in sh.entities.values():
            if isinstance(e, M.Leader) and e.balloon:
                try:
                    n = max(n, int(e.text.strip()))
                except ValueError:
                    pass
    return n + 1


class LeaderCmd(Command):
    """LEADER (AutoCAD's LEADER and MLEADER in one): pick the arrow's point, then where the
    line bends, Enter; then type the note, or B for a balloon with an item number (Enter
    takes the next one). Its text is paper-sized, as a dimension's."""
    name, title = "LEADER", "Leader"

    def begin(self):
        self.pts = []
        self.step = "points"
        self.ctx.prompt("Specify the arrow's point")

    def _height(self):
        return float(self.ctx.project.settings.get("dim_height", 0.1)) * self.ctx.sheet().k()

    def point(self, p):
        if self.step != "points":
            return
        self.pts.append(p)
        self.base = self.last = p
        if len(self.pts) == 1:
            self.ctx.prompt("Specify where the line goes")
        else:
            self.ctx.prompt("Next point, or Enter for the text")

    def enter(self):
        if self.step == "points":
            if len(self.pts) < 2:
                self.finish()
                return
            self.step = "text"
            self.ctx.prompt("Type the note (Enter: none), or B for a balloon", [("Balloon", "B")],
                            typing=True)
            return
        if self.step == "text":
            self._make("", False)
        elif self.step == "number":
            self._make(str(next_balloon(self.ctx.project)), True)

    def text(self, s):
        if self.step == "text":
            if s.strip().upper() == "B":
                self.step = "number"
                self.ctx.prompt("Item number: Enter for %d, or type one"
                                % next_balloon(self.ctx.project), typing=True)
                return True
            self._make(s, False)
            return True
        if self.step == "number":
            self._make(s.strip() or str(next_balloon(self.ctx.project)), True)
            return True
        return False

    def _make(self, text, balloon):
        ld = M.Leader(self.pts, text, balloon, self._height())
        with self.ctx.edit(self.title) as ed:
            if ld.layer not in self.ctx.project.layers:
                ed.layer(ld.layer, None, M.Layer(ld.layer, "#00c8c8").to_dict())
            ed.add(self.ctx.sheet(), ld)
        self.ctx.message("Leader with %s" % ("balloon %s" % text if balloon
                                             else ("note \"%s\"" % text if text else "no text")))
        self.finish()

    def preview(self, p):
        if self.step != "points" or not self.pts:
            return []
        return [M.Leader(self.pts + [p], "", False, self._height())]


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

    def _straight(self, p):
        """The end point straight across or up and down from the start, whichever way the
        point lies (rail and duct go straight: a snap off the line only sets the length)."""
        a = self.p1
        if abs(p[0] - a[0]) >= abs(p[1] - a[1]):
            return (p[0], a[1])
        return (a[0], p[1])

    def point(self, p):
        if self.p1 is None:
            self.p1 = self.base = self.last = p
            self.end_prompt()
            return
        p = self._straight(p)
        if G.dist(self.p1, p) < 1e-6:
            return
        e = self.place(self.p1, p)
        with self.ctx.edit(self.title) as ed:
            if e.layer not in self.ctx.project.layers:
                ed.layer(e.layer, None, M.Layer(e.layer).to_dict())
            ed.add(self.ctx.sheet(), e)
        self.ctx.message("%s, %s long" % (e.name(), M.fmt_inches(e.length())))
        self.finish()

    def preview(self, p):
        if self.p1 is None:
            return []
        raw = p
        p = self._straight(p)
        if G.dist(self.p1, p) < 1e-6:
            return []
        self.side_from(raw, p)
        return [self.place(self.p1, p)]

    def end_prompt(self):
        self.ctx.prompt("Specify end point, or type the length (toward the cursor)")

    def side_from(self, raw, p):
        """(where the cursor is off the line: a duct's side)"""

    def place(self, a, b):
        return self.make(a, b)


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
        # (the standard sizes as buttons too: width x depth, inches)
        self.ctx.prompt("Specify start corner (%s; or a size: width x depth, 2x3, 1.5x3, "
                        "50x75mm)" % M.size_text(*self._size()),
                        [(M.size_text(w, d), "%gx%g" % (w, d)) for w, d in M.DUCT_SIZES])

    def text(self, s):
        if s.strip().upper() == "F" and self.p1 is not None:
            self.side = -self.side
            return True
        got = parse_duct_size(s)
        if got is None or self.p1 is not None:
            return False
        self.ctx.project.settings["duct_size"] = [got[0], got[1]]
        self._prompt_start()
        return True

    def make(self, a, b):
        w, d = self._size()
        hatch = {"HATCH": "1"} if self.ctx.project.settings.get("duct_hatch") else None
        return M.Duct(a, b, "", w, d, attrs=hatch)

    # (from a corner, not its middle: the owner, 0.18, "For adding wire duct, the start point
    # needs to be at the corner, not the middle": the two points are one edge, corner to
    # corner, the duct on the side of it the cursor is on, F the other side)
    side = 1.0

    def end_prompt(self):
        self.ctx.prompt("Specify the other corner along this edge, or type the length (the "
                        "duct goes on the side the cursor is; F: the other side)",
                        [("Other side", "F")])

    def side_from(self, raw, p):
        a = self.p1
        L = G.dist(a, p)
        if L <= 1e-9:
            return
        n = (-(p[1] - a[1]) / L, (p[0] - a[0]) / L)          # (left of the way it goes)
        off = (raw[0] - a[0]) * n[0] + (raw[1] - a[1]) * n[1]
        if abs(off) > 1e-9:
            self.side = 1.0 if off > 0 else -1.0

    def place(self, a, b):
        w, _d = self._size()
        L = G.dist(a, b)
        n = (-(b[1] - a[1]) / L, (b[0] - a[0]) / L)
        k = self.side * w / 2.0
        return self.make((a[0] + n[0] * k, a[1] + n[1] * k), (b[0] + n[0] * k, b[1] + n[1] * k))


class ScootCmd(_TwoPoint):
    """SCOOT (AutoCAD Electrical's): select devices, a base point, then where to. They move
    with everything attached to them (the owner, 0.17.3: "I need to be able to scoot a motor
    and everything attached to it gets scooted with it. Same thing if I scoot a vfd"): the
    symbols wired to them and the wires between, straight across or up and down; a wire
    leaving that branch onto a bus slides along it, or stretches when the move isn't along
    it (scoot.branch_moved). O: only these devices, sliding along their own wire as before
    (across a rung, or up and down a vertical wire), the wires on their pins stretching and
    shortening, stopping short of a wire's far end or corner."""
    name, title = "SCOOT", "Scoot"
    only = False
    ACROSS = ("A wire runs through a pin of what would move, across the way it goes: scoot "
              "along that wire, or cut it at the pin first (Trim wire)")
    STRANDS = ("A wire would come off a pin: it runs on through a pin of a device (one that "
               "stays, or one that moves while the wire's far end stays). Cut it at the pin "
               "first (Trim wire), or scoot that device too")
    why = ACROSS

    def begin(self):
        from . import scoot
        sel = _selected(self.ctx)
        self.devs = scoot.devices(sel)
        self.run = None
        if not self.devs:
            # a wire's run instead: picked, then where it goes (the owner, 0.16: AutoCAD
            # Electrical's Scoot drags a wire too, the wires joined to it following)
            self.ents = []
            self.from_pt = None
            self.picking = True
            self.ctx.set_selection(set())
            self.ctx.prompt("Scoot: click the run of wire to move (or select symbols on a "
                            "wire first)")
            return
        self.ax = scoot.axis(self.devs[0])
        self.ents = self.devs
        self.from_pt = None
        self._ask_base()

    def _ask_base(self):
        self.ctx.prompt("Specify base point (%s)" % (
            "only these, along their wire" if self.only else
            "with everything attached to them"),
            [("Everything attached", "A") if self.only else ("Only these", "O")])

    def text(self, s):
        k = s.strip().upper()
        if self.devs and k in ("O", "A"):
            self.only = k == "O"
            if self.from_pt is None:
                self._ask_base()
            return True
        return False

    def _branch_delta(self, p):
        """Straight across or up and down, whichever the cursor is more."""
        dx, dy = p[0] - self.from_pt[0], p[1] - self.from_pt[1]
        return (dx, 0.0) if abs(dx) >= abs(dy) else (0.0, dy)

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
        if not self.only:
            dx, dy = self._branch_delta(p)
            sheet = self.ctx.sheet()
            got = scoot.branch_moved(sheet, self.devs, dx, dy)
            self.why = self.ACROSS
            if got is not None and scoot.strands(sheet, got, (dx, dy)):
                self.why = self.STRANDS
                return None
            return got
        d = self._slide(p)
        return [e.moved(self.ax[0] * d, self.ax[1] * d) if scoot.axis(e) == self.ax else e
                for e in self.devs]

    def apply(self, p):
        if self.only:
            d = self._slide(p)
        else:
            dx, dy = self._branch_delta(p)
            d = abs(dx) + abs(dy)
        sheet = self.ctx.sheet()
        got = self.result(p)
        if got is None:
            self.ctx.message(self.why)
            self.finish()
            return
        with self.ctx.edit(self.title) as ed:
            # (a wire squeezed to nothing between what moves and what stays goes)
            put_changed(ed, sheet, got)
        self.ctx.message("Scooted %s%s" % (M.fmt_inches(abs(d)), "" if self.only else
                                           " with everything attached (%d objects)"
                                           % len(got)))
        self.finish()

    # ---- a wire's run ----------------------------------------------------------------------
    def pick(self, p):
        w = self.ctx.pick_entity(p, M.Wire)
        if w is None:
            self.ctx.message("Click a wire")
            return
        k = min(range(len(w.points) - 1),
                key=lambda i: G.dist_to_segment(p, w.points[i], w.points[i + 1]))
        a, b = w.points[k], w.points[k + 1]
        if abs(a[0] - b[0]) > 1e-9 and abs(a[1] - b[1]) > 1e-9:
            self.ctx.message("That run is slanted: Scoot moves runs across or up and down")
            return
        self.run = (w, k)
        self.picking = False
        self.base = self.last = p
        self.ctx.prompt("Specify where the run goes (%s)" % (
            "up or down" if abs(a[1] - b[1]) < 1e-9 else "left or right"))

    def _run_moved(self, p):
        w, k = self.run
        return _run_drag(self.ctx, w, k, p)

    def point(self, p):
        if self.run is None:
            return _TwoPoint.point(self, p)
        got = self._run_moved(p)
        if not got:
            w, k = self.run
            _run_drag(self.ctx, w, k, p, say=True)
        if got:
            sheet = self.ctx.sheet()
            with self.ctx.edit(self.title) as ed:
                for e in got.values():
                    ed.change(sheet, e)
        self.finish()

    def preview(self, p):
        if self.run is None:
            if not self.devs or self.from_pt is None:
                return []
            return (self.result(p) or []) + [M.Line(self.from_pt, p)]
        return list(self._run_moved(p).values())


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


class AlignObjectsCmd(Command):
    """ALIGNOBJ: line up the selected objects (footprints, DIN rail, duct...) by an edge or
    their middles, as drawing programs' Align does: Left, Center, Right, Top, Middle or Bottom,
    then click the object to line them up with (Enter: the selection's own outer edge, or
    its middle). Each moves straight across (Left, Center, Right) or straight up and down
    (Top, Middle, Bottom); one undoable step; wires on a moved symbol's pins follow."""
    name, title = "ALIGNOBJ", "Align objects"
    selects = True
    WAYS = {"L": "left", "C": "center", "R": "right", "T": "top", "M": "middle",
            "B": "bottom"}

    def begin(self):
        self.ents = _selected(self.ctx)
        self.way = None
        if len(self.ents) < 2:
            self.ctx.message("Select two or more objects to line up")
            self.finish()
            return
        self.ctx.prompt("Line them up by", [("Left", "L"), ("Center", "C"), ("Right", "R"),
                                            ("Top", "T"), ("Middle", "M"), ("Bottom", "B")])

    def text(self, s):
        k = s.strip().upper()[:1]
        if self.way is None and k in self.WAYS:
            self.way = self.WAYS[k]
            self.picking = True
            self.ctx.prompt("Click the object to line them up with (Enter: the selection's "
                            "own %s)" % ("middle" if self.way in ("center", "middle")
                                         else "%s edge" % self.way))
            return True
        return False

    @staticmethod
    def _at(bb, way):
        """The edge or middle of a box that `way` lines up."""
        return {"left": bb[0], "right": bb[2], "center": (bb[0] + bb[2]) / 2,
                "bottom": bb[1], "top": bb[3], "middle": (bb[1] + bb[3]) / 2}[way]

    def pick(self, p):
        e = self.ctx.pick_entity(p)
        if e is None:
            self.ctx.message("Click an object (Enter: line them up with the selection's "
                             "own edge)")
            return
        self._apply(e.bbox(), keep=e.id)

    def enter(self):
        if self.selecting():
            return Command.enter(self)
        if self.way is None:
            self.finish()
            return
        boxes = [e.bbox() for e in self.ents]
        x0 = min(b[0] for b in boxes)
        y0 = min(b[1] for b in boxes)
        x1 = max(b[2] for b in boxes)
        y1 = max(b[3] for b in boxes)
        self._apply((x0, y0, x1, y1))

    def _apply(self, ref, keep=None):
        target = self._at(ref, self.way)
        across = self.way in ("left", "center", "right")
        sheet = self.ctx.sheet()
        moved = 0
        with self.ctx.edit(self.title) as ed:
            for e in self.ents:
                cur = sheet.entities.get(e.id)
                if cur is None or cur.id == keep:
                    continue
                d = target - self._at(cur.bbox(), self.way)
                if abs(d) <= 1e-9:
                    continue
                ed.change(sheet, cur.moved(d, 0.0) if across else cur.moved(0.0, d))
                moved += 1
        self.ctx.message("Lined up %d object(s) by their %s" % (
            moved, self.way if self.way in ("center", "middle") else self.way + " edges"))
        self.finish()


class DistributeCmd(Command):
    """DISTRIBUTE: spread the selected objects (three or more) evenly, as drawing programs'
    Distribute does: Horizontally or Vertically, the two outermost staying where they are and
    the others moved straight across (or up and down) so the gaps between them are equal.
    With Snap on, each move is rounded to the snap spacing (pins stay on the grid, so wires
    still meet them; the gaps then differ by up to one snap step). One undoable step; wires on
    a moved symbol's pins follow."""
    name, title = "DISTRIBUTE", "Distribute objects"
    selects = True

    def begin(self):
        self.ents = _selected(self.ctx)
        if len(self.ents) < 3:
            self.ctx.message("Select three or more objects to spread out")
            self.finish()
            return
        self.ctx.prompt("Spread them out", [("Horizontally", "H"), ("Vertically", "V")])

    def text(self, s):
        k = s.strip().upper()[:1]
        if k not in ("H", "V"):
            return False
        self._apply(0 if k == "H" else 1)
        return True

    def _apply(self, axis):
        sheet = self.ctx.sheet()
        boxes = [(e, e.bbox()) for e in self.ents]
        # (by their middles; objects on top of each other, a hatch and its outline, in the
        # order they were drawn)
        boxes.sort(key=lambda t: ((t[1][axis] + t[1][axis + 2]) / 2, t[0].id))
        first, last = boxes[0][1], boxes[-1][1]
        sizes = sum(b[axis + 2] - b[axis] for _e, b in boxes)
        gap = ((last[axis + 2] - first[axis]) - sizes) / (len(boxes) - 1)
        snap = self.ctx.snap_spacing if getattr(self.ctx, "snap_on", False) else 0.0
        at = first[axis + 2] + gap
        moved = 0
        with self.ctx.edit(self.title) as ed:
            for e, b in boxes[1:-1]:
                d = at - b[axis]
                if snap > 0:
                    d = round(d / snap) * snap
                at += (b[axis + 2] - b[axis]) + gap
                cur = sheet.entities.get(e.id)
                if cur is None or abs(d) <= 1e-9:
                    continue
                ed.change(sheet, cur.moved(d, 0.0) if axis == 0 else cur.moved(0.0, d))
                moved += 1
        self.ctx.message("Spread %d object(s) out %s" % (
            len(boxes), "across" if axis == 0 else "up and down"))
        self.finish()


class DeleteDotCmd(Command):
    """DELDOT: click a junction dot and it goes (the wires still join there; Undo, or a click
    on the same spot again, brings it back). Keep clicking; Enter ends. A dot goes where three
    wire ends meet, or a wire ends on another wire's middle or bend (the owner, 0.16: "I need
    to be able to delete the connection dots if needed")."""
    name, title = "DELDOT", "Delete dot"

    def begin(self):
        self.picking = True
        self.ctx.set_selection(set())
        self.ctx.prompt("Click a junction dot to delete (where one was deleted: back again; "
                        "Enter to finish)")

    def pick(self, p):
        from . import wires
        sheet = self.ctx.sheet()
        r = max(10.0 / max(self.ctx.scale, 1e-9), 0.05 * sheet.k())
        # (the nearest to the click, shown or deleted: two dots side by side are each theirs)
        near = [(G.dist(q, p), 0, q) for q in wires.junctions(sheet) if G.dist(q, p) <= r]
        near += [(G.dist(q, p), 1, q) for q in sheet.no_dots
                 if G.dist(q, p) <= r and wires._dot_at(sheet, q)]
        best = min(near) if near else None
        if best is not None and best[1] == 0:
            q = best[2]
            with self.ctx.edit(self.title) as ed:
                ed.sheet_meta(sheet, no_dots=[list(t) for t in sheet.no_dots] + [list(q)])
            self.ctx.message("Dot deleted (the wires still join there)")
        elif best is not None:
            q = best[2]
            with self.ctx.edit("Restore dot") as ed:
                ed.sheet_meta(sheet, no_dots=[list(t) for t in sheet.no_dots if tuple(t) != q])
            self.ctx.message("Dot back")
        else:
            self.ctx.message("No junction dot there")


class WireLabelCmd(Command):
    """WIRELABEL (Wire number label): click a wire where its number shows again, as many as
    you like (the owner, 0.17.2: "On long stretches of wire, I need to be able to insert wire
    labels in multiple places ... also manually. But don't freeze the wire number"). Each
    shows the wire's own number, whatever it becomes (kept as a place along the wire, not as
    text); R then a click takes the nearest one off; U undoes the last."""
    name, title = "WIRELABEL", "Wire number label"

    def begin(self):
        self.picking = True
        self.removing = False
        self.done = 0
        self.ctx.set_selection(set())
        self._ask()

    def _ask(self):
        self.ctx.prompt("Click a wire where its number %s (Enter to finish)" %
                        ("label goes off" if self.removing else "shows again"),
                        [("Remove", "R"), ("Undo", "U")])

    def pick(self, p):
        sheet = self.ctx.sheet()
        w = _pick_wire(self.ctx, p)
        if w is None:
            self.ctx.message("Click a wire")
            return
        t = w.length_at(p)
        if self.removing:
            if not w.labels:
                self.ctx.message("That wire has no label placed by hand")
                return
            near = min(w.labels, key=lambda x: abs(x - t))
            new = [x for x in w.labels if x != near]
        else:
            new = w.labels + [t]
        with self.ctx.edit(self.title) as ed:
            ed.change(sheet, w.copy(labels=new))
        self.done += 1

    def text(self, s):
        k = s.strip().upper()
        if k == "R":
            self.removing = not self.removing
            self._ask()
            return True
        if k == "U":
            if self.done:
                self.ctx.project.undo()
                self.done -= 1
            return True
        return False

    def enter(self):
        self.finish()


class SignalArrowsCmd(Command):
    """SIGARROW (Source/destination arrows, as AutoCAD Electrical's signal arrows; the owner,
    0.18: "I would like source and destination arrows for wire cross references"): click the
    end of a wire where it leaves (a Source arrow goes there), then the end where it arrives,
    on this sheet or another (go to it in the Sheets panel: the command goes on), and a
    Destination arrow goes there. They are a pair of one new name: one wire, the source's
    number on both, each showing the wire's number and the other's place (2046 / 7-A2). Goes
    on with the next pair until Enter or Esc."""
    name, title = "SIGARROW", "Source/destination arrows"
    across_sheets = True

    def begin(self):
        self.src = None
        self.done = 0
        self.ctx.set_selection(set())
        self._ask()

    def _ask(self):
        if self.src is None:
            self.ctx.prompt("Click the end of the wire where it leaves (the source arrow goes "
                            "there); Enter to finish")
        else:
            self.ctx.prompt("Click the end of the wire where it arrives (the destination "
                            "arrow), here or on another sheet (Sheets panel); Esc cancels")

    def _end(self, p):
        from . import wirenums
        from .wires import connects_at
        w = _pick_wire(self.ctx, p)
        if w is None:
            self.ctx.message("Click a wire near its end")
            return None
        got = wirenums.wire_end(self.ctx.sheet(), w, p)
        if connects_at(got[0], got[1], exclude=w.id):
            self.ctx.message("That end is connected to something: click the open end of a "
                             "wire (the end where it leaves or arrives)")
            return None
        return got, w

    def pick(self, p):
        from . import wirenums
        got = self._end(p)
        if got is None:
            return
        (end, w) = got
        project = self.ctx.project
        if self.src is None:
            self.src = (end, w)
            self.ctx.message("Source: wire %s. Now the end where it arrives" % (w.num or "?"))
            self._ask()
            return
        (s_end, s_w) = self.src
        a = wirenums.group_of(project, s_end[0], s_end[0].entities.get(s_w.id, s_w))
        b = wirenums.group_of(project, end[0], w)
        if a is not None and b is not None and a[0] == b[0]:
            self.ctx.message("That is the same wire: click the end of the wire it goes on to")
            return
        lib = getattr(self.ctx.window(), "library", None)
        defs = [project.blocks.get(n) or (lib.get("symbol", n) if lib is not None else None)
                for n in wirenums.ARROWS]
        if None in defs:
            self.ctx.message("The Source arrow and Destination arrow symbols aren't in the "
                             "library")
            self.finish()
            return
        src_sheet = s_end[0]
        num = src_sheet.entities[s_w.id].num if s_w.id in src_sheet.entities else None
        with self.ctx.edit(self.title) as ed:
            name = wirenums.cross_reference(ed, project, s_end, end, defs[0], defs[1], True)
            wirenums.match_arrow_layers(ed, project, name)
            if num and wirenums.enabled(project):
                wirenums.sync(ed, project)
                cur = src_sheet.entities[s_w.id]
                if cur.num != num:
                    # (the destination takes the source's number: numbering would give the
                    # pair the number of the sheet first in order)
                    wirenums.set_number(ed, project, src_sheet, cur, num, True)
        self.done += 1
        self.ctx.message("Arrows %s: wire %s from %s to %s (Undo takes them back)" % (
            name, num or "?", project.zone_text(src_sheet, *s_end[1]) or "?",
            project.zone_text(end[0], *end[1]) or "?"))
        self.src = None
        self._ask()

    def enter(self):
        self.finish()


class NumberSourceCmd(Command):
    """NUMSOURCE (Numbering source): click the symbol the sheet's wires start from (a
    disconnect, say): numbering on this sheet then follows the wires from it (Sheet properties:
    Along the wires; tags.wire_walk), as the owner asked, 0.18: "Can it track my bus?". One
    step; Renumber sheet or Update numbers then numbers it that way."""
    name, title = "NUMSOURCE", "Numbering source"

    def begin(self):
        self.ctx.set_selection(set())
        self.ctx.prompt("Click the symbol the wires start from (a disconnect, say)")

    def pick(self, p):
        e = self.ctx.pick_entity(p, M.Insert)
        if e is None or not e.pin_points():
            self.ctx.message("Click a symbol with pins")
            return
        with self.ctx.edit(self.title) as ed:
            ed.sheet_meta(self.ctx.sheet(), number_order="wires", number_from=e.id)
        self.ctx.message("Numbering on this sheet follows the wires from %s: Renumber sheet or "
                         "Update numbers numbers it so" % (e.attrs.get("TAG") or e.block))
        self.finish()


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


def wire_gauge(text):
    """A gauge typed for Wire size, as kept ("12", "1/0", "250 kcmil"), or None when it isn't
    one: 0000 to 40 AWG, 1/0 to 4/0, or kcmil (MCM) sizes."""
    import re
    t = " ".join(str(text or "").strip().upper().split())
    if t.endswith("AWG"):
        t = t[:-3].strip()
    m = re.fullmatch(r"(\d{2,4})\s*(KCMIL|MCM)", t)
    if m:
        return "%s kcmil" % int(m.group(1))
    m = re.fullmatch(r"([1-4])/0", t)
    if m:
        return t
    if re.fullmatch(r"\d{1,2}", t) and 0 < int(t) <= 40:
        return str(int(t))
    return None


class WireSizeCmd(Command):
    """WIRESIZE (Wire size): the selected wires, or wires clicked one by one, given a gauge
    of their own in place of their layer's (the owner, 0.18.2: "per wire, with the layer as
    default"), or back to their layer's (L). Their gauge label shows it."""
    name, title = "WIRESIZE", "Wire size"

    def begin(self):
        self.wires = [e.id for e in _selected(self.ctx) if isinstance(e, M.Wire)]
        if self.wires:
            self._ask_size()
            return
        self.picking = True
        self.ctx.set_selection(set())
        self.ctx.prompt("Click the wires to size (Enter when done)")

    def pick(self, p):
        w = _pick_wire(self.ctx, p)
        if w is None:
            self.ctx.message("Click a wire")
            return
        if w.id not in self.wires:
            self.wires.append(w.id)
            self.ctx.set_selection(set(self.wires))

    def _ask_size(self):
        self.picking = False
        sheet = self.ctx.sheet()
        ws = [sheet.entities[i] for i in self.wires if i in sheet.entities]
        own = sorted({w.awg for w in ws})
        layer = sorted({(self.ctx.project.layers.get(w.layer).awg
                         if self.ctx.project.layers.get(w.layer) else "") for w in ws})
        now = M.gauge_text(own[0]) if len(own) == 1 and own[0] else \
            ("the layer's (%s)" % (M.gauge_text(layer[0]) or "none")
             if len(own) == 1 and len(layer) == 1 else "mixed")
        self.ctx.prompt("Gauge (AWG) for %d wire(s), now %s: type it (14, 1/0, 250 kcmil), "
                        "or L for the layer's" % (len(ws), now), [("Layer's", "L")])

    def text(self, s):
        if self.picking:
            return False
        k = s.strip().upper()
        if k in ("L", "LAYER", "BYLAYER"):
            got = ""
        else:
            got = wire_gauge(s)
            if got is None:
                self.ctx.message("Not a wire gauge: type 14, 1/0 or 250 kcmil, or L for the "
                                 "layer's")
                return True
        sheet = self.ctx.sheet()
        ws = [sheet.entities[i] for i in self.wires if i in sheet.entities]
        changed = [w for w in ws if w.awg != got]
        if changed:
            with self.ctx.edit(self.title) as ed:
                for w in changed:
                    ed.change(sheet, w.copy(awg=got))
        self.ctx.message("%d wire(s): %s" % (len(ws), M.gauge_text(got) or
                                             "the layer's gauge"))
        self.ctx.set_selection(set())
        self.finish()
        return True

    def enter(self):
        if self.picking and self.wires:
            self._ask_size()
            return
        self.finish()


class WireColorLabelCmd(Command):
    """WIRECOLOR (Wire color label): the selected wires, or wires clicked one by one, write
    their insulation color in their gauge label too (12 AWG BRN), or stop (the owner, 0.18.4:
    the color "can be a toggle-able option on a per-wire basis"). On when any of them is off,
    else off."""
    name, title = "WIRECOLOR", "Wire color label"

    def begin(self):
        self.wires = [e.id for e in _selected(self.ctx) if isinstance(e, M.Wire)]
        if self.wires:
            self._apply()
            return
        self.ctx.set_selection(set())
        self.ctx.prompt("Click the wires to show or hide their color (Enter when done)")

    def pick(self, p):
        w = _pick_wire(self.ctx, p)
        if w is None:
            self.ctx.message("Click a wire")
            return
        if w.id not in self.wires:
            self.wires.append(w.id)
            self.ctx.set_selection(set(self.wires))

    def _apply(self):
        sheet = self.ctx.sheet()
        ws = [sheet.entities[i] for i in self.wires if i in sheet.entities]
        on = any(not w.show_color for w in ws)
        if ws:
            with self.ctx.edit(self.title) as ed:
                for w in ws:
                    if w.show_color != on:
                        ed.change(sheet, w.copy(show_color=on))
        self.ctx.message("%d wire(s): color %s in the gauge label" % (len(ws), "shown" if on
                                                                       else "not shown"))
        self.ctx.set_selection(set())
        self.finish()

    def enter(self):
        if self.wires:
            self._apply()
            return
        self.finish()


class DimUnitsCmd(Command):
    """DIMUNITS (Dimension units): the selected dimensions, or dimensions clicked one by one,
    read decimal (12.50") or fractional (1-9/16"; the owner, 0.18.4: "change dimensions to
    decimal or fractional"). D: decimal; F: fractional, to the project's precision (1/16
    unless it says otherwise); or type the precision: 1/8, 1/16, 1/32, 1/64."""
    name, title = "DIMUNITS", "Dimension units"

    def begin(self):
        self.dims = [e.id for e in _selected(self.ctx) if isinstance(e, M.Dimension)]
        if self.dims:
            self._ask()
            return
        self.picking = True
        self.ctx.set_selection(set())
        self.ctx.prompt("Click the dimensions to change (Enter when done)")

    def pick(self, p):
        e = self.ctx.pick_entity(p, M.Dimension)
        if e is None:
            self.ctx.message("Click a dimension")
            return
        if e.id not in self.dims:
            self.dims.append(e.id)
            self.ctx.set_selection(set(self.dims))

    def _ask(self):
        self.picking = False
        sheet = self.ctx.sheet()
        now = sorted({sheet.entities[i].units for i in self.dims if i in sheet.entities})
        self.ctx.prompt("Units for %d dimension(s), now %s: D decimal, F fractional, or 1/8, "
                        "1/16, 1/32, 1/64" % (len(self.dims), now[0] if len(now) == 1
                                               else "mixed"),
                        [("Decimal", "D"), ("Fractional", "F")])

    def text(self, s):
        if self.picking:
            return False
        k = s.strip().upper()
        if k in ("D", "DECIMAL"):
            got = "decimal"
        elif k in ("F", "FRACTIONAL", "FRACTION"):
            st = M.dim_units(self.ctx.project.settings.get("dim_units", "decimal"))
            got = st if st != "decimal" else "1/16"
        elif s.strip() in M.DIM_UNITS[1:]:
            got = s.strip()
        else:
            self.ctx.message("Type D (decimal), F (fractional), or 1/8, 1/16, 1/32 or 1/64")
            return True
        sheet = self.ctx.sheet()
        ds = [sheet.entities[i] for i in self.dims if i in sheet.entities]
        changed = [d for d in ds if d.units != got]
        if changed:
            with self.ctx.edit(self.title) as ed:
                for d in changed:
                    ed.change(sheet, d.copy(units=got))
        self.ctx.message("%d dimension(s): %s" % (len(ds), "decimal" if got == "decimal"
                                                   else "fractional, to %s\"" % got))
        self.ctx.set_selection(set())
        self.finish()
        return True

    def enter(self):
        if self.picking and self.dims:
            self._ask()
            return
        self.finish()


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


class AddPinCmd(Command):
    """ADDPIN (Add pin, in a block's tab): click where a pin goes, then its name (Enter takes
    the one offered: one more than the highest number); again for the next, Enter or Esc
    ends. A pin is a text on BLOCK PINS: its insertion point is where a wire attaches."""
    name, title = "ADDPIN", "Add pin"

    def begin(self):
        from . import block_editor as BE
        self.BE = BE
        self.sess = getattr(self.ctx, "block_session", None)
        if self.sess is None:
            self.ctx.message("Add pin works in a block's tab (Edit block... opens one)")
            self.finish()
            return
        self._ask_point()

    def _offered(self):
        return self.BE.next_pin_name(self.BE.pin_names(self.ctx.project, self.sess))

    def _ask_point(self):
        self.step, self.at = "pos", None
        self.ctx.prompt("Pin location (pin %s; Enter or Esc ends)" % self._offered())

    def point(self, p):
        if self.step != "pos":
            return
        self.at = self.base = self.last = p
        self.step = "name"
        self.ctx.prompt("Pin name <%s>" % self._offered(), typing=True)

    def wants_raw_text(self):
        return self.step == "name"

    def text(self, s):
        if self.step != "name":
            return False
        name = s.strip() or self._offered()
        if name in self.BE.pin_names(self.ctx.project, self.sess):
            self.ctx.message("There's already a pin %s: type another name" % name)
            self.ctx.prompt("Pin name <%s>" % self._offered(), typing=True)
            return True
        with self.ctx.edit("Add pin") as ed:
            ed.add(self.ctx.sheet(), self.BE.pin_marker(self.sess, self.at, name))
        self.ctx.message("Pin %s added" % name)
        self._ask_point()
        return True

    def enter(self):
        if self.step == "name":
            self.text("")
        else:
            self.finish()

    def preview(self, p):
        if self.step == "pos":
            return [self.BE.pin_marker(self.sess, p, self._offered())]
        return [self.BE.pin_marker(self.sess, self.at, self._offered())]


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
    "HATCH": (HatchCmd, ["H", "BHATCH", "BH", "FILL"]),
    "MTEXT": (MTextCmd, ["MT", "T2", "NOTE"]),
    "USETITLEBLOCK": (UseTitleBlockCmd, ["USETB", "TBUSE"]),
    "LEADER": (LeaderCmd, ["LE", "LEAD", "MLEADER", "MLD", "QLEADER", "BALLOON"]),
    "DASHBOX": (DashBoxCmd, ["DB", "DBOX", "BOX"]),
    "ARRAY": (ArrayCmd, ["AR", "ARRAYRECT", "ARRAYPOLAR"]),
    "OFFSET": (OffsetCmd, ["O"]),
    "NUMBER": (NumberCmd, ["NUM", "TCOUNT"]),
    "DIMALIGNED": (DimAlignedCmd, ["DAL"]),
    "DINRAIL": (RailCmd, ["RAIL", "DR"]),
    "DUCT": (DuctCmd, ["WIREWAY", "WD", "PANDUIT"]),     # (what people call it)
    "SCOOT": (ScootCmd, ["AESCOOT"]),
    "ADDPIN": (AddPinCmd, ["PIN", "AP"]),
    "AEALIGN": (AlignDevicesCmd, ["ALIGNDEV"]),
    "DISTRIBUTE": (DistributeCmd, ["DIST"]),
    "DELDOT": (DeleteDotCmd, ["DD"]),
    "ALIGNOBJ": (AlignObjectsCmd, ["ALO"]),
    "LAYOFF": (LayerOffCmd, []),
    "LAYISO": (LayerIsoCmd, []),
    "LAYON": (LayerOnCmd, []),
    "LAYLCK": (LayerLockCmd, []),
    "LAYULK": (LayerUnlockAllCmd, []),
    "WIRECROSS": (WireCrossCmd, ["WX"]),
    "TRIMWIRE": (TrimWireCmd, ["AETRIM", "TW"]),
    "WIRELABEL": (WireLabelCmd, ["WL", "WNL"]),
    "WIRESIZE": (WireSizeCmd, ["WSZ"]),
    "DIMUNITS": (DimUnitsCmd, ["DU"]),
    "WIRECOLOR": (WireColorLabelCmd, ["WCL"]),
    "STRETCH": (StretchCmd, ["S"]),
    "NUMSOURCE": (NumberSourceCmd, ["NSRC"]),
    "SIGARROW": (SignalArrowsCmd, ["SDA", "SOURCEARROW", "XARROW"]),
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
