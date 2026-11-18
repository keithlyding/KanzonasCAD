"""Scoot with everything attached never pulls a wire off a pin of a device that stays (the
sweep, 0.18.2, seed 406: a wire from a breaker's line pin ran away and back along the row of
line pins, through the next breaker's; scooting the first breaker moved that wire's end and
left the other breaker's pins with no wire). Such a move is refused, saying why."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class ScootStrandsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.s = self.v.sheet()
        cb = self.win.library.get("symbol", "Circuit breaker 3-pole")
        for at in ("10,5", "5,5"):
            self.v.run(C.InsertCmd, cb, {})
            type_in(self.v, at)
            while self.v.cmd is not None:
                self.v.cmd.enter()
        self.a, self.b = sorted(self.s.inserts(), key=lambda e: -e.pos[0])
        pins = sorted((q for _n, q in self.a.pin_points()), key=lambda q: (-q[1], -q[0]))
        a1 = pins[0]                                # (a top pin of A, rightmost)
        self.row = [q for _n, q in self.b.pin_points() if abs(q[1] - a1[1]) < 1e-9]
        self.assertTrue(self.row)                   # (B's pins on that row)
        xmin = min(q[0] for q in self.row) - 2.0
        top = a1[1] + 3.0
        with self.p.edit("wire") as ed:
            # a bus across the top; a drop off its middle runs away up, back down left of B
            # and along the row of pins to A's (through B's: not ending on them)
            ed.add(self.s, M.Wire([(a1[0] - 1.0, top), (a1[0] + 1.0, top)]))
            self.w = ed.add(self.s, M.Wire([(a1[0], top), (a1[0], top + 1.0),
                                            (xmin, top + 1.0), (xmin, a1[1]), a1]))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def wired(self, q):
        return any(w.touches(q) for w in self.s.wires())

    def test_refused_not_stranded(self):
        self.assertTrue(all(self.wired(q) for q in self.row))
        said = []
        self.v.message = lambda m, *a: said.append(m)
        steps = len(self.p.undo_stack)
        self.v.set_selection({self.a.id})
        self.v.run(C.ScootCmd)
        x, y = self.a.pos
        type_in(self.v, "%r,%r" % (x, y), "%r,%r" % (x, y + 0.5))
        self.assertTrue(all(self.wired(q) for q in self.row),
                        "B's pins lost their wire")
        self.assertEqual(len(self.p.undo_stack), steps)          # (nothing moved)
        self.assertTrue(any("come off a pin" in m for m in said), said)

    def test_a_branch_clear_of_others_still_moves(self):
        # (the wire cut back to end before B's pins: nothing else on it, the scoot goes)
        a1 = self.w.points[-1]
        with self.p.edit("short") as ed:
            ed.change(self.s, self.w.copy(points=[(a1[0], a1[1] + 3.0), a1]))
        self.assertFalse(any(self.wired(q) for q in self.row))
        self.v.set_selection({self.a.id})
        self.v.run(C.ScootCmd)
        x, y = self.a.pos
        type_in(self.v, "%r,%r" % (x, y), "%r,%r" % (x, y + 0.5))
        self.assertAlmostEqual(self.s.entities[self.a.id].pos[1], y + 0.5)


class ScootMovedPinStrandsTest(unittest.TestCase):
    """The other way round (the sweep, 0.18.2, seed 901): a breaker that moves with the branch,
    a wire leaving the branch running through two of its pins to a far end that stays. The
    breaker went, its pins off that wire."""

    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p, self.s = self.v.project, self.v.sheet()
        lib = self.win.library
        with self.p.edit("parts") as ed:
            self.d = ed.add(self.s, M.Insert("Disconnect 3-pole", (10.0, 5.0), 0.0, 1.0, False,
                                             {}, lib.get("symbol", "Disconnect 3-pole"), 0.1))
            self.b = ed.add(self.s, M.Insert("Circuit breaker 3-pole", (20.5, 9.25), 270.0,
                                             1.0, False, {},
                                             lib.get("symbol", "Circuit breaker 3-pole"), 0.1))
        dp = dict(self.d.pin_points())
        bp = sorted((q for _n, q in self.b.pin_points()), key=lambda q: (q[0], q[1]))
        self.col = [q for q in bp if abs(q[0] - bp[0][0]) < 1e-9]       # (B's left column)
        top = max(q[1] for q in self.col)
        far = bp[-1]
        with self.p.edit("wires") as ed:
            # D to B: B moves with D (the branch)
            ed.add(self.s, M.Wire([dp["T1"] if "T1" in dp else list(dp.values())[3],
                                   (far[0] + 2.0, 5.5), (far[0] + 2.0, far[1]), far]))
            # (as the sweep's drawing had them) a wire down onto B's top left pin, and one
            # leaving D up through B's left column of pins to end on that wire's middle: it
            # leaves the branch there, only its end on D moving
            start = sorted(dp.values(), key=lambda q: (-q[0], q[1]))[0]
            x = self.col[0][0]
            ed.add(self.s, M.Wire([(x, top + 2.0), (x, top)]))
            self.w = ed.add(self.s, M.Wire([start, (x, start[1]), (x, top + 0.5)]))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def wired(self, q):
        return any(w.touches(q) for w in self.s.wires())

    def test_refused_not_stranded(self):
        self.assertTrue(all(self.wired(q) for q in self.col))
        said = []
        self.v.message = lambda m, *a: said.append(m)
        steps = len(self.p.undo_stack)
        self.v.set_selection({self.d.id})
        self.v.run(C.ScootCmd)
        x, y = self.d.pos
        type_in(self.v, "%r,%r" % (x, y), "%r,%r" % (x + 0.5, y))
        b = self.s.entities[self.b.id]
        moved = abs(b.pos[0] - self.b.pos[0]) > 1e-9
        if moved:                                       # (then its pins kept their wire)
            for q in self.col:
                self.assertTrue(self.wired((q[0] + 0.5, q[1])), q)
        else:
            self.assertEqual(len(self.p.undo_stack), steps)
            self.assertTrue(any("come off a pin" in m for m in said), said)


if __name__ == "__main__":
    unittest.main()
