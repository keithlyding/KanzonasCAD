"""A symbol turned 45 degrees, moved, can stop with a pin a hair from a wire passing across it
(the long battery, seed 5052 at step 1697: a drive's terminal 02 and the wire on it 0.0089"
under a wire running across the drive's row of pins). The wire end is on its pin, joined as
drawn; the passing wire is not joined to it (that would wire two circuits together), and
the battery's drawing-slop check leaves such an end out, as it does ends on slanted runs:
where a turned symbol's pins are is chance. The same end on an upright symbol is still found."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import geometry as G
from kanzonascad import model as M
from tests import battery_checks as BC


class TurnedPinNearWireTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        self.s, self.p = v.sheet(), v.project

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def coil(self, angle):
        """A relay coil at (5, 5) turned by angle, a wire from its first pin to the right,
        and a wire straight across 0.0089" + 0.5 above that pin (so 0.0089" above once the
        coil is moved down 0.5); returns (coil, its wire, the passing wire)."""
        before = set(self.s.entities)
        self.v.run(C.InsertCmd, self.win.library.get("symbol", "Relay coil"), {})
        type_in(self.v, "5,5")
        while self.v.cmd is not None:
            self.v.cmd.enter()
        ins = [e for i, e in self.s.entities.items() if i not in before and
               isinstance(e, M.Insert)][0]
        with self.p.edit("turn") as ed:
            ins = ed.change(self.s, ins.copy(angle=angle))
        q = ins.pin_points()[0][1]
        with self.p.edit("wires") as ed:
            w = ed.add(self.s, M.Wire([q, (q[0] + 3.0, q[1])]))
            y = q[1] - 0.5 + 0.0089
            across = ed.add(self.s, M.Wire([(q[0] - 2.0, y), (q[0] + 2.0, y)]))
        return ins, w, across

    def move_down(self, ins):
        self.v.set_selection({ins.id})
        self.v.run(C.MoveCmd)
        type_in(self.v, "%r,%r" % ins.pos, "@0,-0.5")
        self.assertIsNone(self.v.cmd)

    def test_turned_symbol(self):
        ins, w, across = self.coil(45.0)
        self.move_down(ins)
        q = dict(self.s.entities[ins.id].pin_points())
        end = self.s.entities[w.id].points[0]
        self.assertTrue(any(G.dist(end, p) <= 1e-9 for p in q.values()),
                        "the wire left its pin")
        self.assertEqual(self.s.entities[across.id].points, across.points,
                         "the passing wire was changed (joined to the pin?)")
        self.assertAlmostEqual(abs(end[1] - across.points[0][1]), 0.0089, places=6)
        self.assertEqual(BC.near_misses(self.s), [])
        self.assertGreater(BC.CHECKED["near misses: ends on pins of turned symbols left out"], 0)

    def test_upright_symbol_still_found(self):
        ins, w, across = self.coil(0.0)
        self.move_down(ins)
        near = BC.near_misses(self.s)
        self.assertEqual([(i, k) for i, _p, k, _d in near], [(w.id, "wire")])
        self.assertAlmostEqual(near[0][3], 0.0089, places=6)


if __name__ == "__main__":
    unittest.main()
