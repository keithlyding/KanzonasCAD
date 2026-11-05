"""Big blocks (a footprint made from a maker's drawing: thousands of lines, arcs and texts) stay
quick to work with: the snaps, hover and a Move's preview look at the pieces near the cursor
or draw once, instead of every piece on every mouse move (three such footprints froze the
program for seconds on a Move)."""
import random
import unittest

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import render, trim, view as V

N = 2000


def _footprint(n=N, seed=2):
    random.seed(seed)
    ents = []
    for i in range(n):
        x, y = random.uniform(0, 6), random.uniform(0, 5)
        r = random.random()
        if r < 0.7:
            ents.append(M.Line((x, y), (x + random.uniform(-.05, .05),
                                        y + random.uniform(-.05, .05))))
        elif r < 0.9:
            ents.append(M.Arc((x, y), random.uniform(.01, .05), 0, 180))
        else:
            ents.append(M.Text((x, y), "T%d" % i, 0.03))
    return M.BlockDef("FP", "footprint", ents)


class BigBlocksTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.snap_on = self.v.polar_on = self.v.ortho_on = False
        self.v.osnap_on = True
        self.v.osnap_modes = {"end", "mid", "center", "int", "near", "insert"}
        self.p = self.v.project
        self.s = self.v.sheet()
        with self.p.edit("place") as ed:
            ed.block(_footprint())
            self.ids = [ed.add(self.s, M.Insert("FP", (1 + i * 3.5, 2),
                                                defn=self.p.blocks["FP"])).id for i in range(3)]
        self.v.zoom("extents")
        APP.processEvents()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def move(self, x, y):
        q = QPointF(x, y)
        APP.sendEvent(self.v, QMouseEvent(QEvent.MouseMove, q, q, Qt.NoButton, Qt.NoButton,
                                          Qt.NoModifier))
        self.v.repaint()

    def count(self, module, name):
        calls = [0]
        real = getattr(module, name)

        def counted(*a, **k):
            calls[0] += 1
            return real(*a, **k)
        setattr(module, name, counted)
        self.addCleanup(setattr, module, name, real)
        return calls

    def test_snaps_look_only_at_pieces_near_the_cursor(self):
        calls = self.count(trim, "intersect")
        self.v.run(C.LineCmd)
        for i in range(10):
            self.v.object_snap((4.0 + i * 0.2, 4.0))
        # (every piece of each footprint against the others' was ~1,000,000 per call)
        self.assertLess(calls[0], 20000)
        self.v.cancel()

    def test_move_preview_is_drawn_once_and_slid(self):
        self.v.set_selection({self.ids[0]})
        self.v.run(C.MoveCmd)
        type_in(self.v, "2,3")
        self.move(390, 295)                     # (the preview and the highlight made once)
        calls = self.count(V, "entities_path")
        for i in range(10):
            self.move(400 + i * 13, 300 + i * 5)
        self.assertEqual(calls[0], 0)
        type_in(self.v, "4,3")
        self.assertAlmostEqual(self.s.entities[self.ids[0]].pos[0], 3.0)

    def test_hover_measures_only_nearby_pieces(self):
        self.v.set_selection(set())
        real = M.Insert.distance
        calls = [0]

        def counted(ins, p):
            calls[0] += 1
            return real(ins, p)
        M.Insert.distance = counted
        try:
            for i in range(10):
                self.move(300 + i * 30, 400)
        finally:
            M.Insert.distance = real
        self.assertEqual(calls[0], 0)                   # (each measured every piece)
        self.assertTrue(render)

    def test_hover_still_finds_the_footprint(self):
        fp = self.s.entities[self.ids[1]]
        w = next(e for e in fp.world_entities() if isinstance(e, M.Line))
        got = self.v.pick_entity(w.p1)
        self.assertIsNotNone(got)
        self.assertEqual(got.id, fp.id)
        self.assertIsNone(self.v.pick_entity((50.0, 50.0)))


if __name__ == "__main__":
    unittest.main()
