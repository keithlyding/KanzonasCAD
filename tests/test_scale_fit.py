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

    def test_closed_window_goes_at_once(self):
        """Sheet scale, opened and cancelled, leaves nothing for the garbage collector: no
        reference cycle keeps the window, and none of its widgets is owned by Python while Qt
        gives it a parent. Both together let the collector free a window's widgets in any
        order later on, and the unit tests crashed (segfault) about one run in four."""
        import shiboken6
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QWidget
        from kanzonascad.scale_dialog import SheetScaleDialog, sheet_scale
        d = SheetScaleDialog(self.win, self.p, self.s, None)
        # (not through findChildren, which itself hands what it finds to the parent)
        wrong = [type(w).__name__ for w in shiboken6.getAllValidWrappers()
                 if isinstance(w, QWidget) and w is not d and w.window() is d
                 and shiboken6.ownedByPython(w)]
        self.assertEqual(wrong, [])
        d.deleteLater()
        del d
        for _i in range(3):
            # (Cancel as a person would: findChildren here would hand the window back to Qt)
            QTimer.singleShot(0, lambda: APP.activeModalWidget().reject())
            self.assertFalse(sheet_scale(self.win, self.p, self.s, None))
        APP.processEvents()
        # gone already (a window kept by a cycle stays a child of the main window until a
        # collection)
        self.assertEqual(self.win.findChildren(SheetScaleDialog), [])

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


class FitUpToTheFrameTest(unittest.TestCase):
    """Fit picks the biggest scale at which the status bar doesn't say "doesn't fit" (the
    owner, with an AutoCAD Electrical sheet: "Fit made it 1:5, but 1:4 fits as well"): the
    margin kept clear is used when the drawing needs it."""

    def setUp(self):
        self.p = M.Project.new()
        self.s = self.p.sheets[0]               # ANSI B, title block in the lower right

    def test_owner_sheet(self):
        # the owner's drawing: 55.39" x 33.91", 8.48" tall at 1:4; above the title block the
        # room is 8.625" up to the frame and the title block, 8.125" with the margin
        with self.p.edit("draw") as ed:
            # (placed over the title block at first)
            ed.add(self.s, M.Polyline([(36.17, -12.64), (91.56, -12.64), (91.56, 21.27),
                                       (36.17, 21.27)], True))
        self.assertEqual(F.fit_for(self.p, self.s), ("", 0.25))
        box = F.drawing_box(self.s)
        area, tb = F.room(self.p, self.s)
        self.assertFalse(F.placed_inside(box, 0.25, area, tb))
        F.apply(self.p, self.s, "", 0.25, center=True)
        self.assertIsNone(F.outside(self.p, self.s))
        b = [c * 0.25 for c in F.drawing_box(self.s)]
        a, t = F.limits(area, tb)
        # centered in the room above the title block, the margin shared top and bottom
        self.assertAlmostEqual(b[1] - t[3], a[3] - b[3])
        self.assertAlmostEqual(b[0] - a[0], a[2] - b[2])

    def test_margin_kept_when_there_is_room(self):
        with self.p.edit("draw") as ed:
            ed.add(self.s, M.Polyline([(0, 0), (20, 0), (20, 10), (0, 10)], True))
        self.assertEqual(F.fit_for(self.p, self.s), ("", 0.5))
        F.apply(self.p, self.s, "", 0.5, center=True)
        area, tb = F.room(self.p, self.s)
        b = [c * 0.5 for c in F.drawing_box(self.s)]
        # (10" x 5" in the room with the margin, centered there)
        self.assertTrue(b[0] >= area[0] - 1e-9 and b[2] <= area[2] + 1e-9 and
                        b[1] >= tb[3] - 1e-9 and b[3] <= area[3] + 1e-9)

    def test_fit_never_says_doesnt_fit(self):
        import random
        rnd = random.Random(3)
        for _i in range(60):
            p = M.Project.new()
            s = p.sheets[0]
            w, h = rnd.uniform(1, 200), rnd.uniform(1, 200)
            with p.edit("draw") as ed:
                ed.add(s, M.Polyline([(0, 0), (w, 0), (w, h), (0, h)], True))
            name, v = F.fit_for(p, s)
            F.apply(p, s, name, v, center=True)
            self.assertIsNone(F.outside(p, s), (w, h, v))
            # and the next bigger preset would not fit
            bigger = [x for _n, x in F.presets_like("") if x > v + 1e-12]
            if bigger:
                area, tb = F.room(p, s)
                self.assertFalse(F.fits(w, h, min(bigger), area, tb), (w, h, v))


class RotateSheetTest(unittest.TestCase):
    def setUp(self):
        self.p = M.Project.new()
        self.s = self.p.sheets[0]

    def _corner_of_title_block(self):
        from kanzonascad.sheetframe import title_block_rect
        tb = title_block_rect(self.p, self.s)
        w, h = self.s.paper()
        cx, cy = (tb[0] + tb[2]) / 2, (tb[1] + tb[3]) / 2
        return ("bottom" if cy < h / 2 else "top") + " " + ("left" if cx < w / 2 else "right")

    def test_frame_turns_with_the_sheet_both_ways(self):
        self.assertEqual(self._corner_of_title_block(), "bottom right")
        zone = self.s.zone_at(*self.s.turn(3.0, 3.0))
        for clockwise, rot, paper, corner in ((True, 270, (11.0, 17.0), "bottom left"),
                                              (True, 180, (17.0, 11.0), "top left"),
                                              (False, 270, (11.0, 17.0), "bottom left"),
                                              (False, 0, (17.0, 11.0), "bottom right"),
                                              (False, 90, (11.0, 17.0), "top right")):
            F.rotate(self.p, self.s, clockwise)
            self.assertEqual(self.s.rotation, rot)
            self.assertEqual(self.s.paper_inches(), paper)
            self.assertEqual(self._corner_of_title_block(), corner)
            # the zones turn too: a spot of the layout keeps its zone
            self.assertEqual(self.s.zone_at(*self.s.turn(3.0, 3.0)), zone)
            # the border and the title block's texts turn (rotated text), the frame inside
            from kanzonascad.sheetframe import frame_entities
            ents = frame_entities(self.p, self.s)
            w, h = self.s.paper()
            for e in ents:
                bb = e.bbox()
                self.assertTrue(-1e-6 <= bb[0] and bb[2] <= w + 1e-6 and -1e-6 <= bb[1] and
                                bb[3] <= h + 1e-6, (rot, e))
            texts = [e for e in ents if isinstance(e, M.Text)]
            self.assertTrue(all(abs((t.angle - rot) % 360) < 1e-6 for t in texts))
        again = M.Project.from_dict(json.loads(json.dumps(self.p.to_dict())))
        self.assertEqual(again.sheets[0].rotation, 90)

    def test_drawing_stays_upright_and_on_the_page_one_step_each(self):
        with self.p.edit("draw") as ed:
            ln = ed.add(self.s, M.Line((3, 3), (8, 8)))
            t = ed.add(self.s, M.Text((3, 2), "NOTE", 0.2))
        steps = len(self.p.undo_stack)
        F.rotate(self.p, self.s, True)
        self.assertEqual(len(self.p.undo_stack), steps + 1)
        self.assertEqual(self.s.entities[t.id].angle, 0.0)              # upright
        a, b = self.s.entities[ln.id].p1, self.s.entities[ln.id].p2
        self.assertAlmostEqual(b[0] - a[0], 5)                          # same shape
        self.assertIsNone(F.outside(self.p, self.s))
        self.p.undo()
        self.assertEqual(self.s.rotation, 0)
        self.assertEqual(self.s.extents()[:2], (3.0, 2.0))

    def test_other_way_only_when_it_prints_bigger(self):
        w, h = F.cabinet_box([20, 48, 8])
        rot, (name, v) = F.other_way(self.p, self.s, w, h)
        # 1:4 instead of 1:5 (turned, the title block stands tall in the lower left corner;
        # up to the frame and the title block, 0.15.7: with the margin kept, 1:5 instead of 1:8)
        self.assertEqual((rot, v), (270, 0.25))
        self.assertIsNone(F.other_way(self.p, self.s, *F.cabinet_box([36, 24, 10])))
        with self.p.edit("draw") as ed:
            ed.add(self.s, M.Line((0, 0), (w, h)))
        steps = len(self.p.undo_stack)
        F.apply(self.p, self.s, name, v, center=True, rotation=270)
        self.assertEqual(len(self.p.undo_stack), steps + 1)
        self.assertEqual((self.s.rotation, self.s.scale), (270, 0.25))
        self.assertIsNone(F.outside(self.p, self.s))

    def test_pdf_page_is_tall(self):
        import os
        import re
        import tempfile
        from kanzonascad import fileio
        F.rotate(self.p, self.s, True)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "p.pdf")
            fileio.export_pdf(self.p, path)
            with open(path, "rb") as f:
                data = f.read()
        box = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)", data)
        self.assertIsNotNone(box)
        w, h = float(box.group(1)), float(box.group(2))
        self.assertAlmostEqual(h / w, 17 / 11, places=2)

    def test_shortcuts_menu_and_window(self):
        from kanzonascad.scale_dialog import SheetScaleDialog
        win, v = window()
        try:
            p, s = v.project, v.sheet()
            keys = [k.toString() for k in win.acts["sheet_cw"].shortcuts()]
            self.assertIn("Ctrl+Shift++", keys)
            self.assertIn("Ctrl+Shift+-",
                          [k.toString() for k in win.acts["sheet_ccw"].shortcuts()])
            win.acts["sheet_cw"].trigger()
            APP.processEvents()
            self.assertEqual(s.rotation, 270)
            win.acts["sheet_ccw"].trigger()
            self.assertEqual(s.rotation, 0)
            d = SheetScaleDialog(win, p, s, None)
            for b, x in zip(d.cab, (20, 48, 8)):
                b.setValue(x)
            d.fit()
            self.assertEqual(d.combo.currentText(), "1:5")
            self.assertFalse(d.suggest.isHidden())
            self.assertIn("1:4 instead of 1:5", d.suggest.text())
            d._turn_suggested()
            self.assertEqual((d.rotation(), d.combo.currentText()), (270, "1:4"))
            self.assertTrue(d.suggest.isHidden())
            d.grab()
            d._ok()
            self.assertEqual((s.rotation, s.scale_text()), (270, "1:4"))
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()


if __name__ == "__main__":
    unittest.main()
