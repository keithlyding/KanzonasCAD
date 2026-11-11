"""Snapping reaches the sheet's border and title block (the owner: "I would also like to be
able to snap to the title block"), which are drawn apart from the drawing; they are still never
picked or selected."""
import time
import unittest

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad.sheetframe import border_entities, title_block_entities, title_block_rect


class FrameSnapTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.snap_on = False
        self.v.polar_on = self.v.ortho_on = False
        self.p = self.v.project
        self.s = self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def test_border_corner_snaps(self):
        line = next(e for e in border_entities(self.s) if isinstance(e, M.Line))
        q = line.p1
        got = self.v.object_snap((q[0] + 0.01, q[1] + 0.01), {"end"})
        self.assertIsNotNone(got)
        self.assertEqual(got[0], "end")
        self.assertAlmostEqual(got[1][0], q[0])
        self.assertAlmostEqual(got[1][1], q[1])

    def test_title_block_line_end_snaps(self):
        tb = [e for e in title_block_entities(self.p, self.s) if isinstance(e, M.Line)]
        self.assertTrue(tb, "the default title block has lines")
        rect = title_block_rect(self.p, self.s)
        # a line end inside the title block, away from the border
        line = max(tb, key=lambda e: min(e.p1[0] - rect[0], e.p1[1] - rect[1]))
        q = line.p1
        got = self.v.object_snap((q[0] + 0.005, q[1] - 0.005), {"end"})
        self.assertIsNotNone(got)
        self.assertAlmostEqual(got[1][0], q[0])
        self.assertAlmostEqual(got[1][1], q[1])
        mid = ((line.p1[0] + line.p2[0]) / 2, (line.p1[1] + line.p2[1]) / 2)
        if line.length() > 0.2:
            got = self.v.object_snap((mid[0] + 0.005, mid[1] + 0.005), {"mid"})
            self.assertEqual(got[0], "mid")

    def test_follows_title_block_edits(self):
        tbs = self.p.title_block
        with self.p.edit("tb line") as ed:
            ed.add(tbs, M.Line((1.0, 1.0), (1.5, 1.37)))
        placed = [e for e in title_block_entities(self.p, self.s) if isinstance(e, M.Line)
                  and abs(e.length() - 0.5 * (1 + 0.37 ** 2 / 0.25) ** 0.5) < 1e-6]
        self.assertTrue(placed)
        q = placed[-1].p2
        got = self.v.object_snap((q[0] + 0.005, q[1]), {"end"})
        self.assertIsNotNone(got)
        self.assertAlmostEqual(got[1][0], q[0])
        self.p.undo()
        got = self.v.object_snap((q[0] + 0.005, q[1]), {"end"})
        self.assertTrue(got is None or abs(got[1][0] - q[0]) > 1e-9
                        or abs(got[1][1] - q[1]) > 1e-9)

    def test_hidden_layer_and_never_picked(self):
        line = next(e for e in border_entities(self.s) if isinstance(e, M.Line))
        self.assertIsNone(self.v.pick_entity(line.p1))
        tb = [e for e in title_block_entities(self.p, self.s) if isinstance(e, M.Line)]
        rect = title_block_rect(self.p, self.s)
        line = max(tb, key=lambda e: min(e.p1[0] - rect[0], e.p1[1] - rect[1]))
        q = line.p1
        self.assertIsNone(self.v.pick_entity(q))
        self.assertIsNotNone(self.v.object_snap(q, {"end"}))
        lay = self.p.layers[line.layer]
        lay.visible = False
        try:
            got = self.v.object_snap(q, {"end"})
            self.assertTrue(got is None or got[1] != q)
        finally:
            lay.visible = True

    def test_speed(self):
        # (built once per frame change; a mouse move only queries it)
        self.v.object_snap((5, 5), {"end"})
        t = time.perf_counter()
        for i in range(500):
            self.v.object_snap((1 + i * 0.03, 1 + i * 0.01), {"end", "mid", "int", "near"})
        self.assertLess((time.perf_counter() - t) / 500, 0.01)


if __name__ == "__main__":
    unittest.main()
