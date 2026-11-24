"""Trace's button and Ctrl+E, and several things selected (0.23.2; the owner, Nov 2026: "Don't
toggle with ctrl e. That always opens or brings it to forefront. Only clicking the button
should toggle it", and with several selected, "Last one picked"): the Trace button on the
ribbon (Schematic and View > Panels) and View, Trace panel open and close the panel and show
checked while it is open; Ctrl+E only opens it or brings it to the front; the panel lists the
object picked last, a window's device nearest the top left of what it caught, and its header
says how many others are selected."""
import math
import unittest

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QDockWidget, QLabel, QToolButton

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import where_used as WU


def send(v, kind, pos, button, buttons, mods=Qt.NoModifier):
    """A mouse event as the system sends one (QTest's moves don't always carry the buttons)."""
    kinds = {"press": QEvent.MouseButtonPress, "move": QEvent.MouseMove,
             "release": QEvent.MouseButtonRelease}
    pos = QPointF(pos)
    APP.sendEvent(v, QMouseEvent(kinds[kind], pos, v.mapToGlobal(pos), button, buttons, mods))
    APP.processEvents()


class TraceToggleTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.s = self.p.sheets[0]
        self.win.trace_dock.hide()
        self.btn = self.win.acts["trace_panel"]

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    # ---- helpers ------------------------------------------------------------------------------
    def coils(self, *places):
        coil = self.win.library.get("symbol", "Relay coil")
        out = []
        with self.p.edit("coils") as ed:
            for i, at in enumerate(places):
                out.append(ed.add(self.s, M.Insert(coil.name, at, defn=coil, attrs={
                    "TAG": "CR%d" % (101 + i), "DEV": "d%d" % i, "TAG_LOCK": "1"})))
        self.v.zoom("sheet")
        APP.processEvents()
        return out

    def settle(self):
        for _i in range(5000):
            if not self.win.trace_busy():
                return
            QTest.qWait(2)
        self.fail("Trace never finished")

    def head(self):
        return self.win.trace_panel.header.text()

    def traced(self):
        sub = self.win._trace_subject
        return sub[1] if sub is not None else None

    def spot(self, e):
        """A pixel where a click picks e (and no grip of what is selected is there)."""
        bb = e.bbox()
        a, b = self.v.to_screen((bb[0], bb[3])), self.v.to_screen((bb[2], bb[1]))
        for i in range(1, 20):
            for j in range(1, 20):
                q = QPointF(a.x() + (b.x() - a.x()) * i / 20, a.y() + (b.y() - a.y()) * j / 20)
                # (not on a grip: Shift+click there picks the grip)
                if self.v.pick_entity(self.v.to_world(q)) is e and self.v.grip_at(q) is None:
                    return q
        self.fail("nowhere to click %r" % (e,))

    def click(self, e, mods=Qt.NoModifier):
        q = self.spot(e)
        send(self.v, "move", q, Qt.NoButton, Qt.NoButton, mods)
        send(self.v, "press", q, Qt.LeftButton, Qt.LeftButton, mods)
        send(self.v, "release", q, Qt.LeftButton, Qt.NoButton, mods)
        self.settle()

    def drag_window(self, a, b):
        """A window dragged from drawing point a to b, left to right (what is wholly inside)."""
        pa, pb = self.v.to_screen(a), self.v.to_screen(b)
        send(self.v, "move", pa, Qt.NoButton, Qt.NoButton)
        self.assertIsNone(self.v.pick_entity(a))
        send(self.v, "press", pa, Qt.LeftButton, Qt.LeftButton)
        for i in range(1, 13):
            q = QPointF(pa.x() + (pb.x() - pa.x()) * i / 12, pa.y() + (pb.y() - pa.y()) * i / 12)
            send(self.v, "move", q, Qt.NoButton, Qt.LeftButton)
        send(self.v, "release", pb, Qt.LeftButton, Qt.NoButton)
        self.settle()

    def ribbon_buttons(self):
        return [b for b in self.win.ribbon.findChildren(QToolButton)
                if b.defaultAction() is self.btn]

    def in_sight(self):
        d = self.win.trace_dock
        return d.isVisible() and not d.visibleRegion().isEmpty()

    # ---- the button ---------------------------------------------------------------------------
    def test_the_actions(self):
        key = self.win.acts["trace"]
        self.assertEqual([s.toString() for s in key.shortcuts()], ["Ctrl+E"])
        self.assertFalse(key.isCheckable())             # (Ctrl+E can't flip anything)
        self.assertTrue(self.btn.isCheckable())
        self.assertEqual(self.btn.shortcuts(), [])
        self.assertEqual(self.btn.iconText(), WU.NAME)
        self.assertIn(WU.NAME, self.btn.text())
        # (on the ribbon twice: Schematic's Cross-references and View's Panels)
        self.assertEqual(len(self.ribbon_buttons()), 2)
        view_menu = [a for a in self.win.menuBar().actions() if a.text() == "&View"][0].menu()
        self.assertIn(self.btn, view_menu.actions())

    def test_the_button_toggles_and_shows_checked(self):
        cr = self.coils((4, 7))[0]
        self.v.set_selection({cr.id})
        d = self.win.trace_dock
        self.assertFalse(self.btn.isChecked())
        for b in self.ribbon_buttons():
            self.assertFalse(b.isChecked())
        first, second = self.ribbon_buttons()
        first.click()
        self.settle()
        self.assertFalse(d.isHidden())
        self.assertTrue(self.in_sight())
        self.assertEqual(self.traced()[:2], ("device", "d0"))       # (filled, as Ctrl+E)
        self.assertTrue(self.head().startswith("CR101"), self.head())
        self.assertTrue(self.btn.isChecked())
        for b in self.ribbon_buttons():
            self.assertTrue(b.isChecked())
        second.click()                                  # (the other place: closes it)
        APP.processEvents()
        self.assertTrue(d.isHidden())
        self.assertFalse(self.btn.isChecked())
        for b in self.ribbon_buttons():
            self.assertFalse(b.isChecked())
        self.btn.trigger()                              # (View, Trace panel)
        self.settle()
        self.assertFalse(d.isHidden())
        self.assertTrue(self.btn.isChecked())
        self.btn.trigger()
        self.assertTrue(d.isHidden())
        self.assertFalse(self.btn.isChecked())

    def test_ctrl_e_as_a_key_never_closes(self):
        cr = self.coils((4, 7))[0]
        self.v.set_selection({cr.id})
        d = self.win.trace_dock
        self.win.activateWindow()
        for _i in range(3):
            self.v.setFocus()
            QTest.keyClick(self.v, Qt.Key_E, Qt.ControlModifier)
            self.settle()
            self.assertFalse(d.isHidden())
            self.assertTrue(self.in_sight())
            self.assertTrue(self.btn.isChecked())
        self.assertEqual(len(self.win.trace_panel.rows()), 1)
        self.assertTrue(self.win.trace_panel.table.hasFocus())   # (the rows take the keys)
        # (behind another panel's tab: Ctrl+E brings it to the front)
        other = self.tabbed_behind()
        self.v.setFocus()
        QTest.keyClick(self.v, Qt.Key_E, Qt.ControlModifier)
        self.settle()
        self.assertTrue(self.in_sight())
        self.assertTrue(other.visibleRegion().isEmpty())
        self.assertTrue(self.btn.isChecked())

    def tabbed_behind(self):
        """Another panel, tabbed with Trace's and in front of it."""
        other = QDockWidget("Other", self.win)
        other.setObjectName("other")
        other.setWidget(QLabel("other"))
        self.win.addDockWidget(Qt.BottomDockWidgetArea, other)
        self.addCleanup(self.win.removeDockWidget, other)
        self.win.tabifyDockWidget(self.win.trace_dock, other)
        other.show()
        other.raise_()
        APP.processEvents()
        self.assertFalse(self.win.trace_dock.isHidden())
        self.assertTrue(self.win.trace_dock.visibleRegion().isEmpty())
        self.assertFalse(other.visibleRegion().isEmpty())
        return other

    def test_a_panel_tabbed_behind_is_raised_not_closed(self):
        cr = self.coils((4, 7))[0]
        self.v.set_selection({cr.id})
        self.btn.trigger()
        self.settle()
        other = self.tabbed_behind()
        self.assertTrue(self.btn.isChecked())           # (still open, out of sight)
        self.assertFalse(self.win._trace_in_sight())
        self.ribbon_buttons()[0].click()
        self.settle()
        d = self.win.trace_dock
        self.assertFalse(d.isHidden())
        self.assertTrue(self.in_sight())
        self.assertTrue(other.visibleRegion().isEmpty())
        self.assertTrue(self.btn.isChecked())
        self.ribbon_buttons()[0].click()                # (now in sight: closed)
        APP.processEvents()
        self.assertTrue(d.isHidden())
        self.assertFalse(self.btn.isChecked())

    def test_its_x_unchecks_the_button(self):
        self.btn.trigger()
        self.settle()
        self.assertTrue(self.btn.isChecked())
        x = [b for b in self.win.trace_dock.findChildren(QAbstractButton)
             if b.objectName() == "qt_dockwidget_closebutton"]
        self.assertEqual(len(x), 1)
        x[0].click()
        APP.processEvents()
        self.assertTrue(self.win.trace_dock.isHidden())
        self.assertFalse(self.btn.isChecked())
        for b in self.ribbon_buttons():
            self.assertFalse(b.isChecked())

    def test_checked_from_the_window_state(self):
        # (KanzonasCAD started with the panel left open, and left closed: the button says so)
        from kanzonascad.main_window import MainWindow
        st = self.win.settings
        for open_ in (True, False):
            self.win.trace_dock.setVisible(open_)
            APP.processEvents()
            st.setValue("window_state", self.win.saveState())
            w2 = MainWindow()
            try:
                self.assertEqual(w2.trace_dock.isHidden(), not open_)
                self.assertEqual(w2.acts["trace_panel"].isChecked(), open_)
                w2.show()
                APP.processEvents()
                self.assertEqual(w2.acts["trace_panel"].isChecked(), open_)
            finally:
                w2.close()

    # ---- several selected ---------------------------------------------------------------------
    def test_the_last_one_clicked(self):
        a, b, c = self.coils((3, 8), (8, 8), (13, 8))
        self.btn.trigger()                              # (open: it follows the clicks)
        self.click(a)
        self.assertEqual(self.traced()[1], "d0")
        self.assertEqual(self.head(), "CR101 — 1 place")
        self.click(c)                                   # (a click adds to the selection)
        self.click(b)
        self.assertEqual(self.v.sel, {a.id, b.id, c.id})
        self.assertEqual(self.traced()[1], "d1")
        self.assertEqual(self.head(), "CR102 — 1 place (and 2 others selected)")
        # (the last one taken out, Shift+click: the one picked before it)
        self.click(b, Qt.ShiftModifier)
        self.assertEqual(self.v.sel, {a.id, c.id})
        self.assertEqual(self.traced()[1], "d2")
        self.assertEqual(self.head(), "CR103 — 1 place (and 1 other selected)")
        self.click(c, Qt.ShiftModifier)
        self.assertEqual(self.traced()[1], "d0")
        self.assertEqual(self.head(), "CR101 — 1 place")
        # (one picked earlier taken out: the last one stays, one fewer with it)
        self.click(b)
        self.click(c)
        self.click(a, Qt.ShiftModifier)
        self.assertEqual(self.traced()[1], "d2")
        self.assertEqual(self.head(), "CR103 — 1 place (and 1 other selected)")

    def test_ctrl_e_takes_the_last_one_too(self):
        a, b = self.coils((3, 8), (8, 8))
        self.v.set_selection({b.id})
        self.v.set_selection({a.id, b.id})
        self.assertTrue(self.win.trace())
        self.settle()
        self.assertEqual(self.traced()[1], "d0")
        self.assertTrue(self.head().endswith("(and 1 other selected)"), self.head())

    def test_a_window_the_device_nearest_its_top_left(self):
        # (made in this order so that the one wanted is neither the first made nor the
        # highest)
        far, b, c, a = self.coils((14, 2), (8, 8.5), (3, 4), (3, 8))
        with self.p.edit("wire") as ed:
            w = ed.add(self.s, M.Wire([(2.0, 9.6), (10.0, 9.6)]))
            ln = ed.add(self.s, M.Line((1.5, 9.8), (2.0, 9.8)))
        self.btn.trigger()
        self.click(far)
        self.drag_window((1.0, 10.0), (11.0, 3.0))
        caught = {a.id, b.id, c.id, w.id, ln.id}
        self.assertEqual(self.v.sel, caught | {far.id})
        # worked out here: the top left corner of what the window caught, and the device whose
        # own top left corner is nearest it (the wire and the line above them don't count as
        # devices, but they stretch the corner up and left)
        boxes = [self.s.entities[i].bbox() for i in caught]
        corner = (min(bb[0] for bb in boxes), max(bb[3] for bb in boxes))
        want = min((a, b, c), key=lambda e: math.hypot(e.bbox()[0] - corner[0],
                                                       e.bbox()[3] - corner[1]))
        self.assertIs(want, a)
        self.assertEqual(self.traced()[1], want.attrs["DEV"])
        self.assertEqual(self.head(), "CR104 — 1 place (and 5 others selected)")
        # (a window of wires and lines alone: its wire nearest the top left)
        self.v.set_selection(set())
        with self.p.edit("wires") as ed:
            w2 = ed.add(self.s, M.Wire([(5.0, 0.5), (9.0, 0.5)]))
            w3 = ed.add(self.s, M.Wire([(1.0, 1.2), (4.0, 1.2)]))
        self.drag_window((0.5, 2.0), (10.0, 0.2))
        self.assertEqual(self.v.sel, {w2.id, w3.id})
        self.assertEqual(self.traced()[0], "wire")
        self.assertEqual(self.traced()[3], w3.id)

    def test_devices_and_wires_before_anything_else(self):
        a, = self.coils((3, 8))
        with self.p.edit("box") as ed:
            box = ed.add(self.s, M.DashBox([(8, 3), (12, 3), (12, 6), (8, 6)], "note",
                                           attrs={"TAG": "BOX1"}))
        self.btn.trigger()
        self.click(a)
        self.click(box)                                 # (picked last, but only a box)
        self.assertEqual(self.v.sel, {a.id, box.id})
        self.assertEqual(self.traced()[1], "d0")
        self.assertEqual(self.head(), "CR101 — 1 place (and 1 other selected)")
        self.click(a, Qt.ShiftModifier)                 # (the box alone: it, then)
        self.assertEqual(self.traced(), ("tag", "BOX1"))

    def test_the_order_kept_is_the_selection_only(self):
        a, b, c = self.coils((3, 8), (8, 8), (13, 8))
        v = self.v
        v.set_selection({a.id})
        v.set_selection({a.id, b.id, c.id})
        self.assertEqual(v.pick_batches(), [sorted([b.id, c.id]), [a.id]])
        v.set_selection({a.id, c.id})
        self.assertEqual(v.pick_batches(), [[c.id], [a.id]])
        self.assertEqual(set(v._pick_seq), {a.id, c.id})     # (nothing kept of the rest)
        v.set_selection(set())
        self.assertEqual(v.pick_batches(), [])
        self.assertEqual(v._pick_seq, {})
        # (another sheet shown and this one again: the selection cleared; picked again, a
        # pick is as new as the click that made it, not as old as before)
        with self.p.edit("sheet") as ed:
            other = self.p.make_sheet("Other")
            ed.add_sheet(other)
        v.set_selection({a.id})
        v.set_selection({a.id, b.id})
        here = v.sheet_id
        v.show_sheet(other.id)
        v.show_sheet(here)
        self.assertEqual(v.sel, set())
        v.set_selection({a.id, b.id})                   # (both picked by this one change)
        self.assertEqual(v.pick_batches(), [sorted([a.id, b.id])])


if __name__ == "__main__":
    unittest.main()
