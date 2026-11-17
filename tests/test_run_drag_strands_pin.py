"""A run of wire dragged by its middle grip, with a wire tapping it that runs from one pin of a
symbol through another (the battery, seed 6006): dragged far the other way, the tapping wire's
end followed the run past its other end and left the pin on its middle with no wire. Such a
drag is refused now, as one that would leave a pin on the run itself is."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class RunDragStrandsPinTest(unittest.TestCase):
    def test_refused(self):
        win, v = window()
        try:
            v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
            p, s = v.project, v.sheet()
            d = win.library.get("symbol", "Relay coil")
            with p.edit("x") as ed:
                ed.block(d)
                coil = ed.add(s, M.Insert(d.name, (3.0, 3.0), defn=p.blocks[d.name],
                                          attrs={"TAG": "CR1"}))
                pins = [q for _n, q in coil.pin_points()]
                left, right = sorted(pins)
                run = ed.add(s, M.Wire([(4.0, 1.0), (4.0, 2.0), (5.0, 2.0), (5.0, 6.0)]))
                tap = ed.add(s, M.Wire([left, (5.0, left[1])]))      # (through the other pin)
            before = run.points
            v.run(C.GripCmd, s.entities[run.id], len(run.points) + 2)
            type_in(v, "-10,3")
            while v.cmd is not None:
                v.cmd.enter()
            self.assertEqual(s.entities[run.id].points, before)
            self.assertTrue(s.entities[tap.id].touches(right))
            # dragged the other way (the tapping wire gets longer): it moves
            v.run(C.GripCmd, s.entities[run.id], len(run.points) + 2)
            type_in(v, "8,3")
            while v.cmd is not None:
                v.cmd.enter()
            self.assertNotEqual(s.entities[run.id].points, before)
            self.assertTrue(any(w.touches(right) for w in s.wires()))
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()
        self.assertTrue(APP)


if __name__ == "__main__":
    unittest.main()
