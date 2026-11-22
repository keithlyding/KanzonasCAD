"""A bus's last spacing is the same on paper on a sheet of another scale, and a bus with no way
round a symbol says so and draws nothing, not through it (the battery, seed 433: a bus 24" wide
clicked 3" from a drive's control terminals ran straight through them)."""
import unittest

from tests.util import APP, window

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wires


class BusSpacingScaleTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.one = self.v.sheet()
        self.win.add_sheet()
        self.four = self.v.sheet()
        with self.p.edit("scale") as ed:
            ed.sheet_scale(self.four, 0.25)
        self.assertAlmostEqual(self.four.k(), 4.0)

    def tearDown(self):
        if self.v.cmd is not None:
            self.v.cancel()
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def spacing_on(self, sheet):
        self.v.show_sheet(sheet.id)
        self.v.run(C.BusCmd)
        got = self.v.cmd.spacing
        self.v.cancel()
        return got

    def test_the_same_on_paper_on_every_sheet(self):
        self.assertAlmostEqual(self.spacing_on(self.one), 0.5)
        self.assertAlmostEqual(self.spacing_on(self.four), 2.0)     # (1/2" on paper at 1:4)
        self.assertAlmostEqual(self.spacing_on(self.one), 0.5)      # (and back)
        self.assertAlmostEqual(self.spacing_on(self.one), 0.5)      # (not growing each time)


    def drive_and_bus(self, spacing):
        """A drive's control terminals at (50, 50), then a 3-wire bus clicked across them from
        3" out on each side: (the drive, its box, the new wires, what was said)."""
        v, s = self.v, self.one
        v.show_sheet(s.id)
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        before = set(s.entities)
        v.run(C.InsertCmd, self.win.library.get("symbol", "Drive control terminals"), {})
        v.input_text("50,50")
        if v.cmd is not None:
            v.cancel()
        e = [x for i, x in s.entities.items() if i not in before and isinstance(x, M.Insert)][0]
        bb = wires.body_box(e)
        y = (bb[1] + bb[3]) / 2 - 0.25
        said = []
        v.message = lambda text: said.append(text)
        try:
            v._bus_count, v._bus_spacing, v._bus_k = 3, spacing, 1.0
            before = set(s.entities)
            v.run(C.BusCmd)
            v.input_text("F")
            v.input_text("%g,%g" % (bb[0] - 3.0, y))
            if v.cmd is not None:
                v.input_text("%g,%g" % (bb[2] + 3.0, y))
            if v.cmd is not None:
                v.cmd.enter()
            if v.cmd is not None:
                v.cancel()
        finally:
            del v.message
        new = [w for i, w in s.entities.items() if i not in before and isinstance(w, M.Wire)]
        return e, bb, new, said

    def test_never_through_a_symbol(self):
        for spacing in (0.25, 0.5, 2.0, 12.0):
            e, bb, new, said = self.drive_and_bus(spacing)
            self.assertFalse([w for w in new if wires._crosses(w.points, [(e, bb)])], spacing)
            self.assertTrue(new or any("can't go round" in t for t in said), spacing)
            self.p.undo()                       # (the bus, then the drive)
            if new:
                self.p.undo()

    def test_no_way_round_says_so_and_draws_nothing(self):
        real = wires.route_around
        try:
            wires.route_around = lambda sheet, a, b, plain, *args, **kw: plain   # (none found)
            e, bb, new, said = self.drive_and_bus(0.5)
        finally:
            wires.route_around = real
        self.assertEqual(new, [])
        self.assertTrue(any("can't go round Drive control terminals" in t for t in said), said)


if __name__ == "__main__":
    unittest.main()
