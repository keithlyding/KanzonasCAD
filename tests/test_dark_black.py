"""Black objects show on the dark drawing (drawn light, as AutoCAD's color 7), and white ones on
white paper (drawn dark); the color itself is kept, and prints as it is."""
import unittest

from PySide6.QtGui import QColor

from tests.util import APP

from kanzonascad import model as M
from kanzonascad.render import Palette


class DarkBlackTest(unittest.TestCase):
    def test_black_inverts_on_dark_and_white_on_light(self):
        p = M.Project.new()
        black = M.Line((0, 0), (1, 0), color="#000000")
        near = M.Line((0, 0), (1, 0), color="#101010")
        white = M.Line((0, 0), (1, 0), color="#ffffff")
        red = M.Line((0, 0), (1, 0), color="#ff0000")
        dark, light = Palette(True), Palette(False)
        self.assertEqual(dark.color(p, black), dark.ink)
        self.assertEqual(dark.color(p, near), dark.ink)
        self.assertEqual(light.color(p, black), QColor("#000000"))
        self.assertEqual(light.color(p, white), light.ink)
        self.assertEqual(dark.color(p, white), QColor("#ffffff"))
        self.assertEqual(dark.color(p, red), QColor("#ff0000"))
        self.assertEqual(black.color, "#000000")              # (kept: it prints black)
        # a layer colored black too
        with p.edit("layer") as ed:
            ed.layer("BLK", None, M.Layer("BLK", "#000000").to_dict())
        self.assertEqual(dark.color(p, M.Line((0, 0), (1, 0), layer="BLK")), dark.ink)
        self.assertTrue(APP)


if __name__ == "__main__":
    unittest.main()
