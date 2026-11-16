"""The owner's list of Nov 16 (evening):
- "Copy is not included in schematic and needs to be": the Schematic and Panel tabs have
  Move, Copy, Rotate, Mirror and Erase.
- "Wires are being added with a little bend going down... That needs to go away": a second
  wire on a pin runs straight onto it (the 45-degree lead is a setting, off).
- "if I want to trim a wire that's not crossing anything but just has a bend, it deletes the
  whole wire instead of up to the bend": Trim wire stops at the wire's bends.
- "after I enter [a symbol], I should be able to hit the enter key to insert the same object
  in again"."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class Base(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.s = self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()


class RibbonTest(Base):
    def test_copy_on_the_schematic_and_panel_tabs(self):
        r = self.win.ribbon
        for title in ("Schematic", "Panel"):
            i = [r.tabText(k) for k in range(r.count())].index(title)
            acts = {a for b in r.widget(i).findChildren(object)
                    for a in ([b.defaultAction()] if hasattr(b, "defaultAction") else [])}
            self.assertIn(self.win.acts["copy"], acts, title)
            self.assertIn(self.win.acts["move"], acts, title)


class NoLeadTest(Base):
    def test_a_second_wire_on_a_pin_runs_straight(self):
        v = self.v
        v.run(C.InsertCmd, self.win.library.get("symbol", "Relay coil"), {})
        type_in(v, "4,4")
        coil = max(self.s.inserts(), key=lambda e: e.id)
        a1 = dict(coil.pin_points())["A1"]
        with self.p.edit("first") as ed:
            ed.add(self.s, M.Wire([(1.0, a1[1]), a1]))
        v.run(C.WireCmd)
        type_in(v, "%r,%r" % a1, "%r,%r" % (a1[0], a1[1] - 2.0))
        if v.cmd is not None:
            v.cmd.enter()
        new = max(self.s.wires(), key=lambda w: w.id)
        self.assertEqual(new.points, [a1, (a1[0], a1[1] - 2.0)])      # (no bend)
        # the lead is still there for whoever turns it on (Schematic settings)
        self.assertFalse(M.DEFAULT_SETTINGS["wire_lead"])
        self.p.settings["wire_lead"] = True
        v.run(C.WireCmd)
        type_in(v, "%r,%r" % a1, "%r,%r" % (a1[0], a1[1] + 2.0))
        if v.cmd is not None:
            v.cmd.enter()
        new = max(self.s.wires(), key=lambda w: w.id)
        self.assertGreater(len(new.points), 2)                          # (its lead)


class TrimToTheBendTest(Base):
    def test_trim_stops_at_the_bend(self):
        with self.p.edit("w") as ed:
            ed.add(self.s, M.Wire([(1.0, 1.0), (5.0, 1.0), (5.0, 4.0)]))
        self.v.run(C.TrimWireCmd)
        self.v.cmd.pick((3.0, 1.0))
        self.v.cancel()
        self.assertEqual([w.points for w in self.s.wires()], [[(5.0, 1.0), (5.0, 4.0)]])

    def test_the_middle_leg_of_a_u(self):
        with self.p.edit("w") as ed:
            ed.add(self.s, M.Wire([(1.0, 4.0), (1.0, 1.0), (6.0, 1.0), (6.0, 4.0)]))
        self.v.run(C.TrimWireCmd)
        self.v.cmd.pick((3.0, 1.0))
        self.v.cancel()
        self.assertEqual(sorted(w.points for w in self.s.wires()),
                         [[(1.0, 4.0), (1.0, 1.0)], [(6.0, 1.0), (6.0, 4.0)]])

    def test_a_crossing_still_stops_it_first(self):
        with self.p.edit("w") as ed:
            ed.add(self.s, M.Wire([(1.0, 1.0), (5.0, 1.0), (5.0, 4.0)]))
            ed.add(self.s, M.Wire([(3.0, 0.0), (3.0, 3.0)]))
        self.v.run(C.TrimWireCmd)
        self.v.cmd.pick((4.0, 1.0))
        self.v.cancel()
        pts = sorted(w.points for w in self.s.wires())
        self.assertIn([(1.0, 1.0), (3.0, 1.0)], pts)
        self.assertIn([(5.0, 1.0), (5.0, 4.0)], pts)


class RepeatInsertTest(Base):
    def test_enter_inserts_the_same_symbol_again(self):
        v = self.v
        coil = self.win.library.get("symbol", "Pilot light")
        v.run(C.InsertCmd, coil, {})
        type_in(v, "2,4")
        self.assertIsNone(v.cmd)
        v.enter()                                   # (Enter with no command: repeat)
        self.assertIsInstance(v.cmd, C.InsertCmd)
        self.assertEqual(v.cmd.defn.name, "Pilot light")
        type_in(v, "4,4")
        lights = [e for e in self.s.inserts() if e.block == "Pilot light"]
        self.assertEqual(len(lights), 2)
        self.assertEqual(len({e.attrs.get("TAG") for e in lights}), 2)    # (its own tag)
        self.assertEqual(dict(lights[-1].pin_points())["1"], (4.0, 4.0))  # (by its pin)


if __name__ == "__main__":
    unittest.main()
