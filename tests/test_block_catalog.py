"""A block's catalog (part) number (the owner: "include the part number as an option when
creating blocks"): kept with the block, filled in as a placed copy's CAT, found by the
Library's search."""
import json
import os
import tempfile
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class BlockCatalogTest(unittest.TestCase):
    def test_kept_and_old_blocks_load_without_it(self):
        b = M.BlockDef("Chassis", "footprint", [M.Line((0, 0), (1, 0))],
                       manufacturer="Allen-Bradley", catalog="1756-A10")
        again = M.BlockDef.from_dict(json.loads(json.dumps(b.to_dict())))
        self.assertEqual(again.catalog, "1756-A10")
        old = M.BlockDef.from_dict({"name": "Old", "kind": "symbol", "entities": []})
        self.assertEqual(old.catalog, "")
        self.assertNotIn("catalog", old.to_dict())      # (old files stay as they were)

    def test_placing_fills_cat_unless_a_part_gave_one(self):
        win, v = window()
        try:
            v.osnap_on = v.snap_on = False
            b = M.BlockDef("Chassis", "footprint", [M.Line((0, 0), (1, 0))],
                           manufacturer="Allen-Bradley", catalog="1756-A10")
            v.run(C.InsertCmd, b, {})
            type_in(v, "3,3")
            ins = max(v.sheet().inserts(), key=lambda e: e.id)
            self.assertEqual(ins.attrs.get("CAT"), "1756-A10")
            self.assertEqual(ins.attrs.get("MFR"), "Allen-Bradley")
            v.run(C.InsertCmd, b, {"CAT": "1756-A13"})
            type_in(v, "6,3")
            ins = max(v.sheet().inserts(), key=lambda e: e.id)
            self.assertEqual(ins.attrs.get("CAT"), "1756-A13")
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()

    def test_library_search_finds_it(self):
        from kanzonascad.library import Library
        from kanzonascad.library_panel import LibraryPanel
        lib = Library(tempfile.mkdtemp())
        lib.save_block(M.BlockDef("Chassis", "footprint", [M.Line((0, 0), (1, 0))],
                                  catalog="1756-A10"))
        panel = LibraryPanel(lib)
        panel.search.setText("1756-a10")
        tree = panel.trees["footprint"]
        names = [tree.topLevelItem(i).child(j).data(0, 0x0100)
                 for i in range(tree.topLevelItemCount())
                 for j in range(tree.topLevelItem(i).childCount())]
        self.assertEqual(names, ["Chassis"])
        panel.search.setText("1769")
        self.assertEqual(panel.trees["footprint"].topLevelItemCount(), 0)
        self.assertTrue(APP and os)


if __name__ == "__main__":
    unittest.main()
