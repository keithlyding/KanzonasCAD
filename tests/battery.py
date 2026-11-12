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
import sys
import tempfile
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tests  # noqa: E402,F401  (settings, library and recovery in scratch folders)
from tests.util import APP, window, type_in  # noqa: E402

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QFileDialog  # noqa: E402

from kanzonascad import commands as C  # noqa: E402
from kanzonascad import model as M  # noqa: E402
from kanzonascad import geometry as G  # noqa: E402
from kanzonascad import wires, crossings, wirenums, fileio, templates  # noqa: E402
from tests import battery_checks as BC  # noqa: E402


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
        try:
            note = fn()
        except Exception:                       # (a battery reports every failure, then goes on)
            self.failures += 1
            self.say("FAIL  %s (%.1f s)\n%s" % (name, time.perf_counter() - t,
                                                traceback.format_exc()))
            return
        self.say("PASS  %s (%.1f s)%s" % (name, time.perf_counter() - t,
                                         "  " + note if note else ""))


# ---- invariants ------------------------------------------------------------------------------
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


def _partition(groups):
    by = {}
    for i, r in groups.items():
        by.setdefault(r, set()).add(i)
    return sorted(sorted(g) for g in by.values())


def check_groups(sheet):
    """The wire groups kept up to date edit by edit are the ones worked out from scratch."""
    kept = _partition(wirenums._sheet_groups(sheet))
    saved = sheet._wire_groups, sheet._wire_adj
    sheet._wire_groups = sheet._wire_adj = None
    fresh = _partition(wirenums._sheet_groups(sheet))
    sheet._wire_groups, sheet._wire_adj = saved
    assert kept == fresh, "wire groups kept up to date differ from a fresh count"
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


def _send(v, kind, pos, button, buttons):
    """A mouse event as the system sends one (with the buttons held: QTest's moves don't
    always say)."""
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QMouseEvent
    kinds = {"press": QEvent.MouseButtonPress, "move": QEvent.MouseMove,
             "release": QEvent.MouseButtonRelease}
    pos = QPointF(pos)
    APP.sendEvent(v, QMouseEvent(kinds[kind], pos, v.mapToGlobal(pos), button, buttons,
                                 _qt()[0].NoModifier))


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
    """Selected objects dragged by one of them move exactly as far as the mouse did."""
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
    w0, w1 = v.to_world(QPointF(start)), v.to_world(QPointF(end))
    d = (w1[0] - w0[0], w1[1] - w0[1])
    _drag_path(v, start, end, steps=10)
    tol = 1e-6 * max(1.0, max(abs(c) for b in before.values() for c in b))
    for i, b in before.items():
        e = s.entities.get(i)
        assert e is not None, "a dragged object is gone"
        nb = e.bbox()
        assert all(abs(nb[k] - b[k] - d[k % 2]) <= tol + 1e-9 for k in range(4)), \
            "dragged %s by %s, it moved %s" % (e.kind, d, (nb[0] - b[0], nb[1] - b[1]))
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
            "Pilot light", "Fuse", "Circuit breaker 1-pole", "Terminal", "Overload contact NC"]
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
        return "%g,%g" % q

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

    def op_bus():
        v.run(C.BusCmd)
        for t in (str(rnd.randint(2, 4)), "0.5"):
            if v.cmd is not None:
                v.input_text(t)
        a = pt()
        b = (a[0] + rnd.choice([-3, 3]), a[1])
        for q in (a, b):
            if v.cmd is not None:
                v.input_text(fmt(q))
        finish()

    def op_symbol():
        name = rnd.choice(syms)
        v.run(C.InsertCmd, lib.get("symbol", name), {})
        if v.cmd is not None:
            v.input_text(fmt(pt()))
        finish()

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

    def op_trim_plain():
        ents = list(s.entities.values())
        if not ents:
            return
        e = rnd.choice(ents)
        x0, y0, x1, y1 = e.bbox()
        v.run(C.TrimCmd)
        v.cmd.pick(((x0 + x1) / 2, (y0 + y1) / 2))
        finish()

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
        v.run(C.ScootCmd)
        if v.cmd is not None:
            type_in(v, fmt(e.pos))
            if v.cmd is not None:
                v.input_text(fmt((e.pos[0] + rnd.choice([-1, 1]) * 0.5, e.pos[1])))
        finish()

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
        for q in (a, (a[0] + 2, a[1]), (a[0] + 1, a[1] - 0.5)):
            if v.cmd is not None:
                v.input_text(fmt(q))
        finish()

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
            type_in(v, fmt(a), fmt(b))
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

    fps = sorted(n for n, d in lib.blocks("footprint")[0].items() if d.builtin)

    def op_footprint():
        # a built-in generic footprint, placed as Insert footprint does
        v.run(C.InsertCmd, lib.get("footprint", rnd.choice(fps)), {})
        if v.cmd is not None:
            v.input_text(fmt(pt()))
        finish()

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

    def op_fit():
        # Fit (the status bar's Scale list: the biggest standard scale the drawing fits at,
        # moved to the middle if need be), or a scale picked from that list
        from kanzonascad import scalefit
        if rnd.random() < 0.3:
            name, val = rnd.choice(scalefit.presets_like(s.scale_name))
            win._set_scale(name, val)
        elif scalefit.fit_for(p, s) is not None:        # (else it opens the Sheet scale window)
            win.fit_scale()
            BC.fit_oracle(p, s)

    # ---- sheets of every size, turn and scale, several of them -------------------------------
    def op_world():
        world["o"] = rnd.choice([(0.0, 0.0), (0.0, 0.0), (480.0, -250.0),
                                 (-2400.0, 1700.0), (12000.0, 8000.0)])
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
        if len(p.sheets) < 6:
            win.add_sheet()

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

    def op_lasso():
        mouse_lasso(v, crnd)

    def op_drag():
        mouse_drag(v, crnd)

    def op_pan():
        mouse_pan(v, crnd)

    def op_undo():
        for _i in range(rnd.randint(1, 4)):
            p.undo()

    def op_redo():
        for _i in range(rnd.randint(1, 4)):
            p.redo()

    table = [(op_wire, 18), (op_bus, 3), (op_symbol, 14), (op_line, 4), (op_text, 3),
             (op_move, 6), (op_copy, 4), (op_rotate, 3), (op_erase, 4), (op_trim, 6),
             (op_trim_plain, 2), (op_delwire, 3), (op_delcomp, 4), (op_clean, 2),
             (op_scoot, 4), (op_align, 2), (op_crossing, 2), (op_rail, 2), (op_dim, 2),
             (op_leader, 3), (op_mtext, 2), (op_hatch, 3), (op_import, 1), (op_explode, 1),
             (op_usetb, 1), (op_footprint, 2), (op_location, 4), (op_cable, 2), (op_attr_vis, 2),
             (op_fit, 2), (op_run_props, 2), (op_world, 1), (op_sheet, 1), (op_new_sheet, 1),
             (op_switch_sheet, 2), (op_big, 1), (op_snap, 3), (op_zoom, 1),
             (op_mouse_window, 3), (op_lasso, 2), (op_drag, 2), (op_pan, 1), (op_undo, 6),
             (op_redo, 4)]
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
            BC.check_index(s, crnd)
            if i % 25 == 24:
                for other in p.sheets:
                    check_sheet(other)
            if i % 50 == 49:
                v.repaint()
                APP.processEvents()
            if i % 25 == 24:
                kinds.update(type(e).__name__ for e in s.entities.values())
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
    with p.edit("notes") as ed:
        s = p.sheets[0]
        ed.add(s, M.Leader([(14, 9), (15, 10), (16, 10)], "SEE NOTE 1"))
        ed.add(s, M.Leader([(12, 9), (13, 10.5)], "1", balloon=True))
        ed.add(s, M.MText((1, 11), "NOTES:\nLINE TWO OF THE NOTE", 0.125, 0.0, "TL", 3.0))
        ed.add(s, M.Polyline([(17, 1), (19, 1), (19, 2), (17, 2)], True))
        ed.add(s, M.Hatch([[(17, 1), (19, 1), (19, 2), (17, 2)]], "ANSI31", 45.0, 0.125))
        ed.add(s, M.Hatch([[(17, 3), (18, 3), (18, 4), (17, 4)]], "SOLID", 0.0, 0.125))
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
    v.show_sheet(p.sheets[0].id)
    return p


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
    notes.append("DXF out and in (%d sheets)" % len(p.sheets))
    pdf = os.path.join(out, "mixed.pdf")
    n = fileio.export_pdf(p, pdf)
    assert n == len(p.sheets) and open(pdf, "rb").read(4) == b"%PDF"
    notes.append("PDF (%d pages)" % n)
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
    t = time.perf_counter()
    a, b = QPoint(3, 3), QPoint(v.width() - 3, v.height() - 3)
    if v.pick_entity(v.to_world(QPointF(a))) is None:
        _drag_path(v, a, b, steps=20)
    window_all = time.perf_counter() - t
    whole = len(v.sel)
    res = [("open and draw", opened, 8.0), ("hover", hover, 0.03), ("snap move", snap, 0.03),
           ("lasso move", lasso, 0.03), ("lasso pick", pick, 1.0),
           ("window around it", window_all, 2.0)]
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
