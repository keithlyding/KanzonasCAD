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
