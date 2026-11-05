"""Align objects (Panel tab): line the selection up by an edge or middle, to a picked object or
the selection's own edge; Import DXF or DWG starts where you imported from last."""
import os
import tempfile
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class AlignObjectsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.polar_on = self.v.ortho_on = False
        self.p = self.v.project
        self.s = self.v.sheet()
        with self.p.edit("boxes") as ed:
            self.a = ed.add(self.s, M.Polyline([(1, 1), (3, 1), (3, 2), (1, 2)], True))
            self.b = ed.add(self.s, M.Polyline([(4, 3), (5, 3), (5, 5), (4, 5)], True))
            self.c = ed.add(self.s, M.Polyline([(6, 0.5), (9, 0.5), (9, 1.5), (6, 1.5)], True))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def bb(self, e):
        return self.s.entities[e.id].bbox()

    def run_align(self, way, pick=None):
        self.v.set_selection({self.a.id, self.b.id, self.c.id})
        self.v.run(C.AlignObjectsCmd)
        type_in(self.v, way)
        if pick is None:
            self.v.enter()
        else:
            self.v.cmd.pick(pick)

    def test_bottom_to_a_picked_object_moves_only_up_and_down(self):
        steps = len(self.p.undo_stack)
        x_before = [self.bb(e)[0] for e in (self.a, self.b, self.c)]
        self.run_align("B", pick=(5, 4))                # the tall one, bottom at 3
        for e in (self.a, self.b, self.c):
            self.assertAlmostEqual(self.bb(e)[1], 3.0)
        self.assertEqual([self.bb(e)[0] for e in (self.a, self.b, self.c)], x_before)
        self.assertEqual(len(self.p.undo_stack), steps + 1)
        self.p.undo()
        self.assertAlmostEqual(self.bb(self.a)[1], 1.0)

    def test_left_edge_of_the_selection_with_enter(self):
        self.run_align("L")
        for e in (self.a, self.b, self.c):
            self.assertAlmostEqual(self.bb(e)[0], 1.0)

    def test_center_and_middle(self):
        self.run_align("C", pick=(2, 1))               # a: center x 2
        for e in (self.b, self.c):
            b = self.bb(e)
            self.assertAlmostEqual((b[0] + b[2]) / 2, 2.0)
        self.run_align("M")                             # the selection's middle
        mids = [(self.bb(e)[1] + self.bb(e)[3]) / 2 for e in (self.a, self.b, self.c)]
        self.assertAlmostEqual(max(mids) - min(mids), 0.0)

    def test_needs_two(self):
        self.v.set_selection({self.a.id})
        self.v.run(C.AlignObjectsCmd)
        self.assertIsNone(self.v.cmd)


class ImportFolderTest(unittest.TestCase):
    def test_import_starts_where_you_imported_from_last(self):
        from PySide6.QtWidgets import QFileDialog
        win, v = window()
        folder = tempfile.mkdtemp()
        seen = []
        real = QFileDialog.getOpenFileName

        def fake(parent, title, start, filt):
            seen.append(start)
            return (os.path.join(folder, "nothing.dxf"), "")
        QFileDialog.getOpenFileName = staticmethod(fake)
        try:
            from PySide6.QtWidgets import QMessageBox
            real_warn = QMessageBox.warning
            QMessageBox.warning = staticmethod(lambda *a, **k: None)
            try:
                win.import_dxf()                # (the file isn't there: a warning, no import)
                win.import_dxf()
            finally:
                QMessageBox.warning = real_warn
        finally:
            QFileDialog.getOpenFileName = real
            win.settings.remove("import_dir")
            v.project.saved_at = len(v.project.undo_stack)
            win.close()
        self.assertEqual(seen[1], folder)
        self.assertTrue(APP)


if __name__ == "__main__":
    unittest.main()
