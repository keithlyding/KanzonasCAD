"""The self-test (python -m kanzonascad --selftest LOG): runs inside the built app (the
Windows exe, the Linux build) and fails the build when something the user relies on broke.
Each check writes PASS/FAIL to the log; the exit code is the number of failures (0 = all
passed)."""

import os
import re
import sys
import tempfile
import time
import traceback

from . import __version__

BUDGET = {
    "start": 5.0,               # the main window shown, seconds
    "big_open": 5.0,            # 60,000 lines read and drawn
    "big_zoom": 2.0,            # ten zoomed repaints of that sheet
    "edit_add": 2.0,            # 1,000 lines added one edit each, on that sheet
    "edit_move": 2.0,           # 1,000 lines moved in one edit, then drawn
    "hover": 0.01,              # one mouse move over the dense sheet (per move)
    "peak_mb": 800,
}


def _menu_commands(win):
    out = []

    def walk(menu):
        for a in menu.actions():
            if a.isSeparator():
                continue
            if a.menu() is not None:
                out.append(a.text())
                walk(a.menu())
            else:
                out.append(a.text())
    for a in win.menuBar().actions():
        if a.menu() is not None:
            walk(a.menu())
    return out


def manual_gaps(win):
    """Menu commands the user manual doesn't name (as the menu shows them, without & and ...)."""
    from . import manual
    text = re.sub(r"\s+", " ", manual.plain_text())
    gaps = []
    for t in _menu_commands(win):
        name = t.replace("&", "").replace("...", "").strip()
        if not name or name == "(none)":
            continue
        if name not in text:
            gaps.append(name)
    return gaps


def _peak_mb():
    try:
        if sys.platform.startswith("win"):
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]
            pmc = PMC()
            pmc.cb = ctypes.sizeof(PMC)
            h = ctypes.windll.kernel32.GetCurrentProcess()
            ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb)
            return pmc.PeakWorkingSetSize / 2 ** 20
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except Exception:
        return 0.0


class _Log:
    def __init__(self, path):
        self.path = path
        self.lines = []
        self.failures = 0

    def write(self, s):
        self.lines.append(s)
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.lines) + "\n")

    def check(self, name, fn):
        t = time.perf_counter()
        try:
            detail = fn()
            self.write("PASS  %s (%.2f s)%s" % (name, time.perf_counter() - t,
                                                ("  " + detail) if detail else ""))
        except Exception:
            self.failures += 1
            self.write("FAIL  %s\n%s" % (name, traceback.format_exc()))


def run(log_path):
    from PySide6.QtWidgets import QApplication
    from . import model as M
    from . import commands as C
    from . import fileio
    log = _Log(log_path)
    log.write("KanzonasCAD %s self-test, Python %s, %s" % (__version__, sys.version.split()[0],
                                                          sys.platform))
    app = QApplication.instance()
    tmp = tempfile.mkdtemp(prefix="kzcad-selftest-")
    state = {}

    def start():
        t = time.perf_counter()
        from .main_window import MainWindow
        w = MainWindow()
        d = w.new_project()
        w.show()
        app.processEvents()
        state["win"], state["view"] = w, d.view
        dt = time.perf_counter() - t
        assert dt < BUDGET["start"], "start-up took %.2f s" % dt
        heavy = [m for m in ("ezdxf", "openpyxl") if m in sys.modules]
        assert not heavy, "start-up imported %s (import them where they're used)" % heavy
        return "%.2f s" % dt
    log.check("start-up", start)

    def drawing():
        v = state["view"]
        v.snap_on = v.osnap_on = False
        v.run(C.LineCmd)
        for t in ("1,1", "@2,0", "@0,1", ""):
            assert v.input_text(t)
        v.run(C.CircleCmd)
        assert v.input_text("5,5") and v.input_text("0.5")
        v.run(C.TextCmd)
        for t in ("2,8", "0.2", "0", "CR1", ""):
            assert v.input_text(t)
        kinds = sorted(e.kind for e in v.sheet().entities.values())
        assert kinds == ["circle", "line", "line", "text"], kinds
        ids = set(v.sheet().entities)
        v.set_selection(ids)
        v.run(C.MoveCmd)
        assert v.input_text("0,0") and v.input_text("@1,1")
        v.project.undo()
        v.project.redo()
        line = [e for e in v.sheet().entities.values() if e.kind == "line"][0]
        assert line.p1 == (2.0, 2.0), line.p1
        v.repaint()
    log.check("drawing commands, undo and redo", drawing)

    def files():
        v = state["view"]
        p = v.project
        path = os.path.join(tmp, "test.kzcad")
        p.save(path)
        q = M.Project.load(path)
        assert q.to_dict() == p.to_dict()
        dxf = os.path.join(tmp, "test.dxf")
        fileio.export_dxf(p, p.sheets[0], dxf)
        ents, rep = fileio.read_dxf(dxf)
        assert len(ents) > len(p.sheets[0].entities), "frame missing from the DXF"
        pdf = os.path.join(tmp, "test.pdf")
        assert fileio.export_pdf(p, pdf) == 1
        assert open(pdf, "rb").read(4) == b"%PDF"
        return "project, DXF out and in, PDF"
    log.check("save, open, DXF and PDF", files)

    def manual():
        gaps = manual_gaps(state["win"])
        assert not gaps, "missing from the manual: %s" % gaps
    log.check("user manual covers every command", manual)

    def big_sheet():
        import random
        w = state["win"]
        rnd = random.Random(7)
        p = M.Project.new()
        s = p.sheets[0]
        t = time.perf_counter()
        for i in range(60000):
            x, y = rnd.uniform(0.7, 16.3), rnd.uniform(0.7, 10.3)
            s._put(M.Line((x, y), (x + rnd.uniform(-0.2, 0.2), y + rnd.uniform(-0.2, 0.2))))
        d = w.add_document(p)
        v = d.view
        v.zoom("sheet")
        v.repaint()
        app.processEvents()
        dt = time.perf_counter() - t
        assert dt < BUDGET["big_open"], "60,000 lines read and drawn in %.2f s" % dt
        t = time.perf_counter()
        for k in range(10):
            v.zoom_at(1.25, None)
            v.repaint()
        dz = time.perf_counter() - t
        assert dz < BUDGET["big_zoom"], "ten zoomed repaints took %.2f s" % dz
        v.zoom("sheet")
        t = time.perf_counter()
        made = []
        for i in range(1000):
            with p.edit("Line") as ed:
                made.append(ed.add(s, M.Line((1, 1 + i * 0.001), (2, 1 + i * 0.001))).id)
        v.repaint()
        da = time.perf_counter() - t
        assert da < BUDGET["edit_add"], "1,000 lines added in %.2f s" % da
        t = time.perf_counter()
        with p.edit("Move") as ed:
            for i in made:
                ed.change(s, s.entities[i].moved(0.5, 0.5))
        v.repaint()
        dm = time.perf_counter() - t
        assert dm < BUDGET["edit_move"], "1,000 lines moved in %.2f s" % dm
        from PySide6.QtCore import QPointF, QEvent, Qt
        from PySide6.QtGui import QMouseEvent
        t = time.perf_counter()
        n = 50
        for i in range(n):
            pos = QPointF(200 + i * 7, 300 + i * 3)
            app.sendEvent(v, QMouseEvent(QEvent.MouseMove, pos, v.mapToGlobal(pos),
                                         Qt.NoButton, Qt.NoButton, Qt.NoModifier))
        dh = (time.perf_counter() - t) / n
        assert dh < BUDGET["hover"] * 3, "a mouse move took %.1f ms" % (dh * 1000)
        p.saved_at = len(p.undo_stack)
        w.close_tab(w.tabs.indexOf(d))
        mb = _peak_mb()
        assert mb < BUDGET["peak_mb"], "peak memory %.0f MB" % mb
        return ("open+draw %.2f s, 10 zooms %.2f s, 1,000 adds %.2f s, 1,000 moved %.2f s, "
                "hover %.1f ms, peak %.0f MB" % (dt, dz, da, dm, dh * 1000, mb))
    log.check("speed budget (60,000-line sheet)", big_sheet)

    w = state.get("win")
    if w is not None:
        for i in range(w.tabs.count()):
            d = w.tabs.widget(i)
            d.project.saved_at = len(d.project.undo_stack)
        w.close()
    log.write("%d failure(s)" % log.failures)
    return log.failures
