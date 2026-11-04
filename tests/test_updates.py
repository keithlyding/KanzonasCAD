import os
import tempfile
import unittest
import zipfile

from tests.util import APP, window

from kanzonascad import updates
from kanzonascad import __version__

SHA = "a" * 64


def rel(tag, body="", assets=(), draft=False):
    return {"tag_name": tag, "draft": draft, "body": body,
            "html_url": "https://github.com/keithlyding/KanzonasCAD/releases/tag/" + tag,
            "assets": list(assets)}


class VersionsTest(unittest.TestCase):
    def test_newest_and_notes_since(self):
        data = [rel("v0.3.1"), rel("v0.4", "<!-- kanzonascad-notes -->\n**New**\n- Tags\n"
                                         "<!-- /kanzonascad-notes -->\n---\nmore"),
                rel("v0.3.3", "no marks"), rel("v9.9", draft=True), "junk", rel("vX")]
        r = updates.newest_release(data, "0.3.2")
        self.assertEqual(r["tag_name"], "v0.4")
        since = updates.notes_since(data, "0.3.2")
        self.assertEqual([v for v, _n, _p in since], ["0.4", "0.3.3"])
        self.assertEqual(since[0][1], "**New**\n- Tags")
        self.assertIsNone(since[1][1])
        self.assertIsNone(updates.newest_release(data, "0.4.0"))     # 0.4.0 is 0.4
        self.assertEqual(updates.version_tuple("v0.3.10"), (0, 3, 10))

    def test_assets_only_from_github_with_a_digest(self):
        name = updates.windows_asset_name("0.4")
        good = {"name": name, "digest": "sha256:" + SHA,
                "browser_download_url": "https://github.com/keithlyding/KanzonasCAD/"
                                        "releases/download/v0.4/" + name}
        self.assertEqual(updates.asset(rel("v0.4", assets=[good]), name),
                         (good["browser_download_url"], SHA))
        for bad in (dict(good, digest=""), dict(good, browser_download_url="http://github.com/x"),
                    dict(good, browser_download_url="https://evil.example.com/x.zip")):
            self.assertIsNone(updates.asset(rel("v0.4", assets=[bad]), name))

    def test_this_copy_runs_from_source(self):
        self.assertEqual(updates.how(), "source")       # the tests run from the git clone
        steps = updates.source_steps(updates.source_folder())
        self.assertEqual([a[-2:] for _p, a in steps[:2]], [["checkout", "main"],
                                                          ["pull", "--ff-only"]])
        self.assertIn("constraints.txt", steps[2][1][-3])


class ZipTest(unittest.TestCase):
    def test_unpack_and_refuse_bad_zips(self):
        app = tempfile.mkdtemp()
        good = os.path.join(app, "good.zip")
        with zipfile.ZipFile(good, "w") as z:
            z.writestr("KanzonasCAD/KanzonasCAD.exe", b"exe")
            z.writestr("KanzonasCAD/_internal/x.dll", b"dll")
        new = updates.unpack(good, app)
        self.assertTrue(os.path.isfile(os.path.join(new, "KanzonasCAD.exe")))
        evil = os.path.join(app, "evil.zip")
        with zipfile.ZipFile(evil, "w") as z:
            z.writestr("../../escape.txt", b"x")
        with self.assertRaises(ValueError):
            updates.unpack(evil, app)
        other = os.path.join(app, "other.zip")
        with zipfile.ZipFile(other, "w") as z:
            z.writestr("Something/else.exe", b"x")
        with self.assertRaises(ValueError):
            updates.unpack(other, app)

    def test_swap_script(self):
        s = updates.swap_script(1234, r"C:\K\_update\KanzonasCAD", r"C:\K")
        self.assertIn('PID eq 1234', s)
        self.assertIn('start "" "%s"' % os.path.join(r"C:\K", "KanzonasCAD.exe"), s)
        self.assertIn("robocopy", s)


class CheckerTest(unittest.TestCase):
    def test_found_skip_and_latest(self):
        w, v = window()
        try:
            c = w._checker()
            got = []
            c.found.disconnect()
            c.result.disconnect()
            c.found.connect(lambda r, s: got.append(("found", r["tag_name"])))
            c.result.connect(lambda t: got.append(("result", t)))
            c.handle([rel("v99.0")], manual=False)
            self.assertEqual(got, [("found", "v99.0")])
            w.settings.setValue("update_skip", "99.0")
            c.handle([rel("v99.0")], manual=False)          # skipped: not told again
            self.assertEqual(len(got), 1)
            c.handle([rel("v99.0")], manual=True)           # asked for: told anyway
            self.assertEqual(len(got), 2)
            c.handle([rel("v" + __version__)], manual=True)
            self.assertEqual(got[-1], ("result", "You have the latest version (%s)."
                                       % __version__))
            c.handle({"message": "rate limited"}, manual=False)   # quiet when automatic
            self.assertEqual(len(got), 3)
            self.assertIn("Check for updates automatically", [
                a.text().replace("&", "") for a in w.acts.values()])
        finally:
            w.settings.setValue("update_skip", "")
            v.project.saved_at = len(v.project.undo_stack)
            w.close()


class InstallerTest(unittest.TestCase):
    """A copy installed with the setup updates by running the next setup."""

    def test_installed_copy_and_its_command(self):
        app = tempfile.mkdtemp()
        self.assertFalse(updates.installed(app))
        self.assertFalse(updates.installed(None))
        open(os.path.join(app, "unins000.exe"), "wb").close()
        self.assertTrue(updates.installed(app))
        cmd = updates.installer_command(r"C:\T\KanzonasCAD-v0.5-setup.exe")
        self.assertEqual(cmd[0], r"C:\T\KanzonasCAD-v0.5-setup.exe")
        # (the same switches the Windows build tests the setup with)
        for flag in ("/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/CLOSEAPPLICATIONS",
                     "/CURRENTUSER", "/RELAUNCH"):
            self.assertIn(flag, cmd)
        self.assertEqual(updates.setup_asset_name("0.5"), "KanzonasCAD-v0.5-setup.exe")

    def _download(self, data, sha):
        from PySide6.QtCore import QEventLoop, QObject, QTimer, QUrl
        src = os.path.join(tempfile.mkdtemp(), "KanzonasCAD-v0.5-setup.exe")
        with open(src, "wb") as f:
            f.write(data)
        owner = QObject()
        self.addCleanup(self._dispose, owner)
        up = updates.ZipUpdater(QUrl.fromLocalFile(src).toString(), sha, None, owner, setup=True)
        got = []
        loop = QEventLoop()
        up.ready.connect(lambda p: (got.append(("ready", p)), loop.quit()))
        up.failed.connect(lambda t: (got.append(("failed", t)), loop.quit()))
        QTimer.singleShot(10000, loop.quit)
        up.start()
        if not got:
            loop.exec()
        return up, got

    @staticmethod
    def _dispose(owner):
        # (Qt deletes the download's objects, in order, before Python forgets them)
        from PySide6.QtCore import QCoreApplication, QEvent
        owner.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def test_setup_downloaded_and_checked(self):
        import hashlib
        data = b"MZ pretend setup" * 1000
        up, got = self._download(data, hashlib.sha256(data).hexdigest())
        self.assertEqual(got[0][0], "ready", got)
        path = got[0][1]
        self.assertEqual(os.path.basename(path), "KanzonasCAD-v0.5-setup.exe")
        with open(path, "rb") as f:
            self.assertEqual(f.read(), data)
        # a wrong download is not kept, nor its folder
        up, got = self._download(data, "b" * 64)
        self.assertEqual(got[0][0], "failed")
        self.assertIn("sha256", got[0][1])
        self.assertFalse(os.path.exists(up.path))
        self.assertFalse(os.path.exists(os.path.dirname(up.path)))
