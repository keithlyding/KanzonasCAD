"""The other copies running, and the files open when KanzonasCAD last closed (the owner, 0.16:
"When updating, if I have two instances of the application running, only one quits. I'd also
like a setting to be able to reopen files that were open when it closed last").

- instances.Instances: each copy listens on a local socket and leaves a note; close_others
  asks every other copy to close for an update and gets back whether it did and its files;
  a note nothing answers is removed. Checked in one process and with a real second process.
- MainWindow: an update stops when another copy stays open (its question cancelled);
  closing writes the open files (with those the other copies had), and with the option on
  they open again."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock

from PySide6.QtWidgets import QMessageBox

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad.instances import Instances
from kanzonascad.main_window import MainWindow

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class InstancesTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.made = []

    def tearDown(self):
        for i in self.made:
            i.stop()

    def make(self, pid):
        i = Instances(self.folder, pid)
        self.made.append(i)
        return i

    def test_another_copy_closes_and_sends_its_files(self):
        a, b = self.make(91001), self.make(91002)
        b.asked.connect(lambda: b.answer(True, ["/x/one.kzcad", "/x/two.kzcad"]))
        self.assertEqual(a.others(), [91002])
        self.assertEqual(a.close_others(5000), (1, 0, ["/x/one.kzcad", "/x/two.kzcad"]))

    def test_a_copy_that_stays_open_is_counted(self):
        a, b, c = self.make(91001), self.make(91002), self.make(91003)
        b.asked.connect(lambda: b.answer(False))
        c.asked.connect(lambda: c.answer(True, ["/y.kzcad"]))
        self.assertEqual(a.close_others(5000), (1, 1, ["/y.kzcad"]))

    def test_answers_read_behind_slow_work(self):
        # (a slow event in the queue, as an earlier test can leave in a full run: the wait ran
        # out before the answers were read, and the copy that answered "kept" counted as gone,
        # its note removed; CI, Nov 2026)
        from PySide6.QtCore import QTimer
        a, b, c = self.make(91001), self.make(91002), self.make(91003)
        b.asked.connect(lambda: b.answer(False))
        c.asked.connect(lambda: c.answer(True, ["/y.kzcad"]))
        QTimer.singleShot(0, lambda: time.sleep(1.5))
        self.assertEqual(a.close_others(1000), (1, 1, ["/y.kzcad"]))
        self.assertEqual(sorted(a.others()), [91002, 91003])

    def test_a_copy_that_never_answers_stays_open(self):
        # (connected but silent past the wait: running, so counted as staying open, its note
        # kept; the update doesn't go ahead over it)
        a, b = self.make(91001), self.make(91002)
        self.assertEqual(a.close_others(300), (0, 1, []))
        self.assertEqual(a.others(), [91002])

    def test_a_note_nothing_answers_is_removed(self):
        a = self.make(91001)
        with open(os.path.join(self.folder, "91009"), "w") as f:
            f.write("kanzonascad-nobody-91009")
        self.assertEqual(a.running_others(), 0)
        self.assertEqual(a.others(), [])
        with open(os.path.join(self.folder, "91008"), "w") as f:
            f.write("kanzonascad-nobody-91008")
        self.assertEqual(a.close_others(5000), (0, 0, []))
        self.assertEqual(a.others(), [])

    def test_stop_takes_the_note_away(self):
        a, b = self.make(91001), self.make(91002)
        self.assertEqual(a.running_others(), 1)
        b.stop()
        self.made.remove(b)
        self.assertEqual(a.others(), [])

    def test_a_note_is_never_seen_half_written(self):
        # (a copy starting while another looked: the note was there before its name was in
        # it, the other read nothing, took the new copy for gone and removed its note; CI,
        # Nov 2026)
        import builtins
        real_open, seen = builtins.open, []
        note = os.path.join(self.folder, "91005")

        class Watched:
            def __init__(self, f):
                self.f = f

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                self.f.close()

            def write(self, text):
                seen.append(os.path.exists(note))
                return self.f.write(text)

        def watched_open(path, mode="r", *a, **k):
            f = real_open(path, mode, *a, **k)
            return Watched(f) if "w" in mode and str(path).startswith(note) else f
        with unittest.mock.patch("builtins.open", watched_open):
            a = self.make(91005)
        self.assertEqual(seen, [False])
        b = self.make(91006)
        self.assertEqual(b.others(), [91005])
        self.assertEqual(b.running_others(), 1)
        self.assertEqual(sorted(os.listdir(self.folder)), ["91005", "91006"])
        self.assertTrue(a.name)

    def test_a_real_second_process_closes(self):
        script = (
            "import sys; sys.path.insert(0, %r)\n"
            "from PySide6.QtCore import QCoreApplication, QTimer\n"
            "app = QCoreApplication([])\n"
            "from kanzonascad.instances import Instances\n"
            "i = Instances(%r)\n"
            "def asked():\n"
            "    i.answer(True, ['/z/three.kzcad'])\n"
            "    i.stop()\n"
            "    app.quit()\n"
            "i.asked.connect(asked)\n"
            "QTimer.singleShot(60000, app.quit)\n"
            "app.exec()\n" % (ROOT, self.folder))
        proc = subprocess.Popen([sys.executable, "-c", script],
                                env=dict(os.environ, QT_QPA_PLATFORM="offscreen"))
        try:
            a = self.make(os.getpid())
            t = time.time()
            while not a.others() and time.time() - t < 30:
                time.sleep(0.05)
            self.assertEqual(a.others(), [proc.pid])
            self.assertEqual(a.running_others(), 1)
            self.assertEqual(a.close_others(20000), (1, 0, ["/z/three.kzcad"]))
            self.assertEqual(proc.wait(20), 0)
            self.assertEqual(a.others(), [])
        finally:
            if proc.poll() is None:
                proc.kill()


class ReopenAndUpdateTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.folder = tempfile.mkdtemp()
        self.mine = Instances(self.folder, 92001)
        self.other = Instances(self.folder, 92002)
        MainWindow.instances = self.mine
        MainWindow.reopen_extra = ()
        self._warn = QMessageBox.warning
        self.warned = []
        QMessageBox.warning = staticmethod(lambda *a, **k: self.warned.append(a[2]))

    def tearDown(self):
        QMessageBox.warning = self._warn
        MainWindow.instances = None
        MainWindow.reopen_extra = ()
        self.mine.stop()
        self.other.stop()
        for w in list(self.win.family):
            for i in range(w.tabs.count()):
                d = w.tabs.widget(i)
                if hasattr(d, "project"):
                    d.project.saved_at = len(d.project.undo_stack)
        self.win.close()

    def saved(self, name):
        path = os.path.join(tempfile.mkdtemp(), name)
        p = M.Project.new()
        p.save(path)
        return path

    def test_the_update_stops_when_another_copy_stays_open(self):
        self.other.asked.connect(lambda: self.other.answer(False))
        self.assertFalse(self.win.close_other_copies())
        self.assertIn("stayed open", self.warned[-1])

    def test_the_update_goes_on_once_the_others_closed(self):
        self.other.asked.connect(lambda: self.other.answer(True, ["/o/other.kzcad"]))
        self.assertTrue(self.win.close_other_copies())
        self.assertEqual(MainWindow.reopen_extra, ("/o/other.kzcad",))

    def test_asked_to_close_it_closes_like_quit_and_answers(self):
        from PySide6.QtWidgets import QApplication
        a = self.saved("asked.kzcad")
        self.win.open_path(a)
        self.mine.asked.connect(self.win.answer_close_for_update)
        quits = []
        real = QApplication.quit
        QApplication.quit = lambda *_a: quits.append(1)
        try:
            self.assertEqual(self.other.close_others(5000),
                             (1, 0, [os.path.abspath(a)]))
        finally:
            QApplication.quit = real
        self.assertFalse(self.win.isVisible())
        self.assertEqual(quits, [1])

    def test_with_unsaved_changes_cancelled_it_stays_and_says_so(self):
        d = self.win.doc()
        with d.project.edit("line") as ed:
            ed.add(d.view.sheet(), M.Line((0.0, 0.0), (1.0, 1.0)))
        self.mine.asked.connect(self.win.answer_close_for_update)
        real = QMessageBox.question
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Cancel)
        try:
            self.assertEqual(self.other.close_others(5000), (0, 1, []))
        finally:
            QMessageBox.question = real
        self.assertTrue(self.win.isVisible())

    def test_closing_keeps_the_open_files_and_they_open_again(self):
        a, b = self.saved("a.kzcad"), self.saved("b.kzcad")
        self.win.open_path(a)
        self.win.open_path(b)
        MainWindow.reopen_extra = (a, "/gone/c.kzcad")
        self.assertEqual(self.win.open_files(), [os.path.abspath(a), os.path.abspath(b)])
        self.assertTrue(self.win.close())
        got = json.loads(self.win.settings.value("open_files"))
        self.assertEqual(got, [os.path.abspath(a), os.path.abspath(b), "/gone/c.kzcad"])
        # a new window, the option on: both open again (the one that's gone is left out)
        self.win, self.v = window()
        self.win.settings.setValue("reopen_files", True)
        self.assertTrue(self.win.reopen_on())
        self.assertEqual(self.win.reopen_last(), 2)
        self.assertEqual(sorted(self.win.open_files()),
                         sorted([os.path.abspath(a), os.path.abspath(b)]))
        self.win.settings.setValue("reopen_files", False)
        self.assertFalse(self.win.reopen_on())


if __name__ == "__main__":
    unittest.main()
