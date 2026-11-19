"""A group of wires sharing a gauge label: an oval round them and a leader out to the label
(the owner, 0.18.5: "can we have like a 3d circle that goes around the 3 wires to say what
gauge they all are?"; asked: an oval and a leader line)."""
import os
import tempfile
import unittest

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import wirelayers
from kanzonascad import wirenums


class GaugeRingTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()
        with self.p.edit("w") as ed:
            wirelayers.add_preset(ed, self.p, ["480 V"])
            for x in (2.0, 2.25, 2.5):
                ed.add(self.s, M.Wire([(x, 1.0), (x, 7.0)], layer="480V BLK"))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_oval_round_the_group_and_a_leader(self):
        labels = wirenums.gauge_labels(self.p, self.s)
        marks = wirenums.gauge_marks(self.p, self.s)
        self.assertEqual([t.text for t in labels], ["12 AWG"])
        self.assertEqual(len(marks), 1)
        (cx, cy), half, thin, up, leader = marks[0]
        self.assertTrue(up)
        self.assertLess(cx - half, 2.0)                     # (round all three)
        self.assertGreater(cx + half, 2.5)
        self.assertTrue(1.0 < cy < 7.0)
        a, b, c = leader
        self.assertAlmostEqual(a[0], cx + half)             # (from the oval's end)
        self.assertAlmostEqual(abs(b[0] - a[0]), abs(b[1] - a[1]))   # (out at 45 degrees)
        t = labels[0]
        self.assertGreater(t.bbox()[0], c[0])               # (the label after the leader)
        self.assertAlmostEqual(t.angle, 0.0)

    def test_a_single_wire_keeps_its_plain_label(self):
        with self.p.edit("one") as ed:
            ed.add(self.s, M.Wire([(8.0, 1.0), (8.0, 7.0)], layer="480V BLK"))
        self.assertEqual(len(wirenums.gauge_marks(self.p, self.s)), 1)
        self.assertEqual(len(wirenums.gauge_labels(self.p, self.s)), 2)

    def test_drawn_and_exported(self):
        import ezdxf
        from kanzonascad import fileio
        path = os.path.join(tempfile.mkdtemp(), "x.dxf")
        fileio.export_dxf(self.p, self.s, path)
        doc = ezdxf.readfile(path)
        texts = [e.dxf.text for e in doc.modelspace() if e.dxftype() == "TEXT"]
        self.assertIn("12 AWG", texts)
        closed = [e for e in doc.modelspace() if e.dxftype() == "LWPOLYLINE" and e.closed]
        self.assertTrue(closed)


if __name__ == "__main__":
    unittest.main()
