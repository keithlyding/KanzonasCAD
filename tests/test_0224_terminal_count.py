"""Terminal count (the owner, 0.22.4: "When I'm tapping off a wire with -1, -2, -3, etc, is
there anything that is totalizing so I know how many terminal blocks I need?", and "Do number
1": one wire on each terminal side): every tapped wire number, its taps, and the terminals
(the number and each tap one) and jumpers (one fewer) they need, with the totals; a tap off a
tap counted with its wire; taps that keep the wire's number aren't counted."""
import unittest

from tests.util import APP, window

from kanzonascad import dialogs
from kanzonascad import model as M
from kanzonascad import reports


class TerminalCountTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.s = self.v.sheet()
        with self.p.edit("page") as ed:
            ed.sheet_meta(self.s, number="2")
            # a wire tapped three times, one of its taps tapped again; another tapped once;
            # one not tapped
            ed.add(self.s, M.Wire([(1.0, 8.0), (12.0, 8.0)]))
            for x in (3.0, 6.0, 9.0):
                ed.add(self.s, M.Wire([(x, 8.0), (x, 4.0)]))
            ed.add(self.s, M.Wire([(6.0, 5.0), (7.5, 5.0)]))          # (off the -2)
            ed.add(self.s, M.Wire([(1.0, 3.0), (12.0, 3.0)]))
            ed.add(self.s, M.Wire([(5.0, 3.0), (5.0, 1.5)]))
            ed.add(self.s, M.Wire([(1.0, 10.0), (12.0, 10.0)]))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def num(self, at):
        return [w.num for w in self.s.wires() if w.touches(at)][0]

    def test_counted_one_terminal_a_wire_end(self):
        rows, (terms, jumpers) = reports.terminal_count_rows(self.p)
        a, b = self.num((1.0, 8.0)), self.num((1.0, 3.0))
        by = {r[0]: r for r in rows}
        self.assertEqual(set(by), {a, b})                       # (the untapped one: not)
        taps = by[a][1].split(", ")
        self.assertEqual(len(taps), 4)                          # (-1, -2, -2a, -3)
        self.assertIn(a + "-2a", taps)
        self.assertEqual(by[a][2:4], ["5", "4"])
        self.assertEqual(by[b][1:4], [b + "-1", "2", "1"])
        self.assertEqual((terms, jumpers), (7, 5))
        self.assertEqual(by[a][4], "2")

    def test_two_wires_tapping_each_other(self):
        # (overlapping, each with an end on the other's middle: one tap, as numbered; the
        # battery's seed 5 found it left out)
        with self.p.edit("overlap") as ed:
            ed.add(self.s, M.Wire([(2.0, 12.0), (5.0, 12.0)]))
            ed.add(self.s, M.Wire([(5.0, 12.0), (7.5, 12.0)]))
            ed.add(self.s, M.Wire([(5.5, 12.0), (8.0, 12.0)]))
        base = self.num((2.0, 12.0))
        rows, _t = reports.terminal_count_rows(self.p)
        by = {r[0]: r for r in rows}
        self.assertEqual(by[base][1:4], [base + "-1", "2", "1"])

    def test_taps_keeping_the_wires_number_not_counted(self):
        with self.p.edit("same") as ed:
            ed.project_settings({"tap_numbers": "same"})
        self.assertEqual(reports.terminal_count_rows(self.p), ([], (0, 0)))

    def test_the_window_with_its_total(self):
        seen = []
        real = dialogs.report_dialog
        dialogs.report_dialog = lambda parent, title, head, rows, *a: seen.append(
            (title, head, rows, a))
        try:
            self.win.acts["terminal_count"].trigger()
        finally:
            dialogs.report_dialog = real
        title, head, rows, _a = seen[0]
        self.assertEqual(title, "Terminal count")
        self.assertEqual(head, reports.COUNT_HEAD)
        self.assertEqual(rows[-1][:4], ["Total", "", "7", "5"])


if __name__ == "__main__":
    unittest.main()
