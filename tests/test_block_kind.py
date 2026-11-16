"""A block's kind can change in Block properties (the owner, 0.16: "I can't edit a power
distribution block properties after I create it... Tag Prefix, part in cross-reference,
etc": made on a panel sheet, Make block makes a panel footprint, and those rows are a
schematic symbol's, greyed out, with no way to change its kind)."""
import unittest

from PySide6.QtWidgets import QComboBox, QDialog, QLabel, QLineEdit

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad.library_panel import block_details_dialog, block_with_details


def answer(fill):
    """QDialog.exec answering the block details dialog with fill(dlg)."""
    def run(dlg):
        fill(dlg)
        return QDialog.Accepted
    return run


class BlockKindTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.lib = self.win.library
        # a power distribution block made as a footprint (as Make block does on a panel sheet)
        self.fp = M.BlockDef("PDB 3-pole", "footprint",
                             [M.Polyline([(0, 0), (2, 0), (2, 3), (0, 3)], True)])
        self.lib.save_block(self.fp)

    def tearDown(self):
        for k in ("symbol", "footprint"):
            self.lib.delete_block(k, "PDB 3-pole")
        self.v.project.saved_at = len(self.v.project.undo_stack)
        self.win.close()

    def test_the_rows_say_why_they_are_grey_and_kind_changes(self):
        seen = {}

        def fill(dlg):
            kind = dlg.findChildren(QComboBox)[0]
            prefix = [w for w in dlg.findChildren(QLineEdit)
                      if w.placeholderText().startswith("CR, M")][0]
            seen["grey"] = not prefix.isEnabled()
            seen["note"] = any("Change Kind" in lab.text() and lab.isVisibleTo(dlg)
                               for lab in dlg.findChildren(QLabel))
            seen["kind_on"] = kind.isEnabled()
            kind.setCurrentIndex(kind.findData("symbol"))
            seen["open"] = prefix.isEnabled()
            prefix.setText("pdb")
            role = [b for b in dlg.findChildren(QComboBox) if b.findData("parent") >= 0][0]
            role.setCurrentIndex(role.findData("device"))
        saved = QDialog.exec
        QDialog.exec = answer(fill)
        try:
            new = self.win.block_properties("footprint", "PDB 3-pole")
        finally:
            QDialog.exec = saved
        self.assertTrue(seen["grey"] and seen["note"] and seen["kind_on"] and seen["open"],
                        seen)
        self.assertEqual((new.kind, new.prefix, new.role), ("symbol", "PDB", "device"))
        self.assertIsNotNone(new.tag_pos)                 # (a tag spot above it)
        self.assertGreater(new.tag_pos[1], 3.0)
        self.assertIsNotNone(self.lib.get("symbol", "PDB 3-pole"))
        self.assertFalse(self.lib.has_own("footprint", "PDB 3-pole"))   # (moved over)

    def test_a_symbol_keeps_its_details(self):
        sym = M.BlockDef("PDB 3-pole", "symbol", [M.Line((0, 0), (1, 0))],
                         [{"name": "1", "pos": (0, 0)}, {"name": "2", "pos": (1, 0)}],
                         prefix="DB", role="device")
        new, _m = block_with_details(sym, {"kind": "symbol", "name": "PDB 3-pole",
                                           "prefix": "PDB", "role": "parent",
                                           "pin_names": ["IN", "OUT"]})
        self.assertEqual((new.prefix, new.role, [p["name"] for p in new.pins]),
                         ("PDB", "parent", ["IN", "OUT"]))


if __name__ == "__main__":
    unittest.main()
