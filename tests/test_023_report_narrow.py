"""A report sheet with little room (a title block strip as wide as most of the page, a long
Tags column) keeps its short columns readable: every column was shrunk by the same share, and
the BOM's Item column came out too narrow for "3", left empty (the long battery, seed 4792).
Wide columns give up room first; a short one keeps what it needs."""
import unittest

from kanzonascad import report_sheets as RS


class ReportNarrowTest(unittest.TestCase):
    def test_short_columns_keep_their_text(self):
        head = ["Item", "Qty", "Manufacturer", "Catalog number", "Description", "Tags"]
        tags = ", ".join("PLC%d" % (1000 + i) for i in range(40))
        rows = [[str(i), str(10 + i), "Allen-Bradley", "1734-IB8",
                 "24V DC sinking input module, 8 points (POINT I/O)", tags]
                for i in range(1, 12)]
        for room in (9.5, 6.0, 4.0):
            widths = RS._widths(head, rows, room)
            self.assertLessEqual(sum(widths), room + 1e-9)
            for r in rows:
                self.assertEqual(RS._fit(r[0], widths[0]), r[0], (room, widths))
                self.assertEqual(RS._fit(r[1], widths[1]), r[1], (room, widths))

    def test_room_enough_as_before(self):
        head, rows = ["Item", "Qty"], [["1", "2"]]
        widths = RS._widths(head, rows, 100.0)
        self.assertEqual(widths, RS._widths(head, rows, 50.0))


if __name__ == "__main__":
    unittest.main()
