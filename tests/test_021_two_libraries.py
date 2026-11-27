"""Two library folders (the owner's choice, Nov 2026: "Two library folders", each chosen
freely, one shared in a synced folder and one personal, say): both searched together, each
item showing which library it is from (the second's marked); a block or part saved back where
it is, new ones where Save new blocks and parts to the second library says; a folder that can't
be written to is used read-only."""
import os
import stat
import sys
import tempfile
import unittest

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad.library import Library, Part


def _block(name):
    return M.BlockDef(name, "symbol", [M.Line((0, 0), (1, 0))], [], None, 0.1, "Mine")


class TwoLibrariesTest(unittest.TestCase):
    def setUp(self):
        self.a, self.b = tempfile.mkdtemp(), tempfile.mkdtemp()
        Library(self.b).save_block(_block("Personal coil"))
        Library(self.b).save_part(Part(manufacturer="X", catalog="P1", symbol="Personal coil"))
        self.lib = Library(self.a, self.b)

    def test_searched_together(self):
        self.assertIsNotNone(self.lib.get("symbol", "Personal coil"))
        self.assertEqual(self.lib.where("symbol", "Personal coil"), "second")
        self.assertEqual(self.lib.where("symbol", "Relay coil"), "built in")
        self.assertEqual([p.catalog for p in self.lib.parts(builtin=False)], ["P1"])
        self.assertEqual(len(self.lib.second_parts), 1)

    def test_saved_back_where_it_is_and_new_where_asked(self):
        d = self.lib.get("symbol", "Personal coil")
        d.description = "changed"
        self.lib.save_block(d)
        self.assertEqual(Library(self.b).get("symbol", "Personal coil").description, "changed")
        self.assertFalse(Library(self.a).has_own("symbol", "Personal coil"))
        self.lib.save_block(_block("Shared coil"))
        self.assertTrue(Library(self.a).has_own("symbol", "Shared coil"))
        self.lib.save_second = True
        self.lib.save_block(_block("Mine too"))
        self.assertTrue(Library(self.b).has_own("symbol", "Mine too"))
        part = self.lib.parts(builtin=False)[0]
        part.description = "updated"
        self.lib.save_part(part)
        self.assertEqual(Library(self.b).parts(builtin=False)[0].description, "updated")
        self.assertEqual(Library(self.a).parts(builtin=False), [])
        self.lib.delete_part(part.id)
        self.assertEqual(self.lib.parts(builtin=False), [])

    @unittest.skipIf(sys.platform == "win32" or os.geteuid() == 0,
                     "read-only folders aren't read-only to root (or as such on Windows)")
    def test_read_only_used_read_only(self):
        os.chmod(self.b, stat.S_IRUSR | stat.S_IXUSR)
        try:
            self.assertIsNotNone(self.lib.get("symbol", "Personal coil"))
            with self.assertRaises(OSError):
                self.lib.save_block(self.lib.get("symbol", "Personal coil"))
        finally:
            os.chmod(self.b, stat.S_IRWXU)

    def test_window(self):
        win, v = window()
        try:
            win.library = Library(self.a)
            win.library_panel.library = win.library
            win.ask_second_library = lambda: self.b
            win.choose_second_library()
            self.assertEqual(win.library.second.folder, self.b)
            self.assertTrue(win.acts["library_save2"].isEnabled())
            win.acts["library_save2"].trigger()
            self.assertTrue(win.library.save_second)
            win.ask_second_library = lambda: ""
            win.choose_second_library()
            self.assertIsNone(win.library.second)
            self.assertFalse(win.library.save_second)
        finally:
            win.settings.remove("library_folder2")
            win.settings.remove("library_save_second")
            win.close()
        self.assertTrue(APP)


if __name__ == "__main__":
    unittest.main()
