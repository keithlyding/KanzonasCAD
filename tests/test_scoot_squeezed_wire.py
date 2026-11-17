"""Scoot with everything attached squeezing a wire to nothing (the long battery, seed 4101): a
short wire from a bus line that moves with the branch down to a wire end that stays was left
with one point; it goes, as Clean up wires takes wires of no length."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class ScootSqueezedWireTest(unittest.TestCase):
    def test_squeezed_wire_goes(self):
        win, v = window()
        try:
            v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
            p, s = v.project, v.sheet()
            d = win.library.get("symbol", "Circuit breaker 3-pole")
            ds = win.library.get("symbol", "Disconnect 3-pole")
            with p.edit("x") as ed:
                ed.block(d)
                ed.block(ds)
                pd = p.blocks[d.name]
                # (the disconnect the breaker's wires run to: the bus line moves with them)
                ed.add(s, M.Insert(ds.name, (10.25, 4.0), 0.0, defn=p.blocks[ds.name],
                                   attrs={"TAG": "DS1"}))
                cb = ed.add(s, M.Insert(d.name, (7.5, 1.25), 270.0, defn=pd, attrs={"TAG": "CB1"}))
                ed.add(s, M.Insert(d.name, (5.0, 1.25), 270.0, defn=pd, attrs={"TAG": "CB2"}))
                for pts in ([(5, 4), (5, 3.5)], [(10, 3.5), (7, 3.5)], [(5, 3.5), (1, 3.5)],
                            [(10, 4), (1, 4)], [(7.5, 4), (7.5, 1.5)], [(7, 3.5), (7, 1.5)],
                            [(4.5, 3.5), (4.5, 1.5)], [(8, 1.5), (8, 4.5), (10, 4.5)]):
                    ed.add(s, M.Wire([(float(a), float(b)) for a, b in pts]))
            v.set_selection({cb.id})
            v.run(C.ScootCmd)
            type_in(v, "7.5,1.25", "7.5,0.75")
            while v.cmd is not None:
                v.cmd.enter()
            self.assertEqual([w.points for w in s.wires() if len(w.points) < 2], [])
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()
        self.assertTrue(APP)


if __name__ == "__main__":
    unittest.main()
