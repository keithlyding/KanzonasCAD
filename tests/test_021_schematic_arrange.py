"""Align objects and Distribute objects on a schematic (the owner, 0.21.2: "I need alignment and
distribution on the schematic sheet too"): on the Schematic tab, and symbols lined up or spread
out keep every wire on their pins, square."""
import unittest

from PySide6.QtWidgets import QToolButton

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class SchematicArrangeTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        coil = self.win.library.get("symbol", "Relay coil")
        self.coils = []
        for at in ((3.0, 7.0), (4.1, 6.0), (6.3, 4.6)):
            before = set(self.v.sheet().entities)
            self.v.run(C.InsertCmd, coil, {})
            type_in(self.v, "%r,%r" % at)
            while self.v.cmd is not None:
                self.v.cmd.enter()
            self.coils += [e for i, e in self.v.sheet().entities.items()
                           if i not in before and isinstance(e, M.Insert)]
        s = self.v.sheet()
        with self.p.edit("rungs") as ed:
            for c in self.coils:
                (_n1, a), (_n2, b) = c.pin_points()[:2]
                ed.add(s, M.Wire([(1.0, a[1]), a]))
                ed.add(s, M.Wire([b, (9.0, b[1])]))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def check_wires(self):
        s = self.v.sheet()
        for w in s.wires():
            for a, b in zip(w.points, w.points[1:]):
                self.assertTrue(abs(a[0] - b[0]) < 1e-9 or abs(a[1] - b[1]) < 1e-9, w.points)
        for c in s.inserts():
            for n, q in c.pin_points():
                self.assertTrue(any(w.touches(q, 1e-9) for w in s.wires()), (n, q))

    def test_on_the_schematic_tab(self):
        r = self.win.ribbon
        page = r.widget(r.tab_index("Schematic")).widget()
        acts = {b.defaultAction() for b in page.findChildren(QToolButton)}
        self.assertIn(self.win.acts["align_obj"], acts)
        self.assertIn(self.win.acts["distribute"], acts)

    def test_lined_up_with_their_wires(self):
        self.v.set_selection({c.id for c in self.coils})
        self.v.run(C.AlignObjectsCmd)
        self.v.input_text("C")
        self.v.enter()
        xs = {round(self.v.sheet().entities[c.id].pos[0], 9) for c in self.coils}
        self.assertEqual(len(xs), 1)
        self.check_wires()

    def test_spread_out_with_their_wires(self):
        self.v.set_selection({c.id for c in self.coils})
        self.v.run(C.DistributeCmd)
        self.v.input_text("V")
        ys = sorted(self.v.sheet().entities[c.id].pos[1] for c in self.coils)
        self.assertAlmostEqual(ys[1] - ys[0], ys[2] - ys[1])
        self.check_wires()


if __name__ == "__main__":
    unittest.main()
