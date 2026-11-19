"""The owner, 0.17.2: "I need to be able to signify that when I tap off a wire, I can either
change the wire number or leave as is. On long stretches of wire, I need to be able to insert
wire labels in multiple places, preferably automatically but also manually. But don't freeze
the wire number" (asked: when tapping, ask; automatically, near both ends of long wires;
manually, a click on the wire).

- A wire drawn off the middle of another asks: Enter keeps its number, N a new one; double-
  click the tap to change it later.
- A wire longer than "wire_label_ends" (paper inches) shows its number near both ends.
- Wire number label: a click on a wire shows its number there too, always its current number;
  kept on the wire, so it moves, copies, undoes, saves, joins and is cut with it."""
import os
import tempfile
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wirenums


class WireLabelTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        self.s, self.p = v.sheet(), v.project
        with self.p.edit("taps") as ed:      # (0.17.2's way: a tap the wire's number to start;
            ed.project_settings({"tap_numbers": "same"})     # -1, -2...: test_0183_tap_numbers)
        self.said = []
        v.messaged.connect(self.said.append)

    def tearDown(self):
        self.win.__dict__.pop("ask_wire_number", None)
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def wire(self, *pts):
        before = set(self.s.entities)
        self.v.run(C.WireCmd)
        type_in(self.v, *["%r,%r" % q for q in pts])
        if self.v.cmd is not None and self.v.cmd.tapped is None:
            self.v.cmd.enter()
        return [e for i, e in self.s.entities.items() if i not in before
                and isinstance(e, M.Wire)]

    def num(self, at):
        return [w.num for w in self.s.wires() if w.touches(at)][0]

    def shown(self):
        return sorted((t.text, round(t.pos[0], 3), round(t.pos[1], 3))
                      for t in wirenums.labels(self.p, self.s))

    # ---- taps ---------------------------------------------------------------------------
    def test_a_tap_asks_and_enter_keeps_the_number(self):
        self.wire((1.0, 5.0), (5.0, 5.0))
        self.wire((3.0, 5.0), (3.0, 7.0))               # (off its middle)
        self.assertIsNotNone(self.v.cmd)
        self.assertIn("Tapped off wire", self.v._prompt[0])
        self.v.enter()
        self.assertIsNone(self.v.cmd)
        self.assertEqual(self.num((3.0, 7.0)), self.num((1.0, 5.0)))

    def test_n_gives_the_tap_a_number_of_its_own(self):
        self.wire((1.0, 5.0), (5.0, 5.0))
        self.wire((3.0, 5.0), (3.0, 7.0))
        type_in(self.v, "N")
        self.assertIsNone(self.v.cmd)
        a, b = self.num((1.0, 5.0)), self.num((3.0, 7.0))
        self.assertTrue(a and b)
        self.assertNotEqual(a, b)
        # still connected (a dot at the tap), only numbered apart
        from kanzonascad import wires
        self.assertIn((3.0, 5.0), wires.junctions(self.s))
        # undo: one number again
        self.p.undo()
        self.assertEqual(self.num((3.0, 7.0)), self.num((1.0, 5.0)))

    def test_double_click_changes_it_later(self):
        self.wire((1.0, 5.0), (5.0, 5.0))
        self.wire((3.0, 5.0), (3.0, 7.0))
        self.v.enter()
        tap = [w for w in self.s.wires() if w.touches((3.0, 7.0))][0]
        asked = []

        def ask(num, tap_of=None, own=False, locked=False):
            asked.append((num, tap_of, own))
            return num, True
        self.win.ask_wire_number = ask
        self.win.edit_wire_number(tap)
        self.assertEqual(asked[0][1], self.num((1.0, 5.0)))      # (it says which it taps)
        self.assertNotEqual(self.num((3.0, 7.0)), self.num((1.0, 5.0)))
        # and back
        self.win.ask_wire_number = lambda num, tap_of=None, own=False, locked=False: (num,
                                                                                      False)
        self.win.edit_wire_number([w for w in self.s.wires() if w.touches((3.0, 7.0))][0])
        self.assertEqual(self.num((3.0, 7.0)), self.num((1.0, 5.0)))

    def test_a_wire_end_to_end_isnt_asked(self):
        self.wire((1.0, 5.0), (5.0, 5.0))
        self.wire((5.0, 5.0), (5.0, 8.0))               # (on its end: not a tap)
        self.assertIsNone(self.v.cmd)

    # ---- both ends ---------------------------------------------------------------------
    def test_long_wires_show_their_number_near_both_ends(self):
        self.wire((1.0, 5.0), (13.0, 5.0))              # (12" long)
        self.wire((1.0, 3.0), (4.0, 3.0))               # (3")
        num = self.num((1.0, 5.0))
        got = [t for t in wirenums.labels(self.p, self.s) if t.text == num]
        self.assertEqual(sorted(round(t.pos[0], 6) for t in got), [2.0, 12.0])
        short = self.num((1.0, 3.0))
        self.assertEqual(len([t for t in wirenums.labels(self.p, self.s) if t.text == short]),
                         1)
        # off: one, as before
        with self.p.edit("off") as ed:
            ed.project_settings({"wire_label_ends": 0.0})
        self.assertEqual(len([t for t in wirenums.labels(self.p, self.s) if t.text == num]), 1)

    # ---- by hand -----------------------------------------------------------------------
    def test_labels_placed_by_hand_follow_the_number(self):
        with self.p.edit("off") as ed:
            ed.project_settings({"wire_label_ends": 0.0})
        self.wire((1.0, 5.0), (5.0, 5.0), (5.0, 9.0))
        self.v.center, self.v.scale = (4.0, 6.0), 100.0
        self.v.run(C.WireLabelCmd)
        for q in ((2.0, 5.0), (5.0, 8.0)):
            self.v.cmd.pick(q)
        self.v.enter()
        w = self.s.wires()[0]
        self.assertEqual(w.labels, [1.0, 7.0])
        num = w.num
        spots = [t for t in wirenums.labels(self.p, self.s) if t.text == num]
        self.assertEqual(len(spots), 3)                  # (its own, and the two)
        self.assertIn(90.0, [t.angle for t in spots])    # (the one on the upright run)
        # not frozen: a new number shows at all of them
        with self.p.edit("n") as ed:
            wirenums.set_number(ed, self.p, self.s, w, "7777")
        self.assertEqual({t.text for t in wirenums.labels(self.p, self.s)}, {"7777"})
        # R takes one off
        self.v.run(C.WireLabelCmd)
        type_in(self.v, "R")
        self.v.cmd.pick((2.1, 5.0))
        self.v.enter()
        self.assertEqual(self.s.wires()[0].labels, [7.0])

    def test_they_go_with_the_wire(self):
        w = M.Wire([(1.0, 5.0), (5.0, 5.0)], labels=[1.0, 3.0])
        self.assertEqual(w.moved(2.0, 1.0).labels, [1.0, 3.0])
        d = tempfile.mkdtemp()
        with self.p.edit("w") as ed:
            ed.add(self.s, w)
            ed.add(self.s, M.Wire([(5.0, 5.0), (9.0, 5.0)], labels=[2.0]))
            ed.add(self.s, M.Wire([(1.0, 7.0), (3.0, 7.0)], own_num=True))
        path = os.path.join(d, "t.kzcad")
        self.p.save(path)
        q = M.Project.load(path).sheets[0]
        self.assertEqual(sorted(tuple(x.labels) for x in q.wires()), [(), (1.0, 3.0), (2.0,)])
        self.assertTrue(any(x.own_num for x in q.wires()))
        # joined end to end: both wires' labels, measured along the one wire
        from kanzonascad import wires
        with self.p.edit("join") as ed:
            wires.join_at(ed, self.s, [(5.0, 5.0)])
        joined = [x for x in self.s.wires() if x.touches((9.0, 5.0))][0]
        self.assertEqual(joined.labels, [1.0, 3.0, 6.0])
        # cut (a wire crossing it at 5: the piece from there to its end clicked off): the
        # piece left keeps the ones on it
        with self.p.edit("x") as ed:
            ed.add(self.s, M.Wire([(5.0, 4.0), (5.0, 6.0)]))
        pieces, _ends = wires.trim_wire(self.s, joined, (7.0, 5.0))
        self.assertEqual(sorted(tuple(x.labels) for x in pieces), [(1.0, 3.0)])


if __name__ == "__main__":
    unittest.main()
