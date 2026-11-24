"""Terminal count puts each tap in the row of the wire its number comes from, as the numbering
takes it (wirenums.tap_outputs): a tap touching two wires was numbered from the one that comes
first in numbering order, 1030b, but listed in the other's row, 1047a4's (the long battery,
seed 4773)."""
import unittest
from unittest import mock

from tests.util import APP, window

from kanzonascad import reports
from kanzonascad import wirenums


class TerminalCountFamilyTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_a_tap_of_two_wires_in_the_row_it_is_numbered_from(self):
        s = self.s
        # (A numbered first; T2 taps A first of all; T taps B before it taps A)
        info = {"A": [(0, 1), s, ["1001"], None], "B": [(0, 2), s, ["1002"], None],
                "T2": [(0, 3), s, ["1001-1"], None], "T": [(0, 4), s, ["1001-2"], None]}
        gs = {g: [(s, [])] for g in info}
        taps = [("A", "T2", (0, 1)), ("B", "T", (0, 2)), ("A", "T", (0, 3))]
        outputs = wirenums.tap_outputs([], taps, info)
        self.assertEqual(outputs["T"][0], "A")          # (numbered 1001-2: from A)
        with mock.patch.object(wirenums, "_assemble",
                               return_value=(gs, info, [], taps, {})):
            rows, (terms, jumpers) = reports.terminal_count_rows(self.p)
        self.assertEqual([r[:2] for r in rows], [["1001", "1001-1, 1001-2"]])
        self.assertEqual((terms, jumpers), (3, 2))


if __name__ == "__main__":
    unittest.main()
