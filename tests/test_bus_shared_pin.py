"""Found by the quick battery (0.17.5, seed 12): two 3-pole disconnects stacked half an inch
apart share pins (their poles make one even line of four). A bus clicked on the lower one's
bottom pin landed one pin up, on the upper one's three, leaving the clicked pin without a
wire: the side was looked up again from the first pin of the run, which both share."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class BusSharedPinTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        self.s, self.p = v.sheet(), v.project

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def insert(self, at):
        d = self.win.library.get("symbol", "Disconnect 3-pole")
        with self.p.edit("x") as ed:
            ed.block(d)
            return ed.add(self.s, M.Insert(d.name, at, defn=self.p.blocks[d.name]))

    def test_lands_on_the_clicked_pins_side(self):
        # (one pin up, placed first: a pin both have is the upper one's when looked up)
        self.insert((5.0, 5.5))
        lower = self.insert((5.0, 5.0))
        source = self.insert((20.0, -3.0))
        t = [q for n, q in lower.pin_points() if n.startswith("T")]
        src = [q for n, q in source.pin_points() if n.startswith("T")]
        self.v.run(C.BusCmd)
        type_in(self.v, "%r,%r" % src[1], "%r,%r" % t[2])      # (onto the lower's T3)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        ends = {tuple(q) for w in self.s.wires() for q in (w.points[0], w.points[-1])}
        self.assertTrue(all(tuple(q) in ends for q in t), (t, sorted(ends)))


if __name__ == "__main__":
    unittest.main()
