"""A project open for editing is marked so, and a second copy opens it read-only (the owner,
0.25: "I was able to open two instances of the same file in two different instances of
KanzonasCAD. I think we need something to say locked for editing, open as read only?").

Two copies of the program are two windows here, each its own family, opening as a different
user, computer or process (MainWindow.lock_who)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from PySide6.QtWidgets import QFileDialog, QMessageBox

from tests.util import APP, window

from kanzonascad import backup
from kanzonascad import filelock as FL
from kanzonascad import model as M


def dead_pid():
    """A process id that was running a moment ago and isn't now."""
    pr = subprocess.Popen([sys.executable, "-c", "pass"])
    pr.wait()
    return pr.pid


def history(win):
    return win.cmdline.history.toPlainText()


class FileLockTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "Plant.kzcad")
        p = M.Project.new()
        p.sheets[0].title = "on disk"
        p.save(self.path, backups=0)
        with open(self.path, "rb") as f:
            self.bytes = f.read()
        self.wins = []
        self.asked = []

    def tearDown(self):
        for w in self.wins:
            for _w, d in w.documents():
                d.project.saved_at = len(d.project.undo_stack)
            w.close()
        self.assertTrue(APP)

    def copy(self, user="ann", computer="PC-1", pid=None, answer="read_only"):
        """A copy of the program (a window of its own) opening as that user on that computer;
        answer: what it chooses when the project is open elsewhere."""
        w, _v = window()
        w.lock_who = FL.Who(user, computer, os.getpid() if pid is None else pid)

        def ask(path, info, w=w):
            self.asked.append((w, info))
            return answer
        w.ask_locked = ask
        self.wins.append(w)
        return w

    def note(self, path=None):
        return FL.read(path or self.path)

    def untouched(self):
        with open(self.path, "rb") as f:
            self.assertEqual(f.read(), self.bytes, "the original file was written")

    # ---- the note --------------------------------------------------------------------------
    def test_note_beside_it_while_open(self):
        a = self.copy()
        d = a.open_path(self.path)
        self.assertFalse(d.project.read_only)
        note = FL.note_path(self.path)
        self.assertEqual(os.path.basename(note), ".~lock.Plant.kzcad#")
        got = self.note()
        for k, want in (("user", "ann"), ("computer", "PC-1"), ("pid", os.getpid()),
                        ("program", "KanzonasCAD")):
            self.assertEqual(got[k], want)
        from kanzonascad import __version__
        self.assertEqual(got["version"], __version__)
        self.assertRegex(got["opened"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d")
        self.assertEqual(self.asked, [])
        a.close_tab(a.tabs.indexOf(d))
        self.assertFalse(os.path.exists(note), "the note stayed after the project closed")

    def test_note_gone_on_quit(self):
        a = self.copy()
        a.open_path(self.path)
        self.assertIsNotNone(self.note())
        a.close()                                       # (Quit closes the window)
        self.assertIsNone(self.note())

    def test_release_all_at_exit(self):
        lock = FL.acquire(self.path, FL.Who("ann", "PC-1"))
        self.assertIn(lock, FL._held)
        FL.release_all()
        self.assertIsNone(self.note())

    # ---- another copy ----------------------------------------------------------------------
    def test_another_computer_opens_it_read_only(self):
        a, b = self.copy("ann", "PC-1"), self.copy("bob", "PC-2")
        a.open_path(self.path)
        d = b.open_path(self.path)
        self.assertEqual(len(self.asked), 1)
        self.assertEqual(self.asked[0][1]["computer"], "PC-1")
        self.assertEqual(FL.describe(self.path, self.asked[0][1])[:40],
                         "Plant.kzcad is open on PC-1 by ann since")
        self.assertTrue(d.project.read_only)
        self.assertIn("(read-only)", b.tabs.tabText(b.tabs.indexOf(d)))
        self.assertIn("(read-only)", b.windowTitle())
        self.assertEqual(self.note()["user"], "ann")    # (still ann's)
        # Save, and Ctrl+S: said, nothing written; edits are allowed in memory
        with d.project.edit("line") as ed:
            ed.add(d.view.sheet(), M.Line((1, 1), (2, 2)))
        self.assertTrue(b.acts["save"].isEnabled())
        self.assertFalse(b.save())
        b.acts["save"].trigger()
        self.assertEqual(history(b).count("read-only: use Save As..."), 2)
        self.untouched()
        # closing it offers Save As for the changes (Discard here), and leaves ann's note
        with mock.patch.object(QMessageBox, "question",
                               return_value=QMessageBox.Discard) as asked:
            self.assertTrue(b.close_tab(b.tabs.indexOf(d)))
        self.assertIn("is read-only. Save your changes to a copy", asked.call_args[0][2])
        self.untouched()
        self.assertEqual(self.note()["user"], "ann")

    def test_two_copies_on_this_computer(self):
        a = self.copy("ann", "PC-1", os.getpid())
        live = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            b = self.copy("ann", "PC-1", live.pid)
            a.open_path(self.path)
            d = b.open_path(self.path)          # (ann's copy is running: asked)
            self.assertEqual(len(self.asked), 1)
            self.assertTrue(d.project.read_only)
        finally:
            live.kill()
            live.wait()

    def test_stale_note_taken_over_silently(self):
        FL.acquire(self.path, FL.Who("ann", "pc-1", dead_pid()))   # (a crash left it)
        FL._held.clear()
        b = self.copy("ann", "PC-1")
        d = b.open_path(self.path)
        self.assertEqual(self.asked, [])
        self.assertFalse(d.project.read_only)
        self.assertEqual(self.note()["pid"], os.getpid())

    def test_stale_from_another_computer_is_asked(self):
        FL.acquire(self.path, FL.Who("ann", "PC-9", dead_pid()))
        FL._held.clear()
        b = self.copy("bob", "PC-1", answer=None)       # (Cancel)
        self.assertIsNone(b.open_path(self.path))
        self.assertEqual(len(self.asked), 1)
        self.assertEqual(self.note()["computer"], "PC-9")

    def test_same_copy_twice_switches_to_its_tab(self):
        a = self.copy()
        d = a.open_path(self.path)
        a.new_project()
        self.assertIs(a.open_path(self.path), d)
        self.assertIs(a.doc(), d)
        self.assertEqual(self.asked, [])
        self.assertFalse(d.project.read_only)

    def test_open_anyway(self):
        a, b = self.copy("ann", "PC-1"), self.copy("bob", "PC-2", answer="anyway")
        da = a.open_path(self.path)
        warned = []

        def warning(*args, **k):
            warned.append(args[2])
            return QMessageBox.Yes
        with mock.patch.object(QMessageBox, "warning", warning):
            d = b.open_path(self.path)
        self.assertIn("each copy saves over the other's", warned[0])
        self.assertFalse(d.project.read_only)
        self.assertEqual(self.note()["user"], "bob")
        # ann's copy then saving: warned, No keeps bob's file and note
        with da.project.edit("line") as ed:
            ed.add(da.view.sheet(), M.Line((1, 1), (2, 2)))
        a.tabs.setCurrentWidget(da)
        with mock.patch.object(QMessageBox, "warning", return_value=QMessageBox.No):
            self.assertFalse(a.save())
        self.untouched()
        # ann's copy closing leaves bob's note; bob's closing takes it away
        da.project.saved_at = len(da.project.undo_stack)      # (Discard)
        a.close_tab(a.tabs.indexOf(da))
        self.assertEqual(self.note()["user"], "bob")
        b.close_tab(b.tabs.indexOf(d))
        self.assertIsNone(self.note())

    def test_save_as_makes_your_own_copy(self):
        a, b = self.copy("ann", "PC-1"), self.copy("bob", "PC-2")
        a.open_path(self.path)
        d = b.open_path(self.path)
        with d.project.edit("line") as ed:
            ed.add(d.view.sheet(), M.Line((1, 1), (2, 2)))
        mine = os.path.join(self.dir, "Mine.kzcad")
        seen = []

        def ask(_w, _t, start, _f):
            seen.append(start)
            return mine, ""
        with mock.patch.object(QFileDialog, "getSaveFileName", ask):
            self.assertTrue(b.save_as())
        self.assertEqual(os.path.basename(seen[0]), "Plant (copy).kzcad")
        self.assertFalse(d.project.read_only)
        self.assertNotIn("(read-only)", b.windowTitle())
        self.assertEqual(self.note(mine)["user"], "bob")
        self.assertEqual(self.note()["user"], "ann")
        self.untouched()
        self.assertEqual(len(M.Project.load(mine).sheets[0].entities), 1)
        # Save As over the original, still open in ann's copy: refused
        with mock.patch.object(QFileDialog, "getSaveFileName", return_value=(self.path, "")), \
                mock.patch.object(QMessageBox, "warning") as told:
            self.assertFalse(b.save_as())
        self.assertIn("open on PC-1 by ann", told.call_args[0][2])
        self.untouched()
        b.close_tab(b.tabs.indexOf(d))
        self.assertIsNone(self.note(mine))

    def test_save_as_moves_the_lock(self):
        a = self.copy()
        d = a.open_path(self.path)
        other = os.path.join(self.dir, "Renamed.kzcad")
        with mock.patch.object(QFileDialog, "getSaveFileName", return_value=(other, "")):
            self.assertTrue(a.save_as())
        self.assertIsNone(self.note())
        self.assertEqual(self.note(other)["user"], "ann")
        a.close_tab(a.tabs.indexOf(d))
        self.assertIsNone(self.note(other))

    def test_autosave_never_touches_the_original(self):
        a, b = self.copy("ann", "PC-1"), self.copy("bob", "PC-2")
        da = a.open_path(self.path)
        d = b.open_path(self.path)
        for w, doc in ((a, da), (b, d)):
            with doc.project.edit("line") as ed:
                ed.add(doc.view.sheet(), M.Line((1, 1), (2, 2)))
            self.assertEqual(w.autosave(), 1)
        self.untouched()
        self.assertNotEqual(backup.autosave_path(d.autosave_key),
                            backup.autosave_path(da.autosave_key))
        with open(backup.autosave_path(d.autosave_key), encoding="utf-8") as f:
            got = json.load(f)
        self.assertEqual((got["autosave_of"], got["read_only_of"]), ("", self.path))
        # recovered after a crash: an unsaved project, not the original
        left = [x for x in backup.leftovers() if x[0] == backup.autosave_path(d.autosave_key)]
        self.assertEqual([x[3] for x in left], [self.path])
        others = [x[0] for x in backup.leftovers() if x not in left]
        with mock.patch.object(backup, "leftovers", return_value=left), \
                mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            self.assertEqual(b.offer_recovery(), 1)
        self.assertIsNone(b.doc().project.path)
        for f in others:
            os.remove(f)

    def test_recovered_while_open_elsewhere_is_read_only(self):
        a, b = self.copy("ann", "PC-1"), self.copy("bob", "PC-2")
        da = a.open_path(self.path)
        self.assertTrue(a._save_to(da, self.path))      # (its autosave copy named by the path)
        with open(self.path, "rb") as f:
            self.bytes = f.read()
        q = M.Project.load(self.path)
        with q.edit("line") as ed:
            ed.add(q.sheets[0], M.Line((1, 1), (2, 2)))
        rec = backup.write_autosave(q, "crashed-" + self.path)
        with mock.patch.object(backup, "leftovers",
                               return_value=[(rec, self.path, 0.0, "")]), \
                mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            self.assertEqual(b.offer_recovery(), 1)
        d = b.doc()
        self.assertTrue(d.project.read_only)
        self.assertFalse(b.save())
        self.untouched()
        # (its autosave copy never the one ann's copy writes)
        self.assertNotEqual(backup.autosave_path(d.autosave_key),
                            backup.autosave_path(da.autosave_key))

    # ---- folders that can't take a note --------------------------------------------------
    def test_read_only_folder(self):
        a = self.copy()
        real = os.open

        def refuse(path, *args):
            if os.path.basename(path).startswith(FL.PREFIX):
                raise PermissionError(13, "Permission denied", path)
            return real(path, *args)
        with mock.patch.object(FL.os, "open", refuse):
            d = a.open_path(self.path)
        self.assertTrue(d.project.read_only)
        self.assertIn("its folder can't be written", history(a))
        self.assertIn("Permission denied", history(a))
        self.assertIsNone(self.note())

    def test_read_only_file(self):
        a = self.copy()
        real = os.access
        with mock.patch("kanzonascad.locking.os.access",
                        lambda p, m: False if p == self.path else real(p, m)):
            d = a.open_path(self.path)
        self.assertTrue(d.project.read_only)
        self.assertIn("the file itself is read-only", history(a))

    # ---- two at once ---------------------------------------------------------------------
    def test_atomic_create(self):
        FL.acquire(self.path, FL.Who("ann", "PC-1"))
        with self.assertRaises(FL.Held) as got:
            FL.acquire(self.path, FL.Who("bob", "PC-2"))
        self.assertEqual(got.exception.info["user"], "ann")
        # (the note is made with O_EXCL: a note made between a look and the write isn't
        # written over; os.open is the only call that makes it)
        real = os.open
        flags = []

        def spy(path, fl, *a):
            flags.append(fl)
            return real(path, fl, *a)
        with mock.patch.object(FL.os, "open", spy):
            FL.acquire(os.path.join(self.dir, "Other.kzcad"), FL.Who("bob", "PC-2"))
        self.assertTrue(flags[0] & os.O_EXCL and flags[0] & os.O_CREAT)
        FL.release_all()

    def test_two_taking_over_a_stale_note(self):
        # ann's copy crashed; bob's and carl's (both on PC-1) open it at the same moment:
        # carl's takes it over between bob's look at the stale note and bob's move of it
        FL.acquire(self.path, FL.Who("ann", "PC-1", dead_pid()))
        FL._held.clear()
        real = FL._parse
        raced = []

        def parse(raw):
            if not raced:
                raced.append("carl")
                FL.acquire(self.path, FL.Who("carl", "PC-1"))
            return real(raw)
        with mock.patch.object(FL, "_parse", parse):
            with self.assertRaises(FL.Held) as got:
                FL.acquire(self.path, FL.Who("bob", "PC-1"))
        self.assertEqual(got.exception.info["user"], "carl")
        self.assertEqual(self.note()["user"], "carl")
        self.assertEqual([f for f in os.listdir(self.dir) if f.endswith(".old")], [])
        FL.release_all()

    def test_reopen_for_editing(self):
        a, b = self.copy("ann", "PC-1"), self.copy("bob", "PC-2")
        da = a.open_path(self.path)
        d = b.open_path(self.path)
        self.assertTrue(b.acts["reopen_edit"].isEnabled())
        self.assertIsNone(b.reopen_for_editing())       # (still open in ann's copy)
        self.assertIn("open on PC-1 by ann", history(b))
        a.close_tab(a.tabs.indexOf(da))
        nd = b.reopen_for_editing()
        self.assertIsNot(nd, d)
        self.assertFalse(nd.project.read_only)
        self.assertEqual(self.note()["user"], "bob")
        self.assertFalse(b.acts["reopen_edit"].isEnabled())


if __name__ == "__main__":
    unittest.main()
