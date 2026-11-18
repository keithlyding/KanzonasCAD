"""Tap numbers (the owner, 0.18.3: "all three wires tapping off the bus are still the same wire
number (2007, 2008, 2009). Those need to change where they tap off"; asked: the bus's number
with -1, -2, -3 per drop in the numbering order (2007-1, 2007-2... 2008-1...), the wires past
a device numbered as before, a tap off a tap a, b, c with no dash (2007-1a), on for new
projects with a project from before keeping its numbers; and still, per tap, the wire's number
(S) or one of its own (N), as 0.17.2 asked)."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wirenums


class TapNumberTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.s = self.v.sheet()
        with self.p.edit("page") as ed:
            ed.sheet_meta(self.s, number="2")

    def tearDown(self):
        self.win.__dict__.pop("ask_wire_number", None)
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def num(self, at):
        return [w.num for w in self.s.wires() if w.touches(at)][0]

    def bus(self):
        """Three bus wires (L1 y=8, L2 7.5, L3 7) and a drop off each at x = 3, 6, 9."""
        with self.p.edit("bus") as ed:
            for y in (8.0, 7.5, 7.0):
                ed.add(self.s, M.Wire([(1.0, y), (12.0, y)]))
            for x in (3.0, 6.0, 9.0):
                for i, y in enumerate((8.0, 7.5, 7.0)):
                    ed.add(self.s, M.Wire([(x + 0.25 * i, y), (x + 0.25 * i, 4.0)]))

    def drops(self, x):
        return [self.num((x + 0.25 * i, 4.0)) for i in range(3)]

    def test_new_projects_number_taps_off_the_wire(self):
        self.assertEqual(wirenums.tap_mode(self.p), "suffix")
        self.bus()
        l1, l2, l3 = self.num((1.0, 8.0)), self.num((1.0, 7.5)), self.num((1.0, 7.0))
        self.assertEqual(len({l1, l2, l3}), 3)
        # (the owner's table: per bus wire, -1, -2, -3 in the numbering order)
        self.assertEqual(self.drops(3.0), [l1 + "-1", l2 + "-1", l3 + "-1"])
        self.assertEqual(self.drops(6.0), [l1 + "-2", l2 + "-2", l3 + "-2"])
        self.assertEqual(self.drops(9.0), [l1 + "-3", l2 + "-3", l3 + "-3"])
        # (the bus itself keeps its plain number, and no plain number was spent on a drop)
        self.assertTrue(all("-" not in n for n in (l1, l2, l3)))
        self.assertEqual(sorted(n for n in {w.num for w in self.s.wires()} if "-" not in n),
                         sorted([l1, l2, l3]))

    def test_past_a_device_a_number_of_its_own(self):
        coil = self.win.library.get("symbol", "Relay coil")
        with self.p.edit("bus") as ed:
            ed.add(self.s, M.Wire([(1.0, 8.0), (12.0, 8.0)]))
            c = ed.add(self.s, M.Insert(coil.name, (3.0, 5.0), defn=coil))
        a1, a2 = sorted(q for _n, q in c.pin_points())          # (side by side: A1, A2)
        with self.p.edit("drop") as ed:
            ed.add(self.s, M.Wire([(a1[0], 8.0), a1]))           # (off the bus to A1)
            ed.add(self.s, M.Wire([a2, (8.0, a2[1])]))           # (from A2 on)
        bus = self.num((1.0, 8.0))
        self.assertEqual(self.num((a1[0], 7.0)), bus + "-1")
        past = self.num((8.0, a2[1]))
        self.assertNotIn("-", past)
        self.assertNotEqual(past, bus)

    def test_a_tap_off_a_tap_takes_a_letter(self):
        with self.p.edit("w") as ed:
            ed.add(self.s, M.Wire([(1.0, 8.0), (12.0, 8.0)]))
            ed.add(self.s, M.Wire([(3.0, 8.0), (3.0, 2.0)]))
            ed.add(self.s, M.Wire([(3.0, 5.0), (6.0, 5.0)]))         # (off the drop's middle)
            ed.add(self.s, M.Wire([(3.0, 4.0), (6.0, 4.0)]))
        bus = self.num((1.0, 8.0))
        self.assertEqual(self.num((3.0, 2.0)), bus + "-1")
        got = {self.num((6.0, 5.0)), self.num((6.0, 4.0))}
        self.assertEqual(got, {bus + "-1a", bus + "-1b"})

    def test_same_or_own_per_tap(self):
        self.bus()
        l1 = self.num((1.0, 8.0))
        tap = [w for w in self.s.wires() if w.touches((3.0, 4.0))][0]
        with self.p.edit("same") as ed:
            ed.change(self.s, tap.copy(same_num=True))
        self.assertEqual(self.num((3.0, 4.0)), l1)
        self.assertEqual(self.num((6.0, 4.0)), l1 + "-1")      # (the next one: -1 now)
        tap = [w for w in self.s.wires() if w.touches((6.0, 4.0))][0]
        with self.p.edit("own") as ed:
            ed.change(self.s, tap.copy(own_num=True))
        own = self.num((6.0, 4.0))
        self.assertNotIn("-", own)
        self.assertNotEqual(own, l1)
        self.assertEqual(self.num((9.0, 4.0)), l1 + "-1")
        # (kept in the file)
        q = M.Project.from_dict(self.p.to_dict())
        flags = sorted((w.same_num, w.own_num) for w in q.sheets[0].wires())
        self.assertEqual(flags.count((True, False)), 1)
        self.assertEqual(flags.count((False, True)), 1)

    def test_the_setting_renumbers_in_one_step(self):
        self.bus()
        l1 = self.num((1.0, 8.0))
        steps = len(self.p.undo_stack)
        with self.p.edit("Schematic settings") as ed:
            ed.project_settings({"tap_numbers": "same"})
        self.assertEqual(len(self.p.undo_stack), steps + 1)
        self.assertEqual(self.drops(3.0)[0], l1)
        with self.p.edit("Schematic settings") as ed:
            ed.project_settings({"tap_numbers": "own"})
        own = self.drops(3.0)[0]
        self.assertNotIn("-", own)
        self.assertNotEqual(own, l1)
        self.p.undo()
        self.p.undo()
        self.assertEqual(self.drops(3.0)[0], l1 + "-1")

    def test_two_wires_tapping_each_other(self):
        # (each one's end on the other's middle: numbered from each other round a loop, they
        # got no number; the battery, seed 37)
        with self.p.edit("w") as ed:
            a = ed.add(self.s, M.Wire([(2.0, 5.0), (8.0, 5.0)]))
            b = ed.add(self.s, M.Wire([(8.0, 8.0), (8.0, 2.0), (5.0, 2.0), (5.0, 5.0)]))
        na, nb = self.s.entities[a.id].num, self.s.entities[b.id].num
        self.assertTrue(na and nb, (na, nb))
        plain, tap = sorted((na, nb), key=len)
        self.assertEqual(tap, plain + "-1")

    def test_a_project_from_before_keeps_its_numbers(self):
        d = self.p.to_dict()
        d["settings"].pop("tap_numbers")
        q = M.Project.from_dict(d)
        self.assertEqual(wirenums.tap_mode(q), "same")

    def test_a_typed_number_on_a_tap_stays(self):
        self.bus()
        tap = [w for w in self.s.wires() if w.touches((3.0, 4.0))][0]
        with self.p.edit("typed") as ed:
            wirenums.set_number(ed, self.p, self.s, tap, "2099", True)
        self.assertEqual(self.num((3.0, 4.0)), "2099")
        l1 = self.num((1.0, 8.0))
        self.assertEqual(self.num((6.0, 4.0)), l1 + "-2")       # (the others as they were)

    # ---- drawing a tap ------------------------------------------------------------------
    def draw_tap(self, answer):
        with self.p.edit("w") as ed:
            ed.add(self.s, M.Wire([(1.0, 8.0), (12.0, 8.0)]))
        self.v.run(C.WireCmd)
        type_in(self.v, "3,8", "3,4")
        if self.v.cmd is not None and self.v.cmd.tapped is None:
            self.v.cmd.enter()
        self.assertIsNotNone(self.v.cmd)
        self.assertIn("-1, -2", self.v._prompt[0])
        if answer:
            type_in(self.v, answer)
        else:
            self.v.enter()
        self.assertIsNone(self.v.cmd)
        return self.num((1.0, 8.0)), self.num((3.0, 4.0))

    def test_enter_numbers_it_off_the_wire(self):
        bus, tap = self.draw_tap("")
        self.assertEqual(tap, bus + "-1")

    def test_s_keeps_the_wires_number(self):
        bus, tap = self.draw_tap("S")
        self.assertEqual(tap, bus)
        self.p.undo()
        self.assertEqual(self.num((3.0, 4.0)), bus + "-1")

    def test_n_a_number_of_its_own(self):
        bus, tap = self.draw_tap("N")
        self.assertNotIn("-", tap)
        self.assertNotEqual(tap, bus)

    def test_double_click_choice(self):
        self.bus()
        l1 = self.num((1.0, 8.0))
        asked = []

        def ask(num, tap_of=None, own="", locked=False):
            asked.append((tap_of, own))
            return num, "same", locked
        self.win.ask_wire_number = ask
        self.win.edit_wire_number([w for w in self.s.wires() if w.touches((3.0, 4.0))][0])
        self.assertEqual(asked, [(l1, "")])
        self.assertEqual(self.num((3.0, 4.0)), l1)
        self.win.ask_wire_number = lambda num, tap_of=None, own="", locked=False: (num, "",
                                                                                   locked)
        self.win.edit_wire_number([w for w in self.s.wires() if w.touches((3.0, 4.0))][0])
        self.assertEqual(self.num((3.0, 4.0)), l1 + "-1")

    def test_the_window_offers_three_ways(self):
        from PySide6.QtWidgets import QDialog, QComboBox
        from kanzonascad import dialogs
        seen = {}

        def answer(dlg):
            box = dlg.findChild(QComboBox, "own_num")
            seen["items"] = [box.itemText(i) for i in range(box.count())]
            box.setCurrentIndex(box.findData("own"))
            return QDialog.Accepted
        real = dialogs.QDialog.exec
        dialogs.QDialog.exec = answer
        try:
            out = dialogs.wire_number_dialog(self.win, "2007-1", "2007", "", False, "suffix")
        finally:
            dialogs.QDialog.exec = real
        self.assertEqual(out[1], "own")
        self.assertIn("2007-1", seen["items"][0])
        self.assertEqual(len(seen["items"]), 3)

    def test_schematic_settings_choice(self):
        from PySide6.QtWidgets import QDialog, QComboBox
        from kanzonascad import dialogs
        self.bus()
        l1 = self.num((1.0, 8.0))
        seen = {}

        def answer(dlg):
            box = dlg.findChild(QComboBox, "tap_numbers")
            seen["was"] = box.currentData()
            box.setCurrentIndex(box.findData("same"))
            return QDialog.Accepted
        real = dialogs.QDialog.exec
        dialogs.QDialog.exec = answer
        try:
            self.win.project_properties(1)
        finally:
            dialogs.QDialog.exec = real
        self.assertEqual(seen["was"], "suffix")
        self.assertEqual(self.p.settings["tap_numbers"], "same")
        self.assertEqual(self.drops(3.0), [l1, self.num((1.0, 7.5)), self.num((1.0, 7.0))])


if __name__ == "__main__":
    unittest.main()
