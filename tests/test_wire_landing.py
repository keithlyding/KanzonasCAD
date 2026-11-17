"""Wires and buses landing where they should (the owner: "When connecting bus wires or single
wires between components, will wires automatically snap to the correct location?", then "Yes,
add all four"):

1. Drawing a wire or bus, pins and wire ends pull the point onto them even with Object snap
   off, and a symbol's insertion point (its middle) never does.
2. A wire end that stops just short of a pin or wire without joining it is marked and named
   on the command line.
3. A bus that can't land wire for wire on a symbol's pins says why (how many, how far apart,
   the poles the other way, the side facing away).
4. A bus between two symbols' pins takes a Z (leaving square and arriving square) to land
   wire for wire, each wire on its own pin in order and none crossing another."""
import unittest

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import crossings as X
from kanzonascad import model as M
from kanzonascad import geometry as G


class WireLandingTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        self.lib = self.win.library
        self.said = []
        v.messaged.connect(self.said.append)

    def tearDown(self):
        p = self.v.project
        p.saved_at = len(p.undo_stack)
        self.win.close()

    def insert(self, name, at, keys=""):
        s = self.v.sheet()
        before = set(s.entities)
        self.v.run(C.InsertCmd, self.lib.get("symbol", name), {})
        for k in keys:
            self.v.input_text(k)
        type_in(self.v, "%r,%r" % at)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        return [e for i, e in s.entities.items() if i not in before and isinstance(e, M.Insert)][0]

    def pins(self, e):
        return dict(self.v.sheet().entities[e.id].pin_points())

    def click_near(self, q, dx_px=3):
        """Resolve a mouse click a few pixels off q, as the view does."""
        v = self.v
        c = v.to_screen(q)
        return v.resolve(v.to_world(QPointF(c.x() + dx_px, c.y() - dx_px)))

    # 1 ------------------------------------------------------------------------------------
    def test_a_wire_lands_on_a_pin_with_object_snap_off(self):
        v = self.v
        e = self.insert("Contact NO", (5.0, 5.0), "B")      # (held by pin 2)
        pin1 = self.pins(e)["1"]
        v.center, v.scale = pin1, 100.0
        v.run(C.WireCmd)
        self.assertEqual(self.click_near(pin1), pin1)
        v.cancel()
        # outside a wire or bus, Object snap off means off
        v.run(C.LineCmd)
        self.assertNotEqual(self.click_near(pin1), pin1)
        v.cancel()

    def test_a_symbols_middle_is_never_a_wire_target(self):
        v = self.v
        v.osnap_on = True
        e = self.insert("Relay coil", (5.0, 5.0), "B")
        mid = self.v.sheet().entities[e.id].pos
        v.center, v.scale = mid, 100.0
        v.run(C.LineCmd)
        self.assertEqual(self.click_near(mid, 2), mid)          # (Insert snap, outside wires)
        v.cancel()
        v.run(C.WireCmd)
        self.assertNotEqual(self.click_near(mid, 2), mid)
        v.cancel()

    # 2 ------------------------------------------------------------------------------------
    def test_a_wire_ending_just_short_of_a_pin_is_marked(self):
        v = self.v
        e = self.insert("Contact NO", (5.0, 5.0))
        p2 = self.pins(e)["2"]
        v.run(C.WireCmd)
        type_in(v, "%r,%r" % (p2[0] + 2.0, p2[1]), "%r,%r" % (p2[0] + 0.01, p2[1]))
        v.enter()
        self.assertTrue(any("short of pin 2" in t for t in self.said), self.said)
        self.assertEqual(len(v.miss_marks[2]), 1)
        # exactly on it: nothing
        self.v.project.undo()
        self.said.clear()
        v.run(C.WireCmd)
        type_in(v, "%r,%r" % (p2[0] + 2.0, p2[1]), "%r,%r" % p2)
        self.assertFalse(any("short of" in t for t in self.said), self.said)
        self.assertEqual(v.miss_marks[2], [])

    def test_the_mark_goes_with_the_next_change(self):
        v = self.v
        e = self.insert("Contact NO", (5.0, 5.0))
        p2 = self.pins(e)["2"]
        v.run(C.WireCmd)
        type_in(v, "%r,%r" % (p2[0] + 2.0, p2[1]), "%r,%r" % (p2[0] + 0.01, p2[1]))
        v.enter()
        sid, version, marks = v.miss_marks
        self.assertTrue(marks)
        with v.project.edit("line") as ed:
            ed.add(v.sheet(), M.Line((0.0, 0.0), (1.0, 0.0)))
        self.assertNotEqual(v.sheet().version, version)
        v.grab()                                            # (paints: no mark, no error)

    # 3 ------------------------------------------------------------------------------------
    def bus_from(self, start):
        cmd = self.v.run(C.BusCmd)
        type_in(self.v, "%r,%r" % start)
        return cmd

    def test_a_bus_says_why_it_cant_land(self):
        ds = self.insert("Disconnect 3-pole", (2.0, 8.0))
        fu = self.insert("Fuses 3-pole", (7.0, 8.0), "RR")          # (turned round)
        self.bus_from(self.pins(ds)["T1"])
        type_in(self.v, "%r,%r" % self.pins(fu)["L1"])
        self.assertIn("other way", self.said[-1])
        self.assertIsNotNone(self.v.cmd)                       # (not landed: still drawing)
        self.v.cancel()
        # spacing: a bus 3/4" apart onto 1/2" poles
        self.said.clear()
        fu2 = self.insert("Fuses 3-pole", (12.0, 4.0))
        self.v.run(C.BusCmd)
        self.assertTrue(self.v.input_text("D"))
        self.assertTrue(self.v.input_text("0.75"))
        type_in(self.v, "9.0,4.0", "%r,%r" % self.pins(fu2)["L1"])
        self.assertTrue(any('0.5" apart' in t and '0.75"' in t for t in self.said), self.said)
        self.v.cancel()

    # 4 ------------------------------------------------------------------------------------
    def test_a_bus_takes_a_z_to_land_wire_for_wire(self):
        s = self.v.sheet()
        ds = self.insert("Disconnect 3-pole", (2.0, 7.5))
        for at in ((6.0, 4.5), (6.0, 10.5)):                 # (below and above it)
            fu = self.insert("Fuses 3-pole", at)
            for pin in ("L1", "L2", "L3"):
                before = set(s.entities)
                self.bus_from(self.pins(ds)["T1"])
                type_in(self.v, "%r,%r" % self.pins(fu)[pin])
                self.assertIsNone(self.v.cmd, "%s %s: not landed" % (at, pin))
                new = [e for i, e in s.entities.items() if i not in before]
                ends = {q for w in new for q in (w.points[0], w.points[-1])}
                d, f = self.pins(ds), self.pins(fu)
                for i in "123":
                    self.assertIn(d["T" + i], ends)
                    self.assertIn(f["L" + i], ends)
                # each wire from its T to its own L
                for w in new:
                    a, b = w.points[0], w.points[-1]
                    names = {n for n, q in list(d.items()) + list(f.items()) if q in (a, b)}
                    self.assertEqual({n[1] for n in names}, {next(iter(names))[1]}, names)
                self.assertEqual(X.found(s), [])
                self.v.project.undo()

    def test_in_line_with_its_own_pins_it_says_why_and_doesnt_run_down_them(self):
        # (CI, seed 289: a bus that neither landed nor said why; the same case "landed" by
        # running wire 1 straight down the column of pins it started from)
        ds = self.insert("Disconnect 3-pole", (2.0, 8.0))
        fu = self.insert("Fuses 3-pole", (2.5, 4.0), "RRR")
        cmd = self.bus_from(self.pins(ds)["T1"])
        s = self.v.sheet()
        for n in ("L1", "T1"):
            q = self.pins(fu)[n]
            self.assertIsNone(cmd._landing(s, q), n)
            self.assertIn("square", cmd._why_not_landed(s, q) or "", n)
        self.v.cancel()

    def test_a_bus_turning_too_close_to_its_pins_doesnt_cross_itself(self):
        # (the battery, seed 292: a bus off a vertical column of pins turned 1/4" out, less
        # than its 1/2" spacing, and landed with wire 2 crossing wire 3)
        from kanzonascad import crossings as X
        s = self.v.sheet()
        a = self.insert("Fuses 3-pole", (7.0, 7.0))              # (T1-T3: x 7.5, y 7..6)
        b = self.insert("Fuses 3-pole", (7.75, 5.75), "RRR")     # (L1-L3: y 5.75, x 7.75..)
        self.assertEqual(self.pins(a)["T3"], (7.5, 6.0))
        self.assertEqual(self.pins(b)["L3"], (6.75, 5.75))
        cmd = self.bus_from(self.pins(a)["T1"])
        click = self.pins(b)["L1"]
        before = set(s.entities)
        landed = cmd._landing(s, click) is not None
        type_in(self.v, "%r,%r" % click)
        new = {i for i in s.entities if i not in before}

        def on(w, q):
            return any(G.dist_to_segment(q, *seg) < 1e-9 for seg in zip(w.points, w.points[1:]))
        own = [x[0] for x in X.found(s)
               if sum(1 for i in new if on(s.entities[i], x[0])) >= 2]
        self.assertEqual(own, [])
        if not landed:
            self.assertIn("too close", self.said[-1])
        if self.v.cmd is not None:
            self.v.cancel()

    def test_a_bus_doesnt_land_through_a_symbol(self):
        a = self.insert("Fuses 3-pole", (10.5, 8.0))
        b = self.insert("Fuses 3-pole", (4.0, 8.0))
        self.bus_from(self.pins(a)["L1"])
        type_in(self.v, "%r,%r" % self.pins(b)["L1"])         # (its L side faces away)
        self.assertIsNotNone(self.v.cmd)
        self.assertIn("faces away", self.said[-1])
        self.v.cancel()


if __name__ == "__main__":
    unittest.main()
