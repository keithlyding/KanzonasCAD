"""Choosing a panel sheet's scale: scalefit (no Qt), the Sheet scale window, and the status
bar's scale menu, Fit and warning."""
import json
import unittest

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import scalefit as F


class ScaleFitModelTest(unittest.TestCase):
    def setUp(self):
        self.p = M.Project.new()
        self.s = self.p.sheets[0]
        with self.p.edit("panel") as ed:
            ed.sheet_meta(self.s, kind="panel")

    def test_room_leaves_out_the_corner_title_block(self):
        area, tb = F.room(self.p, self.s)
        self.assertIsNotNone(tb)                            # the default: a corner title block
        boxes = F.free_boxes(area, tb)
        self.assertEqual(len(boxes), 2)                     # above it and left of it
        for b in boxes:
            self.assertFalse(b[0] < tb[0] and b[2] > tb[0] and b[1] < tb[3] and b[3] > tb[1])
        # the room is the same at every scale (it is in paper inches)
        with self.p.edit("1:4") as ed:
            ed.sheet_scale(self.s, 0.25)
        area4, tb4 = F.room(self.p, self.s)
        for a, b in zip(area + tb, area4 + tb4):
            self.assertAlmostEqual(a, b)

    def test_best_scale_is_the_biggest_that_fits(self):
        area, tb = F.room(self.p, self.s)
        name, s = F.best_scale(24, 36, area, tb)
        self.assertEqual((name, s), ("", 0.25))             # 36 / 4 = 9 in on an 11 in sheet
        self.assertTrue(F.fits(24, 36, s, area, tb))
        self.assertFalse(F.fits(24, 36, 0.5, area, tb))
        # architectural presets for a sheet that uses them
        name, s = F.best_scale(24, 36, area, tb, named=True)
        self.assertEqual(name, '3" = 1\'-0"')
        # past the presets: the next whole 1:N
        name, s = F.best_scale(400, 600, area, tb)
        self.assertEqual(name, "")
        n = round(1 / s)
        self.assertTrue(F.fits(400, 600, 1.0 / n, area, tb))
        self.assertFalse(F.fits(400, 600, 1.0 / (n - 1), area, tb))

    def test_cabinet_front_and_side(self):
        self.assertIsNone(F.cabinet_box(None))
        self.assertEqual(F.cabinet_box([30, 48, 0]), (30, 48))
        self.assertEqual(F.cabinet_box([30, 48, 12]), (30 + F.GAP + 12, 48))
        self.assertIsNone(F.fit_for(self.p, self.s))        # nothing drawn, no cabinet
        with self.p.edit("cabinet") as ed:
            ed.sheet_meta(self.s, cabinet=[30, 48, 12])
        name, s = F.fit_for(self.p, self.s)
        area, tb = F.room(self.p, self.s)
        self.assertTrue(F.fits(48, 48, s, area, tb))
        # kept with the project
        again = M.Project.from_dict(json.loads(json.dumps(self.p.to_dict())))
        self.assertEqual(again.sheets[0].cabinet, [30.0, 48.0, 12.0])

    def test_in_words(self):
        self.assertEqual(F.in_words(0.25), "1 inch on paper = 4 inches of panel")
        self.assertIn("real size", F.in_words(1.0))
        self.assertEqual(F.in_words(1 / 4, '3" = 1\'-0"'), "3 inches on paper = 1 foot of panel")
        self.assertEqual(F.in_words(1 / 48, '1/4" = 1\'-0"'),
                         "1/4 inch on paper = 1 foot of panel")
        self.assertEqual(F.in_words(1 / 8, '1-1/2" = 1\'-0"'),
                         "1-1/2 inches on paper = 1 foot of panel")

    def test_outside_and_fit_with_centering_undo_in_one_step(self):
        with self.p.edit("draw") as ed:
            ed.add(self.s, M.Line((0, 0), (40, 60)))
            t = ed.add(self.s, M.Text((5, 5), "NOTE", 0.125))
        self.assertEqual(F.outside(self.p, self.s), "past the border")
        name, s = F.fit_for(self.p, self.s)
        steps = len(self.p.undo_stack)
        moved = F.apply(self.p, self.s, name, s, center=True)
        self.assertIsNotNone(moved)
        self.assertEqual(len(self.p.undo_stack), steps + 1)
        self.assertIsNone(F.outside(self.p, self.s))
        area, tb = F.room(self.p, self.s)
        self.assertTrue(F.placed_inside(self.s.extents(), s, area, tb))
        # paper-sized text kept its printed height
        self.assertAlmostEqual(self.s.entities[t.id].height * s, 0.125)
        self.p.undo()
        self.assertEqual(self.s.scale, 1.0)
        self.assertEqual(self.s.extents()[:2], (0.0, 0.0))

    def test_over_the_title_block(self):
        area, tb = F.room(self.p, self.s)
        with self.p.edit("draw") as ed:        # a small box right on the title block
            ed.add(self.s, M.Line(((tb[0] + tb[2]) / 2, (tb[1] + tb[3]) / 2),
                                  ((tb[0] + tb[2]) / 2 + 1, (tb[1] + tb[3]) / 2 + 0.5)))
        self.assertEqual(F.outside(self.p, self.s), "over the title block")


class SheetScaleWindowTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.s = self.v.sheet()
        with self.p.edit("panel") as ed:
            ed.sheet_meta(self.s, kind="panel")

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def test_fit_from_the_cabinet_then_ok(self):
        from kanzonascad.scale_dialog import SheetScaleDialog
        d = SheetScaleDialog(self.win, self.p, self.s, None)
        self.assertFalse(d.fit_btn.isEnabled())             # nothing to fit yet
        for b, x in zip(d.cab, (30, 48, 12)):
            b.setValue(x)
        self.assertTrue(d.fit_btn.isEnabled())
        d.fit()
        self.assertEqual(d.combo.currentText(), "1:8")
        self.assertEqual(d.words.text(), "1 inch on paper = 8 inches of panel")
        self.assertIn("front and side", d.usage.text())
        self.assertEqual(d.state(d.scale()), "good")
        d.grab()                                            # the preview paints
        d._ok()
        self.assertEqual(self.s.scale_text(), "1:8")
        self.assertEqual(self.s.cabinet, [30.0, 48.0, 12.0])

    def test_too_big_says_so_and_fit_moves_it(self):
        from kanzonascad.scale_dialog import SheetScaleDialog
        with self.p.edit("draw") as ed:
            ed.add(self.s, M.Line((0, 0), (100, 150)))
        d = SheetScaleDialog(self.win, self.p, self.s, None)
        self.assertTrue(d.center.isChecked())               # where it is, it isn't inside
        self.assertEqual(d.state(d.scale()), "bad")
        self.assertIn("too big", d.usage.text())
        d.grab()
        d.fit()
        self.assertEqual(d.state(d.scale()), "good")
        d._ok()
        self.assertIsNone(F.outside(self.p, self.s))

    def test_status_bar_menu_fit_and_warning(self):
        with self.p.edit("draw") as ed:
            ed.add(self.s, M.Line((0, 0), (100, 150)))
        self.win._update_ui()
        self.assertIn("doesn't fit", self.win.scale_label.text())
        self.win._fill_scale_menu()
        names = [a.text() for a in self.win.scale_menu.actions()]
        self.assertTrue(names[0].startswith("Fit ("))
        self.assertIn("1:4", names)
        self.assertIn("More...", names)
        self.win.fit_scale()
        self.assertNotIn("doesn't fit", self.win.scale_label.text())
        self.assertIsNone(F.outside(self.p, self.s))
        # a preset from the menu
        self.win._set_scale("", 1 / 20)
        self.assertEqual(self.s.scale_text(), "1:20")
        APP.processEvents()


if __name__ == "__main__":
    unittest.main()
