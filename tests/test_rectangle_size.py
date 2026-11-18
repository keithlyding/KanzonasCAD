"""A rectangle's size typed after its first corner (the owner: "I'm trying to make a rectangle
that is 0.19x0.15" and it's coming out as 8.76x3.76"": a plain x,y was taken as the corner
x,y of the sheet). After the first corner, x,y is the size (as AutoCAD's dynamic input takes
it), #x,y a point, @x,y as always; D asks the length and width, then which way it goes. A
dashed box takes its size the same way."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class RectangleSizeTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False

    def tearDown(self):
        p = self.v.project
        p.saved_at = len(p.undo_stack)
        self.win.close()

    def last(self, kind=M.Polyline):
        got = [e for e in self.v.sheet().entities.values() if isinstance(e, kind)]
        return got[-1]

    def size(self, e):
        bb = M.Polyline(e.points, True).bbox()
        return (round(bb[2] - bb[0], 9), round(bb[3] - bb[1], 9)), (round(bb[0], 9),
                                                                   round(bb[1], 9))

    def test_typed_size(self):
        self.v.run(C.RectangleCmd)
        type_in(self.v, "8.95,3.91", "0.19,0.15")
        self.assertEqual(self.size(self.last()), ((0.19, 0.15), (8.95, 3.91)))

    def test_negative_size_goes_left_and_down(self):
        self.v.run(C.RectangleCmd)
        type_in(self.v, "5,5", "-2,-1")
        self.assertEqual(self.size(self.last()), ((2.0, 1.0), (3.0, 4.0)))

    def test_size_goes_the_way_the_mouse_is(self):
        # (the owner, 0.18.2: "I set it to 72,72. It built the rectangle to the right
        # dimensions but in a different direction than my mouse was moving")
        for cursor, corner in (((2.0, 9.0), (-67.0, 5.0)),      # left and up
                               ((2.0, 1.0), (-67.0, -67.0)),    # left and down
                               ((9.0, 1.0), (5.0, -67.0)),      # right and down
                               ((9.0, 9.0), (5.0, 5.0))):       # right and up
            self.v.run(C.RectangleCmd)
            type_in(self.v, "5,5")
            self.v.cursor = cursor
            type_in(self.v, "72,72")
            self.assertEqual(self.size(self.last()), ((72.0, 72.0), corner), cursor)

    def test_a_typed_sign_wins_over_the_mouse(self):
        self.v.run(C.RectangleCmd)
        type_in(self.v, "5,5")
        self.v.cursor = (2.0, 1.0)                          # (left and down)
        type_in(self.v, "+2,+1")
        self.assertEqual(self.size(self.last()), ((2.0, 1.0), (5.0, 5.0)))

    def test_a_point_with_hash_and_relative_with_at(self):
        self.v.run(C.RectangleCmd)
        type_in(self.v, "1,1", "#3,2")
        self.assertEqual(self.size(self.last()), ((2.0, 1.0), (1.0, 1.0)))
        self.v.run(C.RectangleCmd)
        type_in(self.v, "5,5", "@1,0.5")
        self.assertEqual(self.size(self.last()), ((1.0, 0.5), (5.0, 5.0)))

    def test_d_asks_length_and_width_then_the_side(self):
        self.v.run(C.RectangleCmd)
        type_in(self.v, "5,5", "D", "0.19", "0.15")
        self.assertIsNotNone(self.v.cmd)
        shown = self.v.cmd.preview((4.0, 4.0))[0]
        self.assertEqual(self.size(shown), ((0.19, 0.15), (4.81, 4.85)))
        self.v.cmd.point((4.0, 4.0))                    # (a click down and left of it)
        self.assertEqual(self.size(self.last()), ((0.19, 0.15), (4.81, 4.85)))
        # Enter: up and right
        self.v.run(C.RectangleCmd)
        type_in(self.v, "1,1", "D", "2", "1")
        self.v.cmd.enter()
        self.assertEqual(self.size(self.last()), ((2.0, 1.0), (1.0, 1.0)))

    def test_the_first_corner_is_still_a_point(self):
        self.v.run(C.RectangleCmd)
        type_in(self.v, "0.19,0.15", "1,1")
        self.assertEqual(self.size(self.last()), ((1.0, 1.0), (0.19, 0.15)))

    def test_a_dashed_box_takes_its_size_too(self):
        self.win.ask_dash_box = lambda box: {"text": "", "device": None}
        try:
            self.v.run(C.DashBoxCmd)
            type_in(self.v, "2,8", "3,-2")
        finally:
            del self.win.ask_dash_box
        b = self.last(M.DashBox)
        self.assertEqual(self.size(b), ((3.0, 2.0), (2.0, 6.0)))


if __name__ == "__main__":
    unittest.main()
