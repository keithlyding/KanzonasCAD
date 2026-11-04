import os
import tempfile
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import crossings
from kanzonascad import model as M


class CrossingTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = False
        self.p = self.v.project
        self.s = self.v.sheet()
        with self.p.edit("wires") as ed:
            ed.add(self.s, M.Wire([(1, 5), (9, 5)]))           # across
            ed.add(self.s, M.Wire([(5, 2), (5, 8)]))           # up and down, crossing it
            ed.add(self.s, M.Wire([(9, 5), (9, 2)]))           # joined at an end: no crossing
            ed.add(self.s, M.Wire([(3, 5), (3, 3)]))           # a T (ends on the middle)

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def setting(self, **kw):
        with self.p.edit("setting") as ed:
            ed.project_settings(kw)

    def test_found_only_where_wires_pass_through_each_other(self):
        got = crossings.found(self.s)
        self.assertEqual([g[0] for g in got], [(5.0, 5.0)])
        p, seg, _o = got[0]
        self.assertEqual(seg, ((5.0, 2.0), (5.0, 8.0)))       # the vertical one jumps
        got = crossings.found(self.s, "horizontal")
        self.assertEqual(got[0][1], ((1.0, 5.0), (9.0, 5.0)))

    def test_style_setting(self):
        self.assertEqual(crossings.jumps(self.p, self.s), [])          # plain to start
        self.setting(wire_crossing="loop")
        j = crossings.jumps(self.p, self.s)
        self.assertEqual([(q, st) for q, _u, _c, st in j], [((5.0, 5.0), "loop")])
        self.setting(wire_crossing="gap")
        self.assertEqual(crossings.jumps(self.p, self.s)[0][3], "gap")
        self.v.repaint()                                               # (draws them)

    def test_by_hand(self):
        # hide the found one, add one where nothing crosses
        self.setting(wire_crossing="loop")
        self.v.run(C.WireCrossCmd)
        type_in(self.v, "N", "5.03,5.02", "L", "7,5")
        marks = [e for e in self.s.entities.values() if isinstance(e, M.WireCross)]
        self.assertEqual(sorted((m.pos, m.style) for m in marks),
                         [((5.0, 5.0), "none"), ((7.0, 5.0), "loop")])
        j = crossings.jumps(self.p, self.s)
        self.assertEqual([(q, st) for q, _u, cu, st in j], [((7.0, 5.0), "loop")])
        # nothing there: told, nothing added
        type_in(self.v, "12,9")
        self.assertEqual(len([e for e in self.s.entities.values()
                              if isinstance(e, M.WireCross)]), 2)
        # erased like any object; undo brings it back; saved
        m = [m for m in marks if m.style == "none"][0]
        with self.p.edit("erase") as ed:
            ed.remove(self.s, m.id)
        self.assertEqual(len(crossings.jumps(self.p, self.s)), 2)
        self.p.undo()
        again = M.Project.from_dict(self.p.to_dict())
        self.assertEqual(sum(isinstance(e, M.WireCross) for e in again.sheets[0].entities.values()),
                         2)

    def test_dxf_cuts_the_jumping_wire(self):
        import ezdxf
        from kanzonascad import fileio
        self.setting(wire_crossing="gap")
        path = os.path.join(tempfile.mkdtemp(), "x.dxf")
        fileio.export_dxf(self.p, self.s, path, include_frame=False)
        doc = ezdxf.readfile(path)
        vertical = [e for e in doc.modelspace().query("LWPOLYLINE")
                    if abs(e.get_points()[0][0] - 5.0) < 1e-6]
        self.assertEqual(len(vertical), 2)                 # cut in two at the gap
        r = crossings.size(self.s)
        ys = sorted(round(p[1], 4) for e in vertical for p in e.get_points())
        self.assertEqual(ys, [2.0, round(5 - r, 4), round(5 + r, 4), 8.0])


if __name__ == "__main__":
    unittest.main()
