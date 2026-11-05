"""Duplicate... a library block (the owner: "duplicate footprints and then change random
things to make it different ... duplicate should open the library copy right away") and Save
block as... in the block editor."""
import unittest
from unittest import mock

from PySide6.QtWidgets import QInputDialog, QMessageBox

from tests import test_block_editing as TBE
from kanzonascad import block_window as BW
from kanzonascad import model as M


def footprint(name="VFD 10x15", **kw):
    return M.BlockDef(name, "footprint", [M.Polyline([(0, 0), (10, 0), (10, 15), (0, 15)], True),
                                          M.Circle((5, 12), 0.1)],
                      category="Drives", manufacturer="Allen-Bradley", family="PowerFlex 525",
                      series="A", catalog="25B-D010N104", **kw)


class DuplicateTest(unittest.TestCase):
    setUp = TBE.BlockWindowTest.setUp
    tearDown = TBE.BlockWindowTest.tearDown

    def names(self, *answers):
        """QInputDialog.getText answering these names in turn (None: Cancel); the names it
        offered are kept."""
        self.offered = []
        it = iter(answers)

        def get_text(_parent, _title, _label, _mode=None, text="", *a, **k):
            self.offered.append(text)
            got = next(it)
            return ("", False) if got is None else (got, True)
        return mock.patch.object(QInputDialog, "getText", staticmethod(get_text))

    def test_duplicate_from_the_library_opens_the_copy(self):
        self.lib.save_block(footprint())
        self.win.show_library(1)
        self.win.library_panel.search.setText("VFD")
        tree = self.win.library_panel.trees["footprint"]
        tree.setCurrentItem(tree.topLevelItem(0).child(0))
        tabs = self.win.tabs.count()
        with self.names("VFD 10x18"):
            self.win.library_panel.b_dup.click()
        self.assertEqual(self.offered, ["VFD 10x15 copy"])
        new = self.lib.get("footprint", "VFD 10x18")
        old = self.lib.get("footprint", "VFD 10x15")
        # everything kept but the name and the catalog number
        self.assertEqual(new.catalog, "")
        self.assertEqual(old.catalog, "25B-D010N104")
        a, b = old.to_dict(), new.to_dict()
        for d in (a, b):
            d.pop("name")
            d.pop("catalog", None)
        self.assertEqual(a, b)
        # opened in Edit block right away
        self.assertEqual(self.win.tabs.count(), tabs + 1)
        d = self.win.doc()
        self.assertTrue(BW.is_block_doc(d))
        self.assertEqual((d.block_session.kind, d.block_session.name), ("footprint", "VFD 10x18"))
        self.assertFalse(self.win.library_dialog.isVisible())

    def test_name_offered_is_free_and_a_taken_one_is_asked_again(self):
        self.lib.save_block(footprint())
        self.lib.save_block(footprint("VFD 10x15 copy"))
        infos = []
        with self.names("VFD 10x15", "Mine"), \
                mock.patch.object(QMessageBox, "information",
                                  lambda *a, **k: infos.append(a[2])):
            self.win.duplicate_block("footprint", "VFD 10x15")
        self.assertEqual(self.offered, ["VFD 10x15 copy 2", "VFD 10x15"])
        self.assertIn("already has a footprint named VFD 10x15", infos[0])
        self.assertIsNotNone(self.lib.get("footprint", "Mine"))

    def test_cancel_changes_nothing(self):
        self.lib.save_block(footprint())
        tabs = self.win.tabs.count()
        with self.names(None):
            self.assertIsNone(self.win.duplicate_block("footprint", "VFD 10x15"))
        self.assertEqual(self.win.tabs.count(), tabs)
        self.assertIsNone(self.lib.get("footprint", "VFD 10x15 copy"))

    def test_duplicate_a_builtin_symbol(self):
        with self.names("My coil"):
            d = self.win.duplicate_block("symbol", "Relay coil")
        mine = self.lib.get("symbol", "My coil")
        self.assertFalse(mine.builtin)
        self.assertEqual(len(mine.pins), len(self.lib.get("symbol", "Relay coil").pins))
        self.assertEqual(d.block_session.name, "My coil")
        self.assertFalse(self.lib.has_own("symbol", "Relay coil"))

    def test_save_block_as(self):
        self.lib.save_block(footprint())
        d = self.win.edit_block("footprint", "VFD 10x15")
        sheet = d.view.sheet()
        with d.project.edit("add") as ed:
            ed.add(sheet, M.Circle((5, 3), 0.2))
        with self.names("VFD 10x15 mod"):
            self.assertTrue(self.win.save_block_as())
        new = self.lib.get("footprint", "VFD 10x15 mod")
        old = self.lib.get("footprint", "VFD 10x15")
        self.assertEqual(len(new.entities), len(old.entities) + 1)
        self.assertEqual(new.catalog, "")
        self.assertEqual(old.catalog, "25B-D010N104")
        # the tab goes on editing the new one, saved
        self.assertEqual(d.block_session.name, "VFD 10x15 mod")
        self.assertEqual(sheet.title, "Block: VFD 10x15 mod")
        self.assertFalse(d.project.is_modified())
        # outside a block's tab it says so
        self.win.tabs.setCurrentIndex(0)
        self.assertFalse(self.win.save_block_as())

    def test_menus_and_panel(self):
        acts = {b.text().replace("&", "") for a in self.win.menuBar().actions() if a.menu()
                for b in a.menu().actions()}
        self.assertIn("Duplicate block...", acts)
        self.assertIn("Save block as...", acts)
        self.assertEqual(self.win.library_panel.b_dup.text(), "Duplicate...")

if __name__ == "__main__":
    unittest.main()
