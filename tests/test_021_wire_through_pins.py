"""A wire whose route would run through a symbol's pin (anywhere but its two ends) isn't taken:
the command line says which pin, and the wire waits for another click, as a bus has since 0.19.12
(the battery saw a wire run down a PLC module's column of pins, wired to every one of them).
Clicking on the pin ends the wire there, as before."""
import unittest

from tests.util import APP, window

from kanzonascad import commands as C
from kanzonascad import geometry as G
from kanzonascad import model as M


class WireThroughPinsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.p.settings["wire_around"] = False      # (the route straight, as clicked)
        self.s = self.v.sheet()
        self.said = []
        self.v.message = lambda text: self.said.append(text)
        d = self.win.library.get("symbol", "1734-IB8 module")
        with self.p.edit("module") as ed:
            self.mod = ed.add(self.s, M.Insert("1734-IB8 module", (10.0, 10.0), 0.0, 1.0,
                                               False, {"TAG": "PLC1"}, d, 0.1))
        pins = self.s.entities[self.mod.id].pin_points()
        # (a column of pins: the same x, one below the other)
        xs = {}
        for n, q in pins:
            xs.setdefault(round(q[0], 6), []).append((q[1], n, q))
        self.col = sorted(max(xs.values(), key=len), reverse=True)
        self.assertGreaterEqual(len(self.col), 3)

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def through(self):
        pins = [q for _n, q in self.s.entities[self.mod.id].pin_points()]
        return [w for w in self.s.wires() for q in pins
                if w.touches(q) and not any(G.dist(q, e) < 1e-6
                                            for e in (w.points[0], w.points[-1]))]

    def test_down_the_column_is_refused(self):
        top = self.col[0][2]
        below = (top[0], self.col[-1][2][1] - 2.0)
        self.v.run(C.WireCmd)
        self.v.input_text("%r,%r" % top)
        self.v.input_text("%r,%r" % below)
        self.v.enter()
        self.assertEqual(self.through(), [])
        self.assertTrue(any("run through PLC1's pin" in t for t in self.said), self.said)

    def test_ending_on_the_next_pin_is_drawn(self):
        top, nxt = self.col[0][2], self.col[1][2]
        self.v.run(C.WireCmd)
        self.v.input_text("%r,%r" % top)
        self.v.input_text("%r,%r" % nxt)
        self.assertIsNone(self.v.cmd)               # (ended by itself on the pin)
        ws = self.s.wires()
        self.assertEqual(len(ws), 1)
        self.assertEqual({tuple(ws[0].points[0]), tuple(ws[0].points[-1])},
                         {tuple(top), tuple(nxt)})
        self.assertEqual(self.through(), [])

    def test_clear_of_the_pins_is_drawn(self):
        top = self.col[0][2]
        self.v.run(C.WireCmd)
        self.v.input_text("%r,%r" % top)
        self.v.input_text("%r,%r" % (top[0] - 3.0, top[1]))  # (away from the module)
        self.v.enter()
        self.assertEqual(len(self.s.wires()), 1)


class WireToAMiddlePinTest(unittest.TestCase):
    """A wire to any pin of a 3-pole symbol, turned any way, from beyond its far side takes the
    corner that keeps clear of the other pins (the plain route came along the row of pins,
    through L1 into L2: the battery's wire_around, refused once wires through pins were)."""

    def test_every_pin_reached_clear_of_the_others(self):
        from kanzonascad import wires
        win, v = window()
        try:
            v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
            p, s = v.project, v.sheet()
            missed = []
            for name in ("Fuses 3-pole", "Disconnect 3-pole"):
                d = win.library.get("symbol", name)
                for ang in (0.0, 90.0, 180.0, 270.0):
                    for pin_name in [p_["name"] for p_ in d.pins]:
                        for off in (-0.5, 0.5):
                            with p.edit("sym") as ed:
                                e = ed.add(s, M.Insert(d.name, (10.0, 10.0), ang, 1.0, False,
                                                       {"TAG": "X1"}, d, 0.1))
                            e = s.entities[e.id]
                            bb = wires.body_box(e)
                            pins = dict(e.pin_points())
                            q = pins[pin_name]
                            side = min((abs(q[0] - bb[0]), "left"), (abs(q[0] - bb[2]), "right"),
                                       (abs(q[1] - bb[1]), "bottom"), (abs(q[1] - bb[3]), "top"))[1]
                            a = {"left": (bb[2] + 2.0, q[1] + off),
                                 "right": (bb[0] - 2.0, q[1] + off),
                                 "bottom": (q[0] + off, bb[3] + 2.0),
                                 "top": (q[0] + off, bb[1] - 2.0)}[side]
                            before = set(s.entities)
                            v.run(C.WireCmd)
                            v.input_text("%r,%r" % a)
                            v.input_text("%r,%r" % q)
                            v.cancel()
                            new = [w for i_, w in s.entities.items()
                                   if i_ not in before and isinstance(w, M.Wire)]
                            ok = [w for w in new if min(G.dist(q, w.points[0]),
                                                        G.dist(q, w.points[-1])) < 1e-6]
                            through = [n for n, r in pins.items() if n != pin_name and
                                       any(w.touches(r) for w in new)]
                            if not ok or through:
                                missed.append((name, ang, pin_name, off, through))
                            p.undo()
                            if new:
                                p.undo()
            self.assertEqual(missed, [])
            p.saved_at = len(p.undo_stack)
        finally:
            win.close()
        self.assertTrue(APP)


if __name__ == "__main__":
    unittest.main()
