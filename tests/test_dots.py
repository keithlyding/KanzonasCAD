"""Junction dots (the owner, 0.16: "Sometimes when I add a wire to the end of a wire, it adds a
connection dot. I don't know why... Please figure out why. Also, I need to be able to delete
the connection dots if needed").

Why: a dot goes where three wire ends meet or a wire ends on another wire's middle or bend.
Carrying a wire on from a free end joins it (no dot); carrying it on from a point that is
already a bend, or where two wires already meet end to end, makes three: a dot.
Delete dot (DELDOT) hides one (the wires still join), saved with the sheet, undone by Undo
or by a click on the same spot."""
import json
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wires


class Base(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.s = self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def draw(self, *ws):
        with self.p.edit("w") as ed:
            for pts in ws:
                ed.add(self.s, M.Wire(pts))

    def wire(self, *typed):
        self.v.run(C.WireCmd)
        type_in(self.v, *typed)
        if self.v.cmd is not None:
            self.v.cmd.enter()


class WhyTest(Base):
    def test_from_a_free_end_no_dot(self):
        for to in ("9,4", "6,7", "6,1", "4,7"):
            self.setUp()
            self.draw([(2.0, 4.0), (6.0, 4.0)])
            self.wire("6,4", to)
            self.assertEqual(wires.junctions(self.s), [], to)
            self.assertEqual(len(self.s.wires()), 1)            # (joined into one)
            self.tearDown()

    def test_from_a_bend_a_dot(self):
        self.draw([(2.0, 4.0), (6.0, 4.0), (6.0, 1.0)])
        self.wire("6,4", "9,4")
        self.assertEqual(wires.junctions(self.s), [(6.0, 4.0)])

    def test_from_where_two_wires_meet_a_dot(self):
        self.draw([(2.0, 4.0), (6.0, 4.0)], [(6.0, 4.0), (6.0, 1.0)])
        self.wire("6,4", "9,4")
        self.assertEqual(wires.junctions(self.s), [(6.0, 4.0)])


class DeleteDotTest(Base):
    def test_delete_and_back(self):
        self.draw([(2.0, 4.0), (8.0, 4.0)], [(5.0, 4.0), (5.0, 1.0)])
        self.assertEqual(wires.junctions(self.s), [(5.0, 4.0)])
        self.v.run(C.DeleteDotCmd)
        self.v.cmd.pick((5.01, 4.01))
        self.assertEqual(wires.junctions(self.s), [])
        self.assertTrue(wires.connects_at(self.s, (5.0, 4.0)))   # (still joined)
        self.v.cmd.pick((5.0, 4.0))                              # (the same spot: back)
        self.assertEqual(wires.junctions(self.s), [(5.0, 4.0)])
        self.v.cmd.pick((5.0, 4.0))
        self.v.cancel()
        self.p.undo()
        self.assertEqual(wires.junctions(self.s), [(5.0, 4.0)])
        self.p.redo()
        self.assertEqual(wires.junctions(self.s), [])

    def test_kept_when_saved_and_not_drawn(self):
        self.draw([(2.0, 4.0), (8.0, 4.0)], [(5.0, 4.0), (5.0, 1.0)])
        self.v.run(C.DeleteDotCmd)
        self.v.cmd.pick((5.0, 4.0))
        self.v.cancel()
        again = M.Project.from_dict(json.loads(json.dumps(self.p.to_dict())))
        s2 = again.sheet_by_id(self.s.id)
        self.assertEqual(wires.junctions(s2), [])
        from kanzonascad.render import _dots_path
        self.assertTrue(_dots_path(s2).isEmpty())

    def test_nothing_there(self):
        self.draw([(2.0, 4.0), (8.0, 4.0)])
        self.v.run(C.DeleteDotCmd)
        self.v.cmd.pick((5.0, 4.0))
        self.v.cancel()
        self.assertEqual(self.s.no_dots, [])


if __name__ == "__main__":
    unittest.main()
