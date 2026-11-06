"""Drawing a sheet with QPainter, for the screen, PDF export and the self-test.

The painter's transform maps drawing inches (y up) to device pixels; everything here is in
drawing units. Entities are drawn as a few QPainterPaths per color, built once and kept in
chunks of ids: a change rebuilds only the chunks it touched, so editing a big sheet doesn't
rebuild every path (see Sheet.touched).

Text is kept as (placement, string) items and drawn on screen with QPainter.drawText, which
draws from Qt's cache of each letter's picture at that size: filling the outlines of a sheet's
letters, smoothed, as one path took seconds a zoom step on a sheet of notes (a minute for
4,000 multi-line notes) where drawText takes a tenth of a second. A PDF and a printout get
the glyph outlines (QPainterPath.addText), the same letters as vectors.
"""

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (QPainter, QPainterPath, QPen, QColor, QBrush, QFont, QFontMetricsF,
                           QTransform, QPaintEngine)

from . import model as M
from . import geometry as G
from .sheetframe import border_entities, title_block_entities

CHUNK = 256
FONT_PX = 100.0                 # glyphs are made at this size, then scaled to the text height
_font_cache = {}


def text_font():
    f = _font_cache.get("font")
    if f is None:
        f = QFont()
        f.setFamilies(["Arial", "Liberation Sans", "DejaVu Sans", "Helvetica"])
        f.setPixelSize(int(FONT_PX))
        f.setHintingPreference(QFont.PreferNoHinting)
        fm = QFontMetricsF(f)
        _font_cache["font"] = f
        _font_cache["fm"] = fm
        # the text height is its capital letters' height
        _font_cache["cap"] = fm.capHeight() or fm.ascent() * 0.7
    return f


def measure(text, height):
    text_font()
    return _font_cache["fm"].horizontalAdvance(text) * height / _font_cache["cap"]


def install_text_measure():
    """Let the model measure text with the font it is drawn with."""
    text_font()
    M.TEXT_MEASURE = measure


def text_transform(t):
    """Where a Text entity's glyphs (made at FONT_PX, y down, baseline at 0) go in drawing
    units."""
    text_font()
    k = t.height / _font_cache["cap"]
    dx, dy = t.offset()
    tr = QTransform()
    tr.translate(t.pos[0], t.pos[1])
    tr.rotate(t.angle)
    tr.translate(dx, dy)
    tr.scale(k, -k)                 # glyphs are y-down; the drawing is y-up
    return tr


def text_path(t):
    """Outline of a Text entity in drawing units."""
    p = QPainterPath()
    p.addText(QPointF(0, 0), text_font(), t.text)
    return text_transform(t).map(p)


def text_item(t):
    """A Text entity as kept for drawing: (placement, string)."""
    return (text_transform(t), t.text)


def draw_texts(painter, items, color, outlines):
    """Draw text items in one color: on screen with drawText (Qt's cached letters); with
    outlines (PDF, print) as filled glyph outlines."""
    if not items:
        return
    f = text_font()
    if outlines:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        for tr, text in items:
            p = QPainterPath()
            p.addText(QPointF(0, 0), f, text)
            painter.drawPath(tr.map(p))
        return
    painter.setPen(QPen(color))
    painter.setBrush(Qt.NoBrush)
    painter.setFont(f)
    base = painter.worldTransform()
    origin = QPointF(0, 0)
    for tr, text in items:
        painter.setWorldTransform(tr * base)
        painter.drawText(origin, text)
    painter.setWorldTransform(base)


def hatch_path(e):
    """A solid hatch's filled area (its loops even-odd: holes stay open), as a path that any
    fill rule fills the same (simplified)."""
    hp = QPainterPath()
    hp.setFillRule(Qt.OddEvenFill)
    for lp in e.loops:
        hp.moveTo(lp[0][0], lp[0][1])
        for q in lp[1:]:
            hp.lineTo(q[0], q[1])
        hp.closeSubpath()
    return hp.simplified()


def solid_fills(e):
    """The solid hatches an entity fills: itself, or the parts of a leader (its arrowhead)."""
    if isinstance(e, M.Hatch):
        return [e] if e.solid() else []
    if isinstance(e, (M.Insert, M.Composite)):
        return [w for w in (e.world_entities() if isinstance(e, M.Insert) else e.parts())
                if isinstance(w, M.Hatch) and w.solid()]
    return []


def add_entity(path, e):
    """Add an entity's outline to a stroke path (texts go to fill paths: see _Chunk)."""
    if isinstance(e, (M.Insert, M.Composite)):
        for w in (e.world_entities() if isinstance(e, M.Insert) else e.parts()):
            if not isinstance(w, M.Text):
                add_entity(path, w)
    elif isinstance(e, M.Line):
        path.moveTo(e.p1[0], e.p1[1])
        path.lineTo(e.p2[0], e.p2[1])
    elif isinstance(e, M.Polyline):
        pts = e.points
        if not pts:
            return
        path.moveTo(pts[0][0], pts[0][1])
        for p in pts[1:]:
            path.lineTo(p[0], p[1])
        if e.closed:
            path.closeSubpath()
    elif isinstance(e, M.Circle):
        c, r = e.center, e.radius
        path.addEllipse(QPointF(c[0], c[1]), r, r)
    elif isinstance(e, M.Arc):
        pts = G.arc_points(e.center, e.radius, e.start, e.end, 3.0)
        path.moveTo(pts[0][0], pts[0][1])
        for p in pts[1:]:
            path.lineTo(p[0], p[1])


class Palette:
    def __init__(self, dark, mono=False):
        self.dark = dark
        self.mono = mono            # every object in the ink color (printing black on white)
        self.ink = QColor("#f0f0f0") if dark else QColor("#000000")
        self.paper = QColor("#000000") if dark else QColor("#ffffff")
        self.backdrop = QColor("#2d2d30") if dark else QColor("#9a9da3")
        self.frame = QColor("#9a9a9a") if dark else QColor("#000000")
        self.select = QColor("#3399ff")
        self.grid = QColor(255, 255, 255, 38) if dark else QColor(0, 0, 0, 30)

    def area(self, rgba):
        """A filled area's color: its own, or light gray when printing black on white (a
        solid black fill would hide the parts' outlines and texts)."""
        return QColor("#c8c8c8").rgba() if self.mono else rgba

    def color(self, project, e):
        if self.mono:
            return self.ink
        c = e.color if e.color is not None else project.layer_color(e.layer)
        if c in (None, M.ADAPTIVE):
            return self.ink
        q = QColor(c)
        if not q.isValid():
            return self.ink
        if not self.dark and q.lightness() > 215:   # white-ish on white paper: draw dark
            return self.ink
        if self.dark and q.lightness() < 40:        # black-ish on the black drawing: light
            return self.ink                         # (as AutoCAD's color 7; it prints black)
        return q


class _Chunk:
    __slots__ = ("strokes", "fills", "areas", "texts")

    def __init__(self):
        self.strokes = {}       # rgba -> QPainterPath
        self.fills = {}         # (leaders' arrowheads)
        self.areas = {}         # (solid hatches: drawn first, under the lines, as AutoCAD's)
        self.texts = {}         # rgba -> [(placement, string)] (draw_texts)


class SheetRenderer:
    """Keeps one sheet's paths; call paint() with the painter set to drawing units."""

    def __init__(self, project, sheet, dark=False, mono=False):
        self.project = project
        self.sheet = sheet
        self.pal = Palette(dark, mono)
        self.chunks = {}
        self._sig = None
        self._frame = None
        self._frame_sig = None
        self._dots = None               # (sheet version, path) of the wire junction dots
        self._xrefs = None              # (references shown, path) of the cross-references

    def set_dark(self, dark):
        if dark != self.pal.dark:
            self.pal = Palette(dark)
            self.chunks.clear()
            self._sig = None
            self._frame = None

    def _layer_sig(self):
        return tuple((n, l.color, l.visible) for n, l in self.project.layers.items())

    def _refresh(self):
        s = self.sheet
        sig = (self._layer_sig(), self.pal.dark)
        if sig != self._sig:
            self._sig = sig
            self.chunks.clear()
            s.touched = set()
            keys = {eid // CHUNK for eid in s.entities}
        else:
            keys = {eid // CHUNK for eid in s.touched}
            s.touched = set()
        if not keys:
            return
        by_chunk = {k: [] for k in keys}
        for eid, e in s.entities.items():
            k = eid // CHUNK
            if k in by_chunk and not isinstance(e, M.WireCross):
                by_chunk[k].append(e)
        for k, ents in by_chunk.items():
            ch = _Chunk()
            self._fill_chunk(ch, ents)
            if ch.strokes or ch.fills or ch.areas or ch.texts:
                self.chunks[k] = ch
            else:
                self.chunks.pop(k, None)

    def _frame_paths(self):
        """(border lines, border texts, title block chunk): the border in the frame color,
        the title block in its own layers' colors (like any drawing)."""
        p = self.project
        s = self.sheet
        sig = (s.size, s.rotation, s.scale, s.scale_name, s.reserve, s.cols, s.rows,
               s.col_start, s.row_start, s.title,
               p.sheet_number(s),
               len(p.sheets),
               tuple(sorted(p.fields.items())), p.title_block.version, self._layer_sig(),
               self.pal.dark)
        if sig != self._frame_sig:
            self._frame_sig = sig
            lines, texts = QPainterPath(), []
            for e in border_entities(s):
                if isinstance(e, M.Text):
                    texts.append(text_item(e))
                else:
                    add_entity(lines, e)
            tb = _Chunk()
            if s is not p.title_block:
                self._fill_chunk(tb, title_block_entities(p, s))
            self._frame = (lines, texts, tb)
        return self._frame

    def _fill_chunk(self, ch, ents):
        layers = self.project.layers
        for e in ents:
            lay = layers.get(e.layer)
            if lay is not None and not lay.visible:
                continue
            if isinstance(e, M.Insert) and e.defn is not None and e.defn.own_colors:
                # (an imported block: each piece in its own color, as AutoCAD shows it)
                self._fill_chunk(ch, e.world_entities())
                continue
            key = self.pal.color(self.project, e).rgba()
            if isinstance(e, (M.Insert, M.Composite)):
                texts = [w for w in (e.world_entities() if isinstance(e, M.Insert)
                                     else e.parts()) if isinstance(w, M.Text)]
                solids = solid_fills(e)
                if texts:
                    ch.texts.setdefault(key, []).extend(text_item(t) for t in texts)
                if solids:
                    # a hatch's fill under the lines; a leader's arrowhead with its text
                    hatch = isinstance(e, M.Hatch)
                    box = ch.areas if hatch else ch.fills
                    k2 = self.pal.area(key) if hatch else key
                    p = box.get(k2)
                    if p is None:
                        p = box[k2] = QPainterPath()
                        p.setFillRule(Qt.WindingFill)
                    for h in solids:
                        p.addPath(hatch_path(h))
            if isinstance(e, M.Text):
                ch.texts.setdefault(key, []).append(text_item(e))
            else:
                p = ch.strokes.get(key)
                if p is None:
                    p = ch.strokes[key] = QPainterPath()
                add_entity(p, e)

    def _paint_dots(self, painter):
        """Junction dots where wires join (worked out again only when the sheet changed)."""
        s = self.sheet
        if self._dots is None or self._dots[0] != s.version:
            self._dots = (s.version, _dots_path(s))
        path = self._dots[1]
        if path.isEmpty():
            return
        color = self.pal.color(self.project, M.Wire([(0, 0), (1, 0)]))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawPath(path)

    def _paint_xrefs(self, painter, outlines):
        """Cross-references and wire numbers (worked out again only when what they show
        changed)."""
        from . import xrefs, wirenums
        shown = tuple(tuple(t) for t in xrefs.shown(self.project, self.sheet))
        nums = tuple((t.text, t.pos, t.angle, t.height)
                     for t in wirenums.labels(self.project, self.sheet))
        if self._xrefs is None or self._xrefs[0] != (shown, nums):
            items = [text_item(M.Text((x, y), t, h, 0.0, "center")) for x, y, t, h in shown]
            items += [text_item(t) for t in wirenums.labels(self.project, self.sheet)]
            self._xrefs = ((shown, nums), items)
        draw_texts(painter, self._xrefs[1], self.pal.color(self.project, M.Text(
            (0, 0), "", 0.1, layer="SYMBOLS")), outlines)

    def paint(self, painter, pen_width=0.0, paper=True, under=None):
        """pen_width 0: cosmetic one-pixel lines (screen); a number: that width in inches
        (PDF/print). under: drawn on the paper before anything else."""
        self._refresh()
        pal = self.pal
        w, h = self.sheet.paper()
        if paper:
            painter.fillRect(QRectF(0, 0, w, h), pal.paper)
        if under is not None:
            under(painter)              # (the grid dots: under the drawing, not over it)
        lines, texts, tb = self._frame_paths()
        pen = QPen(pal.frame, pen_width)
        pen.setCosmetic(pen_width == 0)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(lines)
        outlines = pen_width != 0 or painter.device().paintEngine().type() not in (
            QPaintEngine.Raster, QPaintEngine.OpenGL2)
        draw_texts(painter, texts, pal.frame, outlines)
        self._paint_dots(painter)
        self._paint_xrefs(painter, outlines)
        smooth = painter.testRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        for ch in [tb] + list(self.chunks.values()):
            for rgba, path in ch.areas.items():         # (fills under every line)
                painter.setBrush(QBrush(QColor.fromRgba(rgba)))
                painter.drawPath(path)
        for ch in [tb] + list(self.chunks.values()):
            # on screen, one-pixel lines are drawn without smoothing, as AutoCAD does: a
            # smoothed line falling between two pixel rows would show at half strength
            if pen_width == 0:
                painter.setRenderHint(QPainter.Antialiasing, False)
            painter.setBrush(Qt.NoBrush)
            for rgba, path in ch.strokes.items():
                pen = QPen(QColor.fromRgba(rgba), pen_width)
                pen.setCosmetic(pen_width == 0)
                pen.setCapStyle(Qt.RoundCap)
                pen.setJoinStyle(Qt.RoundJoin)
                painter.setPen(pen)
                painter.drawPath(path)
            painter.setRenderHint(QPainter.Antialiasing, smooth)   # text stays smooth
            painter.setPen(Qt.NoPen)
            for rgba, path in ch.fills.items():
                painter.setBrush(QBrush(QColor.fromRgba(rgba)))
                painter.drawPath(path)
            for rgba, items in ch.texts.items():
                draw_texts(painter, items, QColor.fromRgba(rgba), outlines)
            painter.setPen(Qt.NoPen)
        self._paint_jumps(painter, pen_width)

    def _paint_jumps(self, painter, pen_width):
        """Wire crossings drawn as gaps or loops (crossings.py): the jumping wire is wiped
        across the crossing in the paper's color, the crossed wire drawn again through it, and
        a loop's half circle added."""
        from . import crossings
        jumps = crossings.jumps(self.project, self.sheet)
        if not jumps:
            return
        r = crossings.size(self.sheet)
        wire = self.pal.color(self.project, M.Wire([(0, 0), (1, 0)]))
        cosmetic = pen_width == 0
        wipe = QPen(self.pal.paper, 4 if cosmetic else pen_width * 4)
        wipe.setCosmetic(cosmetic)
        wipe.setCapStyle(Qt.FlatCap)
        ink = QPen(wire, pen_width)
        ink.setCosmetic(cosmetic)
        ink.setCapStyle(Qt.FlatCap)
        painter.setBrush(Qt.NoBrush)
        for p, u, cu, st in jumps:
            a = QPointF(p[0] - u[0] * r, p[1] - u[1] * r)
            b = QPointF(p[0] + u[0] * r, p[1] + u[1] * r)
            painter.setPen(wipe)
            painter.drawLine(a, b)
            painter.setPen(ink)
            if cu is not None:
                k = r * 1.6
                painter.drawLine(QPointF(p[0] - cu[0] * k, p[1] - cu[1] * k),
                                 QPointF(p[0] + cu[0] * k, p[1] + cu[1] * k))
            if st == "loop":
                pts = crossings.loop_points(p, u, r)
                path = QPainterPath(QPointF(*pts[0]))
                for q in pts[1:]:
                    path.lineTo(QPointF(*q))
                painter.drawPath(path)


DOT_RADIUS = 0.03


def _dots_path(sheet):
    from .wires import junctions
    path = QPainterPath()
    for x, y in junctions(sheet):
        path.addEllipse(QPointF(x, y), DOT_RADIUS, DOT_RADIUS)
    return path


def entities_path(entities):
    """(stroke path, fill path) of a few entities (selection highlight, previews)."""
    strokes, fills = QPainterPath(), QPainterPath()
    for e in entities:
        if isinstance(e, M.Text):
            fills.addPath(text_path(e))
        elif isinstance(e, M.WireCross):
            # (a mark placed by hand shows as a small circle while lit)
            strokes.addEllipse(QPointF(*e.pos), e.R, e.R)
        else:
            add_entity(strokes, e)
            if isinstance(e, (M.Insert, M.Composite)):
                for w in (e.world_entities() if isinstance(e, M.Insert) else e.parts()):
                    if isinstance(w, M.Text):
                        fills.addPath(text_path(w))
                for h in solid_fills(e):
                    fills.addPath(hatch_path(h))
    return strokes, fills


def block_pixmap(defn, size=64, dark=False):
    """A small picture of a block for the Library panel."""
    from PySide6.QtGui import QPixmap, QPainter
    pm = QPixmap(size, size)
    pal = Palette(dark)
    pm.fill(pal.paper)
    x0, y0, x1, y1 = defn.extents()
    w, h = max(x1 - x0, 1e-3), max(y1 - y0, 1e-3)
    k = (size - 8) / max(w, h)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.translate(size / 2, size / 2)
    p.scale(k, -k)
    p.translate(-(x0 + x1) / 2, -(y0 + y1) / 2)
    strokes, fills = entities_path(defn.entities)
    pen = QPen(pal.ink, 1.2)
    pen.setCosmetic(True)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawPath(strokes)
    p.setPen(Qt.NoPen)
    p.setBrush(pal.ink)
    p.drawPath(fills)
    pin = QPen(QColor("#2f9e44"), 4)
    pin.setCosmetic(True)
    p.setPen(pin)
    for q in defn.pins:
        p.drawPoint(QPointF(q["pos"][0], q["pos"][1]))
    p.end()
    return pm
