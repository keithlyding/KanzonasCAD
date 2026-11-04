import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wires


class WireToolsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = False
        self.v.polar_on = self.v.ortho_on = False
        self.p = self.v.project
        self.s = self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def add(self, *paths):
        with self.p.edit("wires") as ed:
            return [ed.add(self.s, M.Wire(list(pts))) for pts in paths]

    def paths(self):
        return sorted([tuple(map(tuple, w.points)) for w in self.s.wires()])

    def test_trim_wire_stops_at_the_nearest_wire_or_pin(self):
        # a rung from 1 to 11, crossed at 4 and 8 by wires up and down
        self.add([(1, 5), (11, 5)], [(4, 3), (4, 7)], [(8, 3), (8, 7)])
        self.v.run(C.TrimWireCmd)
        self.v.cmd.pick((6, 5))                         # the piece between the two crossings
        self.assertIn(((1.0, 5.0), (4.0, 5.0)), self.paths())
        self.assertIn(((8.0, 5.0), (11.0, 5.0)), self.paths())
        self.v.cmd.pick((10, 5))                        # nothing beyond 8: to the end
        self.assertNotIn(((8.0, 5.0), (11.0, 5.0)), self.paths())
        type_in(self.v, "U")                            # takes back the last one
        self.assertIn(((8.0, 5.0), (11.0, 5.0)), self.paths())
        self.v.cmd.enter()
        self.p.undo()
        self.assertIn(((1.0, 5.0), (11.0, 5.0)), self.paths())

    def test_trim_wire_stops_at_a_pin_and_joins_what_is_left(self):
        coil = self.win.library.get("symbol", "Relay coil")
        self.add([(1, 5), (11, 5)])
        self.v.run(C.InsertCmd, coil, {"TAG": "CR1"})
        type_in(self.v, "6,5")                          # cuts the rung at its pins
        ins = max(self.s.inserts(), key=lambda e: e.id)
        pins = sorted(q for _n, q in ins.pin_points())
        # trimming right of the coil takes the piece from its pin to the wire's end
        self.v.run(C.TrimWireCmd)
        self.v.cmd.pick((10, 5))
        right = [w for w in self.s.wires() if w.points[0][0] > 6 or w.points[-1][0] > 6]
        self.assertEqual(right, [])                     # the whole right piece went (pin to end)
        self.v.cmd.enter()
        self.assertTrue(any(abs(w.points[-1][0] - pins[0][0]) < 1e-9 or
                            abs(w.points[0][0] - pins[0][0]) < 1e-9 for w in self.s.wires()))

    def test_delete_wire_takes_only_wires_and_joins(self):
        a, b, c = self.add([(1, 5), (5, 5)], [(5, 5), (9, 5)], [(5, 5), (5, 8)])
        with self.p.edit("line") as ed:
            ln = ed.add(self.s, M.Line((0, 0), (1, 1)))
        self.v.set_selection({c.id, ln.id})
        self.v.run(C.DeleteWireCmd)
        self.assertIn(ln.id, self.s.entities)           # the line stays
        self.assertNotIn(c.id, self.s.entities)
        # the two left meeting end to end at (5, 5) are one wire now
        self.assertEqual(self.paths(), [((1.0, 5.0), (9.0, 5.0))])
        self.p.undo()
        self.assertEqual(len(self.s.wires()), 3)

    def test_drawing_joins_and_skips_duplicates(self):
        self.add([(1, 5), (5, 5)])
        self.v.run(C.WireCmd)
        type_in(self.v, "5,5", "5,9")
        self.v.cmd.enter()
        self.assertEqual(self.paths(), [((1.0, 5.0), (5.0, 5.0), (5.0, 9.0))])
        self.v.run(C.WireCmd)
        type_in(self.v, "2,5", "4,5")                   # ends on the wire: drawn over it
        self.assertEqual(len(self.s.wires()), 1)
        # turned off: drawn as asked
        self.p.settings["wire_cleanup"] = False
        self.v.run(C.WireCmd)
        type_in(self.v, "5,9", "9,9")
        self.v.cmd.enter()
        self.assertEqual(len(self.s.wires()), 2)

    def test_clean_up_wires(self):
        self.add([(1, 1), (3, 1)], [(3, 1), (6, 1)],        # end to end: joined
                 [(1, 2), (2, 2), (4, 2)],                   # an in-line point: tidied
                 [(1, 3), (4, 3)], [(2, 3), (3, 3)],         # drawn over: removed
                 [(1, 4), (1, 4)],                           # no length: removed
                 [(1, 5), (2, 5)], [(2, 5), (3, 5)], [(2, 5), (2, 6)])   # 3 ends: kept
        self.v.run(C.CleanWiresCmd)
        got = self.paths()
        self.assertIn(((1.0, 1.0), (6.0, 1.0)), got)
        self.assertIn(((1.0, 2.0), (4.0, 2.0)), got)
        self.assertIn(((1.0, 3.0), (4.0, 3.0)), got)
        self.assertNotIn(((2.0, 3.0), (3.0, 3.0)), got)
        self.assertEqual(sum(1 for p in got if p[0][1] == 5 or p[-1][1] == 5), 3)
        self.assertFalse(any(p[0] == p[-1] for p in got))
        self.p.undo()
        self.assertEqual(len(self.s.wires()), 9)

    def test_cleanup_reports_loose_ends(self):
        self.add([(1, 1), (3, 1)])
        with self.p.edit("clean") as ed:
            got = wires.cleanup(ed, self.s)
        self.assertEqual(got["loose"], 2)

    def test_wire_moved_to_another_layer_stays_a_wire(self):
        (w,) = self.add([(1, 1), (3, 1)])
        self.p.ensure_layer("WIRES_BLUE")
        self.v.set_selection({w.id})
        self.win._fill_layers()
        i = self.win.layer_box.findText("WIRES_BLUE")
        self.assertGreaterEqual(i, 0)
        self.win._layer_picked(i)
        now = self.s.entities[w.id]
        self.assertIsInstance(now, M.Wire)
        self.assertEqual(now.layer, "WIRES_BLUE")


if __name__ == "__main__":
    unittest.main()
