"""Found by the battery (0.17.5, seed 12): a bus started off two wires, clicked beside a drive's
control terminals turned over, fanned onto its nearest pins with a wire that jogged back over
its own leg (a hidden fold, a dot with nothing tapped off). A fan with such a wire isn't
taken."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wires


class BusFanNoFoldTest(unittest.TestCase):
    def test_no_wire_doubles_back(self):
        win, v = window()
        try:
            v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
            s, p = v.sheet(), v.project
            # (a bus off two wires 5" apart, clicked beside a drive's control terminals
            # turned over: the battery's sheet, the pieces that matter)
            d = win.library.get("symbol", "Drive control terminals")
            with p.edit("x") as ed:
                ed.block(d)
                ed.add(s, M.Insert(d.name, (10.75, 2.0), 0.0, 1.0, True,
                                   defn=p.blocks[d.name]))
                ed.add(s, M.Wire([(9.5, 2.0), (9.5, 9.75), (5.5, 9.75)]))
                ed.add(s, M.Wire([(14.5, 4.0), (14.5, 7.0), (9.75, 7.0), (9.75, 7.25)]))
            v.run(C.BusCmd)
            type_in(v, "9.5,6.0", "12.5,4.0")
            while v.cmd is not None:
                v.cmd.enter()
            self.assertEqual([w.points for w in s.wires() if wires.doubles_back(w.points)], [])
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()


    def test_a_wider_bus_onto_closer_poles_has_no_dead_end_jog(self):
        # (a 3/4" bus onto a fuse block's 1/2" poles: a wire jogged over and straight back
        # along the same line before it went on to its pin)
        win, v = window()
        try:
            v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
            s, p = v.sheet(), v.project
            d = win.library.get("symbol", "Fuses 3-pole")
            with p.edit("x") as ed:
                ed.block(d)
                fu = ed.add(s, M.Insert(d.name, (12.0, 4.0), defn=p.blocks[d.name]))
            v.run(C.BusCmd)
            v.input_text("D")
            v.input_text("0.75")
            type_in(v, "9.0,4.0", "%r,%r" % dict(fu.pin_points())["L1"])
            while v.cmd is not None:
                v.cmd.enter()
            ends = {tuple(q) for w in s.wires() for q in (w.points[0], w.points[-1])}
            self.assertTrue(all(tuple(q) in ends for n, q in fu.pin_points()
                                if n.startswith("L")))
            self.assertEqual([w.points for w in s.wires() if wires.doubles_back(w.points)], [])
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()


class ScootPinOnWireTest(unittest.TestCase):
    """Found by the battery (0.17.5, seed 12): a wire from a device's pin to a loose end with a
    pushbutton's pin on its middle (not cut there); scooting the device with what's attached
    moved that wire whole and left the pushbutton's pin on nothing. The pushbutton comes too."""

    def test_a_symbol_on_a_wire_that_moves_comes_along(self):
        from kanzonascad import scoot
        win, v = window()
        try:
            s, p = v.sheet(), v.project
            coil = win.library.get("symbol", "Relay coil")
            pb = win.library.get("symbol", "Pushbutton NO")
            with p.edit("x") as ed:
                ed.block(coil)
                ed.block(pb)
                c = ed.add(s, M.Insert(coil.name, (5.0, 5.0), defn=p.blocks[coil.name]))
                a2 = max((q for _n, q in c.pin_points()), key=lambda q: q[0])
                ed.add(s, M.Wire([a2, (12.0, a2[1])]))             # (to a loose end)
                b = ed.add(s, M.Insert(pb.name, (0.0, 0.0), 90.0, 1.0, False,
                                       defn=p.blocks[pb.name]))
                q = b.pin_points()[0][1]
                b = b.moved(9.0 - q[0], a2[1] - q[1])               # (pin 1 on its middle)
                ed.change(s, b)
            got = scoot.branch_moved(s, [s.entities[c.id]], 0.0, 0.5)
            self.assertIsNotNone(got)
            ids = {x.id for x in got}
            self.assertIn(b.id, ids)                                 # (it comes along)
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()


if __name__ == "__main__":
    unittest.main()
