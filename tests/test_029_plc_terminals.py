"""0.29: the Allen-Bradley PLC modules' pins (the owner, Nov 27 2026, "Both"): named by
Rockwell's terminal numbers with the point beside each ("2  IN 0") for a module whose terminal
block is in allen_bradley.TERMINALS, else by point; wire numbers by address and Import I/O list
go by the point either way, never by the pin's name."""

import unittest
from unittest import mock

from kanzonascad import allen_bradley as AB
from kanzonascad import io_list
from kanzonascad import model as M
from kanzonascad import wirenums
from kanzonascad.wirenums import io_address

# a terminal block whose numbers aren't its points (as a 20-pin RTB's: points on the even
# terminals, commons after them): made up here, only to test the drawing of one
MADE_UP = ("a test, not a Rockwell publication",
           [("2", "IN 0"), ("4", "IN 1"), ("1", "IN 2"), ("3", "IN 3"),
            ("5", "GND-0"), ("6", "GND-0")])


def module(cat):
    return next(b for b in AB.ab_io_modules() if b.catalog == cat)


class TerminalsTest(unittest.TestCase):
    def test_by_point_without_rockwells_numbers(self):
        for cat, _fam, _desc, word, n in AB.IO:
            if cat in AB.TERMINALS:
                continue
            b = module(cat)
            self.assertEqual([p["name"] for p in b.pins], [str(i) for i in range(n)], cat)
            self.assertIn("named by point", b.description, cat)
            self.assertEqual(wirenums.io_points(b),
                             {str(i): (word[0], i) for i in range(n)}, cat)

    def test_terminal_numbers_with_the_point_beside(self):
        with mock.patch.dict(AB.TERMINALS, {"1769-IQ16": MADE_UP}):
            b = module("1769-IQ16")
        self.assertEqual([p["name"] for p in b.pins], ["2", "4", "1", "3", "5", "6"])
        texts = {e.text for e in b.entities if isinstance(e, M.Text)}
        self.assertTrue({"2  IN 0", "4  IN 1", "1  IN 2", "5  GND-0"} <= texts, texts)
        self.assertIn(MADE_UP[0], b.description)
        # wire numbers by address: the point of each pin, not its name; a common none
        self.assertEqual(wirenums.io_points(b), {"2": ("I", 0), "4": ("I", 1),
                                                 "1": ("I", 2), "3": ("I", 3)})
        pts = wirenums.io_points(b)
        self.assertEqual(io_address(*pts["1"], {"SLOT": "4"}), "I:4/2")
        # Import I/O list: point 0's text goes beside terminal 2
        self.assertEqual(io_list._point_pins(b), {0: "2", 1: "4", 2: "1", 3: "3"})


if __name__ == "__main__":
    unittest.main()
