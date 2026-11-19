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

    def wires(self, xs, y0=2.0, y1=6.0, layer="480V BLK", awg="", color=False):
        with self.p.edit("w") as ed:
            for x in xs:
                ed.add(self.s, M.Wire([(x, y0), (x, y1)], layer=layer, awg=awg,
                                      show_color=color))

    def in_line(self, x=None, y=None):
        """The gauge label is in line with the number of the wire at x (upright) or y
        (across), just after it, touching no wire (0.18.4: side by side)."""
        from kanzonascad import geometry as G
        g = wirenums.gauge_labels(self.p, self.s)[0]
        marks = wirenums.gauge_marks(self.p, self.s)
        if marks:
            # (0.18.5: an oval round the group, the label after its leader)
            (cx, cy), half, _thin, up, leader = marks[0]
            if x is not None:
                self.assertTrue(up)
                self.assertGreaterEqual(cx + half, x)
            else:
                self.assertFalse(up)
                self.assertLessEqual(cy - half, y)
            end = leader[-1]
            gb = g.bbox()
            self.assertLess(abs((gb[1] + gb[3]) / 2 - end[1]), g.height)
            self.assertTrue(gb[0] > end[0] or gb[2] < end[0])
            return
        nums = [t for t in wirenums.labels(self.p, self.s)
                if (x is not None and abs(t.angle - 90) < 1e-6 and abs(t.pos[0] - x) < 0.2) or
                (y is not None and abs(t.angle) < 1e-6 and abs(t.pos[1] - y) < 0.2)]
        self.assertTrue(nums)
        n = min(nums, key=lambda t: abs((t.pos[0] - x) if x is not None else (t.pos[1] - y)))
        nb, gb = n.bbox(), g.bbox()
        if x is not None:
            self.assertAlmostEqual((gb[0] + gb[2]) / 2, (nb[0] + nb[2]) / 2, places=6)
            self.assertTrue(gb[1] > nb[3] or gb[3] < nb[1])
        else:
            self.assertAlmostEqual((gb[1] + gb[3]) / 2, (nb[1] + nb[3]) / 2, places=6)
            self.assertTrue(gb[0] > nb[2] or gb[2] < nb[0])
        for w in self.s.wires():
            for a, b in zip(w.points, w.points[1:]):
                self.assertFalse(G.segment_hits_rect(a, b, gb), (g.text, gb, w.points))

    def labels(self):
        return [(t.text, round(t.pos[0], 3), round(t.pos[1], 3))
                for t in wirenums.gauge_labels(self.p, self.s)]

    def test_four_conductors_one_label_on_the_outside_one(self):
        self.wires([2.0, 2.25, 2.5, 2.75])                  # (a starter's conductors)
        got = self.labels()
        self.assertEqual(len(got), 1, got)
        self.assertEqual(got[0][0], "12 AWG")               # (the gauge alone, 0.18.4)
        self.in_line(x=2.75)                                # (by the rightmost's number)
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
        self.assertEqual(got, ["10 AWG", "12 AWG", "12 AWG", "16 AWG"])

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
        self.in_line(y=7.5)                                 # (by the lowest's number)

    def test_a_bus_of_three_colors_one_label(self):
        # (the owner's DS201 bus: BRN, ORG, YEL, "too busy": one label, the colors in order)
        with self.p.edit("bus") as ed:
            for y, lay in ((8.0, "480V BRN"), (7.75, "480V ORG"), (7.5, "480V YEL")):
                ed.add(self.s, M.Wire([(1.0, y), (6.0, y)], layer=lay, show_color=True))
        got = self.labels()
        self.assertEqual(len(got), 1, got)
        self.assertEqual(got[0][0], "12 AWG BRN, ORG, YEL")
        self.in_line(y=7.5)

    def test_conductors_and_a_ground_upright(self):
        self.wires([2.0, 2.25, 2.5], color=True)
        self.wires([2.75], layer="480V GRN", color=True)
        got = self.labels()
        self.assertEqual([t for t, _x, _y in got], ["12 AWG BLK, GRN"])
        # (only the ground's color shown: only it named)
        with self.p.edit("off") as ed:
            for w in list(self.s.wires()):
                if w.layer == "480V BLK":
                    ed.change(self.s, w.copy(show_color=False))
        self.assertEqual([t for t, _x, _y in self.labels()], ["12 AWG GRN"])
        self.in_line(x=2.75)

    def test_no_room_beside_it_goes_across_the_wire(self):
        # (a piece too short for the number and the label side by side: the label on the
        # other side of the wire, as before)
        with self.p.edit("w") as ed:
            ed.add(self.s, M.Wire([(2.0, 5.0), (2.5, 5.0)], layer="480V BLK"))
        g = wirenums.gauge_labels(self.p, self.s)[0]
        self.assertLess(g.bbox()[3], 5.0)                   # (under the wire)

    def test_smaller_than_the_numbers(self):
        self.wires([2.0])
        t = wirenums.gauge_labels(self.p, self.s)[0]
        self.assertAlmostEqual(t.height, 0.06 * self.s.k())
        self.assertLess(t.height, float(self.p.settings["wire_number_height"]) * self.s.k())
        with self.p.edit("h") as ed:
            ed.project_settings({"wire_gauge_height": 0.05})
        self.assertAlmostEqual(wirenums.gauge_labels(self.p, self.s)[0].height,
                               0.05 * self.s.k())

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
