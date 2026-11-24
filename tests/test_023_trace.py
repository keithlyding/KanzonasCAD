"""Trace (0.23; the owner, Nov 2026: "I like Allen Bradley's Cross referencing in their Studio
5000 software. I click on a tag and then use control E to go to a cross-references tab which
shows all the places that tag is used and shows whether it's an output or input, and some
other metadata"): Ctrl+E lists every place a device, a wire or a PLC point is in the project,
in a docked panel that follows the selection while it is open; Enter or a double-click on a
row goes there."""
import time
import unittest

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from tests.util import APP, window, type_in, NEAREST

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import where_used as WU


class TraceTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.lib = self.win.library
        with self.p.edit("sheets") as ed:
            ed.add_sheet(self.p.make_sheet("Controls"))
        self.s1, self.s2 = self.p.sheets
        self.win.trace_dock.hide()      # (another test's window may have left it open)

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def place(self, sheet, name, at, *more, kind="symbol"):
        self.v.show_sheet(sheet.id)
        before = set(sheet.entities)
        self.v.run(C.InsertCmd, self.lib.get(kind, name), {})
        type_in(self.v, "%g,%g" % at, *more)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        return [e for i, e in sheet.entities.items()
                if i not in before and isinstance(e, M.Insert)][0]

    def relay(self):
        """CR101's coil and a contact on sheet 1, an NC contact on sheet 2, its footprint on a
        panel sheet."""
        self.coil = self.place(self.s1, "Relay coil", (3, 9))
        self.tag = self.coil.attrs["TAG"]
        self.no = self.place(self.s1, "Contact NO", (8, 6), NEAREST)
        self.nc = self.place(self.s2, "Contact NC", (5, 4), self.tag)
        panel = self.p.make_sheet("Panel")
        panel.kind = "panel"
        with self.p.edit("panel") as ed:
            ed.add_sheet(panel)
        self.panel = panel
        fp = self.lib.get("footprint", sorted(self.lib.blocks("footprint")[0])[0])
        self.v.show_sheet(panel.id)
        self.v.run(C.InsertCmd, fp, {})
        type_in(self.v, "5,5", self.tag)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        self.fp = [e for e in panel.inserts() if e.attrs.get("TAG") == self.tag][0]
        self.v.show_sheet(self.s1.id)

    def settle(self):
        """The event loop run until Trace has nothing left to do (it works in its turns)."""
        for _i in range(5000):
            if not self.win.trace_busy():
                return
            QTest.qWait(2)
        self.fail("Trace never finished")

    def trace(self):
        got = self.win.trace()
        self.settle()
        return got

    def select(self, sheet, *ents):
        self.v.show_sheet(sheet.id)
        self.v.set_selection({e.id for e in ents})
        self.settle()

    def rows(self):
        return self.win.trace_panel.rows()

    # ---- what is listed ---------------------------------------------------------------------
    def test_a_device_its_contacts_and_footprint(self):
        self.relay()
        self.select(self.s1, self.coil)
        self.assertTrue(self.trace())
        self.assertTrue(self.win.trace_dock.isVisible())
        self.assertEqual(self.win.trace_panel.header.text(), "%s — 4 places" % self.tag)
        got = [(r.sheet_id, r.ids, r.role, r.name) for r in self.rows()]
        self.assertEqual(got, [
            (self.s1.id, (self.coil.id,), "Coil", self.tag),
            (self.s1.id, (self.no.id,), "NO contact", self.tag),
            (self.s2.id, (self.nc.id,), "NC contact", self.tag),
            (self.panel.id, (self.fp.id,), "Footprint", self.tag)])
        r = self.rows()[2]
        self.assertEqual(r.where, self.p.zone_text(self.s2, *self.nc.pos))
        self.assertTrue(r.where.startswith("2-"))
        self.assertEqual(r.sheet, "2  Controls")
        # (a contact, or the footprint, picked: its device's places, the same list)
        for s, e in ((self.s2, self.nc), (self.panel, self.fp)):
            self.select(s, e)
            self.assertTrue(self.trace())
            self.assertEqual([x.ids for x in self.rows()], [x[1] for x in got])

    def test_by_ladder_the_place_is_the_rung(self):
        self.relay()
        with self.p.edit("ladder") as ed:
            ed.add(self.s1, M.Ladder((2.0, 10.0), (12.0, 10.0), 20))
            ed.project_settings({"referencing": "ladder"})
        self.select(self.s1, self.coil)
        self.trace()
        r = self.rows()[0]
        self.assertEqual(r.where, self.p.zone_text(self.s1, *self.coil.pos))
        self.assertTrue(r.where.isdigit(), r.where)         # (a rung number: 102...)

    def test_a_contact_with_its_tag_typed_but_not_linked(self):
        self.relay()
        other = self.place(self.s2, "Pilot light", (10, 4))
        with self.p.edit("same tag") as ed:
            ed.change(self.s2, other.copy(attrs=dict(other.attrs, TAG=self.tag,
                                                     TAG_LOCK="1")))
        self.select(self.s1, self.coil)
        self.trace()
        mine = [r for r in self.rows() if (r.sheet_id, r.ids) == (self.s2.id, (other.id,))]
        self.assertEqual(len(mine), 1)
        self.assertIn("not linked", mine[0].desc)

    def wires_and_arrows(self):
        """Wire from CR101's coil pin across to an arrow on sheet 1, carried on to sheet 2
        by a destination arrow, landing on a contact there."""
        self.relay()
        a1 = dict(self.coil.pin_points())
        pin, q = sorted(a1.items())[-1]
        with self.p.edit("w1") as ed:
            self.w1 = ed.add(self.s1, M.Wire([q, (q[0] + 3.0, q[1])]))
        end = (q[0] + 3.0, q[1])
        self.src = self.place(self.s1, "Source arrow", end)
        q2 = dict(self.nc.pin_points())
        pin2, p2 = sorted(q2.items())[0]
        with self.p.edit("w2") as ed:
            self.w2 = ed.add(self.s2, M.Wire([(p2[0] - 3.0, p2[1]), p2]))
        self.dst = self.place(self.s2, "Destination arrow", (p2[0] - 3.0, p2[1]), "")
        return pin, pin2

    def test_a_wire_across_sheets(self):
        pin, pin2 = self.wires_and_arrows()
        num = self.s1.entities[self.w1.id].num
        self.assertTrue(num)
        self.assertEqual(self.s2.entities[self.w2.id].num, num)    # (carried on)
        self.select(self.s2, self.s2.entities[self.w2.id])
        self.trace()
        self.assertEqual(self.win.trace_panel.header.text(), "Wire %s — 6 places" % num)
        got = [(r.sheet_id, r.role, r.name) for r in self.rows()]
        self.assertEqual(sorted(got), sorted([
            (self.s1.id, "Wire", num), (self.s1.id, "Coil", "%s pin %s" % (self.tag, pin)),
            (self.s1.id, "Source arrow", self.src.attrs["TAG"]),
            (self.s2.id, "Wire", num), (self.s2.id, "NC contact", "%s pin %s" % (self.tag, pin2)),
            (self.s2.id, "Destination arrow", self.dst.attrs["TAG"])]))
        self.assertEqual(self.rows()[0].role, "Wire")       # (its wire first on its sheet)
        arrow = [r for r in self.rows() if r.role == "Source arrow"][0]
        self.assertEqual(arrow.desc, "to " + self.p.zone_text(self.s2, *self.dst.pos))
        # (the arrow picked: its wire's places)
        self.select(self.s1, self.s1.entities[self.src.id])
        self.trace()
        self.assertEqual(len(self.rows()), 6)

    def test_another_wire_given_the_same_number(self):
        self.wires_and_arrows()
        num = self.s1.entities[self.w1.id].num
        with self.p.edit("w3") as ed:
            w1 = self.s1.entities[self.w1.id]
            ed.change(self.s1, w1.copy(num=num, num_lock=True))
            w3 = ed.add(self.s2, M.Wire([(1.0, 1.0), (4.0, 1.0)], num=num, num_lock=True))
        self.assertEqual(self.s2.entities[w3.id].num, num)
        self.select(self.s1, self.s1.entities[self.w1.id])
        self.trace()
        self.assertIn((self.s2.id, (w3.id,)), [(r.sheet_id, r.ids) for r in self.rows()])

    def test_a_plc_point(self):
        mod = self.place(self.s1, "1734-IB8 module", (8, 9))
        with self.p.edit("slot") as ed:
            ed.change(self.s1, mod.copy(attrs=dict(mod.attrs, SLOT="3")))
        pins = dict(mod.pin_points())
        q = pins["2"]
        pb = self.place(self.s1, "Pushbutton NO", (q[0] - 4.0, q[1]))
        pq = sorted(pb.pin_points(), key=lambda t: -t[1][0])[0]
        with self.p.edit("w") as ed:
            ed.add(self.s1, M.Wire([pq[1], q]))
        num = [w.num for w in self.s1.wires()][0]
        # the point under the cursor, nothing selected
        self.v.set_selection(set())
        self.v.cursor = q
        self.assertTrue(self.trace())
        self.assertEqual(self.win.trace_panel.header.text(),
                         "PLC input I:3/2 — 3 places")
        rows = self.rows()
        self.assertEqual((rows[0].role, rows[0].name), ("PLC input", "%s pin 2" %
                                                        mod.attrs["TAG"]))
        self.assertIn("I:3/2", rows[0].desc)
        self.assertIn("wire " + num, rows[0].desc)
        self.assertEqual({r.role for r in rows}, {"PLC input", "Wire", "Device"})
        # the module selected: itself and its wired point
        self.select(self.s1, self.s1.entities[mod.id])
        self.trace()
        self.assertEqual([r.role for r in self.rows()], ["PLC module", "PLC input"])
        # the wire: lands on the pushbutton and the PLC input
        self.select(self.s1, self.s1.wires()[0])
        self.trace()
        self.assertIn(("PLC input", "%s pin 2" % mod.attrs["TAG"]),
                      [(r.role, r.name) for r in self.rows()])

    def test_the_io_list_text_beside_a_point(self):
        mod = self.place(self.s1, "1734-IB8 module", (8, 9))
        q = dict(mod.pin_points())["0"]
        with self.p.edit("w") as ed:
            ed.layer("PLC I/O", None, M.Layer("PLC I/O").to_dict())
            ed.add(self.s1, M.Text((q[0] - 0.15, q[1] + 0.03), "I:5/0  PB101  START", 0.08,
                                   0.0, "right", layer="PLC I/O"))
            ed.add(self.s1, M.Wire([(q[0] - 3.0, q[1]), q]))
        self.v.cursor = q
        self.trace()
        self.assertIn("PB101  START", self.rows()[0].desc)

    # ---- going there ------------------------------------------------------------------------
    def test_going_to_a_row(self):
        self.relay()
        self.select(self.s1, self.coil)
        self.trace()
        r = [x for x in self.rows() if x.role == "NC contact"][0]
        self.v.scale = 0.5                              # (zoomed far out)
        self.assertTrue(self.win.trace_go(r))
        self.assertEqual(self.v.sheet_id, self.s2.id)
        self.assertEqual(self.v.sel, {self.nc.id})
        bb = self.nc.bbox()
        self.assertAlmostEqual(self.v.center[0], (bb[0] + bb[2]) / 2)
        self.assertAlmostEqual(self.v.center[1], (bb[1] + bb[3]) / 2)
        self.assertGreater(self.v.scale, 40)            # (close enough to read)
        # (the list stays: going to a contact doesn't list it again)
        self.assertEqual(len(self.rows()), 4)

    def test_enter_and_double_click(self):
        self.relay()
        self.select(self.s1, self.coil)
        self.trace()
        t = self.win.trace_panel.table
        self.assertTrue(t.hasFocus() or not self.win.isActiveWindow())
        t.setCurrentItem(t.topLevelItem(0))
        QTest.keyClick(t, Qt.Key_Down)
        QTest.keyClick(t, Qt.Key_Down)
        QTest.keyClick(t, Qt.Key_Return)
        self.assertEqual((self.v.sheet_id, self.v.sel), (self.s2.id, {self.nc.id}))
        it = t.topLevelItem(3)
        t.itemDoubleClicked.emit(it, 0)
        self.assertEqual((self.v.sheet_id, self.v.sel), (self.panel.id, {self.fp.id}))

    def test_an_erased_object_is_said_and_listed_again(self):
        self.relay()
        self.select(self.s1, self.coil)
        self.trace()
        r = [x for x in self.rows() if x.role == "NC contact"][0]
        with self.p.edit("erase") as ed:
            ed.remove(self.s2, self.nc.id)
        self.assertFalse(self.win.trace_go(r))
        self.settle()
        self.assertIn("isn't there any more", self.win.cmdline.history.toPlainText())
        self.assertEqual(len(self.rows()), 3)
        self.assertNotEqual(self.v.sheet_id, self.s2.id)
        # the device itself erased: nothing to list, and said so
        with self.p.edit("erase") as ed:
            for e in list(self.s1.inserts()):
                ed.remove(self.s1, e.id)
            ed.remove(self.panel, self.fp.id)
        self.win._trace_refresh()
        self.settle()
        self.assertEqual(self.rows(), [])
        self.assertIn("no longer in the project", self.win.trace_panel.header.text())

    def test_nothing_to_list(self):
        with self.p.edit("line") as ed:
            ln = ed.add(self.s1, M.Line((1, 1), (2, 2)))
        self.select(self.s1, ln)
        self.assertFalse(self.trace())
        self.assertTrue(self.win.trace_dock.isVisible())
        self.assertEqual(self.rows(), [])
        self.assertTrue(self.win.trace_panel.header.text().startswith("Select a device"))

    # ---- the panel --------------------------------------------------------------------------
    def test_ctrl_e_from_the_drawing(self):
        a = self.win.acts["trace"]
        self.assertEqual([s.toString() for s in a.shortcuts()], ["Ctrl+E"])
        others = [k for k, x in self.win.acts.items() if x is not a and
                  any(s.toString() == "Ctrl+E" for s in x.shortcuts())]
        self.assertEqual(others, [])
        self.assertEqual(a.text(), WU.NAME)
        self.relay()
        self.select(self.s1, self.coil)
        self.win.activateWindow()
        self.v.setFocus()
        QTest.keyClick(self.v, Qt.Key_E, Qt.ControlModifier)
        self.settle()
        self.assertTrue(self.win.trace_dock.isVisible())
        self.assertEqual(len(self.rows()), 4)

    def test_it_follows_the_selection_only_while_open(self):
        self.relay()
        calls = []
        real = WU.Trace.__init__

        def counted(job, project, subject):
            calls.append(subject)
            real(job, project, subject)
        WU.Trace.__init__ = counted
        try:
            self.select(self.s1, self.coil)
            self.assertEqual(calls, [])                 # (closed: nothing done)
            self.trace()
            self.select(self.s1, self.no)               # (the same device: kept as it is)
            n = len(calls)
            with self.p.edit("w") as ed:
                w = ed.add(self.s1, M.Wire([(1.0, 2.0), (4.0, 2.0)]))
            self.settle()
            n = len(calls)
            # (several picks in a row: only the last one looked up)
            self.v.set_selection({self.coil.id})
            self.v.set_selection({w.id})
            self.settle()
            self.assertEqual(len(calls), n + 1)
            self.assertEqual(calls[-1][0], "wire")
            self.assertEqual(self.rows()[0].role, "Wire")
            self.v.set_selection(set())                 # (nothing: the list stays)
            self.settle()
            self.assertEqual(self.rows()[0].role, "Wire")
            self.win.trace_dock.close()
            n = len(calls)
            self.select(self.s1, self.coil)
            self.assertEqual(len(calls), n)
            self.assertFalse(self.win.trace_busy())
        finally:
            WU.Trace.__init__ = real

    def test_each_sheet_indexed_again_only_when_it_changed(self):
        self.relay()
        made = []
        real = WU.SheetIndex.__init__

        def counted(ix):
            made.append(ix)
            real(ix)
        WU.SheetIndex.__init__ = counted
        try:
            for i in range(5):                          # (edits, the panel closed)
                with self.p.edit("w") as ed:
                    ed.add(self.s1, M.Line((1, i), (2, i)))
            APP.processEvents()
            self.assertEqual(made, [])
            self.select(self.s1, self.coil)
            self.trace()
            self.assertEqual(len(made), 3)              # (each sheet once)
            self.select(self.s1, self.no)
            self.select(self.s2, self.nc)
            self.assertEqual(len(made), 3)
            with self.p.edit("w") as ed:                # (one sheet changed: it alone)
                ed.add(self.s2, M.Line((1, 1), (2, 2)))
            self.settle()
            self.assertEqual(len(made), 4)
            self.assertEqual(len(self.rows()), 4)
        finally:
            WU.SheetIndex.__init__ = real

    def test_a_click_never_waits_for_the_lookup(self):
        # (the owner: "make sure that the loading of the cross-references doesn't prevent any
        # interaction with the sheet itself"): one small step a turn of the event loop
        from kanzonascad import trace_panel
        self.relay()
        with self.p.edit("lines") as ed:
            for i in range(300):
                ed.add(self.s2, M.Line((1, i * 0.01), (2, i * 0.01)))
        self.trace()
        self.v.set_selection(set())
        for s in self.p.sheets:
            s.__dict__.pop("_trace_index", None)
        slices = (trace_panel.SLICE, WU.SLICE)
        trace_panel.SLICE, WU.SLICE = 0.0, 10
        try:
            self.v.show_sheet(self.s1.id)
            self.v.set_selection({self.coil.id})
            # the click handled: nothing looked up yet, nothing indexed
            self.assertIsNone(self.win._trace_job)
            self.assertTrue(self.win._trace_wait.isActive())
            self.assertFalse(any(hasattr(s, "_trace_index") for s in self.p.sheets))
            self.win._trace_wait.stop()
            self.win._trace_picked()
            self.assertTrue(self.win.trace_panel.header.text().startswith("Tracing"))
            self.win._trace_work()
            job = self.win._trace_job
            self.assertIsNotNone(job)
            self.assertFalse(job.done)
            self.assertFalse(hasattr(self.s2, "_trace_index"))
            # the drawing goes on meanwhile: selecting, drawing
            self.v.set_selection({self.no.id})
            self.v.repaint()
            self.win._trace_wait.stop()
            steps = 0
            while self.win._trace_job is not None:
                self.win._trace_work()
                steps += 1
            self.assertGreater(steps, 5)
            self.assertEqual(len(self.rows()), 4)
            self.assertTrue(self.win.trace_panel.header.text().endswith("4 places"))
        finally:
            trace_panel.SLICE, WU.SLICE = slices

    def test_a_wire_with_no_number_is_looked_up_a_sheet_at_a_time(self):
        # (wire numbers off: the wires joined to it across the project. Each sheet's part is
        # worked out in a step of its own before they are put together, so the whole
        # project isn't worked out in one go on a turn of the event loop; 127 ms on 50 sheets
        # of 200 wires before)
        from kanzonascad import wirenums
        with self.p.edit("wires") as ed:
            ed.project_settings({"wire_numbers": False})
            for s in (self.s1, self.s2):
                for i in range(5):
                    ed.add(s, M.Wire([(1.0, 1.0 + i), (4.0, 1.0 + i)]))
        w = next(iter(self.s1.wires()))
        self.assertFalse(w.num)
        for s in self.p.sheets:
            s.__dict__.pop("_num_summary", None)
        seen = []
        real = wirenums.groups

        def watched(project):
            seen.append([hasattr(s, "_num_summary") for s in project.sheets])
            return real(project)
        try:
            wirenums.groups = watched
            self.v.show_sheet(self.s1.id)
            self.v.set_selection({w.id})
            self.trace()
        finally:
            wirenums.groups = real
        self.assertEqual(seen, [[True, True]])
        self.assertEqual(len(self.rows()), 1)

    def test_many_rows_go_in_a_batch_at_a_time(self):
        from kanzonascad import trace_panel
        self.relay()
        no = self.lib.get("symbol", "Contact NO")
        with self.p.edit("many") as ed:
            for i in range(450):
                ed.add(self.s2, M.Insert(no.name, (1 + (i % 30) * 0.5, 1 + (i // 30) * 0.3),
                                         defn=no, attrs={"TAG": self.tag,
                                                         "PARENT": self.coil.attrs["DEV"]}))
        self.select(self.s1, self.coil)
        self.win.trace_dock.show()
        self.win._trace_begin(self.p, ("device", self.coil.attrs["DEV"], self.tag))
        counts = []
        while self.win._trace_job is not None:
            self.win._trace_work()
            counts.append(self.win.trace_panel.table.topLevelItemCount())
        self.assertEqual(counts[-1], 454)
        self.assertTrue(all(b - a <= trace_panel.ROWS_AT_ONCE
                            for a, b in zip([0] + counts, counts)), counts)

    def test_docked_left_right_or_bottom_and_put_back(self):
        d = self.win.trace_dock
        for area in (Qt.LeftDockWidgetArea, Qt.RightDockWidgetArea, Qt.BottomDockWidgetArea):
            self.assertTrue(d.isAreaAllowed(area))
        self.assertFalse(d.isAreaAllowed(Qt.TopDockWidgetArea))
        self.assertEqual(self.win.dockWidgetArea(d), Qt.BottomDockWidgetArea)
        self.trace()
        self.win.resizeDocks([d], [300], Qt.Vertical)
        APP.processEvents()
        self.win.addDockWidget(Qt.RightDockWidgetArea, d)
        APP.processEvents()
        # (the command line keeps its own height, not the room the panel left)
        cmd = self.win.cmd_dock
        self.assertLess(cmd.height(), cmd.sizeHint().height() + 40)
        state = self.win.saveState()
        from kanzonascad.main_window import MainWindow
        w2 = MainWindow()
        try:
            w2.addDockWidget(Qt.BottomDockWidgetArea, w2.trace_dock)
            w2.trace_dock.hide()
            w2.restoreState(state)
            self.assertEqual(w2.dockWidgetArea(w2.trace_dock), Qt.RightDockWidgetArea)
            self.assertTrue(w2.trace_dock.isVisibleTo(w2))
        finally:
            w2.close()

    def test_speed_on_a_few_thousand(self):
        coil, no = self.lib.get("symbol", "Relay coil"), self.lib.get("symbol", "Contact NO")
        s = self.s1
        with self.p.edit("many") as ed:
            for i in range(1500):
                x, y = 1 + (i % 30) * 0.5, 1 + (i // 30) * 0.2
                ed.add(s, M.Insert(coil.name, (x, y), defn=coil,
                                   attrs={"TAG": "CR%d" % (1000 + i), "DEV": "d%d" % i,
                                          "TAG_LOCK": "1"}))
                ed.add(self.s2, M.Insert(no.name, (x, y), defn=no,
                                         attrs={"TAG": "CR%d" % (1000 + i), "PARENT": "d%d" % i}))
                ed.add(s, M.Wire([(x + 0.5, y), (x + 0.6, y)]))
        devs = [e for e in s.inserts() if e.attrs.get("DEV")]
        wires = list(s.wires())
        self.select(s, devs[0])
        t = time.perf_counter()
        self.trace()
        first = time.perf_counter() - t
        self.assertEqual(len(self.rows()), 2)
        clicks, whole = [], []
        for i in range(1, 26):
            for e in (devs[i * 40], wires[i * 40]):
                t = time.perf_counter()
                self.v.set_selection({e.id})
                clicks.append(time.perf_counter() - t)
                self.settle()
                whole.append(time.perf_counter() - t)
        self.assertEqual(self.rows()[0].ids, (wires[1000].id,))
        self.assertLess(first, 2.0, "the first lookup (the index made) took %.2f s" % first)
        self.assertLess(max(clicks), 0.03, "a click took %.1f ms" % (max(clicks) * 1000))
        self.assertLess(sum(whole) / len(whole), 0.5, "a pick listed in %.2f s" % (
            sum(whole) / len(whole)))


if __name__ == "__main__":
    unittest.main()
