"""A bus carried on from its open ends with a symbol in the way (the battery, seed 77; in
0.17.5 too): the way round turned straight across the bus's own ends, joined a wire to another's
end with a dot and tangled the others. A bus leaving its ends (or pins) leaves them square, the
way it was clicked; a way round that doesn't, or whose wires touch or double back, isn't used."""
import unittest

from tests.util import APP, window

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wires as W


class BusCarryOnAroundTest(unittest.TestCase):
    def test_carried_on_without_joining_its_own_ends(self):
        win, v = window()
        try:
            v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
            p, s = v.project, v.sheet()
            d = win.library.get("symbol", "Pushbutton NO")
            with p.edit("x") as ed:
                ed.block(d)
                for y in (3.0, 2.5, 2.0):
                    ed.add(s, M.Wire([(6.0, y), (8.5, y)]))
                # (a pushbutton just past the top wire's end, in the bus's way)
                ed.add(s, M.Insert(d.name, (9.25, 3.0), 180.0, 1.0, True, {"TAG": "PB1"},
                                   p.blocks[d.name]))
            before = set(W.junctions(s))
            v.run(C.BusCmd)
            v.input_text("8.5,3")
            v.input_text("11.5,3")
            while v.cmd is not None:
                v.cmd.enter()
            self.assertEqual(set(W.junctions(s)) - before, set())
            for w in s.wires():
                self.assertFalse(W.doubles_back(w.points), w.points)
            # each of the three carried on from its own end, none onto another's
            for y in (3.0, 2.5, 2.0):
                self.assertTrue(W.connects_at(s, (8.5, y)) or
                                any(w.touches((8.5, y)) and (8.5, y) not in
                                    (tuple(w.points[0]), tuple(w.points[-1]))
                                    for w in s.wires()), y)
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()
        self.assertTrue(APP)


if __name__ == "__main__":
    unittest.main()
