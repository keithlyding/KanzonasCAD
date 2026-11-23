"""While Update now downloads, a window shows it as KanzonasPDF's does (the owner: "Make the
update notice and update box look and work exactly like KanzonasPDF's"): titled Update,
"Downloading the new KanzonasCAD...", a progress bar that follows the download, and Cancel,
which stops it. A failure closes it and says why in a warning titled Update, with where else
to get the new version. Once the download is checked, KanzonasCAD closes (asking to save)
and the update runs, for the setup, the portable zip, the Windows zip, the AppImage and a
copy run from source."""
import os
import unittest
from unittest import mock

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QProgressDialog, QPushButton

from tests.test_update_box import NEW, SHA, installed_as, rel
from tests.util import APP, window

from kanzonascad import updates


class FakeDownload(QObject):
    progress = Signal(int, int)
    ready = Signal(str)
    failed = Signal(str)
    made = []

    def __init__(self, *a, **k):
        super().__init__()
        self.args, self.kwargs = a, k
        self.cancelled = False
        self.started = False
        FakeDownload.made.append(self)

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True


class FakeSource(QObject):
    line = Signal(str)
    finished = Signal(bool, str)
    made = []

    def __init__(self, *a, **k):
        super().__init__()
        FakeSource.made.append(self)

    def start(self):
        pass    # (the test says when it finishes)


def asset(name):
    return {"name": name, "digest": "sha256:" + SHA,
            "browser_download_url": "https://github.com/keithlyding/KanzonasCAD/releases/"
                                    "download/v%s/%s" % (NEW, name)}


RELEASE = rel("v" + NEW, "notes", [asset(updates.setup_asset_name(NEW)),
                                   asset(updates.portable_asset_name(NEW)),
                                   asset(updates.windows_asset_name(NEW)),
                                   asset(updates.APPIMAGE)])


class UpdateProgressTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        FakeDownload.made = []
        FakeSource.made = []
        self.win.settings.remove(updates.PENDING_KEY)

    def tearDown(self):
        self.win._update_download = None
        self.win.settings.remove(updates.PENDING_KEY)
        self.v.project.saved_at = len(self.v.project.undo_stack)
        self.win.close()

    def progress_window(self):
        found = [w for w in self.win.findChildren(QProgressDialog, "update_progress")
                 if w.isVisible()]
        return found[-1] if found else None

    def start(self, mode):
        """Update now, installed the way mode says; returns (the download, its window)."""
        with installed_as(mode), \
                mock.patch.object(updates, "ZipUpdater", FakeDownload), \
                mock.patch.object(updates, "AppImageUpdater", FakeDownload):
            self.win.update_now(RELEASE)
        APP.processEvents()
        return FakeDownload.made[-1], self.progress_window()

    def test_the_window(self):
        for mode in ("setup", "portable", "windows zip", "appimage"):
            with self.subTest(mode=mode):
                up, prog = self.start(mode)
                self.assertTrue(up.started)
                self.assertIsNotNone(prog, "no progress window")
                self.assertEqual(prog.windowTitle(), "Update")
                self.assertEqual(prog.labelText(), "Downloading the new KanzonasCAD...")
                self.assertEqual([b.text() for b in prog.findChildren(QPushButton)],
                                 ["Cancel"])
                up.progress.emit(30_000_000, 75_000_000)
                self.assertEqual((prog.value(), prog.maximum()), (30_000_000, 75_000_000))
                with mock.patch("kanzonascad.main_window.QMessageBox.information") as info:
                    self.win.update_now(RELEASE)
                info.assert_called_once_with(self.win, "Update",
                                             "The new version is already downloading.")
                prog.findChildren(QPushButton)[0].click()
                self.assertTrue(up.cancelled)
                self.assertIsNone(self.progress_window())
                self.assertIsNone(self.win._update_download)

    def test_the_right_file(self):
        for mode, name in (("setup", updates.setup_asset_name(NEW)),
                           ("portable", updates.portable_asset_name(NEW)),
                           ("windows zip", updates.windows_asset_name(NEW)),
                           ("appimage", updates.APPIMAGE)):
            with self.subTest(mode=mode):
                up, prog = self.start(mode)
                self.assertTrue(up.args[0].endswith("/" + name))
                self.assertEqual(up.args[1], SHA)
                self.assertEqual(up.kwargs.get("setup", False), mode == "setup")
                prog.findChildren(QPushButton)[0].click()

    def test_a_failure_says_so(self):
        tails = {"setup": "You can still download the setup from the release page and run it.",
                 "portable": "You can still download %s from the release page and unzip it "
                             "over this folder." % updates.portable_asset_name(NEW),
                 "windows zip": "You can still download %s from the release page and unzip "
                                "it over this folder." % updates.windows_asset_name(NEW),
                 "appimage": "You can still download KanzonasCAD-x86_64.AppImage from the "
                             "release page and put it in place of this one."}
        for mode, tail in tails.items():
            with self.subTest(mode=mode):
                up, _prog = self.start(mode)
                with mock.patch("kanzonascad.main_window.QMessageBox.warning") as warn:
                    up.failed.emit("The download was not used: its sha256 doesn't match the "
                                   "release.")
                warn.assert_called_once_with(
                    self.win, "Update", "The download was not used: its sha256 doesn't match "
                    "the release.\n\n" + tail)
                self.assertIsNone(self.progress_window())
                self.assertIsNone(self.win._update_download)

    def test_setup_runs_once_closed_and_is_remembered(self):
        up, _prog = self.start("setup")
        with mock.patch.object(self.win, "_close_for_update", return_value=False), \
                mock.patch.object(updates, "start_setup") as run:
            up.ready.emit("/tmp/kzcadsetupX/setup.exe")       # a project kept open: not now
        run.assert_not_called()
        self.assertIsNone(self.win.settings.value(updates.PENDING_KEY))
        self.assertIsNone(self.progress_window())
        up, _prog = self.start("setup")
        with mock.patch.object(self.win, "_close_for_update", return_value=True), \
                mock.patch.object(updates, "start_setup") as run, \
                mock.patch.object(APP, "quit") as quit_:
            up.ready.emit("/tmp/kzcadsetupX/setup.exe")
        run.assert_called_once_with("/tmp/kzcadsetupX/setup.exe", mock.ANY)
        quit_.assert_called_once()
        self.assertEqual(updates.update_outcome(self.win.settings)["version"], NEW)

    def test_zip_swaps_once_closed(self):
        for mode in ("portable", "windows zip"):
            with self.subTest(mode=mode):
                up, _prog = self.start(mode)
                with mock.patch.object(self.win, "_close_for_update", return_value=True), \
                        mock.patch.object(updates, "start_swap") as swap, \
                        mock.patch.object(APP, "quit"):
                    up.ready.emit("/new")
                self.assertEqual(swap.call_args[0][0], "/new")
                self.assertIsNone(self.win.settings.value(updates.PENDING_KEY))

    def test_appimage_kept_open_starts_next_time(self):
        with installed_as("appimage") as folder:
            target = os.path.realpath(os.environ["APPIMAGE"])
            with mock.patch.object(updates, "ZipUpdater", FakeDownload), \
                    mock.patch.object(updates, "AppImageUpdater", FakeDownload):
                self.win.update_now(RELEASE)
            up = FakeDownload.made[-1]
            self.assertEqual(up.args[2], target)
            new = os.path.join(folder, "new.AppImage")
            with open(new, "wb") as f:
                f.write(b"new")
            with mock.patch.object(self.win, "_close_for_update", return_value=False), \
                    mock.patch("kanzonascad.main_window.QMessageBox.information") as info:
                up.ready.emit(new)
            info.assert_called_once_with(self.win, "Update", "The new version is in place. It "
                                         "starts the next time you open KanzonasCAD.")
            self.assertFalse(os.path.exists(new))
            with open(target, "rb") as f:
                self.assertEqual(f.read(), b"new")

    def test_source(self):
        with mock.patch.object(updates, "SourceUpdater", FakeSource):
            with installed_as("source"):
                self.win.update_now(RELEASE)
            APP.processEvents()
            prog = self.progress_window()
            self.assertEqual(prog.windowTitle(), "Update")
            self.assertEqual(prog.labelText(), "Downloading the new KanzonasCAD...")
            self.assertEqual(prog.findChildren(QPushButton), [])    # (git can't be stopped)
            up = FakeSource.made[-1]
            up.line.emit("> git pull --ff-only")
            up.line.emit("fatal: not possible to fast-forward")
            shown = []
            with mock.patch("kanzonascad.main_window.QMessageBox.exec",
                            lambda box: shown.append((box.windowTitle(), box.text(),
                                                      box.detailedText()))):
                up.finished.emit(False, "git stopped with an error (code 128).")
            self.assertEqual(shown, [("Update", "git stopped with an error (code 128).",
                                      "> git pull --ff-only\nfatal: not possible to "
                                      "fast-forward")])
            self.assertIsNone(self.progress_window())
            with installed_as("source"):
                self.win.update_now(RELEASE)
            with mock.patch.object(self.win, "_close_for_update", return_value=True), \
                    mock.patch.object(self.win, "_restart") as restart:
                FakeSource.made[-1].finished.emit(True, "Updated.")
            restart.assert_called_once()


class NoUpdateNowTest(unittest.TestCase):
    """The PortableApps.com package and the Linux folder can't update themselves: Update now
    (if called) opens the release page; a release without a checked file says so first."""

    def test_release_page(self):
        w, v = window()
        try:
            for mode in ("portableapps", "linux folder"):
                with self.subTest(mode=mode), installed_as(mode), \
                        mock.patch("PySide6.QtGui.QDesktopServices.openUrl") as opened, \
                        mock.patch("kanzonascad.main_window.QMessageBox.warning") as warn:
                    w.update_now(RELEASE)
                self.assertEqual(opened.call_count, 1)
                warn.assert_not_called()
            with installed_as("setup"), \
                    mock.patch("PySide6.QtGui.QDesktopServices.openUrl") as opened, \
                    mock.patch("kanzonascad.main_window.QMessageBox.warning") as warn:
                w.update_now(rel("v" + NEW))
            warn.assert_called_once_with(w, "Update", "This release has no checked setup. "
                                         "Opening the release page instead.")
            self.assertEqual(opened.call_count, 1)
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            w.close()


if __name__ == "__main__":
    unittest.main()
