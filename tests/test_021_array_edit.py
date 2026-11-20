"""Editing an array (the owner, Nov 2026: "Yes I want to be able to edit an array"; asked: its
spacing usually; the copies stay linked; copies added take tags of their own and copies kept
keep theirs; wires on copies taken away stay where they are, unconnected): Array keeps what it
made as an array on its sheet; Edit array (ARRAYEDIT) asks its numbers again, Enter keeping each,
and moves, adds and erases copies to match; a copy edited on its own has left the array; U
unlinks it. Saved with the sheet, one Undo each."""
import os
import tempfile
import unittest

from tests.util import APP, window, type_in

from kanzonascad import arrays
from kanzonascad import commands as C
from kanzonascad import geometry as G
from kanzonascad import model as M


class ArrayEditTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.s = self.v.sheet()
        self.said = []
        self.v.message = lambda text: self.said.append(text)
        d = self.win.library.get("symbol", "Relay coil")
        with self.p.edit("coil") as ed:
            self.coil = ed.add(self.s, M.Insert(d.name, (2.0, 2.0), 0.0, 1.0, False,
                                                {"TAG": "CR1"}, d, 0.1))
            self.line = ed.add(self.s, M.Line((1.0, 1.0), (3.0, 1.0)))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def make(self, rows=1, cols=3, dr=0.0, dc=2.0):
        self.v.set_selection({self.coil.id, self.line.id})
        self.v.run(C.ArrayCmd)
        type_in(self.v, "R", str(rows), str(cols), str(dr), str(dc))
        return next(iter(self.s.arrays))

    def coils(self):
        return sorted((e for e in self.s.inserts()), key=lambda e: e.pos[0])

    def edit(self, *answers):
        self.v.set_selection({self.coils()[-1].id})
        self.v.run(C.ArrayEditCmd)
        for a in answers:
            if a is None:
                self.v.enter()
            else:
                self.v.input_text(a)

    def test_spacing_changed_tags_kept(self):
        self.make()
        before = {e.attrs["TAG"]: e.pos for e in self.coils()}
        self.assertEqual(len(before), 3)
        self.edit(None, None, None, "3")                # (only the column spacing: 3")
        got = self.coils()
        self.assertEqual([e.pos[0] for e in got], [2.0, 5.0, 8.0])
        self.assertEqual(sorted(e.attrs["TAG"] for e in got), sorted(before))
        lines = sorted(e.p1[0] for e in self.s.entities.values() if isinstance(e, M.Line))
        self.assertEqual(lines, [1.0, 4.0, 7.0])
        self.p.undo()
        self.assertEqual(sorted(e.pos[0] for e in self.coils()), [2.0, 4.0, 6.0])

    def test_more_and_fewer(self):
        self.make()
        tags = {e.attrs["TAG"] for e in self.coils()}
        self.edit(None, "5", None, None)
        got = self.coils()
        self.assertEqual([e.pos[0] for e in got], [2.0, 4.0, 6.0, 8.0, 10.0])
        self.assertTrue(tags <= {e.attrs["TAG"] for e in got})
        self.assertEqual(len({e.attrs["TAG"] for e in got}), 5)        # (new ones: their own)
        # (fewer: those past the count go, a wire on one stays where it is)
        last = got[-1]
        with self.p.edit("wire") as ed:
            ed.add(self.s, M.Wire([dict(last.pin_points())["A2"], (12.0, 2.0)]))
        self.edit(None, "2", None, None)
        self.assertEqual([e.pos[0] for e in self.coils()], [2.0, 4.0])
        self.assertEqual(len(self.s.wires()), 1)
        self.assertTrue(any("erased" in t for t in self.said))

    def test_a_copy_moved_on_its_own_leaves_it(self):
        aid = self.make()
        mid = self.coils()[1]
        with self.p.edit("move") as ed:
            ed.change(self.s, mid.moved(0.0, 3.0))
        self.assertNotIn(mid.id, [j for ids in arrays.members(self.s, aid).values()
                                  for j in ids])
        self.edit(None, None, None, "3")
        pos = {e.id: e.pos for e in self.coils()}
        self.assertEqual(pos[mid.id], (4.0, 5.0))                       # (left alone)
        self.assertEqual(sorted(x for x, _y in pos.values()), [2.0, 4.0, 8.0])

    def test_unlink_and_saved(self):
        aid = self.make()
        path = os.path.join(tempfile.mkdtemp(), "a.kzcad")
        self.p.save(path, backups=0)
        q = M.Project.load(path)
        self.assertEqual(q.sheets[0].arrays, self.s.arrays)
        self.assertEqual(arrays.find(q.sheets[0], self.coils()[2].id), aid)
        self.v.set_selection({self.coils()[1].id})
        self.v.run(C.ArrayEditCmd)
        self.v.input_text("U")
        self.assertEqual(self.s.arrays, {})
        self.assertEqual(len(self.coils()), 3)
        self.v.set_selection({self.coils()[1].id})
        self.v.run(C.ArrayEditCmd)
        self.assertTrue(any("select an object of an array" in t for t in self.said))

    def test_polar(self):
        self.v.set_selection({self.line.id})
        self.v.run(C.ArrayCmd)
        type_in(self.v, "P", "5,1", "4", "360")
        lines = [e for e in self.s.entities.values() if isinstance(e, M.Line)]
        self.assertEqual(len(lines), 4)
        self.v.set_selection({lines[1].id})
        self.v.run(C.ArrayEditCmd)
        self.v.input_text("8")
        self.v.enter()
        lines = [e for e in self.s.entities.values() if isinstance(e, M.Line)]
        self.assertEqual(len(lines), 8)
        for e in lines:
            self.assertAlmostEqual(G.dist(e.p1, (5.0, 1.0)), 4.0)


if __name__ == "__main__":
    unittest.main()
