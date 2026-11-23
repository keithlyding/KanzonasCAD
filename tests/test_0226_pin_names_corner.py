"""A pin's name beside it on a copy (Show pin names) goes in along the pin's lead line, or in
from the edge of the drawing the pin is on (the owner, 0.22.2: a drive's PE2, on the bottom
line of its box near the corner beside T3, was taken by the middle of the drawing for a pin on
the side, its name drawn over T3's: "I don't like the way this looks ... PE2 and T3 are right
on top of each other")."""
import unittest

from tests.util import APP

from kanzonascad import model as M
from kanzonascad.library import Library


def drive():
    """The owner's drive as drawn: a box 4.25" wide, 2.5" tall, the pins on its top and bottom
    lines with no lead lines, PE2 near the lower right corner."""
    box = M.Polyline([(0, 0), (4.25, 0), (4.25, 2.5), (0, 2.5)], True)
    pins = [{"name": n, "pos": (x, 2.5)} for n, x in (("L1", 0.5), ("L2", 1.5), ("L3", 2.5))]
    pins += [{"name": n, "pos": (x, 0.0)}
             for n, x in (("T1", 0.5), ("T2", 1.5), ("T3", 2.5), ("PE2", 3.5))]
    return M.BlockDef("Owner VFD", "symbol", [box, M.Text((2.0, 1.25), "VFD", 0.3, angle=90)],
                      pins, (-0.5, 1.25), 0.25, "Drives", "", "device", "", "VFD",
                      show_pins=True)


def overlaps(texts):
    out = []
    for i, a in enumerate(texts):
        for b in texts[i + 1:]:
            p, q = a.bbox(), b.bbox()
            if p[0] < q[2] and q[0] < p[2] and p[1] < q[3] and q[1] < p[3]:
                out.append((a.text, b.text))
    return out


class PinNamesAtCornersTest(unittest.TestCase):
    def test_a_pin_on_the_bottom_line_near_a_corner(self):
        for angle in (0.0, 90.0, 180.0, 270.0):
            ins = M.Insert("Owner VFD", (10.0, 10.0), angle=angle, defn=drive())
            texts = ins.pin_texts()
            by = {t.text: t for t in texts}
            self.assertEqual((by["PE2"].align, by["PE2"].valign),
                             (by["T3"].align, by["T3"].valign), angle)
            self.assertEqual(overlaps(texts), [], angle)
        self.assertTrue(APP)

    def test_lead_lines_and_the_built_in_drive(self):
        d = Library().get("symbol", "Variable frequency drive")
        shown = M.BlockDef.from_dict(dict(d.to_dict(), show_pins=True))
        for angle in (0.0, 90.0, 180.0, 270.0):
            texts = M.Insert(shown.name, (10.0, 10.0), angle=angle, defn=shown).pin_texts()
            self.assertEqual(len(texts), len(d.pins))
            self.assertEqual(overlaps(texts), [], angle)
        # (L1 on a lead line out to the left: its name in toward the drive, to its right)
        by = {t.text: t for t in M.Insert(shown.name, (10.0, 10.0), defn=shown).pin_texts()}
        self.assertEqual(by["L1"].align, "left")
        self.assertEqual(by["T1"].align, "right")


if __name__ == "__main__":
    unittest.main()
