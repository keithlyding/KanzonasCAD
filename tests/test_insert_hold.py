"""Insert holds a symbol by its first pin (the owner: "When inserting symbols, it's defaulting
to center but it needs to default to connection... I added in a 3ph disconnect and am trying
to add a 3 ph fuse, but I'm grabbing the fuse in the center, which makes it connect to 3ph
disconnect at the center of the fuses"): the point picked is where that pin lands, turned and
flipped too; B holds it by the next pin, then the block's own base point. Footprints and
blocks without pins are placed by their base point as before."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class InsertHoldTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.lib = self.win.library

    def tearDown(self):
        p = self.v.project
        p.saved_at = len(p.undo_stack)
        self.win.close()

    def insert(self, name, at, keys=(), kind="symbol"):
        v = self.v
        before = set(v.sheet().entities)
        v.run(C.InsertCmd, self.lib.get(kind, name), {})
        for k in keys:
            self.assertTrue(v.input_text(k), k)
        type_in(v, "%r,%r" % at)
        while v.cmd is not None:            # (a contact's "Belongs to": Enter)
            v.cmd.enter()
        new = [e for i, e in v.sheet().entities.items() if i not in before and
               isinstance(e, M.Insert)]
        self.assertEqual(len(new), 1)
        return new[0]

    def test_three_pole_fuses_join_the_disconnect_on_every_pole(self):
        ds = self.insert("Disconnect 3-pole", (4.0, 6.0))
        self.assertEqual(dict(ds.pin_points())["L1"], (4.0, 6.0))
        fu = self.insert("Fuses 3-pole", dict(ds.pin_points())["T1"])
        d, f = dict(ds.pin_points()), dict(fu.pin_points())
        for a, b in (("T1", "L1"), ("T2", "L2"), ("T3", "L3")):
            self.assertEqual(d[a], f[b])
        # ...and the contactor after the fuses, the overloads after it
        ct = self.insert("Contactor power contacts 3-pole", f["T1"])
        ol = self.insert("Overload heaters 3-pole", dict(ct.pin_points())["T1"])
        c, o = dict(ct.pin_points()), dict(ol.pin_points())
        for a, b in (("T1", "L1"), ("T2", "L2"), ("T3", "L3")):
            self.assertEqual(c[a], o[b])

    def test_every_symbol_with_pins_lands_its_first_pin_turned_and_flipped(self):
        names = [n for n, d in self.lib.blocks("symbol")[0].items() if d.pins]
        self.assertGreater(len(names), 20)
        for n in names:
            for keys in ((), ("R",), ("R", "R", "F"), ("F", "R", "R", "R")):
                at = (3.0 + len(keys), 4.0)
                e = self.insert(n, at, keys)
                first = e.defn.pins[0]["name"]
                self.assertEqual(dict(e.pin_points())[first], at, "%s %s" % (n, keys))

    def test_b_holds_it_by_the_next_pin_then_its_base_point(self):
        e = self.insert("Contact NO", (5.0, 5.0), ["B"])
        self.assertEqual(dict(e.pin_points())["2"], (5.0, 5.0))
        e = self.insert("Contact NO", (7.0, 5.0), ["B", "B"])
        self.assertEqual(e.pos, (7.0, 5.0))                  # (its own base point)
        e = self.insert("Contact NO", (9.0, 5.0), ["B", "B", "B"])
        self.assertEqual(dict(e.pin_points())["1"], (9.0, 5.0))   # (round to the first)

    def test_the_preview_is_where_it_will_land(self):
        v = self.v
        v.run(C.InsertCmd, self.lib.get("symbol", "Fuses 3-pole"), {})
        shown = v.cmd.preview((2.0, 3.0))[0]
        self.assertEqual(dict(shown.pin_points())["L1"], (2.0, 3.0))
        v.cancel()

    def test_a_footprint_keeps_its_base_point(self):
        fps = [n for n, d in self.lib.blocks("footprint")[0].items() if not d.pins]
        if not fps:
            self.skipTest("no footprint in the library")
        e = self.insert(fps[0], (10.0, 10.0), kind="footprint")
        self.assertEqual(e.pos, (10.0, 10.0))


if __name__ == "__main__":
    unittest.main()
