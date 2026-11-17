"""Clean up wires joining two wires end to end where the second runs straight back along the
first, its end a hair off the other's line (52455.999999999985 for 52456, far from the origin:
the long battery on GitHub, seed 3283): the guard against that join used a fixed tolerance the
hair passed, and the join made a wire folded back over itself. Measured by angle now."""
import unittest

from kanzonascad import model as M
from kanzonascad import wires as W


class CleanupNoFoldJoinTest(unittest.TestCase):
    def test_not_joined_back_over_itself(self):
        p = M.Project.new()
        s = p.sheets[0]
        y = 52456.0
        with p.edit("x") as ed:
            ed.add(s, M.Wire([(65820.5, y - 20.0), (65818.25, y - 20.0), (65818.25, y),
                              (65817.5, y)]))
            ed.add(s, M.Wire([(65817.5, 52455.999999999985), (65820.5, 52455.999999999985)]))
        with p.edit("Clean up") as ed:
            W.cleanup(ed, s)
        for w in s.wires():
            self.assertFalse(W.doubles_back(w.points), w.points)

    def test_straight_on_still_joined(self):
        p = M.Project.new()
        s = p.sheets[0]
        with p.edit("x") as ed:
            ed.add(s, M.Wire([(1.0, 1.0), (2.0, 1.0)]))
            ed.add(s, M.Wire([(2.0, 1.0), (2.0, 3.0)]))
        with p.edit("Clean up") as ed:
            W.cleanup(ed, s)
        self.assertEqual(len(s.wires()), 1)


if __name__ == "__main__":
    unittest.main()
