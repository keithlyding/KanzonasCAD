"""A flipped symbol's own texts in DXF export (0.20's known gap): AutoCAD draws the texts of a
block flipped with it (its MIRRTEXT doesn't reach inside blocks), so the "TR" of a flipped timer
coil read backwards in AutoCAD, while KanzonasCAD draws it readable. A block placed flipped
somewhere now carries its texts as locked attributes (KZTEXT1...), placed readable on each
copy where the program draws them, and they read back as the block's own texts."""
import os
import tempfile
import unittest

import ezdxf

from tests.util import APP, window

from kanzonascad import fileio
from kanzonascad import model as M

PARTS = [("Timer coil", (3.0, 8.0), 0.0, True, "TR1"),
         ("Timer coil", (3.0, 5.0), 0.0, False, "TR2"),
         ("Timer coil", (8.0, 5.0), 90.0, True, "TR3"),
         ("Motor 3-phase", (12.0, 6.0), 270.0, True, "M1"),
         ("Motor", (16.0, 6.0), 0.0, False, "M2")]


def _reads_mirrored(t):
    """Does AutoCAD draw this TEXT, ATTDEF or ATTRIB mirror-written?"""
    ext = t.dxf.get("extrusion", (0.0, 0.0, 1.0))
    flags = t.dxf.get("text_generation_flag", 0)
    return (ext[2] < 0) ^ bool(flags & 2) ^ bool(flags & 4)


def _upright(angle):
    return not (90.0 + 1e-6 < angle % 360.0 <= 270.0 + 1e-6)


class MirroredTextTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.s = self.v.sheet()
        lib = self.win.library
        with self.p.edit("parts") as ed:
            for name, pos, ang, mir, tag in PARTS:
                ed.add(self.s, M.Insert(name, pos, ang, 1.0, mir, {"TAG": tag},
                                        lib.get("symbol", name), 0.1))
        self.ins = list(self.s.inserts())
        self.path = os.path.join(tempfile.mkdtemp(), "x.dxf")
        fileio.export_dxf(self.p, self.s, self.path, include_frame=False)
        self.doc = ezdxf.readfile(self.path)
        self.refs = list(self.doc.modelspace().query("INSERT"))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def drawn(self, ref):
        """The texts AutoCAD shows on a copy: its block's TEXTs and its own ATTRIBs (the
        KZTEXT ones), as (text, x, y, angle, mirrored)."""
        out = [(t.dxf.text, t.dxf.insert[0], t.dxf.insert[1], t.dxf.rotation,
                _reads_mirrored(t))
               for t in ref.virtual_entities() if t.dxftype() == "TEXT"]
        for a in ref.attribs:
            if a.dxf.tag.startswith(fileio.TEXT_TAG):
                p, _al, _va, rot = fileio._text_place(a)
                out.append((a.dxf.text, p[0], p[1], rot, _reads_mirrored(a)))
        return out

    def test_every_copy_reads_as_drawn(self):
        for ins, ref in zip(self.ins, self.refs):
            got = self.drawn(ref)
            mine = fileio._placed_texts(ins)
            self.assertEqual(sorted(g[0] for g in got), sorted(t.text for t in mine),
                             msg=ins.attrs["TAG"])
            for g in got:
                self.assertFalse(g[4], msg="%s: %r reads mirrored" % (ins.attrs["TAG"], g[0]))
                self.assertTrue(_upright(g[3]), msg="%s: %r upside down" % (
                    ins.attrs["TAG"], g[0]))
            if ins.defn.name in ("Timer coil", "Motor 3-phase"):
                # (a flipped block's: where and how the program draws them)
                kz = sorted((a for a in ref.attribs if a.dxf.tag.startswith(fileio.TEXT_TAG)),
                            key=lambda a: a.dxf.tag)
                for a, t in zip(kz, mine):
                    p, al, va, rot = fileio._text_place(a)
                    self.assertAlmostEqual(p[0], t.pos[0], places=9)
                    self.assertAlmostEqual(p[1], t.pos[1], places=9)
                    self.assertAlmostEqual(rot % 360.0, t.angle % 360.0, places=9)
                    self.assertEqual((al, va), (t.align, t.valign))
                    self.assertTrue(a.dxf.lock_position)

    def test_only_flipped_blocks_change(self):
        kinds = {b.name: [e.dxftype() for e in b] for b in self.doc.blocks
                 if b.name in ("Timer coil", "Motor 3-phase", "Motor")}
        self.assertNotIn("TEXT", kinds["Timer coil"])
        self.assertNotIn("TEXT", kinds["Motor 3-phase"])
        self.assertIn("TEXT", kinds["Motor"])                 # (never flipped: as before)
        attdefs = [e for e in self.doc.blocks.get("Timer coil") if e.dxftype() == "ATTDEF"]
        kz = [a for a in attdefs if a.dxf.tag.startswith(fileio.TEXT_TAG)]
        self.assertEqual([(a.dxf.tag, a.dxf.text) for a in kz], [("KZTEXT1", "TR")])
        self.assertFalse(kz[0].is_const or kz[0].is_invisible)

    def test_reads_back_as_the_same_symbols(self):
        ents, _rep = fileio.read_dxf(self.path)
        got = {e.attrs.get("TAG"): e for e in ents if isinstance(e, M.Insert)}
        for ins in self.ins:
            back = got[ins.attrs["TAG"]]
            self.assertEqual(back.block, ins.block)
            self.assertEqual(bool(back.mirror), bool(ins.mirror))
            self.assertFalse(any(k.startswith(fileio.TEXT_TAG) for k in back.attrs))
            self.assertEqual([t.text for t in fileio._block_texts(back.defn)],
                             [t.text for t in fileio._block_texts(ins.defn)])
            for a, b in zip(fileio._placed_texts(back), fileio._placed_texts(ins)):
                self.assertAlmostEqual(a.pos[0], b.pos[0], places=6)
                self.assertAlmostEqual(a.pos[1], b.pos[1], places=6)
                self.assertAlmostEqual(a.angle % 360.0, b.angle % 360.0, places=6)
        # (no stray texts beside them: the KZTEXT attributes were their own drawing's)
        self.assertFalse([t for t in ents if isinstance(t, M.Text) and t.text in ("TR", "MTR")])


if __name__ == "__main__":
    unittest.main()
