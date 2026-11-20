"""DXF export with AutoCAD Electrical's attribute names (the roadmap's item 11, phase 2; Options:
"Use AutoCAD Electrical attribute names in DXF"): a symbol's tag as TAG1, its maker as MFG, its
catalog number as CAT, its description as DESC1; a footprint's tag as P_TAG1. Off, KanzonasCAD's
own names as in 0.20. Either way the DXF reads back as the same symbols."""
import os
import tempfile
import unittest

import ezdxf

from tests.util import APP, window

from kanzonascad import fileio
from kanzonascad import model as M


class AceNamesTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.s = self.v.sheet()
        lib = self.win.library
        d = lib.get("symbol", "Relay coil")
        fp = next(iter(lib.blocks("footprint")[0].values()))
        with self.p.edit("parts") as ed:
            ed.add(self.s, M.Insert(d.name, (3.0, 3.0), 0.0, 1.0, False,
                                    {"TAG": "CR1", "DESC": "Run relay", "MFR": "AB",
                                     "CAT": "700-HC"}, d, 0.1))
            ed.add(self.s, M.Insert(fp.name, (8.0, 3.0), 0.0, 1.0, False, {"TAG": "CR1"},
                                    fp, 0.1))
        self.path = os.path.join(tempfile.mkdtemp(), "x.dxf")

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def attribs(self, ace):
        fileio.export_dxf(self.p, self.s, self.path, include_frame=False, ace_names=ace)
        refs = list(ezdxf.readfile(self.path).modelspace().query("INSERT"))
        return [{a.dxf.tag: a.dxf.text for a in r.attribs} for r in refs]

    def test_ace_names(self):
        coil, fp = self.attribs(True)
        self.assertEqual((coil.get("TAG1"), coil.get("MFG"), coil.get("CAT"),
                          coil.get("DESC1")), ("CR1", "AB", "700-HC", "Run relay"))
        self.assertNotIn("TAG", coil)
        self.assertEqual(fp.get("P_TAG1"), "CR1")
        ents, _rep = fileio.read_dxf(self.path)
        back = sorted((e for e in ents if isinstance(e, M.Insert)), key=lambda e: e.pos[0])
        self.assertEqual([e.attrs.get("TAG") for e in back], ["CR1", "CR1"])
        self.assertEqual((back[0].attrs.get("MFR"), back[0].attrs.get("CAT")), ("AB", "700-HC"))
        self.assertEqual(back[0].defn.kind, "symbol")
        self.assertIsNotNone(back[0].defn.tag_pos)          # (its tag spot, from TAG1's)

    def test_wires_as_lines(self):
        # (the owner, in AutoCAD Electrical: "the wires are registering as poly lines and not
        # wires", so Scoot didn't move them: a wire is one LINE a straight run, on its layer)
        with self.p.edit("wire") as ed:
            ed.add(self.s, M.Wire([(1.0, 1.0), (4.0, 1.0), (4.0, 3.0)], layer="WIRES"))
        fileio.export_dxf(self.p, self.s, self.path, include_frame=False, ace_names=True)
        msp = ezdxf.readfile(self.path).modelspace()
        lines = [e for e in msp.query("LINE") if e.dxf.layer == "WIRES"]
        self.assertEqual(sorted((tuple(e.dxf.start)[:2], tuple(e.dxf.end)[:2]) for e in lines),
                         [((1.0, 1.0), (4.0, 1.0)), ((4.0, 1.0), (4.0, 3.0))])
        self.assertEqual([e for e in msp.query("LWPOLYLINE") if e.dxf.layer == "WIRES"], [])
        # (crossing wires: whole, not cut at a jump, with no loop drawn on their layer)
        with self.p.edit("cross") as ed:
            ed.project_settings({"wire_crossing": "loop"})
            ed.add(self.s, M.Wire([(2.0, 0.0), (2.0, 2.0)], layer="WIRES"))
        fileio.export_dxf(self.p, self.s, self.path, include_frame=False, ace_names=True)
        msp = ezdxf.readfile(self.path).modelspace()
        down = [e for e in msp.query("LINE") if e.dxf.layer == "WIRES" and
                abs(e.dxf.start[0] - 2.0) < 1e-9 and abs(e.dxf.end[0] - 2.0) < 1e-9]
        self.assertEqual(len(down), 1)
        self.assertAlmostEqual(abs(down[0].dxf.end[1] - down[0].dxf.start[1]), 2.0)
        self.assertEqual([e for e in msp.query("LWPOLYLINE") if e.dxf.layer == "WIRES"], [])
        # (KanzonasCAD's own names: a wire stays one polyline, as before)
        fileio.export_dxf(self.p, self.s, self.path, include_frame=False)
        msp = ezdxf.readfile(self.path).modelspace()
        self.assertGreaterEqual(len([e for e in msp.query("LWPOLYLINE")
                                     if e.dxf.layer == "WIRES"]), 2)   # (cut where it jumps)

    def test_pins_as_wire_connections(self):
        # (the owner, in AutoCAD Electrical's block editor: "the pins have a pretext of kz on all
        # of them"; its wire connections are X?TERMnn, ? the side a wire comes from: 1 right,
        # 2 top, 4 left, 8 bottom, with TERMnn the pin's label)
        fileio.export_dxf(self.p, self.s, self.path, include_frame=False, ace_names=True)
        doc = ezdxf.readfile(self.path)
        coil = doc.blocks.get("Relay coil")
        tags = {a.dxf.tag: a.dxf.text for a in coil.query("ATTDEF")}
        self.assertFalse(any(t.startswith("KZPIN") for t in tags))
        d = self.win.library.get("symbol", "Relay coil")
        for i, pin in enumerate(d.pins):
            side = fileio.pin_side(d, pin["pos"])
            self.assertIn("X%dTERM%02d" % (side, i + 1), tags)
            self.assertEqual(tags["TERM%02d" % (i + 1)], pin["name"])
        sides = sorted(fileio.pin_side(d, q["pos"]) for q in d.pins)
        self.assertEqual(sides, [1, 4])     # (a coil: A1 on the left, A2 on the right)
        ref = next(r for r in doc.modelspace().query("INSERT") if r.dxf.name == "Relay coil")
        self.assertIn("TERM01", {a.dxf.tag for a in ref.attribs})
        # (read back: the same pins, where they were, and no TERM attributes on it)
        ents, _rep = fileio.read_dxf(self.path)
        back = next(e for e in ents if isinstance(e, M.Insert) and e.block == "Relay coil")
        mine = next(e for e in self.s.inserts() if e.block == "Relay coil")
        self.assertEqual(sorted(back.pin_points()), sorted(mine.pin_points()))
        self.assertFalse([k for k in back.attrs if "TERM" in k])

    def test_own_names_by_default(self):
        coil, fp = self.attribs(False)
        self.assertEqual((coil.get("TAG"), coil.get("MFR")), ("CR1", "AB"))
        self.assertNotIn("TAG1", coil)
        self.assertEqual(fp.get("TAG"), "CR1")


if __name__ == "__main__":
    unittest.main()
