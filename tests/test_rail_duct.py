import os
import tempfile
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import materials
from kanzonascad import model as M


class RailDuctTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = False
        self.p = self.v.project
        self.s = self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def runs(self):
        return sorted((e for e in self.s.entities.values() if isinstance(e, M.Run)),
                      key=lambda e: e.id)

    def test_draw_rail_with_a_profile_and_a_typed_length(self):
        self.v.run(C.RailCmd)
        type_in(self.v, "15", "2,2", "12,2")             # TS35 x 15, two clicks
        self.v.run(C.RailCmd)
        type_in(self.v, "mini", "2,4", "@18,0")
        r1, r2 = self.runs()
        self.assertEqual((r1.size, r1.length()), ("TS35x15", 10.0))
        self.assertAlmostEqual(r1.width, 35 / 25.4)
        self.assertAlmostEqual(r1.depth, 15 / 25.4)
        self.assertEqual((r2.size, r2.length()), ("TS15", 18.0))
        # stretched by its end grip; moved by its middle one
        self.assertEqual(r1.with_grip(2, (20, 2)).length(), 18.0)
        self.assertEqual(r1.with_grip(1, (7, 5)).p1, (2.0, 5.0))
        # real size: scaling makes it longer, its profile stays
        big = r1.scaled((2, 2), 2)
        self.assertEqual((big.length(), big.width), (20.0, r1.width))

    def test_draw_duct_typed_size_and_properties(self):
        self.v.run(C.DuctCmd)
        type_in(self.v, "50x75mm", "1,10", "1,40")
        d = self.runs()[0]
        self.assertAlmostEqual(d.width, 50 / 25.4)
        self.assertAlmostEqual(d.depth, 75 / 25.4)
        self.assertEqual(d.name(), "Wire duct 50 x 75 mm")
        self.assertEqual(self.p.settings["duct_size"], [50 / 25.4, 75 / 25.4])
        self.assertEqual(M.Duct((0, 0), (1, 0), "", 2, 3).name(), "Wire duct 2 x 3")
        self.assertEqual(C.parse_duct_size("1.5x3"), (1.5, 3.0))
        self.assertIsNone(C.parse_duct_size("big"))
        # saved and read back; drawn as plain lines in DXF
        again = M.Entity.from_dict(d.to_dict())
        self.assertEqual(again.to_dict(), d.to_dict())
        self.assertTrue(d.exploded() and not any(isinstance(e, M.Run) for e in d.exploded()))

    def test_materials_pack_cuts_into_stock_lengths(self):
        self.assertEqual(materials.pack([30, 30, 30], 72)[0], 2)          # 30+30, 30
        self.assertEqual(materials.pack([50, 40, 30, 20], 72)[0], 2)      # 50+20, 40+30
        self.assertEqual(materials.pack([100], 72)[0], 2)                 # longer than stock
        with self.p.edit("runs") as ed:
            for y, L in ((2, 30), (4, 30), (6, 30)):
                ed.add(self.s, M.Duct((0, y), (L, y), "", 2, 3))
            ed.add(self.s, M.Rail((0, 20), (20, 20), "TS35x7.5",
                                  *M.RAIL_PROFILES["TS35x7.5"][1:],
                                  attrs={"MFR": "Phoenix", "CAT": "1208131"}))
        rows = materials.rows(self.p)
        duct = [r for r in rows if r["item"] == "Wire duct"][0]
        self.assertEqual((len(duct["cuts"]), duct["total"], duct["sticks"]), (3, 90.0, 2))
        rail = [r for r in rows if r["item"] == "DIN rail"][0]
        self.assertEqual((rail["mfr"], rail["cat"], rail["sticks"]), ("Phoenix", "1208131", 1))
        path = os.path.join(tempfile.mkdtemp(), "m.csv")
        self.assertEqual(materials.write_csv(self.p, path), 2)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("Wire duct,2 x 3", text)
        self.assertIn('30.00""', text)                  # (the inch mark, CSV-quoted)


if __name__ == "__main__":
    unittest.main()
