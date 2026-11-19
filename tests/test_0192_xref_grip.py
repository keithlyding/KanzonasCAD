"""A contact's cross-reference (its device's place, 2-E6) can be dragged by its grip to a place
of its own, inside a big block say (the owner, 0.19.2, a drive's control-terminal block: "is
there a way to edit the location of the cross reference that appears? The object is large
enough that I could put it inside of it"); it then moves and turns with the block."""
import os
import tempfile
import unittest

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import xrefs


class XrefGripTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()
        lib = self.win.library
        vfd = lib.get("symbol", "Variable frequency drive")
        terms = lib.get("symbol", "Drive control terminals")
        with self.p.edit("x") as ed:
            ed.block(vfd)
            ed.block(terms)
            self.dev = ed.add(self.s, M.Insert(vfd.name, (5.0, 15.0),
                                               attrs={"TAG": "VFD201", "DEV": "d1"},
                                               defn=self.p.blocks[vfd.name]))
            self.c = ed.add(self.s, M.Insert(terms.name, (20.0, 15.0),
                                             attrs={"TAG": "VFD201", "PARENT": "d1"},
                                             defn=self.p.blocks[terms.name]))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def ref(self):
        """The contact's reference: the one nearest the contact (the drive's own listing of
        its contacts is by the drive)."""
        c = self.s.entities[self.c.id]
        bb = c.bbox()
        mid = ((bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0)
        return min(xrefs.live(self.p, self.s),
                   key=lambda t: (t[0] - mid[0]) ** 2 + (t[1] - mid[1]) ** 2)

    def test_dragged_inside_and_kept(self):
        c = self.s.entities[self.c.id]
        under = self.ref()
        names = [n for n, _q in c.text_grips()]
        self.assertIn("@XREF", names)
        i = 1 + names.index("@XREF")
        bb = c.bbox()
        inside = ((bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0)
        with self.p.edit("drag") as ed:
            ed.change(self.s, c.with_grip(i, inside))
        x, y = self.ref()[:2]
        self.assertAlmostEqual(x, inside[0], places=6)
        self.assertLess(abs(y - inside[1]), 0.1)
        self.assertNotEqual((x, y), under[:2])
        # moved with the block
        with self.p.edit("move") as ed:
            ed.change(self.s, self.s.entities[self.c.id].moved(3.0, -2.0))
        x2, y2 = self.ref()[:2]
        self.assertAlmostEqual(x2 - x, 3.0, places=6)
        self.assertAlmostEqual(y2 - y, -2.0, places=6)
        # saved and opened
        path = os.path.join(tempfile.mkdtemp(), "x.kzcad")
        self.p.save(path)
        q = M.Project.load(path)
        self.assertIn("@XREF", q.sheets[0].entities[self.c.id].attr_at)
        self.p.undo()
        self.p.undo()
        self.assertEqual(self.ref()[:2], under[:2])


if __name__ == "__main__":
    unittest.main()
