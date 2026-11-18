"""Wire layers' gauge and color (the owner, 0.16: "I need to be able to set the awg and color
of wire layers. Also needs some intuitive way of displaying the gauge"): Layers has AWG and
Wire color columns; each run of wire on such a layer shows "10 AWG BRN" on the other side of
the wire from its number; Schematic settings can turn it off; layers a bus adds carry their
color's name."""
import json
import unittest

from PySide6.QtWidgets import QInputDialog

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import dialogs
from kanzonascad import model as M
from kanzonascad import wirenums


class GaugeTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.s = self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def set_layer(self, name, **kw):
        before = self.p.layers[name].to_dict() if name in self.p.layers else None
        after = dict(before or M.Layer(name).to_dict(), **kw)
        with self.p.edit("layer") as ed:
            ed.layer(name, before, after)

    def test_the_label_beside_the_wire(self):
        self.set_layer("POWER", color="#a0522d", awg="10", wire_color="BRN")
        with self.p.edit("w") as ed:
            ed.add(self.s, M.Wire([(1.0, 5.0), (6.0, 5.0)], layer="POWER"))
            ed.add(self.s, M.Wire([(2.0, 8.0), (2.0, 3.0)], layer="POWER"))
            ed.add(self.s, M.Wire([(8.0, 2.0), (12.0, 2.0)]))           # (WIRES: none)
        got = sorted((t.text, round(t.angle)) for t in wirenums.gauge_labels(self.p, self.s))
        self.assertEqual(got, [("10 AWG", 0), ("10 AWG", 90)])     # (the gauge, 0.18.4)
        # (Wire color label: the color too, on the wires asked)
        up = [w for w in self.s.wires() if w.points[0][0] == 2.0][0]
        self.v.set_selection({up.id})
        self.v.run(C.WireColorLabelCmd)
        got = sorted((t.text, round(t.angle)) for t in wirenums.gauge_labels(self.p, self.s))
        self.assertEqual(got, [("10 AWG", 0), ("10 AWG BRN", 90)])
        self.v.set_selection({up.id})
        self.v.run(C.WireColorLabelCmd)                                  # (and off again)
        self.assertEqual(sorted(t.text for t in wirenums.gauge_labels(self.p, self.s)),
                         ["10 AWG", "10 AWG"])
        self.v.set_selection({w.id for w in self.s.wires() if w.layer == "POWER"})
        self.v.run(C.WireColorLabelCmd)
        across = [t for t in wirenums.gauge_labels(self.p, self.s) if t.angle == 0][0]
        self.assertLess(across.bbox()[3], 5.0)                          # (under the wire)
        num = [t for t in wirenums.labels(self.p, self.s) if t.pos[1] > 4.0 and t.angle == 0]
        self.assertTrue(num and num[0].bbox()[1] > 5.0)                 # (its number above)

    def test_one_label_a_run_and_its_parts(self):
        self.set_layer("POWER", awg="12")
        with self.p.edit("w") as ed:
            ed.add(self.s, M.Wire([(1.0, 5.0), (4.0, 5.0)], layer="POWER"))
            ed.add(self.s, M.Wire([(4.0, 5.0), (4.0, 2.0)], layer="POWER"))
        self.assertEqual([t.text for t in wirenums.gauge_labels(self.p, self.s)], ["12 AWG"])
        self.set_layer("POWER", awg="", wire_color="RED")
        self.assertEqual(wirenums.gauge_labels(self.p, self.s), [])       # (no gauge)
        with self.p.edit("color") as ed:
            for w in list(self.s.wires()):
                ed.change(self.s, w.copy(show_color=True))
        self.assertEqual([t.text for t in wirenums.gauge_labels(self.p, self.s)], ["RED"])

    def test_off_saved_and_undone(self):
        self.set_layer("POWER")
        self.set_layer("POWER", awg="14", wire_color="BLK")
        with self.p.edit("w") as ed:
            ed.add(self.s, M.Wire([(1.0, 5.0), (6.0, 5.0)], layer="POWER"))
        again = M.Project.from_dict(json.loads(json.dumps(self.p.to_dict())))
        self.assertEqual(again.layers["POWER"].wire_label(), "14 AWG BLK")
        self.p.settings["wire_gauge_shown"] = False
        self.assertEqual(wirenums.gauge_labels(self.p, self.s), [])
        self.p.settings["wire_gauge_shown"] = True
        self.p.undo()
        self.p.undo()
        self.assertEqual(self.p.layers["POWER"].wire_label(), "")

    def test_the_layers_window(self):
        self.set_layer("POWER")
        dlg = dialogs.LayersDialog(self.win, self.p, "0")
        saved = QInputDialog.getItem
        QInputDialog.getItem = staticmethod(lambda *a, **k: ("10 AWG", True))
        try:
            dlg._wire("POWER", True)
            QInputDialog.getItem = staticmethod(lambda *a, **k: ("brn", True))
            dlg._wire("POWER", False)
        finally:
            QInputDialog.getItem = saved
        self.assertEqual((self.p.layers["POWER"].awg, self.p.layers["POWER"].wire_color),
                         ("10", "BRN"))
        row = [r for r in range(dlg.table.rowCount())
               if dlg.table.item(r, 0).data(0x0100) == "POWER"][0]
        self.assertEqual(dlg.table.item(row, 4).text(), "10")
        dlg.close()

    def test_a_bus_layer_carries_its_color(self):
        self.win.ask_bus_layers = lambda n, cur: ["WIRE BROWN", "WIRE ORANGE", "WIRE YELLOW"]
        self.v.run(C.BusCmd)
        type_in(self.v, "L", "1,8", "5,8")
        if self.v.cmd is not None:
            self.v.cmd.enter()
        self.assertEqual(self.p.layers["WIRE ORANGE"].wire_color, "ORG")
        # (side by side: one label naming the three, in order across, 0.18.4, their colors
        # shown as asked; on every wire as asked, each its own)
        self.v.set_selection({w.id for w in self.s.wires()})
        self.v.run(C.WireColorLabelCmd)
        texts = [t.text for t in wirenums.gauge_labels(self.p, self.s)]
        self.assertEqual(texts, ["BRN, ORG, YEL"])
        with self.p.edit("each") as ed:
            ed.project_settings({"wire_gauge_each": "each"})
        texts = sorted(t.text for t in wirenums.gauge_labels(self.p, self.s))
        self.assertEqual(texts, ["BRN", "ORG", "YEL"])


if __name__ == "__main__":
    unittest.main()
