"""0.16.7, the owner: "Bus needs to go around objects as well"; "is there a way I can adjust
the clearance distance, like change to 1/4 inch instead?"; "am I able to drag a wire left or
right if it's vertical or up-and-down if it's horizontal, and then the rest of the wires will
automatically reconnect to it in its new location? ... I believe it's also called scoot"."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wires as W


class BusAroundRunsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        self.s, self.p = v.sheet(), v.project
        self.said = []
        v.messaged.connect(self.said.append)

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def box(self, at=(4.0, 3.0)):
        d = M.BlockDef("Box", "symbol", [M.Polyline([(0, 0), (3, 0), (3, 2), (0, 2)], True)],
                       [{"name": "1", "pos": (0, 1)}], (1.5, 2.2), 0.1, "", "", "device", "",
                       "X")
        self.v.run(C.InsertCmd, d, {})
        self.v.cmd.hold = 1
        type_in(self.v, "%r,%r" % at)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        return self.s.inserts()[-1]

    def through(self, ents, box):
        return any(W._crosses(w.points, [(box, W.body_box(box))]) for w in ents)

    def test_a_bus_goes_round_a_symbol_either_side(self):
        box = self.box()
        for flip in (False, True):
            before = set(self.s.entities)
            self.v.run(C.BusCmd)
            if flip:
                self.v.input_text("F")
            type_in(self.v, "5.5,8", "5.5,1")
            self.v.cmd.enter()
            new = [e for i, e in self.s.entities.items() if i not in before]
            self.assertEqual(len(new), 3)
            self.assertFalse(self.through(new, box), [w.points for w in new])
            self.p.undo()

    def test_a_bus_whose_first_wire_just_misses_goes_round(self):
        # (the battery, seed 8, on a 1:6 sheet: the first wire passed beside the symbol, the
        # other two through it, and the bus went straight through)
        box = self.box()                                # (x 4..7, y 3..5)
        for flip in (False, True):
            x = 7.25 if not flip else 3.75              # (the first wire beside it, the others
            before = set(self.s.entities)               # toward it)
            self.v.run(C.BusCmd)
            if flip:
                self.v.input_text("F")
            type_in(self.v, "%r,8" % x, "%r,1" % x)
            self.v.cmd.enter()
            new = [e for i, e in self.s.entities.items() if i not in before]
            self.assertEqual(len(new), 3)
            self.assertTrue(any(abs(w.points[0][0] - x) < 1e-9 for w in new))
            self.assertFalse(self.through(new, box), [w.points for w in new])
            self.p.undo()

    def test_the_clearance_is_a_setting(self):
        box = self.box()
        got = {}
        for clear in (0.125, 0.25):
            with self.p.edit("clear") as ed:
                ed.project_settings({"wire_clear": clear})
            self.v.run(C.WireCmd)
            type_in(self.v, "5.5,8", "5.5,1")
            self.v.cmd.enter()
            w = self.s.wires()[-1]
            got[clear] = min(abs(q[0] - 4.0) for q in w.points if q[0] < 4.0)
            self.p.undo()
        self.assertAlmostEqual(got[0.125], 0.125)
        self.assertAlmostEqual(got[0.25], 0.25)
        del box

    def wires_(self):
        with self.p.edit("w") as ed:
            a = ed.add(self.s, M.Wire([(1, 8), (4, 8), (4, 3), (7, 3)]))
            t = ed.add(self.s, M.Wire([(4, 6), (8, 6)]))
            c = ed.add(self.s, M.Wire([(4, 8), (4, 10)]))
        return a, t, c

    def test_drag_a_run_and_the_wires_on_it_follow(self):
        a, t, c = self.wires_()
        self.v.run(C.GripCmd, a, len(a.points) + 1)        # (the middle of its vertical run)
        type_in(self.v, "5.5,5")
        self.assertEqual(self.s.entities[a.id].points,
                         [(1.0, 8.0), (5.5, 8.0), (5.5, 3.0), (7.0, 3.0)])
        self.assertEqual(self.s.entities[t.id].points, [(5.5, 6.0), (8.0, 6.0)])     # (a T)
        self.assertEqual(self.s.entities[c.id].points, [(5.5, 8.0), (5.5, 10.0)])    # (on)
        self.p.undo()
        self.assertEqual(self.s.entities[a.id].points, a.points)

    def test_scoot_drags_a_run_too(self):
        a, t, _c = self.wires_()
        self.v.set_selection({a.id})
        self.v.run(C.ScootCmd)
        self.v.cmd.pick((4.0, 5.0))
        type_in(self.v, "2.5,5")
        self.assertEqual(self.s.entities[a.id].points[1:3], [(2.5, 8.0), (2.5, 3.0)])
        self.assertEqual(self.s.entities[t.id].points[0], (2.5, 6.0))

    def test_a_run_ending_on_a_pin_keeps_it_with_a_jog(self):
        self.v.run(C.InsertCmd, self.win.library.get("symbol", "Relay coil"), {})
        type_in(self.v, "2,1")
        while self.v.cmd is not None:
            self.v.cmd.enter()
        a1 = dict(self.s.inserts()[0].pin_points())["A1"]
        with self.p.edit("w") as ed:
            x = ed.add(self.s, M.Wire([a1, (a1[0] - 1, a1[1])]))
        self.v.run(C.GripCmd, x, 2)
        type_in(self.v, "1,1.5")
        self.assertEqual(self.s.entities[x.id].points[0], a1)
        self.assertEqual(self.s.entities[x.id].points[1:], [(a1[0], 1.5), (a1[0] - 1, 1.5)])

    def test_a_run_through_a_pin_is_not_moved(self):
        self.v.run(C.InsertCmd, self.win.library.get("symbol", "Relay coil"), {})
        type_in(self.v, "2,1")
        while self.v.cmd is not None:
            self.v.cmd.enter()
        a1 = dict(self.s.inserts()[0].pin_points())["A1"]
        with self.p.edit("w") as ed:
            x = ed.add(self.s, M.Wire([(a1[0] - 1, a1[1]), (a1[0] + 1, a1[1])]))
        x = self.s.entities[x.id]
        self.v.run(C.GripCmd, x, len(x.points))
        type_in(self.v, "1,1.5")
        self.assertEqual(self.s.entities[x.id].points, x.points)
        self.assertIn("would leave a symbol's pin", self.said[-1])

    def test_a_run_dragged_past_the_end_of_its_neighbour_keeps_the_pins_on_it(self):
        # (the battery, seed 31: a short run dragged far down past the end of the long run
        # beside it, which shrank and turned over, leaving the two pins on it)
        self.v.run(C.InsertCmd, self.win.library.get("symbol", "Relay coil"), {})
        self.v.input_text("R")
        type_in(self.v, "7.5,3")
        while self.v.cmd is not None:
            self.v.cmd.enter()
        pins = [q for _n, q in self.s.inserts()[0].pin_points()]
        with self.p.edit("w") as ed:
            x = ed.add(self.s, M.Wire([(8.0, 8.5), (7.5, 8.5), (7.5, -2.0)]))
        x = self.s.entities[x.id]
        self.assertTrue(all(x.touches(q) for q in pins), pins)
        self.v.run(C.GripCmd, x, len(x.points))              # (the short run across)
        type_in(self.v, "7.75,-10")
        self.assertEqual(self.s.entities[x.id].points, x.points)
        self.assertIn("would leave a symbol's pin", self.said[-1])
        # dragged less far, it moves
        self.v.run(C.GripCmd, x, len(x.points))
        type_in(self.v, "7.75,6")
        self.assertEqual(self.s.entities[x.id].points[:2], [(8.0, 6.0), (7.5, 6.0)])

    def test_the_settings_window_has_the_clearance(self):
        from PySide6.QtWidgets import QDoubleSpinBox
        from kanzonascad import dialogs
        seen = {}
        real = dialogs.QDialog.exec

        def look(dlg):
            box = dlg.findChild(QDoubleSpinBox, "wire_clear")
            seen["v"] = box.value() if box else None
            return dialogs.QDialog.Rejected
        dialogs.QDialog.exec = look
        try:
            self.win.project_properties(1)
        finally:
            dialogs.QDialog.exec = real
        self.assertEqual(seen.get("v"), 0.125)


if __name__ == "__main__":
    unittest.main()
