import os
import tempfile
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import fileio
from kanzonascad.library import Library, Part


class LibraryFilesTest(unittest.TestCase):
    def test_builtin_symbols_have_pins_and_load(self):
        lib = Library(tempfile.mkdtemp())
        syms, bad = lib.blocks("symbol")
        self.assertEqual(bad, [])
        self.assertGreaterEqual(len(syms), 25)
        coil = syms["Relay coil"]
        self.assertEqual([p["name"] for p in coil.pins], ["A1", "A2"])
        self.assertEqual((coil.role, coil.prefix), ("parent", "CR"))
        self.assertEqual(syms["Contact NC"].contact, "NC")
        for s in syms.values():                     # pins on the 1/8 inch snap
            for p in s.pins:
                for c in p["pos"]:
                    self.assertAlmostEqual(round(c / 0.03125) * 0.03125, c)

    def test_own_blocks_and_parts_last(self):
        folder = tempfile.mkdtemp()
        lib = Library(folder)
        fp = M.BlockDef("AB 100-C09", "footprint", [M.Polyline([(0, 0), (1.77, 0), (1.77, 3),
                                                                 (0, 3)], True)],
                        category="Contactors")
        lib.save_block(fp)
        mine = M.BlockDef("Relay coil", "symbol", [M.Circle((0, 0), 0.2)],
                          [{"name": "A1", "pos": (-0.25, 0)}])
        lib.save_block(mine)
        part = Part(manufacturer="Allen-Bradley", catalog="100-C09D10", description="Contactor",
                    symbol="Contactor coil", footprint="AB 100-C09")
        lib.save_part(part)
        again = Library(folder)                     # as on the next start
        self.assertIn("AB 100-C09", again.blocks("footprint")[0])
        self.assertEqual(again.get("symbol", "Relay coil").entities[0].radius, 0.2)  # yours wins
        self.assertEqual(again.part(part.id).catalog, "100-C09D10")
        self.assertEqual([p.id for p in again.parts_using("footprint", "AB 100-C09")], [part.id])
        again.delete_block("symbol", "Relay coil")
        self.assertTrue(again.get("symbol", "Relay coil").builtin)  # the built-in one is back


class UnitsTest(unittest.TestCase):
    def test_millimeters(self):
        self.assertAlmostEqual(C.parse_number("45mm"), 45 / 25.4)
        self.assertAlmostEqual(C.parse_number('2"'), 2.0)
        p = C.parse_point("@25.4mm,0", (1, 1))
        self.assertAlmostEqual(p[0], 2.0)


class BlockWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = False
        self.details = None
        self.win.ask_block_details = lambda ents: self.details

    def tearDown(self):
        for i in range(self.win.tabs.count()):
            p = self.win.tabs.widget(i).project
            p.saved_at = len(p.undo_stack)
        self.win.close()

    def draw_coil(self):
        v = self.v
        with v.project.edit("draw") as ed:
            a = ed.add(v.sheet(), M.Circle((5, 5), 0.125))
            b = ed.add(v.sheet(), M.Line((4.75, 5), (4.875, 5)))
            c = ed.add(v.sheet(), M.Line((5.125, 5), (5.25, 5)))
        return {a.id, b.id, c.id}

    def test_make_symbol_with_pins_then_insert_and_tag(self):
        v, w = self.v, self.win
        v.set_selection(self.draw_coil())
        self.details = {"kind": "symbol", "name": "My coil", "category": "Mine",
                        "description": "Coil", "role": "parent", "contact": "",
                        "prefix": "CR", "pin_names": ["A1", "A2"], "replace": True}
        v.run(C.MakeBlockCmd)
        type_in(v, "5,5", "4.75,5", "5.25,5", "", "5,5.25")
        ins = list(v.sheet().entities.values())
        self.assertEqual(len(ins), 1)
        ins = ins[0]
        self.assertIsInstance(ins, M.Insert)
        self.assertEqual([n for n, _p in ins.pin_points()], ["A1", "A2"])
        self.assertEqual(ins.pin_points()[0][1], (4.75, 5.0))
        saved = w.library.get("symbol", "My coil")
        self.assertEqual(saved.pins[1]["pos"], (0.25, 0.0))
        self.assertEqual(saved.tag_pos, (0.0, 0.25))
        self.assertEqual(saved.prefix, "CR")
        # place it again from the library, turned and flipped
        v.run(C.InsertCmd, saved, {"TAG": "CR601"})
        type_in(v, "R", "F", "8,4")
        new = [e for e in v.sheet().entities.values() if e.id != ins.id][0]
        self.assertEqual((new.angle, new.mirror, new.attrs["TAG"]), (90.0, True, "CR601"))
        self.assertEqual(new.layer, "SYMBOLS")
        texts = [t.text for t in new.world_entities() if t.kind == "text"]
        self.assertIn("CR601", texts)
        v.repaint()
        # undo takes the insert, then the block making, back
        v.project.undo()
        v.project.undo()
        self.assertEqual(len(v.sheet().entities), 3)
        self.assertNotIn("My coil", v.project.blocks)

    def test_footprint_scaled_to_real_size_by_reference(self):
        v = self.v
        with v.project.edit("draw") as ed:
            r = ed.add(v.sheet(), M.Polyline([(1, 1), (3, 1), (3, 4), (1, 4)], True))
        v.set_selection({r.id})
        v.run(C.ScaleCmd)
        type_in(v, "1,1", "R", "1,1", "3,1", "45mm")      # the 2" width is really 45 mm
        pts = v.sheet().entities[r.id].points
        self.assertAlmostEqual(pts[1][0] - pts[0][0], 45 / 25.4)
        self.assertAlmostEqual(pts[2][1] - pts[1][1], 3 * 45 / 25.4 / 2)
        v.set_selection({r.id})
        self.details = {"kind": "footprint", "name": "Contactor 45mm", "category": "Panel",
                        "description": "", "role": "device", "contact": "", "prefix": "",
                        "pin_names": [], "replace": True}
        v.run(C.MakeBlockCmd)
        type_in(v, "1,1")
        fp = self.win.library.get("footprint", "Contactor 45mm")
        self.assertEqual(fp.pins, [])
        self.assertAlmostEqual(fp.extents()[2], 45 / 25.4)

    def test_explode_copy_paste_save_and_dxf(self):
        v, w = self.v, self.win
        coil = w.library.get("symbol", "Relay coil")
        v.run(C.InsertCmd, coil, {"TAG": "CR601", "MFR": "AB"})
        type_in(v, "4,6")
        ins = list(v.sheet().entities.values())[0]
        # copy to a new project: the block definition comes along
        v.set_selection({ins.id})
        self.assertTrue(w.copy_clip())
        d2 = w.new_project()
        v2 = d2.view
        v2.osnap_on = v2.snap_on = False
        w.paste()
        type_in(v2, "2,2")
        pasted = list(v2.sheet().entities.values())[0]
        self.assertIsNotNone(pasted.defn)
        self.assertIn("Relay coil", v2.project.blocks)
        # saved and opened again, still drawn from the project's own copy
        path = os.path.join(tempfile.mkdtemp(), "p.kzcad")
        v2.project.save(path)
        q = M.Project.load(path)
        qi = list(q.sheets[0].entities.values())[0]
        self.assertIs(qi.defn, q.blocks["Relay coil"])
        # DXF out: the block goes out as its lines and its tag text
        dxf = os.path.join(tempfile.mkdtemp(), "p.dxf")
        fileio.export_dxf(q, q.sheets[0], dxf, include_frame=False)
        ents, _rep = fileio.read_dxf(dxf)
        self.assertIn("circle", [e.kind for e in ents])
        # pasted onto page 1 of the new project, the device's tag took that page: CR101
        self.assertIn("CR101", [e.text for e in ents if e.kind == "text"])
        # explode
        w.tabs.setCurrentIndex(0)
        v.set_selection({ins.id})
        v.run(C.ExplodeCmd)
        kinds = sorted(e.kind for e in v.sheet().entities.values())
        self.assertNotIn("insert", kinds)
        self.assertIn("circle", kinds)

    def test_library_panel_lists_and_inserts(self):
        w, v = self.win, self.v
        panel = w.library_panel
        panel.refresh()
        tree = panel.trees["symbol"]
        names = []
        for i in range(tree.topLevelItemCount()):
            top = tree.topLevelItem(i)
            names += [top.child(j).text(0) for j in range(top.childCount())]
        self.assertTrue(any(n.startswith("Pushbutton NO") for n in names))
        panel.search.setText("e-stop")
        panel.search.setText("emergency")
        self.assertEqual(sum(tree.topLevelItem(i).childCount()
                             for i in range(tree.topLevelItemCount())), 1)
        w.acts["insert_symbol"].trigger()
        self.assertTrue(w.library_dialog.isVisible())
        self.assertEqual(panel.tabs.currentIndex(), 0)
        item = tree.topLevelItem(0).child(0)          # (the popup refreshed the list)
        self.assertTrue(item.text(0).startswith("Emergency stop"))
        panel._insert_item("symbol", item)
        self.assertIsInstance(v.cmd, C.InsertCmd)
        self.assertFalse(w.library_dialog.isVisible())     # out of the way while placing
        v.cancel()
        w.acts["insert_footprint"].trigger()
        self.assertEqual(panel.tabs.currentIndex(), 1)
        w.library_dialog.hide()
