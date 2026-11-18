"""One gauge and color label for wires side by side alike (the owner, 0.18.4, a photo of
"12 AWG BLK" on every conductor from each starter to its drive and on to its motor: "I don't
need 12awg black on every wire. It's too busy and takes up space. Can this intuitively mark
the gauge and color of one wire instead of all of them?")."""
import unittest

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import wirelayers
from kanzonascad import wirenums


class GaugeBundleTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()
        with self.p.edit("layers") as ed:
            wirelayers.add_preset(ed, self.p, ["480 V", "24 VDC"])

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def wires(self, xs, y0=2.0, y1=6.0, layer="480V BLK", awg=""):
        with self.p.edit("w") as ed:
            for x in xs:
                ed.add(self.s, M.Wire([(x, y0), (x, y1)], layer=layer, awg=awg))

    def labels(self):
        return [(t.text, round(t.pos[0], 3), round(t.pos[1], 3))
                for t in wirenums.gauge_labels(self.p, self.s)]

    def test_four_conductors_one_label_on_the_outside_one(self):
        self.wires([2.0, 2.25, 2.5, 2.75])                  # (a starter's conductors)
        got = self.labels()
        self.assertEqual(len(got), 1, got)
        self.assertEqual(got[0][0], "12 AWG BLK")
        self.assertGreater(got[0][1], 2.75)                 # (right of the rightmost)
        # every wire again, as asked in Schematic settings
        with self.p.edit("each") as ed:
            ed.project_settings({"wire_gauge_each": "each"})
        self.assertEqual(len(self.labels()), 4)

    def test_groups_apart_and_unlike_wires(self):
        self.wires([2.0, 2.25, 2.5])
        self.wires([6.0, 6.25, 6.5])                        # (another drive, 3.5" away)
        self.wires([2.75], awg="10")                        # (one of its own size beside)
        self.wires([3.0], layer="24VDC BLU")                # (another color beside)
        got = sorted(t for t, _x, _y in self.labels())
        self.assertEqual(got, ["10 AWG BLK", "12 AWG BLK", "12 AWG BLK", "16 AWG BLU"])

    def test_side_by_side_but_not_along_each_other(self):
        self.wires([2.0], 2.0, 4.0)
        self.wires([2.25], 5.0, 9.0)                        # (close across, not alongside)
        self.assertEqual(len(self.labels()), 2)

    def test_a_bus_across_one_label_under_the_lowest(self):
        with self.p.edit("bus") as ed:
            for y in (8.0, 7.75, 7.5):
                ed.add(self.s, M.Wire([(1.0, y), (12.0, y)], layer="480V BLK"))
        got = self.labels()
        self.assertEqual(len(got), 1, got)
        self.assertLess(got[0][2], 7.5)

    def test_kept_up_to_date(self):
        self.wires([2.0, 2.25])
        self.assertEqual(len(self.labels()), 1)
        w = [w for w in self.s.wires() if w.points[0][0] == 2.25][0]
        with self.p.edit("size") as ed:
            ed.change(self.s, w.copy(awg="10"))
        self.assertEqual(len(self.labels()), 2)
        self.p.undo()
        self.assertEqual(len(self.labels()), 1)


if __name__ == "__main__":
    unittest.main()
