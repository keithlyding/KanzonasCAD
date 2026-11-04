"""An exhaustive battery of tests, run by hand before a release (too long for every build):

    QT_QPA_PLATFORM=offscreen python tests/battery.py [OUT_FOLDER] [--ops N] [--seed S]

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
from kanzonascad import wires, crossings, wirenums, fileio, templates  # noqa: E402


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


def norm(d):
    """A project's dict, for comparing two states: each sheet's entities in id order (undo
    puts a restored entity back at the end of the sheet's list: the same drawing)."""
    d = json.loads(json.dumps(d, sort_keys=True))
    for s in d.get("sheets", []) + ([d["title_block"]] if isinstance(d.get("title_block"),
                                                                   dict) else []):
        if isinstance(s.get("entities"), list):
            s["entities"].sort(key=lambda e: e.get("id", 0))
    return d


# ---- 1. random editing -------------------------------------------------------------------------
def random_editing(log, out, ops, seed):
    rnd = random.Random(seed)
    win, v = window()
    v.osnap_on = v.snap_on = v.polar_on = v.ortho_on = False
    p = v.project
    s = v.sheet()
    lib = win.library
    syms = ["Contact NO", "Contact NC", "Relay coil", "Pushbutton NO", "Pushbutton NC",
            "Pilot light", "Fuse", "Circuit breaker 1-pole", "Terminal", "Overload contact NC"]
    syms = [n for n in syms if lib.get("symbol", n) is not None]
    start = norm(p.to_dict())
    counts = {}
    errors = []

    def pt():
        # on a 1/4" grid, mostly on a few rungs so things meet
        if rnd.random() < 0.6:
            return (rnd.randint(4, 60) * 0.25, rnd.choice([2, 3, 4, 5, 6, 7, 8]) * 1.0)
        return (rnd.randint(4, 60) * 0.25, rnd.randint(4, 40) * 0.25)

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
             (op_undo, 6), (op_redo, 4)]
    fns = [f for f, w in table for _i in range(w)]
    roundtrips = 0
    path = os.path.join(out, "random.kzcad")
    for i in range(ops):
        fn = rnd.choice(fns)
        name = fn.__name__[3:]
        counts[name] = counts.get(name, 0) + 1
        try:
            fn()
            v.set_selection(set())
            check_sheet(s)
            if i % 50 == 49:
                v.repaint()
                APP.processEvents()
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
            "round trips; %d undone" % (ops, ", ".join("%s %d" % kv for kv in sorted(
                counts.items())), len(s.entities), len(s.wires()), len(s.inserts()),
                roundtrips, n_undo)
    win.close()
    if errors:
        raise AssertionError("%d step(s) failed (seed %d):\n%s" % (len(errors), seed,
                                                                 "\n".join(errors)))
    assert back["sheets"] == start["sheets"], "undo all the way didn't give the empty sheet"
    assert again == final, "redo all the way didn't give the final project"
    return stats


# ---- 2. every menu command ---------------------------------------------------------------------
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
    closer = DialogCloser()
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
        win.close()
    finally:
        closer.stop()
        sys.excepthook = hook
    if errors:
        raise AssertionError("%d command(s) raised:\n%s" % (len(errors), "\n".join(errors)))
    return "%d menu commands triggered over 3 phases; %d dialogs opened and closed" % (
        done, len(closer.closed))


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
    v.show_sheet(p.sheets[0].id)
    return p


def files(log, out):
    win, v = window()
    p = mixed_project(win)
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
    import fitz
    pdf = os.path.join(out, "mixed.pdf")
    d = fitz.open(pdf)
    names = []
    for i, page in enumerate(d):
        png = os.path.join(out, "page-%d.png" % (i + 1))
        page.get_pixmap(dpi=80).save(png)
        names.append(os.path.basename(png))
    return ", ".join(names)


def main(argv):
    out = argv[1] if len(argv) > 1 and not argv[1].startswith("--") else \
        tempfile.mkdtemp(prefix="kanzonascad-battery-")
    ops = int(argv[argv.index("--ops") + 1]) if "--ops" in argv else 3000
    seed = int(argv[argv.index("--seed") + 1]) if "--seed" in argv else 1
    os.makedirs(out, exist_ok=True)
    log = Log(os.path.join(out, "battery.log"))
    import kanzonascad
    log.say("KanzonasCAD %s battery, Python %s, %s, seed %d" % (
        kanzonascad.__version__, sys.version.split()[0], sys.platform, seed))
    log.check("random editing", lambda: random_editing(log, out, ops, seed))
    log.check("every menu command", lambda: every_command(log, out))
    log.check("files", lambda: files(log, out))
    log.check("speed at scale", lambda: speed(log, out))
    log.check("pictures", lambda: pictures(log, out))
    log.say("%d failure(s); output in %s" % (log.failures, out))
    return 1 if log.failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
