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
    "snap_move": 0.03,          # one mouse move in a command, snaps on, and the screen drawn
    "view_step": 0.016,         # a pan or wheel zoom step shown (60 a second): the last picture
                                # moved and scaled, no object drawn again until it stops
    "peak_mb": 800,
    "big_print": 5.0,           # that sheet printed, fit to letter paper (into a PDF file)
    "big_window": 2.0,          # that sheet opened in a new window and drawn, then closed
    "wire_edit": 0.15,          # one wire added to a 12,030-wire sheet: numbers, dots, crossings,
                                # near misses (nearmiss.py: only round what the edit changed)
    "near_scan": 1.0,           # near misses on that sheet worked out whole (opened)
    # a sheet of notes: 2,000 hatches (and their outlines), 1,000 leaders, 1,000 multi-line
    # notes, 1,000 pictures and 2,000 texts (text drawn as filled outlines took seconds a zoom
    # step here)
    "notes_open": 2.0,          # added and drawn
    "notes_zoom": 2.0,          # ten zoomed repaints
    "notes_move": 1.0,          # 1,000 of them moved in one edit, then drawn
    "notes_undo": 1.0,          # that undone, then drawn
    "import_blocks": 4.0,       # a DXF of 1,000 block references (attributes), 200 dimensions
                                # and 500 hatches imported
    "bom": 0.5,                 # the bill of materials of 2,000 parts
    # (0.24) Library > Import blocks from folder...: 200 small block files (DXF) read, listed
    # in its window (with their pictures) and put in the library
    "block_folder": 10.0,
    "block_folder_step": 0.1,   # the longest step between two turns of the event loop
    "pdf_in": 4.0,              # a PDF page of 6,000 lines and 2,000 texts read (Import PDF)
    "lasso_move": 0.03,         # a mouse move dragging a lasso around half that sheet (average)
    "lasso_pick": 1.0,          # what the lasso caught, worked out when the button is let go
    # (0.22: ladders, as a new kind of object must be measured) a sheet of 100 ladders of 40
    # rungs (4,000 rung numbers):
    "ladders_open": 2.0,        # added, numbered and drawn
    "ladders_zoom": 2.0,        # ten zoomed repaints
    "ladders_move": 1.0,        # all moved in one edit (renumbered), then drawn
    "ladders_undo": 1.0,        # that undone, then drawn
    "ladder_refs": 0.5,         # 2,000 places read by rung (cross-references, reports)
    # (0.26: dashed polygons, as a new kind of object must be measured; and Join) a sheet of
    # 2,000 dashed polygons of six corners, with notes:
    "dpoly_open": 2.0,          # added and drawn
    "dpoly_zoom": 2.0,          # ten zoomed repaints
    "dpoly_move": 1.0,          # all moved in one edit, then drawn
    "dpoly_undo": 1.0,          # that undone, then drawn
    "join": 1.0,                # 4,000 lines in 1,000 chains (and 1,000 gaps) joined, then drawn
    "join_undo": 1.0,           # that undone, then drawn
    "pull": 1.0,                # cables between locations: 2,000 wires from terminals to
                                # 2,000 devices, half of them in the field
    # (0.27: terminal strips) 50 sheets, a strip of 100 terminals each (5,000 terminals, a
    # device wired to each side, 10,000 wires, half the far ends in the field):
    "strips_open": 0.5,         # Terminal strips... opened: every strip listed, the first shown
    "strips_plan": 1.0,         # the terminal plan of every terminal worked out (its wire
                                # groups read afresh: 0.3 s here, 0.5 s on the build's Linux
                                # computer; as "pull", for five times as many wires; the
                                # owner's choice, Nov 2026)
    "strips_apply": 0.5,        # a strip renumbered backwards and written back (OK), one step
    # (0.28: panel wiring) 20 schematic sheets of 50 contactor coils and 50 breakers (2,000
    # devices, 10,000 wires), each device's footprint on one of 4 panel sheets showing their
    # terminal wire labels (4,000 labeled terminals, a third of the contactors turned):
    "wiring_list": 1.0,         # the device wiring list worked out (4,000 rows)
    "wiring_open": 1.0,         # a panel sheet's labels worked out and the sheet drawn
    "wiring_zoom": 2.0,         # ten zoomed repaints of it
    "wiring_edit": 0.5,         # a device retagged on a schematic sheet, the labels following
    # (0.23: Trace, Ctrl+E) on 50 sheets of 1,000 lines, 40 coils, 40 contacts and 40 wires:
    "trace_index": 2.0,         # the first list, every sheet indexed (50 sheets)
    "trace_click": 0.005,       # a click (selection change) with the panel open: the lookup
                                # never runs in it, only starts a timer
    "trace_step": 0.03,         # one turn of Trace's work on the event loop, at the most
    "trace_list": 0.5,          # a pick fully listed (typical)
    # (0.25: the Properties panel, Ctrl+1) on a sheet of 20,000 objects (lines, texts,
    # symbols, wires), the panel open:
    "props_click": 0.005,       # a click (selection change): the panel only starts a timer
    "props_fill": 0.2,          # the panel filled with one object (typical)
    "props_all": 2.0,           # ...with all 20,000 selected (Select all)
    "props_repaint": 0.01,      # a repaint with it open: no slower than closed, give or take
    # (0.25: Devices without a footprint) 50 sheets, 2,000 devices, 1,000 footprints:
    "missing_fp": 0.5,          # the check worked out after a change
    "gc_pause": 0.05,           # (0.26) one full collection by Python's collector, at the most,
                                # while working on an opened 60,000-line project (gcpolicy)
    "pdf_links": 2.0,           # (0.23.1) the links of 2,000 cross-references added to the PDF
                                # of 20 sheets (Export to PDF)
    # (0.29: saved circuits, as a new kind of thing must be measured) a circuit of 100 rungs (a
    # coil, two contacts, four wires each: 700 objects) on a sheet of 2,100 devices:
    "circuit_save": 0.5,        # made from the selection and written to the library
    "circuit_place": 1.5,       # placed (retagged, relinked, numbered, wires cut), then drawn
    "circuit_move": 0.03,       # a mouse move while it follows the mouse (the preview slid)
    "circuit_undo": 1.0,        # the placing undone, then drawn
    "circuit_browse": 2.0,      # Insert circuit's window listing 100 circuits, pictures drawn
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
            k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
            k32.GetCurrentProcess.restype = wintypes.HANDLE      # (64-bit handles intact)
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                                   wintypes.DWORD]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            h = k32.GetCurrentProcess()
            if not psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
                raise OSError("GetProcessMemoryInfo failed")
            mb = pmc.PeakWorkingSetSize / 2 ** 20
        else:
            import resource
            mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except (OSError, AttributeError, ImportError, ValueError) as ex:
        # (up to 0.15.11 any failure here gave 0 MB, and the memory budget passed unmeasured:
        # a check that can't measure must say so)
        raise AssertionError("peak memory couldn't be measured: %s" % ex)
    if mb <= 0:
        raise AssertionError("peak memory measured as %.1f MB" % mb)
    return mb


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
    # a scratch library: the self-test never touches the user's own
    os.environ["KANZONASCAD_LIBRARY"] = os.path.join(tmp, "library")
    os.environ["KANZONASCAD_RECOVERY"] = os.path.join(tmp, "recovery")
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
        heavy = [m for m in ("ezdxf", "ezdwg", "openpyxl", "pdfminer") if m in sys.modules]
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
        for t in ("H", "0.2", "2,8", "CR1", ""):
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

    def dwg():
        import tempfile
        import ezdwg
        from . import fileio
        folder = tempfile.mkdtemp(prefix="kzcad-selftest")
        path = os.path.join(folder, "test.dwg")
        d = ezdwg.new()
        m = d.modelspace()
        m.add_line((1, 1), (5, 1))
        m.add_circle((3, 3), 0.5)
        m.add_text("DWG", (1, 5), 0.25)
        d.save(path)
        ents, rep = fileio.read_dwg(path)
        kinds = sorted(e.kind for e in ents)
        assert kinds == ["circle", "line", "text"], kinds
        line = [e for e in ents if e.kind == "line"][0]
        assert abs(line.length() - 4.0) < 1e-6, line.length()      # units kept (not meters)
        return "read with %s: %s" % (rep["reader"], ", ".join(kinds))
    log.check("DWG import", dwg)

    def pdf_in():
        # (a page of a CAD program's PDF: lines, a circle and real text, read back where they
        # were; and a big page, in time. Inside the built program, this is what proves
        # pdfminer and its data came along)
        import random
        from . import pdf_import
        from .pdf_samples import Page, write_pdf
        pg = Page(17 * 72, 11 * 72)
        pg.line((72, 72), (360, 72))
        pg.circle((432, 432), 18)
        pg.text((144, 288), "CR101", 9, angle=90)
        path = write_pdf(os.path.join(tmp, "in.pdf"), [pg])
        ents, rep = pdf_import.read_pdf(path)
        got = sorted((e.kind, e.text if e.kind == "text" else "") for e in ents)
        assert got == [("circle", ""), ("line", ""), ("text", "CR101")], got
        t = [e for e in ents if e.kind == "text"][0]
        assert t.pos == (2.0, 4.0) and t.angle == 90.0, (t.pos, t.angle)
        r = random.Random(7)
        big = Page(34 * 72, 22 * 72)
        for _i in range(6000):
            x, y = r.uniform(36, 2400), r.uniform(36, 1500)
            big.line((x, y), (x + 36, y))
        for i in range(2000):
            big.text((r.uniform(36, 2400), r.uniform(36, 1500)), "CR%d" % i, 8)
        write_pdf(os.path.join(tmp, "big.pdf"), [big])
        t0 = time.perf_counter()
        ents, rep = pdf_import.read_pdf(os.path.join(tmp, "big.pdf"))
        dt = time.perf_counter() - t0
        assert rep["lines"] == 6000, rep["lines"]
        assert dt < BUDGET["pdf_in"], "a page of 6,000 lines and 2,000 texts took %.2f s" % dt
        return "lines, circle and text back where they were; 8,000 objects read in %.2f s" % dt
    log.check("PDF import", pdf_in)

    def panel():
        from . import sheetframe
        p = M.Project.new()
        s = p.sheets[0]
        with p.edit("panel") as ed:
            ed.sheet_meta(s, kind="panel")
            ed.add(s, M.Line((1, 1), (37, 1)))
            ed.sheet_scale(s, 0.25)
            d = ed.add(s, M.Dimension((1, 1), (37, 1), (19, -1),
                                      height=p.settings["dim_height"] * s.k()))
        assert s.paper() == (68.0, 44.0) and s.paper_inches() == (17.0, 11.0), s.paper()
        assert d.label() == '36.00"', d.label()
        assert sheetframe.field_values(p, s)["Scale"] == "1:4"
        from . import materials
        with p.edit("rail and duct") as ed:
            ed.add(s, M.Rail((2, 2), (32, 2), "TS35x7.5", *M.RAIL_PROFILES["TS35x7.5"][1:]))
            ed.add(s, M.Duct((2, 5), (32, 5), "", 2, 3))
            ed.add(s, M.Duct((2, 8), (52, 8), "", 2, 3))
        got = {r["item"]: (r["total"], r["sticks"]) for r in materials.rows(p)}
        assert got == {"DIN rail": (30.0, 1), "Wire duct": (80.0, 2)}, got
        return "1:4 sheet, real-size drawing, %s dimension; rail and duct %s" % (
            d.label(), got)
    log.check("panel sheets and dimensions", panel)

    def library():
        from .library import Library
        lib = Library()
        syms, bad = lib.blocks("symbol")
        assert not bad, bad
        assert len(syms) >= 25, "only %d built-in symbols" % len(syms)
        v = state["view"]
        v.osnap_on = v.snap_on = False
        v.run(C.InsertCmd, syms["Relay coil"], {"TAG": "CR601"})
        assert v.input_text("5.75,6")       # (held by its first pin, A1: placed where it goes)
        ins = [e for e in v.sheet().entities.values() if isinstance(e, M.Insert)]
        assert ins and ins[0].pin_points()[0][1] == (5.75, 6.0), ins[0].pin_points()
        lib.save_block(M.BlockDef("Self-test footprint", "footprint", [M.Circle((0, 0), 1)]))
        assert Library().get("footprint", "Self-test footprint") is not None
        fps, bad = lib.blocks("footprint")
        assert not bad, bad
        generic = [b for b in fps.values() if b.builtin]
        assert len(generic) >= 30, "only %d built-in footprints" % len(generic)
        v.repaint()
        return "%d built-in symbols, %d built-in footprints; insert, pins and library folder" % (
            len(syms), len(generic))
    log.check("symbol library", library)

    def wiring():
        from .library import Library
        from . import wires
        v = state["view"]
        v.osnap_on = v.snap_on = False
        before = len(v.sheet().entities)
        v.run(C.WireCmd)
        for t in ("1,3", "8,3", ""):
            assert v.input_text(t)
        v.run(C.InsertCmd, Library().get("symbol", "Contact NO"), {})
        assert v.input_text("3.75,3")       # (its pin 1 on the wire)
        if v.cmd is not None:
            assert v.input_text("")     # (a coil is already on the sheet: it belongs to that)
        ws = [e for e in v.sheet().entities.values() if isinstance(e, M.Wire)]
        assert sorted(w.points[0][0] for w in ws) == [1.0, 4.25], [w.points for w in ws]
        ins = [e for e in v.sheet().entities.values() if isinstance(e, M.Insert)][-1]
        with v.project.edit("Move") as ed:
            ed.change(v.sheet(), ins.moved(0, 0.5))
        ws = [e for e in v.sheet().entities.values() if isinstance(e, M.Wire)]
        assert any(w.points[-1] == (3.75, 3.5) for w in ws), [w.points for w in ws]
        v.project.undo()
        assert wires.junctions(v.sheet()) == []
        v.repaint()
        return "wire, cut under a symbol, follows a moved symbol (%d objects)" % (
            len(v.sheet().entities) - before)
    log.check("wires", wiring)

    def tagging():
        from .library import Library
        from . import tags
        w = state["win"]
        v = state["view"]
        coil = Library().get("symbol", "Relay coil")
        before = {e.id for e in v.sheet().entities.values() if tags.is_device(e)}
        page = v.project.sheet_number(v.sheet())
        made = []
        for at in ("9,9", "9,8"):
            v.run(C.InsertCmd, coil, {})
            assert v.input_text(at)
            made.append([e for e in v.sheet().entities.values() if tags.is_device(e)
                         and e.id not in before and e.id not in made][0].id)
        got = [v.sheet().entities[i].attrs["TAG"] for i in made]
        assert all(t.startswith("CR" + page) for t in got) and len(set(got)) == 2, got
        w.renumber_sheet()
        return "devices tagged %s; renumbered" % ", ".join(got)
    log.check("device tags", tagging)

    def cross_references():
        from .library import Library
        from . import tags, xrefs
        v = state["view"]
        p, sheet = v.project, v.sheet()
        coil = Library().get("symbol", "Relay coil")
        v.run(C.InsertCmd, coil, {})
        assert v.input_text("12,9")
        c = max((e for e in sheet.entities.values() if tags.is_device(e)), key=lambda e: e.id)
        v.run(C.InsertCmd, Library().get("symbol", "Contact NC"), {})
        assert v.input_text("14,4")
        assert v.input_text(c.attrs["TAG"].lower())         # belongs to that coil
        k = max((e for e in sheet.entities.values() if tags.is_child(e)), key=lambda e: e.id)
        assert k.attrs.get("PARENT") == c.attrs["DEV"], k.attrs
        texts = [t[2] for t in xrefs.live(p, sheet)]
        # (numbered on its coil as placed, its first NC 21-22: pinnumbers.py, 0.28)
        want = ["NC 21-22 " + p.zone_text(sheet, 14, 4), p.zone_text(sheet, 12, 9)]
        assert all(t in texts for t in want), (texts, want)
        v.repaint()
        return "contact linked to %s; %s" % (c.attrs["TAG"], ", ".join(want))
    log.check("contacts and cross-references", cross_references)

    def wire_numbers():
        import time
        from . import wirenums
        p = M.Project.new()
        with p.edit("sheets") as ed:
            for i in range(39):
                ed.add_sheet(p.make_sheet("S%d" % i))
        with p.edit("wires") as ed:
            for sh in p.sheets:
                for r in range(150):
                    y = 1 + r * 0.05
                    ed.add(sh, M.Wire([(1, y), (8, y)]))
                    ed.add(sh, M.Wire([(9, y), (15, y)]))
        sh = p.sheets[5]
        got = sorted({w.num for w in sh.wires()})
        assert got[0] == "6001" and len(got) == 300, got[:3]
        t = time.perf_counter()
        for i in range(10):
            with p.edit("one") as ed:
                ed.add(sh, M.Wire([(1, 9.5 + i * 0.01), (3, 9.5 + i * 0.01)]))
        each = (time.perf_counter() - t) / 10
        assert each < 0.25, "a wire added to a 12,000-wire project took %.0f ms" % (each * 1000)
        assert wirenums.labels(p, sh)
        return "12,000 wires numbered; one more wire %.0f ms" % (each * 1000)
    log.check("wire numbers", wire_numbers)

    def wire_editing():
        import time
        from . import wires, crossings, nearmiss
        p = M.Project.new()
        s = p.sheets[0]
        with p.edit("rungs") as ed:
            ed.project_settings({"wire_crossing": "loop"})
            for i in range(400):            # 400 rungs of 30 pieces, 30 wires crossing them
                for j in range(30):
                    ed.add(s, M.Wire([(j * 1.0, i * 0.25), (j * 1.0 + 1.0, i * 0.25)]))
            for j in range(30):
                ed.add(s, M.Wire([(j + 0.375, -0.5), (j + 0.375, 100.5)]))
        wires.junctions(s)
        crossings.jumps(p, s)
        t = time.perf_counter()
        assert nearmiss.found(s) == []
        scan = time.perf_counter() - t
        t = time.perf_counter()
        for k in range(10):
            with p.edit("one") as ed:
                ed.add(s, M.Wire([(40 + k, 0), (40 + k, 1)]))
            wires.junctions(s)
            crossings.jumps(p, s)
            nearmiss.found(s)
        each = (time.perf_counter() - t) / 10
        # (a wire end stopped 0.005" short of a rung: marked, after the one edit)
        t = time.perf_counter()
        with p.edit("short") as ed:
            ed.add(s, M.Wire([(5.5, 0.255), (5.5, 0.6)]))
        got = nearmiss.found(s)
        near = time.perf_counter() - t
        assert [round(m[2], 6) for m in got] == [0.005], got
        assert scan < BUDGET["near_scan"], \
            "near misses on a 12,030-wire sheet worked out in %.2f s" % scan
        assert each < BUDGET["wire_edit"], \
            "a wire added to a 12,030-wire sheet (numbers, dots, crossings, near misses) " \
            "took %.0f ms" % (each * 1000)
        assert near < BUDGET["wire_edit"], "a near miss found after an edit in %.0f ms" % (
            near * 1000)
        return ("one wire on a 12,030-wire sheet, numbered, dots, crossings and near misses: "
                "%.0f ms; near misses on the whole sheet %.0f ms, one found after an edit "
                "%.0f ms" % (each * 1000, scan * 1000, near * 1000))
    log.check("wire editing speed (12,030-wire sheet)", wire_editing)

    def manual():
        gaps = manual_gaps(state["win"])
        assert not gaps, "missing from the manual: %s" % gaps
    log.check("user manual covers every command", manual)

    def storage():
        # where settings, the library and recovery copies go (portable: the data folder
        # beside the program, or the PortableApps.com package's Data folder)
        from . import paths, library, backup
        st = state["win"].settings
        st.setValue("selftest/last_run", "ok")
        st.sync()
        assert st.status() == st.Status.NoError, "settings can't be written: %s" % st.status()
        st.remove("selftest")           # (written and read back: nothing of it is kept)
        if not paths.is_portable():
            if sys.platform == "win32":
                return "(installed: registry + AppData)"
            return "(settings: %s)" % st.fileName()
        base = paths.portable_data_dir()
        ini = os.path.join(base, "settings.ini")
        assert os.path.normcase(os.path.abspath(st.fileName())) == \
            os.path.normcase(os.path.abspath(ini)), "portable settings in %s" % st.fileName()
        assert os.path.isfile(ini), "portable settings file missing"
        saved = {k: os.environ.pop(k, None) for k in ("KANZONASCAD_LIBRARY",
                                                      "KANZONASCAD_RECOVERY")}
        try:
            lib, rec = library.default_folder(), backup.recovery_folder()
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v
        for what, folder in (("library", lib), ("recovery", rec)):
            assert os.path.normcase(folder).startswith(os.path.normcase(base) + os.sep), \
                "portable %s folder outside the data folder: %s" % (what, folder)
        return "(portable: %s%s)" % (base, ", updated by its platform"
                                     if paths.platform_updates() else "")
    log.check("storage location", storage)

    def update_files():
        # the packaged app reaches GitHub over TLS; the portable zip's update keeps the data
        # folder; the AppImage helpers see an AppImage
        import zipfile
        from PySide6.QtNetwork import QSslSocket
        from . import updates
        assert QSslSocket.supportsSsl(), "no TLS support: update checks can't reach GitHub"
        app_dir = os.path.join(tmp, "app")
        os.makedirs(app_dir, exist_ok=True)
        good = os.path.join(tmp, "portable.zip")
        with zipfile.ZipFile(good, "w") as z:
            z.writestr("KanzonasCAD/KanzonasCAD.exe", "exe")
            z.writestr("KanzonasCAD/portable.txt", "portable")
            z.writestr("KanzonasCAD/_internal/a.dll", "dll")
            z.writestr("KanzonasCAD/data/settings.ini", "theirs")
        new = updates.unpack(good, app_dir)
        assert os.path.isfile(os.path.join(new, "_internal", "a.dll"))
        assert not os.path.exists(os.path.join(new, "data")), "update would replace settings"
        bat = updates.swap_script(4242, new, app_dir)
        assert "PID eq 4242" in bat and os.path.join(new, "data") in bat
        fake = os.path.join(tmp, "fake.AppImage")
        with open(fake, "wb") as f:
            f.write(b"\x7fELF\x02\x01\x01\x00AI\x02" + b"\x00" * 64)
        assert updates.is_appimage_file(fake) and not updates.is_appimage_file(good)
        return "(TLS: %s; this copy updates by: %s)" % (QSslSocket.activeBackend(),
                                                         updates.how())
    log.check("updates (portable zip, AppImage)", update_files)

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
            v._moving_until = 0.0       # (each drawn sharp: not the moved picture of a step)
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
        # in a command, with the running snaps on, the screen drawn after each move (the
        # crosshair, snap marker and rubber band over the picture the view keeps of the
        # drawing, not every one of the 60,000 lines again), zoomed out and zoomed in
        from . import commands as C
        v.osnap_on = True
        v.run(C.LineCmd)
        v.input_text("5,5")
        v.repaint()
        ds = 0.0
        r = v.renderer()
        drawn = [0]
        real_paint = r.paint

        def counted(*a, **k):
            drawn[0] += 1
            return real_paint(*a, **k)
        r.paint = counted
        try:
            for zoom in (1.0, 40.0):
                v.zoom("sheet")
                v.scale *= zoom
                v.repaint()
                drawn[0] = 0
                t = time.perf_counter()
                for i in range(n):
                    pos = QPointF(200 + i * 7, 300 + i * 3)
                    app.sendEvent(v, QMouseEvent(QEvent.MouseMove, pos, v.mapToGlobal(pos),
                                                 Qt.NoButton, Qt.NoButton, Qt.NoModifier))
                    v.repaint()
                ds = max(ds, (time.perf_counter() - t) / n)
                # (the time depends on the machine; this doesn't: no object is drawn again)
                assert drawn[0] == 0, "the drawing was drawn again on %d of %d mouse moves" % (
                    drawn[0], n)
            # panning and wheel zoom steps (the owner: "the gui doesn't seem to move and zoom
            # in/out as smoothly as autocad"): the last picture moved and scaled, no object
            # drawn again until they stop, then drawn sharp once
            v.cancel()
            v.zoom("sheet")
            v.repaint()
            drawn[0] = 0
            t = time.perf_counter()
            for i in range(n):
                if i % 2:
                    v.zoom_at(1.1 if i % 4 == 1 else 1 / 1.1, QPointF(300, 200))
                else:
                    v.center = (v.center[0] + 4.0 / v.scale, v.center[1] + 2.0 / v.scale)
                    v._moving()
                v.repaint()
            dv = (time.perf_counter() - t) / n
            assert drawn[0] == 0, "the drawing was drawn again on %d of %d pan and zoom steps" \
                % (drawn[0], n)
            v._moving_until = 0.0
            v.repaint()
            assert drawn[0] >= 1, "not drawn again sharp once panning and zooming stopped"
        finally:
            r.paint = real_paint
        v.cancel()
        assert ds < BUDGET["snap_move"], "a mouse move with snaps, drawn, took %.1f ms" % (
            ds * 1000)
        assert dv < BUDGET["view_step"], "a pan or zoom step took %.1f ms" % (dv * 1000)
        # Print (fit to letter paper, into a PDF file) and the sheet in a window of its own
        from . import print_out
        t = time.perf_counter()
        pdf = os.path.join(tmp, "big-print.pdf")
        assert print_out.print_sheets(p, print_out.pdf_printer(pdf), [s]) == 1
        dp = time.perf_counter() - t
        assert os.path.getsize(pdf) > 10000, "the printed sheet is nearly empty"
        assert dp < BUDGET["big_print"], "printing the sheet took %.2f s" % dp
        t = time.perf_counter()
        w2 = w.new_window(s.id)
        w2.view().repaint()
        w2.close()
        app.processEvents()
        dw = time.perf_counter() - t
        assert w.family == [w], "the second window didn't close"
        assert dw < BUDGET["big_window"], "the sheet in a new window took %.2f s" % dw
        p.saved_at = len(p.undo_stack)
        w.close_tab(w.tabs.indexOf(d))
        mb = _peak_mb()
        assert mb < BUDGET["peak_mb"], "peak memory %.0f MB" % mb
        return ("open+draw %.2f s, 10 zooms %.2f s, 1,000 adds %.2f s, 1,000 moved %.2f s, "
                "hover %.1f ms, snap move drawn %.1f ms, pan/zoom step %.1f ms, printed %.2f s, "
                "new window %.2f s, peak %.0f MB"
                % (dt, dz, da, dm, dh * 1000, ds * 1000, dv * 1000, dp, dw, mb))

    def text_font():
        """The font text is drawn and measured with: the letters as tall as asked, a line as
        wide as a sans-serif font makes it (a font that measures far narrower or wider would
        wrap multi-line notes and place texts unlike the drawing shows)."""
        from PySide6.QtGui import QFontInfo
        from . import render
        f = render.text_font()
        fam = QFontInfo(f).family()
        w = M.text_width("ALL WIRING 14 AWG UNLESS NOTED", 0.1)
        cap = render._font_cache["cap"]
        assert 1.6 < w < 3.6, "a 0.1\" line measured %.2f\" in %s (cap %.1f px)" % (w, fam, cap)
        return "%s, cap height %.1f px of %d, reference line %.2f\"" % (
            fam, cap, render.FONT_PX, w)
    log.check("text font", text_font)
    log.check("speed budget (60,000-line sheet)", big_sheet)

    def collector_pauses():
        """(0.26) Python's full collections while working on a big project the program
        opened: none may stop the window longer than the budget (gcpolicy; up to 0.25 each
        went through every object: 60 to 860 ms on the builds, the window frozen). Worked on
        until Python has made a few on its own, as it does every so often."""
        import gc
        import random
        from PySide6.QtCore import QPointF, QEvent, Qt
        from PySide6.QtGui import QMouseEvent
        from . import gcpolicy
        assert gcpolicy.installed(), "the main window didn't set up gcpolicy"
        w = state["win"]
        coil, no = w.library.get("symbol", "Relay coil"), w.library.get("symbol", "Contact NO")
        rnd = random.Random(11)
        src = M.Project.new()
        while len(src.sheets) < 40:
            src.sheets.append(src.make_sheet("Sheet %d" % (len(src.sheets) + 1)))
        for k, s in enumerate(src.sheets):
            for i in range(1000):
                x, y = rnd.uniform(0.7, 16.3), rnd.uniform(0.7, 10.3)
                s._put(M.Line((x, y), (x + rnd.uniform(-0.2, 0.2), y + rnd.uniform(-0.2, 0.2))))
            for i in range(60):
                x, y = 1 + (i % 8) * 1.8, 1 + (i // 8) * 1.2
                n = k * 60 + i
                m = (n + 60 * 7) % 2400                 # (a contact of a coil 7 sheets on)
                s._put(M.Insert(coil.name, (x, y), defn=coil,
                                attrs={"TAG": "CR%d" % (1000 + n), "DEV": "d%d" % n}))
                s._put(M.Insert(no.name, (x + 0.8, y), defn=no,
                                attrs={"TAG": "CR%d" % (1000 + m), "PARENT": "d%d" % m}))
                s._put(M.Wire([(x, y - 0.5), (x + 0.6, y - 0.5)], num="%d%03d" % (k % 9 + 1, i)))
        path = os.path.join(tmp, "collector.kzcad")
        src.save(path)
        del src, s
        pauses = []
        started = [None]

        def timed(phase, info):
            if info.get("generation") != 2:
                return
            if phase == "start":
                started[0] = time.perf_counter()
            elif started[0] is not None:
                pauses.append(time.perf_counter() - started[0])
                started[0] = None
        d = w.open_path(path)
        assert d is not None, "the project didn't open"
        v, p = d.view, d.project
        v.zoom("sheet")
        v.repaint()
        app.processEvents()
        steps = 0
        gc.callbacks.append(timed)
        try:
            # (a few objects picked and moved, undone and done again now and then, copied and
            # pasted where they were (Enter), the view zoomed, the mouse moved, the sheets gone
            # through: until Python has made three full collections of its own, or the most
            # steps a full collection took up to 0.25)
            while len(pauses) < 3 and steps < 1500:
                s = p.sheets[steps % len(p.sheets)]
                v.show_sheet(s.id)
                ids = list(s.entities)
                for i in range(5):
                    pos = QPointF(150 + (steps * 37 + i * 11) % 600, 120 + (steps * 13) % 400)
                    app.sendEvent(v, QMouseEvent(QEvent.MouseMove, pos, v.mapToGlobal(pos),
                                                 Qt.NoButton, Qt.NoButton, Qt.NoModifier))
                pick = rnd.sample(ids, 40)
                v.set_selection(set(pick))
                if steps % 3 == 2:
                    w.copy_clip()
                    w.paste()
                    v.enter()
                else:
                    with p.edit("Move") as ed:
                        for i in pick:
                            ed.change(s, s.entities[i].moved(0.01, 0.01))
                if steps % 4 == 3:
                    p.undo()
                    p.redo()
                v.zoom_at(1.1 if steps % 2 else 1 / 1.1, QPointF(300, 200))
                v._moving_until = 0.0
                v.repaint()
                app.processEvents()
                steps += 1
        finally:
            gc.callbacks.remove(timed)
            p.saved_at = len(p.undo_stack)
            w.close_tab(w.tabs.indexOf(d))
        assert pauses, "Python made no full collection in %d steps: nothing measured" % steps
        worst = max(pauses)
        assert worst < BUDGET["gc_pause"], \
            "a full collection stopped the window %.0f ms (%d of %d over %.0f ms, %d steps)" % (
                worst * 1000, sum(x >= BUDGET["gc_pause"] for x in pauses), len(pauses),
                BUDGET["gc_pause"] * 1000, steps)
        return "%d full collection(s) in %d steps, the longest %.1f ms" % (
            len(pauses), steps, worst * 1000)
    log.check("speed budget (Python's collector)", collector_pauses)

    def notes_sheet():
        import os
        import random
        import tempfile
        from . import bom, fileio
        w = state["win"]
        rnd = random.Random(5)
        p = M.Project.new()
        s = p.sheets[0]
        # (0.21: 1,000 pictures, as a new kind of object must be measured: two pictures,
        # each many times, as a logo is on every sheet)
        import base64
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice
        from PySide6.QtGui import QColor, QImage
        pics = []
        for color in ("#c03030", "#3060c0"):
            img = QImage(120, 60, QImage.Format_RGB32)
            img.fill(QColor(color))
            raw = QByteArray()
            buf = QBuffer(raw)
            buf.open(QIODevice.WriteOnly)
            img.save(buf, "PNG")
            buf.close()
            pics.append(base64.b64encode(bytes(raw)).decode("ascii"))
        t = time.perf_counter()
        with p.edit("Notes") as ed:
            for i in range(2000):
                x, y = rnd.uniform(1, 15), rnd.uniform(1, 9)
                sq = [(x, y), (x + .3, y), (x + .3, y + .3), (x, y + .3)]
                ed.add(s, M.Polyline(sq, True))
                ed.add(s, M.Hatch([sq], rnd.choice(["SOLID", "ANSI31", "ANSI37", "LINES"]),
                                  45.0, 0.02))
                ed.add(s, M.Text((x, y - .2), "TB%d-%d" % (i // 20, i % 20), 0.1,
                                 rnd.choice([0.0, 90.0])))
            for i in range(1000):
                x, y = rnd.uniform(1, 15), rnd.uniform(1, 9)
                ed.add(s, M.Leader([(x, y), (x + .5, y + .5), (x + .8, y + .5)],
                                   "%d" % (i + 1) if i % 3 == 0 else "SEE NOTE %d" % i,
                                   balloon=i % 3 == 0))
                ed.add(s, M.MText((x, y), "1. ALL WIRE 14 AWG MTW UNLESS NOTED\n2. GROUND "
                                  "PER NEC 250", 0.1, 0.0, "TL", 1.5))
                # (0.16.4: dashed boxes with a note, as a new kind of object must be measured)
                ed.add(s, M.DashBox.from_corners((x, y), (x + 1.2, y - .8),
                                                 text="FIELD WIRING\nBY OTHERS", height=0.1))
                ed.add(s, M.Picture((x + .2, y - .6), 0.6, 0.3, pics[i % 2], "png",
                                    rnd.choice([0.0, 90.0])))
        d = w.add_document(p)
        v = d.view
        v.zoom("sheet")
        v.repaint()
        app.processEvents()
        do = time.perf_counter() - t
        assert do < BUDGET["notes_open"], "added and drawn in %.2f s" % do
        t = time.perf_counter()
        for k in range(10):
            v.zoom_at(1.25, None)
            v._moving_until = 0.0       # (each drawn sharp: not the moved picture of a step)
            v.repaint()
        dz = time.perf_counter() - t
        assert dz < BUDGET["notes_zoom"], "ten zoomed repaints took %.2f s" % dz
        v.zoom("sheet")
        # a lasso drawn around half the sheet (it took seconds a mouse move over an imported
        # panel: each lit object's outline tested against every lasso edge)
        import math
        from PySide6.QtCore import QPointF, QEvent, Qt
        from PySide6.QtGui import QMouseEvent

        def mouse(kind, pos, button, buttons):
            app.sendEvent(v, QMouseEvent(kind, pos, v.mapToGlobal(pos), button, buttons,
                                         Qt.NoModifier))
        def at(i, n):
            # around the middle of the drawing, from the empty margin above it (a press on an
            # object would grab it instead)
            a = math.pi / 2 + 2 * math.pi * 0.97 * i / n
            return v.to_screen((8.5 + 6.0 * math.cos(a), 5.5 + 4.9 * math.sin(a)))
        n = 120
        mouse(QEvent.MouseMove, at(0, n), Qt.NoButton, Qt.NoButton)
        mouse(QEvent.MouseButtonPress, at(0, n), Qt.LeftButton, Qt.LeftButton)
        t = time.perf_counter()
        for i in range(1, n + 1):
            mouse(QEvent.MouseMove, at(i, n), Qt.NoButton, Qt.LeftButton)
            v.repaint()
        dl = (time.perf_counter() - t) / n
        t = time.perf_counter()
        mouse(QEvent.MouseButtonRelease, at(n, n), Qt.LeftButton, Qt.NoButton)
        dp = time.perf_counter() - t
        caught = len(v.sel)
        v.set_selection(set())
        assert caught > 100, "the lasso caught %d objects" % caught
        assert dl < BUDGET["lasso_move"], "a lasso mouse move took %.1f ms" % (dl * 1000)
        assert dp < BUDGET["lasso_pick"], "the lasso's pick took %.2f s" % dp
        ids = [e.id for e in s.entities.values() if isinstance(e, M.Picture)][:500]
        ids += [e.id for e in s.entities.values()
                if isinstance(e, (M.Leader, M.Hatch, M.MText, M.DashBox))][:1000 - len(ids)]
        t = time.perf_counter()
        with p.edit("Move") as ed:
            for i in ids:
                ed.change(s, s.entities[i].moved(0.5, 0.5))
        v.repaint()
        dm = time.perf_counter() - t
        assert dm < BUDGET["notes_move"], "1,000 moved in %.2f s" % dm
        t = time.perf_counter()
        p.undo()
        v.repaint()
        du = time.perf_counter() - t
        assert du < BUDGET["notes_undo"], "the move undone in %.2f s" % du
        p.saved_at = len(p.undo_stack)
        w.close_tab(w.tabs.indexOf(d))
        # a DXF as another program writes it, imported
        import ezdxf
        doc = ezdxf.new("R2013")
        doc.header["$INSUNITS"] = 1
        b = doc.blocks.new("TB")
        b.add_lwpolyline([(0, 0), (.2, 0), (.2, .5), (0, .5)], close=True)
        b.add_circle((.1, .25), .05)
        for k, tag in enumerate(("TAG1", "MFG", "CAT")):
            b.add_attdef(tag, (0, -.1 * (k + 1)), dxfattribs={"height": .05})
        msp = doc.modelspace()
        for i in range(1000):
            r = msp.add_blockref("TB", (i % 50 * .3, i // 50 * .7))
            r.add_auto_attribs({"TAG1": "T%d" % i, "MFG": "PHOENIX", "CAT": "3044076"})
        for i in range(200):
            msp.add_linear_dim(base=(i * .1, 20), p1=(i * .1, 19),
                               p2=(i * .1 + .5, 19)).render()
        for i in range(500):
            h = msp.add_hatch()
            h.paths.add_polyline_path([(i * .1, 25), (i * .1 + .05, 25), (i * .1 + .05, 25.05)],
                                      is_closed=True)
        path = os.path.join(tempfile.mkdtemp(), "blocks.dxf")
        doc.saveas(path)
        q = M.Project.new()
        t = time.perf_counter()
        got = fileio.import_dxf(q, q.sheets[0], path)
        di = time.perf_counter() - t
        assert di < BUDGET["import_blocks"], "the DXF imported in %.2f s" % di
        kept = [e for e in q.sheets[0].entities.values() if isinstance(e, M.Insert)]
        assert len(kept) == 1000, "%d of 1,000 blocks kept as blocks" % len(kept)
        t = time.perf_counter()
        head, body = bom.table(q)
        db = time.perf_counter() - t
        assert db < BUDGET["bom"], "the bill of materials took %.2f s" % db
        assert any("3044076" in " ".join(str(c) for c in r) for r in body), \
            "the imported parts' catalog number is not in the bill of materials"
        return ("drawn %.2f s, 10 zooms %.2f s, lasso move %.1f ms (picked %d in %.2f s), "
                "1,000 moved %.2f s, undone %.2f s, "
                "DXF of 1,000 blocks imported %.2f s (%d objects), BOM %.3f s"
                % (do, dz, dl * 1000, caught, dp, dm, du, di, got["count"], db))
    log.check("speed budget (notes, hatches, leaders, imports)", notes_sheet)

    def ladder_sheet():
        w = state["win"]
        p = M.Project.new()
        s = p.sheets[0]
        t = time.perf_counter()
        with p.edit("Ladders") as ed:
            ed.layer("LADDER", None, M.Layer("LADDER", M.ADAPTIVE).to_dict())
            ed.project_settings({"referencing": "ladder"})
            for i in range(100):
                x, y = 1.0 + (i % 10) * 1.5, 30.0 + (i // 10) * 21.0
                ed.add(s, M.Ladder((x, y), (x + 1.2, y), rungs=40, spacing=0.5, height=0.1))
        d = w.add_document(p)
        v = d.view
        v.zoom("extents")
        v.repaint()
        app.processEvents()
        do = time.perf_counter() - t
        lads = s.ladders()
        assert len(lads) == 100 and lads[-1].number(39), "the ladders aren't numbered"
        assert do < BUDGET["ladders_open"], "100 ladders added and drawn in %.2f s" % do
        t = time.perf_counter()
        for _k in range(10):
            v.zoom_at(1.25, None)
            v._moving_until = 0.0
            v.repaint()
        dz = time.perf_counter() - t
        assert dz < BUDGET["ladders_zoom"], "ten zoomed repaints took %.2f s" % dz
        t = time.perf_counter()
        hits = 0
        for i in range(2000):
            lad = lads[i % 100]
            q = (lad.a[0] + 0.6, lad.a[1] - (i % 40) * 0.5)
            hits += p.zone_text(s, *q) == lad.number(i % 40)
        dr = time.perf_counter() - t
        assert hits == 2000, "%d of 2,000 places read their rung" % hits
        assert dr < BUDGET["ladder_refs"], "2,000 places read by rung in %.2f s" % dr
        t = time.perf_counter()
        with p.edit("Move") as ed:
            for lad in list(s.ladders()):
                ed.change(s, s.entities[lad.id].moved(0.25, 0.0))
        v.repaint()
        dm = time.perf_counter() - t
        assert dm < BUDGET["ladders_move"], "100 ladders moved in %.2f s" % dm
        t = time.perf_counter()
        p.undo()
        v.repaint()
        du = time.perf_counter() - t
        assert du < BUDGET["ladders_undo"], "the move undone in %.2f s" % du
        p.saved_at = len(p.undo_stack)
        w.close_tab(w.tabs.indexOf(d))
        return ("100 ladders, 4,000 rungs: drawn %.2f s, 10 zooms %.2f s, 2,000 places by rung "
                "%.3f s, moved %.2f s, undone %.2f s" % (do, dz, dr, dm, du))
    log.check("speed budget (ladders)", ladder_sheet)

    def dash_polygons():
        w = state["win"]
        p = M.Project.new()
        s = p.sheets[0]
        t = time.perf_counter()
        with p.edit("Dashed polygons") as ed:
            ed.layer("NOTES", None, M.Layer("NOTES", M.ADAPTIVE).to_dict())
            for i in range(2000):
                x, y = 1.0 + (i % 50) * 0.32, 1.0 + (i // 50) * 0.24
                ed.add(s, M.DashPolygon([(x, y), (x + .3, y), (x + .3, y + .1), (x + .15, y + .1),
                                         (x + .15, y + .2), (x, y + .2)],
                                        text="F%d" % i if i % 2 else "", height=0.03))
        d = w.add_document(p)
        v = d.view
        v.zoom("extents")
        v.repaint()
        app.processEvents()
        do = time.perf_counter() - t
        assert do < BUDGET["dpoly_open"], "2,000 dashed polygons added and drawn in %.2f s" % do
        t = time.perf_counter()
        for _k in range(10):
            v.zoom_at(1.25, None)
            v._moving_until = 0.0
            v.repaint()
        dz = time.perf_counter() - t
        assert dz < BUDGET["dpoly_zoom"], "ten zoomed repaints took %.2f s" % dz
        v.zoom("extents")
        t = time.perf_counter()
        with p.edit("Move") as ed:
            for e in list(s.entities.values()):
                ed.change(s, e.moved(0.25, 0.0))
        v.repaint()
        dm = time.perf_counter() - t
        assert dm < BUDGET["dpoly_move"], "2,000 dashed polygons moved in %.2f s" % dm
        t = time.perf_counter()
        p.undo()
        v.repaint()
        du = time.perf_counter() - t
        assert du < BUDGET["dpoly_undo"], "the move undone in %.2f s" % du
        # Join: 1,000 chains of three lines and a polyline, each with a line a hair off
        with p.edit("Lines") as ed:
            ids = set()
            for i in range(1000):
                x, y = 1.0 + (i % 40) * 0.4, 12.0 + (i // 40) * 0.4
                for e in (M.Line((x, y), (x + .1, y)), M.Line((x + .1, y), (x + .2, y)),
                          M.Line((x + .2, y), (x + .2, y + .1)),
                          M.Polyline([(x + .2, y + .1), (x + .3, y + .1), (x + .3, y + .3)]),
                          M.Line((x + .301, y + .3), (x + .35, y + .3))):
                    ids.add(ed.add(s, e).id)
        v.repaint()
        v.set_selection(ids)
        t = time.perf_counter()
        v.run(C.JoinCmd)
        v.repaint()
        dj = time.perf_counter() - t
        made = [e for e in s.entities.values() if type(e) is M.Polyline]
        assert len(made) == 1000 and all(len(e.points) == 5 for e in made) and \
            len(s.entities) == 4000, "Join made %d polylines of 1,000 chains" % len(made)
        assert dj < BUDGET["join"], "5,000 objects joined in %.2f s" % dj
        t = time.perf_counter()
        p.undo()
        v.repaint()
        dju = time.perf_counter() - t
        assert dju < BUDGET["join_undo"], "the join undone in %.2f s" % dju
        p.saved_at = len(p.undo_stack)
        w.close_tab(w.tabs.indexOf(d))
        return ("2,000 dashed polygons: drawn %.2f s, 10 zooms %.2f s, moved %.2f s, undone "
                "%.2f s; Join of 5,000 objects into 1,000 polylines %.2f s, undone %.2f s"
                % (do, dz, dm, du, dj, dju))
    log.check("speed budget (dashed polygons, Join)", dash_polygons)

    def pull_list():
        from . import pull
        w = state["win"]
        lib = w.library
        term, strip, lt = (lib.get("symbol", n) for n in ("Terminal", "Terminal strip",
                                                            "Pilot light"))
        p = M.Project.new()
        s = p.sheets[0]
        s.location = "MCP"
        s._put(M.Insert(strip.name, (1, 10.5), defn=strip, attrs={"TAG": "TB1"}))
        for i in range(2000):
            x, y = 1 + (i % 40) * 0.4, 1 + (i // 40) * 0.18
            t = M.Insert(term.name, (x, y), defn=term, attrs={"TAG": "TB1", "TERM": str(i + 1)})
            d = M.Insert(lt.name, (x + 0.2, y), defn=lt,
                         attrs=dict({"TAG": "LT%d" % i}, **({"LOC": "FIELD"} if i % 2 else {})))
            s._put(t)
            s._put(d)
            s._put(M.Wire([dict(t.pin_points())["2"], d.pin_points()[0][1]]))
        t0 = time.perf_counter()
        rs, _u = pull.runs(p)
        head, rows = pull.table(p)
        dt = time.perf_counter() - t0
        assert [(r["name"], len(r["conductors"])) for r in rs] == [
            ("MCP \u2194 FIELD", 1000)], [(r["name"], len(r["conductors"])) for r in rs]
        assert rows[0][6].startswith("TB1-"), rows[0]
        assert dt < BUDGET["pull"], "the pull list took %.2f s" % dt
        return "1,000 conductors to pull of 2,000 wires: %.3f s" % dt
    log.check("speed budget (cables between locations)", pull_list)

    def terminal_strips():
        from . import strip_window, strips
        w = state["win"]
        lib = w.library
        term, strip, lt = (lib.get("symbol", n) for n in ("Terminal", "Terminal strip",
                                                            "Pilot light"))
        p = M.Project.new()
        while len(p.sheets) < 50:
            p.sheets.append(p.make_sheet("Sheet %d" % (len(p.sheets) + 1)))
        for b in (term, strip, lt):
            p.blocks[b.name] = b
        for k, s in enumerate(p.sheets):
            s.location = "MCP"
            tb = M.Insert(strip.name, (1, 10.5), defn=strip,
                          attrs={"TAG": "TB%d" % (k + 1), "DEV": "strip%d" % k})
            s._put(tb)
            for i in range(100):
                x, y = 3 + (i % 10) * 1.4, 1 + (i // 10) * 0.9
                t = M.Insert(term.name, (x, y), defn=term,
                             attrs={"TAG": tb.attrs["TAG"], "PARENT": "strip%d" % k,
                                    "TERM": str(i + 1)})
                s._put(t)
                pins = dict(t.pin_points())
                for side, dx in (("1", -0.5), ("2", 0.5)):
                    d = M.Insert(lt.name, (x + dx, y + 0.3), defn=lt,
                                 attrs=dict({"TAG": "LT%d_%d%s" % (k, i, side)},
                                            **({"LOC": "FIELD"} if side == "2" else {})))
                    s._put(d)
                    s._put(M.Wire([pins[side], d.pin_points()[0][1]]))
        from . import wirenums
        with p.edit("Wire numbers") as ed:          # (numbered, as a project opened is)
            wirenums.sync(ed, p)
        p.undo_stack.clear()
        t0 = time.perf_counter()
        dlg = strip_window.StripEditorDialog(w, p)
        do = time.perf_counter() - t0
        assert dlg.list.count() == 50 and dlg.table.rowCount() == 100, (
            dlg.list.count(), dlg.table.rowCount())
        assert "(FIELD)" in dlg.table.item(0, 4).text(), dlg.table.item(0, 4).text()
        t0 = time.perf_counter()
        rows = strips.plan_rows(p)
        dp = time.perf_counter() - t0
        assert len(rows) == 5000 and rows[0][5].endswith("(FIELD)"), rows[0]
        lay = dlg.layout_of(0)
        lay.rows.reverse()
        lay.renumber(1)
        t0 = time.perf_counter()
        assert dlg.apply()
        da = time.perf_counter() - t0
        dlg.deleteLater()
        got = [r.places[0][1].pos for r in strips.find(p, wires=False)[0].rows]
        assert got[0][1] > got[-1][1], "the strip renumbered backwards: %r" % got[:2]
        assert len(p.undo_stack) == 1
        assert do < BUDGET["strips_open"], "Terminal strips... opened in %.2f s" % do
        assert dp < BUDGET["strips_plan"], "the terminal plan in %.2f s" % dp
        assert da < BUDGET["strips_apply"], "a strip renumbered and written back in %.2f s" % da
        return ("50 strips of 100 terminals (10,000 wires): Terminal strips... opened %.3f s, "
                "the terminal plan %.3f s, a strip renumbered and written back %.3f s"
                % (do, dp, da))
    log.check("speed budget (terminal strips)", terminal_strips)

    def panel_wiring():
        from . import panelwiring, wirenums
        w = state["win"]
        lib = w.library
        coil, cb = lib.get("symbol", "Contactor coil"), lib.get("symbol", "Circuit breaker 1-pole")
        fk, fb = lib.get("footprint", "Contactor 9-18 A"), lib.get("footprint",
                                                                   "Breaker 1-pole (DIN)")
        p = M.Project.new()
        for b in (coil, cb, fk, fb):
            p.blocks[b.name] = b
        while len(p.sheets) < 20:
            s = p.make_sheet("Sheet %d" % (len(p.sheets) + 1))
            s.id = p.new_sheet_id()
            p.sheets.append(s)
        panels = []
        for k in range(4):
            ps = p.make_sheet("Panel %d" % (k + 1), "panel")
            ps.id, ps.scale, ps.terminal_labels = p.new_sheet_id(), 0.125, True
            p.sheets.append(ps)
            panels.append(ps)
        n = 0
        for s in p.sheets[:20]:
            s.location = "MCP"
            for i in range(50):
                x, y = 1.0 + (i % 5) * 3.0, 1.0 + (i // 5) * 0.9
                c = M.Insert(coil.name, (x + 1.8, y), defn=coil,
                             attrs={"TAG": "M%d" % n, "DEV": "m%d" % n})
                b = M.Insert(cb.name, (x, y), defn=cb,
                             attrs=dict({"TAG": "CB%d" % n, "DEV": "b%d" % n},
                                        **({"LOC": "FIELD"} if i % 2 else {})))
                s._put(c)
                s._put(b)
                cp, bp = dict(c.pin_points()), dict(b.pin_points())
                # (ten wires: four from the breaker to the coil, three off each other end)
                a, z = bp["2"], cp["A1"]
                xs = [a[0] + (z[0] - a[0]) * t / 4.0 for t in range(5)]
                for j in range(4):
                    s._put(M.Wire([(xs[j], y), (xs[j + 1], y)]))
                for q, dx in ((bp["1"], -0.1), (cp["A2"], 0.1)):
                    for j in range(3):
                        s._put(M.Wire([(q[0] + dx * j, q[1]), (q[0] + dx * (j + 1), q[1])]))
                ps = panels[n // 500]
                m = n % 500
                px, py = 4.0 + (m % 25) * 5.0, 4.0 + (m // 25) * 4.5
                ps._put(M.Insert(fk.name, (px, py), defn=fk, angle=90.0 if m % 3 == 0 else 0.0,
                                 attrs={"TAG": c.attrs["TAG"], "PARENT": c.attrs["DEV"]}))
                ps._put(M.Insert(fb.name, (px + 2.2, py), defn=fb,
                                 attrs={"TAG": b.attrs["TAG"], "PARENT": b.attrs["DEV"]}))
                n += 1
        with p.edit("Wire numbers") as ed:          # (numbered, as a project opened is)
            wirenums.sync(ed, p)
        p.undo_stack.clear()
        assert sum(len(s.wires()) for s in p.sheets) == 10000
        t0 = time.perf_counter()
        rows = panelwiring.rows(p)
        dl = time.perf_counter() - t0
        assert len(rows) == 4000 and rows[1][6] == "M0:A1", rows[:2]
        p._panel_wiring = None
        d = w.add_document(p)
        v = d.view
        v.show_sheet(panels[0].id)
        t0 = time.perf_counter()
        v.zoom("extents")
        v.repaint()
        app.processEvents()
        do = time.perf_counter() - t0
        labs = panelwiring.labels(p, panels[0])
        num = rows[1][2]
        assert len(labs) == 2000 and "%s → CB0:2" % num in {t.text for t in labs}, labs[:2]
        t0 = time.perf_counter()
        for _k in range(10):
            v.zoom_at(1.25, None)
            v._moving_until = 0.0
            v.repaint()
        dz = time.perf_counter() - t0
        s0 = p.sheets[0]
        m0 = next(x for x in s0.inserts() if x.attrs.get("TAG") == "M0")
        t0 = time.perf_counter()
        with p.edit("Retag") as ed:
            ed.change(s0, m0.copy(attrs=dict(m0.attrs, TAG="MX", TAG_LOCK="1")))
        v.repaint()
        de = time.perf_counter() - t0
        assert "%s → MX:A1" % num in {t.text for t in panelwiring.labels(p, panels[0])}, \
            "the labels didn't follow the device retagged"
        p.saved_at = len(p.undo_stack)
        w.close_tab(w.tabs.indexOf(d))
        assert dl < BUDGET["wiring_list"], "the wiring list in %.2f s" % dl
        assert do < BUDGET["wiring_open"], "a panel sheet's labels and drawing in %.2f s" % do
        assert dz < BUDGET["wiring_zoom"], "ten zoomed repaints in %.2f s" % dz
        assert de < BUDGET["wiring_edit"], "a device retagged, the labels following: %.2f s" % de
        return ("2,000 devices, 10,000 wires: the wiring list %.3f s, a panel sheet of 2,000 "
                "labels drawn %.3f s, 10 zooms %.3f s, a device retagged and the labels "
                "following %.3f s" % (dl, do, dz, de))
    log.check("speed budget (panel wiring)", panel_wiring)

    def trace():
        # (Trace, 0.23; the owner: "make sure that the loading of the cross-references doesn't
        # prevent any interaction with the sheet itself"): 50 sheets of 1,000 lines, 40 coils,
        # 40 contacts of another sheet's coils and 40 numbered wires each, the panel open
        import random
        from PySide6.QtCore import QPointF, QEvent, Qt
        from PySide6.QtGui import QMouseEvent
        from . import trace_panel
        w = state["win"]
        coil, no = w.library.get("symbol", "Relay coil"), w.library.get("symbol", "Contact NO")
        rnd = random.Random(11)
        p = M.Project.new()
        while len(p.sheets) < 50:
            p.sheets.append(p.make_sheet("Sheet %d" % (len(p.sheets) + 1)))
        picks = []
        for k, s in enumerate(p.sheets):
            for i in range(1000):
                x, y = rnd.uniform(0.7, 16.3), rnd.uniform(0.7, 10.3)
                s._put(M.Line((x, y), (x + rnd.uniform(-0.2, 0.2), y + rnd.uniform(-0.2, 0.2))))
            for i in range(40):
                x, y = 1 + (i % 8) * 1.8, 1 + (i // 8) * 1.8
                n = k * 40 + i
                c = M.Insert(coil.name, (x, y), defn=coil,
                             attrs={"TAG": "CR%d" % (1000 + n), "DEV": "d%d" % n})
                m = (n + 40 * 7) % 2000             # (a contact of a coil 7 sheets on)
                ct = M.Insert(no.name, (x + 0.8, y), defn=no,
                              attrs={"TAG": "CR%d" % (1000 + m), "PARENT": "d%d" % m})
                wr = M.Wire([(x, y - 0.5), (x + 0.6, y - 0.5)], num="%d%03d" % (k % 9 + 1, i))
                for e in (c, ct, wr):
                    s._put(e)
                if i % 10 == 0:
                    picks.append((s, c))
                    picks.append((s, wr))
        d = w.add_document(p)
        v = d.view
        app.processEvents()
        ticks, clicks, whole, moves, heads = [], [], [], [], []
        real_work = w._trace_work
        import gc
        gc.collect()        # (Trace timed, not a collection of the sheets made before)
        in_gc = [0.0, None]     # (time in Python's collector during a step, when one started)

        def collector(phase, info):
            if phase == "start":
                in_gc[1] = time.perf_counter()
            elif in_gc[1] is not None:
                in_gc[0] += time.perf_counter() - in_gc[1]
                in_gc[1] = None

        def timed():
            # (Python's collector can stop the program anywhere for a while, on any work, the
            # 0.25 build: 243 ms in one step; Trace's own slices are what this times)
            in_gc[0] = 0.0
            t0 = time.perf_counter()
            real_work()
            ticks.append(time.perf_counter() - t0 - in_gc[0])
        w._trace_work = timed
        gc.callbacks.append(collector)
        try:
            w.trace_dock.show()
            t0 = time.perf_counter()
            v.set_selection({picks[0][1].id})
            assert w.trace()
            while w.trace_busy():
                app.processEvents()
            first = time.perf_counter() - t0
            assert len(w.trace_panel.rows()) == 2, w.trace_panel.header.text()
            for n, (s, e) in enumerate(picks[1:41]):
                v.show_sheet(s.id)
                app.processEvents()
                t0 = time.perf_counter()
                v.set_selection({e.id})
                clicks.append(time.perf_counter() - t0)
                while w.trace_busy():
                    pos = QPointF(200 + n * 3 + len(moves) % 50, 300)
                    t1 = time.perf_counter()
                    app.sendEvent(v, QMouseEvent(QEvent.MouseMove, pos, v.mapToGlobal(pos),
                                                 Qt.NoButton, Qt.NoButton, Qt.NoModifier))
                    v.repaint()
                    moves.append(time.perf_counter() - t1)
                    app.processEvents()
                whole.append(time.perf_counter() - t0)
                heads.append(w.trace_panel.header.text())
            assert sum(h.startswith("Wire") for h in heads) == 20, heads
        finally:
            gc.callbacks.remove(collector)
            w._trace_work = real_work
            w.trace_dock.hide()
            p.saved_at = len(p.undo_stack)
            w.close_tab(w.tabs.indexOf(d))
        click, tick, move = max(clicks), max(ticks), max(moves)
        typical = sorted(whole)[len(whole) // 2]
        assert first < BUDGET["trace_index"], "Trace's first list took %.2f s" % first
        assert click < BUDGET["trace_click"], "a click with Trace open took %.1f ms" % (
            click * 1000)
        assert tick < BUDGET["trace_step"], "a step of Trace took %.1f ms" % (tick * 1000)
        assert move < BUDGET["snap_move"], "a mouse move while Trace works took %.1f ms" % (
            move * 1000)
        assert typical < BUDGET["trace_list"], "a pick listed in %.2f s" % typical
        return ("50 sheets: first list %.2f s; a click %.1f ms at most; a step %.1f ms at "
                "most (slices of %.0f ms); a mouse move meanwhile %.1f ms at most; listed in "
                "%.3f s typical, %.3f s at most" % (
                    first, click * 1000, tick * 1000, trace_panel.SLICE * 1000, move * 1000,
                    typical, max(whole)))
    log.check("speed budget (Trace)", trace)

    def props():
        # (0.25, the Properties panel; the owner's rule for Trace too: "make sure that the
        # loading ... doesn't prevent any interaction with the sheet itself") a sheet of
        # 20,000 objects, the panel open: a click only starts the panel's timer, the panel
        # fills from the selection alone, and a repaint is no slower with it open
        import random
        from PySide6.QtCore import QPointF, QEvent, Qt
        from PySide6.QtGui import QMouseEvent
        w = state["win"]
        coil = w.library.get("symbol", "Relay coil")
        rnd = random.Random(25)
        p = M.Project.new()
        s = p.sheets[0]
        p.blocks[coil.name] = coil
        picks = []
        for i in range(20000):
            x, y = rnd.uniform(0.7, 16.3), rnd.uniform(0.7, 10.3)
            k = i % 10
            if k == 0:
                e = M.Insert(coil.name, (x, y), defn=coil,
                             attrs={"TAG": "CR%d" % (1000 + i), "DEV": "d%d" % i})
            elif k == 1:
                e = M.Wire([(x, y), (x + 0.3, y)], num="%d" % (1000 + i))
            elif k == 2:
                e = M.Text((x, y), "T%d" % i, 0.1)
            else:
                e = M.Line((x, y), (x + rnd.uniform(-0.2, 0.2), y + rnd.uniform(-0.2, 0.2)))
            s._put(e)
            if k < 3 and i % 50 < 3:
                picks.append(e)
        d = w.add_document(p)
        v = d.view
        app.processEvents()
        clicks, fills, rep_closed, rep_open = [], [], [], []
        real_fill = w.props_fill

        def timed():
            t0 = time.perf_counter()
            real_fill()
            fills.append(time.perf_counter() - t0)

        def repaint(into):
            v._picture = None           # (the drawing drawn again, not the last picture)
            t0 = time.perf_counter()
            v.repaint()
            into.append(time.perf_counter() - t0)
        w.props_fill = timed
        try:
            w.props_dock.hide()
            app.processEvents()
            for e in picks[:30]:
                v.set_selection({e.id})
                repaint(rep_closed)
            w.properties()
            app.processEvents()
            fills.clear()
            import gc
            gc.collect()        # (the click timed, not a collection of the sheets made before)
            for e in picks[:60]:
                bb = e.bbox()
                pos = v.to_screen(((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2))
                pos = QPointF(pos)
                t0 = time.perf_counter()
                v.set_selection({e.id})
                clicks.append(time.perf_counter() - t0)
                assert w.props_busy(), "the panel filled inside the click"
                while w.props_busy():
                    app.sendEvent(v, QMouseEvent(QEvent.MouseMove, pos, v.mapToGlobal(pos),
                                                 Qt.NoButton, Qt.NoButton, Qt.NoModifier))
                    app.processEvents()
                assert w.props_panel.header.text().split(" ")[0] in ("Symbol", "Wire", "Text"), \
                    w.props_panel.header.text()
                if len(rep_open) < 30:
                    repaint(rep_open)
            n_fills = len(fills)
            t0 = time.perf_counter()
            v.select_all()
            w.props_fill()
            every = time.perf_counter() - t0
            head = w.props_panel.header.text()
            assert head.startswith("20000 selected"), head
        finally:
            w.props_fill = real_fill
            w.props_dock.hide()
            p.saved_at = len(p.undo_stack)
            w.close_tab(w.tabs.indexOf(d))
        click = max(clicks)
        fill = sorted(fills[:n_fills])[n_fills // 2]
        closed = sorted(rep_closed)[len(rep_closed) // 2]
        opened = sorted(rep_open)[len(rep_open) // 2]
        assert click < BUDGET["props_click"], "a click with the panel open took %.1f ms" % (
            click * 1000)
        assert fill < BUDGET["props_fill"], "the panel filled in %.3f s" % fill
        assert every < BUDGET["props_all"], "20,000 selected: the panel filled in %.2f s" % every
        assert opened < closed * 1.5 + BUDGET["props_repaint"], \
            "a repaint took %.1f ms with the panel open, %.1f ms closed" % (
                opened * 1000, closed * 1000)
        return ("20,000 objects: a click %.2f ms at most; the panel filled in %.1f ms typical "
                "(%.1f ms at most); all 20,000 selected %.2f s; a repaint %.1f ms open, %.1f "
                "ms closed (typical)" % (click * 1000, fill * 1000, max(fills[:n_fills]) * 1000,
                                         every, opened * 1000, closed * 1000))
    log.check("speed budget (Properties panel)", props)

    def missing_footprints():
        # (0.25) Devices without a footprint on 50 sheets: 2,000 devices, 1,000 footprints
        # linked to half of them on 10 panel sheets; worked out again after a change, and a
        # sheet drawn with the marks on
        from . import missing_fp, render
        w = state["win"]
        coil = w.library.get("symbol", "Relay coil")
        fpd = w.library.get("footprint", "Breaker 1-pole (DIN)")
        p = M.Project.new()
        p.blocks[coil.name] = coil
        p.blocks[fpd.name] = fpd
        while len(p.sheets) < 50:
            p.sheets.append(p.make_sheet("Sheet %d" % (len(p.sheets) + 1),
                                         "panel" if len(p.sheets) >= 40 else "schematic"))
        n = 0
        for k, s in enumerate(p.sheets[:40]):
            for i in range(50):
                s._put(M.Insert(coil.name, (1 + (i % 10) * 1.5, 1 + (i // 10) * 1.8),
                                defn=coil, attrs={"TAG": "CR%d" % (1000 + n), "DEV": "d%d" % n}))
                n += 1
        for j in range(1000):
            s = p.sheets[40 + j // 100]
            s._put(M.Insert(fpd.name, (1 + (j % 10) * 1.5, 1 + (j % 100 // 10) * 1.0),
                            defn=fpd, attrs={"TAG": "CR%d" % (1000 + 2 * j),
                                             "PARENT": "d%d" % (2 * j)}))
        t0 = time.perf_counter()
        got = missing_fp.find(p)
        first = time.perf_counter() - t0
        assert len(got) == 1000, len(got)
        s0 = p.sheets[0]
        with p.edit("one more") as ed:
            ed.add(s0, M.Insert(coil.name, (15, 9), defn=coil, attrs={"TAG": "CR9999",
                                                                     "DEV": "x"}))
        t0 = time.perf_counter()
        got = missing_fp.find(p)
        again = time.perf_counter() - t0
        assert len(got) == 1001, len(got)
        t0 = time.perf_counter()
        for _i in range(100):
            missing_fp.find(p)
        kept = (time.perf_counter() - t0) / 100
        from PySide6.QtGui import QImage, QPainter
        img = QImage(1700, 1100, QImage.Format_ARGB32)
        times = {}
        for on in (False, True):
            p.settings[missing_fp.SETTING] = on
            r = render.SheetRenderer(p, s0, True)
            qp = QPainter(img)
            r.paint(qp)                 # (its caches made)
            qp.end()
            t0 = time.perf_counter()
            for _i in range(10):
                qp = QPainter(img)
                qp.scale(100, 100)
                r.paint(qp)
                qp.end()
            times[on] = (time.perf_counter() - t0) / 10
        worst = max(first, again)
        assert worst < BUDGET["missing_fp"], "worked out in %.3f s" % worst
        assert times[True] < times[False] * 1.5 + 0.01, \
            "a sheet drawn in %.1f ms with the marks, %.1f ms without" % (
                times[True] * 1000, times[False] * 1000)
        return ("50 sheets, 2,000 devices, 1,000 footprints: worked out %.1f ms (after a "
                "change %.1f ms; unchanged %.3f ms); a sheet of 50 drawn %.1f ms with the "
                "marks, %.1f ms without" % (first * 1000, again * 1000, kept * 1000,
                                             times[True] * 1000, times[False] * 1000))
    log.check("speed budget (devices without a footprint)", missing_footprints)

    def pdf_links():
        from . import pdf_links as PL, xrefs
        lib = state["win"].library
        coil, no = lib.get("symbol", "Relay coil"), lib.get("symbol", "Contact NO")
        p = M.Project.new()
        with p.edit("sheets") as ed:
            for i in range(19):
                ed.add_sheet(p.make_sheet("S%d" % (i + 2)))
        # (on each sheet 10 coils, each with 5 contacts on the next sheet: 1,000 contacts,
        # each a reference under it and a line under its coil)
        for i, s in enumerate(p.sheets):
            nxt = p.sheets[(i + 1) % len(p.sheets)]
            for c in range(10):
                dev = "D%d-%d" % (i, c)
                s._put(M.Insert(coil.name, (1.5 + c * 1.5, 9.5), defn=coil,
                                attrs={"TAG": "CR%d" % (100 * i + c), "DEV": dev}))
                for k in range(5):
                    nxt._put(M.Insert(no.name, (1.5 + c * 1.5, 8.0 - k * 1.4), defn=no,
                                      attrs={"TAG": "CR%d" % (100 * i + c), "PARENT": dev}))
        n_refs = sum(len(xrefs.shown(p, s)) for s in p.sheets)
        assert n_refs == 2000, n_refs
        pdf = os.path.join(tmp, "links.pdf")
        t0 = time.perf_counter()
        fileio.export_pdf(p, pdf, links=False)
        dw = time.perf_counter() - t0
        t0 = time.perf_counter()
        n = PL.add_links(p, pdf, p.sheets)
        dt = time.perf_counter() - t0
        assert n == 2000, n
        assert dt < BUDGET["pdf_links"], "2,000 links added in %.2f s" % dt
        return "20 sheets drawn to PDF %.2f s; their 2,000 cross-reference links added %.3f s" % (
            dw, dt)
    log.check("speed budget (cross-reference links in a PDF)", pdf_links)

    def block_folder():
        import ezdxf
        from . import block_import as BI
        from . import import_blocks_window as IB
        from .library import Library
        src = os.path.join(tmp, "blocks")
        os.makedirs(src)
        for i in range(200):
            # (a coil as AutoCAD Electrical keeps one: wire connections X4TERM01 and X1TERM02,
            # their pin numbers, its tag)
            doc = ezdxf.new()
            doc.header["$INSUNITS"] = 1
            m = doc.modelspace()
            m.add_circle((0.0, 0.0), 0.25)
            m.add_line((-0.5, 0.0), (-0.25, 0.0))
            m.add_line((0.25, 0.0), (0.5, 0.0))
            for tag, at, text in (("X4TERM01", (-0.5, 0.0), ""), ("X1TERM02", (0.5, 0.0), ""),
                                  ("TERM01", (-0.4, 0.05), "A1"), ("TERM02", (0.4, 0.05), "A2"),
                                  ("TAG1", (0.0, 0.4), "")):
                m.add_attdef(tag, at, text=text, dxfattribs={"height": 0.08})
            doc.saveas(os.path.join(src, "HCR%03d.dxf" % i))
        lib = Library(os.path.join(tmp, "imported"))
        w = state["win"]
        # (the steps timed, not a full garbage collection of the 60,000-line sheets
        # measured before, which lands in whatever step runs then)
        import gc
        gc.collect()
        t0 = time.perf_counter()
        rows, read_step = IB.scan(w, BI.drawing_files(src))
        t_read = time.perf_counter()
        dlg = IB.ImportBlocksDialog(w, lib)
        dlg.folder = src
        dlg.set_rows(rows)
        listed = dlg.fill_step
        imp = dlg.importer()
        t_list = time.perf_counter()
        done, put_step = IB.put_in(w, imp)
        dt = time.perf_counter() - t0
        # (where the time went: on the Windows build 200 files flushed to disk one after the
        # other once took 12 s, their steps all short)
        parts = "reading %.2f s, listing %.2f s, writing %.2f s" % (
            t_read - t0, t_list - t_read, t0 + dt - t_list)
        dlg.deleteLater()
        assert done and len(imp.imported) == 200, (done, len(imp.imported), imp.failed)
        got = Library(lib.folder).get("symbol", "HCR117")
        assert [(q["name"], q["pos"]) for q in got.pins] == [("A1", (-0.5, 0.0)),
                                                             ("A2", (0.5, 0.0))], got.pins
        step = max(read_step, put_step, listed)
        assert dt < BUDGET["block_folder"], "200 block files imported in %.2f s (%s)" % (
            dt, parts)
        assert step < BUDGET["block_folder_step"], \
            "a step of %.3f s (reading %.3f, listing %.3f, writing %.3f)" % (
                step, read_step, listed, put_step)
        return ("200 block files read, listed and put in the library %.2f s (%s); longest "
                "step %.3f s (reading %.3f, listing %.3f, writing %.3f)" % (
                    dt, parts, step, read_step, listed, put_step))
    log.check("speed budget (import blocks)", block_folder)

    def saved_circuits():
        from . import circuits as CI
        from .circuit_window import CircuitBrowser
        from .library import Library
        w = state["win"]
        lib = Library(os.path.join(tmp, "circuits"))
        coil, no = w.library.get("symbol", "Relay coil"), w.library.get("symbol", "Contact NO")
        p = M.Project.new()
        s = p.sheets[0]
        p.blocks[coil.name], p.blocks[no.name] = coil, no
        # (the sheet: 700 devices, each with two contacts, on rungs of their own)
        for i in range(700):
            x, y = 40.0 + (i % 20) * 6.0, 2.0 + (i // 20) * 0.5
            s._put(M.Insert(coil.name, (x + 4.25, y), defn=coil,
                            attrs={"TAG": "CR%d" % (5000 + i), "DEV": "d%d" % i}))
            for dx in (0.25, 1.25):
                s._put(M.Insert(no.name, (x + dx, y), defn=no,
                                attrs={"TAG": "CR%d" % (5000 + i), "PARENT": "d%d" % i}))
        ents = []
        for i in range(100):
            y = 2.0 + i * 0.5
            dev = "c%d" % i
            ents.append(M.Insert(coil.name, (4.25, y), defn=coil, attrs={"DEV": dev,
                                                                       "TAG": "CR%d" % i}))
            for dx in (0.25, 1.25):
                ents.append(M.Insert(no.name, (dx, y), defn=no, attrs={"PARENT": dev,
                                                                     "TAG": "CR%d" % i}))
            for a, b in ((-1.0, 0.0), (0.5, 1.0), (1.5, 4.0), (4.5, 6.0)):
                ents.append(M.Wire([(a, y), (b, y)]))
        t0 = time.perf_counter()
        c = CI.make(p, ents, (0.0, 0.0), "Big", "Speed")
        lib.save_circuit(c)
        dsave = time.perf_counter() - t0
        c = lib.circuits()[0]["Big"]
        d = w.add_document(p)
        v = d.view
        v.zoom("extents")
        v.repaint()
        app.processEvents()
        cmd = v.run(C.InsertCircuitCmd, c)
        from PySide6.QtCore import QPointF, QEvent, Qt
        from PySide6.QtGui import QMouseEvent

        def move(q):
            app.sendEvent(v, QMouseEvent(QEvent.MouseMove, q, v.mapToGlobal(q), Qt.NoButton,
                                         Qt.NoButton, Qt.NoModifier))
            v.repaint()
        move(QPointF(200.0, 200.0))             # (its picture made once)
        t0 = time.perf_counter()
        for i in range(30):
            move(QPointF(200.0 + 3 * i, 200.0 + i))
        dmove = (time.perf_counter() - t0) / 30
        assert cmd._shown is not None, "Insert circuit showed nothing as the mouse moved"
        n0 = len(s.entities)
        t0 = time.perf_counter()
        v.input_text("8,60")
        v.repaint()
        dplace = time.perf_counter() - t0
        assert len(s.entities) == n0 + 700, (n0, len(s.entities))
        tagged = {e.attrs["TAG"] for e in s.inserts() if e.block == coil.name}
        assert len(tagged) == 800, len(tagged)
        devs = {e.attrs["DEV"] for e in s.inserts() if e.block == coil.name}
        linked = [e for e in s.inserts() if e.block == no.name and e.attrs.get("PARENT") in devs]
        assert len(linked) == 1600, len(linked)
        t0 = time.perf_counter()
        p.undo()
        v.repaint()
        dundo = time.perf_counter() - t0
        assert len(s.entities) == n0
        small = CI.make(p, ents[:7], (0.0, 0.0), "Rung")
        for i in range(100):
            lib.save_circuit(small.renamed("Rung %03d" % i, "Category %d" % (i % 10)))
        t0 = time.perf_counter()
        dlg = CircuitBrowser(w, lib)
        listed = sum(dlg.tree.topLevelItem(i).childCount()
                     for i in range(dlg.tree.topLevelItemCount()))
        dbrowse = time.perf_counter() - t0
        dlg.deleteLater()
        assert listed == 101, listed
        p.saved_at = len(p.undo_stack)
        w.close_tab(w.tabs.indexOf(d))
        for key, dt in (("circuit_save", dsave), ("circuit_place", dplace),
                        ("circuit_move", dmove), ("circuit_undo", dundo),
                        ("circuit_browse", dbrowse)):
            assert dt < BUDGET[key], "%s took %.3f s" % (key, dt)
        return ("a circuit of 700 objects saved %.3f s, placed on a sheet of 2,100 devices "
                "%.2f s, a mouse move with it %.1f ms, undone %.2f s; 101 circuits listed "
                "with pictures %.2f s" % (dsave, dplace, dmove * 1000, dundo, dbrowse))
    log.check("speed budget (saved circuits)", saved_circuits)

    w = state.get("win")
    if w is not None:
        for i in range(w.tabs.count()):
            d = w.tabs.widget(i)
            d.project.saved_at = len(d.project.undo_stack)
        w.close()
    from . import gcpolicy
    gcpolicy.uninstall()            # (as the program does when it quits)
    log.write("%d failure(s)" % log.failures)
    return log.failures
