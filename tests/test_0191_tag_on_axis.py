"""A sideways symbol's tag dragged onto the symbol's own line keeps its place when the symbol
moves (the sweep, 0.19.1, seed 3507: a 3-pole fuse block turned 270 and flipped, its tag on its
axis, moved by 2", 2": the tag jumped from one side of its spot to the other, as a rounding
error changed sign)."""
import unittest

from tests.util import APP, window

from kanzonascad import model as M


class TagOnAxisTest(unittest.TestCase):
    def test_moves_with_the_symbol(self):
        win, v = window()
        try:
            lib = win.library
            d = lib.get("symbol", "Fuses 3-pole")
            p, s = v.project, v.sheet()
            with p.edit("x") as ed:
                ed.block(d)
                e = ed.add(s, M.Insert(d.name, (-5.75, 14.75), 270.0, 1.0, True,
                                       {"TAG": "FU110"}, p.blocks[d.name],
                                       attr_at={"TAG": (-1.25, 2.296212748401287e-16, 0.0)}))
            first = s.entities[e.id].tag_text()
            for dx, dy in ((2.0, 2.0), (0.1, -3.3), (-7.25, 0.5), (123.456, 78.9)):
                moved = s.entities[e.id].copy(pos=[-5.75 + dx, 14.75 + dy])
                t = moved.tag_text()
                self.assertEqual(t.align, first.align)
                b0, b1 = first.bbox(), t.bbox()
                self.assertAlmostEqual(b1[0] - b0[0], dx, places=9)
                self.assertAlmostEqual(b1[1] - b0[1], dy, places=9)
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()
        self.assertTrue(APP)


if __name__ == "__main__":
    unittest.main()
