"""Drawing a sheet with QPainter, for the screen, PDF export and the self-test.

The painter's transform maps drawing inches (y up) to device pixels; everything here is in
drawing units. Entities are drawn as a few QPainterPaths per color, built once and kept in
chunks of ids: a change rebuilds only the chunks it touched, so editing a big sheet doesn't
rebuild every path (see Sheet.touched).

Text is drawn as glyph outlines (QPainterPath.addText), sharp at every zoom and the same on
screen and in the PDF.
"""

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (QPainterPath, QPen, QColor, QBrush, QFont, QFontMetricsF,
                           QTransform)

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


def text_path(t):
    """Outline of a Text entity in drawing units."""
    f = text_font()
    p = QPainterPath()
    p.addText(QPointF(0, 0), f, t.text)
    k = t.height / _font_cache["cap"]
    w = _font_cache["fm"].horizontalAdvance(t.text) * k
    dx = {"left": 0.0, "center": -w / 2, "right": -w}[t.align]
    tr = QTransform()
    tr.translate(t.pos[0], t.pos[1])
    tr.rotate(t.angle)
    tr.translate(dx, 0)
    tr.scale(k, -k)                 # glyphs are y-down; the drawing is y-up
    return tr.map(p)


def add_entity(path, e):
    """Add an entity's outline to a stroke path (texts go to fill paths: see _Chunk)."""
    if isinstance(e, M.Line):
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
        return q


class _Chunk:
    __slots__ = ("strokes", "fills")

    def __init__(self):
        self.strokes = {}       # rgba -> QPainterPath
        self.fills = {}


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
            if k in by_chunk:
                by_chunk[k].append(e)
        for k, ents in by_chunk.items():
            ch = _Chunk()
            self._fill_chunk(ch, ents)
            if ch.strokes or ch.fills:
                self.chunks[k] = ch
            else:
                self.chunks.pop(k, None)

    def _frame_paths(self):
        """(border lines, border texts, title block chunk): the border in the frame color,
        the title block in its own layers' colors (like any drawing)."""
        p = self.project
        s = self.sheet
        sig = (s.size, s.cols, s.rows, s.title, p.sheet_number(s), len(p.sheets),
               tuple(sorted(p.fields.items())), p.title_block.version, self._layer_sig(),
               self.pal.dark)
        if sig != self._frame_sig:
            self._frame_sig = sig
            lines, texts = QPainterPath(), QPainterPath()
            for e in border_entities(s):
                if isinstance(e, M.Text):
                    texts.addPath(text_path(e))
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
            key = self.pal.color(self.project, e).rgba()
            if isinstance(e, M.Text):
                p = ch.fills.get(key)
                if p is None:
                    p = ch.fills[key] = QPainterPath()
                    p.setFillRule(Qt.WindingFill)
                p.addPath(text_path(e))
            else:
                p = ch.strokes.get(key)
                if p is None:
                    p = ch.strokes[key] = QPainterPath()
                add_entity(p, e)

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
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(pal.frame))
        painter.drawPath(texts)
        for ch in [tb] + list(self.chunks.values()):
            painter.setBrush(Qt.NoBrush)
            for rgba, path in ch.strokes.items():
                pen = QPen(QColor.fromRgba(rgba), pen_width)
                pen.setCosmetic(pen_width == 0)
                pen.setCapStyle(Qt.RoundCap)
                pen.setJoinStyle(Qt.RoundJoin)
                painter.setPen(pen)
                painter.drawPath(path)
            painter.setPen(Qt.NoPen)
            for rgba, path in ch.fills.items():
                painter.setBrush(QBrush(QColor.fromRgba(rgba)))
                painter.drawPath(path)


def entities_path(entities):
    """(stroke path, fill path) of a few entities (selection highlight, previews)."""
    strokes, fills = QPainterPath(), QPainterPath()
    for e in entities:
        if isinstance(e, M.Text):
            fills.addPath(text_path(e))
        else:
            add_entity(strokes, e)
    return strokes, fills
