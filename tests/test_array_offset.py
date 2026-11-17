"""Array, Offset and the middle grips (the owner: "I thought we had array on KanzonasCAD" (it
didn't), "I need a middle grabber on rectangles also, so I can resize it longer or shorter",
and "duplicate a shape either larger or smaller than the one selected. I think it's called
offset in Autocad")."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


def rnd9(q):
    return tuple(round(c, 9) for c in q)


class ArrayOffsetTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        self.s = v.sheet()
        self.p = v.project

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def add(self, e):
        with self.p.edit("add") as ed:
            return ed.add(self.s, e)

    def of(self, kind):
        return [e for e in self.s.entities.values() if isinstance(e, kind)]

    # ---- Array ----------------------------------------------------------------------------
    def test_rectangular_array(self):
        r = self.add(M.Polyline([(1, 1), (2, 1), (2, 1.5), (1, 1.5)], True))
        self.v.set_selection({r.id})
        self.v.run(C.ArrayCmd)
        type_in(self.v, "R", "3", "4", "1", "-2")
        got = sorted(rnd9(e.points[0]) for e in self.of(M.Polyline))
        want = sorted((1.0 + c * -2, 1.0 + r_ * 1) for r_ in range(3) for c in range(4))
        self.assertEqual(got, want)
        self.p.undo()
        self.assertEqual(len(self.of(M.Polyline)), 1)

    def test_polar_array(self):
        c = self.add(M.Circle((8.0, 8.0), 0.5))
        self.v.set_selection({c.id})
        self.v.run(C.ArrayCmd)
        type_in(self.v, "P", "5,8", "4")
        self.v.cmd.enter()                                  # (360)
        got = sorted(rnd9(e.center) for e in self.of(M.Circle))
        self.assertEqual(got, [(2.0, 8.0), (5.0, 5.0), (5.0, 11.0), (8.0, 8.0)])
        # a half circle: 3 items, the last at 180
        self.v.set_selection({c.id})
        self.v.run(C.ArrayCmd)
        type_in(self.v, "P", "5,8", "3", "180")
        self.assertIn((2.0, 8.0), [rnd9(e.center) for e in self.of(M.Circle)])
        self.assertIn((5.0, 11.0), [rnd9(e.center) for e in self.of(M.Circle)])

    def test_arrayed_devices_get_tags_of_their_own(self):
        self.v.run(C.InsertCmd, self.win.library.get("symbol", "Pilot light"), {})
        type_in(self.v, "2,2")
        while self.v.cmd is not None:
            self.v.cmd.enter()
        lt = self.s.inserts()[0]
        self.v.set_selection({lt.id})
        self.v.run(C.ArrayCmd)
        type_in(self.v, "R", "1", "3", "1", "1")
        tags = sorted(e.attrs["TAG"] for e in self.s.inserts())
        self.assertEqual(len(set(tags)), 3, tags)

    # ---- Offset ---------------------------------------------------------------------------
    def test_offset_a_rectangle_smaller_and_larger(self):
        r = self.add(M.Polyline([(1, 1), (3, 1), (3, 2), (1, 2)], True))
        self.v.run(C.OffsetCmd)
        type_in(self.v, "0.25")
        self.v.cmd.pick((2.0, 1.0))
        self.v.cmd.point((2.0, 1.5))                        # inside: smaller
        self.v.cmd.pick((2.0, 1.0))
        self.v.cmd.point((2.0, 0.0))                        # outside: larger
        self.v.cmd.enter()
        boxes = sorted(rnd9(e.bbox()) for e in self.of(M.Polyline))
        self.assertEqual(boxes, [(0.75, 0.75, 3.25, 2.25), (1.0, 1.0, 3.0, 2.0),
                                 (1.25, 1.25, 2.75, 1.75)])
        self.assertTrue(all(e.closed for e in self.of(M.Polyline)))

    def test_offset_too_far_inside_is_refused(self):
        self.add(M.Polyline([(1, 1), (3, 1), (3, 2), (1, 2)], True))
        said = []
        self.v.messaged.connect(said.append)
        self.v.run(C.OffsetCmd)
        type_in(self.v, "0.6")
        self.v.cmd.pick((2.0, 1.0))
        self.v.cmd.point((2.0, 1.5))
        self.assertIn("inside out", said[-1])
        self.assertEqual(len(self.of(M.Polyline)), 1)
        self.v.cancel()

    def test_offset_lines_circles_arcs_and_through(self):
        self.add(M.Line((1, 5), (4, 5)))
        self.add(M.Circle((8, 8), 1.0))
        self.add(M.Arc((8, 3), 1.0, 0, 90))
        self.v.run(C.OffsetCmd)
        type_in(self.v, "0.5")
        self.v.cmd.pick((2.0, 5.0))
        self.v.cmd.point((2.0, 4.0))
        self.v.cmd.pick((9.0, 8.0))
        self.v.cmd.point((8.0, 8.0))
        self.v.cmd.pick((9.0, 3.0))
        self.v.cmd.point((10.0, 3.0))
        self.v.cmd.enter()
        self.assertIn(((1.0, 4.5), (4.0, 4.5)), [(e.p1, e.p2) for e in self.of(M.Line)])
        self.assertIn(0.5, [e.radius for e in self.of(M.Circle)])
        self.assertIn(1.5, [e.radius for e in self.of(M.Arc)])
        # Through: the copy passes through the point clicked
        self.v.run(C.OffsetCmd)
        type_in(self.v, "T")
        self.v.cmd.pick((2.0, 5.0))
        self.v.cmd.point((3.0, 6.25))
        self.assertIn(((1.0, 6.25), (4.0, 6.25)),
                      [(rnd9(e.p1), rnd9(e.p2)) for e in self.of(M.Line)])
        self.v.cancel()

    def test_offset_remembers_the_distance_and_refuses_wires(self):
        w = self.add(M.Wire([(1, 1), (5, 1)]))
        said = []
        self.v.messaged.connect(said.append)
        self.v.run(C.OffsetCmd)
        type_in(self.v, "0.3")
        self.v.cmd.pick((2.0, 1.0))
        self.assertIn("lines, polylines", said[-1])
        self.v.cancel()
        # the next Offset offers the same distance: Enter takes it
        r = self.add(M.Polyline([(1, 3), (3, 3), (3, 4), (1, 4)], True))
        self.v.run(C.OffsetCmd)
        self.v.cmd.enter()
        self.v.cmd.pick((2.0, 3.0))
        self.v.cmd.point((2.0, 2.0))
        self.v.cancel()
        self.assertIn((0.7, 2.7, 3.3, 4.3), [rnd9(e.bbox()) for e in self.of(M.Polyline)
                                             if e.id != r.id])
        self.assertEqual(len(self.of(M.Wire)), 1)       # (the wire: no copy)
        del w

    # ---- middle grips ---------------------------------------------------------------------
    def test_a_rectangles_middle_grips_make_it_longer_or_shorter(self):
        r = self.add(M.Polyline([(1, 1), (3, 1), (3, 2), (1, 2)], True))
        self.assertEqual(len(r.grips()), 8)
        self.v.run(C.GripCmd, r, 5)                         # (the right side's middle)
        type_in(self.v, "4.5,1.9")                          # (up a little: only across counts)
        got = self.s.entities[r.id]
        self.assertEqual([rnd9(q) for q in got.points], [(1, 1), (4.5, 1), (4.5, 2), (1, 2)])
        self.v.run(C.GripCmd, got, 6)                       # (the top's middle) down
        type_in(self.v, "2,1.25")
        got = self.s.entities[r.id]
        self.assertEqual([rnd9(q) for q in got.points],
                         [(1, 1), (4.5, 1), (4.5, 1.25), (1, 1.25)])

    def test_a_wire_has_its_corners_then_the_middles_of_its_runs(self):
        # (0.16.7: a wire's run dragged by its middle grip, the wires on it following:
        # tests/test_bus_around_runs.py)
        w = self.add(M.Wire([(1, 1), (5, 1), (5, 3)]))
        self.assertEqual(w.grips(), [(1.0, 1.0), (5.0, 1.0), (5.0, 3.0), (3.0, 1.0), (5.0, 2.0)])


if __name__ == "__main__":
    unittest.main()
