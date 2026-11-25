"""Export to PDF asks for color or black and white (the owner, 0.26): the window's Save as type
offers both, starts on the last pick, and keeps it (the same setting as Options' Export to PDF
in the layers' colors)."""
import os
import tempfile
import unittest
from unittest import mock

from PySide6.QtWidgets import QFileDialog

from tests.util import APP, window

from kanzonascad import dialogs, fileio


class PdfColorChoiceTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.path = os.path.join(tempfile.mkdtemp(), "x.pdf")
        self.win.settings.setValue("pdf_colors", False)
        self.asked, self.monos = [], []

    def tearDown(self):
        self.win.settings.remove("pdf_colors")
        self.win.close()
        self.assertTrue(APP)

    def export(self, pick):
        real = fileio.export_pdf

        def ask(_parent, _title, _start, types, first):
            self.asked.append((types.split(";;"), first))
            return self.path, pick

        def spy(project, p, *a, **kw):
            self.monos.append(kw.get("mono", True))
            return real(project, p, *a, **kw)
        with mock.patch.object(QFileDialog, "getSaveFileName", ask), \
                mock.patch.object(fileio, "export_pdf", spy):
            self.win.export_pdf()

    def test_both_offered_and_the_pick_kept(self):
        bw, color = self.win.PDF_BW, self.win.PDF_COLOR
        self.export(color)
        self.export(color)
        self.export(bw)
        self.export(bw)
        self.assertEqual([types for types, _f in self.asked], [[bw, color]] * 4)
        # (offered first: black and white to start, then the last pick)
        self.assertEqual([first for _t, first in self.asked], [bw, color, color, bw])
        self.assertEqual(self.monos, [False, False, True, True])
        self.assertTrue(os.path.getsize(self.path) > 500)
        self.assertIn("black and white", self.win.statusBar().currentMessage())

    def test_the_options_switch_is_the_same_setting(self):
        self.export(self.win.PDF_COLOR)
        shown = []

        def untick(_parent, cur, _view):
            shown.append(cur["pdf_colors"])
            return dict(cur, pdf_colors=False)
        with mock.patch.object(dialogs, "options_dialog", untick):
            self.assertTrue(self.win.options())
        self.assertEqual(shown, [True], "Options doesn't show the Export to PDF window's pick")
        self.export("")                 # (a dialog that says nothing of the type: as set)
        self.assertEqual(self.asked[-1][1], self.win.PDF_BW)
        self.assertEqual(self.monos[-1], True)


if __name__ == "__main__":
    unittest.main()
