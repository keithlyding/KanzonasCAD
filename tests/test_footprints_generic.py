"""The program's own generic footprints (the owner, Nov 2026: a new panel sheet had nothing to
place): listed in the library as built in, at typical real sizes, a footprint of yours of the
same name over them, placed on a panel sheet and onto DIN rail like any footprint."""
import tempfile
import unittest

from tests.util import APP, window, type_in  # noqa: F401

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad.footprints_generic import builtin_footprints, MM
from kanzonascad.library import Library


def size(d):
    bb = None
    for e in d.entities:
        b = e.bbox()
        bb = b if bb is None else (min(bb[0], b[0]), min(bb[1], b[1]), max(bb[2], b[2]),
                                   max(bb[3], b[3]))
    return bb[2] - bb[0], bb[3] - bb[1]


class GenericFootprintsTest(unittest.TestCase):
    def test_listed_as_built_in(self):
        lib = Library(tempfile.mkdtemp())
        fps, bad = lib.blocks("footprint")
        self.assertEqual(bad, [])
        names = {b.name for b in builtin_footprints()}
        self.assertGreaterEqual(len(names), 30)
        self.assertTrue(names <= set(fps))
        for n in names:
            d = fps[n]
            self.assertEqual(d.kind, "footprint")
            self.assertTrue(d.builtin)
            self.assertTrue(d.category.startswith("Generic/"), d.category)
            self.assertIn("check the maker's drawing", d.description)
        # (symbols aren't footprints, and the other way around)
        syms, _b = lib.blocks("symbol")
        self.assertFalse(names & set(syms))

    def test_typical_sizes(self):
        fps = {b.name: b for b in builtin_footprints()}
        w, h = size(fps["Breaker 1-pole (DIN)"])
        self.assertAlmostEqual(w, 18 * MM, places=3)    # one DIN module
        self.assertAlmostEqual(h, 90 * MM, places=3)
        self.assertAlmostEqual(size(fps["Breaker 3-pole (DIN)"])[0], 54 * MM, places=3)
        self.assertAlmostEqual(size(fps["Terminal block 2.5 mm2 (#12 AWG)"])[0], 5.2 * MM,
                               places=3)
        for d in fps.values():
            w, h = size(d)
            self.assertTrue(0.05 < w < 6 and 0.3 < h < 6, (d.name, w, h))
            # on the rail by its middle, except what mounts on the back panel or the door
            on_door = d.category in ("Generic/Transformers", "Generic/Door devices")
            self.assertEqual(d.rail_pos is None, on_door, d.name)

    def test_yours_over_built_in(self):
        lib = Library(tempfile.mkdtemp())
        mine = M.BlockDef("Contactor 9-18 A", "footprint", [M.Circle((0, 0), 2)],
                          catalog="100-C09D10")
        lib.save_block(mine)
        got = lib.get("footprint", "Contactor 9-18 A")
        self.assertFalse(got.builtin)
        self.assertEqual(got.catalog, "100-C09D10")

    def test_placed_on_a_panel_sheet(self):
        win, v = window()
        try:
            v.osnap_on = v.snap_on = v.polar_on = v.ortho_on = False
            p, s = v.project, v.sheet()
            with p.edit("Panel") as ed:
                ed.sheet_meta(s, kind="panel")
            d = win.library.get("footprint", "Breaker 2-pole (DIN)")
            v.run(C.InsertCmd, d, {"TAG": "CB1"})
            type_in(v, "10,10")
            if v.cmd is not None:
                v.cancel()
            got = [e for e in s.entities.values() if isinstance(e, M.Insert)]
            self.assertEqual(len(got), 1)
            self.assertEqual(got[0].block, "Breaker 2-pole (DIN)")
            self.assertEqual(got[0].attrs.get("TAG"), "CB1")
            self.assertIn("Breaker 2-pole (DIN)", p.blocks)      # (the project's copy)
            p.saved_at = len(p.undo_stack)
        finally:
            win.close()


if __name__ == "__main__":
    unittest.main()
