"""Blocks' manufacturer, family and series; a library block's Properties...; Edit block...
(the block editor) and Save block; updating the copies placed in a project."""
import json
import os
import tempfile
import unittest
from unittest import mock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFormLayout, QMessageBox, QWidget

from tests.util import APP, window, type_in

from kanzonascad import block_editor as BE
from kanzonascad import commands as C
from kanzonascad import library_panel as LP
from kanzonascad import model as M
from kanzonascad.library import Library, Part


def _no_builtin(d):
    d = dict(d)
    d.pop("builtin", None)
    return d


def coil(name="Test coil", **kw):
    return M.BlockDef(name, "symbol", [M.Circle((0, 0), 0.125), M.Line((-0.25, 0), (-0.125, 0)),
                                       M.Line((0.125, 0), (0.25, 0))],
                      [{"name": "A1", "pos": (-0.25, 0)}, {"name": "A2", "pos": (0.25, 0)}],
                      (0, 0.2), 0.1, "Mine", "A coil", "parent", "", "CR", **kw)


class MakerFieldsTest(unittest.TestCase):
    def test_round_trip_and_old_files(self):
        b = coil(manufacturer="Allen-Bradley", family="ControlLogix", series="B")
        d = b.to_dict()
        self.assertEqual((d["manufacturer"], d["family"], d["series"]),
                         ("Allen-Bradley", "ControlLogix", "B"))
        again = M.BlockDef.from_dict(json.loads(json.dumps(d)))
        self.assertEqual((again.manufacturer, again.family, again.series),
                         ("Allen-Bradley", "ControlLogix", "B"))
        # an old block (no such keys) loads with them blank, and blank ones aren't written
        old = coil().to_dict()
        self.assertNotIn("manufacturer", old)
        blank = M.BlockDef.from_dict(old)
        self.assertEqual((blank.manufacturer, blank.family, blank.series), ("", "", ""))
        # the library file and a project keep them
        lib = Library(tempfile.mkdtemp())
        lib.save_block(b)
        self.assertEqual(Library(lib.folder).get("symbol", b.name).family, "ControlLogix")
        p = M.Project.new()
        with p.edit("block") as ed:
            ed.block(b)
        path = os.path.join(tempfile.mkdtemp(), "p.kzcad")
        p.save(path)
        self.assertEqual(M.Project.load(path).blocks[b.name].series, "B")

    def test_suggestions_follow_the_manufacturer(self):
        lib = Library(tempfile.mkdtemp())
        lib.save_block(coil("A", manufacturer="Allen-Bradley", family="ControlLogix",
                            series="B"))
        lib.save_block(coil("B", manufacturer="allen-bradley", family="PowerFlex 525"))
        lib.save_block(coil("C", manufacturer="Siemens", family="SIMATIC S7-1500",
                            series="V2"))
        lib.save_part(Part(manufacturer="Phoenix Contact", catalog="3044102"))
        self.assertEqual(lib.maker_values("manufacturer"),
                         ["Allen-Bradley", "Phoenix Contact", "Siemens"])
        self.assertEqual(lib.maker_values("family", "Allen-Bradley"),
                         ["ControlLogix", "PowerFlex 525"])
        self.assertEqual(lib.maker_values("family", "Siemens"), ["SIMATIC S7-1500"])
        self.assertEqual(lib.maker_values("family"),
                         ["ControlLogix", "PowerFlex 525", "SIMATIC S7-1500"])
        self.assertEqual(lib.maker_values("series", "Allen-Bradley", "ControlLogix"), ["B"])
        self.assertEqual(lib.maker_values("series", "Siemens", "ControlLogix"), [])
        # the dialog's lists follow what is typed
        holder = QWidget()
        form = QFormLayout(holder)
        asked = []
        boxes = LP.maker_fields(form, lib, None, asked.append)
        items = lambda box: [box.itemText(i) for i in range(box.count())]
        self.assertEqual(items(boxes["manufacturer"]),
                         ["Allen-Bradley", "Phoenix Contact", "Siemens"])
        boxes["manufacturer"].setEditText("Siemens")
        self.assertEqual(items(boxes["family"]), ["SIMATIC S7-1500"])
        boxes["family"].setEditText("SIMATIC S7-1500")
        self.assertEqual(items(boxes["series"]), ["V2"])
        self.assertTrue(boxes["series"].toolTip().startswith("The line or generation"))
        self.assertTrue(boxes["family"].lineEdit().placeholderText())
        # the "?" asks for the manual's section
        holder.findChild(QWidget, "maker_help").click()
        self.assertEqual(asked, [LP.MAKER_ANCHOR])
        holder.deleteLater()


class BlockWindowTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = False
        self.v.polar_on = self.v.ortho_on = False
        # a library of this test's own (built-in symbols changed here stay here)
        self.win.library.folder = tempfile.mkdtemp()
        self.lib = self.win.library
        self.questions = []
        self.answer = QMessageBox.Yes
        self._q = QMessageBox.question

        def question(_parent, title, text, *a, **k):
            self.questions.append(text)
            return self.answer
        QMessageBox.question = staticmethod(question)

    def tearDown(self):
        QMessageBox.question = self._q
        for i in range(self.win.tabs.count()):
            p = self.win.tabs.widget(i).project
            p.saved_at = len(p.undo_stack)
        self.win.library_dialog.hide()
        self.win.close()

    def place(self, defn, at, attrs=None):
        self.v.run(C.InsertCmd, defn, attrs or {})
        type_in(self.v, "%g,%g" % at)
        return max(self.v.sheet().inserts(), key=lambda e: e.id)

    def wire(self, a, b):
        with self.v.project.edit("wire") as ed:
            return ed.add(self.v.sheet(), M.Wire([a, b], layer="WIRES"))

    # ---- placing, the panel, New part ----------------------------------------------------
    def test_insert_fills_mfr(self):
        b = coil(manufacturer="Siemens", family="SIMATIC S7-1500")
        self.lib.save_block(b)
        ins = self.place(self.lib.get("symbol", b.name), (5, 5))
        self.assertEqual(ins.attrs["MFR"], "Siemens")
        # a part's own manufacturer wins
        ins2 = self.place(self.lib.get("symbol", b.name), (7, 5), {"MFR": "Rockwell"})
        self.assertEqual(ins2.attrs["MFR"], "Rockwell")
        # no manufacturer: nothing filled
        ins3 = self.place(self.lib.get("symbol", "Relay coil"), (9, 5))
        self.assertFalse(ins3.attrs.get("MFR"))

    def test_panel_search_filters_and_tooltip(self):
        self.lib.save_block(coil("AB in", manufacturer="Allen-Bradley", family="CompactLogix",
                                 series="A"))
        self.lib.save_block(coil("AB out", manufacturer="Allen-Bradley", family="ControlLogix"))
        self.lib.save_block(coil("S7 in", manufacturer="Siemens", family="SIMATIC S7-1500"))
        panel = self.win.library_panel
        panel.refresh()
        tree = panel.trees["symbol"]

        def shown():
            out = []
            for i in range(tree.topLevelItemCount()):
                top = tree.topLevelItem(i)
                out += [top.child(j).data(0, Qt.UserRole) for j in range(top.childCount())]
            return sorted(out)
        panel.search.setText("compactlogix")
        self.assertEqual(shown(), ["AB in"])
        panel.search.setText("siemens")
        self.assertEqual(shown(), ["S7 in"])
        panel.search.setText("")
        mf = panel.mfr_filter
        self.assertEqual([mf.itemText(i) for i in range(mf.count())],
                         ["All manufacturers", "Allen-Bradley", "Siemens"])
        mf.setCurrentIndex(mf.findData("Allen-Bradley"))
        self.assertEqual(shown(), ["AB in", "AB out"])
        ff = panel.family_filter
        self.assertEqual([ff.itemText(i) for i in range(ff.count())],
                         ["All families", "CompactLogix", "ControlLogix"])
        ff.setCurrentIndex(ff.findData("ControlLogix"))
        self.assertEqual(shown(), ["AB out"])
        mf.setCurrentIndex(0)
        ff.setCurrentIndex(0)
        self.assertGreater(len(shown()), 30)                # the built-in ones are back
        item = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())
                if tree.topLevelItem(i).text(0) == "Mine"][0].child(0)
        self.assertIn("Family: CompactLogix", item.toolTip(0))
        self.assertIn("Series: A", item.toolTip(0))

    def test_new_part_from_a_selected_block(self):
        self.lib.save_block(coil(manufacturer="Siemens"))
        panel = self.win.library_panel
        panel.refresh()
        tree = panel.trees["symbol"]
        panel.tabs.setCurrentIndex(0)
        tree.setCurrentItem(tree.findItems("Test coil", Qt.MatchExactly | Qt.MatchRecursive, 0)[0])
        got = {}
        with mock.patch.object(LP, "part_dialog",
                               lambda *a, **k: got.update(k) or None):
            panel.edit_part(new=True)
        self.assertEqual(got, {"symbol": "Test coil", "manufacturer": "Siemens"})

    def test_make_block_takes_the_fields_and_help_opens_the_manual(self):
        v = self.v
        with v.project.edit("draw") as ed:
            ids = {ed.add(v.sheet(), M.Circle((5, 5), 0.125)).id}
        v.set_selection(ids)
        self.win.ask_block_details = lambda ents: {
            "kind": "symbol", "name": "Made", "category": "", "description": "",
            "role": "device", "contact": "", "prefix": "X", "pin_names": [], "replace": True,
            "manufacturer": "Phoenix Contact", "family": "CLIPLINE", "series": ""}
        v.run(C.MakeBlockCmd)
        type_in(v, "5,5", "", "")
        b = self.lib.get("symbol", "Made")
        self.assertEqual((b.manufacturer, b.family, b.series), ("Phoenix Contact", "CLIPLINE",
                                                                ""))
        # the "?" anchor scrolls the manual to its section
        dlg = self.win.manual_dialog(LP.MAKER_ANCHOR)
        dlg.show()
        APP.processEvents()
        bar = dlg.browser.verticalScrollBar()
        self.assertGreater(bar.value(), 0)
        dlg.close()
        dlg.deleteLater()
        # the real dialog: three fields and a "?"
        seen = {}

        def look(dlg_self):
            seen["names"] = {w.objectName() for w in dlg_self.findChildren(QWidget)}
            return QDialog.Rejected
        with mock.patch.object(QDialog, "exec", look):
            self.assertIsNone(LP.block_details_dialog(self.win, self.lib, on_help=print))
        self.assertTrue({"maker_manufacturer", "maker_family", "maker_series",
                         "maker_help"} <= seen["names"])

    # ---- Properties... -------------------------------------------------------------------
    def test_properties_rename_relinks_parts_and_updates_copies(self):
        self.lib.save_block(coil())
        part = Part(manufacturer="AB", catalog="700-HA", symbol="Test coil")
        self.lib.save_part(part)
        ins = self.place(self.lib.get("symbol", "Test coil"), (5, 5), {"TAG": "CR7"})
        w = self.wire((5.25, 5), (7, 5))                   # on A2
        steps = len(self.v.project.undo_stack)

        def details(parent, library, kind_hint="symbol", defn=None, on_help=None):
            self.assertEqual(defn.name, "Test coil")
            return {"kind": "symbol", "name": "Ice cube relay", "category": "Relays",
                    "description": "Plug-in relay", "role": "parent", "contact": "",
                    "prefix": "CR", "wiring": "", "pin_names": ["13", "14"],
                    "manufacturer": "Allen-Bradley", "family": "700-HA", "series": "D"}
        with mock.patch.object(LP, "block_details_dialog", details):
            new = self.win.block_properties("symbol", "Test coil")
        self.assertEqual(new.name, "Ice cube relay")
        self.assertFalse(self.lib.has_own("symbol", "Test coil"))
        saved = self.lib.get("symbol", "Ice cube relay")
        self.assertEqual([p["name"] for p in saved.pins], ["13", "14"])
        self.assertEqual((saved.family, saved.series), ("700-HA", "D"))
        self.assertEqual(self.lib.part(part.id).symbol, "Ice cube relay")
        self.assertEqual(self.questions[-1], "Update the copy of Test coil in Untitled?")
        # the copy: renamed, its tag kept, its wire still on its pin; one step
        p = self.v.project
        cur = p.sheets[0].entities[ins.id]
        self.assertEqual((cur.block, cur.attrs["TAG"]), ("Ice cube relay", "CR7"))
        self.assertEqual([n for n, _q in cur.pin_points()], ["13", "14"])
        self.assertNotIn("Test coil", p.blocks)
        self.assertEqual(p.sheets[0].entities[w.id].points[0], (5.25, 5.0))
        self.assertEqual(len(p.undo_stack), steps + 1)
        p.undo()
        cur = p.sheets[0].entities[ins.id]
        self.assertEqual(cur.block, "Test coil")
        self.assertIs(cur.defn, p.blocks["Test coil"])
        self.assertNotIn("Ice cube relay", p.blocks)
        p.redo()
        self.assertEqual(p.sheets[0].entities[ins.id].block, "Ice cube relay")

    def test_properties_of_a_builtin_saves_your_own_copy(self):
        self.win.show_library(0)
        self.win.library_panel.search.setText("Relay coil")
        tree = self.win.library_panel.trees["symbol"]
        tree.setCurrentItem(tree.topLevelItem(0).child(0))
        details = lambda parent, library, kind_hint="symbol", defn=None, on_help=None: {
            "kind": "symbol", "name": defn.name, "category": defn.category,
            "description": defn.description, "role": defn.role, "contact": defn.contact,
            "prefix": defn.prefix, "wiring": defn.wiring,
            "pin_names": [p["name"] for p in defn.pins], "manufacturer": "Allen-Bradley",
            "family": "", "series": ""}
        with mock.patch.object(LP, "block_details_dialog", details):
            self.win.library_panel.b_props.click()
        self.assertTrue(self.lib.has_own("symbol", "Relay coil"))
        mine = self.lib.get("symbol", "Relay coil")
        self.assertFalse(mine.builtin)
        self.assertEqual(mine.manufacturer, "Allen-Bradley")
        self.assertEqual(self.questions, [])            # nothing placed: nothing to ask

    # ---- Edit block... -------------------------------------------------------------------
    def test_every_builtin_symbol_round_trips_exactly(self):
        syms, _bad = Library(tempfile.mkdtemp()).blocks("symbol")
        fp = M.BlockDef("VFD 10x15", "footprint",
                        [M.Polyline([(0, 0), (10, 0), (10, 15), (0, 15)], True),
                         M.Circle((5, 12.3), 0.1), M.Text((5, 7.1), "VFD", 0.5, align="center"),
                         M.Arc((1, 1), 0.3, 10, 200)], category="Drives",
                        manufacturer="Allen-Bradley", family="PowerFlex 525", series="A")
        for b in list(syms.values()) + [fp]:
            p, sess = BE.open_block(b)
            res = BE.to_block(p, sess)
            self.assertEqual(res.defn.to_dict(), _no_builtin(b.to_dict()), b.name)
            self.assertEqual(res.warnings, [], b.name)
        # and through the window: open, Save block, the library file is the block
        self.lib.save_block(fp)
        d = self.win.edit_block("footprint", "VFD 10x15")
        self.assertEqual(d.name(), "Block: VFD 10x15")
        self.assertEqual(self.win.tabs.tabText(self.win.tabs.currentIndex()), "Block: VFD 10x15")
        self.assertLess(d.view.sheet().scale, 1.0)              # big: a 1:N sheet
        self.assertTrue(self.win.acts["save_block"].isEnabled())
        self.assertTrue(self.win.acts["save"].isEnabled())
        self.win.acts["save_block"].trigger()
        with open(self.lib._path("footprint", "VFD 10x15"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), fp.to_dict())
        d.view.repaint()                                    # (the pin rings drawn)

    def test_edit_geometry_and_pins_then_save_and_update(self):
        self.lib.save_block(coil())
        a = self.place(self.lib.get("symbol", "Test coil"), (5, 5), {"TAG": "CR1"})
        b = self.place(self.lib.get("symbol", "Test coil"), (5, 8), {"TAG": "CR2"})
        w1 = self.wire((5.25, 5), (7, 5))                  # on a's A2: A2 moves
        w2 = self.wire((4.75, 5), (3, 5))                  # on a's A1: A1 is removed
        w3 = self.wire((5.25, 8), (7, 8))                  # on b's A2
        main = self.win.doc()
        p = main.project
        steps = len(p.undo_stack)
        # opened from the drawing's selection
        self.v.set_selection({a.id})
        d = self.win.edit_block()
        self.assertIsNot(d, main)
        bv = d.view
        bp = d.project
        sess = d.block_session
        s = bv.sheet()
        ox, oy = sess.offset
        self.assertFalse(bp.is_modified())
        self.assertTrue(self.win.acts["save_block"].isVisible())
        pins = {e.text: e for e in s.entities.values()
                if isinstance(e, M.Text) and e.layer == BE.LAYER_PINS}
        self.assertEqual(sorted(pins), ["A1", "A2"])
        self.assertEqual(pins["A2"].pos, (ox + 0.25, oy))
        # draw a line, move A2 out by 0.25, erase A1, add a pin X1 (a copy of A2's marker)
        with bp.edit("edit") as ed:
            ed.add(s, M.Line((ox + 0.25, oy), (ox + 0.5, oy)))
            ed.change(s, pins["A2"].copy(pos=[ox + 0.5, oy]))
            ed.remove(s, pins["A1"].id)
            ed.add(s, pins["A2"].copy(id=None, text="X1", pos=[ox, oy - 0.25]))
        self.assertTrue(bp.is_modified())
        self.assertTrue(self.win.save_block())
        saved = self.lib.get("symbol", "Test coil")
        self.assertEqual([(q["name"], q["pos"]) for q in saved.pins],
                         [("A2", (0.5, 0.0)), ("X1", (0.0, -0.25))])
        self.assertEqual(len(saved.entities), 4)
        self.assertEqual(saved.entities[-1].p2, (0.5, 0.0))
        self.assertFalse(bp.is_modified())
        self.assertEqual(self.questions[-1], "Update the 2 copies of Test coil in Untitled?")
        # the copies: one step; A2's wires stretched, A1's wire left where it was
        self.assertEqual(len(p.undo_stack), steps + 1)
        ents = p.sheets[0].entities
        self.assertEqual(ents[w1.id].points[0], (5.5, 5.0))
        self.assertEqual(ents[w3.id].points[0], (5.5, 8.0))
        self.assertEqual(ents[w2.id].points[0], (4.75, 5.0))
        self.assertEqual(ents[a.id].attrs["TAG"], "CR1")
        self.assertEqual([n for n, _q in ents[a.id].pin_points()], ["A2", "X1"])
        self.assertIn("1 wire(s) stay where they were",
                      self.win.cmdline.history.toPlainText())
        p.undo()
        ents = p.sheets[0].entities
        self.assertEqual(ents[w1.id].points[0], (5.25, 5.0))
        self.assertEqual([n for n, _q in ents[a.id].pin_points()], ["A1", "A2"])
        self.assertEqual(len(p.blocks["Test coil"].pins), 2)
        # saving again with nothing changed keeps the block as it is
        self.win.tabs.setCurrentWidget(d)
        self.answer = QMessageBox.No
        self.assertTrue(self.win.save_block())
        self.assertEqual(self.lib.get("symbol", "Test coil").to_dict(), saved.to_dict())

    def test_closing_an_edited_block_asks(self):
        d = self.win.edit_block("symbol", "Contact NO")
        s = d.view.sheet()
        with d.project.edit("x") as ed:
            ed.add(s, M.Line((0, 0), (1, 1)))
        self.answer = QMessageBox.Cancel
        self.assertFalse(self.win.close_tab(self.win.tabs.indexOf(d)))
        self.assertIn("Save the changes to the block Contact NO", self.questions[-1])
        self.answer = QMessageBox.Discard
        self.assertTrue(self.win.close_tab(self.win.tabs.indexOf(d)))
        self.assertFalse(self.lib.has_own("symbol", "Contact NO"))     # nothing saved
        # Edit block with nothing to edit says so (no dialog)
        self.v.set_selection(set())
        self.assertIsNone(self.win.edit_block())
        self.assertFalse(self.win.acts["save_block"].isEnabled())

    def test_editing_a_builtin_saves_your_own_copy(self):
        d = self.win.edit_block("symbol", "Pilot light")
        s = d.view.sheet()
        with d.project.edit("x") as ed:
            ed.add(s, M.Line((0, 0), (0.1, 0.1)))
        self.win.acts["save"].trigger()                     # (Save in a block's tab)
        self.assertTrue(self.lib.has_own("symbol", "Pilot light"))
        mine = self.lib.get("symbol", "Pilot light")
        self.assertFalse(mine.builtin)
        builtin = self.lib.builtins()["Pilot light"]
        self.assertEqual(len(mine.entities), len(builtin.entities) + 1)
        self.assertEqual(mine.pins, builtin.pins)


if __name__ == "__main__":
    unittest.main()
