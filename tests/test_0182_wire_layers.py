"""Wire layers (the owner, 0.18.2: "I'll need a lot of different ones...480, 120, 24vdc,
Ethernet and others"; asked: 480 V black, red, orange, brown, yellow, a white neutral and a
green ground, 12 AWG; 120 V red, black, a white neutral, 14 AWG; 24 VDC blue and a blue with
white stripes common, 16 AWG; Ethernet green, a cable with no size; and a size per wire, the
layer's to start)."""
import os
import tempfile
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wirelayers
from kanzonascad import wirenums
from kanzonascad import wires


class WireLayerPresetTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.s = self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def add(self, groups=None):
        self.win.ask_wire_layer_groups = lambda: groups or wirelayers.preset_groups()
        self.win.acts["wire_layers"].trigger()

    def test_the_preset(self):
        steps = len(self.p.undo_stack)
        self.add()
        self.assertEqual(len(self.p.undo_stack), steps + 1)            # (one step)
        L = self.p.layers
        for name in ("480V BLK", "480V RED", "480V ORG", "480V BRN", "480V YEL", "480V WHT",
                     "480V GRN"):
            self.assertEqual(L[name].awg, "12", name)
        self.assertEqual([L[n].wire_color for n in ("480V WHT", "480V GRN")], ["WHT", "GRN"])
        for name in ("120V RED", "120V BLK", "120V WHT"):
            self.assertEqual(L[name].awg, "14", name)
        self.assertEqual((L["24VDC BLU"].awg, L["24VDC BLU"].wire_color), ("16", "BLU"))
        self.assertEqual((L["24VDC BLU-WHT"].awg, L["24VDC BLU-WHT"].wire_color),
                         ("16", "BLU/WHT"))
        self.assertEqual((L["ETHERNET"].awg, L["ETHERNET"].wire_color), ("", ""))
        self.assertEqual(L["ETHERNET"].color, "#00b050")
        self.p.undo()
        self.assertNotIn("480V BLK", self.p.layers)

    def test_only_the_groups_ticked_and_own_layers_kept(self):
        with self.p.edit("mine") as ed:
            ed.layer("120V RED", None, M.Layer("120V RED", "#ff00ff", awg="12").to_dict())
        self.add(["120 V"])
        self.assertNotIn("480V BLK", self.p.layers)
        self.assertIn("120V WHT", self.p.layers)
        mine = self.p.layers["120V RED"]
        self.assertEqual((mine.color, mine.awg), ("#ff00ff", "12"))     # (left as it was)

    def test_wires_go_on_a_preset_layer(self):
        self.add(["Ethernet"])
        self.v.current_layer = "ETHERNET"
        self.assertEqual(C.wire_layer(self.v), "ETHERNET")
        self.v.current_layer = "0"
        self.assertEqual(C.wire_layer(self.v), "WIRES")

    def test_stripes(self):
        self.assertEqual(wirelayers.stripe("BLU/WHT"), "#ffffff")
        self.assertEqual(wirelayers.stripe("GRN/YEL"), "#ffd700")
        self.assertIsNone(wirelayers.stripe("BLU"))
        self.assertIsNone(wirelayers.stripe("BLU/XYZ"))
        self.assertIsNone(wirelayers.stripe(""))

    def test_striped_wire_drawn_with_white_on_blue(self):
        from PySide6.QtGui import QImage, QPainter, QColor, QTransform
        from kanzonascad import render
        self.add(["24 VDC"])
        with self.p.edit("w") as ed:
            ed.add(self.s, M.Wire([(2.0, 5.0), (8.0, 5.0)], layer="24VDC BLU-WHT"))
            ed.add(self.s, M.Wire([(2.0, 3.0), (8.0, 3.0)], layer="24VDC BLU"))

        def row(y, mono=False):
            r = render.SheetRenderer(self.p, self.s, dark=True, mono=mono)
            img = QImage(800, 800, QImage.Format_ARGB32)
            img.fill(0)
            p = QPainter(img)
            p.setTransform(QTransform(50, 0, 0, -50, 0, 700))   # (50 px an inch, y up)
            r.paint(p)
            p.end()
            py = int(round(700 - 50 * y))
            return {QColor(img.pixel(x, py)).name() for x in range(120, 380)}
        striped, plain = row(5.0), row(3.0)
        self.assertIn("#ffffff", striped)
        self.assertIn("#3070ff", striped)
        self.assertNotIn("#ffffff", plain)
        self.assertNotIn("#ffffff", row(5.0, mono=True) - {"#f0f0f0"})


class WireSizeTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.s = self.v.sheet()
        with self.p.edit("layers") as ed:
            wirelayers.add_preset(ed, self.p, ["480 V"])
        with self.p.edit("w") as ed:
            self.w = ed.add(self.s, M.Wire([(2.0, 5.0), (8.0, 5.0)], layer="480V BLK"))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def now(self):
        return self.s.entities[self.w.id]

    def gauges(self):
        return [t.text for t in wirenums.gauge_labels(self.p, self.s)]

    def test_size_of_its_own_and_back_to_the_layers(self):
        self.assertEqual(self.gauges(), ["12 AWG"])
        self.v.set_selection({self.w.id})
        self.v.run(C.WireSizeCmd)
        type_in(self.v, "10 awg")
        self.assertIsNone(self.v.cmd)
        self.assertEqual(self.now().awg, "10")
        self.assertEqual(self.gauges(), ["10 AWG"])
        self.v.set_selection({self.w.id})
        self.v.run(C.WireSizeCmd)
        type_in(self.v, "L")
        self.assertEqual(self.now().awg, "")
        self.assertEqual(self.gauges(), ["12 AWG"])
        self.p.undo()
        self.assertEqual(self.now().awg, "10")

    def test_clicked_wires_and_a_wrong_size(self):
        said = []
        self.v.message = lambda m, *a: said.append(m)
        self.v.run(C.WireSizeCmd)
        self.v.cmd.pick((5.0, 5.0))
        self.v.cmd.enter()
        type_in(self.v, "banana")
        self.assertTrue(any("Not a wire gauge" in m for m in said), said)
        self.assertIsNotNone(self.v.cmd)
        type_in(self.v, "250 mcm")
        self.assertEqual(self.now().awg, "250 kcmil")
        self.assertEqual(self.gauges(), ["250 kcmil"])               # (no "AWG" after kcmil)

    def test_gauges_typed(self):
        g = C.wire_gauge
        self.assertEqual([g("14"), g("1/0"), g("4/0 AWG"), g("500 KCMIL"), g("08")],
                         ["14", "1/0", "4/0", "500 kcmil", "8"])
        self.assertEqual([g("0"), g("5/0"), g("x"), g("")], [None, None, None, None])

    def test_kept_when_cut_saved_and_not_joined_to_another_size(self):
        with self.p.edit("size") as ed:
            ed.change(self.s, self.now().copy(awg="10"))
            x = ed.add(self.s, M.Wire([(4.0, 4.0), (4.0, 6.0)], layer="480V BLK"))
        pieces, _ends = wires.trim_wire(self.s, self.now(), (6.0, 5.0))
        self.assertTrue(pieces)
        self.assertEqual({w.awg for w in pieces}, {"10"})
        with self.p.edit("cross off") as ed:
            ed.remove(self.s, x.id)
        d = self.p.to_dict()
        q = M.Project.from_dict(d)
        self.assertEqual([w.awg for s in q.sheets for w in s.wires()], ["10"])
        # (another wire end to end with it, of the layer's size: two wires, not one)
        with self.p.edit("other") as ed:
            o = ed.add(self.s, M.Wire([(8.0, 5.0), (10.0, 5.0)], layer="480V BLK"))
        with self.p.edit("clean") as ed:
            wires.cleanup(ed, self.s)
        self.assertIn(o.id, self.s.entities)
        self.assertEqual(sorted(w.awg for w in self.s.wires()), ["", "10"])
        # (and of one size: made one)
        with self.p.edit("same") as ed:
            ed.change(self.s, self.s.entities[o.id].copy(awg="10"))
        with self.p.edit("clean") as ed:
            got = wires.cleanup(ed, self.s)
        self.assertEqual(got["joined"], 1)
        self.assertEqual(len(self.s.wires()), 1)

    def test_label_kcmil_on_a_layer(self):
        self.assertEqual(M.gauge_text("250 kcmil"), "250 kcmil")
        self.assertEqual(M.gauge_text("2/0"), "2/0 AWG")
        self.assertEqual(M.Layer("X", awg="350 kcmil", wire_color="BLK").wire_label(),
                         "350 kcmil BLK")

    def test_saved_file_round_trip(self):
        with self.p.edit("size") as ed:
            ed.change(self.s, self.now().copy(awg="8"))
        path = os.path.join(tempfile.mkdtemp(), "x.kzcad")
        self.p.save(path)
        q = M.Project.load(path)
        self.assertEqual([w.awg for s in q.sheets for w in s.wires()], ["8"])
        self.assertEqual(q.layers["480V GRN"].awg, "12")


if __name__ == "__main__":
    unittest.main()
