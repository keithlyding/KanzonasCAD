"""A wire takes its layer from the pin it starts on (the owner, 0.22.1: "Yes, on the auto wire
layer", to: PLC I/O on 24VDC BLU, commons on BLU-WHT, motor and drive terminals on 480 V, 120 V
control on 120V RED; per-pin defaults in the block editor). Only layers the project has; a wire
joined to another still takes that wire's layer; the setting off, the layer picked."""
import os
import tempfile
import unittest

from tests.util import APP, window, type_in

from kanzonascad import autolayer
from kanzonascad import block_editor as BE
from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wirelayers


class AutoWireLayerTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p, self.s = self.v.project, self.v.sheet()
        self.lib = self.win.library
        with self.p.edit("layers") as ed:
            wirelayers.add_preset(ed, self.p)

    def tearDown(self):
        if self.v.cmd is not None:
            self.v.cancel()
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def place(self, block, at, attrs=None):
        before = set(self.s.entities)
        self.v.run(C.InsertCmd, self.lib.get("symbol", block), dict(attrs or {}))
        type_in(self.v, at)
        if self.v.cmd is not None:
            self.v.cancel()
        return next(e for i, e in self.s.entities.items()
                    if i not in before and isinstance(e, M.Insert))

    def wire(self, a, b):
        self.v.run(C.WireCmd)
        type_in(self.v, "%r,%r" % a, "%r,%r" % b)
        if self.v.cmd is not None:
            self.v.cmd.enter()
        if self.v.cmd is not None:
            self.v.cancel()
        return max(self.s.wires(), key=lambda w: w.id)

    def from_pin(self, ins, pin, dx=-1.5):
        q = dict(ins.pin_points())[pin]
        return self.wire(q, (q[0] + dx, q[1]))

    def test_plc_points_and_commons(self):
        mod = self.place("1734-OE4C module", "8,9", {"SLOT": "3"})
        self.assertEqual(self.from_pin(mod, "0", 1.5).layer, "24VDC BLU")      # (OUT 0)
        self.assertEqual(self.from_pin(mod, "4", 1.5).layer, "24VDC BLU-WHT")  # (C)
        self.assertEqual(self.from_pin(mod, "6", 1.5).layer, "24VDC BLU")      # (V)
        ana = self.place("PLC analog input module, 4 channels IN/RTN", "3,9")
        self.assertEqual(self.from_pin(ana, "2").layer, "24VDC BLU")           # (IN-0)
        self.assertEqual(self.from_pin(ana, "1").layer, "24VDC BLU-WHT")       # (RTN-0)

    def test_motor_drive_and_transformer(self):
        mtr = self.place("Motor 3-phase", "10,4")
        self.assertEqual(self.from_pin(mtr, "T1").layer, "480V BLK")
        vfd = self.place("Variable frequency drive", "4,4")
        self.assertEqual(self.from_pin(vfd, "L2").layer, "480V BLK")
        self.assertEqual(self.from_pin(vfd, "PE1").layer, "480V GRN")
        xf = self.place("Control transformer", "4,7.5")
        self.assertEqual(self.from_pin(xf, "X1").layer, "120V RED")
        self.assertEqual(self.from_pin(xf, "X2", 1.5).layer, "120V WHT")

    def test_ended_on_a_pin_and_the_start_wins(self):
        mod = self.place("1734-IB8 module", "8,9", {"SLOT": "2"})
        q = dict(mod.pin_points())["0"]
        w = self.wire((q[0] - 2.0, q[1]), q)                  # (ends on IN 0)
        self.assertEqual(w.layer, "24VDC BLU")
        coil = self.place("Relay coil", "3,6")
        a = dict(coil.pin_points())
        self.assertEqual(self.wire(a[sorted(a)[0]], (1.5, 6.0)).layer, "WIRES")  # (no rule)

    def test_a_joined_wire_and_the_layer_box_and_off(self):
        mod = self.place("1734-IB8 module", "8,9", {"SLOT": "2"})
        q = dict(mod.pin_points())["1"]
        with self.p.edit("w") as ed:
            ed.add(self.s, M.Wire([(q[0] - 3.0, q[1]), (q[0] - 2.0, q[1])], layer="120V RED"))
        # (joining a wire: one conductor, its layer)
        self.assertEqual(self.wire((q[0] - 2.0, q[1]), q).layer, "120V RED")
        q2 = dict(mod.pin_points())["2"]
        C.set_wire_layer(self.v, "120V BLK")                  # (a pick: the pin still says)
        self.assertEqual(self.from_pin(mod, "2").layer, "24VDC BLU")
        with self.p.edit("off") as ed:
            ed.project_settings({"wire_layer_auto": False})
        self.assertEqual(self.wire(dict(mod.pin_points())["3"], (q2[0] - 1.5, q2[1] - 0.5))
                         .layer, "120V BLK")

    def test_only_layers_the_project_has(self):
        with self.p.edit("drop") as ed:
            ed.layer("24VDC BLU", self.p.layers["24VDC BLU"].to_dict(), None)
        mod = self.place("1734-IB8 module", "8,9", {"SLOT": "2"})
        self.assertEqual(self.from_pin(mod, "0").layer, "WIRES")

    def test_a_pins_own_layer_saved_and_through_the_block_editor(self):
        d = M.BlockDef("Horn", "symbol", [M.Circle((0, 0), 0.125)],
                       [{"name": "1", "pos": (-0.25, 0), "layer": "120V RED"},
                        {"name": "2", "pos": (0.25, 0)}], (0, 0.2), 0.1, "Mine", "A horn",
                       "device", "", "AH")
        self.assertEqual(M.BlockDef.from_dict(d.to_dict()).pins[0]["layer"], "120V RED")
        self.assertNotIn("layer", d.to_dict()["pins"][1])
        self.assertEqual(autolayer.pin_layer(self.p, d, "1"), "120V RED")
        self.assertIsNone(autolayer.pin_layer(self.p, d, "2"))
        # the block editor: opened, kept; Pins... sets one, undone with it
        bp, sess = BE.open_block(d)
        self.assertEqual(BE.to_block(bp, sess).defn.pins[0]["layer"], "120V RED")
        rows = [(e.id, e.text, x, y, "120V WHT" if e.text == "2" else "")
                for e, (x, y) in BE.pin_markers(bp, sess)]
        self.assertIsNone(BE.apply_pins(bp, sess, rows))
        got = BE.to_block(bp, sess).defn.pins
        self.assertEqual([q.get("layer") for q in got], [None, "120V WHT"])
        bp.undo()
        got = BE.to_block(bp, sess).defn.pins
        self.assertEqual([q.get("layer") for q in got], ["120V RED", None])
        path = os.path.join(tempfile.mkdtemp(), "b.kzcad")
        bp.save(path)                                         # (the editor's sheet saved)
        q = M.Project.load(path)
        self.assertEqual(list(q.sheets[0].pin_layers.values()), ["120V RED"])

    def test_the_message(self):
        said = []
        self.v.messaged.connect(said.append)
        mod = self.place("1734-IB8 module", "8,9", {"SLOT": "2"})
        self.from_pin(mod, "0")
        self.assertTrue(any("On 24VDC BLU" in t for t in said), said)


if __name__ == "__main__":
    unittest.main()
