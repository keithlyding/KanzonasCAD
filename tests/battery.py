"""An exhaustive battery of tests, run by hand before a release (too long for every build):

    QT_QPA_PLATFORM=offscreen python tests/battery.py [OUT_FOLDER] [--ops N] [--seed S]
        [--drawing YOUR.dwg]

1. Random editing: thousands of commands (drawing, wiring, symbols, editing, wire tools,
   panel objects) with undo and redo mixed in, checking after every step that the model holds
   together (spatial index, wires, ids, JSON), every so often that a save and open gives the
   same project, and at the end that undo all the way back gives the empty project and redo
   all the way forward gives the final one.
2. Every menu command, with a project open (on a sheet and on the title block) and with none,
   any dialog it opens closed by itself: no command may raise.
3. Files: a project with every kind of object saved and opened, exported to DXF and read back,
   exported to PDF, made into a template and a new project made from it.
4. Speed on big sheets, beyond the self-test's budget: the wire tools, cleanup, Delete
   component, crossings and wire numbers at scale.
5. Pictures: PDF pages of the mixed project rendered to PNG for a person to look at.
6. A drawing as AutoCAD Electrical writes it (made here; or yours, --drawing PATH): opened,
   placed, Fit, hidden attributes, every snap and selection checked, saved, DXF out and in.
7. Windows paths: the recent files list under Windows' path rules.
8. Speed on an imported drawing: hover, snaps, a lasso and a window within the mouse budget.

Random editing also draws on sheets of every size, turn and scale, on several sheets, far from
the origin and big; drives the mouse (windows, crossings, lassos, drags, panning, the wheel);
and checks what each of those must do against every object (not the index): what a window or
lasso selects, where a snap lands, that Fit fits and the next scale doesn't, that zooming out
shows the whole sheet (tests/battery_checks.py).

How much runs (the owner, Nov 2026): every build runs it short (the Linux job: 1,000 steps);
a release that bumps the middle number (0.16, 0.17...) runs it long (3,000 steps, three seeds)
before it is published.

Writes OUT_FOLDER/battery.log (and the pictures) and exits 1 if anything failed.
"""

import json
import math
import os
import random
import re
import sys
import tempfile
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tests  # noqa: E402,F401  (settings, library and recovery in scratch folders)
from tests.util import APP, window, type_in  # noqa: E402

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QFileDialog  # noqa: E402

from kanzonascad import block_editor as BE  # noqa: E402
from kanzonascad import commands as C  # noqa: E402
from kanzonascad import model as M  # noqa: E402
from kanzonascad import geometry as G  # noqa: E402

# a tap's ending on the number it taps: -1, a or -a, and off a tap more of the other kind
# (2007-1a, 2007a1, 2007-a1a; 0.22.4), lowercase (a distribution outlet's 1006A isn't one)
TAP_END = re.compile(r"(?:-\d+|-?[a-z]+)[a-z0-9]*$")
from kanzonascad import wires, crossings, wirenums, wirelayers, fileio, templates  # noqa: E402
from kanzonascad import tags as tags_mod  # noqa: E402
from kanzonascad import xrefs as XR  # noqa: E402
from tests import battery_checks as BC  # noqa: E402


# An error raised while a view paints is reported here, with its traceback (an error in a paint
# run from the event loop has no Python caller to see it; with a painter left open on a picture
# it crashed the run with no word of what it was: 0.16's long battery, twice, under load)
PAINT_ERRORS = []


def _watch_paints():
    from kanzonascad.view import CadView
    if getattr(CadView, "_battery_watched", False):
        return
    real = CadView.paintEvent

    def paint(self, e):
        try:
            return real(self, e)
        except Exception:
            PAINT_ERRORS.append(traceback.format_exc())
            raise
    CadView.paintEvent = paint
    real_input = CadView.input_text

    def typed(self, text):
        # the mouse first where a typed point goes (when on screen) and the view painted
        # there: the command's preview and the crosshair drawn on its way, as a user sees them
        # (0.16.1: Bus failed every paint, and the mouse vanished over the page; typed points
        # never painted a command on its way)
        if self.cmd is not None and isinstance(text, str) and "," in text and "@" not in text:
            try:
                q = self.to_screen(tuple(float(c) for c in text.split(",")[:2]))
            except ValueError:
                q = None
            if q is not None and 0 <= q.x() < self.width() and 0 <= q.y() < self.height():
                from PySide6.QtCore import QPoint
                _move(self, QPoint(round(q.x()), round(q.y())))
                self.repaint()
        return real_input(self, text)
    CadView.input_text = typed
    CadView._battery_watched = True


class Log:
    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8")
        self.failures = 0

    def say(self, text):
        print(text)
        self.f.write(text + "\n")
        self.f.flush()

    def check(self, name, fn):
        t = time.perf_counter()
        seen = len(PAINT_ERRORS)
        try:
            note = fn()
            if len(PAINT_ERRORS) > seen:
                raise AssertionError("%d error(s) while painting:\n%s" % (
                    len(PAINT_ERRORS) - seen, "\n".join(PAINT_ERRORS[seen:seen + 3])))
        except Exception:                       # (a battery reports every failure, then goes on)
            self.failures += 1
            self.say("FAIL  %s (%.1f s)\n%s" % (name, time.perf_counter() - t,
                                                traceback.format_exc()))
            return
        self.say("PASS  %s (%.1f s)%s" % (name, time.perf_counter() - t,
                                         "  " + note if note else ""))


# ---- invariants ------------------------------------------------------------------------------
def blocks_known(project, sheet):
    """Every block copy on the sheet has its block in the project (saved with it): Import I/O
    list put modules on new sheets without theirs, gone once the project was opened again (the
    battery, 0.22.4, seed 44)."""
    for e in sheet.inserts():
        assert e.block in project.blocks, \
            "%s on sheet %s isn't one of the project's blocks" % (e.block, sheet.id)
    BC.CHECKED["block copies' blocks in the project"] += 1


def check_sheet(sheet):
    """The model holds together: every entity is found by the spatial index where it is, ids
    are unique and numeric, wires have two or more distinct finite points, and everything
    turns into JSON."""
    ids = list(sheet.entities)
    assert len(ids) == len(set(ids))
    for eid, e in sheet.entities.items():
        assert e.id == eid, (eid, e.id)
        x0, y0, x1, y1 = e.bbox()
        for v in (x0, y0, x1, y1):
            assert math.isfinite(v), (e.kind, e.bbox())
        found = {o.id for o in sheet.query((x0 - 1e-6, y0 - 1e-6, x1 + 1e-6, y1 + 1e-6))}
        assert eid in found, "entity %s (%s) missing from the index" % (eid, e.kind)
        if isinstance(e, M.Wire):
            assert len(e.points) >= 2, e.points
            for a, b in zip(e.points, e.points[1:]):
                assert abs(a[0] - b[0]) > 1e-9 or abs(a[1] - b[1]) > 1e-9, e.points
    json.dumps(sheet.to_dict())
    check_groups(sheet)
    # (drawing slop: wire ends that look joined but aren't)
    near = BC.near_misses(sheet)
    assert not near, "%d wire end(s) almost meet something without joining it: %s" % (
        len(near), ["%s %.2g from a %s" % (tuple(round(c, 4) for c in p), d, k)
                    for _i, p, k, d in near[:3]])
    back = BC.folds(sheet)
    assert not back, "%d wire(s) double back over themselves: %s" % (
        len(back), [tuple(round(c, 4) for c in q) for _i, q in back[:3]])


def _partition(groups):
    by = {}
    for i, r in groups.items():
        by.setdefault(r, set()).add(i)
    return sorted(sorted(g) for g in by.values())


def _number_state(p, s, w):
    """What numbering knew of wire w, for a failure's message."""
    g = wirenums.group_of(p, s, w)
    other = wirenums.taps(s, w)
    return "taps %s; tap numbers %s; own %s, same %s; its group %s" % (
        other.num if other is not None else None, wirenums.tap_mode(p), w.own_num, w.same_num,
        [(x.id, x.num, x.num_lock) for _s, x in (g[1] if g else [])][:6])


def _tap_pairs(sheet):
    return sorted((k, tuple(q)) for k, q in sheet._wire_adj_split[2].items())


def check_groups(sheet):
    """The wire groups kept up to date edit by edit are the ones worked out from scratch."""
    kept = _partition(wirenums._sheet_groups(sheet))
    saved = sheet._wire_groups, sheet._wire_adj
    sheet._wire_groups = sheet._wire_adj = None
    fresh = _partition(wirenums._sheet_groups(sheet))
    sheet._wire_groups, sheet._wire_adj = saved
    assert kept == fresh, "wire groups kept up to date differ from a fresh count"
    # (taps numbered apart, 0.18.3: their groups and the taps found, kept edit by edit too)
    kept = (_partition(wirenums._sheet_groups(sheet, True)), _tap_pairs(sheet))
    saved = sheet._wire_groups_split, sheet._wire_adj_split
    sheet._wire_groups_split = sheet._wire_adj_split = None
    fresh = (_partition(wirenums._sheet_groups(sheet, True)), _tap_pairs(sheet))
    sheet._wire_groups_split, sheet._wire_adj_split = saved
    assert kept == fresh, "taps kept up to date differ from a fresh count: %s" % (
        sorted(set(kept[1]) ^ set(fresh[1]))[:4],)
    BC.CHECKED["taps kept up to date"] += 1
    kept = (wires.junctions(sheet), sorted(crossings.found(sheet)))
    saved = (sheet._junctions, sheet._junction_state, sheet._crossings,
             sheet._crossing_state)
    sheet._junctions = sheet._junction_state = sheet._crossings = sheet._crossing_state = None
    fresh = (wires.junctions(sheet), sorted(crossings.found(sheet)))
    (sheet._junctions, sheet._junction_state, sheet._crossings,
     sheet._crossing_state) = saved
    assert kept == fresh, "junction dots or crossings kept up to date differ from a fresh count"


def norm(d):
    """A project's dict, for comparing two states: each sheet's entities in id order (undo
    puts a restored entity back at the end of the sheet's list: the same drawing)."""
    d = json.loads(json.dumps(d, sort_keys=True))
    for s in d.get("sheets", []) + ([d["title_block"]] if isinstance(d.get("title_block"),
                                                                   dict) else []):
        if isinstance(s.get("entities"), list):
            s["entities"].sort(key=lambda e: e.get("id", 0))
    # the title block is kept as a plain list of its entities: the same rule (seed 214 of the
    # per-build run: Use as title block undone and redone gave the same entities in another
    # order)
    if isinstance(d.get("title_block"), list):
        d["title_block"].sort(key=lambda e: e.get("id", 0) if isinstance(e, dict) else 0)
    return d


def sample_dxf(out):
    """A small DXF as another program writes it, with what imports must keep: a block with
    AutoCAD Electrical attributes (TAG1, MFG, CAT, DESC1), a linear dimension, multi-line
    text, a leader and a solid hatch. Made once per folder."""
    path = os.path.join(out, "sample.dxf")
    if os.path.exists(path):
        return path
    import ezdxf
    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 1
    blk = doc.blocks.new("RELAY_K")
    blk.add_lwpolyline([(0, 0), (1, 0), (1, 0.6), (0, 0.6)], close=True)
    blk.add_circle((0.5, 0.3), 0.15)
    for i, tag in enumerate(("TAG1", "MFG", "CAT", "DESC1")):
        blk.add_attdef(tag, (0, -0.15 * (i + 1)), dxfattribs={"height": 0.1})
    msp = doc.modelspace()
    ref = msp.add_blockref("RELAY_K", (1, 1))
    ref.add_auto_attribs({"TAG1": "CR9", "MFG": "AB", "CAT": "700-HA32A1", "DESC1": "RELAY"})
    ref = msp.add_blockref("RELAY_K", (3, 1), dxfattribs={"rotation": 90})
    ref.add_auto_attribs({"TAG1": "CR8", "MFG": "AB", "CAT": "700-HA32A1"})
    msp.add_linear_dim(base=(1, 2.5), p1=(1, 2), p2=(4, 2)).render()
    msp.add_mtext("FIRST LINE\\PSECOND LINE", dxfattribs={"insert": (5, 3),
                                                           "char_height": 0.12})
    msp.add_leader([(5, 1), (6, 2), (6.5, 2)])
    h = msp.add_hatch(color=1)
    h.paths.add_polyline_path([(7, 0), (8, 0), (8, 1), (7, 1)], is_closed=True)
    doc.saveas(path)
    return path


def first_difference(a, b, path="project"):
    """Where two JSON-like values first differ, for a failure message."""
    if type(a) is not type(b):
        return "%s: %r != %r" % (path, a, b)
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                return "%s.%s: %s" % (path, k, "only after" if k not in a else "only before")
            if a[k] != b[k]:
                return first_difference(a[k], b[k], "%s.%s" % (path, k))
        return "%s: the same" % path
    if isinstance(a, list):
        if len(a) != len(b):
            ids = lambda xs: [x.get("id") for x in xs if isinstance(x, dict)]
            return "%s: %d items != %d (ids only before: %s, only after: %s)" % (
                path, len(a), len(b), sorted(set(ids(a)) - set(ids(b)), key=str)[:5],
                sorted(set(ids(b)) - set(ids(a)), key=str)[:5])
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                return first_difference(x, y, "%s[%d]" % (path, i))
        return "%s: the same" % path
    return "%s: %r != %r" % (path, a, b)


def place_of(e):
    """Where an object is, for comparing a copy with its original: a block reference by its
    insertion point (its box changes with a new tag), a ladder by its rails (its box takes in
    its rung numbers, which start with its sheet's number: wider on sheet 17 than on sheet 8,
    the long battery, 0.26, seed 4982), anything else by its box."""
    if isinstance(e, M.Insert):
        return tuple(e.pos)
    if isinstance(e, M.Ladder):
        return tuple(e.a) + tuple(e.b)
    return tuple(e.bbox())


# ---- the mouse, as a person uses it -------------------------------------------------------------
def _qt():
    from PySide6.QtCore import Qt, QPoint, QPointF
    from PySide6.QtTest import QTest
    return Qt, QPoint, QPointF, QTest


def _empty_spot(v, rnd, tries=40):
    """A pixel where a press starts a window (no object, no grip under it), or None."""
    Qt, QPoint, QPointF, QTest = _qt()
    for _i in range(tries):
        q = QPoint(rnd.randint(5, v.width() - 5), rnd.randint(5, v.height() - 5))
        if v.pick_entity(v.to_world(QPointF(q))) is None and v.grip_at(QPointF(q)) is None:
            return q
    return None


def _send(v, kind, pos, button, buttons, mods=None):
    """A mouse event as the system sends one (with the buttons held: QTest's moves don't
    always say); mods: the keys held (none)."""
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QMouseEvent
    kinds = {"press": QEvent.MouseButtonPress, "move": QEvent.MouseMove,
             "release": QEvent.MouseButtonRelease}
    pos = QPointF(pos)
    APP.sendEvent(v, QMouseEvent(kinds[kind], pos, v.mapToGlobal(pos), button, buttons,
                                 _qt()[0].NoModifier if mods is None else mods))


def _click(v, q, mods=None):
    """A left click at pixel q, keys mods held (Shift: taken out of the selection)."""
    Qt = _qt()[0]
    _send(v, "move", q, Qt.NoButton, Qt.NoButton, mods)
    _send(v, "press", q, Qt.LeftButton, Qt.LeftButton, mods)
    _send(v, "release", q, Qt.LeftButton, Qt.NoButton, mods)
    APP.processEvents()


def _spot(v, e):
    """A pixel on the screen where a click picks e (no grip there), or None."""
    Qt, QPoint, QPointF, QTest = _qt()
    bb = e.bbox()
    a, b = v.to_screen((bb[0], bb[3])), v.to_screen((bb[2], bb[1]))
    for i in range(1, 12):
        for j in range(1, 12):
            q = QPointF(a.x() + (b.x() - a.x()) * i / 12, a.y() + (b.y() - a.y()) * j / 12)
            if not (2 <= q.x() <= v.width() - 2 and 2 <= q.y() <= v.height() - 2):
                continue
            got = v.pick_entity(v.to_world(q))
            if got is not None and got.id == e.id and v.grip_at(q) is None:
                return q
    return None


def trace_last_picked(p, s, sel, picks):
    """What Trace must list for the selection sel made by picks (the ids each pick added,
    oldest first), as the owner chose (Nov 2026, "Last one picked"): in the newest pick holding
    a device or a wire (still selected), its device, or else its wire, nearest the top left
    corner of all that pick added; with no device or wire selected, the same among the rest
    of what stands for something. A device is a symbol whose subject isn't a wire (an arrow on
    a wire is the wire)."""
    from kanzonascad import where_used as WU
    rest = None
    for ids in reversed(picks):
        mine = [s.entities[i] for i in sorted(ids) if i in sel and i in s.entities]
        ranked = []
        for x in mine:
            sub = WU.subject_of(p, s, x)
            if sub is not None:
                ranked.append((1 if sub[0] == "wire" else 0 if isinstance(x, M.Insert)
                               else 2, x))
        if not ranked:
            continue
        r0 = min(r for r, _x in ranked)
        left = min(x.bbox()[0] for x in mine)
        top = max(x.bbox()[3] for x in mine)
        best = min((x for r, x in ranked if r == r0), key=lambda x: (
            math.hypot(x.bbox()[0] - left, x.bbox()[3] - top), x.id))
        if r0 < 2:
            return best
        if rest is None:
            rest = best
    return rest


def _press(v, q, button=None):
    Qt = _qt()[0]
    button = Qt.LeftButton if button is None else button
    _send(v, "move", q, Qt.NoButton, Qt.NoButton)
    _send(v, "press", q, button, button)


def _move(v, q, held=None):
    Qt = _qt()[0]
    _send(v, "move", q, Qt.NoButton, Qt.NoButton if held is None else held)
    APP.processEvents()


def _release(v, q, button=None):
    Qt = _qt()[0]
    button = Qt.LeftButton if button is None else button
    _send(v, "release", q, button, Qt.NoButton)
    APP.processEvents()


def _drag_path(v, a, b, steps=24, button=None):
    Qt, QPoint, QPointF, QTest = _qt()
    button = Qt.LeftButton if button is None else button
    _press(v, a, button)
    for i in range(1, steps + 1):
        _move(v, QPoint(round(a.x() + (b.x() - a.x()) * i / steps),
                        round(a.y() + (b.y() - a.y()) * i / steps)), button)
    _release(v, b, button)


def mouse_window(v, rnd, click_click=False):
    """A window or crossing dragged (or clicked corner to corner) with the mouse selects what
    every object, checked one by one, says it must."""
    Qt, QPoint, QPointF, QTest = _qt()
    if v.cmd is not None:
        v.cancel()
    v.set_selection(set())
    APP.processEvents()
    a = _empty_spot(v, rnd)
    if a is None:
        return
    b = QPoint(rnd.randint(5, v.width() - 5), rnd.randint(5, v.height() - 5))
    if abs(b.x() - a.x()) < 8:
        return
    wa, wb = v.to_world(QPointF(a)), v.to_world(QPointF(b))
    want = BC.expected_window(v, wa, wb)
    if click_click:
        _press(v, a)
        _release(v, a)
        _move(v, b)
        assert v._window is not None, "a click on an empty spot didn't start a window"
        _press(v, b)
        _release(v, b)
    else:
        _drag_path(v, a, b)
    got = v.selection()
    assert got == want, "%s %s selected %d, not %d (extra %s, missing %s)" % (
        "click-click" if click_click else "dragged",
        "crossing" if wb[0] < wa[0] else "window", len(got), len(want),
        sorted(got - want)[:5], sorted(want - got)[:5])
    BC.CHECKED["click-click window" if click_click else "dragged window"] += 1
    v.set_selection(set())


def mouse_blank_press(v, rnd):
    """A press where nothing is drawn (no pixel of any object within the pickbox) starts a
    window, as in AutoCAD; only a text's box picks the text (the owner: "I was clicking in a
    hatch... in Autocad, it let me draw a select rectangle from the same spot")."""
    Qt, QPoint, QPointF, QTest = _qt()
    if v.cmd is not None:
        v.cancel()
    v.set_selection(set())
    APP.processEvents()
    grid = v.grid_on
    v.grid_on = False
    hatches = [e for e in v.sheet().entities.values() if isinstance(e, M.Hatch)
               and not e.solid() and BC.selectable(v, e)]
    if hatches and rnd.random() < 0.5:
        # (inside a hatch, zoomed in until the gaps between its lines are wider than the pickbox
        # each side: where the owner pressed)
        h = rnd.choice(hatches)
        b = h.bbox()
        v.scale = max(v.scale, 40.0 / max(h.spacing, 1e-6))
        v.center = (rnd.uniform(b[0], b[2]), rnd.uniform(b[1], b[3]))
        v.update()
    try:
        q = BC.blank_spot(v, rnd)
        if q is None:
            return
        _blank_press_at(v, q)
    finally:
        v.grid_on = grid
        v.update()


def _blank_press_at(v, q):
    Qt, QPoint, QPointF, QTest = _qt()
    from kanzonascad.view import PICKBOX
    wp = v.to_world(QPointF(q))
    _press(v, q)
    started = v._window is not None
    picked = set(v.sel)
    _release(v, q)
    if v._window is not None:
        v._window = None                    # (the click's window: let it go)
        v._preview = set()
    if not started:
        r = PICKBOX / v.scale
        s = v.sheet()
        bad = [s.entities[i] for i in picked if i in s.entities
               and not BC.text_under(v, s.entities[i], wp, r)]
        assert not bad, "a press where nothing is drawn picked %s instead of starting a " \
            "window" % [e.kind + (" " + e.pattern if isinstance(e, M.Hatch) else "")
                        for e in bad[:3]]
    BC.CHECKED["press on blank"] += 1
    v.set_selection(set())
    v.update()


def mouse_lasso(v, rnd):
    """A lasso dragged round a loop selects what every object says it must (window lasso
    dragged to the right first, crossing lasso to the left)."""
    Qt, QPoint, QPointF, QTest = _qt()
    if v.cmd is not None:
        v.cancel()
    v.set_selection(set())
    a = _empty_spot(v, rnd)
    if a is None:
        return
    cx = rnd.randint(v.width() // 4, 3 * v.width() // 4)
    cy = rnd.randint(v.height() // 4, 3 * v.height() // 4)
    rx, ry = rnd.randint(60, v.width() // 3), rnd.randint(60, v.height() // 3)
    way = rnd.choice([1, -1])
    path = [a]
    for i in range(1, 25):
        t = way * 2 * math.pi * i / 24
        path.append(QPoint(int(cx + rx * math.cos(t)), int(cy + ry * math.sin(t))))
    _press(v, a)
    for q in path[1:]:
        _move(v, q, Qt.LeftButton)
    w = v._window
    if w is None:
        return
    lasso, crossing, bent = list(w["lasso"] or []), w["crossing"], w.get("bent")
    end = path[-1]
    we = v.to_world(QPointF(end))
    if lasso and len(lasso) >= 3 and bent:
        want = BC.expected_lasso(v, lasso + [we], crossing)
    else:
        want = BC.expected_window(v, v.to_world(QPointF(a)), we)
    _release(v, end)
    got = v.selection()
    assert got == want, "lasso (%s) selected %d, not %d (extra %s, missing %s)" % (
        "crossing" if crossing else "window", len(got), len(want), sorted(got - want)[:5],
        sorted(want - got)[:5])
    BC.CHECKED["lasso" if lasso and bent else "lasso as window"] += 1
    v.set_selection(set())


def mouse_drag(v, rnd):
    """Selected objects dragged by one of them move exactly as far as the mouse did (with Snap
    on, that rounded to whole snap steps)."""
    Qt, QPoint, QPointF, QTest = _qt()
    if v.cmd is not None:
        v.cancel()
    s = v.sheet()
    ents = [e for e in s.entities.values() if BC.selectable(v, e)
            and not isinstance(e, (M.WireCross,))]
    if not ents:
        return
    sel = rnd.sample(ents, min(len(ents), rnd.randint(1, 4)))
    v.set_selection({e.id for e in sel})
    APP.processEvents()
    start = None
    for e in sel:
        for line in e.outline()[:3]:
            for p0, p1 in zip(line, line[1:]):
                q = (p0[0] + (p1[0] - p0[0]) / 3, p0[1] + (p1[1] - p0[1]) / 3)
                px = v.to_screen(q)
                if not (5 < px.x() < v.width() - 5 and 5 < px.y() < v.height() - 5):
                    continue
                pp = QPoint(round(px.x()), round(px.y()))
                hit = v.pick_entity(v.to_world(QPointF(pp)))
                if hit is not None and hit.id in v.sel and v.grip_at(QPointF(pp)) is None:
                    start = pp
                    break
            if start:
                break
        if start:
            break
    if start is None:
        v.set_selection(set())
        return
    end = QPoint(min(max(5, start.x() + rnd.randint(-120, 120)), v.width() - 5),
                 min(max(5, start.y() + rnd.randint(-120, 120)), v.height() - 5))
    if abs(end.x() - start.x()) + abs(end.y() - start.y()) < 12:
        v.set_selection(set())
        return
    before = {i: s.entities[i].bbox() for i in v.sel}
    # (a contact block dragged onto or off its operator's dashed line hides or shows its tag,
    # 0.19.10, so its box changes size: its place is checked instead)
    was_at = {i: (s.entities[i].pos, s.entities[i].hidden) for i in v.sel
              if isinstance(s.entities[i], M.Insert)}
    # (a ladder dragged past another is numbered on from it, and its box takes the numbers'
    # widths: its rails are checked instead, as Move's check, seed 4401)
    rails = {i: (s.entities[i].a, s.entities[i].b) for i in v.sel
             if isinstance(s.entities[i], M.Ladder)}
    w0, w1 = v.to_world(QPointF(start)), v.to_world(QPointF(end))
    d = (w1[0] - w0[0], w1[1] - w0[1])
    # wires and symbols with pins are dragged with Snap on, as they are drawn (a freehand drag
    # can leave a wire end a hair from another: the user's doing, not the program's, and the
    # near-miss check would blame the program): then they go whole snap steps; anything else
    # freehand half the time, exactly as far as the mouse
    joins = any(isinstance(e, M.Wire) or (isinstance(e, M.Insert) and e.defn is not None and
                                          e.defn.pins) for e in sel)
    snap = joins or rnd.random() < 0.5
    was = v.snap_on
    v.snap_on = snap
    if snap:
        k = v.snap_spacing
        d = (round(d[0] / k) * k, round(d[1] / k) * k)
        if d == (0.0, 0.0):
            v.snap_on = was
            v.set_selection(set())
            return
    try:
        _drag_path(v, start, end, steps=10)
    finally:
        v.snap_on = was
    tol = 1e-6 * max(1.0, max(abs(c) for b in before.values() for c in b))
    for i, b in before.items():
        e = s.entities.get(i)
        assert e is not None, "a dragged object is gone"
        nb = e.bbox()
        if i in was_at and isinstance(e, M.Insert) and e.hidden != was_at[i][1]:
            pos, hid = was_at[i]
            assert set(e.hidden) ^ set(hid) == {"TAG"} and e.defn is not None and \
                e.defn.prefix in XR.LINKED, \
                "dragging %s changed what it shows: %r to %r" % (e.block, hid, e.hidden)
            assert all(abs(e.pos[k] - pos[k] - d[k]) <= tol + 1e-9 for k in range(2)), \
                "dragged %s by %s, it moved %s" % (e.block, d, (e.pos[0] - pos[0],
                                                                e.pos[1] - pos[1]))
            BC.CHECKED["drag: a contact block's tag on or off its dashed line"] += 1
            continue
        if i in rails:
            for q0, q1 in zip(rails[i], (e.a, e.b)):
                assert all(abs(q1[k] - q0[k] - d[k]) <= tol + 1e-9 for k in range(2)), \
                    "dragged a ladder by %s, its rails moved %s" % (d, (q1[0] - q0[0],
                                                                       q1[1] - q0[1]))
            continue
        assert all(abs(nb[k] - b[k] - d[k % 2]) <= tol + 1e-9 for k in range(4)), \
            "dragged %s by %s, it moved %s (its box %s to %s)" % (
                e.kind, d, (nb[0] - b[0], nb[1] - b[1]), b, nb)
    BC.CHECKED["drag"] += 1
    v.set_selection(set())


def mouse_pan(v, rnd):
    """Dragging with the middle button keeps the point grabbed under the mouse."""
    Qt, QPoint, QPointF, QTest = _qt()
    a = QPoint(rnd.randint(5, v.width() - 5), rnd.randint(5, v.height() - 5))
    b = QPoint(rnd.randint(5, v.width() - 5), rnd.randint(5, v.height() - 5))
    grabbed = v.to_world(QPointF(a))
    _drag_path(v, a, b, steps=8, button=Qt.MiddleButton)
    now = v.to_world(QPointF(b))
    tol = 1e-6 * max(1.0, abs(grabbed[0]) + abs(grabbed[1]))
    assert G.dist(grabbed, now) <= tol + 2.0 / v.scale, \
        "panning lost the point grabbed: %s now under %s" % (grabbed, now)
    BC.CHECKED["pan"] += 1


# ---- 1. random editing -------------------------------------------------------------------------
# Drawings kept to a realistic size (the owner's choice, Nov 2026, asked: "cap to realistic
# drawings"): sheets no bigger than 1:100 (MAX_K) and drawing within about 10,000 inches of the
# origin (FAR). Before, Fit's scale grew with the drawing and each clear spot went 20 scales
# past it, until sheets of 1:68,593 had wires 500,000 inches out, where a slanted wire's chance
# crossing left 0.001" gaps that no real drawing has. Every check is as strict as before.
FAR = 1e4
UNREAD = object()       # (a Properties panel field the battery doesn't read from the model)
MAX_K = 100.0


def random_editing(log, out, ops, seed, drawing=None):
    """drawing: a DXF, DWG or project to start from (the owner's own drawings, on their
    computer: they never go in the repository) instead of an empty project."""
    rnd = random.Random(seed)
    crnd = random.Random(seed * 7919 + 1)
    BC.CHECKED.clear()           # (the checks' own: the steps stay the same)
    win, v = window()
    if drawing:
        closer = DialogCloser() if CLOSER is None else None
        try:
            win.open_path(drawing)
        finally:
            if closer is not None:
                closer.stop()
        APP.processEvents()
        v = win.view()
    v.osnap_on = v.snap_on = v.polar_on = v.ortho_on = False
    p = v.project
    s = v.sheet()
    # where and how big the steps draw: near the origin at first; Far drawing moves it (an
    # imported drawing is far from the origin and big: up to 0.15.6 a window around one found
    # only its lower left 32", and the battery, drawing within 15" of the origin, never saw it)
    world = {"o": (0.0, 0.0), "k": 1.0}
    dump_at = int(os.environ["BATTERY_DUMP_AT"]) if os.environ.get("BATTERY_DUMP_AT") else None
    lib = win.library
    syms = ["Contact NO", "Contact NC", "Relay coil", "Pushbutton NO", "Pushbutton NC",
            "Pilot light", "Fuse", "Circuit breaker 1-pole", "Terminal", "Overload contact NC",
            "Disconnect 3-pole", "Fuses 3-pole", "Circuit breaker 3-pole",
            "Fused disconnect 3-pole", "Starter 3-pole", "Drive control terminals",
            # (0.19: PLC I/O modules drawn whole, a terminal a rung)
            "1734-IB8 module", "1734-OE4C module", "PLC digital output module, 16 points",
            # (0.19.1: IN/RTN channels; a module over two sheets, its continued piece a part
            # of it as a contact of its coil)
            "PLC analog input module, 4 channels IN/RTN",
            "PLC digital input module, 16 points, points 0-7",
            "PLC digital input module, points 8-15 continued",
            # (0.29: IEC symbols, and the Allen-Bradley ones)
            "Relay coil (IEC)", "Contact NO (IEC)", "Contact NC (IEC)",
            "Circuit breaker 3-pole (IEC)", "Motor protection circuit breaker 3-pole",
            "Overload relay, electronic 3-pole", "Selector switch 3-position",
            "Selector switch 3-position contact, closed right", "1769-IF4 module"]
    syms = [n for n in syms if lib.get("symbol", n) is not None]
    start = norm(p.to_dict())
    counts = {}
    errors = []
    sample = sample_dxf(out)
    kinds = set()

    def pt():
        # on a 1/4" grid, mostly on a few rungs so things meet (moved and spread by `world`)
        if rnd.random() < 0.6:
            q = (rnd.randint(4, 60) * 0.25, rnd.choice([2, 3, 4, 5, 6, 7, 8]) * 1.0)
        else:
            q = (rnd.randint(4, 60) * 0.25, rnd.randint(4, 40) * 0.25)
        o, k = world["o"], world["k"]
        return (o[0] + q[0] * k, o[1] + q[1] * k)

    def fmt(q):
        return "%.12g,%.12g" % q       # (%g kept 6 digits: 12010.25 typed as 12010.2)

    def some(n=None):
        ents = list(s.entities.values())
        if not ents:
            return []
        k = n or rnd.randint(1, min(6, len(ents)))
        return rnd.sample(ents, min(k, len(ents)))

    def finish():
        if v.cmd is not None:
            v.cmd.enter()
        if v.cmd is not None:
            v.cancel()

    def op_wire():
        # (0.16: on the wire layer picked, else the sheet's default; 0.21: the default is the
        # sheet's own or the project's, and picking a layer that isn't a wire layer goes back
        # to it; worked out here from the names, not from wirelayers)
        if rnd.random() < 0.1:
            name = rnd.choice(["WIRE BROWN", "WIRE BLACK", None])
            if name is not None and name not in p.layers:
                with p.edit("layer") as ed:
                    ed.layer(name, None, M.Layer(name).to_dict())
            with p.edit("sheet wire layer") as ed:
                ed.sheet_meta(s, wire_layer=name)
            C.clear_wire_picks(v, s)
        default = s.wire_layer if s.wire_layer in p.layers else (
            p.settings.get("wire_layer") or "WIRES")
        want = default
        if rnd.random() < 0.2:
            name = rnd.choice(["WIRE BROWN", "WIRE BLACK", "0"])
            if name not in p.layers:
                with p.edit("layer") as ed:
                    ed.layer(name, None, M.Layer(name).to_dict())
            v.current_layer = name
            C.set_wire_layer(v, name)
            want = name if name.startswith("WIRE") else default
            BC.CHECKED["wire layer picked, or back to the sheet's default"] += 1
        assert C.wire_layer(v) == want, (want, C.wire_layer(v))
        before = set(s.entities)
        old_wires = [list(map(tuple, w.points)) for w in s.wires()]
        v.run(C.WireCmd)
        a = pt()
        type_in(v, fmt(a))
        for _i in range(rnd.randint(1, 3)):
            if v.cmd is None:
                break
            b = pt()
            if b != a:
                v.input_text(fmt(b))
                a = b
        finish()
        v.current_layer = "0"
        C.set_wire_layer(v, "0")
        new = [e for i, e in s.entities.items() if i not in before and isinstance(e, M.Wire)]
        # (0.21: a wire, as a bus, ends on pins but never runs through one)
        bus_clear_of_pins(new, old_wires, "wire")
        if len(new) == 1 and not wires.pins_on(s, new[0].points[0]):
            # (a wire joined to another keeps the older's layer: only a wire on its own)
            if not any(wires.connects_at(s, q, exclude=new[0].id)
                       for q in (new[0].points[0], new[0].points[-1])):
                assert new[0].layer == want, "a wire drawn on %s went on %s" % (want,
                                                                              new[0].layer)
                BC.CHECKED["wire on the current layer"] += 1
        if len(new) == 1:
            # (0.19.7: a wire starting or ending on wires of one layer takes that layer,
            # whatever the current one; worked out from the wires touching its ends now)
            w = new[0]
            touched = set()
            for q in (w.points[0], w.points[-1]):
                for o in s.wires():
                    if o.id != w.id and o.touches(q, wires.TOL):
                        touched.add(o.layer)
            if len(touched) == 1:
                assert w.layer in touched, "a wire joined to %s went on %s" % (
                    touched.pop(), w.layer)
                BC.CHECKED["wire joined takes its layer"] += 1

    def clear_of_drawing(k):
        # a spot off on its own: just past the right of what is drawn (not hundreds of times
        # the scale away: on a 1:2000 sheet that was a million inches, and the wires later
        # steps drew out to it made every step crawl, the Linux build's seed 306)
        # None when that spot is past FAR inches: each spot is 20 scales past the drawing, a Fit
        # makes the scale bigger, and the next spot farther, until (CI's long run of 0.17, seed
        # 3151: a 1:259,482,614 sheet) the spot was 13 billion inches out, where doubles are
        # 2e-6" apart, coarser than the program's tolerance, and a pin can't be put exactly on a
        # wire: no drawing is that big, and these steps, which check exact places, skip it)
        bb = s.extents()
        x = (bb[2] if bb is not None else world["o"][0]) + 20.0 * k
        got = (round((x + rnd.randint(0, 40) * k) / 0.25) * 0.25,
               round((world["o"][1] + rnd.randint(0, 40) * k) / 0.25) * 0.25)
        if max(abs(got[0]), abs(got[1])) + 100.0 * k > FAR:
            BC.CHECKED["clear spot too far out to be exact: skipped"] += 1
            return None
        return got

    def op_wire_around():
        # (0.16.7: a wire to a pin on the far side of a symbol goes round it, not through it,
        # and arrives straight out of the pin's side; off on its own, far from everything)
        k = s.k()
        o = clear_of_drawing(k)
        if o is None:
            return
        name = rnd.choice(["Drive control terminals", "Disconnect 3-pole", "Relay coil",
                           "Fuses 3-pole", "Variable frequency drive", "Motor 3-phase",
                           "1734-IB8 module"])
        if rnd.random() < 0.3:
            # (0.22.1: the preset's layers in, so a wire to a drive's, motor's or PLC point's pin
            # takes its voltage's layer)
            with p.edit("preset") as ed:
                wirelayers.add_preset(ed, p)
        before = set(s.entities)
        v.run(C.InsertCmd, lib.get("symbol", name), {})
        for _i in range(rnd.randint(0, 3)):
            v.input_text("R")
        v.input_text(fmt(o))
        finish()
        got = [e for i, e in s.entities.items() if i not in before and isinstance(e, M.Insert)]
        if len(got) != 1:
            return
        e = got[0]
        bb = wires.body_box(e)
        pin_name, pin = rnd.choice(e.pin_points())
        # from beyond the edge across from the pin's side, a fair way off (outside the
        # symbol: turned, a point worked out across its middle was inside it, seed 31)
        sides = [(abs(pin[0] - bb[0]), "left"), (abs(pin[0] - bb[2]), "right"),
                 (abs(pin[1] - bb[1]), "bottom"), (abs(pin[1] - bb[3]), "top")]
        side = min(sides)[1]
        off = rnd.choice([-1, 1]) * 0.5 * k
        a = {"left": (bb[2] + 2.0 * k, pin[1] + off), "right": (bb[0] - 2.0 * k, pin[1] + off),
             "bottom": (pin[0] + off, bb[3] + 2.0 * k),
             "top": (pin[0] + off, bb[1] - 2.0 * k)}[side]
        # (the far end on the quarter-inch grid, as clicked with Snap on: the outline's edge
        # isn't on it, as Bus around's seed 4421)
        g = 0.25 * k
        a = (round(a[0] / g) * g, round(a[1] / g) * g)
        before = set(s.entities)
        v.run(C.WireCmd)
        type_in(v, fmt(a), fmt(pin))
        finish()
        new = [w for i, w in s.entities.items() if i not in before and isinstance(w, M.Wire)]
        # (on it as the program joins: within TOL; the point is typed with 12 digits, so a
        # pin at 6.000000000000001 is typed 6, seed 8)
        mine = [w for w in new if min(G.dist(pin, w.points[0]), G.dist(pin, w.points[-1]))
                <= wires.TOL]
        assert mine, "the wire to %s's pin %s didn't end on it" % (name, pin_name)
        w = mine[0]
        assert not wires._crosses(w.points, [(e, bb)]), \
            "a wire to %s's pin %s ran through it: %s" % (name, pin_name, w.points)
        BC.CHECKED["wire goes around a symbol"] += 1
        # (0.22.1: a wire on its own ending on a pin takes the layer the pin's kind gives,
        # when the project has it; worked out here from the symbol's name and the pin's, not
        # from autolayer)
        far = w.points[0] if G.dist(pin, w.points[-1]) <= wires.TOL else w.points[-1]
        if len(new) == 1 and not wires.connects_at(s, far, exclude=w.id) and \
                not wires.pins_on(s, far):
            want = None
            if name in ("Variable frequency drive", "Motor 3-phase"):
                want = "480V GRN" if pin_name.startswith("PE") else (
                    "480V BLK" if pin_name[:1] in "LT" else None)
            elif name == "1734-IB8 module":
                want = "24VDC BLU"                  # (every terminal an input point)
            if want is None or want not in p.layers or \
                    not p.settings.get("wire_layer_auto", True):
                assert w.layer == C.wire_layer(v), \
                    "a wire to %s's pin %s went on %s" % (name, pin_name, w.layer)
            else:
                assert w.layer == want, "a wire to %s's pin %s went on %s, not %s" % (
                    name, pin_name, w.layer, want)
                BC.CHECKED["a wire to a drive's, motor's or PLC point's pin takes its layer"] += 1

    def op_bus_around():
        # (0.16.7: a bus clicked across a symbol off on its own goes round it: none of its
        # wires runs through it)
        k = s.k()
        o = clear_of_drawing(k)
        if o is None:
            return
        name = rnd.choice(["Drive control terminals", "Disconnect 3-pole", "Variable frequency drive"])
        before = set(s.entities)
        v.run(C.InsertCmd, lib.get("symbol", name), {})
        v.input_text(fmt(o))
        finish()
        got = [e for i, e in s.entities.items() if i not in before and isinstance(e, M.Insert)]
        if len(got) != 1:
            return
        e = got[0]
        bb = wires.body_box(e)
        cy = (bb[1] + bb[3]) / 2
        # (clicked on the quarter-inch grid, as with Snap on: worked out from the symbol's
        # outline, the bus started at x.19444, and a wire moved later passed 0.0087" from it,
        # the near-miss check's seed 4421: that slop was the battery's, not the program's)
        g = 0.25 * k
        a = (round((bb[0] - 3.0 * k) / g) * g, round((cy + rnd.choice([-1, 1]) * 0.25 * k) / g) * g)
        b = (round((bb[2] + 3.0 * k) / g) * g, a[1])
        before = set(s.entities)
        said = []
        v.message = lambda text: said.append(text)
        try:
            v.run(C.BusCmd)
            width = max(0, v.cmd.count - 1) * v.cmd.spacing
            if rnd.random() < 0.5:
                v.input_text("F")
            v.input_text(fmt(a))
            if v.cmd is not None:
                v.input_text(fmt(b))
            finish()
        finally:
            del v.message
        new = [w for i, w in s.entities.items() if i not in before and isinstance(w, M.Wire)]
        through = [w.points for w in new if wires._crosses(w.points, [(e, bb)])]
        assert not through, "a bus across %s ran through it: %s" % (name, through[:1])
        if not new:
            # (0.21.3: a bus far wider than the 3" clicked beside the symbol, its other wires
            # already past it, has no way round: it says so and draws nothing, not through it,
            # seed 433; a bus that fits must go round)
            assert width >= 3.0 * k, "a %g\" wide bus didn't go round %s" % (width, name)
            assert any("can't go round" in t for t in said), \
                "a bus too wide to go round %s drew nothing and said nothing" % name
            BC.CHECKED["bus too wide to go round says so"] += 1
            return
        BC.CHECKED["bus goes around a symbol"] += 1

    def op_wire_run():
        # (0.16.7: a run of wire dragged sideways by its middle grip: it is where it was
        # dragged, and every pin that had a wire on it still has one)
        cands = []
        for w in s.wires():
            for i, (a, b) in enumerate(zip(w.points, w.points[1:])):
                if (abs(a[0] - b[0]) < 1e-9) != (abs(a[1] - b[1]) < 1e-9):
                    cands.append((w, i))
        if not cands:
            return
        w, i = rnd.choice(cands)
        a, b = w.points[i], w.points[i + 1]
        wired = {q for e in s.inserts() for _n, q in e.pin_points() if wires.pins_on(s, q) and
                 any(x.touches(q) for x in s.wires())}
        to = pt()
        # (a pin on the run's middle or a corner of it: refused, the wire left as it was;
        # worked out here from the pins, seeds 11 and 23)
        # (or a pin or a wire's end on the part of a run beside it that gets shorter: seed 31,
        # a run dragged past the end of the long run beside it, which had two pins on it)
        horiz0 = abs(a[1] - b[1]) < 1e-9
        dd = (0.0, to[1] - a[1]) if horiz0 else (to[0] - a[0], 0.0)
        pins_all = [q for e in s.inserts() for _n, q in e.pin_points()]

        def held(x, k, seen):
            """Is run k of wire x kept from moving: a pin on it (not x's own end), a pin or a
            wire's end on the part of a run beside it that the move shortens, or the same on
            a wire carrying it straight on, which moves with it (seed 8: a pin on the wire
            carrying the run on)."""
            p0, p1 = x.points[k], x.points[k + 1]
            n = len(x.points) - 1
            if any(G.dist_to_segment(q, p0, p1) <= 1e-6 and
                   not (k == 0 and G.dist(q, p0) <= 1e-6) and
                   not (k + 1 == n and G.dist(q, p1) <= 1e-6) for q in pins_all):
                return True
            for j, c in ((k - 1, k), (k + 2, k + 1)):
                if not 0 <= j <= n:
                    continue
                f, old = x.points[j], x.points[c]
                nw = (old[0] + dd[0], old[1] + dd[1])
                spots = pins_all + [q for y in s.wires() if y.id != x.id
                                    for q in (y.points[0], y.points[-1])]
                if any(G.dist(q, old) > 1e-6 and G.dist_to_segment(q, f, old) <= 1e-6 and
                       G.dist_to_segment(q, f, nw) > 1e-6 for q in spots):
                    return True
            for y in s.wires():
                if y.id in seen:
                    continue
                for end in (0, -1):
                    e = y.points[end]
                    nb = y.points[1] if end == 0 else y.points[-2]
                    if (G.dist(e, p0) <= 1e-6 or G.dist(e, p1) <= 1e-6) and \
                            G.dist_to_segment(nb, p0, p1) > 1e-6 and \
                            ((abs(nb[0] - e[0]) < 1e-6) if dd[0] != 0.0 else
                             (abs(nb[1] - e[1]) < 1e-6)):
                        if held(y, 0 if end == 0 else len(y.points) - 2, seen | {x.id}):
                            return True
                        break
            return False
        pinned = held(w, i, {w.id})
        v.set_selection(set())
        v.run(C.GripCmd, w, len(w.points) + i)
        v.input_text(fmt(to))
        finish()
        if w.id not in s.entities:
            return                      # (cleaned up into another wire)
        if pinned:
            if s.entities[w.id].points == w.points:
                BC.CHECKED["wire run with a pin on it left"] += 1
                return
            # (a wire carrying it on may have had the pin: then nothing moved either)
            assert False, "a run with a pin on it was moved: %s" % s.entities[w.id].points
        if s.entities[w.id].points == w.points:
            # (refused, as it must be when the drag would leave a pin with no wire: a wire
            # tapping the run, a pin on its middle, followed past its other end, seed 6006;
            # worked out here from the drag the run would make and every pin by it)
            got = wires.segment_drag(s, w, i, to)
            if got is not None and any(wires.doubles_back(q) for q in got.values()):
                # (refused, as it must be: onto its own run beside it, the other way, the
                # wire would run back over itself, seed 704)
                BC.CHECKED["wire run that would fold the wire refused"] += 1
                return
            if got is not None:
                after_w = [M.Wire(pts) if x.id in got else x for x in s.wires()
                           for pts in [got.get(x.id)]]
                lost = [q for q in wired if not any(x.touches(q) for x in after_w)]
                if lost:
                    BC.CHECKED["wire run that would leave a pin refused"] += 1
                    return
        horiz = abs(a[1] - b[1]) < 1e-9
        moved = any((abs(p[1] - to[1]) < 1e-9 and abs(q[1] - to[1]) < 1e-9) if horiz else
                    (abs(p[0] - to[0]) < 1e-9 and abs(q[0] - to[0]) < 1e-9)
                    for p, q in zip(s.entities[w.id].points, s.entities[w.id].points[1:]))
        assert moved, "a run dragged to %s isn't there: %s" % (to, s.entities[w.id].points)
        after = {q for e in s.inserts() for _n, q in e.pin_points() if
                 any(x.touches(q) for x in s.wires())}
        lost = wired - after
        assert not lost, "dragging a run left pins %s without their wire" % sorted(lost)[:3]
        BC.CHECKED["wire run dragged"] += 1

    def op_bus():
        # (0.16: started on a symbol's pins it takes them; S straight; L layers)
        if rnd.random() < 0.15:
            # (0.18.5: now and then with 45-degree leads at pins that already have a wire)
            with p.edit("leads") as ed:
                ed.project_settings({"wire_lead": not p.settings.get("wire_lead", False)})
        sides = []
        for e in s.inserts():
            for _n, q in e.pin_points():
                got = C.pin_side(s, q)
                if got is not None:
                    sides.append(got)
                    break
        ends, taps = [], []
        for w in s.wires():
            for q in (w.points[0], w.points[-1]):
                got = C.end_side(s, q)
                if got is not None:
                    ends.append((q, got))
            for a, b in zip(w.points, w.points[1:]):
                m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                got = C.tap_lines(s, m)
                # (a symbol's pin or a bus's end there too is what a click takes first: seed
                # 2793, a pin on the middle of a wire)
                if got is not None and C.pin_side(s, m) is None and C.end_side(s, m) is None:
                    taps.append((m, got))
            if len(ends) > 8 and len(taps) > 8:
                break
        before = set(s.entities)
        old_wires = [list(w.points) for w in s.wires()]
        before_dots = set(wires.junctions(s))
        cmd = v.run(C.BusCmd)
        side = None
        from_ends = from_taps = None
        what = rnd.random()
        if ends and what < 0.2:
            from_ends = rnd.choice(ends)
            a = from_ends[0]
        elif taps and what < 0.4:
            from_taps = rnd.choice(taps)
            a = from_taps[0]
        elif sides and rnd.random() < 0.5:
            a = rnd.choice(rnd.choice(sides)[0])
            # (the side of the pin clicked: two symbols overlapping can share a pin, and the
            # bus takes one of theirs)
            side = C.pin_side(s, a)
        else:
            # (the spacing 1/2" on paper, as a user types it: 0.5 on a 1:87 sheet is 0.0057" on
            # paper, and carried to the next bus, the same on paper, made a 1:1 one's wires
            # 0.0057" apart, the near-miss check's seed 4442: the battery's own slop)
            for t in (str(rnd.randint(2, 4)), "%r" % (0.5 * s.k())):
                if v.cmd is not None:
                    v.input_text(t)
            a = pt()
        if v.cmd is not None and rnd.random() < 0.3:
            v.input_text("S")
        if v.cmd is not None and rnd.random() < 0.3 and from_ends is None:
            cmd.layers = rnd.choice([ls for _t, ls in C.BUS_LAYERS])
        for q in (a, (a[0] + rnd.choice([-3, 3]), a[1] + rnd.choice([0, 0, -2, 2]))):
            if v.cmd is not None:
                v.input_text(fmt(q))
        finish()
        if from_ends is not None and len(s.wires()) and \
                not any(i in before and i not in s.entities for i in before):
            # a bus carried on from its open end: every old end carried on (joined, no dot)
            for q in from_ends[1][0]:
                assert wires.connects_at(s, q), "a carried-on bus left %s loose" % (q,)
                if tuple(q) not in before_dots:
                    assert tuple(q) not in set(wires.junctions(s)), \
                        "carrying a bus on put a dot at %s" % (q,)
                # (and no wire leaves an end straight back over the wire it carries on: two
                # wires from that end the same way, one drawn over the other; seed 43)
                legs = []
                for w in s.wires():
                    for e0, e1 in ((w.points[0], w.points[1]), (w.points[-1], w.points[-2])):
                        if G.dist(e0, q) <= 1e-9:
                            L = G.dist(e0, e1)
                            legs.append(((e1[0] - e0[0]) / L, (e1[1] - e0[1]) / L))
                for i in range(len(legs)):
                    for j in range(i + 1, len(legs)):
                        assert legs[i][0] * legs[j][0] + legs[i][1] * legs[j][1] < 1 - 1e-9, \
                            "carrying a bus on drew a wire back over its own at %s" % (q,)
            BC.CHECKED["bus carried on"] += 1
        if from_taps is not None:
            # one off each of the wires side by side: each new wire starts on a different one
            across, lines, _gap = from_taps[1]
            new = [e for i, e in s.entities.items() if i not in before and isinstance(e, M.Wire)]
            k = 1 if across else 0
            got = sorted(round(w.points[0][k], 6) for w in new)
            if len(new) == len(lines):
                assert got == sorted(round(c, 6) for c in lines), \
                    "a bus off wires side by side started at %s, not %s" % (got, lines)
                BC.CHECKED["bus off wires side by side"] += 1
        if side is not None:
            # each wire from its own pin of the side started on: worked out from the pins
            new = [e for i, e in s.entities.items() if i not in before and isinstance(e, M.Wire)]
            starts = {tuple(w.points[0]) for w in new} | {tuple(w.points[-1]) for w in new}
            if len(new) == len(side[0]):
                missing = [q for q in side[0] if tuple(q) not in starts]
                assert not missing, "bus from a symbol's pins missed %s" % missing
                BC.CHECKED["bus from pins"] += 1
        bus_clear_of_pins([e for i, e in s.entities.items()
                           if i not in before and isinstance(e, M.Wire)], old_wires)

    def bus_clear_of_pins(new, old=(), what="bus"):
        # (0.19.11: no wire of a bus runs through a symbol's pin, only ends on it; worked out
        # from every pin near the wires, the battery's seed 152; a piece of a wire that was
        # there before, cut by the bus's cleanup and so a new id, is not the bus's: seed 163)
        def was_there(a, b):
            m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            return any(all(any(G.dist_to_segment(q, *seg) <= 1e-6
                               for seg in zip(o, o[1:])) for q in (a, b, m)) for o in old)
        for w in new:
            ends = (w.points[0], w.points[-1])
            for a, b in zip(w.points, w.points[1:]):
                if was_there(a, b):
                    continue
                bb = (min(a[0], b[0]) - 1e-6, min(a[1], b[1]) - 1e-6,
                      max(a[0], b[0]) + 1e-6, max(a[1], b[1]) + 1e-6)
                for e in s.query(bb):
                    if isinstance(e, M.Insert):
                        for n, q in e.pin_points():
                            assert any(G.dist(q, x) <= 1e-6 for x in ends) or \
                                G.dist_to_segment(q, a, b) > 1e-6, \
                                "a %s wire runs through %s's pin %s: %r" % (what, e.block, n,
                                                                             w.points)
        if new:
            BC.CHECKED["%s clear of pins" % what] += 1

    def op_bus_land():
        # (0.16.3: a bus from one symbol's pins ended on another's lands wire for wire, each
        # wire on its own pin in order and none crossing another, taking a Z when it must; or
        # it doesn't claim to and says why)
        sides = []
        for e in s.inserts():
            for _n, q in e.pin_points():
                got = C.pin_side(s, q)
                if got is not None and len(got[0]) == 3 and abs(got[1] - 0.5) < 1e-9:
                    sides.append((e.id, got[0]))
        if len(sides) < 2:
            return
        (ia, a), (ib, b) = rnd.sample(sides, 2)
        if ia == ib:
            return
        before = set(s.entities)
        old_wires = [list(w.points) for w in s.wires()]
        cmd = v.run(C.BusCmd)
        start = rnd.choice(a)
        # (symbols overlapping can share a pin: the side the start takes is the one the bus
        # leaves from, as at its end below; seed 5 and CI's long run, seeds 3121 and 3123: the
        # other disconnect's side was taken, and its pins were counted as left without wires)
        a = C.pin_side(s, start)[0]
        v.input_text(fmt(start))
        if v.cmd is None:
            return
        click = rnd.choice(b)
        # (symbols overlapping can share a pin: the side the click takes is the one it lands
        # on, seed 11)
        b = C.pin_side(s, click)[0]
        why = cmd._why_not_landed(s, click)
        landed = cmd._landing(s, click) is not None
        v.input_text(fmt(click))
        done = v.cmd is None
        finish()
        new = [e for i, e in s.entities.items() if i not in before and isinstance(e, M.Wire)]
        bus_clear_of_pins(new, old_wires)
        if landed:
            assert done, "a bus that lands on a symbol's pins didn't end there"
            # (cleanup may join a new wire to an old one: the pins are checked on every wire)
            every = {tuple(q) for w in s.wires() for q in (w.points[0], w.points[-1])}
            missing = [q for q in list(a) + list(b) if tuple(q) not in every]
            assert not missing, "a landed bus left pins %s without their wire" % missing
            def on(w, q):
                return any(G.dist_to_segment(q, *seg) < 1e-9
                           for seg in zip(w.points, w.points[1:]))
            mine = [x[0] for x in crossings.found(s) if sum(1 for w in new if on(w, x[0])) >= 2]
            assert not mine, "a landed bus's own wires cross at %s" % mine
            BC.CHECKED["bus lands wire for wire"] += 1
        else:
            assert why, "a bus ended on a symbol's pins without landing, and said nothing"
            BC.CHECKED["bus says why it didn't land"] += 1

    def op_symbol():
        name = rnd.choice(syms)
        before = set(s.entities)
        cmd = v.run(C.InsertCmd, lib.get("symbol", name), {})
        for k in rnd.sample(["R", "F", "V", "B"], rnd.randint(0, 3)):
            v.input_text(k)
        held = cmd.holds[cmd.hold][0]
        at = pt()
        if v.cmd is not None:
            v.input_text(fmt(at))
        # (a contact asking which device: the one offered as the nearest, or Enter, which
        # places it on its own since 0.17: linked to that device, or to none)
        linked = None
        c = v.cmd
        if c is not None and c.pending is not None and c.cands and not c.footprint_of and \
                c.link_name is None:
            dev = c.cands[0][1]
            if rnd.random() < 0.5:
                v.input_text(dev.attrs["TAG"])
                linked = tags_mod.find_tag(p, dev.attrs["TAG"])[1].attrs["DEV"]
            else:
                linked = ""
        finish()
        # (held by a pin, that pin is exactly where the point was given: 0.16)
        new = [e for i, e in s.entities.items() if i not in before and isinstance(e, M.Insert)]
        if held is not None and len(new) == 1:
            got = dict(new[0].pin_points())[held]
            assert got == at, "%s held by pin %s: the pin went to %s, not %s" % (
                name, held, got, at)
            BC.CHECKED["insert by its pin"] += 1
        if len(new) == 1 and tags_mod.is_device(new[0]) and not tags_mod.locked(new[0]):
            # (0.29: tagged with the project's prefix: an IEC project's 81346-2 letter, K for
            # a relay, Q for a contactor, X for a terminal strip; worked out from the table)
            d = new[0].defn
            want = d.prefix
            if p.settings.get("symbol_standard") == "iec":
                want = tags_mod.IEC_ROLE_LETTERS.get((d.prefix, d.role)) or \
                    tags_mod.IEC_LETTERS.get(d.prefix, d.prefix)
            tag = new[0].attrs.get("TAG", "")
            assert tags_mod.split(tag, want) is not None, "%s placed tagged %s, not %s..." % (
                name, tag, want)
            BC.CHECKED["a new device tagged with the project's letters"] += 1
        if linked is not None and len(new) == 1:
            got = new[0].attrs.get("PARENT", "")
            assert got == linked, "%s's device: %r, not %r" % (name, got, linked)
            BC.CHECKED["contact linked as asked" if linked else "contact on its own"] += 1
        if v.cmd is None and rnd.random() < 0.25:
            # Enter: the same symbol again (0.16), held by its first pin
            before = set(s.entities)
            v.enter()
            assert isinstance(v.cmd, C.InsertCmd) and v.cmd.defn.name == name, \
                "Enter didn't insert %s again" % name
            at = pt()
            v.input_text(fmt(at))
            finish()
            again = [e for i, e in s.entities.items() if i not in before and
                     isinstance(e, M.Insert)]
            assert len(again) == 1 and again[0].block == name, "Enter inserted %s" % again
            first = again[0].defn.pins[0]["name"] if again[0].defn.pins else None
            if first is not None:
                assert dict(again[0].pin_points())[first] == at
            BC.CHECKED["insert again with Enter"] += 1

    def op_symbol_on_bus():
        # (0.16.2: a 3-pole symbol clicked onto three wires lands every pole on its own wire,
        # however it is turned and flipped: it flips itself when that lands more of its pins)
        name = rnd.choice([n for n in syms if lib.get("symbol", n).pins and
                           len(lib.get("symbol", n).pins) == 6])
        turns = rnd.randint(0, 3)
        # (in a clear spot: laid over other wires, which pin ends on which wire isn't defined,
        # seed 306)
        a = clear_of_drawing(s.k())
        if a is None:
            return
        up = turns % 2 == 1                     # (turned sideways: the bus runs up and down)
        L = 3.0
        with p.edit("bus to land on") as ed:
            side = rnd.choice([1, -1])
            for i in range(3):
                off = side * i * 0.5
                pts = [(a[0] + off, a[1] + L), (a[0] + off, a[1] - L)] if up else \
                    [(a[0] - L, a[1] + off), (a[0] + L, a[1] + off)]
                ed.add(s, M.Wire(pts))
        before = set(s.entities)
        v.run(C.InsertCmd, lib.get("symbol", name), {})
        for _i in range(turns):
            v.input_text("R")
        if rnd.random() < 0.5:
            v.input_text("F")
        v.input_text(fmt(a))
        finish()
        new = [e for i, e in s.entities.items() if i not in before and isinstance(e, M.Insert)]
        assert len(new) == 1, "%s not placed on the bus" % name
        ends = {(round(q[0], 9), round(q[1], 9)) for w in s.wires()
                for q in (w.points[0], w.points[-1])}
        off = [n for n, q in new[0].pin_points() if (round(q[0], 9), round(q[1], 9)) not in ends]
        assert not off, "%s turned %d times on a bus: pins %s on no wire" % (name, turns, off)
        BC.CHECKED["3-pole lands on a bus"] += 1

    def op_tag_grip():
        # (0.16.2: a symbol's tag dragged by its grip goes exactly there, the symbol and its
        # pins staying; it follows the symbol)
        got = [e for e in s.inserts() if e.text_grips()]
        if not got:
            return
        e = rnd.choice(got)
        names = [n for n, _q in e.text_grips()]
        i = rnd.randrange(len(names))
        pins = e.pin_points()
        to = pt()
        v.set_selection(set())
        v.run(C.GripCmd, e, i + 1)
        v.input_text(fmt(to))
        finish()
        e2 = s.entities[e.id]
        q = dict(e2.text_grips())[names[i]]
        assert G.dist(q, to) < 1e-9, "%s of %s dragged to %s went to %s" % (
            names[i], e.block, to, q)
        assert e2.pin_points() == pins and e2.pos == e.pos, "dragging %s moved %s" % (
            names[i], e.block)
        BC.CHECKED["text grip"] += 1

    def ladder_numbers_expected():
        """{ladder id: [numbers]} of the sheet's ladders, worked out from the page, the
        numbering style and each ladder's place (left to right, then top down), not from
        ladders.py."""
        how = p.settings.get("ladder_numbers") or "hundreds"
        page = p.sheet_number(s)
        try:
            base = int(page) * 100
        except ValueError:
            base = (p.sheets.index(s) + 1) * 100
        nxt = 1 if how == "prefix" else base
        out = {}
        for lad in sorted((e for e in s.entities.values() if isinstance(e, M.Ladder)),
                          key=lambda e: (round(e.a[0], 6), -e.a[1])):
            start = lad.first if lad.first is not None else nxt
            if how == "prefix":
                out[lad.id] = ["%s-%02d" % (page, start + i) for i in range(lad.rungs)]
            else:
                out[lad.id] = [str(start + i) for i in range(lad.rungs)]
            nxt = start + lad.rungs
        return out

    def op_trace():
        # (0.23: Trace, Ctrl+E: a device or a wire picked as a user would, every place it is
        # listed, worked out here from the objects themselves: the inserts sharing its hidden
        # id or its tag, the wires carrying its number and the arrows on them; then a row gone
        # to: its sheet shown, its object selected and in the middle of the view)
        nonlocal s
        from kanzonascad import where_used as WU
        devs = [(sh, e) for sh in p.sheets for e in sh.inserts()
                if tags_mod.is_device(e) and e.attrs.get("DEV")]
        ws = [(sh, w) for sh in p.sheets for w in sh.wires() if w.num]
        # (half the time a wire with an arrow on it, when there is one)
        arrowed = [(sh, w) for sh in p.sheets for c in sh.inserts()
                   if c.defn is not None and c.defn.wiring == "link"
                   for _n, q in c.pin_points() for w in sh.query_point(q, 1e-6)
                   if isinstance(w, M.Wire) and w.num and w.touches(q, 1e-6)]
        if arrowed and rnd.random() < 0.5:
            ws = arrowed
        if not devs and not ws:
            return
        pick = rnd.choice(devs if devs and (not ws or rnd.random() < 0.5) else ws)
        sh, e = pick
        v.show_sheet(sh.id)
        s = v.sheet()
        dock, btn = win.trace_dock, win.acts["trace_panel"]

        def settle():
            APP.processEvents()
            t0 = time.perf_counter()
            while win.trace_busy():                     # (it works in the event loop's turns)
                APP.processEvents()
                assert time.perf_counter() - t0 < 60, "Trace never finished"

        def in_sight():
            return dock.isVisible() and not dock.visibleRegion().isEmpty()

        def toggle():
            # (0.23.2: the button closes the panel when it is open and in sight, else opens
            # or raises it and lists what is selected; checked while the panel is open)
            was_open, seen = not dock.isHidden(), in_sight()
            btn.trigger()
            settle()
            if was_open and seen:
                assert dock.isHidden() and not btn.isChecked(), "the button didn't close it"
            else:
                assert not dock.isHidden() and in_sight() and btn.isChecked(), \
                    "the button didn't open it"
            BC.CHECKED["trace: the button toggles the panel"] += 1

        assert btn.isChecked() == (not dock.isHidden()), "the Trace button's check is wrong"
        if rnd.random() < 0.3:
            toggle()
        # several picked (0.23.2): the step's own record of what each pick added
        v.set_selection({e.id})
        picks = [{e.id}]
        how = rnd.random()
        if how < 0.4:                                   # (e in sight, with room around it)
            k = s.k()
            v.zoom_to(e.bbox(), (rnd.uniform(4.0, 12.0) * k, rnd.uniform(3.0, 8.0) * k))
            APP.processEvents()
        clicked = []
        if how < 0.25:                                  # (clicks: each adds one)
            Qt, QPoint, QPointF, QTest = _qt()
            c0, c1 = v.to_world(QPointF(0, v.height())), v.to_world(QPointF(v.width(), 0))
            others = [x for x in s.query((c0[0], c0[1], c1[0], c1[1])) if x.id != e.id]
            for x in rnd.sample(others, min(len(others), rnd.randint(1, 4))):
                q = _spot(v, x)
                if q is None or x.id in v.sel:
                    continue
                _click(v, q)
                assert x.id in v.sel, "a click on %r didn't add it" % (x,)
                picks.append({x.id})
                clicked.append(x)
        elif how < 0.4:                                 # (a window around e: many at once)
            Qt, QPoint, QPointF, QTest = _qt()
            bb, k = e.bbox(), s.k()
            wa = (bb[0] - rnd.uniform(0.2, 3.0) * k, bb[3] + rnd.uniform(0.2, 3.0) * k)
            wb = (bb[2] + rnd.uniform(0.2, 3.0) * k, bb[1] - rnd.uniform(0.2, 3.0) * k)
            a_px, b_px = v.to_screen(wa), v.to_screen(wb)
            inside = all(2 <= q.x() <= v.width() - 2 and 2 <= q.y() <= v.height() - 2
                         for q in (a_px, b_px))
            if inside and v.pick_entity(wa) is None and v.grip_at(a_px) is None:
                before = set(v.sel)
                _drag_path(v, QPoint(round(a_px.x()), round(a_px.y())),
                           QPoint(round(b_px.x()), round(b_px.y())), steps=12)
                wa = v.to_world(QPointF(QPoint(round(a_px.x()), round(a_px.y()))))
                wb = v.to_world(QPointF(QPoint(round(b_px.x()), round(b_px.y()))))
                caught = BC.expected_window(v, wa, wb)
                assert v.sel == before | caught, "the window around %r selected %d, not %d" % (
                    e, len(v.sel), len(before | caught))
                picks.append(caught - before)
                BC.CHECKED["trace: a window's pick"] += 1
        if dock.isHidden() and rnd.random() < 0.3:
            toggle()                                    # (the button: opens and lists)
        else:
            win.acts["trace"].trigger()                 # (Ctrl+E: opens, never closes)
            settle()
        assert not dock.isHidden() and in_sight() and btn.isChecked(), "Ctrl+E didn't open it"

        def traced_right():
            want = trace_last_picked(p, s, v.sel, picks)
            got = win._trace_subject[1] if win._trace_subject else None
            assert want is not None and got == WU.subject_of(p, s, want), \
                "Trace listed %r, the last picked is %r (%r)" % (got, want, picks)
            n = len(v.sel) - 1
            note = "" if n < 1 else " (and %d other%s selected)" % (n, "" if n == 1 else "s")
            head = win.trace_panel.header.text()
            assert head.endswith(note), (head, note)
            if n:
                BC.CHECKED["trace: the last one picked of several"] += 1
            return want, head[:len(head) - len(note)]

        want, head = traced_right()
        if clicked and rnd.random() < 0.5:
            # (the last click taken out, Shift+click: the one picked before it, live)
            q = _spot(v, clicked[-1])
            if q is not None:
                _click(v, q, _qt()[0].ShiftModifier)
                assert clicked[-1].id not in v.sel, "Shift+click didn't take it out"
                settle()
                want, head = traced_right()
                BC.CHECKED["trace: the one picked before the last, taken out"] += 1
        sel_e = (sh, want)
        if sel_e not in devs and sel_e not in ws:
            # (something else picked last, a contact, a PLC point, a wire with no number:
            # listed for it, its places checked by the steps above for devices and wires)
            e = None
        else:
            e = want
        rows = win.trace_panel.rows()
        assert rows, "Trace listed nothing for %r: %s" % (want, head)
        assert head.endswith("%d place%s" % (len(rows), "" if len(rows) == 1 else "s")), head
        got = {(r.sheet_id, i) for r in rows for i in r.ids}
        if isinstance(e, M.Insert):
            dev, tag = e.attrs["DEV"], (e.attrs.get("TAG", "") or "").strip().upper()
            want = set()
            for o in p.sheets:
                for x in list(o.inserts()) + [b for b in o.entities.values()
                                              if isinstance(b, M.DashBox)]:
                    if isinstance(x, M.Insert) and (x.defn is None or x.defn.wiring == "link"):
                        continue
                    if isinstance(x, M.DashBox) and not (x.attrs.get("PARENT") or
                                                         x.attrs.get("TAG")):
                        continue
                    if dev in (x.attrs.get("DEV"), x.attrs.get("PARENT")) or (
                            tag and (x.attrs.get("TAG", "") or "").strip().upper() == tag):
                        want.add((o.id, x.id))
            assert got == want, "Trace of %s: listed %s, there are %s" % (
                tag, sorted(got - want), sorted(want - got))
            BC.CHECKED["trace: a device's places"] += 1
        elif e is not None:
            num = e.num
            want = {(o.id, w.id) for o in p.sheets for w in o.wires() if w.num == num}
            wires_got = {(r.sheet_id, i) for r in rows if r.role == "Wire" for i in r.ids}
            assert want <= wires_got, "Trace of wire %s: left out %s" % (
                num, sorted(want - wires_got))
            for o_id, i in wires_got - want:        # (only wires joined to one of that number)
                o = p.sheet_by_id(o_id)
                assert o.entities[i].num != num and any(
                    o2.entities[j].num == num for o2_id, j in wires_got
                    for o2 in [p.sheet_by_id(o2_id)]), (o_id, i)
            ends = {}
            for o_id, i in wires_got:
                ends.setdefault(o_id, []).append(p.sheet_by_id(o_id).entities[i])
            for o_id, mine in ends.items():
                o = p.sheet_by_id(o_id)
                for c in o.inserts():
                    if c.defn is None or c.defn.wiring != "link":
                        continue
                    if any(w.touches(q, 1e-6) for _n, q in c.pin_points() for w in mine):
                        assert (o_id, c.id) in got, "Trace of wire %s: arrow %s left out" % (
                            num, c.attrs.get("TAG"))
                        BC.CHECKED["trace: an arrow on the wire"] += 1
            BC.CHECKED["trace: a wire's places"] += 1
        r = rnd.choice(rows)
        assert win.trace_go(r), "couldn't go to %r" % (r,)
        s = v.sheet()
        assert v.sheet_id == r.sheet_id and v.sel == set(r.ids), (v.sheet_id, v.sel, r)
        o = p.sheet_by_id(r.sheet_id)
        bb = None
        for i in r.ids:
            bb = G.bbox_union(bb, o.entities[i].bbox())
        tol = 1e-6 * max(1.0, abs(v.center[0]), abs(v.center[1]))
        assert bb[0] - tol <= v.center[0] <= bb[2] + tol and \
            bb[1] - tol <= v.center[1] <= bb[3] + tol, ("not centered on it", v.center, bb)
        BC.CHECKED["trace: gone to a row"] += 1
        r = rnd.random()
        if r < 0.25:
            toggle()                                    # (the button: in sight, so closed)
            assert dock.isHidden()
        elif r < 0.5:
            dock.close()                                # (its X)
            APP.processEvents()
            assert not btn.isChecked(), "the Trace button stayed checked after its X"
            BC.CHECKED["trace: its X unchecks the button"] += 1

    def op_ladder():
        # (0.22: a ladder through its command, as the owner would: its rungs numbered from the
        # page and the ladders to its left; on a sheet by ladder, a point on a rung reads its
        # number)
        k = s.k()
        a = pt()
        w = rnd.choice([3.0, 4.0, 6.0]) * k
        rungs = rnd.randint(2, 12)
        first = rnd.randint(100, 900) if rnd.random() < 0.2 else None
        before = set(s.entities)
        v.run(C.LadderCmd)
        if first is not None:
            v.input_text("F")
            v.input_text(str(first))
        v.input_text(fmt(a))
        if v.cmd is not None:
            v.input_text(fmt((a[0] + w, a[1])))
        if v.cmd is not None:
            v.input_text(str(rungs))
        finish()
        new = [e for i, e in s.entities.items() if i not in before and isinstance(e, M.Ladder)]
        assert len(new) == 1, "the ladder command drew %d ladders" % len(new)
        lad = new[0]
        assert lad.rungs == rungs and lad.first == first, (lad.rungs, rungs, lad.first, first)
        if rnd.random() < 0.3:
            with p.edit("Rung numbers") as ed:
                ed.project_settings({"ladder_numbers": rnd.choice(["hundreds", "prefix"])})
        want = ladder_numbers_expected()
        for e in s.entities.values():
            if isinstance(e, M.Ladder):
                assert e.numbers() == want[e.id], "ladder rungs numbered %s, not %s" % (
                    e.numbers()[:3], want[e.id][:3])
        BC.CHECKED["ladder rungs numbered from the page"] += 1
        if rnd.random() < 0.5:
            with p.edit("References") as ed:
                ed.sheet_meta(s, referencing="ladder")
            lad = s.entities[lad.id]
            i = rnd.randrange(lad.rungs)
            q = (lad.a[0] + lad.width() / 2, lad.a[1] - i * lad.spacing)
            # (the first ladder, left to right then top down, that q is on: within a third of
            # its width past its rails and half a rung past its ends, measured along its own
            # rungs and rails: a ladder turned by an earlier step runs up or sideways, the
            # long battery's seed 4791, where this read only ladders running down)
            hit = None
            for e in sorted((e for e in s.entities.values() if isinstance(e, M.Ladder)),
                            key=lambda e: (round(e.a[0], 6), -e.a[1])):
                wd = G.dist(e.a, e.b)
                ux, uy = (e.b[0] - e.a[0]) / wd, (e.b[1] - e.a[1]) / wd
                along = (q[0] - e.a[0]) * ux + (q[1] - e.a[1]) * uy
                down = ((q[0] - e.a[0]) * uy - (q[1] - e.a[1]) * ux) / e.spacing
                m = wd / 3.0
                if -m <= along <= wd + m and -0.5 <= down <= e.rungs - 0.5:
                    hit = e.numbers()[int(round(down))]
                    break
            assert p.zone_text(s, *q) == hit, "a point on rung %s reads %s" % (
                hit, p.zone_text(s, *q))
            BC.CHECKED["a place on a ladder reads its rung"] += 1

    def op_dash_box():
        # (0.16.4: a dashed box through its command and window: a note, belonging to nothing,
        # to a device from the list, or to one picked on the drawing on another sheet)
        from kanzonascad import tags, xrefs
        a, b = pt(), pt()
        if abs(a[0] - b[0]) < 1e-9 or abs(a[1] - b[1]) < 1e-9:
            return
        devs = tags.device_choices(p)
        how = rnd.choice(["none", "list", "pick"]) if devs else "none"
        dev = rnd.choice(devs) if devs else None
        text = rnd.choice(["", "FIELD WIRING", "BY OTHERS\nSEE DWG E-2"])
        here = s
        win.ask_dash_box = lambda box: {"text": text, "device": dev[1] if how == "list" else None,
                                        "pick": how == "pick"}
        try:
            before = set(here.entities)
            v.run(C.DashBoxCmd)
            v.input_text(fmt(a))
            v.input_text("#" + fmt(b))             # (a point: a plain x,y is the size)
            if how == "pick":
                assert isinstance(v.cmd, C.PickDeviceCmd), "Pick on drawing didn't start"
                v.show_sheet(dev[0].id)
                APP.processEvents()
                assert isinstance(v.cmd, C.PickDeviceCmd), "picking stopped on another sheet"
                got = dict(dev[1].pin_points())
                q = next(iter(got.values())) if got else dev[1].pos
                hit = v.pick_entity(q, M.Insert)
                if hit is None or not tags.is_device(hit):
                    # (another symbol over that pin is what a click there picks, seeds 23 and
                    # 292: the program says it isn't a device and waits; Esc stops, no box)
                    v.escape()
                    how = "esc"
                else:
                    v.cmd.point(q)
                for _i in range(3):
                    APP.processEvents()
                assert v.sheet() is here, "picking didn't come back to the box's sheet"
        finally:
            del win.ask_dash_box
            finish()
        new = [e for i, e in here.entities.items() if i not in before and isinstance(e, M.DashBox)]
        if how == "esc":
            assert not new, "Esc while picking made a box"
            BC.CHECKED["dashed box: Esc while picking"] += 1
            return
        assert len(new) == 1, "Dashed box made %d boxes" % len(new)
        box = new[0]
        x0, x1 = sorted((a[0], b[0]))
        y0, y1 = sorted((a[1], b[1]))
        assert box.points == [(x0, y1), (x1, y1), (x1, y0), (x0, y0)], \
            "the box isn't between its corners: %s" % box.points
        assert box.text == text
        if how == "none":
            assert not box.tag(), "a box belonging to nothing shows %s" % box.tag()
        else:
            # (a pick may click another device overlapping it: it belongs to the one clicked)
            parent = tags.devices(p).get(box.attrs.get("PARENT"))
            assert parent is not None, "the box belongs to no device"
            assert box.tag() == parent[1].attrs.get("TAG"), "the box shows %s, not %s" % (
                box.tag(), parent[1].attrs.get("TAG"))
            assert xrefs.live(p, parent[0]), "the device lists nothing"
            BC.CHECKED["dashed box belongs to a device"] += 1
        BC.CHECKED["dashed box"] += 1

    def op_dash_poly():
        # (0.26: a dashed polygon through its command and window: its corners clicked one by
        # one, closed with C or Enter; a note, belonging to nothing or to a device from the
        # list). Worked out here from the corners typed: its corners are those typed (one in
        # a straight run with its neighbors is no corner), every dash lies on its outline, and
        # three corners in a line make none (the command waits)
        from kanzonascad import tags
        pts = []
        for _i in range(rnd.randint(3, 6)):
            q = pt()
            if not pts or G.dist(q, pts[-1]) > 1e-9:
                pts.append(q)
        devs = tags.device_choices(p)
        dev = rnd.choice(devs)[1] if devs and rnd.random() < 0.4 else None
        text = rnd.choice(["", "BY OTHERS", "FIELD\nDEVICES"])
        here = s
        win.ask_dash_box = lambda box: {"text": text, "device": dev, "pick": False}
        try:
            before = set(here.entities)
            v.run(C.DashPolygonCmd)
            for q in pts:
                v.input_text("#" + fmt(q))
            v.input_text(rnd.choice(["C", ""]))
            waiting = v.cmd is not None
        finally:
            del win.ask_dash_box
            if v.cmd is not None:
                v.escape()
        new = [e for i, e in here.entities.items() if i not in before]
        ring = [q for i, q in enumerate(pts) if i == 0 or G.dist(q, pts[i - 1]) > 1e-9]
        while len(ring) > 1 and G.dist(ring[0], ring[-1]) <= 1e-9:
            ring.pop()
        area = abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1])))
        scale = max(1.0, max(abs(c) for q in ring for c in q)) ** 2
        if len(ring) < 3 or area <= 1e-9 * scale:
            assert not new and waiting, "a dashed polygon with no area: %r" % new
            BC.CHECKED["dashed polygon: none without area"] += 1
            return
        assert len(new) == 1 and isinstance(new[0], M.DashPolygon), \
            "Dashed polygon made %r" % new
        e = new[0]
        sides = list(zip(e.points, e.points[1:] + e.points[:1]))
        for q in e.points:
            assert any(G.dist(q, r) <= 1e-9 for r in ring), "a corner %r not clicked" % (q,)
        for q in ring:
            assert any(G.dist_to_segment(q, a, b) <= 1e-6 for a, b in sides), \
                "a corner clicked, %r, not on its outline" % (q,)
        for a, b in e.dash_pieces():
            assert any(G.dist_to_segment(a, c, d) <= 1e-6 and G.dist_to_segment(b, c, d) <= 1e-6
                       for c, d in sides), "a dash off its outline"
        assert e.text == text
        if dev is not None:
            assert e.tag() == dev.attrs.get("TAG"), "the polygon shows %r, not %r" % (
                e.tag(), dev.attrs.get("TAG"))
            BC.CHECKED["dashed polygon belongs to a device"] += 1
        BC.CHECKED["dashed polygon"] += 1

    def op_join():
        # (0.26: Join, through its command, as a user would: lines drawn end to end with LINE
        # (and a polyline or an arc carried on from them, an end a hair off now and then),
        # then those and a few others selected and joined). What Join must do, worked out
        # from the objects: nothing else changes; the joinable ones selected (lines, arcs,
        # open polylines) cover the same as before, as long in all; and of what is left no
        # two straight ones meet end to end alone there (no third end) without one lying back
        # over the other, nor two arcs of one circle end to start: those should have joined
        from kanzonascad import join as J
        before = set(s.entities)
        q = pt()
        k = world["k"]
        v.run(C.LineCmd)
        type_in(v, fmt(q))
        for _i in range(rnd.randint(1, 3)):
            if v.cmd is None:
                break
            q = (q[0] + rnd.choice([-1, 0, 1, 2]) * 0.5 * k, q[1] + rnd.choice([-1, 0, 1]) *
                 0.5 * k)
            v.input_text(fmt(q))
        finish()
        if rnd.random() < 0.4:
            off = (rnd.choice([0.0, 0.0, 0.003]) * k, 0.0)
            a = (q[0] + off[0], q[1])
            v.run(C.PolylineCmd)
            type_in(v, fmt(a), fmt((a[0] + 0.5 * k, a[1])), fmt((a[0] + 0.5 * k, a[1] + 0.5 * k)))
            finish()
        elif rnd.random() < 0.3:
            v.run(C.ArcCmd)
            type_in(v, fmt(q), fmt((q[0] + 0.5 * k, q[1] + 0.5 * k)), fmt((q[0] + k, q[1])))
            finish()
        drawn = [i for i in s.entities if i not in before]
        others = [e.id for e in some(rnd.randint(0, 3))]
        picked = {i for i in drawn + others if i in s.entities and
                  not v.layer_locked(s.entities[i].layer)}
        if not picked:
            return
        was = {i: e for i, e in s.entities.items()}
        v.set_selection(picked)
        n = len(p.undo_stack)
        v.run(C.JoinCmd)
        finish()
        assert len(p.undo_stack) <= n + 1, "Join took more than one step"
        gone = [i for i in was if i not in s.entities]
        for i, e in was.items():
            if i in s.entities and i not in picked:
                assert s.entities[i].to_dict() == e.to_dict(), "Join changed an object not picked"
        assert all(i in picked and J.joinable(was[i]) for i in gone), \
            "Join took away an object it can't join"
        new = [e for i, e in s.entities.items() if i not in was]
        olds = [was[i] for i in gone]

        def samples(e):
            if isinstance(e, M.Arc):
                sw = G.sweep(e.start, e.end)
                return [G.polar(e.center, e.radius, e.start + sw * t) for t in (0, .3, .5, 1)]
            if isinstance(e, M.Circle):
                return [G.polar(e.center, e.radius, a) for a in (0, 90, 200)]
            pts_ = [e.p1, e.p2] if isinstance(e, M.Line) else list(e.points)
            out = list(pts_)
            for a, b in zip(pts_, pts_[1:]):
                out.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
            return out

        def length(e):
            if isinstance(e, M.Arc):
                return math.radians(G.sweep(e.start, e.end)) * e.radius
            if isinstance(e, M.Circle):
                return 2 * math.pi * e.radius
            pts_ = [e.p1, e.p2] if isinstance(e, M.Line) else list(e.points)
            if isinstance(e, M.Polyline) and e.closed:
                pts_ = pts_ + pts_[:1]
            return sum(G.dist(a, b) for a, b in zip(pts_, pts_[1:]))
        tol = 1e-6 * max(1.0, k)
        for a in olds:
            for q in samples(a):
                assert min((b.distance(q) for b in new), default=1.0) <= tol, \
                    "Join lost a piece at %r" % (q,)
        for b in new:
            for q in samples(b):
                assert min((a.distance(q) for a in olds), default=1.0) <= tol, \
                    "Join drew something new at %r" % (q,)
        assert abs(sum(map(length, olds)) - sum(map(length, new))) <= tol * (len(olds) + 1), \
            "joined, not as long in all"
        if gone:
            BC.CHECKED["Join covers what it joined"] += 1
        left = [s.entities[i] for i in picked if i in s.entities] + new
        ends = []
        for e in left:
            if not J.joinable(e):
                continue
            if isinstance(e, M.Arc):
                ends += [(e.start_point(), e, 0), (e.end_point(), e, 1)]
            elif isinstance(e, M.Line):
                ends += [(e.p1, e, 0), (e.p2, e, 1)]
            else:
                ends += [(e.points[0], e, 0), (e.points[-1], e, 1)]
        for qa, a, ea in ends:
            here_ = [(qb, b, eb) for qb, b, eb in ends if G.dist(qa, qb) <= 1e-6]
            if len(here_) != 2:
                continue
            (_q1, x, ex), (_q2, y, ey) = here_
            if x is y:
                continue
            if isinstance(x, M.Arc) != isinstance(y, M.Arc):
                continue
            if isinstance(x, M.Arc):
                same = G.dist(x.center, y.center) <= 1e-6 and abs(x.radius - y.radius) <= 1e-6
                assert not (same and ex != ey and G.sweep(x.start, x.end) +
                            G.sweep(y.start, y.end) <= 360.0 + 1e-9), \
                    "two arcs of one circle left end to start at %r" % (qa,)
                continue

            def leg(e, end):
                pts_ = [e.p1, e.p2] if isinstance(e, M.Line) else list(e.points)
                a_, b_ = (pts_[0], pts_[1]) if end == 0 else (pts_[-1], pts_[-2])
                L = G.dist(a_, b_)
                return ((b_[0] - a_[0]) / L, (b_[1] - a_[1]) / L)
            u, w = leg(x, ex), leg(y, ey)
            back = abs(u[0] * w[1] - u[1] * w[0]) <= 1e-9 and u[0] * w[0] + u[1] * w[1] > 0
            assert back, "two lines or polylines left end to end alone at %r: not joined" % (qa,)
        BC.CHECKED["Join leaves nothing it could join"] += 1

    def op_bus_swap():
        # (0.26: a bus from one symbol's three pins to another's with W, phases 1 and 3
        # swapped). The same bus without W first, undone: then with W the first wire lands
        # where the plain bus's third did and the third where its first did, the second as
        # it did; every pin has its wire; the bus's wires cross only in plain crosses (no end
        # on another, none lying on another). Or, with no room to cross over, it says so and
        # draws nothing
        sides = []
        for e in s.inserts():
            for _n, q in e.pin_points():
                got = C.pin_side(s, q)
                if got is not None and len(got[0]) == 3 and abs(got[1] - 0.5) < 1e-9:
                    sides.append((e.id, got[0]))
        if len(sides) < 2:
            return
        (ia, a), (ib, b) = rnd.sample(sides, 2)
        if ia == ib:
            return
        start = rnd.choice(a)
        a = C.pin_side(s, start)[0]
        click = rnd.choice(b)
        b = C.pin_side(s, click)[0]

        def run(swap):
            before = set(s.entities)
            n = len(p.undo_stack)
            msgs = []
            v.messaged.connect(msgs.append)
            try:
                v.run(C.BusCmd)
                v.input_text(fmt(start))
                if v.cmd is None:
                    return None, msgs, False
                if swap:
                    v.input_text("W")
                v.input_text(fmt(click))
                done = v.cmd is None
                if not done:
                    v.escape()
            finally:
                v.messaged.disconnect(msgs.append)
            new = [e for i, e in s.entities.items() if i not in before and isinstance(e, M.Wire)]
            if not done or len(p.undo_stack) != n + 1 or len(new) != 3:
                return None, msgs, done
            got = {}
            for w in new:
                ends = (w.points[0], w.points[-1])
                fa = [i for i, q in enumerate(a) for r in ends if G.dist(q, r) <= 1e-9]
                fb = [i for i, q in enumerate(b) for r in ends if G.dist(q, r) <= 1e-9]
                if len(fa) != 1 or len(fb) != 1:
                    return None, msgs, done     # (cleanup joined it to another: not checked)
                got[fa[0]] = fb[0]
            return (got, new), msgs, done
        plain, _m, _done = run(False)
        if plain is None:
            return
        p.undo()
        swapped, msgs, done = run(True)
        if swapped is None and done:
            BC.CHECKED["bus swap joined by cleanup: skipped"] += 1
            return
        if swapped is None:
            assert any("Swap 1 and 3" in m or "Not landed" in m or "can't" in m
                       for m in msgs), "a swapped bus didn't land and said nothing: %r" % msgs
            BC.CHECKED["bus swap: no room, said"] += 1
            return
        got, new = swapped
        want = {i: plain[0][{0: 2, 2: 0}.get(i, i)] for i in range(3)}
        assert got == want, "phases 1 and 3 swapped landed %r, the plain bus %r" % (
            got, plain[0])
        for w in new:
            for o in new:
                if o is w:
                    continue
                for q in (w.points[0], w.points[-1]):
                    assert min(G.dist_to_segment(q, c, d) for c, d in zip(o.points, o.points[1:])) \
                        > 1e-6, "a swapped bus's wire ends on another at %r" % (q,)
                for c, d in zip(w.points, w.points[1:]):
                    for e_, f_ in zip(o.points, o.points[1:]):
                        u = (d[0] - c[0], d[1] - c[1])
                        x = (f_[0] - e_[0], f_[1] - e_[1])
                        if abs(u[0] * x[1] - u[1] * x[0]) > 1e-9 * (1 + abs(u[0]) + abs(u[1])) \
                                * (1 + abs(x[0]) + abs(x[1])):
                            continue
                        if G.dist_to_segment(e_, c, d) > 1e-9 and \
                                G.dist_to_segment(f_, c, d) > 1e-9 and \
                                G.dist_to_segment(c, e_, f_) > 1e-9:
                            continue
                        uu = u[0] ** 2 + u[1] ** 2
                        t = sorted(((r[0] - c[0]) * u[0] + (r[1] - c[1]) * u[1]) / uu
                                   for r in (e_, f_))
                        assert t[1] <= 1e-9 or t[0] >= 1 - 1e-9, \
                            "two wires of a swapped bus lie on each other"
        BC.CHECKED["bus swaps phases 1 and 3"] += 1

    def op_fp_label_hidden():
        # (0.26: "Footprint tag sizing not consistent when showing/hiding") a footprint's
        # label lines all hidden (the Footprint label menu's none), Footprint label height or
        # the sheet's scale changed meanwhile (text kept its size on paper, or not), then
        # shown again as its attributes window and the Properties panel show them: each line
        # the height it was; with Footprint label height changed, as that change puts every
        # footprint's label (on paper, its sheet's scale times its size, else the new height),
        # worked out here from the heights before and the sizes
        from kanzonascad import scalefit
        from kanzonascad import tags
        fs = [e for e in s.inserts() if tags.is_footprint(e) and not v.layer_locked(e.layer)
              and e.label_texts() and not e.fixed]
        if not fs:
            return
        f = rnd.choice(fs)
        label = f.label
        had = {k: t.height for k, t in f.label_texts()}
        sizes = {k: f.label_size(k)[0] for k in had}
        k0 = s.k()
        v.set_selection({f.id})
        win.acts["fp_label_none"].trigger()
        assert not s.entities[f.id].label, "Footprint label, none: still %r" % (
            s.entities[f.id].label)
        ho = float(p.settings.get("fp_label_height", 0.08))
        hn = ho
        if rnd.random() < 0.5:
            hn = rnd.choice([0.06, 0.08, 0.1, 0.125])
            with p.edit("Project properties") as ed:
                ed.project_settings({"fp_label_height": hn})
        if rnd.random() < 0.4 and s is not p.title_block:
            name, val = rnd.choice(scalefit.presets_like(s.scale_name))
            if 1.0 / val <= MAX_K:
                scalefit.apply(p, s, name, val, paper_text=False)
        cur = s.entities[f.id]
        with p.edit("Attributes") as ed:
            for sh, e in win.attribute_changes(p, s, cur, dict(cur.attrs), {"label": label}):
                ed.change(sh, e)
        now = {k: t.height for k, t in s.entities[f.id].label_texts()}
        want = dict(had) if hn == ho else {k: (sizes[k] or hn) * k0 for k in had}
        assert set(now) == set(want), "shown again: lines %r, not %r" % (sorted(now),
                                                                        sorted(want))
        for k in want:
            assert abs(now[k] - want[k]) <= 1e-9 * max(1.0, want[k]), \
                "footprint label line %s shown again %r tall, not %r" % (k, now[k], want[k])
        BC.CHECKED["footprint label lines hidden and shown again"] += 1

    def op_array():
        # (0.16.5: copies in rows and columns, or round a center: exactly where they go)
        sel = [e for e in some(rnd.randint(1, 3)) if not isinstance(e, (M.Wire, M.WireCross))]
        if not sel:
            return
        before = set(s.entities)
        v.set_selection({e.id for e in sel})
        v.run(C.ArrayCmd)
        if rnd.random() < 0.7:
            rows, cols = rnd.randint(1, 3), rnd.randint(1, 3)
            dr, dc = rnd.choice([-1, 1]) * rnd.randint(1, 8) * 0.25, \
                rnd.choice([-1, 1]) * rnd.randint(1, 8) * 0.25
            type_in(v, "R", str(rows), str(cols), "%.12g" % dr, "%.12g" % dc)
            shifts = [(c * dc, r * dr) for r in range(rows) for c in range(cols) if r or c]
        else:
            n = rnd.randint(2, 5)
            type_in(v, "P", fmt(pt()), str(n), "360")
            shifts = None
        finish()
        new = [e for i, e in s.entities.items() if i not in before]
        want = (len(shifts) if shifts is not None else n - 1) * len(sel)
        assert len(new) == want, "Array made %d objects, not %d" % (len(new), want)
        if shifts:
            def key(e):
                # (a ladder by its left rail's top: its copies are numbered on, their numbers
                # other widths)
                if isinstance(e, M.Ladder):
                    return e.a
                return e.pos if isinstance(e, M.Insert) else e.bbox()[:2]
            # (matched within a millionth, not rounded to six places: 0.1666625 and a hair
            # under it round apart, a copy's place a trillionth off was taken as wrong, CI
            # seed 334)
            got = sorted((e.kind, key(e)[0], key(e)[1]) for e in new)
            exp = sorted((e.kind, key(e)[0] + dx, key(e)[1] + dy)
                         for dx, dy in shifts for e in sel)
            left = list(got)
            for k, x, y in exp:
                hit = next((g for g in left if g[0] == k and abs(g[1] - x) <= 1e-6 and
                            abs(g[2] - y) <= 1e-6), None)
                assert hit is not None, "Array put no %s copy at %s (copies at %s)" % (
                    k, (x, y), [g[1:] for g in got if g[0] == k][:4])
                left.remove(hit)
            BC.CHECKED["array where they go"] += 1

    def op_array_edit():
        # (0.21: an array changed with Edit array as the owner would: a copy picked, a new
        # spacing typed, the rest kept with Enter: every copy still the array's lands where its
        # place in rows and columns puts it from the source as it is now, those that had left
        # the array stay where they were; worked out from the array's record and the sheet)
        from kanzonascad import arrays
        live = [aid for aid in s.arrays if arrays.alive(s, aid) and
                s.arrays[aid]["mode"] == "R" and arrays.members(s, aid)]
        if not live:
            return
        aid = rnd.choice(live)
        a = s.arrays[aid]
        have = arrays.members(s, aid)
        left = {j: s.entities[j].to_dict() for k, ids in a["items"].items()
                if int(k) not in have for j in ids if j in s.entities}
        pick = rnd.choice([j for ids in have.values() for j in ids])
        rows, cols = int(a["vals"][0]), int(a["vals"][1])
        dr = rnd.choice([-1, 1]) * rnd.randint(1, 8) * 0.25 * s.k()
        dc = rnd.choice([-1, 1]) * rnd.randint(1, 8) * 0.25 * s.k()
        v.set_selection({pick})
        v.run(C.ArrayEditCmd)
        if v.cmd is None:
            return
        v.enter()
        v.enter()
        v.input_text("%.12g" % dr)
        if v.cmd is not None:
            v.input_text("%.12g" % dc)
        finish()
        src = [s.entities[i] for i in a["source"]]
        now = s.arrays.get(aid)
        assert now is not None, "Edit array lost the array"
        offs = arrays.offsets("R", [rows, cols, dr, dc])
        for k, ids in now["items"].items():
            for e, j in zip(src, ids):
                want = arrays.place(e, offs[int(k)])
                assert j in s.entities and arrays._same(s.entities[j], want), \
                    "Edit array left copy %s of %s elsewhere" % (k, e.kind)
        for j, d in left.items():
            assert j in s.entities and s.entities[j].to_dict() == d, \
                "Edit array moved a copy that had left the array"
        BC.CHECKED["array edited where they go"] += 1

    def op_offset():
        # (0.16.5: a copy a set distance away, smaller or bigger)
        a = pt()
        w, h = rnd.randint(2, 8) * 0.25, rnd.randint(2, 8) * 0.25
        kind = rnd.choice(["rect", "line", "circle"])
        with p.edit("to offset") as ed:
            if kind == "rect":
                e = ed.add(s, M.Polyline([a, (a[0] + w, a[1]), (a[0] + w, a[1] + h),
                                          (a[0], a[1] + h)], True))
                on, inside = (a[0] + w / 2, a[1]), (a[0] + w / 2, a[1] + h / 2)
                outside = (a[0] + w / 2, a[1] - 1)
            elif kind == "line":
                e = ed.add(s, M.Line(a, (a[0] + w, a[1])))
                on, inside, outside = (a[0] + w / 2, a[1]), (a[0] + w / 2, a[1] + 1), \
                    (a[0] + w / 2, a[1] - 1)
            else:
                e = ed.add(s, M.Circle(a, w))
                on, inside, outside = (a[0] + w, a[1]), a, (a[0] + 3 * w, a[1])
        d = rnd.randint(1, 3) * 0.125
        side = rnd.choice([inside, outside])
        before = set(s.entities)
        v.set_selection(set())
        v.run(C.OffsetCmd)
        type_in(v, "%.12g" % d)
        v.cmd.pick(on)
        if v.cmd is not None and v.cmd.ent is not None and v.cmd.ent.id == e.id:
            v.cmd.point(side)
        else:
            finish()
            return                      # (another object nearer the pick)
        finish()
        new = [x for i, x in s.entities.items() if i not in before]
        out = side is outside
        if kind == "rect":
            if not out and (2 * d >= min(w, h) - 1e-9):
                assert not new, "a rectangle offset past its middle was made"
                return
            k = d if out else -d
            exp = (a[0] - k, a[1] - k, a[0] + w + k, a[1] + h + k)
            assert len(new) == 1 and all(abs(x - y) < 1e-9 for x, y in zip(new[0].bbox(), exp)), \
                "offset rectangle %s, not %s" % (new and new[0].bbox(), exp)
        elif kind == "line":
            exp = a[1] + (-d if out else d)
            assert len(new) == 1 and abs(new[0].p1[1] - exp) < 1e-9 and \
                abs(new[0].p2[1] - exp) < 1e-9, "offset line not %s away" % d
        else:
            exp = w + d if out else w - d
            assert len(new) == 1 and abs(new[0].radius - exp) < 1e-9, \
                "offset circle radius %s, not %s" % (new and new[0].radius, exp)
        BC.CHECKED["offset where it goes"] += 1

    def op_mid_grip():
        # (0.16.5: a rectangle's side dragged by its middle grip: still a rectangle, that side
        # moved straight out or in by how far the grip went across it)
        rects = [e for e in s.entities.values() if type(e) is M.Polyline and e.closed and
                 len(e.points) == 4 and all((abs(q[0] - r[0]) < 1e-9 or abs(q[1] - r[1]) < 1e-9)
                                            and G.dist(q, r) > 1e-6
                                            for q, r in zip(e.points, e.points[1:] + e.points[:1]))]
        # (four sides of some length: a rectangle squashed flat, a side dragged onto the one
        # across, has sides of none, and no way across them to move, seed 31)
        if not rects:
            return
        e = rnd.choice(rects)
        k = rnd.randrange(4)
        to = pt()
        v.set_selection(set())
        v.run(C.GripCmd, e, 4 + k)
        v.input_text(fmt(to))
        finish()
        got = s.entities[e.id]
        a, b = e.points[k], e.points[(k + 1) % 4]
        horiz = abs(a[1] - b[1]) < 1e-9
        for i, q in enumerate(got.points):
            if i in (k, (k + 1) % 4):
                assert (abs(q[1] - to[1]) < 1e-9) if horiz else (abs(q[0] - to[0]) < 1e-9), \
                    "a side dragged to %s went to %s" % (to, q)
            else:
                assert q == e.points[i], "a middle grip moved another corner"
        BC.CHECKED["middle grip"] += 1

    def op_number():
        # (0.16.6: texts on a grid of rows and columns, numbered: each takes the number its
        # place in the order gives it, worked out from the grid the battery made)
        from kanzonascad import numbering as N
        rows, cols = rnd.randint(1, 4), rnd.randint(1, 3)
        a = pt()
        dx, dy = rnd.choice([1.0, 1.5, 2.0]), rnd.choice([0.25, 0.5])
        grid = {}
        with p.edit("texts to number") as ed:
            for r in range(rows):
                for c in range(cols):
                    word = rnd.choice(["X", "TERM", "Relay 1 Common", "1"])
                    t = ed.add(s, M.Text((a[0] + c * dx, a[1] - r * dy), word, 0.1))
                    grid[t.id] = (r, c, word)
        how = {"sequence": rnd.choice(N.SEQUENCES), "prefix": rnd.choice(["", "S", "TB1-"]),
               "suffix": rnd.choice(["", "A"]), "start": "1", "step": rnd.choice([1, 2]),
               "digits": rnd.choice([0, 2]), "letter_start": "A",
               "order": rnd.choice(N.ORDERS), "mode": rnd.choice(N.MODES)}
        if how["sequence"] in ("letter", "lower"):
            how["start"] = "A" if how["sequence"] == "letter" else "a"
        win.ask_numbering = lambda n: dict(how)
        try:
            v.set_selection(set(grid))
            v.run(C.NumberCmd)
        finally:
            del win.ask_numbering
            finish()
        names = N.labels(rows * cols, how["sequence"], how["start"], how["step"],
                         how["digits"], how["prefix"], how["suffix"], how["letter_start"])
        for i, (r, c, word) in grid.items():
            k = c * rows + r if how["order"] == "down" else r * cols + c
            want = N.apply_to(word, names[k], how["mode"])
            got = s.entities[i].text
            assert got == want, "Number texts gave row %d column %d %r, not %r (%s)" % (
                r, c, got, want, how["order"])
        BC.CHECKED["number texts"] += 1

    def op_line():
        v.run(C.LineCmd)
        type_in(v, fmt(pt()), fmt(pt()))
        finish()

    def op_text():
        v.run(C.TextCmd)
        type_in(v, fmt(pt()))
        if v.cmd is not None:
            v.input_text("T%d" % rnd.randint(1, 99))
        finish()

    def op_move(cls=C.MoveCmd):
        sel = some()
        if not sel:
            return
        v.set_selection({e.id for e in sel})
        v.run(cls)
        if v.cmd is not None:
            a = pt()
            v.input_text(fmt(a))
            if v.cmd is not None:
                v.input_text(fmt((a[0] + rnd.choice([-1, 0, 1]) * 0.5,
                                  a[1] + rnd.choice([-1, 0, 1]) * 0.5)))
        finish()

    def op_move_area():
        # (0.18.2: a crossing box over a part of the drawing, then Move typed, every object
        # snap on, as the owner moves part of a panel: "one of my vfds disappeared"): every
        # object selected is still there, moved exactly as typed (a wire may be joined into
        # another by the cleanup, so only the rest is checked one by one)
        from kanzonascad import osnap as OS
        ents = [e for e in s.entities.values() if BC.selectable(v, e)]
        if len(ents) < 4:
            return
        a, b = rnd.choice(ents).bbox(), rnd.choice(ents).bbox()
        box = (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))
        sel = {e.id for e in s.query(box) if BC.selectable(v, e) and e.crosses(box)}
        if not sel:
            return
        before = {i: s.entities[i] for i in sel}
        k = s.k()
        d = (rnd.choice([-1, 0, 1]) * 0.5 * k, rnd.choice([-1, 1]) * 0.5 * k)
        modes, on = v.osnap_modes, v.osnap_on
        v.osnap_modes, v.osnap_on = {m for m, _n, _t in OS.MODES}, True
        try:
            v.set_selection(sel)
            v.run(C.MoveCmd)
            if v.cmd is None:
                return
            base = rnd.choice(list(before.values())).bbox()[:2]
            v.input_text(fmt(base))
            if v.cmd is not None:
                v.input_text("@%r,%r" % d)
            finish()
        finally:
            v.osnap_modes, v.osnap_on = modes, on
        for i, e in before.items():
            if isinstance(e, (M.Wire, M.WireCross)):
                continue
            now = s.entities.get(i)
            assert now is not None, "moving %d objects, %s %d went" % (
                len(sel), type(e).__name__, i)
            if isinstance(e, M.Insert):
                # (a symbol by where it is: a contact block moved off its operator shows its
                # tag again, and its box grows, the battery's seed 386, as the drag check's
                # seed 379: its position moved as typed, not turned, flipped or scaled)
                assert all(abs(now.pos[j] - e.pos[j] - d[j]) <= 1e-6 * max(1.0, abs(e.pos[j]))
                           for j in range(2)), "%s %d (%s) moved %s, not %s" % (
                    type(e).__name__, i, e.block, (now.pos[0] - e.pos[0],
                                                   now.pos[1] - e.pos[1]), d)
                assert (now.angle, now.mirror, now.scale, now.block) == \
                    (e.angle, e.mirror, e.scale, e.block), "moving %s %d turned or changed it" % (
                        e.block, i)
                continue
            if isinstance(e, M.Ladder):
                # (a ladder by its rails: moved past another, it is numbered on from that one,
                # and numbers of other widths make its box another width, seed 4401; its rails
                # moved as typed, its rungs and spacing as they were)
                for q0, q1 in ((e.a, now.a), (e.b, now.b)):
                    assert all(abs(q1[j] - q0[j] - d[j]) <= 1e-6 * max(1.0, abs(q0[j]))
                               for j in range(2)), "Ladder %d moved %s, not %s" % (
                        i, (q1[0] - q0[0], q1[1] - q0[1]), d)
                assert (now.rungs, now.spacing) == (e.rungs, e.spacing), \
                    "moving Ladder %d changed its rungs" % i
                if now.numbers() != e.numbers():
                    BC.CHECKED["a ladder moved past another numbered on from it"] += 1
                continue
            b0, b1 = e.bbox(), now.bbox()
            assert all(abs(b1[j] - b0[j] - d[j % 2]) <= 1e-6 * max(1.0, abs(b0[j]))
                       for j in range(4)), "%s %d moved %s, not %s" % (
                type(e).__name__, i, (b1[0] - b0[0], b1[1] - b0[1]), d)
        BC.CHECKED["an area moved, everything in it"] += 1

    def op_copy():
        op_move(C.CopyCmd)

    def op_rotate():
        sel = some(2)
        if not sel:
            return
        v.set_selection({e.id for e in sel})
        v.run(C.RotateCmd)
        if v.cmd is not None:
            v.input_text(fmt(pt()))
            if v.cmd is not None:
                v.input_text(rnd.choice(["90", "180", "270"]))
        finish()

    def op_erase():
        sel = some(2)
        if sel:
            v.set_selection({e.id for e in sel})
            v.run(C.EraseCmd)
        finish()

    def op_trim():
        ws = s.wires()
        if not ws:
            return
        w = rnd.choice(ws)
        a, b = w.points[0], w.points[1]
        v.run(C.TrimWireCmd)
        v.cmd.pick(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
        finish()

    def length(e):
        import math
        if isinstance(e, M.Line):
            return G.dist(e.p1, e.p2)
        if isinstance(e, M.Polyline):
            return sum(G.dist(a, b) for a, b in e.segments())
        if isinstance(e, M.Arc):
            return math.radians(G.sweep(e.start, e.end)) * e.radius
        if isinstance(e, M.Circle):
            return 2 * math.pi * e.radius
        return 0.0

    def op_trim_plain():
        ents = list(s.entities.values())
        if not ents:
            return
        e = rnd.choice(ents)
        x0, y0, x1, y1 = e.bbox()
        q = ((x0 + x1) / 2, (y0 + y1) / 2)
        if isinstance(e, (M.Line, M.Polyline)) and not isinstance(e, M.Wire):
            # (on it: the middle of one of its pieces)
            a, b = e.segments()[0] if isinstance(e, M.Polyline) else (e.p1, e.p2)
            q = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        v.run(C.TrimCmd)
        hit = v.pick_entity(q)
        lit = v.cmd.hover_parts(hit, q) if hit is not None else None
        before = set(s.entities)
        v.cmd.pick(q)
        finish()
        if hit is not None and lit and isinstance(hit, (M.Line, M.Polyline, M.Arc, M.Circle)) \
                and hit.id not in s.entities:
            # (0.16.5: what lights up as the cursor goes over it is what is cut away: the rest
            # is what is left)
            kept = sum(length(x) for i, x in s.entities.items() if i not in before)
            whole, cut = length(hit), sum(length(x) for x in lit)
            assert abs(kept + cut - whole) <= 1e-6 * max(1.0, whole), \
                "Trim lit %.6g of %.6g and left %.6g: %r at %r, lit %r, left %r" % (
                    cut, whole, kept, hit, q, lit,
                    [x for i, x in s.entities.items() if i not in before])
            BC.CHECKED["trim lights what it cuts"] += 1

    def op_wire_xref():
        # (0.17.5) a wire's number typed in the Wire number window, as a double-click opens it:
        # one another wire has (a cross-reference: Source, Destination or just the same
        # number) or a new one, locked or not. Source or Destination: a pair of off-sheet
        # connectors of one new name on the two open ends (out where it leaves, in where it
        # arrives) and one number on both; the same number: as typed; the lock as ticked
        if not wirenums.enabled(p):
            return
        from kanzonascad import wires as W
        ws = [w for w in s.wires() if w.num and any(
            not W.connects_at(s, q, exclude=w.id) for q in (w.points[0], w.points[-1]))]
        if len(ws) < 2:
            return
        a, b = rnd.sample(ws, 2)
        if wirenums.group_of(p, s, a)[0] == wirenums.group_of(p, s, b)[0]:
            return
        num = rnd.choice([b.num, b.num, "9%03d" % rnd.randint(0, 999)])
        if num != b.num and any(w.num == num for sh in p.sheets for w in sh.wires()):
            # (a "new" number some wire has already: it is another wire's number, and is asked
            # about as one, seed 2509 step 1138)
            return
        lock = rnd.random() < 0.7
        if num == a.num:
            # (it has that number already: two groups kept with one number on purpose, "just
            # the same number" earlier; typing it again changes nothing and asks nothing,
            # seed 3262)
            return
        how = rnd.choice(["source", "destination", "same", None])
        # (by sheet and id: ids are a sheet's own, seed 4103)
        links = {(sh.id, e.id) for sh in p.sheets for e in sh.inserts()
                 if e.defn is not None and e.defn.wiring == "link"}
        win.ask_wire_number = lambda n, tap_of=None, own=False, locked=False: (num, own, lock)
        asked = []
        win.ask_cross_reference = lambda n, where: asked.append(n) or how
        try:
            win.edit_wire_number(s.entities[a.id])
        finally:
            win.__dict__.pop("ask_wire_number", None)
            win.__dict__.pop("ask_cross_reference", None)
        new = [e for sh in p.sheets for e in sh.inserts()
               if e.defn is not None and e.defn.wiring == "link" and (sh.id, e.id) not in links]
        got = s.entities.get(a.id)
        if num != b.num or got is None:
            assert not new, "connectors placed for a number no other wire had"
            return
        assert asked == [num], "a number another wire has wasn't asked about: %r" % asked
        if how in ("source", "destination"):
            assert len(new) == 2 and new[0].attrs["TAG"] == new[1].attrs["TAG"], \
                "a cross-reference didn't place one pair of connectors: %r" % (
                    [(e.block, e.attrs.get("TAG")) for e in new])
            mine = [e for e in new if e.id in s.entities and
                    any(G.dist(q, r) < 1e-9 for _n, q in e.pin_points()
                        for r in (got.points[0], got.points[-1]))]
            want = "Source arrow" if how == "source" else "Destination arrow"
            assert any(e.block == want for e in mine), "%s: no %s on the wire" % (how, want)
            other = s.entities.get(b.id)
            assert other is not None and got.num == other.num == num, \
                "a cross-reference left two numbers: %s, %s" % (got.num, other and other.num)
            # (unticked, it is locked when numbering would change it: the typed number stays)
            assert got.num_lock or not lock, "the lock wasn't as ticked"
            BC.CHECKED["cross-reference by a number typed"] += 1
        elif how == "same":
            # (locked whatever was ticked: an unlocked duplicate would be numbered again)
            assert not new and got.num == num and got.num_lock, \
                "just the same number %s (locked %s): the wire has %s, locked %s; %d new " \
                "connector(s)" % (num, lock, got.num, got.num_lock, len(new))
            BC.CHECKED["the same number, as typed"] += 1
        else:
            assert not new and got.num == a.num, "cancelled, yet the number changed"

    def op_sig_arrows():
        # (0.18) Source/destination arrows through the command: a click near one wire's open
        # end, then another's: a Source arrow and a Destination arrow of one name on those
        # ends, one wire with the source's number
        from kanzonascad import wires as W
        def opens(w):
            return [q for q in (w.points[0], w.points[-1])
                    if not W.connects_at(s, q, exclude=w.id)]
        ws = [w for w in s.wires() if opens(w) and G.dist(w.points[0], w.points[-1]) > 0.5]
        if len(ws) < 2:
            return
        a, b = rnd.sample(ws, 2)
        if wirenums.group_of(p, s, a)[0] == wirenums.group_of(p, s, b)[0]:
            return
        qa, qb = rnd.choice(opens(a)), rnd.choice(opens(b))
        num = a.num
        before = {e.id for e in s.inserts()}
        v.run(C.SignalArrowsCmd)
        for q in (qa, qb):
            if v.cmd is not None and getattr(v.cmd, "pick", None):
                v.cmd.pick(q)
        finish()
        new = [e for e in s.inserts() if e.id not in before and e.block in wirenums.ARROWS]
        if not new:
            return                  # (a pick took another wire there: nothing placed, checked)
        assert len(new) == 2 and new[0].attrs["TAG"] == new[1].attrs["TAG"], \
            "arrows not a pair: %r" % [(e.block, e.attrs.get("TAG")) for e in new]
        at = {e.block: e.pin_points()[0][1] for e in new}
        assert G.dist(at["Source arrow"], qa) < 1e-9 and \
            G.dist(at["Destination arrow"], qb) < 1e-9, \
            "arrows not on the ends clicked: %r, %r %r" % (at, qa, qb)
        if num and wirenums.enabled(p):
            nb = [w.num for w in s.wires() if w.touches(qb)]
            assert nb and nb[0] == num, "the destination took %r, not the source's %s" % (
                nb, num)
        # (0.18: their text outside them, off their wires)
        from kanzonascad import xrefs as X
        texts = X.texts(p, s)
        num_now = (s.entities[a.id].num if a.id in s.entities else None) \
            if wirenums.enabled(p) else None
        for e in new:
            pin = e.pin_points()[0][1]
            ws = [w for w in s.wires() if w.touches(pin)]
            if not ws:
                continue
            # (its own text: the arrow pair's two texts can be alike and big on a scaled
            # sheet, where the other's may be the nearer one: any text of the arrow's kind
            # beside it, clear of the arrow and of its wire, will do)
            eb = e.bbox()
            # (its text can go a few heights farther out, clear of a wire that wraps round
            # it: xrefs._outside)
            reach = 8.0 * float(p.settings.get("xref_height", 0.065)) * s.k()

            def beside(box):
                return box[0] <= eb[2] + reach and box[2] >= eb[0] - reach and \
                    box[1] <= eb[3] + reach and box[3] >= eb[1] - reach

            def clear(box):
                if box[0] < eb[2] and box[2] > eb[0] and box[1] < eb[3] and box[3] > eb[1]:
                    return False
                return not any(G.segment_hits_rect(q, r, box)
                               for q, r in zip(ws[0].points, ws[0].points[1:]))
            mine = [t for t in texts if beside(t.bbox()) and
                    (not num_now or t.text.startswith("%s / " % num_now))]
            assert mine, "no text beside the %s at %r" % (e.block, pin)
            assert any(clear(t.bbox()) for t in mine), \
                "the text of a %s lies on it or on its wire: %r, the arrow %r, its wire %r" % (
                    e.block, [(t.text, t.bbox()) for t in mine], eb, ws[0].points)
        BC.CHECKED["source and destination arrows"] += 1

    def op_update_numbers():
        # (0.18) Update numbers and cross-references, as the window answers: tags, wires,
        # cross-references, renumbered or kept, on this sheet or every sheet, one step; then
        # every unlocked device on those sheets has a tag of its sheet's page, none twice
        o = {"tags": rnd.random() < 0.8, "wires": rnd.random() < 0.8,
             "xrefs": rnd.random() < 0.8, "renumber": rnd.random() < 0.5,
             "sheets": [s] if rnd.random() < 0.5 else list(p.sheets)}
        win.ask_update_numbers = lambda project, sheet: o
        n0 = len(p.undo_stack)
        try:
            win.update_numbers()
        finally:
            win.__dict__.pop("ask_update_numbers", None)
        assert len(p.undo_stack) - n0 <= 1, "Update numbers took more than one step"
        if o["tags"]:
            seen = {}
            for sh in o["sheets"]:
                if sh is p.title_block:
                    continue
                page = p.sheet_number(sh)
                for e in sh.entities.values():
                    if tags_mod.is_device(e) and not tags_mod.locked(e):
                        # (a tag of the other standard's letters is kept: its own)
                        got = tags_mod.split(e.attrs.get("TAG", ""),
                                             tags_mod.tag_prefix(p, e))
                        assert got is not None and got[0] == page, \
                            "%s on sheet %s after Update numbers" % (e.attrs.get("TAG"), page)
                        k = e.attrs["TAG"]
                        assert k not in seen, "%s twice after Update numbers" % k
                        seen[k] = 1
            BC.CHECKED["Update numbers: tags of their page, none twice"] += 1
        if o["tags"] and o["renumber"]:
            # renumbered, each page's unlocked devices of a prefix hold the lowest counts no
            # other device has (worked out here from the devices alone: a footprint or a
            # power section carrying a device's tag holds no number)
            for sh in o["sheets"]:
                if sh is p.title_block:
                    continue
                page = p.sheet_number(sh)
                mine = [e for e in sh.entities.values()
                        if tags_mod.is_device(e) and not tags_mod.locked(e)]
                # (by the project's prefixes: an IEC project's letters, K for its relays,
                # timers and PLC modules alike; a count held by any device whose tag is made
                # of the prefix)
                for prefix in {tags_mod.prefix_for(p, e.defn) for e in mine}:
                    held = set()
                    for sx in p.sheets:
                        for e in sx.entities.values():
                            if not tags_mod.is_device(e) or \
                                    tags_mod.tag_prefix(p, e) != prefix or \
                                    (sx is sh and not tags_mod.locked(e)):
                                continue
                            got = tags_mod.split(e.attrs.get("TAG", ""), prefix)
                            if got and got[0] == page:
                                held.add(got[1])
                    group = [e for e in mine if tags_mod.prefix_for(p, e.defn) == prefix]
                    want, n = [], 0
                    while len(want) < len(group):
                        n += 1
                        if n not in held:
                            want.append(n)
                    got = sorted(tags_mod.split(e.attrs["TAG"], prefix)[1] for e in group)
                    assert got == want, "renumbered %s on sheet %s: %s, not %s" % (
                        prefix, page, got, want)
            BC.CHECKED["renumbered: the lowest free numbers"] += 1
            # renumbered again, the same tags: a footprint carrying its device's tag held the
            # number as if a device of its own, so a page went 204, 205, then back to 201
            # (the owner, Nov 2026, "I never know what they're going to do")
            def device_tags():
                return {(sh.id, e.id): e.attrs.get("TAG") for sh in o["sheets"]
                        for e in sh.entities.values() if tags_mod.is_device(e)}
            before = device_tags()
            win.ask_update_numbers = lambda project, sheet: o
            try:
                win.update_numbers()
            finally:
                win.__dict__.pop("ask_update_numbers", None)
            after = device_tags()
            moved = {k: (before[k], after.get(k)) for k in before if before[k] != after.get(k)}
            assert not moved, "renumbered again, tags changed: %r" % sorted(moved.values())[:6]
            BC.CHECKED["renumbered again, the same tags"] += 1

    def op_stretch():
        # (0.18) STRETCH through the command: a crossing window over some wire ends, moved;
        # every wire end inside (of a wire not wholly inside) moved by exactly that, one step
        ws = s.wires()
        if not ws:
            return
        w = rnd.choice(ws)
        q = rnd.choice([w.points[0], w.points[-1]])
        k = s.k()
        h = rnd.choice([0.3, 1.0, 2.5]) * k
        rect = (q[0] - h, q[1] - h, q[0] + h, q[1] + h)
        d = rnd.choice([(0.5, 0.0), (-0.5, 0.0), (0.0, 0.5), (0.0, -1.0), (1.0, 0.5)])
        d = (d[0] * k, d[1] * k)
        before = {x.id: x for x in s.query(rect) if isinstance(x, M.Wire)}
        n0 = len(p.undo_stack)
        v.run(C.StretchCmd)
        type_in(v, fmt(rect[:2]), fmt(rect[2:]), fmt(q), fmt((q[0] + d[0], q[1] + d[1])))
        finish()
        if len(p.undo_stack) == n0:
            return
        assert len(p.undo_stack) == n0 + 1, "Stretch took more than one step"

        def inside(r):
            return rect[0] - 1e-9 <= r[0] <= rect[2] + 1e-9 and \
                rect[1] - 1e-9 <= r[1] <= rect[3] + 1e-9
        for x in before.values():
            got = s.entities.get(x.id)
            if got is None or all(inside(r) for r in x.points):
                continue
            for i in (0, -1):
                if inside(x.points[i]):
                    want = (x.points[i][0] + d[0], x.points[i][1] + d[1])
                    # (a wire may be joined to another after: its end is still a wire end
                    # there, or on a pin it was taken to)
                    assert any(G.dist(r, want) < 1e-6 for y in s.wires()
                               for r in (y.points[0], y.points[-1])) or \
                        wires.pins_on(s, want) or pulled_on(want), \
                        "Stretch: an end at %s didn't go to %s" % (
                            x.points[i], want)
        BC.CHECKED["stretch moves the ends in the window"] += 1

    def pulled_on(want):
        # (0.18.3, the owner's choice: an end left less than wires.PULL from a pin or another
        # wire is put on it, the battery sweep, seed 1803; so an end may sit that near where
        # it was sent, but only joined there: on a pin, or on another wire)
        for y in s.wires():
            for r in (y.points[0], y.points[-1]):
                if G.dist(r, want) < wires.PULL and (wires.pins_on(s, r) or any(
                        o.id != y.id and o.distance(r) <= wires.TOL
                        for o in s.query((r[0] - 1e-6, r[1] - 1e-6, r[0] + 1e-6, r[1] + 1e-6))
                        if isinstance(o, M.Wire))):
                    BC.CHECKED["an end pulled on, joined"] += 1
                    return True
        return False

    def op_grips():
        # (0.18) several grips picked with Shift (the view's picked grips), one of them
        # dragged: every picked grip moves the same way
        ws = s.wires()
        if len(ws) < 2:
            return
        pick = rnd.sample(ws, min(len(ws), rnd.randint(2, 3)))
        grips = [(w, rnd.choice([0, len(w.points) - 1])) for w in pick]
        start = {(w.id, i): w.grips()[i] for w, i in grips}
        k = s.k()
        d = (rnd.choice([-1, 1]) * 0.5 * k, rnd.choice([0, 1]) * 0.5 * k)
        v.set_selection({w.id for w in pick})
        v.picked_grips = {(w.id, i) for w, i in grips}
        w0, i0 = grips[0]
        v.run(C.GripCmd, w0, i0, [(w, i) for w, i in grips])
        g = start[(w0.id, i0)]
        type_in(v, fmt((g[0] + d[0], g[1] + d[1])))
        finish()
        for (wid, i), g in start.items():
            want = (g[0] + d[0], g[1] + d[1])
            assert any(G.dist(r, want) < 1e-6 for y in s.wires() for r in y.points) or \
                wires.pins_on(s, want) or pulled_on(want), \
                "a picked grip at %s didn't go to %s" % (g, want)
        BC.CHECKED["picked grips move together"] += 1

    def op_lock_numbers():
        # (0.18) Lock numbers..., as the window answers: on the selected wires, or this sheet
        o = {"lock": rnd.random() < 0.6, "wires": True, "tags": rnd.random() < 0.7,
             "sheets": None if rnd.random() < 0.5 else [s]}
        ws = s.wires()
        if not ws:
            return
        chosen = rnd.sample(ws, min(len(ws), rnd.randint(1, 4)))
        v.set_selection({w.id for w in chosen})
        win.ask_lock_numbers = lambda project, sheet, n: o
        try:
            win.lock_numbers()
        finally:
            win.__dict__.pop("ask_lock_numbers", None)
        target = chosen if o["sheets"] is None else s.wires()
        for w in target:
            got = s.entities.get(w.id)
            if got is not None and got.num:
                assert got.num_lock == o["lock"], "wire %s %slocked after %s (%s)" % (
                    got.num, "" if got.num_lock else "un", "Lock" if o["lock"] else "Unlock",
                    _number_state(p, s, got))
        BC.CHECKED["Lock numbers as asked"] += 1

    def op_number_bus():
        # (0.18) numbering along the wires: a disconnect and a bus off on its own, three
        # breakers dropped off it, the bus running right or left from the disconnect; Numbering
        # source on the disconnect, Renumber sheet: the breakers count away from it along the
        # bus, whichever way it runs
        o = clear_of_drawing(s.k())
        if o is None:
            return
        lib_ds, lib_cb = lib.get("symbol", "Disconnect 3-pole"), lib.get("symbol",
                                                                        "Circuit breaker 3-pole")
        way = rnd.choice([1, -1])
        with p.edit("a bus to number") as ed:
            for d in (lib_ds, lib_cb):
                if d.name not in p.blocks:
                    ed.block(d)
            ds = M.Insert(lib_ds.name, o, 0.0 if way > 0 else 180.0, defn=p.blocks[lib_ds.name])
            ds = ed.add(s, ds.copy(attrs=tags_mod.new_attrs(p, s, ds.defn, {})))
            ends = sorted((q for n, q in ds.pin_points() if n.startswith("T")),
                          key=lambda q: -q[1])
            for q in ends:
                ed.add(s, M.Wire([q, (q[0] + way * 9.0, q[1])]))
            cbs = []
            for j in range(3):
                x = ends[0][0] + way * (2.0 + 2.5 * j)
                e = M.Insert(lib_cb.name, (0.0, 0.0), 270.0, defn=p.blocks[lib_cb.name])
                q = dict(e.pin_points())
                e = e.moved(x - q["L1"][0], ends[-1][1] - 2.0 - q["L1"][1])
                # (tagged as Insert tags a device: CB? of this page, its own id)
                e = ed.add(s, e.copy(attrs=tags_mod.new_attrs(p, s, e.defn, {})))
                q = dict(e.pin_points())
                for i in range(3):
                    lq = q["L%d" % (i + 1)]
                    ed.add(s, M.Wire([(lq[0], ends[i][1]), lq]))      # (a drop)
                cbs.append(e)
        if any(len(dict(e.pin_points())) < 6 for e in cbs):
            return
        v.center, v.scale = ds.pos, max(v.scale, 40.0 / s.k())
        v.run(C.NumberSourceCmd)
        if v.cmd is not None:
            v.cmd.pick(ds.pos)
        finish()
        if s.number_from != ds.id:
            return                      # (a pick there took another symbol: not checked)
        with p.edit("Renumber sheet") as ed:
            tags_mod.renumber_sheet(ed, p, s)
        got = [tags_mod.split(s.entities[e.id].attrs.get("TAG", ""), "CB") for e in cbs]
        if all(g is not None for g in got) and all(not tags_mod.locked(s.entities[e.id])
                                                   for e in cbs):
            counts = [g[1] for g in got]
            assert counts == sorted(counts), \
                "along the bus (running %s) the breakers got %s" % (
                    "right" if way > 0 else "left", [s.entities[e.id].attrs["TAG"] for e in cbs])
            BC.CHECKED["numbering follows the bus"] += 1
        with p.edit("order back") as ed:
            ed.sheet_meta(s, number_order="across", number_from=None)

    def op_tap():
        # (0.17.2: a wire drawn off the middle of another asks; 0.18.3: Enter numbers it as
        # the project's tap numbers say (the same, the wire's with -1, or its own), S keeps
        # the wire's number, N gives it one of its own; worked out from the numbers after. On
        # a wire of its own, just past the drawing: what the tap means is then known)
        if not wirenums.enabled(p):
            return
        if rnd.random() < 0.2:
            with p.edit("tap numbers") as ed:
                ed.project_settings({"tap_numbers": rnd.choice(["same", "suffix", "own"])})
        if rnd.random() < 0.2:
            # (0.22.4: how a tap's number ends, the project's and now and then a sheet's own)
            with p.edit("tap style") as ed:
                ed.project_settings({"tap_style": rnd.choice(M.TAP_STYLES)})
                if rnd.random() < 0.4:
                    ed.sheet_meta(s, tap_style=rnd.choice(M.TAP_STYLES + (None,)))
        mode = wirenums.tap_mode(p)
        k = s.k()
        o = clear_of_drawing(k)
        if o is None:
            return
        a, b = o, (o[0] + 4.0 * k, o[1])
        with p.edit("a wire to tap") as ed:
            w = ed.add(s, M.Wire([a, b]))
        m = (o[0] + 2.0 * k, o[1])
        to = (m[0], m[1] + rnd.choice([-1, 1]) * 1.5 * k)
        v.run(C.WireCmd)
        v.input_text(fmt(m))
        if v.cmd is not None:
            v.input_text(fmt(to))
        if v.cmd is not None and v.cmd.tapped is None:
            v.cmd.enter()
        asked = v.cmd is not None and v.cmd.tapped is not None
        assert asked, "a wire drawn off another's middle didn't ask about its number"
        said = rnd.choice(["N", "S", ""])
        if said:
            v.input_text(said)
        else:
            v.enter()
        finish()
        tap = [x for x in s.wires() if x.touches(to) and x.touches(m)]
        main = s.entities.get(w.id)
        assert len(tap) == 1 and main is not None, "the tap or the wire it taps is gone"
        if not said and rnd.random() < 0.3:
            # (0.22.4: the tap's own style, chosen in its Wire number window)
            pick = rnd.choice(M.TAP_STYLES + ("",))
            win.ask_wire_number = lambda n, tap_of=None, own="", locked=False: (
                n, own, locked, pick)
            try:
                win.edit_wire_number(tap[0])
            finally:
                win.__dict__.pop("ask_wire_number", None)
            tap = [x for x in s.wires() if x.touches(to) and x.touches(m)]
            assert len(tap) == 1 and tap[0].tap_style == pick, \
                "a tap's style not kept: %r, not %r" % (tap and tap[0].tap_style, pick)
            BC.CHECKED["tap style chosen for one wire"] += 1
        how = {"N": "own", "S": "same"}.get(said, mode)
        if main.num and tap[0].num:
            # (the wire just drawn taps nothing: its tap is one level down, the first: -1, a
            # or -a as the tap's own style says, else its sheet's, else the project's)
            style = tap[0].tap_style or s.tap_style or p.settings.get("tap_style") or "-1"
            want = {"same": main.num, "suffix": main.num + style}
            if how == "own":
                assert tap[0].num != main.num, "a tap with its own number: %s, %s" % (
                    tap[0].num, main.num)
            else:
                assert tap[0].num == want[how], "a tap (%s, %r typed) numbered %s off %s" % (
                    mode, said, tap[0].num, main.num)
            BC.CHECKED["tap numbered as asked"] += 1
            if how == "suffix":
                BC.CHECKED["tap numbered -1, a or -a off the wire"] += 1

    def op_wire_size():
        # (0.18.2: Wire size: a wire clicked given a gauge of its own, or the layer's again;
        # the wire layer preset added now and then, and a layer of it made current, so wires
        # are drawn on it, two-color ones striped)
        if rnd.random() < 0.15:
            from kanzonascad import wirelayers
            win.ask_wire_layer_groups = lambda: rnd.sample(wirelayers.preset_groups(),
                                                           rnd.randint(1, 4))
            win.acts["wire_layers"].trigger()
            have = [n for n in p.layers if wirelayers.is_preset(n)]
            if have:
                pick = rnd.choice(have + ["WIRES"])
                C.set_wire_layer(v, pick)
                assert C.wire_layer(v) == pick, (pick, C.wire_layer(v))
                C.set_wire_layer(v, "0")
                BC.CHECKED["wire layers added, wires go on them"] += 1
            return
        ws = [w for w in s.wires() if w.length() > 0.5]
        if not ws:
            return
        w = rnd.choice(ws)
        q, _i = w.at_length(rnd.uniform(0.1, w.length() - 0.1))
        under = C._pick_wire(v, q)
        if under is None or under.id != w.id:
            return                      # (another wire there first: not this one)
        v.set_selection(set())
        v.run(C.WireSizeCmd)
        v.cmd.pick(q)
        v.cmd.enter()
        typed = rnd.choice(["14", "10", "1/0", "250 kcmil", "L", "6 AWG"])
        v.input_text(typed)
        finish()
        now = s.entities.get(w.id)
        want = "" if typed == "L" else C.wire_gauge(typed)
        assert now is not None and now.awg == want, (typed, now and now.awg)
        lay = p.layers.get(now.layer)
        g = now.awg or (lay.awg if lay is not None else "")
        if p.settings.get("wire_gauge_shown", True) and g:
            # (its gauge shown: the label of its run, or of the wires side by side with it of
            # that gauge, starts with it; the color only where asked, 0.18.3, the owner: "I
            # don't think we need to include the wire color")
            text = M.gauge_text(g)
            got = [t.text for t in wirenums.gauge_labels(p, s)]
            assert any(t == text or t.startswith(text + " ") for t in got), (text, now.layer)
        BC.CHECKED["wire size as typed"] += 1

    def op_wire_label():
        # (0.17.2: Wire number label: a click on a wire shows its number there too, its
        # current number; R takes the nearest off)
        ws = [w for w in s.wires() if w.length() > 0.5]
        if not ws:
            return
        w = rnd.choice(ws)
        t = rnd.uniform(0.1, w.length() - 0.1)
        q, _i = w.at_length(t)
        v.run(C.WireLabelCmd)
        removing = bool(w.labels) and rnd.random() < 0.3
        if removing:
            v.input_text("R")
        if v.cmd is None:
            return
        under = C._pick_wire(v, q)
        if under is None or under.id != w.id:
            v.cancel()
            return                      # (another wire there first: not this one)
        v.cmd.pick(q)
        finish()
        now = s.entities.get(w.id)
        if now is None:
            return
        if removing:
            assert len(now.labels) == len(w.labels) - 1, (w.labels, now.labels)
        else:
            assert len(now.labels) == len(w.labels) + 1, (w.labels, now.labels)
            # (where it was clicked, on the drawing: a wire that crosses itself has that point
            # at two distances along it, and the label may go at the first, seed 105)
            assert any(abs(x - t) < 1e-6 or G.dist(now.at_length(x)[0], q) < 1e-6
                       for x in now.labels), (t, now.labels, q)
        if wirenums.enabled(p) and now.num:
            shown = {(round(x.pos[0], 6), round(x.pos[1], 6)): x.text
                     for x in wirenums.labels(p, s)}
            h = float(p.settings.get("wire_number_height", 0.08)) * s.k()
            for x in now.labels:
                spot, _k = now.at_length(x)
                near = [txt for (px, py), txt in shown.items()
                        if abs(px - spot[0]) <= h and abs(py - spot[1]) <= h]
                assert now.num in near, "a label at %s doesn't show %s: %s" % (
                    spot, now.num, near)
        BC.CHECKED["wire label placed by hand"] += 1

    def op_delwire():
        ws = s.wires()
        if ws:
            v.set_selection({w.id for w in rnd.sample(ws, min(2, len(ws)))})
            v.run(C.DeleteWireCmd)
        finish()

    def op_delcomp():
        ins = s.inserts()
        if ins:
            v.set_selection({rnd.choice(ins).id})
            v.run(C.DeleteComponentCmd)
        finish()

    def op_clean():
        v.set_selection(set())
        v.run(C.CleanWiresCmd)
        finish()

    def op_scoot():
        ins = [e for e in s.inserts() if len(e.pin_points()) >= 2]
        if not ins:
            return
        e = rnd.choice(ins)
        v.set_selection({e.id})
        cmd = v.run(C.ScootCmd)
        # (0.17.3: with everything attached, the pins that had wires keep them; O: only it,
        # along its wire, as before)
        only = rnd.random() < 0.5
        wired = {q for x in s.inserts() for _n, q in x.pin_points()
                 if any(w.touches(q) for w in s.wires())}
        if v.cmd is not None and cmd.devs and only:
            v.input_text("O")
        d = (rnd.choice([-1, 1]) * 0.5, 0.0) if rnd.random() < 0.5 else \
            (0.0, rnd.choice([-1, 1]) * 0.5)
        moved = []
        if v.cmd is not None:
            type_in(v, fmt(e.pos))
            if v.cmd is not None and cmd.devs and not only:
                got = cmd.result((e.pos[0] + d[0], e.pos[1] + d[1]))
                moved = {x.id for x in got or () if isinstance(x, M.Insert)}
            if v.cmd is not None:
                v.input_text(fmt((e.pos[0] + d[0], e.pos[1] + d[1])))
        finish()
        if moved:
            # each pin that had a wire still has one, where it is now (moved with the branch)
            after = {q for x in s.inserts() for _n, q in x.pin_points()
                     if any(w.touches(q) for w in s.wires())}
            gone = [q for q in wired if q not in after and not any(
                (abs(q[0] + d[0] - r[0]) < 1e-9 and abs(q[1] + d[1] - r[1]) < 1e-9)
                for r in after)]
            assert not gone, "scooting %s with what's attached left pins %s without a wire" % (
                e.block, gone[:3])
            BC.CHECKED["scoot with everything attached"] += 1

    def op_align():
        ins = [e for e in s.inserts() if len(e.pin_points()) >= 2]
        if len(ins) < 2:
            return
        a, b = rnd.sample(ins, 2)
        v.run(C.AlignDevicesCmd)
        v.cmd.pick(a.pos)
        if v.cmd is not None:
            v.cmd.pick(b.pos)
        finish()

    def op_crossing():
        ws = s.wires()
        if not ws:
            return
        w = rnd.choice(ws)
        a, b = w.points[0], w.points[1]
        v.run(C.WireCrossCmd)
        v.input_text(rnd.choice(["G", "L", "N"]))
        v.cmd.point(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
        finish()

    def op_rail():
        v.run(rnd.choice([C.RailCmd, C.DuctCmd]))
        a = pt()
        type_in(v, fmt(a))
        if v.cmd is not None:
            v.input_text(fmt((a[0] + 3, a[1])))
        finish()

    def op_dim():
        v.run(C.DimLinearCmd)
        a = pt()
        if rnd.random() < 0.5 and v.cmd is not None:
            # (0.17.4: the second point follows Ortho, with the snaps off: the mouse a little
            # off level is held level from the first point)
            v.input_text(fmt(a))
            flags = (v.osnap_on, v.snap_on, v.ortho_on, v.polar_on)
            v.osnap_on, v.snap_on, v.ortho_on, v.polar_on = False, False, True, False
            try:
                got = v.resolve((a[0] + 2.0, a[1] + 0.3))
            finally:
                v.osnap_on, v.snap_on, v.ortho_on, v.polar_on = flags
            assert abs(got[1] - a[1]) < 1e-9, "a dimension's second point off Ortho: %r from %r" % (
                got, a)
            BC.CHECKED["dimension follows Ortho"] += 1
            pts = [(a[0] + 2, a[1]), (a[0] + 1, a[1] - 0.5)]
        else:
            pts = [a, (a[0] + 2, a[1]), (a[0] + 1, a[1] - 0.5)]
        for q in pts:
            if v.cmd is not None:
                v.input_text(fmt(q))
        finish()

    def op_arrow_pair():
        # (0.18.5: a destination arrow paired with a chosen source from the list: it takes
        # that one's name, and its text shows that one's place)
        from kanzonascad import wirenums as WN
        srcs = [(sh, c) for sh in p.sheets for c in sh.inserts()
                if c.block == WN.ARROWS[0] and c.attrs.get("TAG")]
        k = s.k()
        o = clear_of_drawing(k)
        if not srcs or o is None:
            return
        with p.edit("a wire to land on") as ed:
            ed.add(s, M.Wire([o, (o[0] + 3.0 * k, o[1])]))
        want = rnd.choice(srcs)
        win.pick_connector = lambda cands: next(
            ((sh, c) for sh, c in cands if c is want[1]), None)
        try:
            v.run(C.InsertCmd, lib.get("symbol", WN.ARROWS[1]), {})
            v.input_text(fmt(o))
            if v.cmd is not None:
                v.input_text(C.PAIR_LIST)
            finish()
        finally:
            win.__dict__.pop("pick_connector", None)
        got = [c for c in s.inserts() if c.block == WN.ARROWS[1] and
               G.dist(c.pin_points()[0][1], o) < 1e-6]
        if not got:
            return                      # (not placed there: another pin took it, say)
        # (the source as it is now: it follows its wire's number, 0.18.6, and pairing can
        # renumber that wire)
        now = want[0].entities.get(want[1].id)
        assert now is not None and got[0].attrs.get("TAG") == now.attrs["TAG"], (
            "a destination paired from the list took %r, not %r (was %r)" % (
                got[0].attrs.get("TAG"), now and now.attrs["TAG"], want[1].attrs["TAG"]))
        BC.CHECKED["arrow paired as chosen"] += 1
        # (0.19.11: linked to that very source arrow, and its cross-reference shows that one
        # whatever the order of the others of its name)
        cur = s.entities[got[0].id]
        linked = WN.linked_source(p, cur)
        assert linked is not None and linked[1] is now, \
            "a destination paired from the list isn't linked to that source arrow"
        pairs = XR.arrow_pairs(p, WN.connectors(p).get(cur.attrs["TAG"].strip().upper(), []))
        assert [oc for _os, oc in pairs.get(id(cur), [])] == [now], \
            "a linked destination is paired with another source"
        BC.CHECKED["linked destination shows its source"] += 1

    def op_source_master():
        # (0.19.11: a destination placed on a wire whose number is locked on its own page (a
        # foreign number) doesn't take its source's wire over: the source's wire keeps a number
        # of its own page, worked out from the source's sheet, and the destination follows)
        from kanzonascad import wirenums as WN
        if not WN.enabled(p) or len(p.sheets) < 2:
            return
        srcs = [(sh, c) for sh in p.sheets for c in sh.inserts()
                if c.block == WN.ARROWS[0] and c.attrs.get("TAG")]
        if not srcs:
            return
        sh, src = rnd.choice(srcs)
        home = [w for w in sh.wires() if w.touches(src.pin_points()[0][1])]
        if not home or s is sh or any(w.num_lock and w.num == home[0].num
                                      for w in sh.wires()):
            return                  # (a number typed on the source's page holds: not this)
        k = s.k()
        o = clear_of_drawing(k)
        if o is None:
            return
        foreign = "%s%03d" % (p.sheet_number(s), rnd.randint(700, 899))
        with p.edit("a wire numbered by hand") as ed:
            ed.add(s, M.Wire([o, (o[0] + 3.0 * k, o[1])], num=foreign, num_lock=True))
        win.pick_connector = lambda cands: next(
            ((x, c) for x, c in cands if c is src), None)
        try:
            v.run(C.InsertCmd, lib.get("symbol", WN.ARROWS[1]), {})
            v.input_text(fmt(o))
            if v.cmd is not None:
                v.input_text(C.PAIR_LIST)
            finish()
        finally:
            win.__dict__.pop("pick_connector", None)
        now = [w for w in sh.wires() if w.touches(src.pin_points()[0][1])]
        if not now or not now[0].num or now[0].num_lock:
            return
        # (never the number typed on the destination's wire, nor a tap of it)
        assert now[0].num != foreign and not (now[0].num.startswith(foreign) and TAP_END.fullmatch(
            now[0].num[len(foreign):])), \
            "a source arrow's wire on page %s took %s, typed on the destination's page" % (
                p.sheet_number(sh), now[0].num)
        # (a wire of its own: a number of its page. A tap is numbered from the wire it taps,
        # 1006-1, 1006-1a, 1006a..., and that wire may be carried from another page by arrows,
        # page 1's 1001 tapped on page 2 is 1001-1 there: the long battery's seed 4793)
        base = TAP_END.sub("", now[0].num)
        got = WN.split(base)
        if got is None and WN.by_io_address(p):
            return                          # (numbered by a PLC point's address, O:3/0)
        if base == now[0].num:
            # (of the first page with a source arrow of its name: a sheet duplicated with its
            # arrows has a second source of one name, and the wires they join are one group,
            # numbered from the first sheet in order; seed 2901, 0.29: page 51's source 29009,
            # a copy of page 29's)
            first = next(p.sheet_number(x) for x in p.sheets if any(
                c.block == WN.ARROWS[0] and c.attrs.get("TAG") == src.attrs["TAG"]
                for c in x.inserts()))
            assert got and got[0] == first, \
                "a source arrow's wire on page %s took %s from a destination's page" % (
                    p.sheet_number(sh), now[0].num)
        BC.CHECKED["a source's wire keeps its page's number"] += 1

    def op_wire_color():
        # (0.18.4: Wire color label on the selected wires: on when any is off, else off;
        # worked out from the wires before)
        ws = s.wires()
        if not ws:
            return
        if rnd.random() < 0.2:
            # (0.22.4: the project's "...and its color" turned on or off: every wire without a
            # choice of its own follows it)
            with p.edit("wire colors") as ed:
                ed.project_settings({"wire_color_shown": not p.settings.get("wire_color_shown")})
        pick = rnd.sample(ws, min(len(ws), rnd.randint(1, 3)))
        dflt = bool(p.settings.get("wire_color_shown"))
        want = any(not (w.show_color if w.show_color is not None else dflt) for w in pick)
        v.set_selection({w.id for w in pick})
        v.run(C.WireColorLabelCmd)
        finish()
        for w in pick:
            got = s.entities.get(w.id)
            if got is not None:
                assert got.show_color == want, "Wire color label left a wire %s" % (
                    "showing" if got.show_color else "hiding")
        BC.CHECKED["wire color label as asked"] += 1

    def op_fp_label_color():
        # (0.18.7: Panel settings, Footprint label color: every footprint's labels take it, or
        # their footprint's color again when it's off; undone with the rest)
        want = rnd.choice(["", "#00ffff", "#ffff00"])
        with p.edit("Footprint label color") as ed:
            ed.project_settings({"fp_label_color": want})
        for sh in p.sheets:
            for e in sh.inserts():
                if e.defn is not None and e.defn.kind == "footprint":
                    assert (e.label_color or "") == want, \
                        "a footprint's labels are %r, the setting %r" % (e.label_color, want)
                    if want and e.label_texts():
                        assert {w.color for w in e.world_entities() if isinstance(w, M.Text)
                                and w.text in {t.text for _k, t in e.label_texts()}} == {want}
                    BC.CHECKED["footprint label color as set"] += 1

    def op_xref_device():
        # (0.19.3: arrows show the device at their wire's other end on a second line, set for
        # the project, a sheet or one arrow, each overriding the one before; worked out here
        # from the three settings, the reference lines counted before and after)
        from kanzonascad import wirenums as WN

        def on(sh, c):
            own = c.attrs.get("XDEV")
            if own in ("1", "0"):
                return own == "1"
            if sh.xref_device is not None:
                return bool(sh.xref_device)
            return bool(p.settings.get("xref_device", True))

        def second_lines():
            n = 0
            for name, ends in WN.connectors(p).items():
                pairs = XR.arrow_pairs(p, ends)
                for sh, c in ends:
                    if c.block not in WN.ARROWS or not on(sh, c):
                        continue
                    pair = pairs.get(id(c), [])
                    if any(XR.far_device(os_, oc) for os_, oc in pair):
                        n += 1
            return n

        def shown():
            return sum(len(XR.live(p, sh)) for sh in p.sheets)
        before, lines = shown(), second_lines()
        level = rnd.choice(["project", "sheet", "arrow"])
        arrows = [c for c in s.inserts() if c.block in WN.ARROWS]
        if level == "arrow" and not arrows:
            level = "sheet"
        with p.edit("Arrows show the far device") as ed:
            if level == "project":
                ed.project_settings({"xref_device": not p.settings.get("xref_device", True)})
            elif level == "sheet":
                ed.sheet_meta(s, xref_device=rnd.choice([None, True, False]))
            else:
                c = rnd.choice(arrows)
                attrs = dict(c.attrs)
                got = rnd.choice([None, "1", "0"])
                if got is None:
                    attrs.pop("XDEV", None)
                else:
                    attrs["XDEV"] = got
                ed.change(s, c.copy(attrs=attrs))
        after = shown()
        assert after - before == second_lines() - lines, (
            "arrows' far-device lines went from %d to %d shown, %d to %d set (%s)" % (
                before, after, lines, second_lines(), level))
        BC.CHECKED["arrow far device as set"] += 1

    def op_dim_units():
        # (0.18.4: Dimension units on the selected dimensions, D, F or a precision typed; new
        # dimensions as the project says, now and then changed; each reads its true length in
        # its format, worked out here from its two points)
        if rnd.random() < 0.2:
            with p.edit("dim units") as ed:
                ed.project_settings({"dim_units": rnd.choice(M.DIM_UNITS)})
        ds = [e for e in s.entities.values() if isinstance(e, M.Dimension)]
        if not ds:
            return
        pick = rnd.sample(ds, min(len(ds), rnd.randint(1, 3)))
        v.set_selection({d.id for d in pick})
        v.run(C.DimUnitsCmd)
        typed = rnd.choice(["D", "F", "1/8", "1/16", "1/32", "1/64"])
        v.input_text(typed)
        finish()
        proj = M.dim_units(p.settings.get("dim_units"))
        want = {"D": "decimal", "F": proj if proj != "decimal" else "1/16"}.get(typed, typed)
        for d in pick:
            got = s.entities.get(d.id)
            if got is None or got.text:
                continue
            a, b = got.p1, got.p2
            u, val = got.direction()
            true = abs((b[0] - a[0]) * u[0] + (b[1] - a[1]) * u[1])
            assert got.units == want, "Dimension units %r gave %s, not %s" % (typed, got.units,
                                                                                 want)
            if want == "decimal":
                expect = "%.2f\"" % true
            else:
                den = int(want.split("/")[1])
                n = int(round(true * den))
                w_, r_ = divmod(n, den)
                if r_:
                    import math as _m
                    g = _m.gcd(r_, den)
                    expect = "%s%d/%d\"" % ("%d-" % w_ if w_ else "", r_ // g, den // g)
                else:
                    expect = "%d\"" % w_
            assert got.label() == expect, "a dimension of %r reads %s, not %s" % (
                true, got.label(), expect)
            BC.CHECKED["dimension reads in its units"] += 1

    def op_frame():
        # (0.18.4: border and zones, title block, off and on for the project or a sheet: what
        # is drawn is what the sheet's say, else the project's)
        what = rnd.choice(["show_border", "show_title_block"])
        with p.edit("frame") as ed:
            if rnd.random() < 0.5:
                ed.project_settings({what: rnd.random() < 0.6})
            else:
                ed.sheet_meta(s, **{what: rnd.choice([None, True, False])})
        on = {}
        for k in ("show_border", "show_title_block"):
            own = getattr(s, k)
            on[k] = bool(p.settings.get(k, True)) if own is None else own
        ents = sheetframe.frame_entities(p, s)
        n_b = len(sheetframe.border_entities(s)) if on["show_border"] else 0
        assert (len(ents) > n_b) == (on["show_title_block"] and bool(
            p.title_block.entities)), "the title block %s drawn, the sheet says %s" % (
                "is" if len(ents) > n_b else "isn't", on["show_title_block"])
        assert sum(1 for e in ents if e.layer == sheetframe.FRAME_LAYER) >= (
            1 if on["show_border"] else 0), "the border isn't drawn"
        BC.CHECKED["border and title block as set"] += 1

    texts = ["NOTE", "SEE DETAIL A", "LINE ONE\nLINE TWO", "A LONGER NOTE THAT WRAPS"]
    win.ask_mtext = lambda text="": rnd.choice(texts + [""])
    from kanzonascad import bom, sheetframe, pull

    def op_leader():
        v.run(C.LeaderCmd)
        a = pt()
        pts = [a, (a[0] + rnd.choice([-1, 1]) * 0.75, a[1] + 0.5)]
        if rnd.random() < 0.4:
            pts.append((pts[1][0] + rnd.choice([-0.5, 0.5]), pts[1][1]))
        type_in(v, *[fmt(q) for q in pts])
        if v.cmd is not None:
            v.cmd.enter()
        if v.cmd is not None:
            if rnd.random() < 0.4:
                v.input_text("B")
                if v.cmd is not None:
                    v.input_text(rnd.choice(["", str(rnd.randint(1, 30))]))
            else:
                v.input_text(rnd.choice(texts))
        finish()

    def op_mtext():
        v.run(C.MTextCmd)
        a = pt()
        type_in(v, fmt(a))
        if v.cmd is not None:
            if rnd.random() < 0.7:
                v.input_text(fmt((a[0] + rnd.choice([1, 2, 3]), a[1] - 1)))
            else:
                v.cmd.enter()
        finish()

    def op_hatch():
        a = pt()
        b = (a[0] + rnd.choice([0.5, 1, 2]), a[1] + rnd.choice([0.5, 1]))
        if rnd.random() < 0.7:
            v.run(C.RectangleCmd)
            # (the second corner typed as a size, as a user would, or as a point with #)
            type_in(v, fmt(a), fmt((b[0] - a[0], b[1] - a[1])) if rnd.random() < 0.5
                    else "#" + fmt(b))
            finish()
        v.run(C.HatchCmd)
        if v.cmd is not None and rnd.random() < 0.6:
            v.input_text(rnd.choice(["SOLID", "ANSI31", "ANSI37", "LINES"]))
        if v.cmd is not None and rnd.random() < 0.2:
            v.input_text("AN")
            if v.cmd is not None:
                v.input_text(rnd.choice(["0", "30", "45", "135"]))
        if v.cmd is not None:
            v.input_text(fmt(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)))
        finish()

    ace = BC.ace_like_dxf(os.path.join(out, "ace_like.dxf"), devices=24)

    def op_import():
        # the small sample, or a drawing as AutoCAD Electrical writes one (hidden and moved
        # attributes, a frame bigger than the sheet, far from the origin)
        fileio.import_dxf(p, s, sample if rnd.random() < 0.6 else ace, at=pt())

    def op_explode():
        ins = [e for e in s.entities.values() if isinstance(e, M.Insert)]
        if ins:
            v.set_selection({rnd.choice(ins).id})
            v.run(C.ExplodeCmd)
        finish()

    def op_usetb():
        imp = [e for e in s.entities.values() if isinstance(e, M.Insert)
               and e.defn is not None and e.defn.category == "Imported"]
        if not imp:
            return
        # (through the command, as a person does: on a turned sheet it says to turn it
        # upright first)
        v.set_selection({rnd.choice(imp).id})
        v.run(C.UseTitleBlockCmd)
        finish()

    def op_title_block():
        # (0.22.4) Edit title block in a tab of its own: a line drawn there, then Save title
        # block (in the project, one step, back to the drawing) or Close title block and
        # Discard (the project's as it was)
        from unittest import mock
        from PySide6.QtWidgets import QMessageBox
        src, sheet_id = win.doc(), v.sheet_id
        lines = lambda pr: sorted(tuple(map(tuple, (e.p1, e.p2))) for e in
                                  pr.title_block.entities.values() if isinstance(e, M.Line))
        before = lines(p)
        win.acts["edit_tb"].trigger()
        d = win.doc()
        assert d is not src and d.view.sheet() is d.project.title_block, \
            "Edit title block didn't open a tab of its own"
        # (inside the title block's outline, as anyone draws in one: a line far from it made
        # it, and a strip title block, span the sheet, the room left for the drawing a sliver;
        # seed 469's report and I/O sheets)
        bb = None
        for e in d.project.title_block.entities.values():
            bb = G.bbox_union(bb, e.bbox())
        if bb is None or bb[2] - bb[0] < 1.0:
            bb = (0.5, 0.1, 4.5, 1.0)
        a = (round(rnd.uniform(bb[0], bb[2] - 0.6), 3), round(rnd.uniform(bb[1], bb[3]), 3))
        b = (round(a[0] + 0.5, 3), a[1])
        t = d.view
        t.snap_on = t.osnap_on = t.ortho_on = t.polar_on = False
        t.run(C.LineCmd)
        for q in (a, b):
            if t.cmd is not None:
                t.input_text(fmt(q))
        while t.cmd is not None:
            t.cmd.enter()
            if t.cmd is not None:
                t.cancel()
        drawn = lines(d.project) != before
        if rnd.random() < 0.3:
            # (0.22.4: Save as title block: kept in the library by name, the tab still open)
            from kanzonascad import titleblocks as TBL
            name = "Battery %d" % rnd.randint(1, 3)
            with mock.patch.object(win, "ask_title_block_name", return_value=name), \
                    mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
                win.acts["save_tb_as"].trigger()
            assert (name, False) in TBL.names(win.library) and win.doc() is d, \
                "Save as title block didn't keep %s in the library" % name
            BC.CHECKED["title block saved in the library"] += 1
        save = rnd.random() < 0.6
        if save:
            win.acts["save_tb"].trigger()
        else:
            with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Discard):
                win.acts["close_tb"].trigger()
        assert win.doc() is src and v.sheet_id == sheet_id and win.tabs.indexOf(d) < 0, \
            "Save or Close title block didn't go back to the drawing"
        if save and drawn:
            assert (a, b) in lines(p) or (b, a) in lines(p), \
                "the line drawn in the title block's tab isn't in the project's"
            BC.CHECKED["title block saved from its tab"] += 1
        elif not save:
            assert lines(p) == before, "a title block closed without saving changed"
            BC.CHECKED["title block closed without saving"] += 1
        if rnd.random() < 0.3:
            # (0.22.4: Title blocks...: a ready-made one or one of the library's put in the
            # project, where it sits; checked against the library's own copy)
            from kanzonascad import titleblocks as TBL
            name = rnd.choice([n for n, _b in TBL.names(win.library)])
            with mock.patch.object(win, "ask_title_block", return_value=name):
                win.acts["title_blocks"].trigger()
            pos, ents, _lays, _blocks = TBL.load(win.library, name, p)
            texts = lambda es: sorted(e.text for e in es if isinstance(e, M.Text))
            assert texts(p.title_block.entities.values()) == texts(ents) and \
                p.settings.get("tb_position") == pos, "Title blocks... didn't put %s in" % name
            BC.CHECKED["title block from the library"] += 1

    fps = sorted(n for n, d in lib.blocks("footprint")[0].items() if d.builtin)

    def op_footprint():
        # a built-in generic footprint, placed as Insert footprint does (0.16: asked which
        # device it is; Enter: the next one with no footprint)
        from kanzonascad import tags
        before = set(s.entities)
        offered = tags.footprint_candidates(p)
        v.run(C.InsertCmd, lib.get("footprint", rnd.choice(fps)), {})
        if v.cmd is not None:
            v.input_text(fmt(pt()))
        if v.cmd is not None and rnd.random() < 0.2:
            v.input_text("N")
        finish()
        new = [e for i, e in s.entities.items() if i not in before and isinstance(e, M.Insert)]
        if offered and len(new) == 1 and new[0].attrs.get("PARENT"):
            # some device's footprint now, with its tag, and the only footprint with it
            f = new[0]
            dev = tags.devices(p).get(f.attrs["PARENT"])
            assert dev is not None, "a footprint linked to no device"
            assert f.attrs.get("TAG") == dev[1].attrs.get("TAG"), "a footprint's tag isn't its device's"
            same = [e for sh in p.sheets for e in sh.inserts() if tags.is_footprint(e)
                    and e.attrs.get("TAG", "").upper() == f.attrs["TAG"].upper()]
            assert len(same) == 1, "two footprints tagged %s" % f.attrs["TAG"]
            BC.CHECKED["footprint takes a device"] += 1

    def op_fp_labels():
        # (0.18.1) a footprint's label as the Footprint label menu and grips change it: a line
        # shown or not (several at once), or one dragged; then what it shows is what it says
        # it shows, a dragged line is where it was put and the others stay; and a linked
        # footprint has its device's ratings
        from kanzonascad import tags
        fs = [e for e in s.inserts() if tags.is_footprint(e) and not v.layer_locked(e.layer)]
        if not fs:
            return
        f = rnd.choice(fs)
        if rnd.random() < 0.6 or not f.label_texts():
            key = rnd.choice(list(M.LABELS) + [""])
            v.set_selection({f.id})
            had = M.label_keys(f.label)
            win.acts["fp_label_" + (key or "none")].trigger()
            now = M.label_keys(s.entities[f.id].label)
            want = [] if not key else ([k for k in had if k != key] if key in had
                                       else had + [key])
            assert now == want, "Footprint label %r: %r became %r, not %r" % (key, had, now,
                                                                             want)
            BC.CHECKED["footprint label lines"] += 1
        else:
            grips = f.text_grips()
            i = rnd.randrange(len(grips))
            q = (grips[i][1][0] + rnd.uniform(-1, 1), grips[i][1][1] + rnd.uniform(-1, 1))
            with p.edit("Grip") as ed:
                ed.change(s, f.with_grip(i + 1, q))
            now = s.entities[f.id].text_grips()
            assert G.dist(now[i][1], q) < 1e-6, "a label line dragged to %r is at %r" % (
                q, now[i][1])
            for j, (n, at) in enumerate(grips):
                if j != i:
                    assert G.dist(dict(now)[n], at) < 1e-6, "dragging one label line moved %s" % n
            BC.CHECKED["footprint label grips"] += 1
        f = s.entities[f.id]
        got = tags.parent_of(p, f)
        if got is not None:
            for k in tags.LINKED_ATTRS:
                assert f.attrs.get(k, "") == got[1].attrs.get(k, ""), \
                    "a linked footprint's %s is %r, its device's %r" % (
                        k, f.attrs.get(k), got[1].attrs.get(k))
            BC.CHECKED["linked footprint ratings"] += 1

    def op_fp_label_sizes():
        # (0.24.1) a footprint's label lines' text sizes and turns, as a user sets them: sizes
        # in its block (Block properties, Label text sizes: saved to the library and the
        # copies updated), and on a copy (its attributes window: a size, an angle and Keep
        # readable per line; with other footprints selected, the sizes changed go to them).
        # Each line's height and angle are worked out here from what was stored: the copy's
        # size, else the block's, else the project's (tag_h); a line turned on its own at its
        # angle with the footprint, kept readable (90 < a <= 270 drawn 180 less) unless unticked
        from unittest import mock
        from PySide6.QtWidgets import QDoubleSpinBox, QCheckBox
        from kanzonascad import library_panel
        from kanzonascad import tags
        fs = [e for e in s.inserts() if tags.is_footprint(e) and not v.layer_locked(e.layer)
              and e.label]
        if not fs:
            return
        f = rnd.choice(fs)
        keys = [M.label_size_key(k) for k in M.label_keys(f.label)]
        real = library_panel.QDialog.exec
        if rnd.random() < 0.35 and lib.get("footprint", M.library_block_name(
                f.block, "footprint")) is not None:
            want = {k: rnd.choice([0.0, 0.05, 0.1, 0.15, 0.2]) for k in rnd.sample(
                keys, rnd.randint(1, len(keys)))}

            def answer(dlg):
                for k, x in want.items():
                    b = dlg.findChild(QDoubleSpinBox, "label_size_" + k)
                    assert b is not None and b.isEnabled(), "Block properties: no size for " + k
                    b.setValue(x)
                return QDialog.Accepted
            library_panel.QDialog.exec = answer
            try:
                with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
                    new = win.block_properties("footprint", M.library_block_name(
                        f.block, "footprint"))
            finally:
                library_panel.QDialog.exec = real
            if new is None:
                return
            got = p.blocks[f.block].label_sizes
            for k, x in want.items():
                assert got.get(k) == (x or None), "Block properties: %s's size %r, typed %r" % (
                    k, got.get(k), x)
            BC.CHECKED["footprint label sizes in its block"] += 1
        else:
            f = s.entities[f.id]
            others = [e for e in fs if e.id != f.id][:rnd.randint(0, 2)]
            v.set_selection({f.id} | {o.id for o in others})
            sizes = {k: rnd.choice([0.0, 0.06, 0.12, 0.25]) for k in rnd.sample(
                keys, rnd.randint(0, len(keys)))}
            turn = rnd.choice(keys)
            ang = rnd.choice([0.0, 45.0, 90.0, 180.0, 270.0])
            keep = rnd.random() < 0.6
            before = {o.id: dict(o.label_sizes) for o in others}

            def answer(dlg):
                for k, x in sizes.items():
                    dlg.findChild(QDoubleSpinBox, "label_size_" + k).setValue(x)
                dlg.findChild(QDoubleSpinBox, "label_angle_" + turn).setValue(ang)
                dlg.findChild(QCheckBox, "label_readable_" + turn).setChecked(keep)
                return QDialog.Accepted
            had = dict(f.label_sizes)
            library_panel.QDialog.exec = answer
            try:
                win.edit_attributes(f)
            finally:
                library_panel.QDialog.exec = real
            g = s.entities[f.id]
            want = dict(had)
            for k, x in sizes.items():
                if x:
                    want[k] = x
                else:
                    want.pop(k, None)
            assert g.label_sizes == want, "a copy's sizes %r, typed %r over %r" % (
                g.label_sizes, sizes, had)
            assert (turn in g.label_as_set) == (not keep), "Keep readable not kept"
            for o in others:
                ow = dict(before[o.id])
                for k in set(had) | set(want):
                    if had.get(k) != want.get(k):
                        if k in want:
                            ow[k] = want[k]
                        else:
                            ow.pop(k, None)
                assert s.entities[o.id].label_sizes == ow, "the other selected footprint's " \
                    "sizes %r, not %r" % (s.entities[o.id].label_sizes, ow)
                BC.CHECKED["footprint label sizes to the selected"] += 1
            BC.CHECKED["footprint label sizes on a copy"] += 1
        g = s.entities[f.id]
        if not g.label_texts():
            return
        assert g.label_k is not None, "a labeled footprint with no label_k"
        blk = g.defn.label_sizes
        for k, t in g.label_texts():
            kk = M.label_size_key(k)
            size = g.label_sizes.get(kk) or blk.get(kk)
            h = size * g.label_k if size else (g.tag_h or 0.125)
            assert abs(t.height - h) < 1e-9, "label line %s %r tall, not %r" % (k, t.height, h)
            r = g.attr_rot.get("@" + kk)
            if r is None:
                a = 90.0 if 45.0 <= g.angle % 180.0 < 135.0 else 0.0
            else:
                a = (g.angle + (-r if g.mirror else r)) % 360.0
                if kk not in g.label_as_set and 90.0 + 1e-9 < a <= 270.0 + 1e-9:
                    a -= 180.0
            assert abs((t.angle - a + 180.0) % 360.0 - 180.0) < 1e-6, \
                "label line %s drawn at %r, not %r" % (k, t.angle, a)
            BC.CHECKED["footprint label line height and angle"] += 1
        shown = [(k, t.text, t.pos, t.height, t.angle) for k, t in g.label_texts()]
        # (saved and opened, the same; undone and redone, the same)
        q = M.Project.from_dict(json.loads(json.dumps(p.to_dict())))
        e2 = q.sheet_by_id(s.id).entities[g.id]
        assert [(k, t.text, t.pos, t.height, t.angle) for k, t in e2.label_texts()] == shown, \
            "a footprint's label lines changed through save and open"
        if p.undo_stack and p.undo_stack[-1].name in ("Attributes", "Update %s" % g.block):
            p.undo()
            p.redo()
            e3 = s.entities.get(g.id)
            assert e3 is not None and [(k, t.text, t.pos, t.height, t.angle)
                                       for k, t in e3.label_texts()] == shown, \
                "a footprint's label lines not the same undone and redone"
            BC.CHECKED["footprint label sizes undone and redone"] += 1

    def props_widget(key):
        """A Properties panel field's widget, found by its name as a test would."""
        from PySide6.QtWidgets import QWidget
        body = win.props_panel.body
        return body.findChild(QWidget, "prop_" + key) if body is not None else None

    def props_fill(ids):
        """The selection set and the Properties panel open and filled with it (as after the
        panel's short wait)."""
        if win.props_dock.isHidden():
            win.properties()
        v.set_selection(set(ids))
        win._props_wait.stop()
        win.props_fill()

    def props_set(key, value):
        """A field of the Properties panel set as a user does: typed and Enter, a number box
        left, a tick clicked, a list item picked."""
        from kanzonascad import props_panel as PP
        w = props_widget(key)
        assert w is not None, "the Properties panel has no %s (it has %s)" % (
            key, sorted(win.props_panel.widgets))
        if isinstance(w, PP._Text):
            w.setText(value)
            w.setModified(True)
            w.editingFinished.emit()
        elif isinstance(w, PP._Number):
            w.setValue(value)
            w.editingFinished.emit()
        elif isinstance(w, PP._Check):
            if w.checkState() != (Qt.Checked if value else Qt.Unchecked):
                w.click()
                assert w.checkState() == (Qt.Checked if value else Qt.Unchecked), \
                    "%s: a click left it %r" % (key, w.checkState())
        else:
            i = next(j for j, d in enumerate(w.datas) if PP._same(d, value))
            w.setCurrentIndex(i)
            w.activated.emit(i)

    def model_value(key, e, sh):
        """A Properties panel field's value read from the object itself (not the panel's
        code): what the field must show, and what setting it must leave."""
        from kanzonascad import missing_fp
        if key == "layer":
            return e.layer
        if key == "color":
            return e.color
        if key in ("TAG", "DESC", "MFR", "CAT", "LOC"):
            return e.attrs.get(key, "")
        if key.startswith("attr_"):
            return e.attrs.get(key[5:], "")
        if key == "nofp":
            return missing_fp.not_needed(e)
        if key == "lock":
            return e.attrs.get("TAG_LOCK") == "1"
        if key.startswith("shown_"):
            return key[6:] not in e.hidden
        if key.startswith("angle_"):
            return round(e.attr_angle(key[6:]), 2) % 360.0
        if key.startswith("label_size_"):
            return e.label_sizes.get(key[11:])
        if key.startswith("label_angle_"):
            return round(e.attr_angle("@" + key[12:]), 2) % 360.0
        if key.startswith("label_readable_"):
            return key[15:] not in e.label_as_set
        if key.startswith("label_"):
            return key[6:] in M.label_keys(e.label)
        if key == "gauge":
            return M.gauge_text(e.awg)
        if key == "color_label":
            return e.show_color
        if key == "wire_num":
            return e.num or ""
        if key == "wire_lock":
            return e.num_lock
        if key == "text":
            return e.text
        if key == "height":
            return round(e.height / (1.0 if e.fixed else sh.k()), 4)
        if key == "length":
            return round(G.dist(e.p1, e.p2), 6)
        if key == "radius":
            return e.radius
        if key in ("x", "y"):
            q = e.center if isinstance(e, M.Circle) else e.pos
            return q[0 if key == "x" else 1]
        if key == "rotation":
            return e.angle
        return UNREAD

    def op_props_panel():
        # (0.25) the Properties panel as a user works it: objects selected (one, a few of a
        # kind, or of mixed kinds), what it shows checked against the objects themselves
        # (*varies* where they differ), then a field set through its widget by name; every one
        # of them must hold what was set, in one step that undoes and redoes exactly
        from PySide6.QtWidgets import QComboBox, QGroupBox
        from kanzonascad import props_panel as PP
        from kanzonascad import wirenums
        ents = list(s.entities.values())
        if not ents:
            return
        first = rnd.choice(ents)
        same = [e for e in ents if PP.kind_of(e) == PP.kind_of(first) and e.id != first.id]
        r = rnd.random()
        if r < 0.5 or not same:
            pick = [first]
        elif r < 0.85:
            pick = [first] + rnd.sample(same, min(len(same), rnd.randint(1, 3)))
        else:
            pick = [first] + rnd.sample(ents, min(len(ents), 2))
            pick = list({e.id: e for e in pick}.values())
        props_fill([e.id for e in pick])
        pick = [s.entities[e.id] for e in pick]
        kinds = {PP.kind_of(e) for e in pick}
        groups = [g.title() for g in win.props_panel.body.findChildren(QGroupBox)]
        if len(kinds) > 1 and kinds != {"text", "mtext"}:
            assert groups == ["General"], "mixed kinds show %s" % groups
            BC.CHECKED["properties: mixed kinds show General"] += 1
        # what it shows, against the objects
        for key, w in win.props_panel.widgets.items():
            vals = [model_value(key, e, s) for e in pick]
            if any(x is UNREAD for x in vals):
                continue
            varies = any(x != vals[0] for x in vals[1:])
            if isinstance(w, PP._Text):
                if varies:
                    assert w.text() == "" and w.placeholderText() == PP.VARIES, \
                        "%s: %r shown for %r" % (key, w.text(), vals)
                elif not w.size:
                    assert w.text() == str(vals[0]), "%s shows %r, not %r" % (
                        key, w.text(), vals[0])
            elif isinstance(w, PP._Check):
                want = Qt.PartiallyChecked if varies else (Qt.Checked if vals[0] else
                                                           Qt.Unchecked)
                assert w.checkState() == want, "%s ticked %r for %r" % (key, w.checkState(),
                                                                        vals)
            elif isinstance(w, QComboBox):
                if varies:
                    assert w.currentText() == PP.VARIES, "%s shows %r for %r" % (
                        key, w.currentText(), vals)
                else:
                    assert PP._same(w.value(), vals[0]), "%s shows %r, not %r" % (
                        key, w.value(), vals[0])
            elif isinstance(w, PP._Number):
                if varies:
                    assert w.text() == PP.VARIES, "%s shows %r for %r" % (key, w.text(), vals)
                else:
                    assert abs(w.value() - vals[0]) < 10 ** -w.decimals(), \
                        "%s shows %r, not %r" % (key, w.value(), vals[0])
            if varies:
                BC.CHECKED["properties: *varies*"] += 1
        BC.CHECKED["properties shown"] += 1
        # a field set
        keys = [k for k, w in win.props_panel.widgets.items() if hasattr(w, "committed")
                and model_value(k, pick[0], s) is not UNREAD]
        if not keys:
            return
        key = rnd.choice(keys)
        w = props_widget(key)
        if isinstance(w, PP._Text) and w.size:
            value = rnd.choice(["", "0.06", "0.15"])
            want = float(value) if value else None
        elif isinstance(w, PP._Text):
            value = {"TAG": "CR%d" % rnd.randint(900, 999), "LOC": rnd.choice(
                         ["", "FIELD", "MCP", "JB-1"]),
                     "gauge": rnd.choice(["", "12", "14", "1/0"]),
                     "wire_num": "9%03d" % rnd.randint(0, 999),
                     "text": "T%d" % rnd.randint(1, 99)}.get(key, rnd.choice(
                         ["", "PUMP", "5", "480V"]))
            if key == "wire_num":
                if len(pick) > 1 or wirenums.others_numbered(p, s, pick[0], value) or \
                        not wirenums.enabled(p):
                    return
            if key == "text" and not value:
                return
            want = M.gauge_text(value) if key == "gauge" else value
            if key == "TAG" and PP.kind_of(pick[0]) == "footprint":
                return                  # (linking a footprint: op_missing_fp)
        elif isinstance(w, PP._Number):
            if key in ("x", "y"):
                value = round(model_value(key, pick[0], s) + rnd.choice([-1.0, 0.5, 2.0]), 4)
            elif "angle" in key or key == "rotation":
                value = rnd.choice([0.0, 45.0, 90.0, 180.0, 270.0])
            elif key == "height":
                value = rnd.choice([0.08, 0.125, 0.2])
            else:
                value = rnd.choice([0.25, 1.0, 2.5])
            want = value
        elif isinstance(w, PP._Check):
            # (half ticked, *varies*: a click ticks it on all of them)
            value = w.checkState() == Qt.PartiallyChecked or rnd.random() < 0.5
            want = value
        else:
            choices = [d for d in w.datas if d is not PP.NA and d != PP.OTHER]
            value = rnd.choice(choices)
            want = value
        before = {e.id: e.to_dict() for e in pick}
        n = len(p.undo_stack)
        props_set(key, value)
        now = [s.entities.get(e.id) for e in pick]
        for e in now:
            assert e is not None, "setting %s took an object away" % key
            got = model_value(key, e, s)
            if key == "wire_lock" and not e.num:
                continue
            if key[5:] in tags_mod.NUMBER_ATTRS and key.startswith("attr_") and not value:
                continue                # (left blank: numbered on its strip by itself)
            if isinstance(want, float) and isinstance(got, float):
                ok = abs((got - want + 180.0) % 360.0 - 180.0) < 1e-6 if "angle" in key or \
                    key == "rotation" else abs(got - want) < 1e-6
            else:
                ok = got == want
            assert ok, "Properties: %s set to %r on %d object(s); %s holds %r" % (
                key, value, len(pick), PP.kind_name(e), got)
        if any(s.entities[e.id].to_dict() != before[e.id] for e in pick):
            assert len(p.undo_stack) == n + 1, "Properties: %s took %d steps" % (
                key, len(p.undo_stack) - n)
            after = {e.id: s.entities[e.id].to_dict() for e in pick}
            if len(p.undo_stack) == n + 1:
                p.undo()
                assert {e.id: s.entities[e.id].to_dict() for e in pick} == before, \
                    "Properties: %s undone isn't as before" % key
                p.redo()
                assert {e.id: s.entities[e.id].to_dict() for e in pick} == after, \
                    "Properties: %s redone isn't as after" % key
                BC.CHECKED["properties: one step, undone and redone"] += 1
            # (the panel shows it, filled again after the change)
            win._props_wait.stop()
            win.props_fill()
            if len(pick) == 1 and isinstance(props_widget(key), PP._Text) and \
                    not props_widget(key).size:
                assert props_widget(key).text() == str(model_value(key, s.entities[pick[0].id],
                                                                   s)), \
                    "the panel shows %r after the change" % props_widget(key).text()
        BC.CHECKED["properties: a field set"] += 1
        BC.missing_right(win, p)

    def op_missing_fp():
        # (0.25) devices without a footprint, as a user changes what the check reads: a
        # sheet's type and location (Sheet properties), a device's No footprint needed (its
        # attributes window, or the Properties panel) or Location (the panel), a footprint
        # given a device's tag (linked) or another (unlinked) in the panel, a footprint
        # placed for a device; then the devices listed, counted and marked are those worked
        # out from the rules (battery_checks.missing_footprints)
        from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit
        from kanzonascad import dialogs, library_panel
        from kanzonascad import tags
        r = rnd.random()
        devs = [e for e in s.inserts() if tags.is_device(e)]
        fps_here = [e for e in s.inserts() if tags.is_footprint(e)]
        if r < 0.25:
            kind = rnd.choice(["panel", "schematic", s.kind])
            loc = rnd.choice(["", "MCP", "JB-1", "FIELD", s.location])
            real = dialogs.QDialog.exec

            def answer(dlg):
                k = dlg.findChild(QComboBox, "kind")
                k.setCurrentIndex(k.findData(kind))
                dlg.findChild(QLineEdit, "location").setText(loc)
                return QDialog.Accepted
            dialogs.QDialog.exec = answer
            try:
                win.sheet_properties()
            finally:
                dialogs.QDialog.exec = real
            assert (s.kind, s.location) == (kind, loc), "Sheet properties: %r" % (
                (s.kind, s.location),)
        elif r < 0.45 and devs:
            d = rnd.choice(devs)
            on = rnd.random() < 0.5
            real = library_panel.QDialog.exec

            def answer(dlg):
                dlg.findChild(QCheckBox, "no_footprint").setChecked(on)
                return QDialog.Accepted
            library_panel.QDialog.exec = answer
            try:
                win.edit_attributes(d)
            finally:
                library_panel.QDialog.exec = real
            assert (s.entities[d.id].attrs.get("NO_FP") == "1") == on, "No footprint needed"
        elif r < 0.65 and devs:
            pick = rnd.sample(devs, min(len(devs), rnd.randint(1, 3)))
            props_fill([e.id for e in pick])
            if rnd.random() < 0.5:
                # (half ticked, *varies*: a click ticks it on all of them)
                on = props_widget("nofp").checkState() == Qt.PartiallyChecked or \
                    rnd.random() < 0.5
                props_set("nofp", on)
                assert all((s.entities[e.id].attrs.get("NO_FP") == "1") == on for e in pick), \
                    "No footprint needed set %r in the Properties panel: %r" % (on, [
                        s.entities[e.id].attrs.get("NO_FP") for e in pick])
            else:
                loc = rnd.choice(["", "FIELD", "JB-1", "MCP"])
                props_set("LOC", loc)
                assert all(s.entities[e.id].attrs.get("LOC", "") == loc for e in pick), \
                    "Location set %r in the Properties panel: %r" % (loc, [
                        s.entities[e.id].attrs.get("LOC") for e in pick])
        elif r < 0.85 and fps_here:
            f = rnd.choice(fps_here)
            alld = [e for sh in p.sheets for e in sh.inserts() if tags.is_device(e)
                    and e.attrs.get("TAG")]
            props_fill([f.id])
            if alld and rnd.random() < 0.7:
                d = rnd.choice(alld)
                props_set("TAG", d.attrs["TAG"])
                got = tags.find_tag(p, d.attrs["TAG"])[1]
                assert s.entities[f.id].attrs.get("PARENT") == got.attrs.get("DEV"), \
                    "a footprint given %s's tag isn't linked to it" % d.attrs["TAG"]
            else:
                props_set("TAG", "ZZ%d" % rnd.randint(1, 99))
                assert not s.entities[f.id].attrs.get("PARENT"), "a footprint given a tag " \
                    "no device has is still linked"
        else:
            op_footprint()
        BC.missing_right(win, p)

    def op_location():
        # as Sheet properties and a device's Location do: the sheet's location, or a device's
        # own (LOC), set or cleared
        with p.edit("Location") as ed:
            if rnd.random() < 0.3 or not s.location:
                ed.sheet_meta(s, location=rnd.choice(["MCP", "MCP", "MCP", "", "PNL-2"]))
            else:
                ins = [e for e in s.entities.values() if isinstance(e, M.Insert)
                       and e.defn is not None and e.defn.kind == "symbol"]
                if ins:
                    e = rnd.choice(ins)
                    attrs = dict(e.attrs)
                    loc = rnd.choice(["FIELD", "JB-1", ""])
                    if loc:
                        attrs["LOC"] = loc
                    else:
                        attrs.pop("LOC", None)
                    ed.change(s, e.copy(attrs=attrs))

    def op_cable():
        # as Cables between locations' OK does: a run's cable, type, marking and a color
        rs = pull.runs(p)[0]
        if not rs:
            return
        r = rnd.choice(rs)
        c = pull.cable(p, r["key"])
        c.update(tag="W%d" % rnd.randint(100, 120), type=rnd.choice(["4C #14 TC", ""]),
                 marking=rnd.choice(list(pull.MARKINGS)))
        c["colors"][rnd.choice(r["conductors"])["num"]] = rnd.choice(["RED", "WHT/BLK", ""])
        new = dict(p.settings.get("cables") or {})
        new[r["key"]] = pull.clean_cable(c)
        with p.edit("Cables between locations") as ed:
            ed.project_settings({"cables": new})

    def op_attr_vis():
        # as Show or hide attributes does: on a few blocks, an attribute they show hidden or
        # shown again, in one step
        ins = [e for e in s.entities.values() if isinstance(e, M.Insert) and e.shown_names()]
        if not ins:
            return
        pick = rnd.sample(ins, min(len(ins), rnd.randint(1, 4)))
        name = rnd.choice(pick[0].shown_names())
        hide = rnd.random() < 0.6
        with p.edit("Show or hide attributes") as ed:
            for e in pick:
                if name in e.shown_names():
                    h = set(e.hidden)
                    (h.add if hide else h.discard)(name)
                    ed.change(s, e.copy(hidden=sorted(h)))

    def op_ratings():
        # (0.17.5) a symbol's attributes window, as a double-click opens it: its ratings typed
        # (a plain number or words), one hidden or shown, one turned; the drawing shows each
        # shown value (a plain number with its unit) at the angle asked, one step
        from PySide6.QtWidgets import QDialog, QDoubleSpinBox, QLineEdit, QCheckBox
        from kanzonascad import library_panel
        ins = [e for e in s.entities.values() if isinstance(e, M.Insert) and e.defn is not None
               and any(a["attr"] in M.RATING_FIELDS for a in e.defn.attr_texts)]
        if not ins:
            return
        e = rnd.choice(ins)
        fields = [a["attr"] for a in e.defn.attr_texts if a["attr"] in M.RATING_FIELDS]
        typed = {f: rnd.choice(["", "5", "460", "7.6", "1/2", "3 PH"]) for f in fields}
        turn = rnd.choice([n for n in e.shown_names() if n != "PINS"])
        ang = rnd.choice([0.0, 90.0, 270.0, 45.0])
        hide = rnd.choice(fields)
        hidden = rnd.random() < 0.3

        def answer(dlg):
            for f, t in typed.items():
                dlg.findChild(QLineEdit, "attr_" + f).setText(t)
            dlg.findChild(QDoubleSpinBox, "angle_" + turn).setValue(ang)
            dlg.findChild(QCheckBox, "show_" + hide).setChecked(not hidden)
            return QDialog.Accepted
        real = library_panel.QDialog.exec
        library_panel.QDialog.exec = answer
        try:
            win.edit_attributes(e)
        finally:
            library_panel.QDialog.exec = real
        got = s.entities[e.id]
        texts = [t for t in got.world_entities() if isinstance(t, M.Text)]
        for f, t in typed.items():
            want = M.attr_display(f, t)
            shown = [x for x in texts if x.text == want]
            if t and f not in got.hidden:
                assert shown, "%s typed %r: not shown on %s" % (f, t, got.block)
                if f == turn:
                    assert any(abs((x.angle - ang + 180.0) % 360.0 - 180.0) < 1e-6
                               for x in shown), "%s turned to %r: drawn at %r" % (
                        f, ang, [x.angle for x in shown])
                    BC.CHECKED["attribute turned"] += 1
            BC.CHECKED["rating shown as typed"] += 1
        assert (hide in got.hidden) == hidden, "%s %s, asked %s" % (
            hide, "hidden" if hide in got.hidden else "shown", "hidden" if hidden else "shown")
        assert abs((got.attr_angle(turn) - ang + 180.0) % 360.0 - 180.0) < 1e-6, \
            "%s's angle %r, asked %r (%s)" % (turn, got.attr_angle(turn), ang, got.block)

    # (0.17.5, the owner's drive with two pins named GND: moved, the wire on one stayed behind)
    two_gnd = M.BlockDef("Battery drive two grounds", "symbol",
                         [M.Polyline([(0.0, -0.75), (1.0, -0.75), (1.0, 0.75), (0.0, 0.75)],
                                     True)],
                         pins=[{"name": "L1", "pos": (0.0, 0.5)},
                               {"name": "GND", "pos": (0.0, -0.5)},
                               {"name": "T1", "pos": (1.0, 0.5)},
                               {"name": "GND", "pos": (1.0, -0.5)}],
                         prefix="VFD", tag_pos=(0.5, 0.9), role="device")

    # (0.19.8: a safety relay's column of pins, some of them picked one at a time for a bus)
    relay = M.BlockDef("Battery safety relay", "symbol",
                       [M.Polyline([(0.0, 1.0), (3.0, 1.0), (3.0, 4.5), (0.0, 4.5)], True)],
                       pins=[{"name": n, "pos": (0.0, 4.0 - 0.5 * i)} for i, n in enumerate(
                           ["S11", "S52", "S12", "S21", "S22", "13"])] +
                       [{"name": "A2", "pos": (3.0, 4.0)}],
                       prefix="SR", tag_pos=(1.5, 4.7), role="device")

    def op_bus_pick():
        # Bus, Pick pins: an evenly spaced few of a symbol's column clicked in any order; a
        # wire leaves each of them and none leaves the others (worked out from the pins)
        k = s.k()
        o = clear_of_drawing(k)
        if o is None:
            return
        before = set(s.entities)
        v.run(C.InsertCmd, relay, {})
        v.input_text(fmt((o[0] + 4.0 * k, o[1])))
        finish()
        new = [e for i, e in s.entities.items() if i not in before and isinstance(e, M.Insert)]
        if len(new) != 1:
            return
        e = new[0]
        col = [(n, q) for n, q in e.pin_points() if n != "A2"]
        step = rnd.choice([1, 2])
        start = rnd.randrange(0, len(col) - step)
        chosen = col[start::step][:rnd.randint(2, 4)]
        if len(chosen) < 2:
            return
        clicks = [q for _n, q in chosen]
        rnd.shuffle(clicks)
        far = min(q[0] for _n, q in col) - 2.0 * k
        v.run(C.BusCmd)
        type_in(v, "P", *(fmt(q) for q in clicks))
        type_in(v, "")
        if v.cmd is None or getattr(v.cmd, "step", "") != "path" or len(v.cmd.points) != 1:
            finish()
            return
        type_in(v, fmt((far, v.cmd.points[0][1])))
        finish()
        made = [w for i, w in s.entities.items() if i not in before and isinstance(w, M.Wire)]
        ends = {tuple(q) for w in made for q in (w.points[0], w.points[-1])}
        for n, q in col:
            want = any(G.dist(q, c) <= 1e-9 for c in clicks)
            assert (tuple(q) in ends) == want, "Bus from picked pins: %s %s a wire" % (
                n, "has no" if want else "got")
        BC.CHECKED["bus from picked pins"] += 1

    def op_column_feed():
        # (0.19.11: drops fed down a column, each drawn on from the corner of the one before,
        # as the owner's page 12: with taps numbered apart, each drop but the last has a
        # number of its own, off the run's)
        k = s.k()
        o = clear_of_drawing(k)
        if o is None:
            return
        before = set(s.entities)
        n = rnd.randint(2, 4)
        x0, x1, top = o[0] + 2.0 * k, o[0] + 4.0 * k, o[1] + (2.0 * n + 1.0) * k
        paths = [[(o[0], top + k), (x0, top + k), (x0, top), (x1, top)]]
        for i in range(1, n):
            y = top - 2.0 * i * k
            paths.append([(x1, y), (x0, y), (x0, y + 2.0 * k)])
        for pts in paths:
            v.run(C.WireCmd)
            type_in(v, *(fmt(q) for q in pts))
            finish()
        if not wirenums.enabled(p) or wirenums.tap_mode(p) == "same":
            return
        made = [w for i, w in s.entities.items() if i not in before and isinstance(w, M.Wire)]
        tol = 1e-6 * max(1.0, k)

        def num_at(q):
            got = {w.num for w in made if w.num and any(G.dist(q, r) <= tol for r in w.points)}
            return got.pop() if len(got) == 1 else None
        drops = [num_at((x1, top - 2.0 * i * k)) for i in range(n)]
        if None in drops or any(w.own_num or w.same_num for w in made):
            return                      # (a drop not drawn as asked: a snap took it elsewhere)
        assert len(set(drops[:-1])) == n - 1 and drops[-1] not in drops[:-1], \
            "a column of drops shares a number: %r" % drops
        BC.CHECKED["column of drops numbered apart"] += 1

    def op_pdb():
        # (0.21: a power distribution block and its outlets: each outlet's wire on phase j
        # takes the block's phase j number with the outlet's letter; worked out from the block
        # and the outlets' numbers, not the numbering)
        k = s.k()
        o = clear_of_drawing(k)
        if o is None or not wirenums.enabled(p):
            return
        before = set(s.entities)
        v.run(C.InsertCmd, lib.get("symbol", "Distribution block 3-pole"), {})
        v.input_text(fmt((o[0] + 3.0 * k, o[1] + 6.0 * k)))
        finish()
        pdb = [e for i, e in s.entities.items() if i not in before and
               isinstance(e, M.Insert) and e.defn is not None and e.defn.wiring == "pdb"]
        if len(pdb) != 1 or not pdb[0].attrs.get("TAG"):
            return
        pdb = pdb[0]
        for _n, q in pdb.pin_points():
            v.run(C.WireCmd)
            type_in(v, fmt(q), fmt((q[0] - 2.0 * k, q[1])))
            finish()
        outs = []
        for i in range(rnd.randint(1, 3)):
            got = set(s.entities)
            v.run(C.InsertCmd, lib.get("symbol", "Distribution block outlet 3-pole"), {})
            v.input_text(fmt((o[0] + (1.0 + 3.0 * i) * k, o[1] + 2.0 * k)))
            if v.cmd is not None:
                v.input_text(pdb.attrs["TAG"])
            finish()
            new = [e for j, e in s.entities.items() if j not in got and isinstance(e, M.Insert)]
            if len(new) == 1:
                outs.append(new[0].id)
                for _n, q in new[0].pin_points():
                    v.run(C.WireCmd)
                    type_in(v, fmt(q), fmt((q[0] + 1.0 * k, q[1])))
                    finish()
        tol = 1e-6 * max(1.0, k)

        def num_at(q):
            got = {w.num for w in s.wires() if w.num and w.touches(q, tol)}
            return got.pop() if len(got) == 1 else None
        pdb = s.entities.get(pdb.id)
        if pdb is None:
            return
        base = {n: num_at(q) for n, q in pdb.pin_points()}
        if None in base.values():
            return
        assert len(set(base.values())) == 3, "a distribution block's phases share a number: %r" \
            % base
        for oid in outs:
            e = s.entities.get(oid)
            if e is None or e.attrs.get("PARENT") != pdb.attrs.get("DEV") or \
                    not (e.attrs.get("OUTLET") or "").isdigit():
                continue
            letter = wirenums.letters(int(e.attrs["OUTLET"]) - 1)
            for n, q in e.pin_points():
                got = num_at(q)
                if got is None:
                    continue
                want = base["L" + n[1:]] + letter
                assert got == want, "outlet %s's %s took %s, not %s" % (
                    e.tag_text().text, n, got, want)
                BC.CHECKED["distribution block outlets numbered by phase"] += 1

    def op_picture():
        # (0.21: a picture or a simple SVG brought in as the owner would, with Import picture
        # or SVG (or dropped): the picture kept in the project, 2" wide on paper, its middle
        # where it was put; the SVG's lines there, as many as it has; then edited, saved and
        # undone with everything else)
        k = s.k()
        o = clear_of_drawing(k)
        if o is None:
            return
        at = (o[0] + 3.0 * k, o[1] + 3.0 * k)
        before = set(s.entities)
        if rnd.random() < 0.5:
            got = win.import_picture(picture_file(out), at)
            new = [e for i, e in s.entities.items() if i not in before]
            assert len(new) == 1 and isinstance(new[0], M.Picture) and got == [new[0].id], \
                "a picture didn't come in as one: %r" % new
            e = new[0]
            assert abs(e.width - 2.0 * k) <= 1e-9 * k and \
                G.dist(e.center(), at) <= 1e-6 * max(1.0, k), \
                "a picture came in %.4g wide at %r, not %.4g at %r" % (e.width, e.center(),
                                                                       2.0 * k, at)
            BC.CHECKED["picture in as put"] += 1
        else:
            got = win.import_picture(svg_file(out), at)
            new = [e for i, e in s.entities.items() if i not in before]
            assert len(new) == SVG_PIECES and sorted(got) == sorted(e.id for e in new), \
                "an SVG brought in %d objects, not %d" % (len(new), SVG_PIECES)
            bb = None
            for e in new:
                bb = G.bbox_union(bb, e.bbox())
            mid = ((bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0)
            assert G.dist(mid, at) <= 1e-6 * max(1.0, k), "an SVG landed at %r, not %r" % (
                mid, at)
            BC.CHECKED["SVG in as lines"] += 1

    def op_assign_part():
        # (0.21: Assign part on a random handful of devices, as the owner would: every one
        # using the part's symbol takes its maker, catalog number and description, keeps its
        # tag, and the project keeps a copy of the part; worked out from the devices before)
        from kanzonascad import partsassign as PA
        from kanzonascad.library import Part
        devs = PA.devices(s, set(s.entities))
        if not devs:
            return
        pick = rnd.sample(devs, min(len(devs), rnd.randint(1, 4)))
        # (a part names its symbol as the library does: a symbol kept as "name (symbol)"
        # beside a footprint of its name is "name", Insert.block_name; 0.25, seed 4902)
        block = rnd.choice(pick).block_name
        part = Part(manufacturer=rnd.choice(["Allen-Bradley", "Siemens", "ABB"]),
                    catalog="BAT-%d" % rnd.randint(1, 10 ** 6), description="battery part",
                    symbol=block)
        win.library.save_part(part)
        before = {e.id: dict(e.attrs) for e in pick}
        v.set_selection(set(before))
        win.ask_part = lambda parts, brand: (part.id, brand)
        try:
            n = win.assign_part()
        finally:
            win.__dict__.pop("ask_part", None)
        want = [i for i in before if s.entities[i].block_name == block]
        assert n == len(want), "Assign part put the part on %d devices, not %d" % (n, len(want))
        for i, old in before.items():
            a = s.entities[i].attrs
            if i in want:
                assert (a.get("CAT"), a.get("PART"), a.get("TAG")) == \
                    (part.catalog, part.id, old.get("TAG")), \
                    "Assign part left %s with %r" % (old.get("TAG"), a)
            else:
                assert a == old, "Assign part changed a device of another symbol"
        assert p.settings["parts"][part.id]["catalog"] == part.catalog
        BC.CHECKED["part assigned to the devices of its symbol"] += 1

    def op_report_sheet():
        # (0.21: a report drawn on sheets of the project, as the owner would: every page in
        # its frame and clear of the title block, and every row's first cell on one of them,
        # worked out from the report itself)
        from kanzonascad import report_sheets as RS
        from kanzonascad.scalefit import outside
        key = rnd.choice(list(RS.kinds()))
        head, rows = RS.table(p, key)
        if len(rows) > 400:
            return                          # (a long report is many pages: kept quick)
        made = win.report_sheet(key)
        assert made and all(m.report == key for m in made), "Report sheet made no sheet"
        texts = set()
        for m in made:
            why = outside(p, m)
            assert why is None, "a %s sheet is drawn %s" % (key, why)
            texts |= {e.text.rstrip("\u2026") for e in m.entities.values()
                      if isinstance(e, M.Text)}
        for r in rows:
            first = str(r[0]) if r else ""
            if first:
                assert any(first.startswith(t) and t for t in texts), \
                    "the %s sheets left out %r" % (key, first)
        v.show_sheet(s.id)                  # (back to the sheet the steps are on)
        BC.CHECKED["report sheets hold their report"] += 1

    def op_io_list():
        # (0.21: an I/O list brought in as the owner would, with Import I/O list...: every
        # point of the list written beside its module's terminal, worked out from the module's
        # pins, nothing past its frame)
        from kanzonascad.scalefit import outside
        pts = sorted(rnd.sample(range(8), rnd.randint(1, 8)))
        path = os.path.join(out, "battery-io.csv")
        with open(path, "w", encoding="utf-8") as f:
            f.write("Slot,Catalog,Point,Tag,Description\n")
            for n in pts:
                f.write("%d,1734-IB8,%d,BAT%d,POINT %d\n" % (rnd.randint(1, 9), n, n, n))
        made = win.import_io_list(path)
        v.show_sheet(s.id)                  # (back to the sheet the steps are on)
        assert made, "Import I/O list made no sheet"
        texts = {}
        for sh in made:
            assert outside(p, sh) is None, "an I/O sheet is drawn past its frame"
            for e in sh.entities.values():
                if isinstance(e, M.Text):
                    texts[e.text] = (sh, e)
        for n in pts:
            got = texts.get("BAT%d  POINT %d" % (n, n))
            assert got is not None, "point %d of the I/O list is missing" % n
            sh, t = got
            mod = next(e for e in sh.inserts() if e.block == "1734-IB8 module")
            pin = dict(mod.pin_points())[str(n)]
            # (0.15" left of it and 0.03" up on paper: in the sheet's scale, the project's for
            # new sheets, which a step can change: seed 43 step 154)
            k = sh.k()
            assert G.dist((t.pos[0] + 0.15 * k, t.pos[1] - 0.03 * k), pin) < 1e-9, \
                "point %d's text isn't beside its terminal" % n
        BC.CHECKED["I/O list points beside their terminals"] += 1

    def io_wanted():
        """({group key: (addresses, locked)} of every wire group on a PLC module's input or
        output point, worked out from the modules' terminal texts, SLOT and ADDRn (and a PLC
        point symbol's ADDR), not from wirenums' own reading of them; addresses None for a
        group on a continued piece (its module's slot: not worked out here), the groups)."""
        gs, _dist = wirenums.groups(p)
        group = {(sh.id, w.id): k for k, members in gs.items() for sh, w in members}
        got = {}
        for sh in p.sheets:
            for e in sh.inserts():
                d = e.defn
                if d is None or d.prefix != "PLC":
                    continue
                pts = {}
                for t in d.entities:
                    m = isinstance(t, M.Text) and re.match(r"(\S+)\s+(IN|OUT)[ -](\d+)$",
                                                           t.text.strip())
                    if m:
                        pts.setdefault(m.group(1), (m.group(2)[0], int(m.group(3))))
                addr_sym = any(a["attr"] == "ADDR" for a in d.attr_texts)
                for name, q in e.pin_points():
                    if addr_sym:
                        a = (e.attrs.get("ADDR") or "").strip()
                    elif name not in pts:
                        continue
                    elif d.role == "child":
                        a = None
                    else:
                        kind, n = pts[name]
                        slot = (e.attrs.get("SLOT") or "").strip()
                        a = (e.attrs.get("ADDR%d" % n) or "").strip() or (
                            "%s:%s/%d" % (kind, slot, n) if slot else "")
                    for w in sh.query_point(q, 1e-6):
                        if getattr(w, "kind", "") == "wire" and w.touches(q, 1e-6):
                            g = group[(sh.id, w.id)]
                            cur = got.setdefault(g, set())
                            if cur is not None:
                                got[g] = None if a is None else cur | ({a} if a else set())
        return {g: (a, any(w.num_lock for _s, w in gs[g])) for g, a in got.items()}, gs

    def op_io_numbers():
        # (0.21: Number wires on PLC I/O points by their address, turned on and off as the
        # owner would in Schematic settings, on a module with wires on some of its points:
        # on, each such wire is numbered by its point's address, worked out from the module;
        # off, they take page numbers again)
        k = s.k()
        o = clear_of_drawing(k)
        if o is None or not wirenums.enabled(p):
            return
        block = rnd.choice(["1734-OB8E module", "1734-IB8 module", "1734-OE4C module",
                            "PLC digital output module, 16 points"])
        slot = rnd.choice(["", "1", "3", "7", "12"])
        before = set(s.entities)
        v.run(C.InsertCmd, lib.get("symbol", block), {"SLOT": slot} if slot else {})
        v.input_text(fmt((o[0] + 3.0 * k, o[1] + 6.0 * k)))
        finish()
        new = [e for i, e in s.entities.items() if i not in before and isinstance(e, M.Insert)]
        if len(new) != 1:
            return
        mod = new[0]
        pins = mod.pin_points()
        if rnd.random() < 0.4:
            # (an address kept on the module, as Import I/O list keeps it)
            n = rnd.randrange(4)
            with p.edit("Attributes") as ed:
                ed.change(s, mod.copy(attrs=dict(mod.attrs, **{"ADDR%d" % n:
                                                               "Local:9:O.Data.%d" % n})))
        for _name, q in rnd.sample(pins, rnd.randint(1, min(4, len(pins)))):
            v.run(C.WireCmd)
            v.input_text(fmt(q))
            if v.cmd is not None:
                v.input_text(fmt((q[0] - 2.0 * k, q[1])))
            finish()
        for on in (True, False):
            with p.edit("Schematic settings") as ed:
                ed.project_settings({"wire_numbers_io": on})
            want, gs = io_wanted()
            for g, (addrs, locked) in want.items():
                if addrs is None or locked or not addrs:
                    continue
                nums = {w.num for _s, w in gs[g]}
                if on:
                    assert nums == {sorted(addrs)[0]}, \
                        "a wire on PLC point %s is numbered %s" % (sorted(addrs), nums)
                    BC.CHECKED["wire on a PLC point numbered by its address"] += 1
                else:
                    assert not nums & addrs and all(
                        n and wirenums.split(TAP_END.sub("", n)) for n in nums), \
                        "with I/O numbering off, a wire on PLC point %s is %s" % (
                            sorted(addrs), nums)
                    BC.CHECKED["wire on a PLC point numbered again when turned off"] += 1
        if rnd.random() < 0.5:
            # (left on for the steps after: everything else works with it too)
            with p.edit("Schematic settings") as ed:
                ed.project_settings({"wire_numbers_io": True})

    def op_contact_blocks():
        # (0.19.10: an emergency stop with contact blocks in its column: joined by a dashed
        # line from it through the farthest, worked out from where they are; none of them
        # listed under it nor showing a reference of their own)
        k = s.k()
        o = clear_of_drawing(k)
        if o is None:
            return
        before = set(s.entities)
        v.run(C.InsertCmd, lib.get("symbol", "Emergency stop NC"), {})
        v.input_text(fmt((o[0] + 2.0 * k, o[1] + 3.0 * k)))
        finish()
        new = [e for i, e in s.entities.items() if i not in before and isinstance(e, M.Insert)]
        if len(new) != 1 or not new[0].attrs.get("DEV"):
            return
        es = new[0]
        first_pin = es.pin_points()[0][1]
        blocks = []
        for i in range(rnd.randint(1, 3)):
            name = rnd.choice(["Pushbutton contact NO", "Pushbutton contact NC"])
            got = set(s.entities)
            v.run(C.InsertCmd, lib.get("symbol", name), {})
            v.input_text(fmt((first_pin[0], first_pin[1] - (i + 1) * k)))
            while v.cmd is not None:
                v.input_text("")
            made = [e for j, e in s.entities.items() if j not in got and isinstance(e, M.Insert)]
            if len(made) != 1:
                return
            with p.edit("belongs") as ed:
                ed.change(s, made[0].copy(attrs=tags_mod.link_attrs(dict(made[0].attrs),
                                                                     s.entities[es.id])))
            blocks.append(made[0].id)
        es = s.entities[es.id]
        ys = [s.entities[b].pos[1] for b in blocks] + [es.pos[1]]
        tol = 1e-6 * max(1.0, k)
        mine = [(a, b) for a, b in XR.links(p, s) if abs(a[0] - es.pos[0]) <= tol and
                abs(b[0] - es.pos[0]) <= tol]
        assert mine and abs(min(a[1] for a, _b in mine) - min(ys)) <= tol and \
            abs(max(b[1] for _a, b in mine) - max(ys)) <= tol, \
            "contact blocks under %s not joined from it to the farthest: %r, blocks at %r" % (
                es.attrs.get("TAG"), mine, ys)
        boxes = [s.entities[b].bbox() for b in blocks]
        for x, y, *_r in XR.live(p, s):
            assert not any(bb[0] - k <= x <= bb[2] + k and bb[1] - 0.5 * k <= y <= bb[1]
                           for bb in boxes), "a joined contact block shows a reference"
        BC.CHECKED["contact blocks joined"] += 1

    def op_copy_onto_wire():
        # (a symbol copied, moved or pasted onto a wire cuts it between its pins, as one
        # inserted does: the owner, "it didn't automatically break the wires and reattach on
        # both terminations"; worked out from the pins and the wire)
        k = s.k()
        o = clear_of_drawing(k)
        if o is None:
            return
        before = set(s.entities)
        v.run(C.InsertCmd, lib.get("symbol", "Relay coil"), {})
        v.input_text(fmt((o[0] + 2.0 * k, o[1] + 3.0 * k)))
        finish()
        new = [e for i, e in s.entities.items() if i not in before and isinstance(e, M.Insert)]
        if len(new) != 1:
            return
        src = new[0]
        with p.edit("a wire") as ed:
            ed.add(s, M.Wire([o, (o[0] + 4.0 * k, o[1])]))
        how = rnd.choice(["copy", "move", "paste"])
        to = (src.pos[0], o[1])
        v.set_selection({src.id})
        if how == "paste":
            win.copy_clip()
            win.paste()
            if v.cmd is None:
                return
            b = v.cmd.base_pt
            type_in(v, fmt((b[0], b[1] - (src.pos[1] - o[1]))))
        else:
            v.run(C.CopyCmd if how == "copy" else C.MoveCmd)
            type_in(v, fmt(src.pos), fmt(to))
        finish()
        placed = [e for i, e in s.entities.items() if isinstance(e, M.Insert) and
                  e.block == "Relay coil" and G.dist(e.pos, to) <= 1e-6 * max(1.0, k)]
        if len(placed) != 1:
            return                      # (not placed there: snapped elsewhere, say)
        pins = [q for _n, q in placed[0].pin_points()]
        lo, hi = min(q[0] for q in pins), max(q[0] for q in pins)
        on = [x for x in s.wires() if all(abs(q[1] - o[1]) <= 1e-6 * max(1.0, k)
                                          for q in x.points) and
              min(q[0] for q in x.points) < hi and max(q[0] for q in x.points) > lo]
        assert not on, "a coil %s onto a wire left it running between its pins: %r" % (
            {"copy": "copied", "move": "moved", "paste": "pasted"}[how],
            [x.points for x in on])
        BC.CHECKED["symbol copied onto a wire cuts it"] += 1

    def op_paste_same_place():
        # (0.26, the owner: "pressing Enter instead of clicking drops the pasted objects at the
        # exact coordinates they were copied from": copied on this sheet, pasted with Enter on
        # another one, or on this one, as a user does it: select, Ctrl+C, the sheet, Ctrl+V,
        # Enter; each copy where its original is, worked out from the originals)
        QTest = _qt()[3]
        ents = [e for e in some() if not isinstance(e, (M.Wire, M.WireCross))]
        if not ents:
            return
        src = s
        want = sorted((type(e).__name__, place_of(e)) for e in ents)
        v.set_selection({e.id for e in ents})
        if not win.copy_clip():
            return
        to = rnd.choice(p.sheets)
        if to is not src:
            v.show_sheet(to.id)
        before = set(to.entities)
        win.paste()
        assert isinstance(v.cmd, C.PasteCmd), "Ctrl+V didn't start pasting"
        assert "Enter" in v._prompt[0], "the paste prompt doesn't say what Enter does: %r" % (
            v._prompt[0],)
        QTest.keyClick(v, Qt.Key_Return)
        assert v.cmd is None, "Enter didn't paste"
        new = [to.entities[i] for i in v.sel if i in to.entities and i not in before]
        got = sorted((type(e).__name__, place_of(e)) for e in new
                     if not isinstance(e, (M.Wire, M.WireCross)))
        assert got == want, "pasted with Enter %s, copied from %s (sheet %s to %s)" % (
            got, want, p.sheet_number(src), p.sheet_number(to))
        BC.CHECKED["paste with Enter: where it was copied from" +
                   (" (another sheet)" if to is not src else "")] += 1

    def op_circuit():
        # (0.29: Save circuit on a handful of objects, then Insert circuit, as the owner would:
        # select, Save circuit..., its base point (Enter: the lower left corner, or clicked),
        # a name; Insert circuit..., R and S as wanted, where it goes. What it must have done
        # worked out from the circuit and the project before: BC.circuit_placed)
        ents = some(rnd.randint(1, 8))
        kids = {e.attrs.get("PARENT") for e in s.inserts() if e.attrs.get("PARENT")}
        devs = [e for e in s.inserts() if tags_mod.is_device(e) and e.attrs.get("DEV") in kids]
        if devs and rnd.random() < 0.6:
            # (a device with its contacts on this sheet, as a rung is saved, and maybe one
            # contact without its device)
            dev = rnd.choice(devs)
            ents += [dev] + [e for e in s.inserts()
                             if e.attrs.get("PARENT") == dev.attrs["DEV"] and
                             rnd.random() < 0.8]
        ents = list({e.id: e for e in ents}.values())
        if not ents:
            return
        v.set_selection({e.id for e in ents})
        name = "Battery circuit %d" % rnd.randint(1, 4)
        win.ask_circuit_details = lambda name_="": (name, rnd.choice(["Control", ""]), "")
        try:
            v.run(C.SaveCircuitCmd)
            if rnd.random() < 0.5:
                v.input_text("")
            else:
                v.input_text(fmt(pt()))
        finally:
            win.__dict__.pop("ask_circuit_details", None)
        finish()
        got = win.library.circuits()[0].get(name)
        assert got is not None, "Save circuit didn't keep %s" % name
        if rnd.random() < 0.3:
            to = rnd.choice(p.sheets)
            if to is not v.sheet():
                v.show_sheet(to.id)
        sh = v.sheet()
        v.set_selection(set())
        before = {"ids": set(sh.entities), "undo": len(p.undo_stack),
                  "devs": {e.attrs.get("DEV") for x in p.sheets for e in x.inserts()},
                  "links": set(wirenums.connectors(p))}
        win.ask_circuit = lambda: got
        try:
            win.insert_circuit()
        finally:
            win.__dict__.pop("ask_circuit", None)
        assert isinstance(v.cmd, C.InsertCircuitCmd), "Insert circuit didn't start"
        angle, scale = 0.0, 1.0
        for _i in range(rnd.randint(0, 3)):
            v.input_text("R")
            angle = (angle + 90.0) % 360.0
        if rnd.random() < 0.3:
            scale = rnd.choice([0.5, 2.0, 1.5])
            v.input_text("S")
            v.input_text("%g" % scale)
        at = pt()
        v.input_text(fmt(at))
        assert v.cmd is None, "Insert circuit still running after its point"
        BC.circuit_placed(p, sh, got, at, angle, scale, before)
        if rnd.random() < 0.2:
            p.undo()
            assert set(sh.entities) == before["ids"], "Undo left part of the circuit"
            BC.CHECKED["circuit undone in one step"] += 1

    def op_same_name_pins():
        # a symbol with two pins of one name, a wire on each pin, off on its own; moved,
        # scooted or turned through the commands: every pin keeps its wire
        k = s.k()
        o = clear_of_drawing(k)
        if o is None:
            return
        before = set(s.entities)
        v.run(C.InsertCmd, two_gnd, {})
        v.input_text(fmt(o))
        finish()
        new = [e for i, e in s.entities.items() if i not in before and isinstance(e, M.Insert)]
        if len(new) != 1:
            return
        e = new[0]
        for _n, q in e.pin_points():
            out = -1.0 if q[0] < e.pos[0] + 0.5 * k else 1.0
            v.run(C.WireCmd)
            type_in(v, fmt(q), fmt((q[0] + out * k, q[1])))
            finish()
        e = s.entities[e.id]
        if not all(any(w.touches(q) for w in s.wires()) for _n, q in e.pin_points()):
            return                              # (a wire refused: nothing to check)
        how = rnd.choice(["move", "scoot", "rotate"])
        v.set_selection({e.id})
        if how == "move":
            v.run(C.MoveCmd)
            type_in(v, fmt(e.pos), fmt((e.pos[0] + 0.5 * k, e.pos[1] + 1.0 * k)))
        elif how == "scoot":
            v.run(C.ScootCmd)
            q = e.pin_points()[0][1]
            type_in(v, fmt(q), fmt((q[0], q[1] + 0.5 * k)))
        else:
            v.run(C.RotateCmd)
            type_in(v, fmt(e.pos), "90")
        finish()
        e = s.entities.get(e.id)
        if e is None:
            return
        left = [(n, q) for n, q in e.pin_points() if not any(w.touches(q) for w in s.wires())]
        assert not left, "%s: pins left without their wire: %s" % (how, left)
        BC.CHECKED["two pins of one name keep their wires"] += 1

    def op_run_props():
        # a DIN rail's or wire duct's Properties window, as a double-click opens it (with other
        # pieces of its kind selected, all of them can take the size): a random width, depth,
        # profile, length and part
        from PySide6.QtWidgets import QDialog
        from kanzonascad import dialogs
        runs = [e for e in s.entities.values() if isinstance(e, M.Run)]
        if not runs:
            return
        e = rnd.choice(runs)
        same = [o for o in runs if type(o) is type(e)]
        v.set_selection({o.id for o in rnd.sample(same, min(len(same), rnd.randint(1, 3)))}
                        | {e.id})

        def answer(dlg):
            if dlg.rail:
                dlg.profile.setCurrentIndex(rnd.randrange(dlg.profile.count()))
            else:
                dlg.width.setValue(rnd.choice([1.0, 1.5, 2.0, 3.0, 4.0, 0.75]))
                dlg.depth.setValue(rnd.choice([2.0, 3.0, 4.0, 5.0]))
            if rnd.random() < 0.3:
                dlg.length.setValue(rnd.choice([1.0, 6.0, 12.0, 30.0]))
            dlg.edits["CAT"].setText(rnd.choice(["", "F2X3LG6", "PN-%d" % rnd.randint(1, 9)]))
            if dlg.all is not None:
                dlg.all.setChecked(rnd.random() < 0.7)
            return QDialog.Accepted
        real = dialogs.RunPropertiesDialog.exec
        dialogs.RunPropertiesDialog.exec = answer
        try:
            win.edit_attributes(e)
        finally:
            dialogs.RunPropertiesDialog.exec = real

    def op_round_trip():
        # drawing slop: drawn objects moved away and back, or turned 90 degrees four times
        # about one point, through the commands, end exactly where they were
        kinds = (M.Line, M.Polyline, M.Circle, M.Arc, M.Text, M.MText, M.Hatch, M.Dimension,
                 M.Leader)
        ents = [e for e in s.entities.values() if isinstance(e, kinds)]
        if not ents:
            return
        pick = rnd.sample(ents, min(len(ents), rnd.randint(1, 4)))
        before = {e.id: e for e in pick}
        if rnd.random() < 0.5:
            d = (rnd.choice([0.1, 1.1, -2.7, 0.3]), rnd.choice([0.7, -0.35, 1.9]))
            for dx, dy in (d, (-d[0], -d[1])):
                v.set_selection(set(before))
                v.run(C.MoveCmd)
                type_in(v, "0,0", fmt((dx, dy)))
                finish()
            what = "moved %s and back" % (d,)
        else:
            c = pt()
            for _k in range(4):
                v.set_selection(set(before))
                v.run(C.RotateCmd)
                type_in(v, fmt(c), "90")
                finish()
            what = "turned 4 x 90 degrees about %s" % (c,)
        for i, e in before.items():
            assert i in s.entities, "%s gone after being %s" % (e.kind, what)
            BC.same_place(e, s.entities[i], what)
        BC.CHECKED["round trip"] += 1

    def op_fit():
        # Fit (the status bar's Scale list: the biggest standard scale the drawing fits at,
        # moved to the middle if need be), or a scale picked from that list
        from kanzonascad import scalefit
        if rnd.random() < 0.3:
            name, val = rnd.choice(scalefit.presets_like(s.scale_name))
            win._set_scale(name, val)
        elif scalefit.fit_for(p, s) is not None:        # (else it opens the Sheet scale window)
            if 1.0 / scalefit.fit_for(p, s)[1] > MAX_K:
                BC.CHECKED["Fit past 1:100 left out (drawings kept realistic)"] += 1
                return
            win.fit_scale()
            BC.fit_oracle(p, s)

    # ---- sheets of every size, turn and scale, several of them -------------------------------
    def op_world():
        world["o"] = rnd.choice([(0.0, 0.0), (0.0, 0.0), (480.0, -250.0),
                                 (-2400.0, 1700.0), (4000.0, 3000.0)])
        world["k"] = rnd.choice([1.0, 1.0, 1.0, 4.0, 24.0])

    def op_sheet():
        from kanzonascad import scalefit
        what = rnd.random()
        if what < 0.4:
            with p.edit("Sheet size") as ed:
                ed.sheet_meta(s, size=rnd.choice(sorted(M.SHEET_SIZES)))
        elif what < 0.7:
            scalefit.rotate(p, s, rnd.random() < 0.5)
        else:
            name, val = rnd.choice(scalefit.presets_like(s.scale_name) + [("", 1 / 24),
                                                                          ("", 1 / 48)])
            win._set_scale(name, val)

    def op_new_sheet():
        if len(p.sheets) >= 6:
            return
        # (0.19.4: a new sheet starts at the project's scale for its kind, Project properties;
        # the sheets already made keep theirs)
        if rnd.random() < 0.3:
            pick = rnd.choice(M.SCALE_PRESETS)
            with p.edit("New sheets' scale") as ed:
                ed.project_settings({rnd.choice(["scale_schematic", "scale_panel"]):
                                     [pick[1], pick[0]]})
        kept = {sh.id: (sh.scale, sh.scale_name) for sh in p.sheets}
        n = len(p.sheets)
        win.add_sheet()
        new = [sh for sh in p.sheets if sh.id not in kept]
        assert len(p.sheets) == n + 1 and len(new) == 1, "New sheet didn't add one sheet"
        sh = new[0]
        key = "scale_panel" if sh.kind == "panel" else "scale_schematic"
        want = tuple(p.settings.get(key) or (1.0, ""))
        assert (sh.scale, sh.scale_name) == (float(want[0]), want[1]), (
            "a new %s sheet is at %r, the project's %r" % (sh.kind, (sh.scale, sh.scale_name),
                                                           want))
        for other in p.sheets:
            if other.id in kept:
                assert (other.scale, other.scale_name) == kept[other.id], \
                    "a new sheet changed another sheet's scale"
        BC.CHECKED["new sheet at the project's scale"] += 1

    def op_switch_sheet():
        v.show_sheet(rnd.choice(p.sheets).id)

    def op_big():
        # a big outline far out (a cabinet at real size, an imported frame)
        o = world["o"]
        x, y = o[0] + rnd.uniform(-3000, 3000), o[1] + rnd.uniform(-3000, 3000)
        w, h = rnd.choice([40, 120, 600, 3000]), rnd.choice([30, 90, 400, 2200])
        v.run(C.LineCmd)
        type_in(v, fmt((x, y)), fmt((x + w, y)), fmt((x + w, y + h)))
        finish()

    # ---- what a command must do, from every object (not the index) --------------------------
    def op_snap():
        BC.snap_oracle(v, crnd)

    def op_zoom():
        BC.zoom_checks(v, crnd)

    def op_mouse_window():
        mouse_window(v, crnd, click_click=crnd.random() < 0.3)

    def op_blank_press():
        mouse_blank_press(v, crnd)

    def op_lasso():
        mouse_lasso(v, crnd)

    def op_drag():
        mouse_drag(v, crnd)

    def op_pan():
        mouse_pan(v, crnd)

    # ---- Print and a sheet in a window of its own (0.16) --------------------------------------
    def op_print():
        from PySide6.QtGui import QPageSize
        from kanzonascad import print_out
        chosen = rnd.sample(p.sheets, rnd.randint(1, min(4, len(p.sheets))))
        size = rnd.choice([(QPageSize.Letter, 8.5, 11), (QPageSize.Tabloid, 11, 17),
                           (QPageSize.AnsiD, 22, 34), (QPageSize.A4, 8.27, 11.69)])
        fit = rnd.random() < 0.7
        area = rnd.choice(print_out.AREAS)
        rect = None
        if area in ("display", "window"):
            chosen = [rnd.choice(chosen)]
            a, b = pt(), pt()
            rect = (a[0], a[1], b[0] + 0.25, b[1] + 0.25)
        turn_ok = rnd.random() < 0.7
        before, rev = norm(p.to_dict()), p.revision
        path = os.path.join(out, "print.pdf")
        n = print_out.print_sheets(p, print_out.pdf_printer(path, QPageSize(size[0]), 72),
                                   chosen, fit, rnd.random() < 0.8, area, rect, turn_ok)
        assert n == len(chosen)
        BC.printed(path, chosen)
        assert norm(p.to_dict()) == before and p.revision == rev, "printing changed the project"
        sheet = rnd.choice(chosen)
        page = (size[1], size[2]) if rnd.random() < 0.5 else (size[2], size[1])
        BC.print_lands(p, sheet, page[0], page[1], fit,
                       box=print_out.area_box(sheet, area, rect, p), turn_ok=turn_ok,
                       whole=area == "sheet")

    def op_window():
        listeners = len(p.listeners)
        w2 = win.new_window(rnd.choice(p.sheets).id)
        v2 = w2.view()
        assert v2.project is p, "the new window shows another project"
        v2.osnap_on = v2.snap_on = v2.polar_on = v2.ortho_on = False
        s2 = v2.sheet()
        n = len(s2.entities)
        a, b = pt(), pt()
        while b == a:                           # (a line of no length isn't drawn)
            b = pt()
        asked = []
        w2._maybe_save = lambda d: asked.append(d) or True
        try:
            v2.run(C.LineCmd)
            type_in(v2, fmt(a), fmt(b))
            if v2.cmd is not None:
                v2.cancel()
            assert len(s2.entities) == n + 1, \
                "a line drawn in the new window isn't in the project"
            if rnd.random() < 0.5:
                win.undo()                      # (Undo in the main window takes it back)
                assert len(s2.entities) == n
                w2.redo()
        finally:
            # (closed whatever happened: a window left open fails every later window step)
            assert w2.close(), "the new window didn't close"
            APP.processEvents()
        assert not asked, "closing a second window asked to save the project"
        BC.second_window(win, w2, p, listeners)
        w2.deleteLater()

    def op_distribute():
        ents = [e for e in s.entities.values() if not isinstance(e, (M.Wire, M.WireCross))]
        if len(ents) < 3:
            return
        sel = rnd.sample(ents, min(len(ents), rnd.randint(3, 6)))
        axis = rnd.choice([0, 1])
        # (their order before: objects bigger than the room between the outermost two get a
        # gap below nothing and can change order by their middles)
        order = [e.id for e in sorted(sel, key=lambda e: ((e.bbox()[axis] + e.bbox()[axis + 2])
                                                         / 2, e.id))]
        # (symbols, which wires land on, with Snap on: with it off they move by whatever evens
        # the gaps and a pin can stop by chance 0.0092" from a wire end, seed 5: the user's
        # doing, as a mouse drag's; mouse_drag does the same)
        snap = rnd.random() < 0.5 or any(isinstance(e, M.Insert) for e in sel)
        was = v.snap_on
        v.snap_on = snap
        try:
            v.set_selection({e.id for e in sel})
            v.run(C.DistributeCmd)
            if v.cmd is not None:
                v.input_text("H" if axis == 0 else "V")
        finally:
            v.snap_on = was
        finish()
        if snap:
            return
        # equal gaps between neighbours, the outermost two where they were: worked out from
        # the boxes (an object whose box another of them moved, as a wire on a pin, aside)
        boxes = [s.entities[i].bbox() for i in order if i in s.entities]
        if len(boxes) == len(sel) and not any(isinstance(e, M.Insert) for e in sel):
            gaps = [b[axis] - a[axis + 2] for a, b in zip(boxes, boxes[1:])]
            tol = 1e-6 * max(1.0, max(abs(c) for b in boxes for c in b))
            assert max(gaps) - min(gaps) <= tol, "distributed unevenly: %s" % gaps
            BC.CHECKED["distribute"] += 1

    def op_del_dot():
        dots = wires.junctions(s)
        if not dots:
            return
        q = rnd.choice(dots)
        v.run(C.DeleteDotCmd)
        v.cmd.pick(q)
        assert q not in wires.junctions(s), "Delete dot left the dot at %s" % (q,)
        assert wires.connects_at(s, q), "Delete dot cut the wires at %s" % (q,)
        if rnd.random() < 0.3:
            v.cmd.pick(q)
            assert q in wires.junctions(s), "a second click didn't bring the dot back"
        finish()
        BC.CHECKED["delete dot"] += 1

    def op_update_blocks():
        # Library > Update blocks from library... on a project whose copy of a symbol is old
        # (its tag elsewhere, as 0.15's were): the copies take the library's, and keep their
        # places, tags and wires (the near-miss and index checks after the step see the wires)
        placed = [e for e in s.inserts() if e.defn is not None and e.defn.kind == "symbol"
                  and lib.get("symbol", e.block) is not None]
        if not placed:
            return
        name = rnd.choice(placed).block
        old = p.blocks[name]
        if old.tag_pos is not None:
            with p.edit("an old copy") as ed:
                ed.block(M.BlockDef.from_dict(dict(
                    old.to_dict(), tag_pos=[old.tag_pos[0], old.tag_pos[1] - 0.08])))
        keep = {e.id: (e.pos, e.attrs.get("TAG")) for e in s.inserts() if e.block == name}
        saved = QMessageBox.question
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
        # ("the same as the library's", when nothing changed: a box nobody would close here)
        told = QMessageBox.information
        QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)
        try:
            win.update_blocks_from_library()
        finally:
            QMessageBox.question = saved
            QMessageBox.information = told
        assert p.blocks[name].same_as(lib.get("symbol", name)), "%s not updated" % name
        now = {e.id: (e.pos, e.attrs.get("TAG")) for e in s.inserts() if e.block == name}
        assert now == keep, "updating %s moved or retagged its copies" % name
        BC.CHECKED["update blocks"] += 1

    def op_pdf_import():
        # (0.17: Import PDF into this sheet... on a page written at random: lines, circles
        # and real text, turned any of four ways, at the sheet's scale or 1:1; every line,
        # circle and text comes in where the page put it, one undoable step, and goes on to
        # be moved, copied, undone and saved with everything else)
        from kanzonascad.pdf_samples import Page, write_pdf
        k = rnd.choice([1.0, s.k()])
        pg = Page(rnd.choice([8.5, 11.0, 17.0]) * 72, rnd.choice([8.5, 11.0]) * 72)
        lines, circles, texts = [], [], []
        for _i in range(rnd.randint(1, 12)):
            x, y = rnd.randint(1, 100) * 4.5, rnd.randint(1, 100) * 4.5
            q = (x + rnd.choice([0, 9, 18, 36]), y + rnd.choice([9, 18, 27]))
            pg.line((x, y), q)
            lines.append(((x, y), q))
        for _i in range(rnd.randint(0, 3)):
            c, r = (rnd.randint(10, 80) * 6.0, rnd.randint(10, 80) * 6.0), rnd.choice([3, 9, 18])
            pg.circle(c, r, fill=r == 3)
            circles.append((c, r))
        for i in range(rnd.randint(0, 4)):
            # (each on its own line, across and up and down: two words close on one line are
            # rightly read as one text, seed 306)
            at, a = (60.0 + i * 90.0, 500 + i * 60.0), rnd.choice([0, 90, 180, 270])
            word = rnd.choice(["CR", "M", "PB", "LT"]) + str(rnd.randint(1, 999))
            pg.text(at, word, 8, angle=a)
            texts.append((at, word, a))
        path = write_pdf(os.path.join(out, "page.pdf"), [pg])
        saved = win.__dict__.get("ask_pdf_import")
        win.ask_pdf_import = lambda *a: {"page": 1, "scale": k, "filled": False}
        try:
            steps = len(p.undo_stack)
            ids = win.import_pdf(path)
        finally:
            if saved is None:
                win.__dict__.pop("ask_pdf_import", None)
        assert len(p.undo_stack) == steps + 1, "Import PDF wasn't one step"
        got = [s.entities[i] for i in ids]

        def pt(q):
            return (round(q[0] / 72.0 * k, 6), round(q[1] / 72.0 * k, 6))

        def near(a, b):
            return abs(a[0] - b[0]) <= 1e-5 * max(1.0, k) and abs(a[1] - b[1]) <= 1e-5 * max(1.0, k)
        segs = [(e.p1, e.p2) for e in got if isinstance(e, M.Line)]
        for a, b in lines:
            assert any((near(pt(a), u) and near(pt(b), w)) or (near(pt(a), w) and near(pt(b), u))
                       for u, w in segs), "PDF line %s-%s didn't come in" % (a, b)
        rounds = [(e.center, e.radius) for e in got if isinstance(e, M.Circle)]
        for c, r in circles:
            assert any(near(pt(c), cc) and abs(rr - r / 72.0 * k) <= 1e-5 * max(1.0, k)
                       for cc, rr in rounds), "PDF circle at %s didn't come in" % (c,)
        words = [(e.text, e.pos, e.angle) for e in got if isinstance(e, M.Text)]
        for at, word, a in texts:
            assert any(w == word and near(pt(at), q) and abs(ang - a % 360) < 1e-6
                       for w, q, ang in words), "PDF text %s didn't come in: %s" % (word, words)
        BC.CHECKED["PDF import"] += 1

    def op_block_pins():
        # in a block's tab (Edit block...): pins added with Add pin, then renamed, moved,
        # reordered and deleted in Pins...; what Save block would make has exactly those pins
        # in that order; undone all the way, the tab is as it opened, and redone as it was
        # (closed without saving: the library stays as it is)
        name = rnd.choice(syms)
        d = win.edit_block("symbol", name)
        if d is None:
            return
        bp, sess, bs, bv = d.project, d.block_session, d.view.sheet(), d.view
        opened = norm({"sheets": [bs.to_dict()]})
        try:
            ox, oy = sess.offset
            bv.run(C.AddPinCmd)
            for _k in range(rnd.randint(1, 3)):
                q = (ox + rnd.randint(-8, 8) * 0.0625, oy + rnd.randint(-8, 8) * 0.0625)
                type_in(bv, "%r,%r" % q)
                offered = BE.next_pin_name(BE.pin_names(bp, sess))
                bv.enter()
                assert offered in BE.pin_names(bp, sess), "Add pin: %s not added" % offered
            bv.escape()
            rows = [(e.id, e.text.strip(), pos[0], pos[1])
                    for e, pos in BE.pin_markers(bp, sess)]
            rnd.shuffle(rows)
            if len(rows) > 1 and rnd.random() < 0.5:
                rows.pop(rnd.randrange(len(rows)))
            rows = [(eid, "P%d" % k if rnd.random() < 0.3 else n,
                     x + rnd.choice([0.0, 0.0625, -0.125]), y) for k, (eid, n, x, y)
                    in enumerate(rows)]
            names = [r[1] for r in rows]
            if len(set(names)) != len(names):
                assert BE.apply_pins(bp, sess, rows) is not None, "two pins, one name, taken"
            else:
                assert BE.apply_pins(bp, sess, rows) is None
                got = BE.to_block(bp, sess).defn.pins
                assert [(q["name"], q["pos"]) for q in got] == \
                    [(n, (BE._round(x), BE._round(y))) for _i, n, x, y in rows], \
                    "Pins...: %r, saved as %r" % (rows, got)
                BC.CHECKED["block pins arranged"] += 1
            after = norm({"sheets": [bs.to_dict()]})
            steps = len(bp.undo_stack)
            while bp.undo_stack:
                bp.undo()
            assert norm({"sheets": [bs.to_dict()]}) == opened, "block tab undone: not as it opened"
            for _k in range(steps):
                bp.redo()
            assert norm({"sheets": [bs.to_dict()]}) == after, "block tab redone: not as it was"
        finally:
            if bv.cmd is not None:
                bv.cancel()
            bp.saved_at = len(bp.undo_stack)
            win.close_tab(win.tabs.indexOf(d))
            APP.processEvents()

    def op_block_attrs():
        # in a block's tab: attributes added with Add attribute, clicked or stacked under the
        # ratings (S); what Save block would make has each one, where it went, a stacked one
        # in the stack after the others; undone all the way, the tab is as it opened, and
        # redone as it was (closed without saving)
        name = rnd.choice(syms)
        d = win.edit_block("symbol", name)
        if d is None:
            return
        bp, sess, bs, bv = d.project, d.block_session, d.view.sheet(), d.view
        opened = norm({"sheets": [bs.to_dict()]})
        try:
            ox, oy = sess.offset
            had = [a["attr"] for a in BE.to_block(bp, sess).defn.attr_texts if a.get("stack")]
            bv.run(C.AddAttrCmd)
            added = []
            for k in range(rnd.randint(1, 3)):
                attr = "BAT%d" % k
                assert bv.input_text(attr)
                if had and rnd.random() < 0.5:
                    assert bv.input_text("S")
                    added.append((attr, None))
                else:
                    q = (ox + rnd.randint(-8, 8) * 0.0625, oy + rnd.randint(-8, 8) * 0.0625)
                    type_in(bv, "%r,%r" % q)
                    added.append((attr, (BE._round(q[0] - ox), BE._round(q[1] - oy))))
            bv.input_text("")
            assert bv.cmd is None, "Add attribute: Enter didn't end it"
            got = {a["attr"]: a for a in BE.to_block(bp, sess).defn.attr_texts}
            for attr, at in added:
                assert attr in got, "Add attribute: %s not in the block" % attr
                if at is not None:
                    assert got[attr]["pos"] == at, "Add attribute: %s at %r, not %r" % (
                        attr, got[attr]["pos"], at)
            stack = [a["attr"] for a in BE.to_block(bp, sess).defn.attr_texts if a.get("stack")]
            want = [a for a, at in added if at is None]
            assert stack[:len(had)] == had and set(want) <= set(stack[len(had):]), \
                "Add attribute: stack %r, had %r, stacked %r" % (stack, had, want)
            BC.CHECKED["block attributes added"] += 1
            after = norm({"sheets": [bs.to_dict()]})
            steps = len(bp.undo_stack)
            while bp.undo_stack:
                bp.undo()
            assert norm({"sheets": [bs.to_dict()]}) == opened, "block tab undone: not as it opened"
            for _k in range(steps):
                bp.redo()
            assert norm({"sheets": [bs.to_dict()]}) == after, "block tab redone: not as it was"
        finally:
            if bv.cmd is not None:
                bv.cancel()
            bp.saved_at = len(bp.undo_stack)
            win.close_tab(win.tabs.indexOf(d))
            APP.processEvents()

    def terminal_count_check():
        # (0.22.2: Terminal count's totals worked out here from the wire numbers, not from
        # wirenums' taps: with taps numbered -1, -2 (and a tap off a tap -1a), a wire number
        # and each of its taps one terminal, one jumper fewer than terminals a tapped number)
        from kanzonascad import reports
        if wirenums.tap_mode(p) != "suffix" or not wirenums.enabled(p):
            return
        nums = {w.num for sh in p.sheets for w in sh.wires() if w.num}
        if any(w.num_lock or w.own_num for sh in p.sheets for w in sh.wires()):
            return                          # (a number typed: anything may be a "tap")
        tapped = {}
        for n in nums:
            # (a number by its PLC address too: O:7/4 tapped is O:7/4-1, the quick battery's
            # seed 11; 0.22.4: or 2007a, 2007-a, and off those 2007a1...: the shortest number
            # it starts with that the rest is a tap's ending of, lowercase, so a distribution
            # outlet's 1006A is not a tap of 1006)
            for k in range(1, len(n)):
                if n[:k] in nums and TAP_END.fullmatch(n[k:]):
                    tapped.setdefault(n[:k], set()).add(n)
                    break
        rows, (got_t, got_j) = reports.terminal_count_rows(p)
        # (a tap that lands on a PLC point, numbered by its address, has no -1 to go by: the
        # seed 44's O:3/3 tapped by Local:9:O.Data.1. It counts only when it really is the
        # address of a PLC point on the project, and every other tap is a -1 of its own number)
        addrs = set()
        if wirenums.by_io_address(p):
            for got in wirenums._assemble_all(p)[5].values():
                addrs.update(got)
        # each row a family (its number and its taps), headed by the number the others are -1,
        # -2... of (two wires each tapping the other, an outlet's 1006A and 1006A-1: shown the
        # other way round up to 0.22.2, the seed 12)
        want_fams = [{b} | v for b, v in tapped.items()]
        heads = {frozenset({b} | v): b for b, v in tapped.items()}
        extra = 0
        for r in rows:
            fam = {r[0]} | {t.strip() for t in r[1].split(",") if t.strip()}
            mine = [f for f in want_fams if f & fam]
            named = set().union(*mine) if mine else set()
            other = fam - named
            assert named <= fam, "Terminal count: %s's family %s left out" % (
                r[0], sorted(named - fam))
            # (with no -1 among them, all but one, whichever heads it, are addresses)
            odd = other - addrs if mine else (set() if len(fam - addrs) <= 1 else fam - addrs)
            assert not odd, \
                "Terminal count: %s's taps %s neither -1, -2... nor a PLC address" % (
                    r[0], sorted(odd))
            if len(mine) == 1 and not other:
                assert r[0] == heads[frozenset(mine[0])], \
                    "Terminal count: the row of %s headed by %s" % (
                        heads[frozenset(mine[0])], r[0])
                BC.CHECKED["terminal count: headed by the tapped number"] += 1
            if other:
                extra += len(other) if mine else len(other) - 1
                BC.CHECKED["terminal count: a tap numbered by its PLC address"] += 1
            if not mine:
                want_fams.append(set())         # (a family of an address tap alone)
        for f in want_fams:
            if f and not any(f & ({r[0]} | {t.strip() for t in r[1].split(",")}) for r in rows):
                raise AssertionError("Terminal count: tapped %s left out" % sorted(f))
        want_t = sum(len(f) for f in want_fams if f) + extra + \
            sum(1 for f in want_fams if not f)
        want_j = sum(len(f) - 1 for f in want_fams if f) + extra
        assert (got_t, got_j) == (want_t, want_j), \
            "Terminal count: %d terminals, %d jumpers; from the numbers %d, %d" % (
                got_t, got_j, want_t, want_j)
        BC.CHECKED["terminal count from the tap numbers"] += 1

    # (0.25: a symbol and a footprint of one name, in the library from the start)
    lib.save_block(M.BlockDef(BC.TWIN, "symbol", [M.Circle((0.25, 0), 0.1)],
                              pins=[{"name": "A1", "pos": (0, 0)}, {"name": "A2",
                                                                    "pos": (0.5, 0)}],
                              role="device", prefix="M"))
    lib.save_block(M.BlockDef(BC.TWIN, "footprint",
                              [M.Polyline([(0, 0), (1.5, 0), (1.5, 2.5), (0, 2.5)], True)]))

    def op_same_name():
        # (0.25) the symbol or the footprint named BC.TWIN placed from the Library (its insert
        # signal, as a double-click), or made again with Make block, of the other kind than
        # the one holding the plain name in the project (up to 0.25 Make block went over it);
        # each copy marked with the kind it was placed as (TWIN), which BC.twins_apart holds
        # every copy to through moves, copies, undo, redo and save/open
        kind = rnd.choice(["symbol", "footprint", "footprint", "make"])
        held = p.blocks.get(BC.TWIN)
        if kind == "make" and held is None:
            kind = rnd.choice(["symbol", "footprint"])
        before = set(s.entities)
        if kind == "make":
            kind = "footprint" if held.kind == "symbol" else "symbol"
            q = pt()
            with p.edit("draw") as ed:
                r = ed.add(s, M.Polyline([q, (q[0] + 1.0, q[1]), (q[0] + 1.0, q[1] + 0.5)],
                                         True))
            v.set_selection({r.id})
            real = win.ask_block_details
            win.ask_block_details = lambda ents: {
                "kind": kind, "name": BC.TWIN, "category": "", "description": "",
                "role": "device", "contact": "", "prefix": "M" if kind == "symbol" else "",
                "pin_names": ["A1", "A2"] if kind == "symbol" else [], "replace": True}
            try:
                v.run(C.MakeBlockCmd)
                typed = [q] + ([q, (q[0] + 1.0, q[1]), "", (q[0] + 0.5, q[1] + 0.75)]
                               if kind == "symbol" else [])
                for t in typed:
                    if v.cmd is not None:
                        v.input_text(fmt(t) if t else "")
                finish()
            finally:
                win.ask_block_details = real
        else:
            win.library_panel.insertRequested.emit(lib.get(kind, BC.TWIN), {})
            if v.cmd is not None:
                v.input_text(fmt(pt()))
            if v.cmd is not None and rnd.random() < 0.5:
                v.input_text("N")
            finish()
        new = [e for i, e in s.entities.items() if i not in before and isinstance(e, M.Insert)]
        if len(new) == 1:
            with p.edit("mark") as ed:
                ed.change(s, new[0].copy(attrs=dict(new[0].attrs, TWIN=kind)))
        BC.twins_apart(p)

    PIECES = "Battery piece color"
    lib.save_block(M.BlockDef(PIECES, "symbol", [M.Line((0, 0), (0.5, 0)),
                                                  M.Circle((0.25, 0), 0.1)],
                              pins=[{"name": "A1", "pos": (0, 0)}, {"name": "A2",
                                                                    "pos": (0.5, 0)}],
                              role="device", prefix="CR"))

    def op_block_piece_color():
        # (0.25) one piece of a block given a color of its own in the block's tab (Edit
        # block..., the Block tab's Color), saved (Save block, its copies updated): every copy
        # then draws that piece in that color and the other in the copy's own (the owner: "I
        # want to key it at the same layer but just change the color of ... a little
        # rectangle in the block"); ByLayer puts it back to the copy's
        from PySide6.QtGui import QColor
        from kanzonascad import no_wheel
        if not any(e.block_name == PIECES for sh in p.sheets for e in sh.inserts()) or \
                rnd.random() < 0.3:
            win.library_panel.insertRequested.emit(lib.get("symbol", PIECES), {})
            if v.cmd is not None:
                v.input_text(fmt(pt()))
            finish()
        d = win.edit_block("symbol", PIECES)
        if d is None:
            return
        circle = next(e for e in d.view.sheet().entities.values() if isinstance(e, M.Circle))
        color = rnd.choice(["#00ff00", "#ff00ff", None])
        d.view.set_selection({circle.id})
        pick = ("Choose a color...", True) if color else ("ByLayer (the layer's color)", True)
        real = (no_wheel.get_item, no_wheel.get_color)
        no_wheel.get_item = lambda *a, **k: pick
        no_wheel.get_color = lambda *a, **k: QColor(color or "#000000")
        try:
            win.acts["object_color"].trigger()
        finally:
            no_wheel.get_item, no_wheel.get_color = real
        got = d.view.sheet().entities[circle.id]
        assert (got.color, got.layer) == (color, circle.layer), "Color in the block's tab: %r" % (
            (got.color, got.layer),)
        from unittest import mock
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            assert win.save_block(), "Save block failed"
        for sh in p.sheets:
            for e in sh.inserts():
                if e.block_name != PIECES or e.defn is None:
                    continue
                cols = {type(w).__name__: w.color for w in e.world_entities()
                        if isinstance(w, (M.Line, M.Circle))}
                assert cols == {"Line": e.color, "Circle": color or e.color}, \
                    "a copy of %s draws its pieces %r (piece %r, copy %r)" % (
                        PIECES, cols, color, e.color)
                BC.CHECKED["a block piece's own color on its copies"] += 1

    def op_lock_file():
        # (0.25) the battery's project saved and held open for editing by this copy, as Open
        # holds it; opened in a second copy (a window of its own, someone on another
        # computer, who picks the question's default, Open read-only): it comes up read-only,
        # its Save refused with the file left as it was (after an edit in it, some of the
        # time); closed, it leaves this copy's lock note; and this copy closing it leaves none
        from kanzonascad import filelock as FL
        path2 = os.path.join(out, "locked.kzcad")
        p.save(path2, backups=0)
        with open(path2, "rb") as f:
            raw = f.read()
        mine = FL.acquire(path2, FL.Who("battery", "BATTERY-PC"))
        w2, _v2 = window()
        w2.lock_who = FL.Who("someone", "OTHER-PC")
        asked = []
        w2.ask_locked = lambda path, info: asked.append(info) or "read_only"
        try:
            d2 = w2.open_path(path2)
            assert d2 is not None and d2.project.read_only, "not opened read-only"
            assert [a.get("computer") for a in asked] == ["BATTERY-PC"], asked
            assert "(read-only)" in w2.windowTitle(), w2.windowTitle()
            if rnd.random() < 0.5:
                with d2.project.edit("line") as ed:
                    ed.add(d2.project.sheets[0], M.Line(pt(), pt()))
            assert not w2.save(), "a read-only project saved"
            with open(path2, "rb") as f:
                assert f.read() == raw, "Save wrote over a read-only project's file"
            d2.project.saved_at = len(d2.project.undo_stack)
            w2.close_tab(w2.tabs.indexOf(d2))
            got = FL.read(path2)
            assert got is not None and got["id"] == mine.info["id"], \
                "closing the read-only copy took the lock note: %r" % (got,)
        finally:
            for _w, o in w2.documents():
                o.project.saved_at = len(o.project.undo_stack)
            w2.close()
            mine.release()
        assert FL.read(path2) is None, "the lock note stayed after the project closed"
        BC.CHECKED["a project open elsewhere opened read-only"] += 1

    imported = {"symbol": [], "footprint": []}    # (names op_import_blocks brought in)

    def op_import_blocks():
        # (0.24: Library > Import blocks from folder..., through its window as a user would: a
        # folder of 1-3 block files written here, some names already in the library (each
        # skipped, replaced or kept both, as picked in the window); the library then holds
        # what the files say, worked out from what was written: names, kinds, pins and where
        # they are; then one of the symbols placed, and a wire lands on its pin)
        from kanzonascad import import_blocks_window as IB
        folder = tempfile.mkdtemp(dir=out, prefix="blocks-")
        names = []
        for _i in range(rnd.randint(1, 3)):
            old = imported["symbol"] + imported["footprint"]
            if old and rnd.random() < 0.3:
                names.append(rnd.choice(old))
            else:
                names.append("BAT BLOCK %d" % rnd.randint(1, 10 ** 9))
        names = list(dict.fromkeys(names))     # (one row a name: a clash with the library)
        want = block_files(folder, rnd, names)
        before = {k: {n: b.to_dict() for n, b in lib.blocks(k)[0].items()}
                  for k in ("symbol", "footprint")}
        picks = {}

        def answer(dlg):
            from PySide6.QtWidgets import QComboBox, QPushButton, QTableWidget
            t = dlg.findChild(QTableWidget, "blocks")
            for i in range(t.rowCount()):
                name = t.item(i, 0).text()
                box = dlg.findChild(QComboBox, "taken_%d" % i)
                if box.isEnabled():
                    picks[name] = rnd.choice(["skip", "replace", "both"])
                    box.setCurrentIndex(box.findData(picks[name]))
            dlg.findChild(QPushButton, "import").click()
            return dlg.result()
        saved = (QFileDialog.getExistingDirectory, IB.ImportBlocksDialog.exec,
                 QMessageBox.information)
        told = []
        QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: folder)
        IB.ImportBlocksDialog.exec = answer
        QMessageBox.information = staticmethod(lambda *a, **k: told.append(a[2]))
        try:
            imp = win.import_blocks()
        finally:
            (QFileDialog.getExistingDirectory, IB.ImportBlocksDialog.exec,
             QMessageBox.information) = saved
            win.library_dialog.hide()
        after = {k: lib.blocks(k)[0] for k in ("symbol", "footprint")}
        if imp is None:
            # (the progress window cancelled: by the battery's dialog closer, on a slow run)
            assert told and told[-1].startswith("Cancelled"), told
            assert {k: {n: b.to_dict() for n, b in after[k].items()} for k in after} == \
                before, "Import blocks cancelled, the library changed"
            BC.CHECKED["import blocks cancelled: library as it was"] += 1
            return
        landed = {}
        for name, (kind, pins) in want.items():
            pick = picks.get(name)
            assert (pick is not None) == (name in before[kind]), \
                "%s: %s in the library, but %s offered" % (
                    name, "already" if name in before[kind] else "not", pick)
            if pick == "skip":
                assert after[kind][name].to_dict() == before[kind][name], \
                    "%s skipped, but changed in the library" % name
                BC.CHECKED["import blocks: a name taken, skipped"] += 1
                continue
            got_name = name
            if pick == "both":
                made = [n for n in after[kind] if n not in before[kind] and
                        re.fullmatch(re.escape(name) + r" \((\d+)\)", n)]
                assert len(made) == 1, "%s kept both: %r" % (name, made)
                got_name = made[0]
                assert after[kind][name].to_dict() == before[kind][name], \
                    "%s kept both, but the one in the library changed" % name
            b = after[kind].get(got_name)
            assert b is not None and b.kind == kind, "%s not in the library as a %s" % (
                got_name, kind)
            got = [(q["name"], q["pos"]) for q in b.pins]
            assert len(got) == len(pins) and all(
                g[0] == w[0] and G.dist(g[1], w[1]) <= 1e-9 for g, w in zip(got, pins)), \
                "%s's pins %r, written %r" % (got_name, got, pins)
            if pins:
                landed[got_name] = b
            if got_name not in imported[kind]:
                imported[kind].append(got_name)
            BC.CHECKED["import blocks: kind and pins as written"] += 1
        BC.CHECKED["import blocks: %s" % ("a name taken" if picks else "all new")] += 1
        if not landed:
            return
        k = s.k()
        o = clear_of_drawing(k)
        if o is None:
            return
        defn = landed[rnd.choice(sorted(landed))]
        before_ids = set(s.entities)
        v.run(C.InsertCmd, defn, {})
        v.input_text(fmt(o))
        finish()
        got = [e for i, e in s.entities.items() if i not in before_ids and isinstance(e, M.Insert)]
        assert len(got) == 1, "%s not placed: %r" % (defn.name, got)
        e = got[0]
        name, pin = rnd.choice(e.pin_points())
        # (straight out of the side of the symbol nearest the pin, past none of its other
        # pins: a wire never runs through a pin, so one that would isn't drawn at all)
        bb = wires.body_box(e)
        sides = sorted([(pin[0] - bb[0], (-1, 0)), (bb[2] - pin[0], (1, 0)),
                        (pin[1] - bb[1], (0, -1)), (bb[3] - pin[1], (0, 1))])
        others = [q for n, q in e.pin_points() if G.dist(q, pin) > wires.TOL]
        # (only out of a side the pin is on: a pin inside the symbol's drawing (an imported
        # block's pins go anywhere) is reached round the drawing, as Wire goes round symbols,
        # never straight through it; the long battery, seed 4902 step 2850: a pin half an
        # inch inside, the way round past another pin, refused as it should be)
        sides = [(m, d) for m, d in sides if m <= wires.TOL]
        if not sides:
            BC.CHECKED["imported symbol's pin inside its drawing: skipped"] += 1
            return
        ways = [(pin[0] + d[0] * 2.0 * k, pin[1] + d[1] * 2.0 * k) for _m, d in sides]
        ways = [a for a in ways if all(G.dist_to_segment(q, a, pin) > wires.TOL
                                       for q in others)]
        if not ways:
            BC.CHECKED["imported symbol's pin boxed in by its others: skipped"] += 1
            return
        a = ways[0]
        before_ids = set(s.entities)
        v.run(C.WireCmd)
        type_in(v, fmt(a), fmt(pin))
        finish()
        new = [w for i, w in s.entities.items() if i not in before_ids and isinstance(w, M.Wire)]
        ends = [q for w in new for q in (w.points[0], w.points[-1])
                if G.dist(q, pin) <= wires.TOL]
        assert ends, "a wire to %s's pin %s doesn't end on it" % (defn.name, name)
        assert any(n == name for x, n in wires.pins_on(s, ends[0]) if x.id == e.id), \
            "a wire on %s's pin %s isn't on it: %r" % (defn.name, name, wires.pins_on(s, ends[0]))
        BC.CHECKED["imported symbol takes a wire on its pin"] += 1

    def op_undo():
        for _i in range(rnd.randint(1, 4)):
            p.undo()

    def op_redo():
        for _i in range(rnd.randint(1, 4)):
            p.redo()

    def op_symbol_standard():
        # (0.29) the project's symbol standard changed (Project properties, Schematic): JIC
        # or IEC 60617, whose tags are made of IEC 81346-2 letters. With unlocked devices
        # tagged in the other standard's letters it asks "Retag the unlocked devices with the
        # <new> letters?" (the owner, Nov 27 2026), answered here at random: Yes retags them
        # all in the one Undo step (locked tags untouched, contacts following), No keeps every
        # tag, Cancel changes nothing; with none, it doesn't ask
        from unittest import mock
        from PySide6.QtWidgets import QComboBox
        from kanzonascad import dialogs

        def device_tags():
            return {(sh.id, e.id): (e.attrs.get("TAG"), tags_mod.locked(e)) for sh in p.sheets
                    for e in sh.entities.values() if tags_mod.is_device(e)}
        before, whole, steps = device_tags(), norm(p.to_dict()), len(p.undo_stack)
        now = p.settings.get("symbol_standard", "jic")
        new = "jic" if now == "iec" else "iec"
        retag = {(sh.id, e.id) for sh, e in tags_mod.to_retag(p, new)}
        answer = rnd.choice([QMessageBox.Yes, QMessageBox.No, QMessageBox.Cancel])
        asked = []

        def exec_(dlg):
            box = dlg.findChild(QComboBox, "symbol_standard")
            box.setCurrentIndex(box.findData(new))
            return QDialog.Accepted

        def question(_parent, _title, text, *_a):
            asked.append(text)
            return answer
        with mock.patch.object(dialogs.QDialog, "exec", exec_), \
                mock.patch.object(QMessageBox, "question", side_effect=question):
            win.project_properties(1)
        assert bool(asked) == bool(retag), "asked %r with %d to retag" % (asked, len(retag))
        if asked and answer == QMessageBox.Cancel:
            assert norm(p.to_dict()) == whole and len(p.undo_stack) == steps, \
                "Cancel changed the project"
            BC.CHECKED["the symbol standard: Cancel changed nothing"] += 1
            return
        assert p.settings.get("symbol_standard") == new, p.settings.get("symbol_standard")
        after = device_tags()
        for k, (tag, lock) in before.items():
            got = after.get(k)
            if k in retag and answer == QMessageBox.Yes:
                sh = p.sheet_by_id(k[0])
                e = sh.entities[k[1]]
                pre = tags_mod.prefix_for(p, e.defn)
                assert got[1] is False and tags_mod.split(got[0], pre) is not None, \
                    "%s not retagged with %s: %r" % (tag, pre, got)
            else:
                assert got == (tag, lock), "the symbol standard changed %r to %r" % (tag, got)
        if retag and answer == QMessageBox.Yes:
            assert not tags_mod.to_retag(p), "left in the other letters: %r" % [
                e.attrs.get("TAG") for _s, e in tags_mod.to_retag(p)][:6]
            index = tags_mod.devices(p)
            for sh in p.sheets:
                for e in sh.inserts():
                    if tags_mod.is_child(e) and e.attrs.get("PARENT") in index:
                        par = index[e.attrs["PARENT"]][1]
                        assert e.attrs.get("TAG") == par.attrs.get("TAG"), \
                            "contact %s of %s" % (e.attrs.get("TAG"), par.attrs.get("TAG"))
            BC.CHECKED["the symbol standard: Yes retagged the unlocked devices"] += 1
        elif retag:
            BC.CHECKED["the symbol standard: No kept the tags"] += 1
        else:
            BC.CHECKED["the symbol standard changed, nothing to ask, the tags kept"] += 1
        assert len(p.undo_stack) == steps + 1, "%d steps" % (len(p.undo_stack) - steps)
        done = norm(p.to_dict())
        p.undo()
        assert norm(p.to_dict()) == whole, "one Undo didn't restore the symbol standard's change"
        p.redo()
        assert norm(p.to_dict()) == done, "Redo didn't give the symbol standard's change back"
        BC.CHECKED["the symbol standard: one Undo restored everything"] += 1

    table = [(op_wire, 18), (op_bus, 3), (op_symbol, 14), (op_line, 4), (op_text, 3),
             (op_move, 6), (op_copy, 4), (op_rotate, 3), (op_erase, 4), (op_trim, 6),
             (op_trim_plain, 2), (op_delwire, 3), (op_delcomp, 4), (op_clean, 2),
             (op_scoot, 4), (op_align, 2), (op_crossing, 2), (op_rail, 2), (op_dim, 2),
             (op_leader, 3), (op_mtext, 2), (op_hatch, 3), (op_import, 1), (op_explode, 1),
             (op_usetb, 1), (op_title_block, 1), (op_footprint, 2), (op_location, 4), (op_cable, 2), (op_attr_vis, 2), (op_ratings, 2), (op_same_name_pins, 1), (op_wire_xref, 2), (op_sig_arrows, 2), (op_update_numbers, 2), (op_stretch, 2), (op_grips, 2), (op_lock_numbers, 2), (op_number_bus, 2),
             (op_fit, 2), (op_run_props, 2), (op_round_trip, 2), (op_world, 1), (op_sheet, 1), (op_new_sheet, 1),
             (op_switch_sheet, 2), (op_big, 1), (op_snap, 3), (op_zoom, 1),
             (op_mouse_window, 3), (op_blank_press, 2), (op_lasso, 2), (op_drag, 2), (op_pan, 1), (op_undo, 6),
             (op_redo, 4), (op_print, 2), (op_window, 2), (op_update_blocks, 1),
             (op_distribute, 2), (op_del_dot, 1), (op_symbol_on_bus, 2), (op_tag_grip, 2), (op_bus_land, 2), (op_dash_box, 2), (op_array, 2), (op_offset, 2), (op_mid_grip, 2), (op_number, 2), (op_wire_around, 2), (op_bus_around, 2), (op_wire_run, 2), (op_block_pins, 1), (op_block_attrs, 1), (op_pdf_import, 2), (op_tap, 2), (op_wire_label, 2), (op_fp_labels, 2), (op_wire_size, 2), (op_move_area, 2), (op_dim_units, 2), (op_frame, 1), (op_wire_color, 1), (op_arrow_pair, 1), (op_fp_label_color, 1), (op_fp_label_sizes, 2), (op_xref_device, 1), (op_bus_pick, 1), (op_copy_onto_wire, 1), (op_contact_blocks, 1), (op_column_feed, 1), (op_source_master, 1), (op_pdb, 1), (op_picture, 1), (op_array_edit, 2), (op_assign_part, 1), (op_report_sheet, 1), (op_io_list, 1), (op_io_numbers, 1), (op_ladder, 2), (op_trace, 2),
             (op_import_blocks, 1), (op_props_panel, 3), (op_missing_fp, 2),
             (op_same_name, 3), (op_lock_file, 1), (op_block_piece_color, 1),
             (op_paste_same_place, 2),
             (op_dash_poly, 2), (op_join, 3), (op_bus_swap, 2), (op_fp_label_hidden, 2),
             (op_circuit, 3), (op_symbol_standard, 2)]
    fns = [f for f, w in table for _i in range(w)]
    roundtrips = 0
    path = os.path.join(out, "random.kzcad")
    for i in range(ops):
        fn = rnd.choice(fns)
        name = fn.__name__[3:]
        counts[name] = counts.get(name, 0) + 1
        try:
            s = v.sheet()               # (an undo can take away the sheet shown: the view moves)
            if dump_at is not None and i == dump_at:
                # (BATTERY_DUMP_AT=N: the project as it is before step N, to look into a failure)
                p.save(os.path.join(out, "before-step-%d.kzcad" % i), backups=0)
            fn()
            s = v.sheet()
            v.set_selection(set())
            check_sheet(s)
            blocks_known(p, s)
            BC.check_index(s, crnd)
            if i % 25 == 24:
                for other in p.sheets:
                    check_sheet(other)
                    blocks_known(p, other)
                BC.footprints_follow(p)
                BC.footprint_label_heights(p)
                BC.arrows_follow(p)
                BC.missing_right(win, p)
                BC.twins_apart(p)
            if i % 50 == 49:
                v.repaint()
                APP.processEvents()
            if i % 25 == 24:
                kinds.update(type(e).__name__ for e in s.entities.values())
                terminal_count_check()
                bom.table(p)
                bom.write_csv(p, os.path.join(out, "bom.csv"))
                runs_now = pull.runs(p)[0]
                pull.write_csv(p, os.path.join(out, "pull.csv"))
                for r in runs_now:
                    assert len(r["locs"]) >= 2 and r["conductors"], r
                if runs_now:
                    kinds.add("pull list")
            if i % 200 == 199:
                p.save(path, backups=0)
                q = M.Project.load(path)
                assert norm(q.to_dict()) == norm(p.to_dict()), "save and open differ"
                roundtrips += 1
                # (0.23.1: the sheets, or some of them, to PDF: its cross-references links)
                # (picked with the checks' own random numbers: the steps stay as they were)
                chosen = [sh for sh in p.sheets if crnd.random() < 0.7] or p.sheets[:1]
                pdf = os.path.join(out, "random.pdf")
                fileio.export_pdf(p, pdf, sheets=chosen)
                BC.pdf_links_right(p, pdf, chosen)
        except Exception:
            errors.append("step %d (%s):\n%s" % (i, name, traceback.format_exc()))
            if v.cmd is not None:
                v.cancel()
            if len(errors) >= 5:
                break
    final = norm(p.to_dict())
    n_undo = 0
    while p.undo_stack:
        p.undo()
        n_undo += 1
    back = norm(p.to_dict())
    for _i in range(n_undo):                # (redo what was undone: no further, the run may
        p.redo()                            # have ended on an undo, leaving steps to redo)
    again = norm(p.to_dict())
    p.saved_at = len(p.undo_stack)
    stats = "%d steps (%s); %d entities, %d wires, %d symbols at the end; %d save/open " \
            "round trips; %d undone; kinds seen: %s; checked to the end: %s; sheets %d" % (
                ops, ", ".join("%s %d" % kv for kv in sorted(counts.items())), len(s.entities),
                len(s.wires()), len(s.inserts()), roundtrips, n_undo, ", ".join(sorted(kinds)),
                ", ".join("%s %d" % kv for kv in sorted(BC.CHECKED.items())), len(p.sheets))
    win.close()
    if errors:
        raise AssertionError("%d step(s) failed (seed %d):\n%s" % (len(errors), seed,
                                                                 "\n".join(errors)))
    assert back["sheets"] == start["sheets"], "undo all the way didn't give the empty sheet: " \
        + first_difference(start["sheets"], back["sheets"])
    assert again == final, "redo all the way didn't give the final project: " + \
        first_difference(final, again)
    return stats


# ---- 2. every menu command ---------------------------------------------------------------------
CLOSER = None


class DialogCloser:
    """Closes any dialog or message box that opens (rejects it), and answers file dialogs
    with nothing chosen."""

    def __init__(self):
        self.closed = []
        self.timer = QTimer()
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.tick)
        self.saved = (QFileDialog.getOpenFileName, QFileDialog.getSaveFileName,
                      QFileDialog.getExistingDirectory, QFileDialog.getOpenFileNames)
        QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ("", ""))
        QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: ([], ""))
        QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ("", ""))
        QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: "")
        self.timer.start()

    def tick(self):
        w = QApplication.activeModalWidget()
        if w is not None:
            self.closed.append(w.windowTitle())
            if isinstance(w, QMessageBox):
                b = w.button(QMessageBox.No) or w.button(QMessageBox.Cancel) or \
                    w.button(QMessageBox.Ok)
                (b.click() if b is not None else w.reject())
            elif isinstance(w, QDialog):
                w.reject()
        for w in QApplication.topLevelWidgets():
            if isinstance(w, QDialog) and w.isVisible() and not w.isModal() and \
                    w.objectName() != "library_dialog":
                pass

    def stop(self):
        self.timer.stop()
        (QFileDialog.getOpenFileName, QFileDialog.getSaveFileName,
         QFileDialog.getExistingDirectory, QFileDialog.getOpenFileNames) = self.saved


def every_command(log, out):
    errors = []
    hook = sys.excepthook
    sys.excepthook = lambda *a: errors.append("".join(traceback.format_exception(*a)))
    closer = CLOSER
    seen = len(closer.closed)
    skip = {"quit", "close"}            # (they end the run; Close is checked last)
    done = 0
    try:
        win, v = window()
        v.osnap_on = v.snap_on = False
        # something to act on
        type_in_cmds(v, win)
        for phase in ("sheet", "title block", "no project"):
            if phase == "title block":
                win.acts["edit_title_block"].trigger() if "edit_title_block" in win.acts \
                    else None
            if phase == "no project":
                for i in reversed(range(win.tabs.count())):
                    d = win.tabs.widget(i)
                    if hasattr(d, "project"):
                        d.project.saved_at = len(d.project.undo_stack)
                    win.close_tab(i)
            for key, act in sorted(win.acts.items()):
                if key in skip or not act.isEnabled():
                    continue
                before = len(errors)
                try:
                    act.trigger()
                    for _i in range(5):
                        APP.processEvents()
                    view = win.view()
                    if view is not None and view.cmd is not None:
                        view.cancel()
                    if act.isCheckable():
                        act.trigger()           # (and back)
                    APP.processEvents()
                except Exception:
                    errors.append("%s (%s): %s" % (key, phase, traceback.format_exc()))
                if len(errors) > before:
                    errors[-1] = "[%s, %s] %s" % (key, phase, errors[-1])
                done += 1
            # a project for the next phase
            if phase == "sheet" and win.view() is None:
                win.new_project()
        # Check for updates (manual) asked GitHub: its answer, arriving after this window is
        # done with, opened a message box no one closed (the next test hung). Cancel it: a
        # cancelled check says nothing
        checker = getattr(win, "_update_checker", None)
        if checker is not None and getattr(checker, "_reply", None) is not None:
            checker._reply.abort()
        win.close()
        win.deleteLater()
    finally:
        sys.excepthook = hook
    if errors:
        raise AssertionError("%d command(s) raised:\n%s" % (len(errors), "\n".join(errors)))
    return "%d menu commands triggered over 3 phases; %d dialogs opened and closed" % (
        done, len(closer.closed) - seen)


def type_in_cmds(v, win):
    v.run(C.WireCmd)
    type_in(v, "1,5", "11,5")
    v.run(C.InsertCmd, win.library.get("symbol", "Contact NO"), {})
    type_in(v, "4,5")
    if v.cmd is not None:
        v.cancel()
    v.run(C.LineCmd)
    type_in(v, "1,1", "3,1", "")
    v.set_selection(set(list(v.sheet().entities)[:2]))


# ---- 3. files --------------------------------------------------------------------------------
def mixed_project(win):
    """A project with every kind of object: wires and a bus, symbols (contacts on a coil,
    3-pole, terminals), text, lines, circles, arcs, a crossing, a double landing, panel sheet
    with rail, duct and dimensions."""
    v = win.view()
    v.osnap_on = v.snap_on = v.polar_on = v.ortho_on = False
    p = v.project
    lib = win.library
    with p.edit("settings") as ed:
        ed.project_settings({"wire_crossing": "loop"})
    for y in (7, 6, 5, 4):
        v.run(C.WireCmd)
        type_in(v, "1,%d" % y, "15,%d" % y)
        if v.cmd is not None:
            v.cmd.enter()
    v.run(C.WireCmd)
    type_in(v, "8,8", "8,3")
    if v.cmd is not None:
        v.cmd.enter()
    v.run(C.InsertCmd, lib.get("symbol", "Relay coil"), {"TAG": "CR1"})
    type_in(v, "12,7")
    for x, y in ((3, 7), (5, 6)):
        v.run(C.InsertCmd, lib.get("symbol", "Contact NO"), {})
        type_in(v, "%d,%d" % (x, y))
        if v.cmd is not None:
            v.input_text("")
    v.run(C.InsertCmd, lib.get("symbol", "Circuit breaker 3-pole"), {"TAG": "CB1"})
    type_in(v, "3,2")
    # (0.19) a PLC I/O module drawn whole, its slot shown
    v.run(C.InsertCmd, lib.get("symbol", "1734-IB8 module"), {"TAG": "PLC1", "SLOT": "2"})
    type_in(v, "20,8")
    while v.cmd is not None:
        v.cmd.enter()
    # (0.21) a timer coil placed flipped: its "TR" read backwards in AutoCAD's copy
    v.run(C.InsertCmd, lib.get("symbol", "Timer coil"), {"TAG": "TR1"})
    type_in(v, "F")
    type_in(v, "14,1")
    while v.cmd is not None:
        v.cmd.enter()
    assert any(e.block == "Timer coil" and e.mirror for e in v.sheet().inserts())
    # (0.17.5) a motor with its ratings, one hidden, one and its tag turned
    v.run(C.InsertCmd, lib.get("symbol", "Motor 3-phase"), {"TAG": "MTR1"})
    type_in(v, "6,2")
    while v.cmd is not None:
        v.cmd.enter()
    mtr = [e for e in v.sheet().inserts() if e.block == "Motor 3-phase"][-1]
    with p.edit("ratings") as ed:
        ed.change(v.sheet(), mtr.copy(attrs=dict(mtr.attrs, HP="5", VOLTS="460", FLA="7.6"),
                                      hidden=["FLA"]).with_attr_angle("HP", 90.0)
                  .with_attr_angle("TAG", 30.0))
    # (0.18.2) the wire layer preset, a striped 24 VDC common and a wire of its own size
    from kanzonascad import wirelayers
    with p.edit("wire layers") as ed:
        wirelayers.add_preset(ed, p)
        ed.add(v.sheet(), M.Wire([(1.0, 0.5), (4.0, 0.5)], layer="24VDC BLU-WHT"))
        ed.add(v.sheet(), M.Wire([(9.0, 0.5), (12.0, 0.5)], layer="480V BLK", awg="10"))
    # (0.18) a pair of source and destination arrows through the command
    with p.edit("wires for arrows") as ed:
        wa = ed.add(v.sheet(), M.Wire([(1.0, 1.0), (4.0, 1.0)]))
        wb = ed.add(v.sheet(), M.Wire([(9.0, 1.0), (12.0, 1.0)]))
    v.run(C.SignalArrowsCmd)
    v.cmd.pick(wa.points[-1])
    v.cmd.pick(wb.points[0])
    if v.cmd is not None:
        v.cmd.enter()
    coil = [e for e in v.sheet().inserts() if e.attrs.get("TAG", "").startswith("CR")][0]
    pin = max((q for _n, q in coil.pin_points()), key=lambda q: q[0])
    v.run(C.WireCmd)
    type_in(v, "%g,%g" % pin, "%g,%g" % (pin[0] + 2, pin[1] + 1))
    if v.cmd is not None:
        v.cmd.enter()
    v.run(C.TextCmd)
    type_in(v, "1,9", "BATTERY TEST")
    if v.cmd is not None:
        v.cmd.enter()
    with p.edit("shapes") as ed:
        s = v.sheet()
        ed.add(s, M.Circle((14, 9), 0.4))
        ed.add(s, M.Arc((12, 9), 0.4, 0, 180))
        panel = p.make_sheet("Panel")
        ed.add_sheet(panel)
    v.show_sheet(panel.id)
    with p.edit("panel") as ed:
        ed.sheet_meta(panel, kind="panel")
        ed.sheet_scale(panel, 0.25)
        ed.add(panel, M.Rail((4, 4), (34, 4), "TS35x7.5", *M.RAIL_PROFILES["TS35x7.5"][1:]))
        ed.add(panel, M.Duct((4, 10), (34, 10), "", 2, 3))
        ed.add(panel, M.Dimension((4, 4), (34, 4), (19, 1), height=0.125 * panel.k()))
        ed.add(panel, M.Dimension((4, 10), (5.5625, 10), (5, 12), height=0.125 * panel.k(),
                                  units="1/16"))
        ed.sheet_meta(panel, show_title_block=False)
    # (0.24.1) a footprint whose label lines have sizes of their own, in its block and on the
    # copy, one turned and drawn as set (Keep readable off), on the 1:4 panel sheet
    fpn = sorted(n for n, d in lib.blocks("footprint")[0].items() if d.builtin)[0]
    fpd = M.BlockDef.from_dict(dict(lib.get("footprint", fpn).to_dict(),
                                    label_sizes={"TAG": 0.12}))
    with p.edit("a footprint with sized label lines") as ed:
        ed.block(fpd)
        fpi = ed.add(panel, M.Insert(fpn, (20, 20), defn=p.blocks[fpn],
                                     attrs={"TAG": "M9", "CAT": "100-C09", "HP": "5"},
                                     tag_h=0.08 * panel.k(), label="tag,cat,HP",
                                     label_sizes={"HP": 0.2}, label_as_set=["CAT"],
                                     attr_rot={"@CAT": 180.0}))
    assert {k: t.height for k, t in fpi.label_texts()} == {
        "tag": 0.12 * panel.k(), "cat": 0.08 * panel.k(), "HP": 0.2 * panel.k()}
    with p.edit("a wire showing its color") as ed:
        w0 = next(iter(p.sheets[0].wires()), None)
        if w0 is not None:
            ed.change(p.sheets[0], w0.copy(show_color=True))
    with p.edit("notes") as ed:
        s = p.sheets[0]
        ed.add(s, M.Leader([(14, 9), (15, 10), (16, 10)], "SEE NOTE 1"))
        ed.add(s, M.Leader([(12, 9), (13, 10.5)], "1", balloon=True))
        ed.add(s, M.MText((1, 11), "NOTES:\nLINE TWO OF THE NOTE", 0.125, 0.0, "TL", 3.0))
        ed.add(s, M.Polyline([(17, 1), (19, 1), (19, 2), (17, 2)], True))
        ed.add(s, M.Hatch([[(17, 1), (19, 1), (19, 2), (17, 2)]], "ANSI31", 45.0, 0.125))
        ed.add(s, M.Hatch([[(17, 3), (18, 3), (18, 4), (17, 4)]], "SOLID", 0.0, 0.125))
        ed.add(s, M.DashBox.from_corners((20, 1), (24, 4), text="FIELD WIRING\nBY OTHERS",
                                         height=0.1))
        # (0.26: a dashed polygon, an L round two devices)
        ed.add(s, M.DashPolygon([(25, 1), (29, 1), (29, 2.5), (27, 2.5), (27, 4), (25, 4)],
                                text="BY OTHERS", height=0.1))
        # (0.22: a ladder, on its layer as the command puts it; its rungs numbered when the
        # edit closes)
        ed.layer("LADDER", None, M.Layer("LADDER", M.ADAPTIVE).to_dict())
        ed.add(s, M.Ladder((25, 10.5), (31, 10.5), rungs=8, spacing=0.5, height=0.1))
    # locations: the schematic and the panel in the MCP, the coil in the field (its own LOC),
    # and the run between them given a cable (Cables between locations)
    from kanzonascad import pull
    with p.edit("locations") as ed:
        s = p.sheets[0]
        ed.sheet_meta(s, location="MCP")
        ed.sheet_meta(panel, location="MCP")
        coil = [e for e in s.inserts() if e.attrs.get("TAG", "").startswith("CR")][0]
        ed.change(s, coil.copy(attrs=dict(coil.attrs, LOC="FIELD")))
    rs = pull.runs(p)[0]
    assert rs and rs[0]["locs"] == ["MCP", "FIELD"], rs
    with p.edit("Cables between locations") as ed:
        ed.project_settings({"cables": {rs[0]["key"]: pull.clean_cable(
            {"tag": "W101", "type": "4C #14 SOOW", "marking": "colors",
             "colors": {rs[0]["conductors"][0]["num"]: "RED"}})}})
    # (0.25) devices without a footprint: CB1 ticked No footprint needed, PLC1 given a
    # footprint on the panel sheet (the coil is in the field)
    from kanzonascad import missing_fp, tags
    with p.edit("footprints") as ed:
        s = p.sheets[0]
        cb = [e for e in s.inserts() if e.attrs.get("TAG") == "CB1"][0]
        ed.change(s, cb.copy(attrs=missing_fp.with_flag(cb.attrs, True)))
        plc = [e for e in s.inserts() if e.attrs.get("TAG") == "PLC1"][0]
        ed.add(panel, M.Insert(fpn, (30, 20), defn=p.blocks[fpn],
                               attrs=tags.link_footprint({}, plc, p.blocks[fpn]),
                               tag_h=0.08 * panel.k(), label="tag"))
    got = {(sh.id, e.id) for sh, e in missing_fp.find(p).missing}
    assert got == BC.missing_footprints(p), (got, BC.missing_footprints(p))
    assert not any(e.attrs.get("TAG") in ("CB1", "PLC1", "CR1") for _sh, e in
                   missing_fp.find(p).missing), [e.attrs.get("TAG") for _sh, e in
                                                 missing_fp.find(p).missing]
    v.show_sheet(p.sheets[0].id)
    # (0.29) IEC symbols (a coil and its contact) and an Allen-Bradley module, then a saved
    # circuit of the coil's rung placed again through the commands, as the owner would
    s = p.sheets[0]
    v.run(C.InsertCmd, lib.get("symbol", "Relay coil (IEC)"), {})
    type_in(v, "20,10")
    v.run(C.InsertCmd, lib.get("symbol", "Contact NO (IEC)"), {})
    type_in(v, "17,10")
    iec = [e for e in s.inserts() if e.block == "Relay coil (IEC)"][0]
    type_in(v, iec.attrs["TAG"])
    v.run(C.InsertCmd, lib.get("symbol", "1769-IF4 module"), {"TAG": "PLC2", "SLOT": "3"})
    type_in(v, "26,8")
    while v.cmd is not None:
        v.cmd.enter()
    rung = {e.id for e in s.inserts() if e.block in ("Relay coil (IEC)", "Contact NO (IEC)")}
    v.set_selection(rung)
    win.ask_circuit_details = lambda name="": ("Mixed rung", "Control", "battery")
    try:
        v.run(C.SaveCircuitCmd)
        v.input_text("")
    finally:
        win.__dict__.pop("ask_circuit_details", None)
    circuit = lib.circuits()[0]["Mixed rung"]
    win.ask_circuit = lambda: circuit
    try:
        win.insert_circuit()
    finally:
        win.__dict__.pop("ask_circuit", None)
    type_in(v, "17,11")
    coils = [e for e in s.inserts() if e.block == "Relay coil (IEC)"]
    assert len(coils) == 2 and len({e.attrs["TAG"] for e in coils}) == 2, coils
    v.set_selection(set())
    # (0.21) a picture kept in the project (a logo), on the first sheet
    fileio.import_picture(p, p.sheets[0], picture_file(tempfile.mkdtemp()), (13.0, 8.0))
    return p


def block_files(folder, rnd, names):
    """1-3 block files written as AutoCAD keeps blocks (op_import_blocks): each a WBLOCK'd
    block (its drawing and attribute definitions in model space, named after the file), or a
    drawing of two named blocks placed in model space; random lines and circles, sometimes
    AutoCAD Electrical wire connections (X?TERMnn, with their pin numbers TERMnn or not), in
    inches or millimeters, a random base point. names: what to call them, in order. Returns
    what the library must then hold, worked out here: {name: (kind, [(pin name, (x, y))])}
    (inches, around the base point)."""
    import ezdxf
    want = {}
    names = list(names)
    n_file = 0
    while names:
        n_file += 1
        units = rnd.choice([1, 4])
        u = 25.4 if units == 4 else 1.0         # (drawing units an inch)
        doc = ezdxf.new()
        doc.header["$INSUNITS"] = units
        two = len(names) >= 2 and rnd.random() < 0.4
        mine = [names.pop(0) for _i in range(2 if two else 1)]
        for name in mine:
            if two:
                bx, by = rnd.randint(-4, 4) * 0.25, rnd.randint(-4, 4) * 0.25
                lay = doc.blocks.new(name, base_point=(bx * u, by * u))
            else:
                bx, by = rnd.randint(-4, 4) * 0.25, rnd.randint(-4, 4) * 0.25
                doc.header["$INSBASE"] = (bx * u, by * u, 0.0)
                lay = doc.modelspace()
            lay.add_line((0.0, 0.0), (u, 0.0))
            for _i in range(rnd.randint(0, 3)):
                a = (rnd.randint(0, 8) * 0.125, rnd.randint(0, 8) * 0.125)
                b = (rnd.randint(0, 8) * 0.125, rnd.randint(0, 8) * 0.125)
                if a != b:
                    lay.add_line((a[0] * u, a[1] * u), (b[0] * u, b[1] * u))
            if rnd.random() < 0.5:
                lay.add_circle((0.5 * u, 0.5 * u), rnd.choice([0.125, 0.25]) * u)
            pins = []
            if rnd.random() < 0.7:
                spots = rnd.sample([(x * 0.25, y * 0.25) for x in range(5) for y in range(5)],
                                   rnd.randint(1, 4))
                numbered = rnd.random() < 0.5
                for i, q in enumerate(spots):
                    nn = "%02d" % (i + 1)
                    lay.add_attdef("X%dTERM%s" % (rnd.choice([1, 2, 4, 8]), nn),
                                   (q[0] * u, q[1] * u), dxfattribs={"flags": 1})
                    shown = str(rnd.randint(1, 99)) if numbered else ""
                    if numbered:
                        lay.add_attdef("TERM" + nn, ((q[0] + 0.05) * u, (q[1] + 0.05) * u),
                                       text=shown)
                    pins.append((shown or str(i + 1), (q[0] - bx, q[1] - by)))
                lay.add_attdef("TAG1", (0.5 * u, 1.25 * u))
            want[name] = ("symbol" if pins else "footprint", pins)
            if two:
                doc.modelspace().add_blockref(name, (0.0, 3.0 * len(want)))
        # (a WBLOCK'd block is named after its file)
        doc.saveas(os.path.join(folder, "%s.%s" % ("blocks %d" % n_file if two else mine[0],
                                                   rnd.choice(["dxf", "DXF"]))))
    return want


SVG_PIECES = 4             # (svg_file's: a line, a rectangle, a circle and a text)


def svg_file(out):
    path = os.path.join(out, "battery.svg")
    if not os.path.isfile(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg" width="2in" height="1in" '
                    'viewBox="0 0 200 100"><line x1="0" y1="0" x2="200" y2="0"/>'
                    '<rect x="10" y="10" width="50" height="20"/>'
                    '<circle cx="100" cy="50" r="25"/>'
                    '<text x="10" y="90" font-size="20">PANEL</text></svg>')
    return path


def picture_file(out):
    path = os.path.join(out, "battery-logo.png")
    if not os.path.isfile(path):
        from PySide6.QtGui import QColor, QImage
        img = QImage(64, 32, QImage.Format_RGB32)
        img.fill(QColor("#2060a0"))
        img.save(path, "PNG")
    return path


def files(log, out):
    win, v = window()
    p = mixed_project(win)
    fileio.import_dxf(p, p.sheets[0], sample_dxf(out), at=(20, 6))
    notes = []
    path = os.path.join(out, "mixed.kzcad")
    p.save(path, backups=0)
    q = M.Project.load(path)
    assert norm(q.to_dict()) == norm(p.to_dict())
    notes.append("save/open")
    for i, s in enumerate(p.sheets):
        dxf = os.path.join(out, "mixed-%d.dxf" % (i + 1))
        fileio.export_dxf(p, s, dxf)
        ents, rep = fileio.read_dxf(dxf)
        assert len(ents) >= len(s.entities), (s.title, len(ents), len(s.entities))
        # (0.20: every symbol and footprint out as a block and back as the same one, its tag
        # and its pins where they were; worked out from the sheet, not the export)
        mine = sorted((e for e in s.inserts() if e.defn is not None),
                      key=lambda e: (e.pos[0], e.pos[1], e.block))
        back = sorted((e for e in ents if isinstance(e, M.Insert)),
                      key=lambda e: (e.pos[0], e.pos[1], e.block))
        assert len(mine) == len(back), "DXF blocks: %d out, %d back" % (len(mine), len(back))
        for a, b in zip(mine, back):
            assert fileio._block_name(a.block, {}) == b.block, \
                "DXF block %r came back as %r" % (a.block, b.block)
            assert G.dist(a.pos, b.pos) < 1e-6 and (a.attrs.get("TAG") or "") == \
                (b.attrs.get("TAG") or ""), "a block came back from DXF changed: %s %s" % (
                    a.block, a.attrs.get("TAG"))
            if a.defn.kind == "symbol":
                pa, pb = dict(a.pin_points()), dict(b.pin_points())
                assert set(pa) == set(pb) and all(G.dist(pa[n], pb[n]) < 1e-6 for n in pa), \
                    "a symbol's pins came back from DXF elsewhere: %s" % a.block
        # (0.21: no text of a block reads mirror-written in AutoCAD: a flipped copy's own texts
        # and attributes as the program draws them, readable; from the DXF, by its flags)
        import ezdxf
        for ref in ezdxf.readfile(dxf).modelspace().query("INSERT"):
            for t in list(ref.virtual_entities()) + list(ref.attribs):
                if t.dxftype() not in ("TEXT", "ATTRIB") or t.dxf.get("invisible", 0):
                    continue
                ext = t.dxf.get("extrusion", (0.0, 0.0, 1.0))
                fl = t.dxf.get("text_generation_flag", 0)
                assert not ((ext[2] < 0) ^ bool(fl & 2) ^ bool(fl & 4)), \
                    "%r of %s reads mirrored in the DXF" % (t.dxf.text, ref.dxf.name)
                BC.CHECKED["DXF block texts read right"] += 1
    notes.append("DXF out and in (%d sheets, blocks as blocks)" % len(p.sheets))
    pdf = os.path.join(out, "mixed.pdf")
    n = fileio.export_pdf(p, pdf)
    assert n == len(p.sheets) and open(pdf, "rb").read(4) == b"%PDF"
    # (0.23.1: each cross-reference a link to what it names; one to a sheet left out, none)
    links = BC.pdf_links_right(p, pdf, p.sheets)
    # (and its copy with the contacts on CR1, one more on the panel sheet at 1:4: references
    # from sheet to sheet; all of it, then the panel alone, its reference's sheet left out)
    r = M.Project.load(path)
    s0, panel = r.sheets[0], r.sheets[-1]
    coil = [e for e in s0.inserts() if e.attrs.get("TAG", "").startswith("CR")][0]
    dev = coil.attrs["DEV"]
    with r.edit("contacts on CR1") as ed:
        for c in [e for e in s0.inserts() if e.block == "Contact NO"]:
            ed.change(s0, c.copy(attrs=dict(c.attrs, PARENT=dev)))
        ed.add(panel, M.Insert(c.block, (20.0, 20.0), defn=c.defn,
                               attrs={"TAG": coil.attrs["TAG"], "PARENT": dev}))
    two = os.path.join(out, "mixed-linked.pdf")
    fileio.export_pdf(r, two)
    links += BC.pdf_links_right(r, two, r.sheets)
    fileio.export_pdf(r, two, sheets=[panel])
    BC.pdf_links_right(r, two, [panel])
    r.saved_at = len(r.undo_stack)
    notes.append("PDF (%d pages, %d cross-reference links)" % (n, links))
    from kanzonascad import pull, dialogs
    q_runs = pull.runs(q)[0]
    assert [r["name"] for r in q_runs] == [r["name"] for r in pull.runs(p)[0]]
    assert pull.cable(q, q_runs[0]["key"])["tag"] == "W101"
    n = pull.write_csv(p, os.path.join(out, "pull list.csv"))
    dialogs.write_pull_pdf(p, os.path.join(out, "pull list.pdf"))
    assert open(os.path.join(out, "pull list.pdf"), "rb").read(4) == b"%PDF"
    notes.append("pull list (%d run(s), %d conductor(s): CSV, PDF)" % (len(q_runs), n))
    tpl = templates.save(p, os.path.join(out, "Templates", "Mixed.kzcad"))
    t = templates.new_from(tpl)
    assert norm(t.to_dict())["sheets"] == norm(p.to_dict())["sheets"]
    assert t.path is None and not t.is_modified()
    notes.append("template and a new project from it")
    p.saved_at = len(p.undo_stack)
    win.close()
    return ", ".join(notes)


# ---- 4. speed ------------------------------------------------------------------------------
def speed(log, out):
    # (0.25 set aside what the sections before left alive (gc.freeze) for these steps: on CI
    # Python's collector went through it all, 3.27 s after a 3,000-step run, seed 4931; since
    # 0.26 the program does that itself, gcpolicy, and these steps are timed as they run)
    res = []
    p = M.Project.new()
    s = p.sheets[0]
    t = time.perf_counter()
    with p.edit("grid") as ed:
        for i in range(100):
            for j in range(120):
                ed.add(s, M.Wire([(j * 0.25, i * 0.25), (j * 0.25 + 0.25, i * 0.25)]))
        for j in range(0, 120, 4):
            ed.add(s, M.Wire([(j * 0.25 + 0.125, -0.5), (j * 0.25 + 0.125, 25.5)]))
    res.append(("12,030 wires added", time.perf_counter() - t, 5.0))
    t = time.perf_counter()
    cr = crossings.found(s)
    res.append(("crossings found (%d)" % len(cr), time.perf_counter() - t, 3.0))
    t = time.perf_counter()
    with p.edit("clean") as ed:
        got = wires.cleanup(ed, s)
    res.append(("clean up (%d joined)" % got["joined"], time.perf_counter() - t, 3.0))
    t = time.perf_counter()
    with p.edit("trim") as ed:
        w = s.wires()[5]
        pieces, ends = wires.trim_wire(s, w, w.points[0])
    res.append(("trim one wire among 12,000", time.perf_counter() - t, 0.1))
    t = time.perf_counter()
    for k in range(200):
        with p.edit("one") as ed:
            nw = ed.add(s, M.Wire([(40 + k * 0.1, 0), (40 + k * 0.1, 1)]))
            wires.tidy_new(ed, s, nw)
    res.append(("200 wires drawn with cleanup", time.perf_counter() - t, 2.0))
    t = time.perf_counter()
    p.undo()
    p.redo()
    res.append(("undo and redo", time.perf_counter() - t, 0.5))
    path = os.path.join(out, "big.kzcad")
    t = time.perf_counter()
    p.save(path, backups=0)
    M.Project.load(path)
    res.append(("save and open", time.perf_counter() - t, 5.0))
    slow = [r for r in res if r[1] > r[2]]
    text = "; ".join("%s %.2f s" % (n, d) for n, d, _b in res)
    assert not slow, "over budget: " + "; ".join("%s %.2f s (budget %.2f)" % r for r in slow)
    return text


# ---- 5. pictures -------------------------------------------------------------------------------
def pictures(log, out):
    try:
        import fitz                     # (PyMuPDF: on a developer's computer; not a dependency)
    except ImportError:
        return "skipped: PyMuPDF not installed (the PDF itself was checked in files)"
    pdf = os.path.join(out, "mixed.pdf")
    d = fitz.open(pdf)
    names = []
    for i, page in enumerate(d):
        png = os.path.join(out, "page-%d.png" % (i + 1))
        page.get_pixmap(dpi=80).save(png)
        names.append(os.path.basename(png))
    return ", ".join(names)


# ---- 6. a drawing as another program writes it -------------------------------------------------
def real_drawing(log, out, path=None):
    """A drawing as AutoCAD Electrical writes one (made here: hidden and moved attributes,
    description lines, a frame bigger than the sheet, far from the origin), or the owner's own
    (path), opened as a person opens one: it lands on the sheet and fits, its hidden attributes
    stay hidden, every check holds, Fit keeps "doesn't fit" off, and a save, a DXF out and in
    and a selection of everything give it back whole."""
    from kanzonascad import scalefit
    path = path or BC.ace_like_dxf(os.path.join(out, "ace_like_big.dxf"), devices=120)
    win, v0 = window()
    win.open_path(path)
    APP.processEvents()
    v = win.view()
    p, s = v.project, v.sheet()
    rnd = random.Random(5)
    check_sheet(s)
    BC.check_index(s, rnd)
    n = len(s.entities)
    hidden = sum(len(e.hidden) for e in s.entities.values() if isinstance(e, M.Insert))
    if path.endswith("ace_like_big.dxf"):
        assert hidden > 0, "no attribute stayed hidden"
        # (MFG, CAT and INST are hidden on the block: none of their values may show)
        shown = [t.text for e in s.entities.values() if isinstance(e, M.Insert)
                 for t in e.world_entities() if isinstance(t, M.Text)]
        assert not any(x in ("AB", "700-HA32A1", "PANEL") for x in shown), \
            "an attribute hidden on the block shows: %s" % [
                x for x in shown if x in ("AB", "700-HA32A1", "PANEL")][:3]
    assert scalefit.outside(p, s) is None, "opened, it runs %s" % scalefit.outside(p, s)
    if scalefit.fit_for(p, s) is not None:
        win.fit_scale()
        BC.fit_oracle(p, s)
    v.zoom("extents")
    assert BC.view_shows(v, s.extents())
    v.select_all()
    assert len(v.sel) == len([e for e in s.entities.values() if BC.selectable(v, e)])
    want = BC.expected_window(v, (-1e9, -1e9), (1e9, 1e9))
    got = {e.id for e in s.query((-1e9, -1e9, 1e9, 1e9))}
    assert want <= got, "the index misses %d objects of the drawing" % len(want - got)
    for _i in range(30):
        BC.snap_oracle(v, rnd)
    kz = os.path.join(out, "real.kzcad")
    p.save(kz, backups=0)
    q = M.Project.load(kz)
    assert norm(q.to_dict()) == norm(p.to_dict()), "save and open differ"
    dxf = os.path.join(out, "real-out.dxf")
    fileio.export_dxf(p, s, dxf)
    ents, _rep = fileio.read_drawing(dxf)
    assert len(ents) >= n, "the DXF out and in has %d objects of %d" % (len(ents), n)
    p.saved_at = len(p.undo_stack)
    win.close()
    return "%s: %d objects (%d attributes hidden), %s, fits; save/open, DXF out and in" % (
        os.path.basename(path), n, hidden, s.scale_text())


# ---- 6b. Fit on many drawings ------------------------------------------------------------------
def fit_many(log, out):
    n = BC.fit_cases(random.Random(13), 300)
    return "%d drawings of every size and place, with notes at their edges, on sheets of " \
        "every size, turn and scale: after Fit each fits, and the next bigger scale doesn't" % n


# ---- 7. Windows paths ----------------------------------------------------------------------------
def windows_paths(log, out):
    return BC.windows_paths(random.Random(11))


# ---- 8. speed on an imported drawing -------------------------------------------------------------
def speed_imported(log, out):
    """Hover, snaps, a lasso and a window on a drawing as AutoCAD Electrical writes one (big
    blocks with attributes, far from the origin), within the mouse budget (30 ms a move)."""
    from PySide6.QtCore import QPointF, QPoint
    path = BC.ace_like_dxf(os.path.join(out, "ace_like_speed.dxf"), devices=1200, seed=9)
    win, v0 = window()
    t = time.perf_counter()
    win.open_path(path)
    APP.processEvents()
    v = win.view()
    v.zoom("extents")
    v.repaint()
    opened = time.perf_counter() - t
    s = v.sheet()
    rnd = random.Random(3)
    pts = [QPointF(rnd.uniform(0, v.width()), rnd.uniform(0, v.height())) for _i in range(150)]
    t = time.perf_counter()
    for q in pts:
        v.pick_entity(v.to_world(q))
    hover = (time.perf_counter() - t) / len(pts)
    modes = {"end", "mid", "center", "quad", "insert", "node", "int", "near"}
    t = time.perf_counter()
    for q in pts:
        v.object_snap(v.to_world(q), modes)
    snap = (time.perf_counter() - t) / len(pts)
    cx, cy, n = v.width() / 2, v.height() / 2, 80
    path_px = [QPoint(int(cx + 0.45 * v.width() * math.cos(2 * math.pi * 0.97 * i / n)),
                      int(cy + 0.45 * v.height() * math.sin(2 * math.pi * 0.97 * i / n)))
               for i in range(n + 1)]
    Qt = _qt()[0]
    _press(v, path_px[0])
    t = time.perf_counter()
    for q in path_px[1:]:
        _move(v, q, Qt.LeftButton)
        v.repaint()
    lasso = (time.perf_counter() - t) / n
    t = time.perf_counter()
    _release(v, path_px[-1])
    pick = time.perf_counter() - t
    caught = len(v.sel)
    v.set_selection(set())
    # pan and wheel steps (the owner: "the gui doesn't seem to move and zoom in/out as
    # smoothly as autocad"): each shown at 60 a second
    v.zoom("extents")
    v.repaint()
    t = time.perf_counter()
    for i in range(40):
        if i % 2:
            v.zoom_at(1.2 if i % 4 == 1 else 1 / 1.2, QPointF(v.width() / 2, v.height() / 2))
        else:
            v.center = (v.center[0] + 6.0 / v.scale, v.center[1])
            v._moving()
        v.repaint()
    step = (time.perf_counter() - t) / 40
    v._moving_until = 0.0
    v.zoom("extents")
    v.repaint()
    t = time.perf_counter()
    a, b = QPoint(3, 3), QPoint(v.width() - 3, v.height() - 3)
    if v.pick_entity(v.to_world(QPointF(a))) is None:
        _drag_path(v, a, b, steps=20)
    window_all = time.perf_counter() - t
    whole = len(v.sel)
    res = [("open and draw", opened, 8.0), ("hover", hover, 0.03), ("snap move", snap, 0.03),
           ("lasso move", lasso, 0.03), ("lasso pick", pick, 1.0),
           ("window around it", window_all, 2.0), ("pan or zoom step", step, 0.016)]
    win.view().project.saved_at = len(win.view().project.undo_stack)
    win.close()
    assert caught > 50, "the lasso caught %d objects" % caught
    slow = [r for r in res if r[1] > r[2]]
    text = "%d objects: " % len(s.entities) + "; ".join(
        "%s %.1f ms" % (nm, d * 1000) if d < 1 else "%s %.2f s" % (nm, d) for nm, d, _b in res) \
        + "; lasso caught %d, window %d" % (caught, whole)
    assert not slow, "over budget: " + "; ".join("%s %.3f s (budget %.3f)" % r for r in slow)
    return text


def main(argv):
    out = argv[1] if len(argv) > 1 and not argv[1].startswith("--") else \
        tempfile.mkdtemp(prefix="kanzonascad-battery-")
    ops = int(argv[argv.index("--ops") + 1]) if "--ops" in argv else 3000
    seed = int(argv[argv.index("--seed") + 1]) if "--seed" in argv else 1
    # --drawing PATH: random editing and the drawing checks start from that drawing (your own:
    # they stay on your computer)
    drawing = argv[argv.index("--drawing") + 1] if "--drawing" in argv else None
    os.makedirs(out, exist_ok=True)
    log = Log(os.path.join(out, "battery.log"))
    _watch_paints()
    # (any dialog closes by itself for the whole run: one opened late, by an answer to a
    # command of an earlier section, Check for updates say, would otherwise wait forever)
    global CLOSER
    CLOSER = DialogCloser()
    import kanzonascad
    log.say("KanzonasCAD %s battery, Python %s, %s, seed %d" % (
        kanzonascad.__version__, sys.version.split()[0], sys.platform, seed))
    log.check("random editing", lambda: random_editing(log, out, ops, seed, drawing))
    log.check("every menu command", lambda: every_command(log, out))
    log.check("files", lambda: files(log, out))
    log.check("speed at scale", lambda: speed(log, out))
    log.check("a drawing as AutoCAD Electrical writes it",
              lambda: real_drawing(log, out))
    if drawing:
        log.check("your drawing (%s)" % os.path.basename(drawing),
                  lambda: real_drawing(log, out, drawing))
    log.check("Fit on many drawings", lambda: fit_many(log, out))
    log.check("Windows paths", lambda: windows_paths(log, out))
    log.check("speed on an imported drawing", lambda: speed_imported(log, out))
    log.check("pictures", lambda: pictures(log, out))
    CLOSER.stop()
    log.say("%d failure(s); output in %s" % (log.failures, out))
    return 1 if log.failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
