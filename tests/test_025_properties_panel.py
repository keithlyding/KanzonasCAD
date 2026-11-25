"""The Properties panel (0.25, Ctrl+1; the owner: "Can text properties be in the block panel, so
I don't have to right click it each time?", and "Everything of the selection"): a docked panel
that follows the selection (after a short wait, never in the click, nothing while closed),
shows each selected object's properties in groups, *varies* where several differ, and applies
a change at once as one step of Undo, through the attributes window's own code; it refreshes
after Undo, Redo and changes made elsewhere. Ctrl+1 opens or raises it, its button (View)
toggles it, and the window keeps its place and whether it is open."""
import time
import unittest

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QCheckBox, QDialog, QDoubleSpinBox, QGroupBox

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import props_panel as PP
from kanzonascad import tags


class Base(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p, self.s = self.v.project, self.v.sheet()
        lib = self.win.library
        self.coil = lib.get("symbol", "Relay coil")
        self.term = lib.get("symbol", "Terminal")
        self.fpdef = lib.get("footprint", "Breaker 1-pole (DIN)")
        with self.p.edit("blocks") as ed:
            for d in (self.coil, self.term, self.fpdef):
                ed.block(d)
        # (closed to start: a window closed with it open, in another test, keeps it open)
        self.win.props_dock.hide()

    def tearDown(self):
        for i in range(self.win.tabs.count()):
            d = self.win.tabs.widget(i)
            d.project.saved_at = len(d.project.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def add(self, defn, at, **kw):
        attrs = kw.pop("attrs", {})
        with self.p.edit("add") as ed:
            return ed.add(self.s, M.Insert(defn.name, at, defn=self.p.blocks[defn.name],
                                           attrs=attrs, **kw))

    def put(self, *ents):
        with self.p.edit("put") as ed:
            return [ed.add(self.s, e) for e in ents]

    def select(self, *ents):
        self.v.set_selection({e.id for e in ents})
        self.settle()

    def settle(self):
        for _i in range(500):
            if not self.win.props_busy():
                return
            QTest.qWait(5)
        self.fail("the panel never filled")

    def w(self, key):
        got = self.win.props_panel.widgets.get(key)
        self.assertIsNotNone(got, "no field %s: %s" % (key, sorted(self.win.props_panel.widgets)))
        return got

    def type(self, key, text):
        e = self.w(key)
        e.setFocus()
        e.selectAll()
        if text:
            QTest.keyClicks(e, text)
        else:
            QTest.keyClick(e, Qt.Key_Delete)
        QTest.keyClick(e, Qt.Key_Return)
        self.settle()

    def number(self, key, x):
        b = self.w(key)
        b.setFocus()
        b.lineEdit().selectAll()
        QTest.keyClicks(b.lineEdit(), ("%g" % x))
        QTest.keyClick(b, Qt.Key_Return)
        self.settle()

    def pick(self, key, text):
        c = self.w(key)
        i = c.findText(text)
        self.assertGreaterEqual(i, 0, "%s has no %s" % (key, text))
        c.setCurrentIndex(i)
        c.activated.emit(i)
        self.settle()

    def groups(self):
        body = self.win.props_panel.body
        return [g.title() for g in body.findChildren(QGroupBox)] if body is not None else []


class PanelTest(Base):
    def test_ctrl1_opens_and_the_button_toggles(self):
        dock, btn = self.win.props_dock, self.win.acts["props_panel"]
        self.assertTrue(dock.isHidden())
        self.assertEqual(self.win.acts["properties"].shortcut().toString(), "Ctrl+1")
        self.win.acts["properties"].trigger()
        self.assertFalse(dock.isHidden())
        self.assertTrue(btn.isChecked())
        self.win.acts["properties"].trigger()           # (Ctrl+1 again: still open)
        self.assertFalse(dock.isHidden())
        btn.trigger()                                    # (the button: closed)
        self.assertTrue(dock.isHidden())
        self.assertFalse(btn.isChecked())
        btn.trigger()
        self.assertFalse(dock.isHidden())
        # (behind another panel's tab: the button raises it rather than closing it)
        self.win.trace()
        self.win.tabifyDockWidget(self.win.trace_dock, dock)
        self.win.trace_dock.raise_()
        APP.processEvents()
        if dock.visibleRegion().isEmpty():
            btn.trigger()
            self.assertFalse(dock.isHidden())
            APP.processEvents()
            self.assertFalse(dock.visibleRegion().isEmpty())

    def test_kept_in_the_window_state(self):
        from kanzonascad.main_window import MainWindow
        self.win.properties()
        self.win.removeDockWidget(self.win.props_dock)
        self.win.addDockWidget(Qt.LeftDockWidgetArea, self.win.props_dock)
        self.win.props_dock.show()
        state = self.win.saveState()
        w2 = MainWindow()
        try:
            w2.props_dock.hide()
            self.assertTrue(w2.restoreState(state))
            self.assertFalse(w2.props_dock.isHidden())
            self.assertEqual(w2.dockWidgetArea(w2.props_dock), Qt.LeftDockWidgetArea)
        finally:
            w2.close()

    def test_follows_the_selection_after_the_click(self):
        c = self.add(self.coil, (5, 5), attrs={"TAG": "CR101", "DEV": "d1"})
        # (closed: nothing waits, nothing is filled)
        self.v.set_selection({c.id})
        self.assertFalse(self.win.props_busy())
        self.win.properties()
        self.v.set_selection(set())
        self.settle()
        t0 = time.perf_counter()
        self.v.set_selection({c.id})
        took = time.perf_counter() - t0
        # (the click only starts the wait: the panel still shows what it showed)
        self.assertTrue(self.win.props_busy())
        self.assertEqual(self.win.props_panel.header.text(), PP.HINT)
        self.settle()
        self.assertEqual(self.win.props_panel.header.text(), "Symbol (%s)" % self.coil.name)
        self.assertLess(took, 0.05)
        self.assertEqual(self.w("TAG").text(), "CR101")

    def test_symbol_fields(self):
        c = self.add(self.coil, (5, 5), attrs={"TAG": "CR101", "DEV": "d1"})
        self.win.properties()
        self.select(c)
        self.assertEqual(self.groups(), ["General", "Symbol", "Text lines"])
        self.type("TAG", "CR777")
        got = self.s.entities[c.id]
        self.assertEqual(got.attrs["TAG"], "CR777")
        self.assertEqual(got.attrs.get("TAG_LOCK"), "1")     # (typed: locked, as the window)
        self.assertEqual(self.p.undo_stack[-1].name, "Properties: Tag")
        self.type("DESC", "Run")
        self.type("LOC", "JB-2")
        self.assertEqual(self.s.entities[c.id].attrs["DESC"], "Run")
        self.assertEqual(self.s.entities[c.id].attrs["LOC"], "JB-2")
        self.type("LOC", "")
        self.assertNotIn("LOC", self.s.entities[c.id].attrs)
        self.w("shown_TAG").click()
        self.settle()
        self.assertIn("TAG", self.s.entities[c.id].hidden)
        self.number("angle_TAG", 90)
        self.assertAlmostEqual(self.s.entities[c.id].attr_angle("TAG"), 90.0)
        self.assertIsInstance(self.w("size_TAG"), PP._Info)     # (read only on a symbol)
        self.w("nofp").click()
        self.settle()
        self.assertEqual(self.s.entities[c.id].attrs.get("NO_FP"), "1")
        self.w("lock").click()
        self.settle()
        self.assertNotIn("TAG_LOCK", self.s.entities[c.id].attrs)

    def test_same_as_the_attributes_window(self):
        """A change made in the panel and the same one in the attributes window give the
        same object."""
        from kanzonascad import library_panel
        a = self.add(self.term, (5, 5), attrs={"TAG": "TB1", "TERM": "3"})
        b = self.add(self.term, (8, 5), attrs={"TAG": "TB1", "TERM": "3"})
        self.win.properties()
        self.select(a)
        self.type("attr_TERM", "12")
        self.number("angle_TERM", 90)
        real = library_panel.QDialog.exec

        def answer(dlg):
            from PySide6.QtWidgets import QLineEdit
            dlg.findChild(QLineEdit, "attr_TERM").setText("12")
            dlg.findChild(QDoubleSpinBox, "angle_TERM").setValue(90.0)
            return QDialog.Accepted
        library_panel.QDialog.exec = answer
        try:
            self.win.edit_attributes(self.s.entities[b.id])
        finally:
            library_panel.QDialog.exec = real
        da, db = self.s.entities[a.id].to_dict(), self.s.entities[b.id].to_dict()
        for d in (da, db):
            d.pop("id")
            d.pop("pos")
            # (the window writes its blank fields as "": the same as none)
            d["attrs"] = {k: x for k, x in d["attrs"].items() if x}
        self.assertEqual(da, db)

    def test_footprint_lines(self):
        f = self.add(self.fpdef, (5, 5), attrs={"TAG": "CB1"}, label="tag")
        self.win.properties()
        self.select(f)
        self.assertEqual(self.groups(), ["General", "Footprint", "Text lines"])
        self.type("label_size_TAG", "0.2")
        self.assertEqual(self.s.entities[f.id].label_sizes, {"TAG": 0.2})
        self.number("label_angle_TAG", 180)
        g = self.s.entities[f.id]
        self.assertAlmostEqual(g.attr_angle("@TAG"), 180.0)
        self.assertAlmostEqual(g.label_angle("tag"), 0.0)          # (kept readable)
        self.w("label_readable_TAG").click()
        self.settle()
        g = self.s.entities[f.id]
        self.assertIn("TAG", g.label_as_set)
        self.assertAlmostEqual(g.label_angle("tag"), 180.0)
        self.w("label_cat").click()
        self.settle()
        self.assertEqual(self.s.entities[f.id].label, "tag,cat")
        self.type("label_size_TAG", "")
        self.assertEqual(self.s.entities[f.id].label_sizes, {})
        # (a size that isn't one: said, nothing changed)
        n = len(self.p.undo_stack)
        self.type("label_size_TAG", "big")
        self.assertEqual(len(self.p.undo_stack), n)
        self.assertIn("Not a size", self.win.statusBar().currentMessage())

    def test_footprint_tag_links_its_device(self):
        c = self.add(self.coil, (2, 8), attrs={"TAG": "CR101", "DEV": "d1"})
        f = self.add(self.fpdef, (5, 5), attrs={"TAG": ""}, label="tag")
        self.win.properties()
        self.select(f)
        self.type("TAG", "CR101")
        self.assertEqual(self.s.entities[f.id].attrs.get("PARENT"), c.attrs["DEV"])

    def test_several_selected_varies_and_one_step(self):
        a = self.add(self.coil, (5, 5), attrs={"TAG": "CR101", "DEV": "d1", "DESC": "A"})
        b = self.add(self.coil, (8, 5), attrs={"TAG": "CR102", "DEV": "d2", "DESC": "B"})
        self.win.properties()
        self.select(a, b)
        self.assertEqual(self.win.props_panel.header.text(), "2 selected: 2 Symbol")
        desc = self.w("DESC")
        self.assertEqual(desc.text(), "")
        self.assertEqual(desc.placeholderText(), PP.VARIES)
        self.assertEqual(self.w("x").text(), PP.VARIES)
        self.assertEqual(self.w("y").value(), 5.0)                   # (the same: shown)
        n = len(self.p.undo_stack)
        self.type("DESC", "Both")
        self.assertEqual(len(self.p.undo_stack), n + 1)
        self.assertEqual([self.s.entities[e.id].attrs["DESC"] for e in (a, b)], ["Both"] * 2)
        self.assertEqual(self.w("DESC").text(), "Both")
        self.assertEqual(self.w("DESC").placeholderText(), "")
        self.p.undo()
        self.settle()
        self.assertEqual([self.s.entities[e.id].attrs["DESC"] for e in (a, b)], ["A", "B"])
        self.assertEqual(self.w("DESC").placeholderText(), PP.VARIES)
        self.p.redo()
        self.settle()
        self.assertEqual(self.w("DESC").text(), "Both")
        # (a tick that varies: half ticked; clicked, ticked on both)
        with self.p.edit("one") as ed:
            ed.change(self.s, self.s.entities[a.id].copy(attrs=dict(
                self.s.entities[a.id].attrs, NO_FP="1")))
        self.settle()
        self.assertEqual(self.w("nofp").checkState(), Qt.PartiallyChecked)
        self.w("nofp").click()
        self.settle()
        self.assertEqual([self.s.entities[e.id].attrs.get("NO_FP") for e in (a, b)], ["1"] * 2)
        # (a list that varies: *varies* first; picked, both)
        self.pick("layer", "0")
        with self.p.edit("one") as ed:
            ed.change(self.s, self.s.entities[a.id].copy(layer="SYMBOLS"))
        self.settle()
        self.assertEqual(self.w("layer").currentText(), PP.VARIES)
        self.pick("color", "Red")
        self.assertEqual({self.s.entities[e.id].color for e in (a, b)}, {"#ff0000"})

    def test_mixed_kinds_show_general_only(self):
        c = self.add(self.coil, (5, 5), attrs={"TAG": "CR101", "DEV": "d1"})
        w, t = self.put(M.Wire([(1, 1), (3, 1)]), M.Text((2, 3), "Hi", 0.125))
        self.win.properties()
        self.select(c, w, t)
        self.assertEqual(self.groups(), ["General"])
        self.assertEqual(sorted(self.win.props_panel.widgets), ["color", "kind", "layer"])
        self.pick("layer", "0")
        self.assertEqual({self.s.entities[e.id].layer for e in (c, w, t)}, {"0"})

    def test_wire_fields(self):
        w, w2 = self.put(M.Wire([(1, 1), (3, 1)]), M.Wire([(1, 4), (3, 4)]))
        self.win.properties()
        self.select(w)
        self.assertEqual(self.groups(), ["General", "Wire"])
        self.type("wire_num", "7001")
        g = self.s.entities[w.id]
        self.assertEqual((g.num, g.num_lock), ("7001", True))
        self.w("wire_lock").click()
        self.settle()
        self.assertFalse(self.s.entities[w.id].num_lock)
        self.type("gauge", "12")
        self.assertEqual(self.s.entities[w.id].awg, "12")
        n = len(self.p.undo_stack)
        self.type("gauge", "huge")
        self.assertEqual(len(self.p.undo_stack), n)
        self.assertEqual(self.s.entities[w.id].awg, "12")
        self.assertIn("Not a wire gauge", self.win.statusBar().currentMessage())
        self.pick("color_label", "Shown")
        self.assertIs(self.s.entities[w.id].show_color, True)
        self.pick("color_label", "As the project")
        self.assertIsNone(self.s.entities[w.id].show_color)
        # (two wires: the number read only, the gauge set on both)
        self.select(w, w2)
        self.assertIsInstance(self.w("wire_num"), PP._Info)
        self.type("gauge", "10")
        self.assertEqual({self.s.entities[e.id].awg for e in (w, w2)}, {"10"})

    def test_text_line_circle(self):
        t, ln, ci = self.put(M.Text((2, 3), "Hi", 0.125), M.Line((1, 1), (4, 1)),
                             M.Circle((8, 8), 0.5))
        self.win.properties()
        self.select(t)
        self.type("text", "Hello")
        self.number("height", 0.25)
        self.number("rotation", 90)
        g = self.s.entities[t.id]
        self.assertEqual((g.text, g.height, g.angle), ("Hello", 0.25, 90.0))
        self.number("x", 6)
        self.assertEqual(self.s.entities[t.id].pos, (6.0, 3.0))
        n = len(self.p.undo_stack)
        self.type("text", "")
        self.assertEqual(len(self.p.undo_stack), n)
        self.select(ln)
        self.assertEqual(self.w("length").value(), 3.0)
        self.number("length", 5)
        self.assertEqual(self.s.entities[ln.id].p2, (6.0, 1.0))
        self.number("line_angle", 90)
        g = self.s.entities[ln.id]
        self.assertAlmostEqual(g.p2[0], 1.0)
        self.assertAlmostEqual(g.p2[1], 6.0)
        self.select(ci)
        self.number("radius", 2)
        self.assertEqual(self.s.entities[ci.id].radius, 2.0)

    def test_refreshes_after_changes_elsewhere(self):
        c = self.add(self.coil, (5, 5), attrs={"TAG": "CR101", "DEV": "d1"})
        self.win.properties()
        self.select(c)
        with self.p.edit("elsewhere") as ed:
            ed.change(self.s, self.s.entities[c.id].copy(attrs=dict(c.attrs, DESC="Pump")))
        self.settle()
        self.assertEqual(self.w("DESC").text(), "Pump")
        self.p.undo()
        self.settle()
        self.assertEqual(self.w("DESC").text(), "")
        self.p.redo()
        self.settle()
        self.assertEqual(self.w("DESC").text(), "Pump")

    def test_symbol_moved_takes_its_wires(self):
        c = self.add(self.coil, (5, 5), attrs={"TAG": "CR101", "DEV": "d1"})
        pin = dict(c.pin_points())
        name, q = next(iter(pin.items()))
        w, = self.put(M.Wire([(q[0] - 2, q[1]), q]))
        self.win.properties()
        self.select(c)
        self.number("y", 6)
        moved = dict(self.s.entities[c.id].pin_points())[name]
        self.assertAlmostEqual(moved[1], q[1] + 1)
        ends = self.s.entities[w.id].points
        self.assertTrue(any(abs(p[0] - moved[0]) < 1e-9 and abs(p[1] - moved[1]) < 1e-9
                            for p in (ends[0], ends[-1])))

    def test_child_tag_is_its_devices(self):
        c = self.add(self.coil, (5, 5), attrs={"TAG": "CR101", "DEV": "d1"})
        no = self.win.library.get("symbol", "Contact NO")
        with self.p.edit("b") as ed:
            ed.block(no)
        k = self.add(no, (8, 5), attrs=tags.link_attrs({}, c))
        self.win.properties()
        self.select(k)
        self.assertNotIn("TAG", self.win.props_panel.widgets)
        self.assertEqual(self.w("parent").text(), "CR101")
        self.assertNotIn("nofp", self.win.props_panel.widgets)


if __name__ == "__main__":
    unittest.main()
