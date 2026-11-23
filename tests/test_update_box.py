"""The update notice and the update box look and work as KanzonasPDF's (the owner: "Make the
update notice and update box look and work exactly like KanzonasPDF's"), for every way
KanzonasCAD can be installed: the setup (for this user or all users), the portable zip, the
PortableApps.com package, the Windows zip, the Linux AppImage, the Linux folder and source.
Each is made believable to updates.how() from what it looks at (the folder, portable.txt,
$APPIMAGE...), not by replacing how() itself."""
import contextlib
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

from PySide6.QtCore import QUrl
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPushButton, QTextBrowser

from tests.util import APP, window

from kanzonascad import __version__, paths, updates

SHA = "b" * 64
NEW = "99.0"


def rel(tag, notes=None, assets=()):
    body = "" if notes is None else ("<!-- kanzonascad-notes -->\n%s\n"
                                     "<!-- /kanzonascad-notes -->" % notes)
    return {"tag_name": tag, "draft": False, "body": body,
            "html_url": "https://github.com/keithlyding/KanzonasCAD/releases/tag/" + tag,
            "assets": list(assets)}


def releases():
    """Two versions newer than this one: 99.0 with notes, 98.5 without."""
    return [rel("v" + NEW, "**New**\n- Wire colors"), rel("v98.5"), rel("v" + __version__)]


@contextlib.contextmanager
def installed_as(mode, all_users=False):
    """Make this copy look installed the way mode says, to updates.how() and the window."""
    folder = tempfile.mkdtemp()
    with contextlib.ExitStack() as st:
        p = st.enter_context
        if mode == "source":
            yield folder
            return
        p(mock.patch.object(updates, "source_folder", return_value=None))
        if mode == "appimage":
            f = os.path.join(folder, "My KanzonasCAD.AppImage")
            open(f, "wb").close()
            p(mock.patch.dict(os.environ, {"APPIMAGE": f}))
            p(mock.patch.object(sys, "platform", "linux"))
            yield folder
            return
        p(mock.patch.object(updates, "running_appimage", return_value=None))
        if mode == "linux folder":
            p(mock.patch.object(updates, "app_folder", return_value=None))
            yield folder
            return
        p(mock.patch.object(updates, "app_folder", return_value=folder))
        p(mock.patch.object(paths, "is_portable",
                            return_value=mode in ("portable", "portableapps")))
        p(mock.patch.object(paths, "platform_updates", return_value=mode == "portableapps"))
        if mode == "setup":
            open(os.path.join(folder, "unins000.exe"), "wb").close()
            p(mock.patch.object(updates, "for_all_users", return_value=all_users))
        yield folder


HOW = {"setup": "installer", "portable": "portable", "portableapps": "tell",
       "windows zip": "windows", "appimage": "appimage", "linux folder": "tell",
       "source": "source"}

TEXTS = {
    "setup": "Update now downloads the new setup, checks it, closes KanzonasCAD (after asking "
             "to save your work) and installs the new version over this one; KanzonasCAD "
             "starts again when it's done. Your projects, library and settings are kept.",
    "portable": "Update now downloads it, closes KanzonasCAD, replaces the program files in "
                "this folder (your data folder is kept) and starts it again.",
    "windows zip": "Update now downloads it, closes KanzonasCAD, replaces the program files in "
                   "this folder and starts it again. Your projects and library are kept.",
    "appimage": "Update now downloads the new AppImage, checks it, closes KanzonasCAD (after "
                "asking to save your work), puts it in place of My KanzonasCAD.AppImage and "
                "starts it again. Your projects, library and settings are kept.",
    "source": "Update now gets the new version (git pull) and what it needs, closes "
              "KanzonasCAD (after asking to save your work) and starts it again. Your "
              "projects, library and settings are kept.",
    "portableapps": None, "linux folder": None}

DOWNLOAD_TIP = "Open the release page to download the new version"
DOWNLOAD_TIP_WIN = "Open the release page to download the installer or portable zip"


class Base(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.win.settings.setValue("update_skip", "")
        self.win.settings.remove(updates.PENDING_KEY)

    def tearDown(self):
        self.win._close_update_notice()
        self.win.settings.setValue("update_skip", "")
        self.win.settings.remove(updates.PENDING_KEY)
        self.v.project.saved_at = len(self.v.project.undo_stack)
        self.win.close()

    def found(self, manual, data=None):
        """What the checker does with GitHub's answer; returns the update boxes opened."""
        boxes = []

        def exec_(dlg):
            dlg.show()
            APP.processEvents()
            boxes.append(self.describe_box(dlg))
            return QDialog.Rejected
        with mock.patch.object(QDialog, "exec", exec_):
            self.win._checker().handle(releases() if data is None else data, manual)
        return boxes

    @staticmethod
    def describe_box(dlg):
        labels = [w.text() for w in dlg.findChildren(QLabel)]
        bb = dlg.findChild(QDialogButtonBox)
        buttons = sorted((b for b in bb.buttons() if b.isVisible()),
                         key=lambda b: b.mapTo(dlg, b.rect().topLeft()).x())
        return {"title": dlg.windowTitle(), "size": (dlg.width(), dlg.height()),
                "labels": labels, "notes": dlg.findChild(QTextBrowser).toMarkdown(),
                "buttons": [b.text() for b in buttons]}

    def notice(self):
        bar = getattr(self.win, "_update_bar", None)
        if bar is None:
            return None
        text = bar.findChild(QLabel)
        return {"text": text.text(),
                "buttons": [b.text() for b in bar.findChildren(QPushButton)],
                "tips": {b.text(): b.toolTip() for b in bar.findChildren(QPushButton)},
                "shown": bar.isVisible(),
                "cut off": text.width() < text.sizeHint().width()}

    def click(self, text):
        for b in self.win._update_bar.findChildren(QPushButton):
            if b.text() == text:
                b.click()
                return
        self.fail("no %s button in the notice" % text)


class NoticeTest(Base):
    def test_notice_for_every_way_it_is_installed(self):
        for mode in HOW:
            with self.subTest(mode=mode), installed_as(mode):
                self.assertEqual(updates.how(), HOW[mode])
                self.win.statusBar().showMessage("Saved something", 60000)
                self.assertEqual(self.found(manual=False), [], "the automatic check opened "
                                 "a window")
                n = self.notice()
                self.assertTrue(n["shown"])
                self.assertEqual(self.win.statusBar().currentMessage(), "")
                self.assertEqual(n["text"], "<b>KanzonasCAD %s is available</b> (you have %s)."
                                 % (NEW, __version__))
                can = TEXTS[mode] is not None
                self.assertEqual(n["buttons"], ["What's new"] + (["Update now"] if can else [])
                                 + ["Download", "Skip this version", "Later"])
                self.assertEqual(n["tips"]["What's new"], "What changed since your version")
                self.assertEqual(n["tips"]["Download"], DOWNLOAD_TIP)
                if can:
                    self.assertEqual(n["tips"]["Update now"], TEXTS[mode])
                APP.processEvents()
                self.assertFalse(self.notice()["cut off"], "the notice's text is cut off")
                self.win._close_update_notice()
                self.assertEqual(self.win.coords.minimumWidth(), 300)
                self.assertTrue(self.win.coords.isVisibleTo(self.win))

    def test_download_tip_on_windows(self):
        with installed_as("setup"), mock.patch.object(sys, "platform", "win32"):
            self.found(manual=False)
            self.assertEqual(self.notice()["tips"]["Download"], DOWNLOAD_TIP_WIN)

    def test_one_notice_at_a_time(self):
        self.found(manual=False)
        first = self.win._update_bar
        self.found(manual=False)
        self.assertIsNot(self.win._update_bar, first)
        APP.processEvents()
        self.assertEqual(len([w for w in self.win.statusBar().findChildren(QPushButton)
                              if w.text() == "What's new" and w.isVisible()]), 1)

    def test_later_skip_download_and_update_now(self):
        self.found(manual=False)
        self.click("Later")
        self.assertIsNone(self.notice())
        self.assertEqual(self.win.settings.value("update_skip", ""), "")

        self.found(manual=False)
        self.click("Skip this version")
        self.assertIsNone(self.notice())
        self.assertEqual(self.win.settings.value("update_skip"), NEW)
        self.assertEqual(self.found(manual=False), [])
        self.assertIsNone(self.notice(), "a skipped version was told again")
        self.win.settings.setValue("update_skip", "")

        self.found(manual=False)
        with mock.patch("PySide6.QtGui.QDesktopServices.openUrl") as opened:
            self.click("Download")
        opened.assert_called_once_with(QUrl(rel("v" + NEW)["html_url"]))
        self.assertIsNone(self.notice())

        self.found(manual=False)
        with mock.patch.object(self.win, "update_now") as upd:
            self.click("Update now")
        self.assertEqual(upd.call_args[0][0]["tag_name"], "v" + NEW)
        self.assertIsNone(self.notice())

    def test_whats_new_opens_the_box(self):
        self.found(manual=False)
        boxes = []
        with mock.patch.object(QDialog, "exec",
                               lambda dlg: boxes.append(self.describe_box(dlg)) or 0):
            self.click("What's new")
        self.assertEqual(len(boxes), 1)
        self.assertEqual(boxes[0]["title"], "Check for updates")
        self.assertIsNotNone(self.notice(), "Later in the box closed the notice")


class BoxTest(Base):
    def test_box_for_every_way_it_is_installed(self):
        for mode in HOW:
            with self.subTest(mode=mode), installed_as(mode):
                boxes = self.found(manual=True)
                self.assertEqual(len(boxes), 1)
                b = boxes[0]
                self.assertIsNone(self.notice(), "asked for: a box, not the notice")
                self.assertEqual(b["title"], "Check for updates")
                self.assertEqual(b["size"], (600, 520))
                self.assertEqual(b["labels"][0], "KanzonasCAD %s is available (you have %s)."
                                 % (NEW, __version__))
                self.assertEqual(b["labels"][1], "<b>What's new since your version</b>")
                how = "Download opens the release page in your browser."
                if TEXTS[mode]:
                    how = TEXTS[mode] + "\n\n" + how
                self.assertEqual(b["labels"][2], how)
                self.assertEqual(b["buttons"], (["Update now"] if TEXTS[mode] else [])
                                 + ["Download", "Later"])

    def test_notes_since_this_version(self):
        notes = self.found(manual=True)[0]["notes"]
        self.assertIn("### Version 99.0", notes)
        self.assertIn("Wire colors", notes)
        self.assertIn("### Version 98.5", notes)
        self.assertIn("[What's new in 98.5](https://github.com/keithlyding/KanzonasCAD/"
                      "releases/tag/v98.5)", notes)
        self.assertLess(notes.index("99.0"), notes.index("98.5"))
        self.assertNotIn("Version " + __version__, notes)

    def test_all_users_needs_administrator_rights(self):
        with installed_as("setup", all_users=True):
            self.assertEqual(self.win._update_now_text(), TEXTS["setup"] + " Installed for "
                             "all users: Windows asks for administrator rights.")

    def choose(self, text):
        """Open the box (asked for) and click text in it."""
        def exec_(dlg):
            for b in dlg.findChild(QDialogButtonBox).buttons():
                if b.text() == text:
                    b.click()
            return QDialog.Accepted
        self.found(manual=False)                    # (a notice there already)
        with mock.patch.object(QDialog, "exec", exec_), \
                mock.patch.object(self.win, "update_now") as upd, \
                mock.patch("PySide6.QtGui.QDesktopServices.openUrl") as opened:
            self.win._checker().handle(releases(), True)
        return upd, opened

    def test_box_buttons(self):
        upd, opened = self.choose("Update now")
        self.assertEqual(upd.call_count, 1)
        self.assertEqual(opened.call_count, 0)
        self.assertIsNone(self.notice(), "Update now in the box left the notice")
        upd, opened = self.choose("Download")
        self.assertEqual(upd.call_count, 0)
        opened.assert_called_once_with(QUrl(rel("v" + NEW)["html_url"]))
        self.assertIsNone(self.notice(), "Download in the box left the notice")
        upd, opened = self.choose("Later")
        self.assertEqual((upd.call_count, opened.call_count), (0, 0))
        self.assertIsNotNone(self.notice(), "Later closed the notice")


class AnswerTest(Base):
    def test_up_to_date(self):
        with mock.patch("kanzonascad.main_window.QMessageBox.information") as info:
            self.win._checker().handle([rel("v" + __version__)], True)
        info.assert_called_once_with(self.win, "Check for updates",
                                     "You have the latest version (%s)." % __version__)

    def test_could_not_check(self):
        class Reply:
            def deleteLater(self):
                pass    # (nothing to delete)

            def error(self):
                return QNetworkReply.HostNotFoundError

            def errorString(self):
                return "Host api.github.com not found"
        with mock.patch("kanzonascad.main_window.QMessageBox.information") as info:
            self.win._checker()._done(Reply(), True)
            self.win._checker()._done(Reply(), False)       # (the automatic check: quiet)
        info.assert_called_once_with(self.win, "Check for updates", "Couldn't reach GitHub to "
                                     "check for updates (Host api.github.com not found).")


class OutcomeTest(Base):
    """After Update now ran a setup: the next start says if the update didn't take."""

    def record(self, version, setup):
        updates.remember_update(self.win.settings, version, setup)
        self.assertEqual(json.loads(self.win.settings.value(updates.PENDING_KEY))["version"],
                         version)

    def test_update_outcome(self):
        folder = tempfile.mkdtemp(prefix="kzcadsetup")
        setup = os.path.join(folder, "KanzonasCAD-v0.1-setup.exe")
        open(setup, "wb").close()
        self.record("0.1", setup)
        out = updates.update_outcome(self.win.settings)
        self.assertEqual(out, {"ok": True, "version": "0.1", "setup": setup})
        self.assertFalse(os.path.exists(folder), "the setup used wasn't removed")
        self.assertIsNone(updates.update_outcome(self.win.settings), "told twice")
        self.win.settings.setValue(updates.PENDING_KEY, "not json")
        self.assertIsNone(updates.update_outcome(self.win.settings))

    def boxes(self):
        shown = []

        def exec_(box):
            shown.append((box.windowTitle(), box.text(), box.informativeText(),
                          [b.text() for b in box.buttons()]))
            return 0
        with mock.patch("kanzonascad.main_window.QMessageBox.exec", exec_), \
                mock.patch.object(self.win._checker(), "check_if_due"):
            self.win.start_update_check()
        return shown

    def test_the_update_did_not_finish(self):
        folder = tempfile.mkdtemp(prefix="kzcadsetup")
        setup = os.path.join(folder, "KanzonasCAD-v%s-setup.exe" % NEW)
        open(setup, "wb").close()
        self.record(NEW, setup)
        shown = self.boxes()
        self.assertEqual(len(shown), 1)
        title, text, more, buttons = shown[0]
        self.assertEqual(title, "Update")
        self.assertEqual(text, "The update to KanzonasCAD %s didn't finish: this is still %s. "
                         "Windows may have kept one of its files in use." % (NEW, __version__))
        self.assertEqual(more, "Run the setup now to finish it: it shows what's in the way "
                               "and can close it.")
        self.assertIn("Run the setup", buttons)
        self.assertTrue(os.path.exists(setup), "the setup to run again was removed")
        self.assertEqual(self.boxes(), [], "told twice")
        os.remove(setup)
        self.record(NEW, setup)
        self.assertEqual(self.boxes()[0][2], "Download the setup from the release page and "
                                             "run it.")

    def test_quiet_when_it_took(self):
        self.record(__version__, "")
        self.assertEqual(self.boxes(), [])
        self.assertEqual(self.boxes(), [])          # (and nothing recorded)


if __name__ == "__main__":
    unittest.main()
