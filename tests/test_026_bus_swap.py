"""Bus to devices: phases 1 and 3 swapped (the owner, 0.26: "Bus to devices: swap phases 1 and
3", to run a motor backward). W while drawing a bus (or the right-click menu's Swap 1 and 3)
lands L1 on the device's third pin and L3 on its first, the two wires crossing over just
before the pins in square steps (every crossing a plain cross: no wire on another, no joint),
shown in the rubber band before the click. Each phase's wire is one wire from its source pin
to the pin it lands on, so its wire number and its layer follow it."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import geometry as G
from kanzonascad import model as M
from kanzonascad import wires


class BusSwapTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p, self.s = self.v.project, self.v.sheet()
        self.msgs = []
        self.v.messaged.connect(self.msgs.append)
        self.cb = self.insert("Circuit breaker 3-pole", (2.0, 8.0))
        self.mtr = self.insert("Motor 3-phase", (8.0, 2.0))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def insert(self, name, at, keys=()):
        before = set(self.s.entities)
        self.v.run(C.InsertCmd, self.win.library.get("symbol", name), {})
        for k in keys:
            self.v.input_text(k)
        type_in(self.v, "%r,%r" % at)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        return [e for i, e in self.s.entities.items()
                if i not in before and isinstance(e, M.Insert)][0]

    def landed_on(self):
        """{source pin: (device tag, pin)} for every wire from the breaker's T pins."""
        out = {}
        for w in self.s.wires():
            a = [n for x, n in wires.pins_on(self.s, w.points[0]) if x.id == self.cb.id]
            b = [(x.attrs["TAG"], n) for x, n in wires.pins_on(self.s, w.points[-1])
                 if x.id == self.mtr.id]
            if a and b:
                out[a[0]] = b[0]
        return out

    def bus(self, *typed, to="T2"):
        self.v.run(C.BusCmd)
        type_in(self.v, "2.5,8.0", *typed)
        type_in(self.v, "%r,%r" % dict(self.mtr.pin_points())[to])

    def test_lands_l1_on_the_third_pin_and_l3_on_the_first(self):
        tag = self.mtr.attrs["TAG"]
        self.bus("W")
        self.assertIsNone(self.v.cmd)
        self.assertEqual(self.landed_on(), {"T1": (tag, "T3"), "T2": (tag, "T2"),
                                            "T3": (tag, "T1")})
        self.assertEqual(len(self.s.wires()), 3)
        self.assertTrue(any("swapped" in m for m in self.msgs), self.msgs)
        self.check_crossings_plain()

    def test_in_order_without_it_and_w_twice_is_off(self):
        tag = self.mtr.attrs["TAG"]
        self.bus("W", "W")
        self.assertEqual(self.landed_on(), {"T1": (tag, "T1"), "T2": (tag, "T2"),
                                            "T3": (tag, "T3")})

    def check_crossings_plain(self):
        """No end of a bus wire on another bus wire, no two lying on each other: the crossings
        are plain crosses (no connection)."""
        ws = self.s.wires()
        for w in ws:
            for o in ws:
                if o is w:
                    continue
                for q in (w.points[0], w.points[-1]):
                    self.assertGreater(min(G.dist_to_segment(q, a, b) for a, b in
                                           zip(o.points, o.points[1:])), 0.01)
                for a, b in zip(w.points, w.points[1:]):
                    for c, d in zip(o.points, o.points[1:]):
                        u = (b[0] - a[0], b[1] - a[1])
                        x = (d[0] - c[0], d[1] - c[1])
                        if abs(u[0] * x[1] - u[1] * x[0]) < 1e-12:
                            # (parallel: never on one line overlapping)
                            off = abs((c[0] - a[0]) * u[1] - (c[1] - a[1]) * u[0])
                            if off < 1e-9:
                                t = [((q[0] - a[0]) * u[0] + (q[1] - a[1]) * u[1]) /
                                     (u[0] ** 2 + u[1] ** 2) for q in (c, d)]
                                self.assertTrue(max(t) <= 1e-9 or min(t) >= 1 - 1e-9,
                                                "%r lies on %r" % ((c, d), (a, b)))

    def test_shown_in_the_rubber_band_before_the_click(self):
        self.v.run(C.BusCmd)
        type_in(self.v, "2.5,8.0")
        pins = dict(self.mtr.pin_points())
        plain = self.v.cmd.preview(pins["T2"])
        self.assertEqual([w.points[-1] for w in plain], [pins["T1"], pins["T2"], pins["T3"]])
        self.assertIn(("Swap 1 and 3", "W"), self.v._prompt[1])
        type_in(self.v, "W")
        self.assertIn(("Phases in order", "W"), self.v._prompt[1])
        got = self.v.cmd.preview(pins["T2"])
        self.assertEqual([w.points[-1] for w in got], [pins["T3"], pins["T2"], pins["T1"]])
        self.assertEqual([w.points[0] for w in got], [w.points[0] for w in plain])
        self.v.escape()

    def test_the_right_click_menu(self):
        self.v.run(C.BusCmd)
        type_in(self.v, "2.5,8.0")
        items = self.v.command_menu_items()
        self.assertEqual(items[0], ("Enter", ""))
        self.assertEqual(items[-1], ("Cancel", None))
        self.assertIn(("Swap 1 and 3  (W)", "W"), items)
        self.v.command_menu_pick("W")
        self.assertTrue(self.v.cmd.swap)
        self.v.command_menu_pick(None)
        self.assertIsNone(self.v.cmd)
        self.assertEqual(self.s.wires(), [])

    def test_wire_numbers_and_layers_follow_the_phases(self):
        tag = self.mtr.attrs["TAG"]
        self.v._bus_layers = ["480V BRN", "480V ORG", "480V YEL"]
        self.bus("W")
        on = self.landed_on()
        self.assertEqual(on["T1"], (tag, "T3"))
        nums = {}
        for w in self.s.wires():
            a = [n for x, n in wires.pins_on(self.s, w.points[0]) if x.id == self.cb.id]
            b = [n for x, n in wires.pins_on(self.s, w.points[-1]) if x.id == self.mtr.id]
            nums[(a[0], b[0])] = (w.num, w.layer)
        self.assertEqual(set(nums), {("T1", "T3"), ("T2", "T2"), ("T3", "T1")})
        # (each phase its own number, the one on both its ends: one wire)
        self.assertEqual(len({n for n, _l in nums.values()}), 3)
        self.assertTrue(all(n for n, _l in nums.values()))
        self.assertEqual(nums[("T1", "T3")][1], "480V BRN")
        self.assertEqual(nums[("T3", "T1")][1], "480V YEL")
        # undone in one step
        self.p.undo()
        self.assertEqual(self.s.wires(), [])

    def test_fanned_onto_pins_spaced_otherwise(self):
        # (a bus 3/4" apart, from nowhere in particular, ended near the motor: it fans onto
        # its nearest three pins, 1/2" apart, each wire jogging over to its own)
        self.v.run(C.BusCmd)
        type_in(self.v, "D", "0.75", "1.0,6.0", "W")
        bb = wires.body_box(self.mtr)
        type_in(self.v, "%r,%r" % (bb[2] - 0.2, (bb[1] + bb[3]) / 2))
        self.assertIsNone(self.v.cmd, self.msgs)
        starts = sorted(w.points[0] for w in self.s.wires())
        self.assertEqual(len(starts), 3)
        self.assertAlmostEqual(G.dist(starts[0], starts[1]), 0.75)
        got = {}
        for w in self.s.wires():
            b = [n for x, n in wires.pins_on(self.s, w.points[-1]) if x.id == self.mtr.id]
            got[w.points[0]] = b[0] if b else None
        self.check_crossings_plain()
        # (the first wire, as the bus's wires go, on the third pin; without W on the first)
        plain = self.plain_fan()
        self.assertEqual({k: {"T1": "T3", "T3": "T1"}.get(x, x) for k, x in plain.items()}, got)

    def plain_fan(self):
        """The same bus as test_fanned_onto_pins_spaced_otherwise's without W, undone after:
        {its wires' starts: the pin each lands on}."""
        n = len(self.p.undo_stack)
        self.p.undo()
        self.v.run(C.BusCmd)
        type_in(self.v, "D", "0.75", "1.0,6.0")
        bb = wires.body_box(self.mtr)
        type_in(self.v, "%r,%r" % (bb[2] - 0.2, (bb[1] + bb[3]) / 2))
        out = {}
        for w in self.s.wires():
            b = [n for x, n in wires.pins_on(self.s, w.points[-1]) if x.id == self.mtr.id]
            out[w.points[0]] = b[0] if b else None
        self.assertEqual(sorted(out.values()), ["T1", "T2", "T3"])
        self.p.undo()
        self.assertEqual(len(self.p.undo_stack), n - 1)
        return out

    def test_no_room_is_refused_and_said(self):
        # (a bus turning onto the pins a quarter inch out: no room to cross over)
        self.v.run(C.BusCmd)
        pins = dict(self.mtr.pin_points())
        type_in(self.v, "2.5,8.0", "%r,%r" % (pins["T1"][0] - 0.25, 4.0), "W")
        n = len(self.s.wires())
        type_in(self.v, "%r,%r" % pins["T1"])
        self.assertIsNotNone(self.v.cmd)            # (still drawing: click farther out)
        self.assertEqual(len(self.s.wires()), n)
        self.assertTrue(any("straight run" in m for m in self.msgs), self.msgs)
        type_in(self.v, "W")
        type_in(self.v, "%r,%r" % pins["T1"])
        self.assertIsNone(self.v.cmd)
        self.assertEqual(len(self.s.wires()), 3)

    def test_only_three_wires_or_more(self):
        self.v.run(C.BusCmd)
        type_in(self.v, "N", "2", "", "1,1")
        self.assertNotIn("W", [k for _l, k in self.v._prompt[1]])
        type_in(self.v, "W")
        self.assertFalse(self.v.cmd.swap)
        self.v.escape()


if __name__ == "__main__":
    unittest.main()
