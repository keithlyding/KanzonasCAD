"""Contact blocks of a pushbutton or selector switch, and the dashed line joining those stacked
in its column (the owner, 0.19.10: "Can you add secondary contacts like that EStop in the
pic?", his print's mushroom head 205PPL13 over two NC blocks and an NO one; asked: drawn by
itself when stacked; pushbutton and selector switch blocks)."""
import os
import tempfile
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import fileio
from kanzonascad import model as M
from kanzonascad import tags
from kanzonascad import xrefs


class ContactBlocksTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.s = self.v.sheet()
        self.lib = self.win.library

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def place(self, name, at, attrs=None):
        before = set(self.s.entities)
        self.v.run(C.InsertCmd, self.lib.get("symbol", name), dict(attrs or {}))
        type_in(self.v, "%g,%g" % at)
        while self.v.cmd is not None:
            type_in(self.v, "")
        return [e for i, e in self.s.entities.items() if i not in before and
                isinstance(e, M.Insert)][0]

    def link(self, block, parent):
        with self.p.edit("belongs") as ed:
            ed.change(self.s, block.copy(attrs=tags.link_attrs(dict(block.attrs), parent)))
        return self.s.entities[block.id]

    def stack(self):
        """The owner's E-stop: its own NC contact, then an NC and an NO block below it."""
        es = self.place("Emergency stop NC", (5.0, 8.0))
        nc = self.link(self.place("Pushbutton contact NC", (5.0, 7.0)), es)
        no = self.link(self.place("Pushbutton contact NO", (5.0, 6.0)), es)
        return self.s.entities[es.id], nc, no

    def test_the_blocks_are_in_the_library(self):
        for name, contact, prefix in (("Pushbutton contact NO", "NO", "PB"),
                                      ("Pushbutton contact NC", "NC", "PB"),
                                      ("Selector switch contact NO", "NO", "SS"),
                                      ("Selector switch contact NC", "NC", "SS")):
            d = self.lib.get("symbol", name)
            self.assertIsNotNone(d, name)
            self.assertEqual((d.role, d.contact, d.prefix), ("child", contact, prefix))

    def test_stacked_blocks_take_the_tag_and_are_joined(self):
        es, nc, no = self.stack()
        self.assertEqual(nc.attrs.get("TAG"), es.attrs.get("TAG"))
        self.assertEqual(no.attrs.get("TAG"), es.attrs.get("TAG"))
        x = es.pos[0]                                       # (its stem: the line's column)
        self.assertEqual(xrefs.links(self.p, self.s), [((x, 6.0), (x, 8.0))])
        # (no cross-references for them, nor listed under the E-stop: the line shows it, as
        # in the owner's print)
        self.assertEqual(xrefs.live(self.p, self.s), [])
        # (moved out of the column: listed, and its own reference back)
        with self.p.edit("aside") as ed:
            ed.change(self.s, no.moved(3.0, 0.0))
        texts = [t for _x, _y, t, *_r in xrefs.live(self.p, self.s)]
        self.assertTrue(any(t.startswith("NO ") for t in texts), texts)
        self.assertEqual(len(texts), 2, texts)

    def test_the_line_follows_a_moved_block_and_leaves_with_it(self):
        es, nc, no = self.stack()
        x = es.pos[0]
        with self.p.edit("down") as ed:
            ed.change(self.s, no.moved(0.0, -2.0))
        self.assertEqual(xrefs.links(self.p, self.s), [((x, 4.0), (x, 8.0))])
        with self.p.edit("aside") as ed:                    # (out of the column: not joined)
            ed.change(self.s, self.s.entities[no.id].moved(3.0, 0.0))
        self.assertEqual(xrefs.links(self.p, self.s), [((x, 7.0), (x, 8.0))])
        self.p.undo()
        self.assertEqual(xrefs.links(self.p, self.s), [((x, 4.0), (x, 8.0))])

    def test_relay_contacts_are_not_joined(self):
        coil = self.place("Relay coil", (5.0, 8.0))
        self.link(self.place("Contact NO", (5.0, 7.0)), coil)
        self.assertEqual(xrefs.links(self.p, self.s), [])

    def test_in_the_dxf_as_dashes(self):
        x = self.stack()[0].pos[0]
        fd, path = tempfile.mkstemp(suffix=".dxf")
        os.close(fd)
        try:
            fileio.export_dxf(self.p, self.s, path, include_frame=False)
            import ezdxf
            doc = ezdxf.readfile(path)
            on_col = [e for e in doc.modelspace().query("LINE")
                      if abs(e.dxf.start.x - x) < 1e-6 and abs(e.dxf.end.x - x) < 1e-6 and
                      6.0 - 1e-6 <= min(e.dxf.start.y, e.dxf.end.y) and
                      max(e.dxf.start.y, e.dxf.end.y) <= 8.0 + 1e-6]
        finally:
            os.remove(path)
        self.assertGreaterEqual(len(on_col), 10)            # (2 inches of 1/16 dashes)


if __name__ == "__main__":
    unittest.main()
