"""A symbol turned 45 degrees, moved, can stop with a pin a hair from a wire passing across it
(the long battery, seed 5052 at step 1697: a drive's terminal 02 and the wire on it 0.0089"
under a wire running across the drive's row of pins). The wire end is on its pin, joined as
drawn; the passing wire is not joined to it (that would wire two circuits together). The
program marks the spot red on the drawing and says so on the command line (the owner, Nov 26
2026: "Warn on the drawing"), until it is moved away or joined; an exact join is not marked."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import dupes
from kanzonascad import geometry as G
from kanzonascad import model as M
from kanzonascad import nearmiss
from tests import battery_checks as BC


class TurnedPinNearWireTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        self.s, self.p = v.sheet(), v.project

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def coil(self, angle):
        """A relay coil at (5, 5) turned by angle, a wire from its first pin to the right,
        and a wire straight across 0.0089" + 0.5 above that pin (so 0.0089" above once the
        coil is moved down 0.5); returns (coil, its wire, the passing wire)."""
        before = set(self.s.entities)
        self.v.run(C.InsertCmd, self.win.library.get("symbol", "Relay coil"), {})
        type_in(self.v, "5,5")
        while self.v.cmd is not None:
            self.v.cmd.enter()
        ins = [e for i, e in self.s.entities.items() if i not in before and
               isinstance(e, M.Insert)][0]
        with self.p.edit("turn") as ed:
            ins = ed.change(self.s, ins.copy(angle=angle))
        q = ins.pin_points()[0][1]
        with self.p.edit("wires") as ed:
            w = ed.add(self.s, M.Wire([q, (q[0] + 3.0, q[1])]))
            y = q[1] - 0.5 + 0.0089
            across = ed.add(self.s, M.Wire([(q[0] - 2.0, y), (q[0] + 2.0, y)]))
        return ins, w, across

    def move_down(self, ins):
        self.v.set_selection({ins.id})
        self.v.run(C.MoveCmd)
        type_in(self.v, "%r,%r" % ins.pos, "@0,-0.5")
        self.assertIsNone(self.v.cmd)

    def said(self):
        got = []
        self.win._say = lambda msg, ms=6000: got.append(msg)
        return got

    def marked(self, p):
        return any(x0 < p[0] < x1 and y0 < p[1] < y1
                   for x0, y0, x1, y1 in dupes.marks(self.p, self.s))

    def test_turned_symbol(self):
        _ins, w, _across = self.flagged()
        self.assertEqual([k for k in nearmiss.found_keyed(self.s) if k[0] == "end"],
                         [("end", w.id, 0)])

    def flagged(self):
        """The turned coil moved down, its pin's near miss flagged: (coil, wire, passing)."""
        ins, w, across = self.coil(45.0)
        said = self.said()
        self.win._project_changed(self.win.doc())
        self.move_down(ins)
        self.win._project_changed(self.win.doc())
        q = dict(self.s.entities[ins.id].pin_points())
        end = self.s.entities[w.id].points[0]
        self.assertTrue(any(G.dist(end, p) <= 1e-9 for p in q.values()),
                        "the wire left its pin")
        self.assertEqual(self.s.entities[across.id].points, across.points,
                         "the passing wire was changed (joined to the pin?)")
        self.assertAlmostEqual(abs(end[1] - across.points[0][1]), 0.0089, places=6)
        # (flagged: one spot, the wire end and the pin under it; marked and said)
        got = nearmiss.found(self.s)
        self.assertEqual(len(got), 1, got)
        self.assertLessEqual(G.dist(got[0][0], end), 1e-9)
        self.assertAlmostEqual(got[0][2], 0.0089, places=6)
        self.assertTrue(self.marked(end))
        self.assertTrue(any("0.0089\" from a wire without joining it" in m and
                            "marked red on the drawing" in m for m in said), said)
        # (the battery's check finds it too, and accepts it only as it is marked)
        self.assertEqual({k[0] for k, _p, _k, _d in BC.near_misses(self.s)}, {"end", "pin"})
        self.assertEqual(BC.near_misses_unflagged(self.s), ([], [], []))
        # (said once, not on every change after)
        n = len(said)
        with self.p.edit("other") as ed:
            ed.add(self.s, M.Line((0, 0), (1, 1)))
        self.win._project_changed(self.win.doc())
        self.assertEqual(said[n:], [])
        return ins, w, across

    def test_moved_away_clears_it(self):
        ins, w, across = self.flagged()
        with self.p.edit("away") as ed:
            ed.change(self.s, self.s.entities[across.id].moved(0, 0.25))
        self.assertEqual(nearmiss.found(self.s), [])
        self.assertFalse(self.marked(self.s.entities[w.id].points[0]))
        self.assertEqual(BC.near_misses(self.s), [])
        self.p.undo()
        self.assertEqual(len(nearmiss.found(self.s)), 1)        # (back with Undo)

    def test_joined_clears_it(self):
        ins, w, across = self.flagged()
        end = self.s.entities[w.id].points[0]
        a = self.s.entities[across.id]
        with self.p.edit("onto") as ed:      # (the passing wire put through the pin)
            ed.change(self.s, a.copy(points=[(a.points[0][0], end[1]), (a.points[1][0], end[1])]))
        self.assertEqual(nearmiss.found(self.s), [])
        self.assertEqual(BC.near_misses_unflagged(self.s), ([], [], []))

    def test_upright_symbol(self):
        ins, w, across = self.coil(0.0)
        self.move_down(ins)
        near = BC.near_misses(self.s)
        self.assertEqual([(k[0], k[1]) for k, _p, kind, _d in near if k[0] == "end"],
                         [("end", w.id)])
        self.assertAlmostEqual(near[0][3], 0.0089, places=6)
        # (marked by the program, but on the grid: no turned symbol explains it, so the
        # battery still fails on it, as on the program's own slop)
        self.assertTrue(nearmiss.found(self.s))
        missed, odd, false = BC.near_misses_unflagged(self.s)
        self.assertEqual((missed, false), ([], []))
        self.assertEqual({k[0] for k, _p, _k, _d in odd}, {"end", "pin"})

    def test_upright_exact_join_not_flagged(self):
        ins, w, across = self.coil(0.0)
        with self.p.edit("onto") as ed:
            ed.change(self.s, self.s.entities[across.id].moved(0, -0.0089))
        self.move_down(ins)
        self.assertEqual(nearmiss.found(self.s), [])
        self.assertEqual(dupes.marks(self.p, self.s), [])
        self.assertEqual(BC.near_misses(self.s), [])


    def test_bare_pin_and_pin_to_pin(self):
        # (a pin with no wire on it, 0.0089" from a wire passing; then a second coil's pin
        # 0.005" from the first's: each marked, nothing joined)
        ins, w, across = self.coil(45.0)
        with self.p.edit("no wire") as ed:
            ed.remove(self.s, w.id)
        q = ins.pin_points()[0][1]
        with self.p.edit("past") as ed:
            ed.change(self.s, self.s.entities[across.id].moved(0, 0.5))
        got = nearmiss.found(self.s)
        self.assertEqual([(round(m[2], 6), m[3]) for m in got],
                         [(0.0089, "pin %s of %s" % (ins.pin_points()[0][0],
                                                    ins.attrs["TAG"]))])
        self.assertLessEqual(G.dist(got[0][0], q), 1e-9)
        self.assertTrue(self.marked(q))
        self.assertEqual(len(self.s.wires()), 1)
        with self.p.edit("gone") as ed:
            ed.remove(self.s, across.id)
        self.assertEqual(nearmiss.found(self.s), [])
        other = self.s.entities[ins.id].copy(id=None, pos=(ins.pos[0] + 0.005, ins.pos[1]),
                                             attrs=dict(ins.attrs, TAG="CR9"))
        with self.p.edit("beside") as ed:
            ed.add(self.s, other)
        got = nearmiss.found(self.s)
        self.assertTrue(got)
        self.assertTrue(all(abs(m[2] - 0.005) < 1e-9 for m in got), got)
        self.assertEqual(BC.near_misses_unflagged(self.s), ([], [], []))


if __name__ == "__main__":
    unittest.main()
