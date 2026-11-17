"""Scoot a whole branch (the owner, 0.17.3, with a photo of motors under drives under
contactors, dropped off a 3-phase bus: "I need to be able to scoot a motor and everything
attached to it gets scooted with it. Same thing if I scoot a vfd"; asked: in any direction, O
for only the one as before).

A fuse block hangs off three bus wires by three drops, and a motor hangs off the fuses. Scooting
the motor (or the fuses) moves both and the wires between; the drops slide along the bus when
the move runs along it, and stretch when it doesn't; nothing comes off its pin or the bus."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from tests import battery_checks as BC


class ScootBranchTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        self.s, self.p, self.lib = v.sheet(), v.project, self.win.library
        self.fu = self.insert("Fuses 3-pole", (5.0, 6.0), "RRR")    # (L1-L3 across at y 6)
        self.mt = self.insert("Motor 3-phase", (5.0, 3.0), "RRR")
        f, m = self.pins(self.fu), self.pins(self.mt)
        with self.p.edit("wires") as ed:
            for y in (9.0, 8.5, 8.0):                                # (the bus)
                ed.add(self.s, M.Wire([(1.0, y), (12.0, y)]))
            for n, y in (("L1", 9.0), ("L2", 8.5), ("L3", 8.0)):     # (drops off it)
                ed.add(self.s, M.Wire([(f[n][0], y), f[n]]))
            for n in ("1", "2", "3"):                                # (fuses to motor)
                ed.add(self.s, M.Wire([f["T" + n], m["T" + n]]))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def insert(self, name, at, keys=""):
        before = set(self.s.entities)
        self.v.run(C.InsertCmd, self.lib.get("symbol", name), {})
        for k in keys:
            self.v.input_text(k)
        type_in(self.v, "%r,%r" % at)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        return [e for i, e in self.s.entities.items() if i not in before and
                isinstance(e, M.Insert)][0]

    def pins(self, e):
        return dict(self.s.entities[e.id].pin_points())

    def scoot(self, e, to, *keys):
        self.v.set_selection({e.id})
        self.v.run(C.ScootCmd)
        for k in keys:
            self.assertTrue(self.v.input_text(k))
        q = self.pins(e)
        first = list(q.values())[0]
        type_in(self.v, "%r,%r" % first, "%r,%r" % (first[0] + to[0], first[1] + to[1]))

    def wired(self, e):
        """Every pin of e has a wire ending on it."""
        return all(any(w.touches(q) for w in self.s.wires()) for q in self.pins(e).values())

    def on_bus(self):
        """Every drop's top end on its bus wire."""
        tops = [w.points[0] for w in self.s.wires() if w.points[0][1] in (9.0, 8.5, 8.0) and
                len(w.points) and w.points[-1][1] < 8.0]
        return len(tops) == 3 and all(
            any(b.touches(t) and abs(b.points[0][1] - t[1]) < 1e-9 for b in self.s.wires()
                if b.points[0][1] == b.points[-1][1]) for t in tops)

    def test_the_motor_brings_its_fuses_and_slides_along_the_bus(self):
        f0, m0 = self.pins(self.fu), self.pins(self.mt)
        self.scoot(self.mt, (2.0, 0.0))
        f1, m1 = self.pins(self.fu), self.pins(self.mt)
        for n in f0:
            self.assertEqual(f1[n], (f0[n][0] + 2.0, f0[n][1]))
        for n in m0:
            self.assertEqual(m1[n], (m0[n][0] + 2.0, m0[n][1]))
        self.assertTrue(self.wired(self.fu) and self.wired(self.mt))
        # the drops moved whole, still straight down from the bus
        drops = [w for w in self.s.wires() if any(w.touches(q) for k, q in f1.items()
                                                  if k.startswith("L"))]
        self.assertEqual(len(drops), 3)
        for w in drops:
            self.assertEqual(len(w.points), 2)
            self.assertEqual(w.points[0][0], w.points[1][0])
        self.assertTrue(self.on_bus())
        self.assertEqual(BC.near_misses(self.s), [])
        # one step
        self.p.undo()
        self.assertEqual(self.pins(self.mt), m0)

    def test_the_fuses_bring_the_motor_and_down_stretches_the_drops(self):
        m0 = self.pins(self.mt)
        self.scoot(self.fu, (0.0, -1.0))
        m1 = self.pins(self.mt)
        for n in m0:
            self.assertEqual(m1[n], (m0[n][0], m0[n][1] - 1.0))
        self.assertTrue(self.wired(self.fu) and self.wired(self.mt))
        self.assertTrue(self.on_bus())
        self.assertEqual(BC.near_misses(self.s), [])

    def test_o_scoots_only_the_one_along_its_wire(self):
        from kanzonascad import scoot
        f0, m0 = self.pins(self.fu), self.pins(self.mt)
        ax = scoot.axis(self.s.entities[self.mt.id])     # (its own wire's way, as before)
        self.scoot(self.mt, (0.25 * ax[0], 0.25 * ax[1]), "O")
        self.assertEqual(self.pins(self.fu), f0)                    # (the fuses stay)
        got = self.pins(self.mt)["T1"]
        self.assertNotEqual(got, m0["T1"])
        self.assertEqual((got[0] - m0["T1"][0]) * ax[1], 0.0)       # (only along it)
        self.assertEqual((got[1] - m0["T1"][1]) * ax[0], 0.0)


if __name__ == "__main__":
    unittest.main()
