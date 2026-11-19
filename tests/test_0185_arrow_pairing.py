"""Pairing an arrow with a chosen one (the owner, 0.18.5: "AutoCAD allows for specific ones,
but I have to tell it where it is, by either selecting it from a drop down or navigating to
the sheet and clicking on it")."""
import unittest

from PySide6.QtWidgets import QApplication

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import xrefs


class ArrowPairingTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.lib = self.win.library
        with self.p.edit("sheets") as ed:
            ed.add_sheet(self.p.make_sheet("Two"))
        self.s1, self.s2 = self.p.sheets
        with self.p.edit("w") as ed:
            for y in (5.0, 3.0):                         # (two sources, waiting)
                ed.add(self.s1, M.Wire([(2.0, y), (6.0, y)]))
            ed.add(self.s2, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
        for y in (5.0, 3.0):
            self.place(self.s1, "Source arrow", (6.0, y))
        self.srcs = sorted((e for e in self.s1.inserts()), key=lambda e: -e.pos[1])

    def tearDown(self):
        self.win.__dict__.pop("pick_connector", None)
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def place(self, sheet, name, at):
        self.v.show_sheet(sheet.id)
        self.v.run(C.InsertCmd, self.lib.get("symbol", name), {})
        type_in(self.v, "%g,%g" % at)

    def dest(self):
        return [e for e in self.s2.inserts() if e.defn.name == "Destination arrow"]

    def test_from_the_list(self):
        offered = []

        def pick(cands):
            offered.extend(c.attrs["TAG"] for _s, c in cands)
            return [(s, c) for s, c in cands if c.attrs["TAG"] == self.srcs[1].attrs["TAG"]][0]
        self.win.pick_connector = pick
        self.place(self.s2, "Destination arrow", (2.0, 5.0))
        self.assertIsNotNone(self.v.cmd)                    # (asking: a name, or pick one)
        type_in(self.v, C.PAIR_LIST)
        self.assertIsNone(self.v.cmd)
        self.assertEqual(sorted(offered), sorted(e.attrs["TAG"] for e in self.srcs))
        d = self.dest()
        self.assertEqual([e.attrs["TAG"] for e in d], [self.srcs[1].attrs["TAG"]])
        # (its text: that source's place only)
        t = [t for _x, _y, t, *_r in xrefs.live(self.p, self.s2) if "/" in t][0]
        where = self.p.zone_text(self.s1, *self.srcs[1].pos)
        self.assertTrue(t.endswith(where), (t, where))

    def test_picked_on_the_drawing(self):
        self.place(self.s2, "Destination arrow", (2.0, 5.0))
        type_in(self.v, C.PAIR_PICK)
        self.assertIsInstance(self.v.cmd, C.PickDeviceCmd)
        self.v.show_sheet(self.s1.id)                       # (go to the source's sheet)
        QApplication.processEvents()
        self.assertIsInstance(self.v.cmd, C.PickDeviceCmd)
        self.v.cmd.point(self.srcs[0].pos)                  # (click it)
        for _ in range(5):
            QApplication.processEvents()
        self.assertIs(self.v.sheet(), self.s2)              # (back where it was placed)
        self.assertEqual([e.attrs["TAG"] for e in self.dest()], [self.srcs[0].attrs["TAG"]])

    def test_typed_name_still_works(self):
        self.place(self.s2, "Destination arrow", (2.0, 5.0))
        type_in(self.v, "Q")
        self.assertEqual([e.attrs["TAG"] for e in self.dest()], ["Q"])


if __name__ == "__main__":
    unittest.main()
