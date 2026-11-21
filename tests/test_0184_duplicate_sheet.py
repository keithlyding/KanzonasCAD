"""Duplicate sheet (the owner, 0.18.4: "I need to be able to duplicate a sheet inside the
project"); gauge labels off other wires' numbers (the owner: "the wire number is on top of
the wire labels from the other wires")."""
import unittest

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import wirelayers
from kanzonascad import wirenums


class DuplicateSheetTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()
        coil = self.win.library.get("symbol", "Relay coil")
        link = self.win.library.get("symbol", "Source arrow")
        with self.p.edit("w") as ed:
            ed.sheet_meta(self.s, number="2", title="Motors")
            self.w = ed.add(self.s, M.Wire([(1.0, 5.0), (2.75, 5.0)]))
            ed.block(coil)
            ed.block(link)
            ed.add(self.s, M.Insert(coil.name, (3.0, 5.0), defn=self.p.blocks[coil.name],
                                    attrs={"TAG": "CR201"}))
            ed.add(self.s, M.Insert(link.name, (1.0, 5.0), 180.0,
                                    defn=self.p.blocks[link.name], attrs={"TAG": "A"}))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_a_copy_of_its_own(self):
        steps = len(self.p.undo_stack)
        self.win.acts["sheet_dup"].trigger()
        self.assertEqual(len(self.p.sheets), 2)
        self.assertEqual(len(self.p.undo_stack), steps + 1)          # (one step)
        c = self.p.sheets[1]
        self.assertIs(self.v.sheet(), c)
        self.assertEqual(c.title, "Motors-2")
        self.assertEqual(len(c.entities), len(self.s.entities))
        self.assertNotEqual(self.p.sheet_number(c), self.p.sheet_number(self.s))
        tags = sorted(e.attrs.get("TAG", "") for e in c.inserts())
        self.assertIn("CR%s01" % self.p.sheet_number(c), tags)       # (its page's tag)
        self.assertNotIn("A", tags)                                  # (not joined: no name)
        orig = self.s.entities[self.w.id].num
        nums = [w.num for w in c.wires()]
        self.assertTrue(nums and nums[0] and nums[0] != orig, (nums, orig))
        self.p.undo()
        self.assertEqual(len(self.p.sheets), 1)


class CopyTitleTest(unittest.TestCase):
    # (the owner, 0.21.2: "instead of adding "copy", can you make it say -2, -3, etc?")
    def test_numbered_on(self):
        from kanzonascad.main_window import copy_title
        self.assertTrue(APP)
        self.assertEqual(copy_title("Motors", ["Motors"]), "Motors-2")
        self.assertEqual(copy_title("Motors", ["Motors", "Motors-2"]), "Motors-3")
        self.assertEqual(copy_title("Motors-2", ["Motors", "Motors-2"]), "Motors-3")
        self.assertEqual(copy_title("480 Distribution - 1", ["480 Distribution - 1",
                                                             "480 Distribution - 2"]),
                         "480 Distribution - 3")
        self.assertEqual(copy_title("", [""]), "")


class GaugeOffNumbersTest(unittest.TestCase):
    def test_upright_wires_side_by_side(self):
        win, v = window()
        try:
            p, s = v.project, v.sheet()
            with p.edit("w") as ed:
                wirelayers.add_preset(ed, p, ["480 V"])
                ed.project_settings({"wire_gauge_each": "each"})
                for i in range(4):
                    ed.add(s, M.Wire([(2.0 + 0.15 * i, 2.0), (2.0 + 0.15 * i, 2.9)],
                                     layer="480V BLK"))
            nums = [t.bbox() for t in wirenums.labels(p, s)]
            gauges = [t.bbox() for t in wirenums.gauge_labels(p, s)]
            self.assertEqual(len(gauges), 4)

            def over(a, b):
                return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]
            for g in gauges:
                self.assertFalse(any(over(g, n) for n in nums), (g, nums))
            for i, g in enumerate(gauges):
                self.assertFalse(any(over(g, o) for o in gauges[i + 1:]))
        finally:
            p.saved_at = len(p.undo_stack)
            win.close()


if __name__ == "__main__":
    unittest.main()
