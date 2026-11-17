"""The owner, 0.17.4: "Vfd symbol needs to have a ground connection on both sides as well.
Linear measurement is not following polar or ortho. I also need the measuring tool repeated in
home and schematic tabs please. Also when using extension, lines and wires needs to snap to
points on a crossing of a line or whatever."

- The drive has PE1 under L1-L3 and PE2 under T1-T3; its phases are still a side of three
  (a bus lands wire for wire), the grounds 3/4" on, out of that run.
- A linear dimension's points follow Ortho (an object snap still first).
- The dimension commands are on the Home and Schematic tabs too.
- Extension: where a tracking line (past a line's end, or across / up and down from a point)
  crosses a line, a wire or a circle snaps."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import osnap as OS


class VfdTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.s = self.v.sheet()

    def tearDown(self):
        self.v.project.saved_at = len(self.v.project.undo_stack)
        self.win.close()

    def test_grounds_on_both_sides_and_the_phases_still_a_side(self):
        d = self.win.library.get("symbol", "Variable frequency drive")
        names = [q["name"] for q in d.pins]
        self.assertEqual(names, ["L1", "L2", "L3", "T1", "T2", "T3", "PE1", "PE2"])
        self.v.run(C.InsertCmd, d, {})
        type_in(self.v, "5,5")
        while self.v.cmd is not None:
            self.v.cmd.enter()
        e = self.s.inserts()[-1]
        p = dict(e.pin_points())
        self.assertEqual(p["PE1"][0], p["L1"][0])                   # (the line side)
        self.assertEqual(p["PE2"][0], p["T1"][0])                   # (the load side)
        self.assertAlmostEqual(p["L3"][1] - p["PE1"][1], 0.75, 9)
        side, gap = C.pin_side(self.s, p["L2"])
        self.assertEqual(side, [p["L1"], p["L2"], p["L3"]])
        self.assertEqual(gap, 0.5)
        side, _gap = C.pin_side(self.s, p["T3"])
        self.assertEqual(side, [p["T1"], p["T2"], p["T3"]])        # (the longer run)


class DimsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.polar_on = False
        v.ortho_on = True
        self.s = v.sheet()

    def tearDown(self):
        self.v.project.saved_at = len(self.v.project.undo_stack)
        self.win.close()

    def test_the_second_point_follows_ortho(self):
        v = self.v
        v.run(C.DimLinearCmd)
        type_in(v, "2,2")
        # (the mouse a little off level: Ortho holds it level)
        self.assertEqual(v.resolve((6.0, 2.3)), (6.0, 2.0))
        v.cancel()

    def test_on_the_home_and_schematic_tabs(self):
        from PySide6.QtWidgets import QToolButton
        r, act = self.win.ribbon, self.win.acts["dim_linear"]
        found = {}
        for i in range(r.count()):
            found[r.tabText(i).replace("&", "")] = any(
                b.defaultAction() is act for b in r.widget(i).findChildren(QToolButton))
        self.assertTrue(found["Home"] and found["Schematic"] and found["Panel"], found)


class ExtensionTest(unittest.TestCase):
    def test_a_tracking_line_crossing_a_line_snaps(self):
        line = M.Line((5.0, 0.0), (5.0, 10.0))          # (up and down at x 5)
        circle = M.Circle((9.0, 3.0), 1.0)
        # past the end of a line running across from (1, 3) to (2, 3): its extension meets
        # x 5 at (5, 3), and the circle at (8, 3)
        got = OS.track_crossings([((2.0, 3.0), (1.0, 0.0))], [], [line, circle],
                                 (5.05, 3.04), 0.2)
        self.assertEqual([q for q, _q0 in got], [(5.0, 3.0)])
        got = OS.track_crossings([((2.0, 3.0), (1.0, 0.0))], [], [line, circle],
                                 (8.1, 3.0), 0.2)
        self.assertEqual([tuple(round(c, 9) for c in q) for q, _q0 in got], [(8.0, 3.0)])
        # behind the end: not an extension
        self.assertEqual(OS.track_crossings([((2.0, 3.0), (1.0, 0.0))], [],
                                            [M.Line((0.0, 0.0), (0.0, 9.0))], (0.0, 3.0),
                                            0.2), [])
        # across from an acquired point
        got = OS.track_crossings([], [(1.0, 7.0)], [line], (5.0, 7.1), 0.2)
        self.assertEqual([q for q, _q0 in got], [(5.0, 7.0)])

    def test_in_the_view(self):
        win, v = window()
        try:
            v.osnap_on, v.snap_on, v.ortho_on, v.polar_on = True, False, False, False
            v.osnap_modes = {"ext", "end"}
            s = v.sheet()
            with v.project.edit("x") as ed:
                ed.add(s, M.Line((1.0, 3.0), (2.0, 3.0)))
                ed.add(s, M.Line((5.0, 0.0), (5.0, 10.0)))
            v.center, v.scale = (4.0, 3.0), 100.0
            v.run(C.LineCmd)
            type_in(v, "7,8")                           # (not above the crossing: no
                                                        # Ortho-like line through it)
            v.cursor = (2.0, 3.0)                       # (hover the end: acquired)
            v.resolve((2.0, 3.0))
            v._acquire()
            self.assertTrue(v.tracked)
            self.assertEqual(v.resolve((5.03, 3.05)), (5.0, 3.0))
            v.cancel()
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()


if __name__ == "__main__":
    unittest.main()
