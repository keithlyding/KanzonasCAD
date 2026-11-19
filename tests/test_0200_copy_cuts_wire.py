"""A symbol copied, moved or pasted onto a wire cuts it between its pins and lands on both
sides, as one inserted there does (the owner: "I just copied this cb902 into this location
from the line above and it didn't automatically break the wires and reattach on both
terminations")."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class CopyCutsWireTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.s = self.v.sheet()
        coil = self.win.library.get("symbol", "Relay coil")
        with self.p.edit("parts") as ed:
            self.cb = ed.add(self.s, M.Insert("Relay coil", (5.0, 8.0), 0.0, 1.0, False,
                                              {"TAG": "CR1"}, coil, 0.1))
            ed.add(self.s, M.Wire([(1.0, 5.0), (12.0, 5.0)]))       # (the line below)
        self.said = []
        self.v.message = lambda text: self.said.append(text)

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def wires_on(self, y):
        return sorted(tuple(w.points) for w in self.s.wires()
                      if all(abs(q[1] - y) < 1e-9 for q in w.points))

    def landed(self):
        """The wires on y=5 after: cut at the new symbol's pins (4.75 and 5.25)."""
        return self.wires_on(5.0) == [((1.0, 5.0), (4.75, 5.0)), ((5.25, 5.0), (12.0, 5.0))]

    def test_copied_onto_the_wire(self):
        self.v.set_selection({self.cb.id})
        self.v.run(C.CopyCmd)
        type_in(self.v, "5,8", "5,5", "")
        self.assertTrue(self.landed(), self.wires_on(5.0))
        self.assertTrue(any("Wire cut" in t for t in self.said), self.said)
        self.p.undo()
        self.assertEqual(self.wires_on(5.0), [((1.0, 5.0), (12.0, 5.0))])   # (one step)

    def test_moved_onto_the_wire(self):
        self.v.set_selection({self.cb.id})
        self.v.run(C.MoveCmd)
        type_in(self.v, "5,8", "5,5")
        self.assertTrue(self.landed(), self.wires_on(5.0))

    def test_pasted_onto_the_wire(self):
        self.v.set_selection({self.cb.id})
        self.win.copy_clip()
        self.win.paste()
        base = self.v.cmd.base_pt                       # (the copy's base point: kept as is)
        type_in(self.v, "%g,%g" % (base[0], base[1] - 3.0))     # (3 below: onto the wire)
        self.assertTrue(self.landed(), self.wires_on(5.0))

    def test_off_the_wire_nothing_cut(self):
        self.v.set_selection({self.cb.id})
        self.v.run(C.CopyCmd)
        type_in(self.v, "5,8", "5,6", "")
        self.assertEqual(self.wires_on(5.0), [((1.0, 5.0), (12.0, 5.0))])


if __name__ == "__main__":
    unittest.main()
