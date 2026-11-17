"""A footprint with the same name as a symbol already in the project (the owner, 0.18: "I
tried to insert a footprint with the same name as a schematic and it changed the footprint to
the schematic in a panel drawing. Can you prevent this?"): the project keeps each, the
footprint as "name (footprint)", and finds its library copy by its own name and kind."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import block_editor as BE
from kanzonascad import commands as C
from kanzonascad import model as M


def sym():
    return M.BlockDef("Same", "symbol", [M.Line((0, 0), (0.5, 0))],
                      pins=[{"name": "1", "pos": (0, 0)}, {"name": "2", "pos": (0.5, 0)}])


def fp():
    return M.BlockDef("Same", "footprint", [M.Polyline([(0, 0), (2, 0), (2, 3), (0, 3)], True)])


class SameNameKindsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.sch = self.v.sheet()
        self.v.run(C.InsertCmd, sym(), {})
        type_in(self.v, "3,3")
        while self.v.cmd is not None:
            self.v.cmd.enter()
        self.panel = self.p.make_sheet("Panel")
        self.panel.kind = "panel"
        with self.p.edit("panel") as ed:
            ed.add_sheet(self.panel, 1)
        self.v.show_sheet(self.panel.id)

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def place_fp(self):
        self.v.run(C.InsertCmd, fp(), {})
        type_in(self.v, "5,5")
        while self.v.cmd is not None:
            if not self.v.input_text("N"):
                self.v.cmd.enter()
        return self.panel.inserts()[0]

    def test_footprint_stays_a_footprint(self):
        e = self.place_fp()
        self.assertEqual(e.defn.kind, "footprint")
        self.assertEqual(e.block, "Same (footprint)")
        self.assertEqual(e.bbox()[2] - e.bbox()[0], 2.0)        # (its own drawing)
        s = self.sch.inserts()[0]
        self.assertEqual((s.block, s.defn.kind), ("Same", "symbol"))
        self.assertEqual(self.p.blocks["Same"].kind, "symbol")
        # a second one shares it
        self.v.run(C.InsertCmd, fp(), {})
        type_in(self.v, "9,5")
        while self.v.cmd is not None:
            if not self.v.input_text("N"):
                self.v.cmd.enter()
        self.assertEqual({x.block for x in self.panel.inserts()}, {"Same (footprint)"})
        # saved and opened again: both
        q = M.Project.from_dict(self.p.to_dict())
        self.assertEqual({(n, b.kind) for n, b in q.blocks.items() if n.startswith("Same")},
                         {("Same", "symbol"), ("Same (footprint)", "footprint")})

    def test_library_names(self):
        self.assertEqual(M.library_block_name("Same (footprint)", "footprint"), "Same")
        self.assertEqual(M.library_block_name("Same (footprint)", "symbol"), "Same (footprint)")
        self.assertEqual(M.project_block_name(self.p, "Same", "symbol"), "Same")
        self.assertEqual(M.project_block_name(self.p, "Same", "footprint"), "Same (footprint)")

    def test_paste_keeps_it_apart(self):
        e = self.place_fp()
        self.v.set_selection({e.id})
        self.win.copy_clip()
        self.win.paste()
        type_in(self.v, "12,5")
        kinds = {x.defn.kind for x in self.panel.inserts()}
        self.assertEqual(kinds, {"footprint"})
        self.assertEqual(len(self.panel.inserts()), 2)

    def test_updating_the_footprint_leaves_the_symbol(self):
        self.place_fp()
        new = fp()
        new.entities = [M.Polyline([(0, 0), (4, 0), (4, 3), (0, 3)], True)]
        from unittest import mock
        from PySide6.QtWidgets import QMessageBox
        with mock.patch.object(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes):
            self.win._offer_update(self.win.doc(), new, "Same", {})
        self.assertEqual(self.sch.inserts()[0].defn.kind, "symbol")
        e = self.panel.inserts()[0]
        self.assertEqual(e.bbox()[2] - e.bbox()[0], 4.0)        # (the footprint took it)
        self.assertEqual(BE.copies(self.p, "Same")[0][1].defn.kind, "symbol")


if __name__ == "__main__":
    unittest.main()
