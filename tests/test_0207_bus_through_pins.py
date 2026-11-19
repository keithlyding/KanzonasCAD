"""A bus whose wires would run through a symbol's pins (anywhere but their ends) isn't drawn:
the command line says which pin, and the bus waits for another click (the battery, 0.19.11,
seed 152: a bus left a turned disconnect's T pins straight through its L pins, then carried on
through a breaker it couldn't land on; later buses onto those pins were dropped as drawn twice)."""
import unittest

from tests.util import APP, window

from kanzonascad import commands as C
from kanzonascad import geometry as G
from kanzonascad import model as M


class BusThroughPinsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.s = self.v.sheet()
        self.said = []
        self.v.message = lambda text: self.said.append(text)
        d = self.win.library.get("symbol", "Disconnect 3-pole")
        with self.p.edit("parts") as ed:
            # (turned a quarter: its L pins and T pins in the same three columns)
            self.dis = ed.add(self.s, M.Insert("Disconnect 3-pole", (5.0, 5.0), 90.0, 1.0,
                                               False, {"TAG": "DS1"}, d, 0.1))
        self.pins = dict(self.s.entities[self.dis.id].pin_points())

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def wires_through(self):
        return [w for w in self.s.wires() for q in self.pins.values()
                if w.touches(q) and not any(G.dist(q, e) < 1e-6 for e in (w.points[0],
                                                                            w.points[-1]))]

    def test_leaving_through_its_own_pins_is_refused(self):
        t1, l1 = self.pins["T1"], self.pins["L1"]
        way = (l1[0] - t1[0], l1[1] - t1[1])                    # (from T through L and on)
        far = (t1[0] + 6 * way[0], t1[1] + 6 * way[1])
        self.v.run(C.BusCmd)
        self.v.input_text("%r,%r" % t1)
        self.v.input_text("%r,%r" % far)
        self.assertEqual(self.wires_through(), [])
        self.assertTrue(any("run through DS1's pin L" in t for t in self.said), self.said)
        self.assertIsNotNone(self.v.cmd)                        # (waiting for another click)
        self.v.cancel()                                         # (Esc: nothing drawn)
        self.assertEqual(self.wires_through(), [])

    def test_a_bus_clear_of_pins_is_drawn(self):
        t1, l1 = self.pins["T1"], self.pins["L1"]
        way = (t1[0] - l1[0], t1[1] - l1[1])                    # (from T away from L)
        far = (t1[0] + 6 * way[0], t1[1] + 6 * way[1])
        self.v.run(C.BusCmd)
        self.v.input_text("%r,%r" % t1)
        self.v.input_text("%r,%r" % far)
        self.v.enter()
        self.assertEqual(len(self.s.wires()), 3)
        self.assertEqual(self.wires_through(), [])

    def test_through_pins_finds_a_middle_not_an_end(self):
        a, t = self.pins["L2"], self.pins["T2"]
        out = (a[0] - t[0], a[1] - t[1])                         # (out of the L side)
        beyond = (a[0] + 3 * out[0], a[1] + 3 * out[1])
        through = (t[0] - 3 * out[0], t[1] - 3 * out[1])
        self.assertEqual(C._through_pins(self.s, [[beyond, through]])[1], "L2")
        self.assertIsNone(C._through_pins(self.s, [[beyond, a]]))      # (ends on it)


if __name__ == "__main__":
    unittest.main()
