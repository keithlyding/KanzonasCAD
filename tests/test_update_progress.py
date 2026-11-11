"""The update window shows the download's progress (the owner: "can it show a progress bar,
like KanzonasPDF does? Right now, it just says downloading"): a bar with how many MB of how
many, Cancel while it downloads (which stops it), Close once it's done or failed."""
import unittest
from unittest import mock

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QProgressBar

from tests.util import APP, window  # noqa: F401


class FakeDownload(QObject):
    progress = Signal(int, int)
    ready = Signal(str)
    failed = Signal(str)
    made = []

    def __init__(self, *a, **k):
        super().__init__(k.get("parent") if "parent" in k else None)
        self.cancelled = False
        FakeDownload.made.append(self)

    def start(self):
        pass

    def cancel(self):
        self.cancelled = True


class UpdateProgressTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        FakeDownload.made = []

    def tearDown(self):
        self.v.project.saved_at = len(self.v.project.undo_stack)
        self.win.close()

    def run_update(self, during):
        seen = {}

        def exec_(dlg):
            up = FakeDownload.made[-1]
            bar = dlg.findChild(QProgressBar, "download_progress")
            box = dlg.findChild(QDialogButtonBox)
            seen["button at start"] = box.button(QDialogButtonBox.Close).text()
            seen["enabled at start"] = box.isEnabled()
            during(up, bar, box, seen)
            return QDialog.Rejected
        with mock.patch("kanzonascad.updates.ZipUpdater", FakeDownload), \
                mock.patch.object(QDialog, "exec", exec_), \
                mock.patch("PySide6.QtWidgets.QMessageBox.question",
                           return_value=0x00010000):                    # (No)
            self.win._run_zip_update("https://example.invalid/x.zip", "0" * 64, "/tmp/nowhere")
        return seen

    def test_bar_follows_the_download(self):
        def during(up, bar, box, seen):
            up.progress.emit(30_000_000, 75_000_000)
            seen["format"] = bar.format()
            seen["value"] = bar.value() / bar.maximum()
            up.ready.emit("/tmp/new")
            seen["done format"] = bar.format()
            seen["done button"] = box.button(QDialogButtonBox.Close).text()
        seen = self.run_update(during)
        self.assertEqual(seen["button at start"], "Cancel")
        self.assertTrue(seen["enabled at start"])
        self.assertEqual(seen["format"], "30.0 of 75.0 MB (40%)")
        self.assertAlmostEqual(seen["value"], 0.4, places=3)
        self.assertEqual(seen["done format"], "Downloaded and checked")
        self.assertEqual(seen["done button"], "Close")

    def test_cancel_stops_it(self):
        def during(up, bar, box, seen):
            up.progress.emit(5_000_000, 75_000_000)
            box.button(QDialogButtonBox.Close).click()
            seen["cancelled"] = up.cancelled
        self.assertTrue(self.run_update(during)["cancelled"])

    def test_a_failure_says_so_and_closes(self):
        def during(up, bar, box, seen):
            up.failed.emit("The download didn't match its checksum.")
            seen["button"] = box.button(QDialogButtonBox.Close).text()
            seen["format"] = bar.format()
        seen = self.run_update(during)
        self.assertEqual(seen["button"], "Close")
        self.assertEqual(seen["format"], "Stopped")


if __name__ == "__main__":
    unittest.main()
