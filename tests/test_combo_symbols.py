"""Two devices in one symbol (the owner, 0.16.2: "Please add 3ph disconnect with fuses and
3phase starter with overloads as symbols"): Fused disconnect 3-pole and Starter 3-pole. They
join the other three-pole symbols pole for pole, their tags line up with theirs, the fused
disconnect shows its rating in each fuse, and the starter is a contact of its Contactor coil
(its tag, listed under the coil)."""
import unittest

from tests.util import APP, window, type_in, NEAREST

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import symbols_jic as J
from kanzonascad import xrefs


class ComboSymbolsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.lib = self.win.library
        self.p = self.v.project

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def insert(self, name, at):
        before = set(self.v.sheet().entities)
        self.v.run(C.InsertCmd, self.lib.get("symbol", name), {})
        type_in(self.v, "%r,%r" % at)
        if self.v.cmd is not None and self.v.cmd.cands:     # (a contact's "Belongs to":
            type_in(self.v, NEAREST)                        # the nearest offered)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        return [e for i, e in self.v.sheet().entities.items()
                if i not in before and isinstance(e, M.Insert)][0]

    def test_in_the_library(self):
        for n in ("Fused disconnect 3-pole", "Starter 3-pole"):
            d = self.lib.get("symbol", n)
            self.assertIsNotNone(d, n)
            self.assertEqual([q["name"] for q in d.pins],
                             ["L1", "L2", "L3", "T1", "T2", "T3"])
            ys = [q["pos"][1] for q in d.pins]
            self.assertEqual(ys, list(J.POLES) * 2)

    def test_a_feeder_in_a_row(self):
        coil = self.insert("Contactor coil", (3.0, 3.0))
        ds = self.insert("Fused disconnect 3-pole", (2.0, 8.0))
        st = self.insert("Starter 3-pole", dict(ds.pin_points())["T1"])
        mt = self.insert("Motor 3-phase", dict(st.pin_points())["T1"])
        s = self.v.sheet()
        ds, st, mt = (s.entities[e.id] for e in (ds, st, mt))
        d, t, m = dict(ds.pin_points()), dict(st.pin_points()), dict(mt.pin_points())
        for i in "123":
            self.assertEqual(d["T" + i], t["L" + i])
            self.assertEqual(t["T" + i], m["T" + i])
        # one tag height, clear of each drawing
        self.assertEqual(len({round(e.tag_text().pos[1], 9) for e in (ds, st, mt)}), 1)
        for e in (ds, st):
            top = e.pos[1] + max(q.bbox()[3] for q in e.defn.entities)
            self.assertGreater(e.tag_text().pos[1], top)
        # the starter is a device of its own (the owner, 0.17: parents shouldn't try to be
        # children): a tag of its own, not the coil's, and listed under nothing
        coil = s.entities[coil.id]
        self.assertIsNone(st.attrs.get("PARENT"))
        self.assertTrue(st.attrs["TAG"].startswith("M"))
        self.assertNotEqual(st.attrs["TAG"], coil.attrs["TAG"])
        self.assertTrue(ds.attrs["TAG"].startswith("DS"))
        under = [t for t in xrefs.live(self.p, s) if t[2].startswith("NO ")]
        self.assertEqual(under, [])

    def test_the_fuse_rating_shows_in_each_fuse(self):
        ds = self.insert("Fused disconnect 3-pole", (2.0, 8.0))
        d = ds.defn
        spots = [a for a in d.attr_texts if a["attr"] == "RATING"]
        self.assertEqual(len(spots), 3)
        boxes = [q.bbox() for q in d.entities if isinstance(q, M.Polyline) and q.closed]
        self.assertEqual(len(boxes), 3)
        for a in spots:
            x, y = a["pos"]
            self.assertTrue(any(b[0] < x < b[2] and b[1] < y < b[3] for b in boxes), a)

    def test_overload_heaters_are_two_hooks(self):
        # (the owner, with a photo of the heaters they want: two hooks of three quarters of
        # a turn, the first up and over from the wire in, the second round under to the wire
        # out; no dashed line through the middle pole's hooks)
        for n, poles, x0 in (("Overload heater", (0.0,), 0.0),
                             ("Overload heaters 3-pole", J.POLES, 0.0),
                             ("Starter 3-pole", J.POLES, 2 * J.PIN)):
            d = self.lib.get("symbol", n)
            for y in poles:
                arcs = sorted((q for q in d.entities if isinstance(q, M.Arc) and
                               abs(q.center[1] - y) < 1e-9), key=lambda q: q.center[0])
                self.assertEqual(len(arcs), 2, n)
                a, b = arcs
                self.assertEqual((a.start, a.end), (270.0, 180.0))
                self.assertEqual((b.start, b.end), (90.0, 0.0))
                # the wire in meets the first's left end, the wire out the second's right end
                left = (a.center[0] - a.radius, y)
                right = (b.center[0] + b.radius, y)
                ends = [q for q in d.entities if isinstance(q, M.Line)]
                self.assertTrue(any(left in (q.p1, q.p2) for q in ends), n)
                self.assertTrue(any(right in (q.p1, q.p2) for q in ends), n)
                # nothing crosses between the hooks
                for q in ends:
                    if abs(q.p1[0] - q.p2[0]) < 1e-9 and abs(q.p1[0] - x0) < 1e-9:
                        lo, hi = sorted((q.p1[1], q.p2[1]))
                        self.assertFalse(lo < y + J.HEATER_R and hi > y - J.HEATER_R,
                                         "%s: a line through the hooks at %s" % (n, y))


if __name__ == "__main__":
    unittest.main()
