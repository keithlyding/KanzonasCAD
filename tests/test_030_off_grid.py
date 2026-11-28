"""A circuit off the sheet's grid (copied by an odd base point: a placed UDT copied from its
box's corner) keeps its own grid when the program works on it (the long battery, 0.30, seed
5223, a circuit 0.00820803997271" off the grid):
- a bus fanned onto its pins put its runs on the sheet's 1/8" grid, and so 0.0082" beside the
  circuit's own wires, a near miss marked on the drawing (step 2087 on CI);
- a coil typed 0.5" over in the Properties panel, from the 68.7582 it showed to 69.2582, went
  exactly there, 0.000008" beside the wire it was put on (step 1682)."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import nearmiss

OFF = 0.00820803997271


class OffGridTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p, self.s = self.v.project, self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def add(self, *ents):
        with self.p.edit("x") as ed:
            return [ed.add(self.s, e) for e in ents]

    def symbol(self, name, at, angle=0.0):
        d = self.win.library.get("symbol", name)
        with self.p.edit("x") as ed:
            ed.block(d)
        return M.Insert(d.name, at, angle=angle, defn=self.p.blocks[d.name])

    def test_bus_fanned_onto_off_grid_pins_keeps_their_grid(self):
        a, b = self.symbol("Disconnect 3-pole", (0.25, 20.5)), \
            self.symbol("Disconnect 3-pole", (10.0 + OFF, 4.25), 90.0)
        # (one of the circuit's wires, from what is above to the disconnect's middle pole)
        a, b, w = self.add(a, b, M.Wire([(10.0 + OFF, 14.75), (10.0 + OFF, 5.0)]))
        self.assertEqual(nearmiss.found(self.s), [])
        start = dict(a.pin_points())["T1"]
        click = dict(b.pin_points())["L1"]
        before = set(self.s.entities)
        self.v.run(C.BusCmd)
        type_in(self.v, "%r,%r" % start, "%r,%r" % click)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        new = [e for i, e in self.s.entities.items() if i not in before and isinstance(e, M.Wire)]
        self.assertEqual(len(new), 3, [e.points for e in new])
        self.assertEqual(nearmiss.found(self.s), [])
        # (its runs up and down by the pins on the pins' grid: none a hair beside a pole)
        for e in new:
            for q, r in zip(e.points, e.points[1:]):
                if abs(q[0] - r[0]) < 1e-9 and q[1] < 15.0:
                    off = (q[0] - OFF) / 0.125
                    self.assertAlmostEqual(off, round(off), 6, e.points)

    def test_position_typed_in_properties_keeps_what_it_doesnt_show(self):
        coil, wire = self.add(self.symbol("Contactor coil", (68.75 + OFF, 1747.75), 90.0),
                              M.Wire([(69.25 + OFF, 1746.75), (69.25 + OFF, 1748.0)]))
        self.v.set_selection({coil.id})
        if self.win.props_dock.isHidden():
            self.win.properties()
        self.win._props_wait.stop()
        self.win.props_fill()
        x = self.win.props_panel.widgets["x"]
        self.assertEqual(round(x.value(), 4), 68.7582)
        x.setValue(69.2582)             # (typed and left, as a user does)
        x.editingFinished.emit()
        got = self.s.entities[coil.id]
        self.assertAlmostEqual(got.pos[0], 69.25 + OFF, 9)
        self.assertEqual(got.pos[1], 1747.75)
        # (its pin on the wire's end: joined, no near miss)
        self.assertEqual(nearmiss.found(self.s), [])
        # (typed on the grid where it is on the grid: exactly what was typed)
        x2 = self.add(self.symbol("Contactor coil", (2.0, 3.0)))[0]
        self.v.set_selection({x2.id})
        self.win._props_wait.stop()
        self.win.props_fill()
        x = self.win.props_panel.widgets["x"]
        x.setValue(2.5)
        x.editingFinished.emit()
        self.assertEqual(self.s.entities[x2.id].pos, (2.5, 3.0))


if __name__ == "__main__":
    unittest.main()
