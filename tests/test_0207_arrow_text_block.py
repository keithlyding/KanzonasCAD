"""An arrow's reference with the far device on a second line is placed as a whole block clear
of its wire, not its first line alone (the battery, 0.19.11, seed 152: over the arrow the block
grew up onto a wire looping round it)."""
import unittest

from tests.util import APP, window

from kanzonascad import geometry as G
from kanzonascad import model as M
from kanzonascad import xrefs
from kanzonascad.wirenums import ARROWS


class ArrowTextBlockTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.lib = self.win.library
        with self.p.edit("sheets") as ed:
            ed.add_sheet(self.p.make_sheet("Two"))
        self.s1, self.s2 = self.p.sheets

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_two_lines_clear_of_a_looping_wire(self):
        # (the source at (6, 5), its wire out to the right, up, back over the arrow just above
        # where one line would go, and down beside it on the left)
        loop = [(6.0, 5.0), (6.8, 5.0), (6.8, 5.18), (5.5, 5.18), (5.5, 4.99)]
        with self.p.edit("loop") as ed:
            ed.add(self.s1, M.Wire(loop))
            ed.add(self.s1, M.Insert(ARROWS[0], (6.0, 5.0), 180.0, 1.0, False, {"TAG": "Q"},
                                     self.lib.get("symbol", ARROWS[0]), 0.1))
            ed.add(self.s2, M.Wire([(2.0, 5.0), (4.0, 5.0)]))
            ed.add(self.s2, M.Insert(ARROWS[1], (2.0, 5.0), 180.0, 1.0, False, {"TAG": "Q"},
                                     self.lib.get("symbol", ARROWS[1]), 0.1))
            ed.add(self.s2, M.Insert("Relay coil", (4.25, 5.0), 0.0, 1.0, False,
                                     {"TAG": "CR9"}, self.lib.get("symbol", "Relay coil"), 0.1))
        items = [it for it in xrefs.live(self.p, self.s1)]
        texts = [t for _x, _y, t, *_r in items]
        self.assertIn("CR9", texts)                         # (the second line is there)
        w = [x for x in self.s1.wires()][0]
        for it in items:
            tb = xrefs.text_item(it).bbox()
            self.assertFalse(any(G.segment_hits_rect(a, b, tb)
                                 for a, b in zip(w.points, w.points[1:])),
                             "%r lies on its wire: %r" % (it[2], tb))


if __name__ == "__main__":
    unittest.main()
