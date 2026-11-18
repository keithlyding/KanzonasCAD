"""Source and destination arrows (the owner, 0.18.4): "for source/destination nomenclature, I
don't want all locations; just the source and destination for that specific wire location";
"I have to type in the wire name for source symbols. That should intuitively grab the wire
number of what I attach it to"; "if I add a destination arrow, not only should the wire
number change, but it's layer needs to match the source layer as well"."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wirelayers
from kanzonascad import wirenums
from kanzonascad import xrefs


class ArrowTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.lib = self.win.library
        with self.p.edit("sheets") as ed:
            wirelayers.add_preset(ed, self.p, ["480 V"])
            ed.add_sheet(self.p.make_sheet("Two"))
            ed.add_sheet(self.p.make_sheet("Three"))
        self.s1, self.s2, self.s3 = self.p.sheets
        with self.p.edit("w") as ed:
            self.a = ed.add(self.s1, M.Wire([(2.0, 5.0), (6.0, 5.0)], layer="480V BRN"))
            self.b = ed.add(self.s2, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
            self.c = ed.add(self.s3, M.Wire([(2.0, 5.0), (6.0, 5.0)]))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def place(self, sheet, name, at, angle_keys=(), answer=None):
        self.v.show_sheet(sheet.id)
        self.v.run(C.InsertCmd, self.lib.get("symbol", name), {})
        for k in angle_keys:
            type_in(self.v, k)
        type_in(self.v, "%g,%g" % at)
        if self.v.cmd is not None and answer is not None:
            type_in(self.v, answer)
        return [e for e in sheet.inserts() if e.defn.name == name][-1]

    def test_source_named_by_its_wire_destination_takes_layer_and_number(self):
        num = self.s1.entities[self.a.id].num
        src = self.place(self.s1, "Source arrow", (6.0, 5.0))
        self.assertIsNone(self.v.cmd)                       # (nothing to type)
        self.assertEqual(src.attrs["TAG"], num)
        dst = self.place(self.s2, "Destination arrow", (2.0, 5.0), answer="")
        self.assertEqual(dst.attrs["TAG"], num)
        b = self.s2.entities[self.b.id]
        self.assertEqual(b.layer, "480V BRN")               # (the source's layer)
        self.assertEqual(b.num, num)                        # (and its number)
        self.p.undo()
        self.assertEqual(self.s2.entities[self.b.id].layer, "WIRES")

    def test_each_arrow_shows_only_its_other_half(self):
        num = self.s1.entities[self.a.id].num
        self.place(self.s1, "Source arrow", (6.0, 5.0))
        self.place(self.s2, "Destination arrow", (2.0, 5.0), answer=num)
        self.place(self.s3, "Destination arrow", (2.0, 5.0), answer=num)
        where = {s.id: self.p.zone_text(s, 4.0, 5.0).split("-")[0] for s in self.p.sheets}

        def text(sheet):
            return [t for x, y, t, *_r in xrefs.live(self.p, sheet) if "/" in t][0]
        t2, t3 = text(self.s2), text(self.s3)
        # (a destination: the source's place only, not the other destination's)
        self.assertNotIn(self.p.sheet_number(self.s3) + "-", t2.split("/")[1])
        self.assertIn(self.p.sheet_number(self.s1) + "-", t2.split("/")[1])
        self.assertNotIn(self.p.sheet_number(self.s2) + "-", t3.split("/")[1])
        # (the source: both its destinations)
        t1 = text(self.s1)
        for s in (self.s2, self.s3):
            self.assertIn(self.p.sheet_number(s) + "-", t1)
        self.assertTrue(where)

    def test_sigarrow_matches_the_layer(self):
        self.v.show_sheet(self.s1.id)
        self.v.run(C.SignalArrowsCmd)
        self.v.cmd.pick((5.9, 5.0))
        self.v.show_sheet(self.s2.id)
        self.v.cmd.pick((2.1, 5.0))
        self.v.cmd.enter()
        self.assertEqual(self.s2.entities[self.b.id].layer, "480V BRN")

    def test_a_number_a_source_has_asks(self):
        num = self.s1.entities[self.a.id].num
        self.place(self.s1, "Source arrow", (6.0, 5.0))
        # (a second source on a wire of that number: named as before, asked)
        with self.p.edit("w") as ed:
            w = ed.add(self.s3, M.Wire([(8.0, 2.0), (8.0, 4.0)]))
            ed.change(self.s3, w.copy(num=num, num_lock=True))
        self.v.show_sheet(self.s3.id)
        self.v.run(C.InsertCmd, self.lib.get("symbol", "Source arrow"), {})
        type_in(self.v, "8,4")
        self.assertIsNotNone(self.v.cmd)                    # (asking its name)
        self.v.cancel()


if __name__ == "__main__":
    unittest.main()
