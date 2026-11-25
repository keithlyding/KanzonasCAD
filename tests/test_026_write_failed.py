"""A file that can't be written is said, never passed over (the owner, 0.26: Export to PDF over
a PDF open in Adobe failed without a word). On Windows a program showing a file keeps it locked:
writing over it, or putting another file in its place, raises PermissionError; that is what is
put in here (os.replace refused), with a folder in the file's place for a file that can't be
opened at all (Qt's PDF writer then draws into nothing and says so only on the console)."""
import os
import tempfile
import unittest
from unittest import mock

from PySide6.QtWidgets import QFileDialog, QMessageBox

from tests.util import APP, window

from kanzonascad import dialogs, fileio
from kanzonascad import model as M
from kanzonascad.print_dialog import PrintDialog


def locked(*_a, **_k):
    raise PermissionError(13, "Access is denied")


OLD = b"%PDF-1.4 the old file\n"


class WriteFailedTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "Plant.pdf")
        with open(self.path, "wb") as f:
            f.write(OLD)

    def kept(self):
        with open(self.path, "rb") as f:
            self.assertEqual(f.read(), OLD, "the file that was there changed")
        self.assertEqual(sorted(os.listdir(self.dir)), ["Plant.pdf"], "a part-written file left")

    def test_export_pdf_over_a_file_in_use(self):
        with mock.patch("os.replace", locked):
            with self.assertRaises(PermissionError):
                fileio.export_pdf(M.Project.new(), self.path)
        self.kept()

    def test_export_pdf_where_no_file_can_be_opened(self):
        folder = os.path.join(self.dir, "a folder.pdf")
        os.mkdir(folder)
        with self.assertRaises(OSError):
            # (links=False: nothing else reads the file afterwards to find it isn't there)
            fileio.export_pdf(M.Project.new(), folder, links=False)
        self.assertTrue(os.path.isdir(folder))

    def test_export_pdf_writes_when_it_can(self):
        self.assertEqual(fileio.export_pdf(M.Project.new(), self.path), 1)
        with open(self.path, "rb") as f:
            got = f.read()
        self.assertTrue(got.startswith(b"%PDF") and got != OLD and len(got) > 500)
        self.assertEqual(os.listdir(self.dir), ["Plant.pdf"])

    def test_pull_list_pdf_over_a_file_in_use(self):
        with mock.patch("os.replace", locked):
            with self.assertRaises(PermissionError):
                dialogs.write_pull_pdf(M.Project.new(), self.path)
        self.kept()

    def test_the_message_says_what_to_do(self):
        text = dialogs.write_failed_text(self.path, PermissionError(13, "Access is denied"))
        self.assertIn(self.path, text)
        self.assertIn("open in another program", text)
        self.assertIn("choose another name", text)
        other = dialogs.write_failed_text(self.path, OSError(28, "No space left on device"))
        self.assertIn("No space left on device", other)
        self.assertNotIn("another program", other)


class WindowSaysTest(unittest.TestCase):
    """Each way out of the window: the failure in a message box."""

    def setUp(self):
        self.win, self.v = window()
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        self.v.project.saved_at = len(self.v.project.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def told(self, run, path):
        with mock.patch.object(QFileDialog, "getSaveFileName", return_value=(path, "")), \
                mock.patch.object(QFileDialog, "getExistingDirectory", return_value=self.dir), \
                mock.patch.object(QMessageBox, "warning") as warning, \
                mock.patch("os.replace", locked):
            run()
        self.assertEqual(warning.call_count, 1, "no message (or more than one)")
        text = warning.call_args[0][2]
        self.assertIn("open in another program", text)
        return text

    def test_export_pdf(self):
        path = os.path.join(self.dir, "x.pdf")
        self.assertIn(path, self.told(self.win.export_pdf, path))
        self.assertNotIn("Exported", self.win.statusBar().currentMessage())

    def test_export_dxf(self):
        import ezdxf.document
        path = os.path.join(self.dir, "x.dxf")
        with mock.patch.object(ezdxf.document.Drawing, "saveas", locked):
            text = self.told(self.win.export_dxf, path)
        self.assertIn(path, text)
        self.assertNotIn("Exported", self.win.statusBar().currentMessage())

    def test_export_all_sheets_to_dxf_stops_and_says(self):
        import ezdxf.document
        self.win.add_sheet()
        with mock.patch.object(ezdxf.document.Drawing, "saveas", locked):
            self.told(self.win.export_dxf_all, "")
        self.assertIn("Exported 0 of 2", self.win.statusBar().currentMessage())

    def test_print_into_a_pdf_file(self):
        d = PrintDialog(self.win, self.v.project, self.v.sheet(), [], display=(0, 0, 8, 6))
        d.printer_box.setCurrentIndex(d.printer_box.count() - 1)
        self.assertTrue(d.to_pdf())
        path = os.path.join(self.dir, "printed.pdf")
        got = []
        self.told(lambda: got.append(d.run(self.dir)), path)
        self.assertEqual(got, [None])
        d.deleteLater()

    def test_a_report_saved_as_csv(self):
        # (Devices without a footprint's Save as CSV or Excel...: a CSV open in Excel)
        dlg = dialogs.MissingFootprintsDialog(self.win)
        dlg.project, dlg.folder = self.v.project, self.dir
        path = os.path.join(self.dir, "report.csv")
        with mock.patch.object(QFileDialog, "getSaveFileName", return_value=(path, "")), \
                mock.patch.object(QMessageBox, "warning") as warning, \
                mock.patch("builtins.open", locked):
            dlg._save()
        self.assertEqual(warning.call_count, 1)
        self.assertIn("open in another program", warning.call_args[0][2])
        dlg.deleteLater()

if __name__ == "__main__":
    unittest.main()
