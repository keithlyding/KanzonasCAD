"""A layer's gauge label switched off on its own (the owner, 0.18.5, control power: "It's all
going to be blue and blue/white, 16awg. I don't need to announce this all over the place")."""
import unittest

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import wirelayers
from kanzonascad import wirenums


class GaugeShownTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()
        with self.p.edit("layers") as ed:
            wirelayers.add_preset(ed, self.p, ["480 V", "24 VDC"])
            ed.add(self.s, M.Wire([(2.0, 2.0), (2.0, 6.0)], layer="480V BLK"))
            ed.add(self.s, M.Wire([(6.0, 2.0), (6.0, 6.0)], layer="24VDC BLU"))
            self.own = ed.add(self.s, M.Wire([(9.0, 2.0), (9.0, 6.0)], layer="24VDC BLU",
                                             awg="14"))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def texts(self):
        return sorted(t.text for t in wirenums.gauge_labels(self.p, self.s))

    def off(self, name):
        lay = self.p.layers[name]
        after = M.Layer.from_dict(dict(lay.to_dict(), gauge_shown=False))
        with self.p.edit("off") as ed:
            ed.layer(name, lay.to_dict(), after.to_dict())

    def test_one_layer_off(self):
        self.assertEqual(self.texts(), ["12 AWG", "14 AWG", "16 AWG"])
        self.off("24VDC BLU")
        # (480 V still labeled; a wire with a gauge of its own still shows it)
        self.assertEqual(self.texts(), ["12 AWG", "14 AWG"])
        q = M.Project.from_dict(self.p.to_dict())
        self.assertFalse(q.layers["24VDC BLU"].gauge_shown)
        self.assertTrue(q.layers["480V BLK"].gauge_shown)
        self.assertNotIn("gauge_shown", self.p.layers["480V BLK"].to_dict())
        self.p.undo()
        self.assertEqual(self.texts(), ["12 AWG", "14 AWG", "16 AWG"])

    def test_the_layers_window(self):
        from kanzonascad import dialogs
        dlg = dialogs.LayersDialog(self.win, self.p, "0")
        t = dlg.table
        row = [r for r in range(t.rowCount()) if t.item(r, 0).text() == "24VDC BLU"][0]
        col = dlg.COLS.index("Gauge shown")
        self.assertEqual(t.item(row, col).text(), "Yes")
        dlg._clicked(row, col)
        self.assertFalse(self.p.layers["24VDC BLU"].gauge_shown)
        self.assertEqual(self.texts(), ["12 AWG", "14 AWG"])
        dlg.close()


if __name__ == "__main__":
    unittest.main()
