"""Bus wires leave a pin that already has a wire on a 45-degree lead, as a single wire does
(the owner, 0.18.5: drops tapped off a disconnect's line side with Bus came straight off the
pins though "A second wire on a pin leaves it on a 45-degree lead" was on)."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class BusLeadTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p, self.s = self.v.project, self.v.sheet()
        ds = self.win.library.get("symbol", "Disconnect 3-pole")
        with self.p.edit("x") as ed:
            ed.block(ds)
            ins = ed.add(self.s, M.Insert(ds.name, (10.0, 8.0), defn=self.p.blocks[ds.name]))
        self.line = [q for _n, q in self.s.entities[ins.id].pin_points()][:3]
        with self.p.edit("in") as ed:
            for q in self.line:
                ed.add(self.s, M.Wire([(2.0, q[1]), q]))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def bus(self):
        before = set(self.s.entities)
        a = self.line[0]
        self.v.run(C.BusCmd)
        type_in(self.v, "%r,%r" % a, "%r,%r" % (a[0] - 3, a[1]), "%r,%r" % (a[0] - 3, 3.0))
        if self.v.cmd is not None:
            self.v.cmd.enter()
        return [e for i, e in self.s.entities.items() if i not in before]

    def test_leads_with_the_setting_on(self):
        with self.p.edit("on") as ed:
            ed.project_settings({"wire_lead": True})
        new = self.bus()
        self.assertEqual(len(new), 3)
        for w in new:
            a, b = w.points[0], w.points[1]
            self.assertIn(tuple(a), [tuple(q) for q in self.line])      # (on its pin)
            dx, dy = abs(b[0] - a[0]), abs(b[1] - a[1])
            self.assertAlmostEqual(dx, dy, places=9)                    # (45 degrees)
            self.assertGreater(dx, 0.0)
        # (the leads side by side, not crossing: each runs beside its own incoming wire)
        ys = sorted(w.points[1][1] for w in new)
        self.assertEqual(len(set(round(y, 6) for y in ys)), 3)

    def test_straight_with_it_off(self):
        new = self.bus()
        for w in new:
            a, b = w.points[0], w.points[1]
            self.assertTrue(abs(a[0] - b[0]) < 1e-9 or abs(a[1] - b[1]) < 1e-9)


if __name__ == "__main__":
    unittest.main()
