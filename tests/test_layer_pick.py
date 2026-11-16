"""Picking a layer in the layer box (the owner, 0.16: "Layers are not responding when I try to
change to a new layer"): with objects selected, they go on it and the box shows their layer
(it showed the current layer again, as if nothing had happened); with none selected, it is
the current layer, and wires drawn then go on it when it is a wire layer (they always went on
WIRES); a drafting layer leaves wires on WIRES."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class LayerPickTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.s = self.v.sheet()
        with self.p.edit("layers") as ed:
            ed.layer("WIRE BROWN", None, M.Layer("WIRE BROWN", "#a0522d").to_dict())
            ed.layer("POWER", None, M.Layer("POWER", "#ff0000", awg="10").to_dict())
        self.win._fill_layers()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def pick(self, name):
        box = self.win.layer_box
        i = box.findText(name)
        box.setCurrentIndex(i)
        box.activated.emit(i)

    def wire(self, a, b):
        self.v.run(C.WireCmd)
        type_in(self.v, a, b)
        if self.v.cmd is not None:
            self.v.cmd.enter()
        return max(self.s.wires(), key=lambda w: w.id)

    def test_selected_objects_move_and_the_box_says_so(self):
        with self.p.edit("w") as ed:
            w = ed.add(self.s, M.Wire([(1.0, 1.0), (5.0, 1.0)]))
            ln = ed.add(self.s, M.Line((1.0, 3.0), (5.0, 3.0)))
        self.v.set_selection({w.id})
        self.assertEqual(self.win.layer_box.currentText(), "WIRES")    # (its layer)
        self.pick("WIRE BROWN")
        self.assertEqual(self.s.entities[w.id].layer, "WIRE BROWN")
        self.assertEqual(self.win.layer_box.currentText(), "WIRE BROWN")
        self.v.set_selection({w.id, ln.id})                            # (two layers)
        self.assertEqual(self.win.layer_box.currentIndex(), -1)
        self.v.set_selection(set())
        self.assertEqual(self.win.layer_box.currentText(), self.v.layer())

    def test_wires_go_on_the_current_wire_layer(self):
        self.pick("WIRE BROWN")
        self.assertEqual(self.wire("1,3", "5,3").layer, "WIRE BROWN")
        self.pick("POWER")                                  # (a gauge: a wire layer)
        self.assertEqual(self.wire("1,5", "5,5").layer, "POWER")
        self.pick("0")                                      # (drafting: wires stay on WIRES)
        self.assertEqual(self.wire("1,7", "5,7").layer, "WIRES")

    def test_a_bus_too_unless_its_layers_are_picked(self):
        self.pick("WIRE BROWN")
        self.v.run(C.BusCmd)
        type_in(self.v, "1,8", "5,8")
        if self.v.cmd is not None:
            self.v.cmd.enter()
        self.assertEqual({w.layer for w in self.s.wires()}, {"WIRE BROWN"})


if __name__ == "__main__":
    unittest.main()
