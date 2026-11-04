import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import osnap as OS


class OsnapTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.snap_on = False
        self.v.polar_on = self.v.ortho_on = False
        self.p = self.v.project
        self.s = self.v.sheet()
        with self.p.edit("geometry") as ed:
            ed.add(self.s, M.Line((2, 2), (10, 2)))
            ed.add(self.s, M.Circle((6, 7), 1.0))
            ed.add(self.s, M.Polyline([(12, 2), (16, 2), (16, 6), (12, 6)], True))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def snap_at(self, x, y, modes=None):
        return self.v.object_snap((x, y), modes)

    def test_geometry(self):
        line = M.Line((0, 0), (10, 0))
        self.assertEqual(OS.nearest(line, (3, 2)), (3.0, 0.0))
        self.assertEqual(OS.perpendicular(line, (4, 5), (4, 0))[0], (4.0, 0.0))
        circle = M.Circle((0, 0), 1.0)
        t = OS.tangent(circle, (2, 0), (0.5, 0.9))[0]
        self.assertAlmostEqual(t[0], 0.5)
        self.assertAlmostEqual(t[1], 3 ** 0.5 / 2)
        self.assertEqual(OS.centroid([(0, 0), (4, 0), (4, 2), (0, 2)]), (2.0, 1.0))

    def test_modes_on_and_off(self):
        v = self.v
        v.run(C.LineCmd)
        self.assertEqual(self.snap_at(2.02, 2.01)[0], "end")
        v.osnap_modes = {"mid"}
        self.assertIsNone(self.snap_at(2.02, 2.01))
        self.assertEqual(self.snap_at(6.02, 2.0), ("mid", (6.0, 2.0)))
        v.osnap_modes = {"gcen"}
        self.assertEqual(self.snap_at(14.02, 4.01), ("gcen", (14.0, 4.0)))
        v.osnap_modes = {"near"}
        k, q = self.snap_at(4.3, 2.02)
        self.assertEqual((k, q), ("near", (4.3, 2.0)))
        v.osnap_on = False                              # F3 off: none
        self.assertIsNone(self.snap_at(4.3, 2.02))

    def test_perpendicular_and_tangent_from_the_line_start(self):
        v = self.v
        v.osnap_modes = {"perp", "tan"}
        v.run(C.LineCmd)
        type_in(v, "4,5")                               # the line starts here
        self.assertEqual(self.snap_at(4.01, 2.02), ("perp", (4.0, 2.0)))
        k, q = self.snap_at(5.1, 7.4)                   # near the circle's upper-left
        self.assertEqual(k, "tan")
        self.assertAlmostEqual(((q[0] - 6) ** 2 + (q[1] - 7) ** 2) ** 0.5, 1.0)

    def test_typed_override_is_for_one_point(self):
        v = self.v
        v.osnap_modes = {"end"}
        v.run(C.LineCmd)
        type_in(v, "PER")                               # not ticked: used once anyway
        self.assertEqual(v.osnap_once, "perp")
        type_in(v, "4,5")                               # (typed point: no snap)
        self.assertIsNone(v.osnap_once)
        type_in(v, "nea")
        self.assertEqual(v.snap_modes(), {"near"})
        type_in(v, "NON")
        self.assertEqual(v.snap_modes(), set())
        v.cancel()

    def test_symbol_pins_are_nodes(self):
        coil = self.win.library.get("symbol", "Relay coil")
        with self.p.edit("coil") as ed:
            ed.block(coil)
            ins = ed.add(self.s, M.Insert(coil.name, (20, 5), defn=self.p.blocks[coil.name]))
        pin = dict(ins.pin_points())["A1"]
        self.v.run(C.LineCmd)
        self.assertEqual(self.snap_at(pin[0] + 0.01, pin[1]), ("node", pin))


if __name__ == "__main__":
    unittest.main()


class TrackingTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.snap_on = False
        self.v.polar_on = self.v.ortho_on = False
        self.p = self.v.project
        self.s = self.v.sheet()
        with self.p.edit("lines") as ed:
            ed.add(self.s, M.Line((2, 2), (6, 2)))           # its extension runs right
            ed.add(self.s, M.Line((2, 6), (4, 8)))           # slanted: for Parallel
            ed.add(self.s, M.Line((10, 4), (10, 9)))         # would meet the first at (10, 2)

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def hover(self, x, y):
        v = self.v
        v.cursor = (x, y)
        v.resolve(v.cursor)
        v._acquire()

    def test_extension(self):
        v = self.v
        v.osnap_modes = {"end", "ext"}
        v.run(C.LineCmd)
        self.hover(6.01, 2.0)                               # acquire the line's end
        self.assertEqual(len(v.tracked), 1)
        k, q = v.object_snap((8.0, 2.03))
        self.assertEqual((k, q), ("ext", (8.0, 2.0)))
        self.assertEqual(v.snap_from, (6.0, 2.0))

    def test_parallel(self):
        v = self.v
        v.osnap_modes = {"par"}
        v.run(C.LineCmd)
        type_in(v, "12,2")                                  # the line starts here
        self.hover(3.0, 7.01)                               # hover the slanted line
        self.assertEqual(len(v.par_dirs), 1)
        k, q = v.object_snap((15.02, 5.0))
        self.assertEqual(k, "par")
        self.assertAlmostEqual(q[0] - 12, q[1] - 2)         # 45 degrees, as the slanted line

    def test_apparent_intersection(self):
        v = self.v
        v.osnap_modes = {"app"}
        v.run(C.LineCmd)
        self.hover(4.0, 2.01)                               # hover the two lines first
        self.hover(10.01, 6.0)
        k, q = v.object_snap((10.02, 2.02))
        self.assertEqual(k, "app")
        self.assertAlmostEqual(q[0], 10.0)
        self.assertAlmostEqual(q[1], 2.0)

    def test_status_bar_snap_list(self):
        w = self.win
        w._fill_osnap_menu()
        acts = [a for a in w.osnap_menu.actions() if a.isCheckable()]
        self.assertEqual(len(acts), len(OS.MODES))
        nea = [a for a in acts if a.text().startswith("Nearest")][0]
        self.assertFalse(nea.isChecked())
        nea.setChecked(True)
        self.assertIn("near", self.v.osnap_modes)
        w._set_osnap_all(False)
        self.assertEqual(self.v.osnap_modes, set())
        w._set_osnap_all(True)
        self.assertEqual(len(self.v.osnap_modes), len(OS.MODES))
