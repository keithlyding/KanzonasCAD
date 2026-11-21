"""Export to PDF in the layers' colors (the owner's list, #14 "color PDF option"): an Options
setting, off to start (black on white, as before); on, Export to PDF... draws in the layers'
colors (fileio.export_pdf mono=False)."""
import os
import tempfile
import unittest
from unittest import mock

from tests.util import APP, window

from kanzonascad import fileio


class ColorPdfTest(unittest.TestCase):
    def test_setting_reaches_the_export(self):
        win, v = window()
        try:
            path = os.path.join(tempfile.mkdtemp(), "x.pdf")
            got = []
            real = fileio.export_pdf

            def spy(project, p, *a, **kw):
                got.append(kw.get("mono", True))
                return real(project, p, *a, **kw)
            with mock.patch("kanzonascad.main_window.QFileDialog.getSaveFileName",
                            return_value=(path, "")), \
                    mock.patch.object(fileio, "export_pdf", spy):
                win.settings.setValue("pdf_colors", False)
                win.export_pdf()
                win.settings.setValue("pdf_colors", True)
                win.export_pdf()
            self.assertEqual(got, [True, False])
            self.assertTrue(os.path.getsize(path) > 500)
        finally:
            win.settings.remove("pdf_colors")
            win.close()
        self.assertTrue(APP)


if __name__ == "__main__":
    unittest.main()
