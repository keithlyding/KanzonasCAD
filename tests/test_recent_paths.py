"""Open recent lists each file once (the owner: "Why does my 'open recent' have two of the same
files but with alternate facing slashes?"): Save as gave C:/Users/... (Qt's Save window), opening
C:\\Users\\..., and the list compared the text. Checked with Windows' path rules (ntpath) on any
system."""
import ntpath
import os
import tempfile
import unittest

from kanzonascad.paths import path_key, recent_list

A = "C:\\Users\\me\\OneDrive - Co\\AutoCad\\BK010-FPC Test Sheet.kzcad"
A_FWD = "C:/Users/me/OneDrive - Co/AutoCad/BK010-FPC Test Sheet.kzcad"
B = "C:\\Users\\me\\Downloads\\BK010-FPC-100-0002.dwg"


class RecentPathsTest(unittest.TestCase):
    def test_same_file_however_written(self):
        self.assertEqual(path_key(A, ntpath), path_key(A_FWD, ntpath))
        self.assertEqual(path_key(A, ntpath), path_key(A.lower(), ntpath))   # (Windows: any case)
        self.assertNotEqual(path_key(A, ntpath), path_key(B, ntpath))

    def test_owner_list_cleaned(self):
        # the owner's list as it was: the same two files twice each
        got = recent_list([A, A_FWD, B, B.replace("\\", "/")], pathmod=ntpath)
        self.assertEqual(got, [A, B])

    def test_saved_with_forward_slashes_goes_first_once(self):
        got = recent_list([B, A], A_FWD, limit=10, pathmod=ntpath)
        self.assertEqual(got, [A, B])           # (written with backslashes, the old one gone)
        self.assertEqual(len(recent_list([A] * 30, B, limit=10, pathmod=ntpath)), 2)

    def test_window_remembers_once_and_finds_open_tab(self):
        from tests.util import window
        win, v = window()
        try:
            with tempfile.TemporaryDirectory() as d:
                path = os.path.join(d, "t.kzcad")
                win._save_to(win.doc(), path)
                win._remember(os.path.join(d, ".", "t.kzcad"))
                self.assertEqual(win._recent()[0], path)
                self.assertEqual(sum(1 for p in win._recent() if path_key(p) == path_key(path)), 1)
                n = win.tabs.count()
                win.open_path(os.path.join(d, ".", "t.kzcad"))      # (already open: its tab)
                self.assertEqual(win.tabs.count(), n)
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()


if __name__ == "__main__":
    unittest.main()
