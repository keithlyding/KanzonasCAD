"""The drawing view: one sheet of a project, drawn with the AutoCAD feel (crosshair cursor,
pickbox, object snaps with markers, ortho, grid snap, window and crossing selection, grips,
wheel zoom at the cursor, middle-button pan) and the commands of commands.py.
"""

import math

from PySide6.QtCore import Qt, QPointF, QRectF, Signal, QTimer
from PySide6.QtGui import (QPainter, QPen, QColor, QBrush, QTransform, QPainterPath,
                           QPolygonF, QGuiApplication)
from PySide6.QtWidgets import QWidget

from . import geometry as G
from . import model as M
from . import commands as C
from .render import SheetRenderer, entities_path, Palette
from .trim import entity_intersections

APERTURE = 10           # object snap reach, pixels
PICKBOX = 5             # pick reach, pixels
GRIP = 7                # grip square, pixels
GRIP_LIMIT = 100        # grips are shown for at most this many selected objects (GRIPOBJLIMIT)
SNAP_PRIORITY = {"end": 0, "int": 0, "center": 1, "quad": 1, "insert": 0, "mid": 2}


class CadView(QWidget):
    promptChanged = Signal(str, list, bool)     # text, [(label, key)], typing
    messaged = Signal(str)
    cursorMoved = Signal(float, float, str)     # x, y, zone
    selectionChanged = Signal()
    commandChanged = Signal()
    sheetChanged = Signal()
    editTextRequested = Signal(object)
    titleBlockDoubleClicked = Signal()
    attributesRequested = Signal(object)        # a block reference double-clicked
    contextMenuWanted = Signal(object)          # global QPoint
    typed = Signal(object)                      # a key typed over the drawing (QKeyEvent)

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.host = None                # the main window: dialogs commands need (Make block)
        self.sheet_id = project.sheets[0].id
        self.renderers = {}
        self.dark = True                # black drawing area (printing is always black on white)
        self.scale = 50.0               # pixels per inch
        self.center = (8.5, 5.5)        # drawing point at the middle of the view
        self.sel = set()
        self.cmd = None
        self.last_cmd = None            # what Enter repeats
        self.cursor = None              # raw drawing point under the mouse
        self.snap = None                # (kind, point) of the object snap in use
        self.grid_on = True
        self.snap_on = True
        self.ortho_on = False
        self.osnap_on = True
        self.polar_on = False
        # crosshair: arms this % of the view long, as AutoCAD's CURSORSIZE (5 to start), or
        # across the whole view
        self.crosshair_size = 5
        self.crosshair_full = False
        self.polar_inc = 45.0           # polar tracking: every multiple of this angle...
        self.polar_extra = []           # ...and these angles too (AutoCAD's additional angles)
        self.polar = None               # (angle, distance) while the cursor is on a polar ray
        self.grid_spacing = 0.5
        self.snap_spacing = 0.125
        self.current_layer = "0"
        self.text_justify = ("left", "baseline")     # TEXT's justification (align, valign)
        self._pan = None
        # while selecting with a window or a lasso: {"start", "pressed" (the button is still
        # down from the first click), "lasso" (points, once dragged), "crossing"}
        self._window = None
        self._preview = set()           # what the window or lasso would select now
        # pressing on a selected object: {"start", "ents", "moved"} until the button is let go
        # (dragged: the selection moves, or with Ctrl a copy goes, where it is dropped)
        self._drag = None
        self._hover = None
        self._hot_grip = None
        self._sel_cache = None
        self._prompt = ("", [], False)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.BlankCursor)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setMinimumSize(200, 150)
        project.listeners.append(self._project_changed)
        self.idle_prompt()
        QTimer.singleShot(0, lambda: self.zoom("sheet"))

    # ---- context the commands use ----------------------------------------------------------
    def sheet(self):
        s = self.project.sheet_by_id(self.sheet_id)
        if s is None:
            s = self.project.sheets[0]
            self.sheet_id = s.id
        return s

    def selection(self):
        return set(self.sel)

    def set_selection(self, ids):
        self.sel = set(ids)
        self._sel_cache = None
        self.selectionChanged.emit()
        self.update()

    def prompt(self, text, options=(), typing=False):
        self._prompt = (text, list(options), typing)
        self.promptChanged.emit(text, list(options), typing)

    def message(self, text):
        self.messaged.emit(text)

    def idle_prompt(self):
        self.prompt("", [], False)

    def edit(self, name):
        return self.project.edit(name)

    def layer(self):
        if self.current_layer not in self.project.layers:
            self.current_layer = "0"
            self.project.ensure_layer("0")
        return self.current_layer

    def text_height(self):
        """New text's height: the project's (Project properties; TEXT's height prompt sets it
        too, as AutoCAD's TEXTSIZE)."""
        return float(self.project.settings["text_height"])

    def set_text_height(self, v):
        self.project.settings["text_height"] = float(v)

    def cursor_point(self):
        return self.cursor

    def layer_visible(self, name):
        lay = self.project.layers.get(name)
        return lay is None or lay.visible

    def layer_locked(self, name):
        lay = self.project.layers.get(name)
        return lay is not None and lay.locked

    def undo(self):
        self.project.undo()

    def done(self, cmd):
        if self.cmd is cmd:
            self.cmd = None
            if cmd.repeatable:
                self.last_cmd = type(cmd)
            self.idle_prompt()
            self.commandChanged.emit()
            self.update()

    # ---- commands --------------------------------------------------------------------------
    def run(self, cls, *args):
        """Start a command (cancelling the one in progress)."""
        if self.cmd is not None:
            self.cancel()
        self._window = None
        self.cmd = cls(self, *args)
        self.commandChanged.emit()
        self.messaged.emit(self.cmd.title.upper())
        self.cmd.start()
        self.update()
        return self.cmd

    def run_name(self, text):
        cls = C.lookup(text)
        if cls is None:
            return False
        self.run(cls)
        return True

    def cancel(self):
        if self.cmd is not None:
            cmd = self.cmd
            cmd.cancel()
            if self.cmd is cmd:         # a command that didn't end itself
                self.done(cmd)
            self.messaged.emit("*Cancel*")
        self._drag = None
        self._window = None
        self._preview = set()
        self.update()

    def enter(self):
        """Enter (or Space, or a right-click in a command): finish the step, or repeat the
        last command when idle."""
        if self.cmd is not None:
            self.cmd.enter()
        elif self.last_cmd is not None:
            self.run(self.last_cmd)
        self.update()

    def input_text(self, text):
        """Something typed on the command line while a command runs. True when it was used."""
        cmd = self.cmd
        if cmd is None:
            return False
        raw = getattr(cmd, "wants_raw_text", lambda: False)()
        if raw:
            return cmd.text(text)
        if not text.strip():
            cmd.enter()
            return True
        if cmd.text(text):
            self.update()
            return True
        p = C.parse_point(text, cmd.last)
        if p is not None and not cmd.selecting() and not cmd.picking:
            cmd.point(p)
            self.update()
            return True
        v = C.parse_number(text)
        if v is not None:
            if cmd.number(v):
                self.update()
                return True
            if cmd.base is not None and self.cursor is not None:
                # direct distance entry: that far toward the cursor
                # (toward the cursor as ortho or polar tracking aims it)
                aim = self.resolve(self.cursor)
                if G.dist(cmd.base, aim) > 1e-12:
                    cmd.point(G.polar(cmd.base, v, G.angle_of(cmd.base, aim)))
                    self.update()
                    return True
        return False

    # ---- sheets ----------------------------------------------------------------------------
    def show_sheet(self, sheet_id):
        if sheet_id == self.sheet_id:
            return
        self.cancel()
        self.sel = set()
        self._sel_cache = None
        self.sheet_id = sheet_id
        self.zoom("sheet")
        self.selectionChanged.emit()
        self.sheetChanged.emit()

    def renderer(self):
        s = self.sheet()
        r = self.renderers.get(s.id)
        if r is None or r.sheet is not s:
            r = self.renderers[s.id] = SheetRenderer(self.project, s, self.dark)
        r.set_dark(self.dark)
        return r

    def set_dark(self, dark):
        self.dark = bool(dark)
        self.update()

    def _project_changed(self):
        s = self.project.sheet_by_id(self.sheet_id)
        if s is None:
            self.sheet_id = self.project.sheets[0].id
            self.sheetChanged.emit()
        ents = self.sheet().entities
        gone = {i for i in self.sel if i not in ents}
        if gone:
            self.sel -= gone
            self.selectionChanged.emit()
        self._sel_cache = None
        self.update()

    # ---- transform -------------------------------------------------------------------------
    def transform(self):
        t = QTransform()
        t.translate(self.width() / 2, self.height() / 2)
        t.scale(self.scale, -self.scale)
        t.translate(-self.center[0], -self.center[1])
        return t

    def to_world(self, pos):
        x = (pos.x() - self.width() / 2) / self.scale + self.center[0]
        y = -(pos.y() - self.height() / 2) / self.scale + self.center[1]
        return (x, y)

    def to_screen(self, p):
        return QPointF((p[0] - self.center[0]) * self.scale + self.width() / 2,
                       -(p[1] - self.center[1]) * self.scale + self.height() / 2)

    def zoom(self, how):
        s = self.sheet()
        if how in ("sheet", "extents"):
            if how == "extents":
                bb = s.extents()
                if bb is None:
                    w, h = s.paper()
                    bb = (0, 0, w, h)
            else:
                w, h = s.paper()
                bb = (0, 0, w, h)
            bw, bh = max(bb[2] - bb[0], 1e-3), max(bb[3] - bb[1], 1e-3)
            vw, vh = max(self.width(), 100), max(self.height(), 100)
            self.scale = max(1e-3, min(vw / bw, vh / bh) * 0.94)
            self.center = ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)
        elif how == "in":
            self.zoom_at(1.5, None)
        elif how == "out":
            self.zoom_at(1 / 1.5, None)
        self.update()

    def zoom_at(self, factor, pos):
        new = min(max(self.scale * factor, 2.0), 50000.0)
        if pos is None:
            self.scale = new
        else:
            before = self.to_world(pos)
            self.scale = new
            after = self.to_world(pos)
            self.center = (self.center[0] + before[0] - after[0],
                           self.center[1] + before[1] - after[1])
        self.update()

    # ---- picking and snapping --------------------------------------------------------------
    def _near(self, p, px):
        r = px / self.scale
        return (p[0] - r, p[1] - r, p[0] + r, p[1] + r), r

    def pick_entity(self, p):
        """The visible, unlocked entity nearest p within the pickbox."""
        rect, r = self._near(p, PICKBOX)
        best, bd = None, None
        for e in self.sheet().query(rect):
            if not self.layer_visible(e.layer) or self.layer_locked(e.layer):
                continue
            d = e.distance(p)
            if d <= r and (bd is None or d < bd):
                best, bd = e, d
        return best

    def object_snap(self, p):
        """(kind, point) of the nearest snap point within the aperture, or None."""
        rect, r = self._near(p, APERTURE)
        cands = [e for e in self.sheet().query(rect) if self.layer_visible(e.layer)]
        best = None
        for e in cands:
            for kind, q in e.snap_points():
                d = G.dist(p, q)
                if d <= r:
                    key = (SNAP_PRIORITY.get(kind, 3), d)
                    if best is None or key < best[0]:
                        best = (key, kind, q)
        near = [e for e in cands if e.distance(p) <= r][:40]
        for i in range(len(near)):
            for j in range(i + 1, len(near)):
                for q in entity_intersections(near[i], near[j]):
                    d = G.dist(p, q)
                    if d <= r:
                        key = (SNAP_PRIORITY["int"], d)
                        if best is None or key < best[0]:
                            best = (key, "int", q)
        return None if best is None else (best[1], best[2])

    @staticmethod
    def _ortho(base, p):
        if abs(p[0] - base[0]) >= abs(p[1] - base[1]):
            return (p[0], base[1])
        return (base[0], p[1])

    def polar_angles(self):
        """Every angle polar tracking locks onto, degrees in [0, 360)."""
        inc = self.polar_inc
        out = set()
        if inc > 0:
            k = 0
            while k * inc < 360 - 1e-9:
                out.add(round(k * inc, 6))
                k += 1
        for a in self.polar_extra:
            out.add(round(float(a) % 360.0, 6))
        return sorted(out)

    def _polar_lock(self, base, p):
        """(point, angle, distance) when p is near a polar ray from base, else None."""
        d = G.dist(base, p)
        if d * self.scale < 4:
            return None
        ang = G.angle_of(base, p)
        best = None
        for a in self.polar_angles():
            diff = abs((ang - a + 180.0) % 360.0 - 180.0)
            off = d * math.sin(math.radians(min(diff, 90.0)))      # distance from the ray
            if diff < 90 and off * self.scale <= APERTURE and (best is None or off < best[0]):
                best = (off, a)
        if best is None:
            return None
        a = best[1]
        along = d * math.cos(math.radians(abs((ang - a + 180.0) % 360.0 - 180.0)))
        if self.snap_on:
            k = self.snap_spacing
            along = max(k, round(along / k) * k)
        return G.polar(base, along, a), a, along

    def resolve(self, p):
        """The point a click at p gives: object snap, else polar tracking or ortho, else grid
        snap."""
        self.snap = None
        self.polar = None
        cmd = self.cmd
        wants_point = cmd is not None and not cmd.selecting() and not cmd.picking
        if not wants_point:
            return p
        if self.osnap_on:
            s = self.object_snap(p)
            if s is not None:
                self.snap = s
                return s[1]
        if self.polar_on and not self.ortho_on and cmd.base is not None:
            lock = self._polar_lock(cmd.base, p)
            if lock is not None:
                self.polar = (lock[1], lock[2])
                return lock[0]
        q = p
        if self.snap_on:
            k = self.snap_spacing
            q = (round(q[0] / k) * k, round(q[1] / k) * k)
        if self.ortho_on and cmd.base is not None:
            q = self._ortho(cmd.base, q)
            if self.snap_on:
                # keep the free coordinate on the snap grid too
                k = self.snap_spacing
                if q[1] == cmd.base[1]:
                    q = (round(p[0] / k) * k, q[1])
                else:
                    q = (q[0], round(p[1] / k) * k)
        return q

    def grip_at(self, pos):
        """(entity, grip index) under the screen point, among the selected objects."""
        if not self.sel or len(self.sel) > GRIP_LIMIT:
            return None
        ents = self.sheet().entities
        half = GRIP / 2 + 2
        for i in self.sel:
            e = ents.get(i)
            if e is None or self.layer_locked(e.layer):
                continue
            for k, g in enumerate(e.grips()):
                q = self.to_screen(g)
                if abs(q.x() - pos.x()) <= half and abs(q.y() - pos.y()) <= half:
                    return e, k
        return None

    # ---- selection -------------------------------------------------------------------------
    def _window_ids(self, end, limit=None):
        """Ids the window (or lasso) would select with the cursor at end; None when more than
        limit objects would have to be checked (the preview then waits for the click)."""
        w = self._window
        lasso = w["lasso"]
        if lasso is not None and len(lasso) >= 3:
            poly = lasso + [end]
            rect = G.bbox_of(poly)
            crossing = w["crossing"]
        else:
            poly = None
            start = w["start"]
            rect = (min(start[0], end[0]), min(start[1], end[1]),
                    max(start[0], end[0]), max(start[1], end[1]))
            crossing = end[0] < start[0]        # right to left: crossing, as in AutoCAD
        cands = self.sheet().query(rect)
        if limit is not None and len(cands) > limit:
            return None
        found = set()
        for e in cands:
            if not self.layer_visible(e.layer) or self.layer_locked(e.layer):
                continue
            if poly is None:
                hit = (e.crosses(rect) or e.inside(rect)) if crossing else e.inside(rect)
            elif crossing:
                hit = G.outline_touches_polygon(e.outline(), poly)
            else:
                hit = G.bbox_inside(e.bbox(), rect) and G.outline_in_polygon(e.outline(), poly)
            if hit:
                found.add(e.id)
        return found

    def _finish_window(self, end):
        found = self._window_ids(end)
        self._window = None
        self._preview = set()
        self.set_selection(self.sel | found)

    def _drag_delta(self, d, p):
        """How far a dragged selection goes: from where it was grabbed to p, on the snap grid
        and straight across or up and down with Ortho, as a Move would."""
        s = d["start"]
        dx, dy = p[0] - s[0], p[1] - s[1]
        if self.ortho_on:
            if abs(dx) >= abs(dy):
                dy = 0.0
            else:
                dx = 0.0
        if self.snap_on:
            k = self.snap_spacing
            dx, dy = round(dx / k) * k, round(dy / k) * k
        return dx, dy

    def cursor_hint(self):
        """What a click here would do, shown on the cursor: "grip" (stretch), "move" (a
        selected object: drag it), "pick" (an object to select) or None."""
        if self._drag is not None:
            return "move"
        if self._window is not None or self.cursor is None:
            return None
        if self.cmd is None and self._hot_grip is not None:
            return "grip"
        h = self._hover
        if h is None or h.id not in self.sheet().entities:
            return None
        if self.cmd is None and h.id in self.sel:
            return "move"
        return "pick"

    def select_all(self):
        ids = {e.id for e in self.sheet().entities.values()
               if self.layer_visible(e.layer) and not self.layer_locked(e.layer)}
        self.set_selection(ids)

    # ---- mouse -----------------------------------------------------------------------------
    def mouseMoveEvent(self, e):
        pos = e.position()
        if self._pan is not None:
            start, c0 = self._pan
            self.center = (c0[0] - (pos.x() - start.x()) / self.scale,
                           c0[1] + (pos.y() - start.y()) / self.scale)
            self.update()
            return
        self.cursor = self.to_world(pos)
        pt = self.resolve(self.cursor)
        d = self._drag
        if d is not None and e.buttons() & Qt.LeftButton:
            if not d["moved"] and G.dist(self.to_screen(d["start"]).toTuple(),
                                         pos.toTuple()) > 5:
                d["moved"] = True
            self.cursorMoved.emit(self.cursor[0], self.cursor[1],
                                  self.project.zone_text(self.sheet(), *self.cursor))
            self.update()
            return
        w = self._window
        if w is not None:
            if w["pressed"] and e.buttons() & Qt.LeftButton:
                start_px = self.to_screen(w["start"])
                if w["lasso"] is None:
                    if G.dist(start_px.toTuple(), pos.toTuple()) > 5:
                        # held down and dragged: a lasso, as in AutoCAD (dragged to the
                        # right: window lasso; to the left: crossing lasso)
                        w["lasso"] = [w["start"]]
                        w["crossing"] = pos.x() < start_px.x()
                else:
                    last = self.to_screen(w["lasso"][-1])
                    if G.dist(last.toTuple(), pos.toTuple()) > 3:
                        w["lasso"].append(self.cursor)
            ids = self._window_ids(self.cursor, limit=3000)
            self._preview = ids if ids is not None else set()
        if self.cmd is None or self.cmd.selecting() or self.cmd.picking:
            self._hover = self.pick_entity(self.cursor) if self._window is None else None
            self._hot_grip = self.grip_at(pos) if self.cmd is None else None
        else:
            self._hover = None
        zone = self.project.zone_text(self.sheet(), pt[0], pt[1])
        self.cursorMoved.emit(pt[0], pt[1], zone)
        self.update()

    def mousePressEvent(self, e):
        pos = e.position()
        self.setFocus()
        if e.button() == Qt.MiddleButton:
            self._pan = (pos, self.center)
            self.setCursor(Qt.ClosedHandCursor)
            return
        p = self.to_world(pos)
        self.cursor = p
        if e.button() == Qt.RightButton:
            if self.cmd is not None:
                self.enter()
            else:
                self.contextMenuWanted.emit(e.globalPosition().toPoint())
            return
        if e.button() != Qt.LeftButton:
            return
        cmd = self.cmd
        if cmd is not None and cmd.picking:
            cmd.pick(p)
            self.update()
            return
        if cmd is not None and not cmd.selecting():
            cmd.point(self.resolve(p))
            self.update()
            return
        # idle, or a command selecting objects
        if self._window is not None:
            self._finish_window(p)          # the second click of a click-click window
            return
        if cmd is None:
            g = self.grip_at(pos)
            if g is not None:
                self.run(C.GripCmd, g[0], g[1])
                return
        ent = self.pick_entity(p)
        if ent is not None:
            if e.modifiers() & Qt.ShiftModifier:
                self.set_selection(self.sel - {ent.id})
            elif cmd is None and ent.id in self.sel:
                ents = self.sheet().entities
                self._drag = {"start": p, "moved": False,
                              "ents": [ents[i] for i in self.sel if i in ents]}
            else:
                self.set_selection(self.sel | {ent.id})
            return
        self._window = {"start": p, "pressed": True, "lasso": None, "crossing": None}
        self._preview = set()
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MiddleButton and self._pan is not None:
            self._pan = None
            self.setCursor(Qt.BlankCursor)
            return
        d = self._drag
        if e.button() == Qt.LeftButton and d is not None:
            self._drag = None
            if d["moved"]:
                dx, dy = self._drag_delta(d, self.to_world(e.position()))
                copy = bool(e.modifiers() & Qt.ControlModifier)
                if abs(dx) > 1e-12 or abs(dy) > 1e-12:
                    sheet = self.sheet()
                    with self.edit("Copy" if copy else "Move") as ed:
                        new = set()
                        for ent in d["ents"]:
                            c = ent.moved(dx, dy)
                            if copy:
                                c.id = None
                                ed.add(sheet, c)
                            else:
                                ed.change(sheet, c)
                            new.add(c.id)
                    self.set_selection(new)
                    self.messaged.emit("%s %d object(s)" % ("Copied" if copy else "Moved",
                                                            len(new)))
            self.update()
            return
        w = self._window
        if e.button() == Qt.LeftButton and w is not None and w["pressed"]:
            if w["lasso"] is not None:
                self._finish_window(self.to_world(e.position()))
            else:
                w["pressed"] = False        # a click: the window follows until the next click

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MiddleButton:
            self.zoom("extents")
            return
        if e.button() == Qt.LeftButton and self.cmd is None:
            p = self.to_world(e.position())
            ent = self.pick_entity(p)
            if isinstance(ent, M.Text):
                self._window = None
                self.editTextRequested.emit(ent)
                return
            if isinstance(ent, M.Insert):
                self._window = None
                self.attributesRequested.emit(ent)
                return
            if ent is None and self.sheet() is not self.project.title_block:
                from .sheetframe import title_block_rect
                r = title_block_rect(self.project, self.sheet())
                if r is not None and r[0] <= p[0] <= r[2] and r[1] <= p[1] <= r[3]:
                    self._window = None
                    self.titleBlockDoubleClicked.emit()
                    return
        self.mousePressEvent(e)

    def wheelEvent(self, e):
        steps = e.angleDelta().y() / 120.0
        if steps:
            self.zoom_at(1.2 ** steps, e.position())

    def leaveEvent(self, e):
        self.cursor = None
        self.update()

    # ---- keys ------------------------------------------------------------------------------
    def keyReleaseEvent(self, e):
        if e.key() == Qt.Key_Control and self._drag is not None:
            self.update()                   # the copy + goes
        super().keyReleaseEvent(e)

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key_Control and self._drag is not None:
            self.update()                   # the copy + shows
            return
        if k == Qt.Key_Escape:
            if self.cmd is not None or self._window is not None:
                self.cancel()
            else:
                self.set_selection(set())
            return
        typing = self._prompt[2]
        text = e.text()
        mods = e.modifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)
        if text and text.isprintable() and not mods and (text != " " or typing):
            self.typed.emit(e)
            return
        if k in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.enter()
            return
        if k == Qt.Key_Delete and self.cmd is None and self.sel:
            self.run(C.EraseCmd)
            return
        super().keyPressEvent(e)

    # ---- painting --------------------------------------------------------------------------
    def paintEvent(self, _e):
        p = QPainter(self)
        pal = Palette(self.dark)
        p.fillRect(self.rect(), pal.backdrop)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.save()
        p.setTransform(self.transform())
        r = self.renderer()
        r.paint(p, under=(lambda q: self._paint_grid(q, pal)) if self.grid_on else None)
        self._paint_selection(p, pal)
        cmd = self.cmd
        if cmd is not None and self.cursor is not None and not cmd.selecting() \
                and not cmd.picking:
            pt = self.resolve(self.cursor)
            prev = cmd.preview(pt)
            if prev:
                strokes, fills = entities_path(prev)
                pen = QPen(pal.select, 0)
                pen.setCosmetic(True)
                p.setPen(pen)
                p.setBrush(Qt.NoBrush)
                p.drawPath(strokes)
                p.setPen(Qt.NoPen)
                p.setBrush(pal.select)
                p.drawPath(fills)
        d = self._drag
        if d is not None and d["moved"] and self.cursor is not None:
            dx, dy = self._drag_delta(d, self.cursor)
            strokes, fills = entities_path([e.moved(dx, dy) for e in d["ents"]])
            pen = QPen(pal.select, 0)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPath(strokes)
            p.setPen(Qt.NoPen)
            p.setBrush(pal.select)
            p.drawPath(fills)
        p.restore()
        self._paint_grips(p, pal)
        self._paint_window(p)
        self._paint_snap(p)
        self._paint_polar(p)
        self._paint_crosshair(p, pal)
        p.end()

    def _paint_grid(self, p, pal):
        k = self.grid_spacing
        if k * self.scale < 8:
            return
        s = self.sheet()
        x0, y0, x1, y1 = s.frame()
        w0 = self.to_world(QPointF(0, self.height()))
        w1 = self.to_world(QPointF(self.width(), 0))
        x0, y0 = max(x0, w0[0]), max(y0, w0[1])
        x1, y1 = min(x1, w1[0]), min(y1, w1[1])
        if x0 >= x1 or y0 >= y1:
            return
        pen = QPen(pal.grid, 2.5 if k * self.scale > 30 else 1.5)
        pen.setCosmetic(True)
        p.setPen(pen)
        pts = []
        i0, i1 = int(math.ceil(x0 / k)), int(math.floor(x1 / k))
        j0, j1 = int(math.ceil(y0 / k)), int(math.floor(y1 / k))
        if (i1 - i0 + 1) * (j1 - j0 + 1) > 40000:
            return
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                pts.append(QPointF(i * k, j * k))
        p.drawPoints(QPolygonF(pts))

    def _paint_selection(self, p, pal):
        s = self.sheet()
        key = (s.version, frozenset(self.sel))
        if self._sel_cache is None or self._sel_cache[0] != key:
            ents = [s.entities[i] for i in self.sel if i in s.entities]
            self._sel_cache = (key, entities_path(ents))
        strokes, fills = self._sel_cache[1]
        pen = QPen(pal.select, 2)
        pen.setCosmetic(True)
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(strokes)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(51, 153, 255, 140))
        p.drawPath(fills)
        lit = [s.entities[i] for i in self._preview if i in s.entities]
        h = self._hover
        if h is not None and h.id in s.entities and self._window is None:
            lit.append(s.entities[h.id])
        if lit:
            self._paint_glow(p, lit)

    def _paint_glow(self, p, ents):
        """Light up what a click (or the window/lasso) would select: a soft wide halo under a
        bright, thicker line."""
        strokes, fills = entities_path(ents)
        halo = QColor(80, 170, 255, 90)
        pen = QPen(halo, 9)
        pen.setCosmetic(True)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(strokes)
        p.drawPath(fills)
        bright = QColor(150, 210, 255)
        pen = QPen(bright, 2.5)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.drawPath(strokes)
        p.setPen(Qt.NoPen)
        p.setBrush(bright)
        p.drawPath(fills)

    def _paint_grips(self, p, pal):
        if self.cmd is not None and not isinstance(self.cmd, C.GripCmd):
            return
        if not self.sel or len(self.sel) > GRIP_LIMIT:
            return
        ents = self.sheet().entities
        hot = self._hot_grip
        p.setPen(QPen(QColor("#1a1a1a"), 1))
        for i in self.sel:
            e = ents.get(i)
            if e is None:
                continue
            for k, g in enumerate(e.grips()):
                q = self.to_screen(g)
                is_hot = hot is not None and hot[0].id == e.id and hot[1] == k
                p.setBrush(QColor("#ff3030") if is_hot else QColor("#2f7bff"))
                p.drawRect(QRectF(q.x() - GRIP / 2, q.y() - GRIP / 2, GRIP, GRIP))

    def _paint_window(self, p):
        w = self._window
        if w is None or self.cursor is None:
            return
        if w["lasso"] is not None:
            poly = QPolygonF([self.to_screen(q) for q in w["lasso"] + [self.cursor]])
            crossing = w["crossing"]
        else:
            a = self.to_screen(w["start"])
            b = self.to_screen(self.cursor)
            r = QRectF(a, b).normalized()
            poly = QPolygonF([r.topLeft(), r.topRight(), r.bottomRight(), r.bottomLeft()])
            crossing = b.x() < a.x()
        if crossing:
            fill, pen = QColor(40, 180, 60, 45), QPen(QColor(40, 160, 60), 1, Qt.DashLine)
        else:
            fill, pen = QColor(40, 110, 230, 45), QPen(QColor(40, 110, 230), 1)
        p.setPen(pen)
        p.setBrush(fill)
        p.drawPolygon(poly)

    def _paint_polar(self, p):
        cmd = self.cmd
        if self.polar is None or cmd is None or cmd.base is None or self.cursor is None:
            return
        ang, dist = self.polar
        a = self.to_screen(cmd.base)
        far = self.to_screen(G.polar(cmd.base, 4 * max(self.width(), self.height()) /
                                     self.scale, ang))
        pen = QPen(QColor(60, 200, 90), 1, Qt.DashLine)
        p.setPen(pen)
        p.drawLine(a, far)
        c = self.to_screen(G.polar(cmd.base, dist, ang))
        text = "Polar: %s < %s\u00b0" % (("%.4f" % dist).rstrip("0").rstrip("."),
                                         ("%.2f" % ang).rstrip("0").rstrip("."))
        fm = p.fontMetrics()
        box = QRectF(c.x() + 14, c.y() + 14, fm.horizontalAdvance(text) + 10,
                     fm.height() + 4)
        p.setPen(QPen(QColor(90, 90, 90)))
        p.setBrush(QColor(255, 255, 225) if not self.dark else QColor(40, 40, 40))
        p.drawRect(box)
        p.setPen(QColor(0, 0, 0) if not self.dark else QColor(230, 230, 230))
        p.drawText(box, Qt.AlignCenter, text)

    def _paint_snap(self, p):
        if self.snap is None or self.cursor is None or self.cmd is None:
            return
        kind, q = self.snap
        c = self.to_screen(q)
        r = 6
        p.setPen(QPen(QColor("#e8c000"), 2))
        p.setBrush(Qt.NoBrush)
        x, y = c.x(), c.y()
        if kind == "end":
            p.drawRect(QRectF(x - r, y - r, 2 * r, 2 * r))
        elif kind == "mid":
            p.drawPolygon(QPolygonF([QPointF(x, y - r), QPointF(x + r, y + r),
                                     QPointF(x - r, y + r)]))
        elif kind == "center":
            p.drawEllipse(c, r, r)
        elif kind == "quad":
            p.drawPolygon(QPolygonF([QPointF(x, y - r), QPointF(x + r, y), QPointF(x, y + r),
                                     QPointF(x - r, y)]))
        elif kind == "int":
            p.drawLine(QPointF(x - r, y - r), QPointF(x + r, y + r))
            p.drawLine(QPointF(x - r, y + r), QPointF(x + r, y - r))
        else:
            p.drawRect(QRectF(x - r, y - r, 2 * r, 2 * r))
            p.drawLine(QPointF(x - r, y), QPointF(x + r, y))

    def _paint_crosshair(self, p, pal):
        if self.cursor is None or self._pan is not None:
            return
        cmd = self.cmd
        pt = self.resolve(self.cursor) if cmd is not None else self.cursor
        c = self.to_screen(pt)
        col = QColor("#ffffff") if self.dark else QColor("#000000")
        col.setAlpha(170)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.setPen(QPen(col, 1))
        if self.crosshair_full:
            p.drawLine(QPointF(0, c.y()), QPointF(self.width(), c.y()))
            p.drawLine(QPointF(c.x(), 0), QPointF(c.x(), self.height()))
        else:
            arm = max(8.0, self.crosshair_arm())
            p.drawLine(QPointF(c.x() - arm, c.y()), QPointF(c.x() + arm, c.y()))
            p.drawLine(QPointF(c.x(), c.y() - arm), QPointF(c.x(), c.y() + arm))
        wants_point = cmd is not None and not cmd.selecting() and not cmd.picking
        if wants_point:
            return
        hint = self.cursor_hint()
        if hint == "grip":
            # the square jumps onto the grip: a click there stretches it
            g = self._hot_grip
            c = self.to_screen(g[0].grips()[g[1]])
        box = QRectF(c.x() - PICKBOX, c.y() - PICKBOX, 2 * PICKBOX, 2 * PICKBOX)
        if hint is None:
            p.setBrush(Qt.NoBrush)
            p.drawRect(box)
            return
        # over something a click would act on: a filled, larger square
        big = box.adjusted(-2, -2, 2, 2)
        p.setPen(QPen(QColor(150, 210, 255), 1.5))
        p.setBrush(QColor(80, 170, 255, 150))
        p.drawRect(big)
        if hint in ("move", "grip"):
            self._paint_move_badge(p, QPointF(big.right() + 11, big.bottom() + 11),
                                   copy=hint == "move" and self._drag is not None
                                   and bool(QGuiApplication.keyboardModifiers()
                                            & Qt.ControlModifier))

    def crosshair_arm(self):
        """Half the crosshair's length in pixels: crosshair_size % of the view's larger side,
        as AutoCAD measures CURSORSIZE (a whole line is twice this)."""
        return max(self.width(), self.height()) * self.crosshair_size / 200.0

    def _paint_move_badge(self, p, c, copy=False):
        """A four-way arrow (and a + when Ctrl makes it a copy) beside the cursor."""
        p.setRenderHint(QPainter.Antialiasing, True)
        col = QColor(150, 210, 255)
        p.setPen(QPen(col, 1.6))
        r, h = 7.0, 3.0
        x, y = c.x(), c.y()
        p.drawLine(QPointF(x - r, y), QPointF(x + r, y))
        p.drawLine(QPointF(x, y - r), QPointF(x, y + r))
        p.setBrush(col)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            tip = QPointF(x + dx * r, y + dy * r)
            nx, ny = -dy, dx
            p.drawPolygon(QPolygonF([tip, QPointF(tip.x() - dx * h + nx * h, tip.y() - dy * h + ny * h),
                                     QPointF(tip.x() - dx * h - nx * h, tip.y() - dy * h - ny * h)]))
        if copy:
            p.setPen(QPen(QColor(120, 230, 120), 2))
            p.drawLine(QPointF(x + 10, y - 9), QPointF(x + 18, y - 9))
            p.drawLine(QPointF(x + 14, y - 13), QPointF(x + 14, y - 5))
