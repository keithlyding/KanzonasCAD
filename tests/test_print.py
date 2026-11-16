"""Print... (File menu, Ctrl+P): the sheets chosen, one a page, fit to the paper (turned to
match it) or at their real size; the Print window's choices; the Sheets list picking several
sheets for it (the owner: "I need to be able to print selected or all sheets")."""
import os
import re
import tempfile
import unittest

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import print_out as P


def pages(path):
    with open(path, "rb") as f:
        return len(re.findall(rb"/Type\s*/Page[^s]", f.read()))


def ink(img):
    """(x0, y0, x1, y1) of the non-white pixels of a picture, or None."""
    w, h = img.width(), img.height()
    xs, ys = [], []
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            if img.pixelColor(x, y).lightness() < 200:
                xs.append(x)
                ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


class PlacementTest(unittest.TestCase):
    def test_fit_turns_a_wide_sheet_onto_a_tall_page(self):
        turn, f, x, y = P.placement(17, 11, 8.5, 11)          # ANSI B on letter
        self.assertTrue(turn)
        self.assertAlmostEqual(f, 11 / 17)                    # its 17" along the 11" side
        self.assertAlmostEqual(y, 0)
        self.assertAlmostEqual(x, (8.5 - 11 * f) / 2)

    def test_fit_keeps_a_sheet_that_matches(self):
        turn, f, x, y = P.placement(11, 8.5, 11, 8.5)
        self.assertFalse(turn)
        self.assertAlmostEqual(f, 1.0)
        self.assertAlmostEqual(x, 0)
        self.assertAlmostEqual(y, 0)
        turn, f, _x, _y = P.placement(8.5, 11, 17, 22)        # small sheet, big paper: bigger
        self.assertFalse(turn)
        self.assertAlmostEqual(f, 2.0)

    def test_actual_size_is_real_size_centered(self):
        turn, f, x, y = P.placement(17, 11, 11, 17, fit=False)
        self.assertTrue(turn)                                 # (the long sides together)
        self.assertEqual(f, 1.0)
        self.assertAlmostEqual(x, 0)
        self.assertAlmostEqual(y, 0)
        turn, f, x, y = P.placement(34, 22, 11, 17, fit=False)   # ANSI D on tabloid: cut off
        self.assertTrue(turn)
        self.assertAlmostEqual(x, (11 - 22) / 2)
        self.assertAlmostEqual(y, (17 - 34) / 2)


class PaintTest(unittest.TestCase):
    def setUp(self):
        self.p = M.Project.new()
        self.s = self.p.sheets[0]
        with self.p.edit("draw") as ed:
            ed.add(self.s, M.Line((1, 1), (10, 7)))

    def paint(self, page_w, page_h, fit=True, dpi=40, sheet=None):
        img = QImage(round(page_w * dpi), round(page_h * dpi), QImage.Format_RGB32)
        img.fill(QColor("white"))
        pa = QPainter(img)
        P.paint_sheet(pa, self.p, sheet or self.s, page_w, page_h, dpi, fit)
        pa.end()
        return img

    def test_the_sheet_fills_the_page_it_is_fit_to(self):
        for page in ((8.5, 11), (11, 8.5), (11, 17), (17, 11), (22, 34)):
            img = self.paint(*page)
            b = ink(img)
            turn, f, x, y = P.placement(*self.s.paper_inches(), *page)
            w, h = self.s.paper_inches()
            pw, ph = (h, w) if turn else (w, h)
            # the border is inside the paper as printed, the paper inside the page
            dpi = 40
            self.assertGreaterEqual(b[0], x * dpi - 2)
            self.assertGreaterEqual(b[1], y * dpi - 2)
            self.assertLessEqual(b[2], (x + pw * f) * dpi + 2)
            self.assertLessEqual(b[3], (y + ph * f) * dpi + 2)
            # and fills it one way: the frame reaches near both edges of the page's short fit
            span_w, span_h = (b[2] - b[0]) / dpi, (b[3] - b[1]) / dpi
            self.assertTrue(span_w > 0.85 * page[0] or span_h > 0.85 * page[1],
                            "%s: drawn %.2f x %.2f" % (page, span_w, span_h))

    def test_a_scaled_panel_sheet_prints_its_whole_paper(self):
        with self.p.edit("1:4") as ed:
            ed.sheet_scale(self.s, 0.25)
            ed.add(self.s, M.Line((4, 4), (40, 28)))
        b = ink(self.paint(8.5, 11))
        self.assertGreater((b[3] - b[1]) / 40, 0.85 * 11)

    def test_turned_onto_the_page_the_title_block_goes_to_the_top(self):
        # (a quarter turn counterclockwise, as a printer's landscape: the sheet's lower right,
        # where the title block is, at the page's upper right; on an empty sheet the title
        # block is the corner with the most ink)
        blank = M.Project.new()
        img = QImage(340, 440, QImage.Format_RGB32)
        img.fill(QColor("white"))
        pa = QPainter(img)
        P.paint_sheet(pa, blank, blank.sheets[0], 8.5, 11, 40)
        pa.end()
        w, h = img.width(), img.height()

        def dark(x0, y0):
            return sum(img.pixelColor(x, y).lightness() < 200
                       for y in range(y0, y0 + h // 4) for x in range(x0, x0 + w // 4))
        corners = {"top right": dark(w - w // 4, 0), "top left": dark(0, 0),
                   "bottom right": dark(w - w // 4, h - h // 4),
                   "bottom left": dark(0, h - h // 4)}
        self.assertEqual(max(corners, key=corners.get), "top right", corners)


class PrintToFileTest(unittest.TestCase):
    def test_one_page_a_sheet_in_the_order_given(self):
        p = M.Project.new()
        with p.edit("sheets") as ed:
            for i in range(3):
                ed.add_sheet(p.make_sheet("S%d" % i), len(p.sheets))
        with tempfile.TemporaryDirectory() as tmp:
            for chosen in ([p.sheets[0]], p.sheets, [p.sheets[3], p.sheets[1]]):
                path = os.path.join(tmp, "out.pdf")
                n = P.print_sheets(p, P.pdf_printer(path), chosen)
                self.assertEqual(n, len(chosen))
                self.assertEqual(pages(path), len(chosen))
        self.assertFalse(p.is_modified() and p.saved_at == len(p.undo_stack))

    def test_printing_changes_nothing(self):
        p = M.Project.new()
        with p.edit("draw") as ed:
            ed.add(p.sheets[0], M.Text((2, 2), "NOTE", 0.125))
        before, rev, steps = p.to_dict(), p.revision, len(p.undo_stack)
        with tempfile.TemporaryDirectory() as tmp:
            P.print_sheets(p, P.pdf_printer(os.path.join(tmp, "a.pdf")), p.sheets)
        self.assertEqual(p.to_dict(), before)
        self.assertEqual((p.revision, len(p.undo_stack)), (rev, steps))


class PrintWindowTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        with self.p.edit("sheets") as ed:
            for i in range(3):
                ed.add_sheet(self.p.make_sheet("S%d" % i), len(self.p.sheets))
        self.win._fill_sheets()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def dialog(self):
        from kanzonascad.print_dialog import PrintDialog
        return PrintDialog(self.win, self.p, self.v.sheet(), self.win.selected_sheet_ids())

    def test_this_sheet_to_start_and_all_of_them(self):
        d = self.dialog()
        self.assertEqual(d.sheets(), [self.v.sheet()])
        self.assertTrue(d.fit.isChecked())
        self.assertTrue(d.mono.isChecked())
        d.all_of_them.setChecked(True)
        d._update()
        self.assertEqual(d.sheets(), self.p.sheets)
        self.assertEqual(d.print_button.text(), "Print 4 sheets")
        self.assertEqual(d.printer_box.itemText(d.printer_box.count() - 1), "PDF file")

    def test_the_sheets_selected_in_the_list(self):
        lst = self.win.sheet_list
        lst.item(1).setSelected(True)
        lst.item(3).setSelected(True)
        ids = self.win.selected_sheet_ids()
        self.assertEqual(len(ids), 3)                         # (with the one shown)
        self.win._fill_sheets()                               # (kept when filled again)
        self.assertEqual(sorted(self.win.selected_sheet_ids()), sorted(ids))
        d = self.dialog()
        self.assertTrue(d.these.isChecked())
        self.assertEqual([s.id for s in d.sheets()],
                         [s.id for s in self.p.sheets if s.id in ids])
        d._tick_all(False)
        self.assertEqual(d.sheets(), [])
        self.assertFalse(d.print_button.isEnabled())

    def test_print_into_a_pdf_file(self):
        d = self.dialog()
        d.printer_box.setCurrentIndex(d.printer_box.count() - 1)
        d.all_of_them.setChecked(True)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "set.pdf")
            from PySide6.QtWidgets import QFileDialog
            saved = QFileDialog.getSaveFileName
            QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (path, ""))
            try:
                self.assertEqual(d.run(tmp), 4)
            finally:
                QFileDialog.getSaveFileName = saved
            self.assertEqual(pages(path), 4)

    def test_ctrl_click_picks_without_changing_the_sheet_shown(self):
        shown = self.v.sheet_id
        from PySide6.QtTest import QTest
        lst = self.win.sheet_list
        r = lst.visualItemRect(lst.item(2))
        QTest.mouseClick(lst.viewport(), Qt.LeftButton, Qt.ControlModifier, r.center())
        APP.processEvents()
        self.assertEqual(self.v.sheet_id, shown)
        self.assertEqual(len(self.win.selected_sheet_ids()), 2)


if __name__ == "__main__":
    unittest.main()
