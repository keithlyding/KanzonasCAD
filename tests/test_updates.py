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
        cmd = updates.installer_command(r"C:\T\KanzonasCAD-v0.5-setup.exe", app)
        self.assertEqual(cmd[0], r"C:\T\KanzonasCAD-v0.5-setup.exe")
        # (the same switches the Windows build tests the setup with)
        for flag in ("/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/CLOSEAPPLICATIONS",
                     "/CURRENTUSER", "/RELAUNCH"):
            self.assertIn(flag, cmd)
        # a copy under Program Files with no uninstall entry of the setup's: all users
        pf = os.path.join(tempfile.mkdtemp(), "Program Files")
        old = os.environ.get("ProgramFiles")
        os.environ["ProgramFiles"] = pf
        try:
            from unittest import mock
            with mock.patch.object(updates, "_installed_in", return_value=None):
                self.assertTrue(updates.for_all_users(os.path.join(pf, "KanzonasCAD")))
                self.assertIn("/ALLUSERS", updates.installer_command(
                    "s.exe", os.path.join(pf, "KanzonasCAD")))
                self.assertFalse(updates.for_all_users(app))
            # the setup's own entry decides, wherever the folder is
            with mock.patch.object(updates, "_installed_in",
                                   side_effect=lambda hive, d: hive == "HKLM"):
                if os.name != "nt":
                    import sys
                    fake = mock.MagicMock(HKEY_CURRENT_USER="HKCU", HKEY_LOCAL_MACHINE="HKLM")
                    with mock.patch.dict(sys.modules, {"winreg": fake}):
                        self.assertTrue(updates.for_all_users(app))
        finally:
            if old is None:
                del os.environ["ProgramFiles"]
            else:
                os.environ["ProgramFiles"] = old
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


class PortableUpdateTest(unittest.TestCase):
    """The portable Windows copy updates from the release's portable zip; its data folder
    (settings, library, recovery copies) is never replaced."""

    def test_how_a_portable_copy_updates(self):
        from unittest import mock
        from kanzonascad import paths
        app = tempfile.mkdtemp()
        with mock.patch.object(updates, "source_folder", return_value=None), \
                mock.patch.object(updates, "running_appimage", return_value=None), \
                mock.patch.object(updates, "app_folder", return_value=app), \
                mock.patch.object(paths, "app_dir", return_value=app):
            self.assertEqual(updates.how(), "windows")
            with open(os.path.join(app, "portable.txt"), "w") as f:
                f.write("portable\n")
            self.assertEqual(updates.how(), "portable")
            # (a portable copy with an uninstaller beside it is still portable)
            open(os.path.join(app, "unins000.exe"), "wb").close()
            self.assertEqual(updates.how(), "portable")
            # the PortableApps.com package: its Platform updates it
            with open(os.path.join(app, "portable.txt"), "w") as f:
                f.write("data=..\\..\\Data\nupdates=off\n")
            self.assertEqual(updates.how(), "tell")
        self.assertEqual(updates.portable_asset_name("0.5"), "KanzonasCAD-v0.5-portable.zip")

    def test_update_keeps_the_data_folder(self):
        app = tempfile.mkdtemp()
        z_path = os.path.join(app, "p.zip")
        with zipfile.ZipFile(z_path, "w") as z:
            z.writestr("KanzonasCAD/KanzonasCAD.exe", b"exe")
            z.writestr("KanzonasCAD/portable.txt", b"portable")
            z.writestr("KanzonasCAD/data/settings.ini", b"[General]\ntheirs=1\n")
        new = updates.unpack(z_path, app)
        self.assertTrue(os.path.isfile(os.path.join(new, "portable.txt")))
        self.assertFalse(os.path.exists(os.path.join(new, "data")))
        s = updates.swap_script(1, new, app)
        line = [ln for ln in s.split("\r\n") if "/XD" in ln][0]
        self.assertIn(os.path.join(new, "data"), line)
        self.assertIn(os.path.join(new, "_internal"), line)

    def test_checker_off_by_default_in_the_portableapps_package(self):
        from unittest import mock
        from PySide6.QtCore import QSettings
        from kanzonascad import paths
        st = QSettings(os.path.join(tempfile.mkdtemp(), "s.ini"), QSettings.IniFormat)
        c = updates.UpdateChecker(st)
        self.assertTrue(c.enabled())
        with mock.patch.object(paths, "platform_updates", return_value=True):
            self.assertFalse(c.enabled())
            st.setValue("update_check", "true")         # turned on by the user
            self.assertTrue(c.enabled())


class AppImageTest(unittest.TestCase):
    """The Linux AppImage replaces itself with the release's, as KanzonasPDF's."""

    APPIMAGE_HEAD = b"\x7fELF\x02\x01\x01\x00AI\x02"

    def test_running_appimage(self):
        import sys
        from unittest import mock
        f = os.path.join(tempfile.mkdtemp(), "KanzonasCAD-x86_64.AppImage")
        open(f, "wb").close()
        with mock.patch.dict(os.environ, {"APPIMAGE": f}):
            if sys.platform.startswith("linux"):
                self.assertEqual(updates.running_appimage(), os.path.realpath(f))
                with mock.patch.object(updates, "source_folder", return_value=None):
                    self.assertEqual(updates.how(), "appimage")
            with mock.patch.object(sys, "platform", "win32"):
                self.assertIsNone(updates.running_appimage())
        with mock.patch.dict(os.environ, {"APPIMAGE": f + ".gone"}):
            self.assertIsNone(updates.running_appimage())
        self.assertEqual(updates.APPIMAGE, "KanzonasCAD-x86_64.AppImage")

    def test_file_checks_and_replace(self):
        d = tempfile.mkdtemp()
        old, new, other = (os.path.join(d, n) for n in ("old.AppImage", "new", "other"))
        with open(old, "wb") as f:
            f.write(self.APPIMAGE_HEAD + b"old")
        os.chmod(old, 0o775)
        with open(new, "wb") as f:
            f.write(self.APPIMAGE_HEAD + b"new")
        with open(other, "wb") as f:
            f.write(b"\x7fELF\x02\x01\x01\x00\x00\x00\x00")
        self.assertTrue(updates.is_appimage_file(new))
        self.assertFalse(updates.is_appimage_file(other))
        self.assertFalse(updates.is_appimage_file(other + ".gone"))
        self.assertIsNone(updates.appimage_unwritable(old))
        updates.replace_appimage(new, old)
        self.assertFalse(os.path.exists(new))
        with open(old, "rb") as f:
            self.assertTrue(f.read().endswith(b"new"))
        if os.name != "nt":
            self.assertEqual(os.stat(old).st_mode & 0o777, 0o755)   # never group-writable

    def test_restart(self):
        cmd = updates.appimage_restart_command("/x/K.AppImage", pid=42)
        self.assertEqual(cmd[0], "/bin/sh")
        self.assertEqual(cmd[-2:], ["42", "/x/K.AppImage"])
        env = updates.restart_env({
            "APPIMAGE": "/x/K.AppImage", "APPDIR": "/tmp/appimage_extracted_ab12",
            "ARGV0": "K", "OWD": "/home/u", "LD_LIBRARY_PATH": "/tmp/appimage_extracted_ab12/"
            "usr/lib", "LD_LIBRARY_PATH_ORIG": "/opt/lib",
            "XDG_DATA_DIRS": "/tmp/appimage_extracted_ab12/usr/share:/usr/share",
            "QT_PLUGIN_PATH": "/tmp/appimage_extracted_ab12/usr/plugins", "HOME": "/home/u"})
        self.assertEqual(env, {"APPIMAGE_EXTRACT_AND_RUN": "1", "LD_LIBRARY_PATH": "/opt/lib",
                               "XDG_DATA_DIRS": "/usr/share", "HOME": "/home/u"})
        # mounted through FUSE: started the normal way
        env = updates.restart_env({"APPDIR": "/tmp/.mount_KanzonXYZ", "PATH": "/usr/bin"})
        self.assertEqual(env, {"PATH": "/usr/bin"})

    def _download(self, data, sha, folder):
        from PySide6.QtCore import QEventLoop, QObject, QTimer, QUrl
        src = os.path.join(tempfile.mkdtemp(), "KanzonasCAD-x86_64.AppImage")
        with open(src, "wb") as f:
            f.write(data)
        target = os.path.join(folder, "KanzonasCAD-x86_64.AppImage")
        owner = QObject()
        self.addCleanup(InstallerTest._dispose, owner)
        up = updates.AppImageUpdater(QUrl.fromLocalFile(src).toString(), sha, target, owner)
        got = []
        loop = QEventLoop()
        up.ready.connect(lambda p: (got.append(("ready", p)), loop.quit()))
        up.failed.connect(lambda t: (got.append(("failed", t)), loop.quit()))
        QTimer.singleShot(10000, loop.quit)
        up.start()
        if not got:
            loop.exec()
        return up, got

    def test_download_checked(self):
        import hashlib
        folder = tempfile.mkdtemp()
        data = self.APPIMAGE_HEAD + b"x" * 5000
        up, got = self._download(data, hashlib.sha256(data).hexdigest(), folder)
        self.assertEqual(got[0][0], "ready", got)
        self.assertEqual(os.path.dirname(got[0][1]), folder)     # next to it: one rename
        with open(got[0][1], "rb") as f:
            self.assertEqual(f.read(), data)
        os.remove(got[0][1])
        # a wrong digest, or a file that isn't an AppImage: refused and removed
        up, got = self._download(data, "b" * 64, folder)
        self.assertEqual(got[0][0], "failed")
        self.assertIn("sha256", got[0][1])
        junk = b"not an appimage" * 100
        up, got = self._download(junk, hashlib.sha256(junk).hexdigest(), folder)
        self.assertEqual(got, [("failed", "The download isn't a KanzonasCAD AppImage.")])
        self.assertEqual(os.listdir(folder), [])
        # one far too big is stopped
        from unittest import mock
        with mock.patch.object(updates, "APPIMAGE_MAX_BYTES", 1000):
            up, got = self._download(data, hashlib.sha256(data).hexdigest(), folder)
        self.assertEqual(got[0][0], "failed")
        self.assertIn("far bigger", got[0][1])
        self.assertEqual(os.listdir(folder), [])
