"""Opening a DXF (a double-click, File > Open) puts the drawing on the page: its coordinates
are the other program's. File > Import into a sheet keeps them."""
import os
import tempfile
import unittest

from tests.util import APP, window

from kanzonascad import fileio
from kanzonascad import model as M
from kanzonascad import scalefit as F


def _dxf(folder, name, x0, y0, w, h, text_h=None):
    import ezdxf
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 1
    ms = doc.modelspace()
    ms.add_lwpolyline([(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)], close=True)
    ms.add_line((x0, y0), (x0 + w, y0 + h))
    ms.add_text("LABEL", dxfattribs={"height": text_h or h / 20}).set_placement(
        (x0 + w * 0.1, y0 + h * 0.5))
    path = os.path.join(folder, name)
    doc.saveas(path)
    return path


class OpenDxfPlaceTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        from kanzonascad.main_window import MainWindow
        self.win = MainWindow()                 # (a double-click: opened before it shows)

    def tearDown(self):
        for i in range(self.win.tabs.count()):
            d = self.win.tabs.widget(i)
            if hasattr(d, "project"):
                d.project.saved_at = len(d.project.undo_stack)
        self.win.close()

    def open(self, path):
        d = self.win.open_path(path)
        self.win.resize(1300, 850)
        self.win.show()
        for _i in range(5):
            APP.processEvents()
        return d, d.view.sheet()

    def on_screen(self, v, bb):
        tl = v.to_world(v.rect().topLeft())
        br = v.to_world(v.rect().bottomRight())
        return tl[0] <= bb[0] and br[0] >= bb[2] and br[1] <= bb[1] and tl[1] >= bb[3]

    def test_far_away_drawing_is_moved_onto_the_page_and_shown(self):
        d, s = self.open(_dxf(self.dir, "far.dxf", 5000, -3000, 8, 5))
        self.assertEqual(s.scale_text(), "1:1")
        self.assertIsNone(F.outside(d.project, s))
        self.assertTrue(self.on_screen(d.view, s.extents()))
        self.assertFalse(d.project.undo_stack)          # (opened, not an edit to undo)

    def test_bigger_than_the_sheet_gets_a_scale_texts_kept_real_size(self):
        d, s = self.open(_dxf(self.dir, "big.dxf", -200, 100, 60, 40, text_h=2.0))
        self.assertEqual(s.scale_text(), "1:5")
        self.assertIsNone(F.outside(d.project, s))
        texts = [e for e in s.entities.values() if isinstance(e, M.Text)]
        self.assertAlmostEqual(texts[0].height, 2.0)   # the DXF's own size
        bb = s.extents()
        self.assertAlmostEqual(bb[2] - bb[0], 60.0, places=3)
        self.assertTrue(self.on_screen(d.view, bb))

    def test_on_the_page_stays_where_it_is(self):
        d, s = self.open(_dxf(self.dir, "onpage.dxf", 2, 2, 6, 4))
        self.assertEqual(s.extents()[:2], (2.0, 2.0))

    def test_kanzonascad_dxf_border_and_all_opens_where_it_was(self):
        win, v = window()
        try:
            p, s = v.project, v.sheet()
            with p.edit("draw") as ed:
                ed.add(s, M.Line((3, 3), (9, 7)))
            path = os.path.join(self.dir, "mine.dxf")
            fileio.export_dxf(p, s, path)
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()
        d, s2 = self.open(path)
        lines = [e for e in s2.entities.values() if isinstance(e, M.Line) and
                 e.layer != "BORDER"]
        self.assertTrue(any(tuple(e.p1) == (3.0, 3.0) and tuple(e.p2) == (9.0, 7.0)
                            for e in lines))

    def test_import_into_a_sheet_keeps_the_coordinates(self):
        win, v = window()
        try:
            p, s = v.project, v.sheet()
            fileio.import_dxf(p, s, _dxf(self.dir, "far2.dxf", 5000, -3000, 8, 5))
            self.assertAlmostEqual(s.extents()[0], 5000.0)
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()


class FirstZoomTest(unittest.TestCase):
    def test_a_zoom_before_the_window_shows_is_kept_and_fitted(self):
        from kanzonascad.main_window import MainWindow
        w = MainWindow()
        d = w.new_project()
        v = d.view
        with v.project.edit("x") as ed:
            ed.add(v.sheet(), M.Line((100, 100), (101, 101)))
        v.zoom("extents")                               # (as opening a drawing does)
        w.resize(1300, 850)
        w.show()
        for _i in range(5):
            APP.processEvents()
        self.assertTrue(abs(v.center[0] - 100.5) < 1e-6)   # not undone by a late zoom
        v.zoom_at(2.0, None)                            # the user's own zoom
        scale = v.scale
        w.resize(1100, 800)
        APP.processEvents()
        self.assertEqual(v.scale, scale)                # kept on a resize
        v.project.saved_at = len(v.project.undo_stack)
        w.close()


if __name__ == "__main__":
    unittest.main()
