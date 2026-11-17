"""Wire numbers out of the way (the owner, 0.18.1: "When I add wires, wire numbers need to try
to move to be out of the way. If no room, a little line and wire number off the wire line can
be used"): a number goes where it comes into nothing (another wire, a symbol and its texts,
another number), along its wire, over or under it; with no room beside the wire, it is set off
to the side with a short line back to the wire."""
import unittest

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import wirenums


def hits(box, sheet, skip):
    for e in sheet.query(box):
        if e.id not in skip and e.crosses(box):
            return e
    return None


class WireNumberRoomTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.s = self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def label_of(self, w):
        w = self.s.entities[w.id]
        got = [t for t in wirenums.labels(self.p, self.s) if t.text == w.num]
        self.assertEqual(len(got), 1, [t.text for t in wirenums.labels(self.p, self.s)])
        return got[0]

    def test_moves_off_a_line_over_its_middle(self):
        with self.p.edit("x") as ed:
            w = ed.add(self.s, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
            # a short line standing just over the middle of the wire, where the number went
            ed.add(self.s, M.Line((4.0, 5.03), (4.0, 5.3)))
        t = self.label_of(w)
        self.assertIsNone(hits(t.bbox(), self.s, {w.id}))
        self.assertEqual(wirenums.label_leaders(self.p, self.s), [])     # (room beside it)

    def test_numbers_dont_sit_on_each_other(self):
        with self.p.edit("x") as ed:
            ws = [ed.add(self.s, M.Wire([(2.0, 5.0 + 0.25 * i), (2.6, 5.0 + 0.25 * i)]))
                  for i in range(3)]
        boxes = [self.label_of(w).bbox() for w in ws]
        for i in range(3):
            self.assertIsNone(hits(boxes[i], self.s, {ws[i].id}))
            for j in range(i + 1, 3):
                a, b = boxes[i], boxes[j]
                self.assertFalse(a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1])

    def test_no_room_beside_it_a_line_back_to_it(self):
        # a short wire boxed in by lines just over and under it: no room beside it
        with self.p.edit("x") as ed:
            w = ed.add(self.s, M.Wire([(2.0, 5.0), (2.4, 5.0)]))
            for y in (5.05, 4.95):
                ed.add(self.s, M.Line((1.5, y), (2.9, y)))
        t = self.label_of(w)
        self.assertIsNone(hits(t.bbox(), self.s, {w.id}))
        lead = wirenums.label_leaders(self.p, self.s)
        self.assertEqual(len(lead), 1)
        a, b = lead[0]
        self.assertTrue(2.0 <= a[0] <= 2.4 and abs(a[1] - 5.0) < 1e-9)  # (from the wire)
        tb = t.bbox()
        self.assertTrue(tb[0] - 1e-9 <= b[0] <= tb[2] + 1e-9 and
                        tb[1] - 1e-9 <= b[1] <= tb[3] + 1e-9)            # (to the number)
        # exported with it
        from kanzonascad import fileio
        import os
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "x.dxf")
        fileio.export_dxf(self.p, self.s, path)
        import ezdxf
        doc = ezdxf.readfile(path)
        lines = [(round(e.dxf.start.x, 6), round(e.dxf.start.y, 6))
                 for e in doc.modelspace().query("LINE")]
        self.assertIn((round(a[0], 6), round(a[1], 6)), lines)


if __name__ == "__main__":
    unittest.main()
