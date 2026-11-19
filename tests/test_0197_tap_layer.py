"""A wire drawn on another wire takes its layer (the owner, 0.19.7: "when connecting a wire to
another wire, do you think the new wire should automatically become the same layer?"; agreed:
yes, and joining wires of two layers stays on the current one with a warning)."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class TapLayerTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.s = self.v.sheet()
        with self.p.edit("layers") as ed:
            for name in ("480V BRN", "24VDC BLU"):
                ed.layer(name, None, M.Layer(name, "#a05a2c", awg="12",
                                             wire_color="BRN").to_dict())
            ed.add(self.s, M.Wire([(1.0, 8.0), (12.0, 8.0)], layer="480V BRN"))
            ed.add(self.s, M.Wire([(1.0, 2.0), (12.0, 2.0)], layer="24VDC BLU"))
        self.v.current_layer = "24VDC BLU"
        self.said = []
        self.v.message = lambda text: self.said.append(text)

    def tearDown(self):
        self.win.__dict__.pop("ask_wire_number", None)
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def draw(self, *pts):
        before = set(self.s.entities)
        self.v.run(C.WireCmd)
        type_in(self.v, *("%g,%g" % q for q in pts))
        if self.v.cmd is not None:
            type_in(self.v, "")                 # (a tap's number: kept)
        if self.v.cmd is not None:
            self.v.cancel()
        return [e for i, e in self.s.entities.items()
                if i not in before and isinstance(e, M.Wire)]

    def test_a_tap_takes_the_wires_layer(self):
        new = self.draw((5.0, 8.0), (5.0, 5.0))
        self.assertEqual([w.layer for w in new], ["480V BRN"])

    def test_ending_on_a_wire_takes_its_layer(self):
        new = self.draw((7.0, 5.0), (7.0, 8.0))
        self.assertEqual([w.layer for w in new], ["480V BRN"])

    def test_on_its_own_the_current_layer(self):
        new = self.draw((5.0, 5.0), (8.0, 5.0))
        self.assertEqual([w.layer for w in new], ["24VDC BLU"])

    def test_two_layers_joined_warns_and_stays_current(self):
        self.v.current_layer = "WIRES"
        new = self.draw((9.0, 8.0), (9.0, 2.0))
        self.assertEqual([w.layer for w in new], ["WIRES"])
        self.assertTrue(any("two layers" in t for t in self.said), self.said)

    def test_preview_shows_the_layer_it_will_take(self):
        self.v.run(C.WireCmd)
        type_in(self.v, "5,8")
        got = self.v.cmd.preview((5.0, 5.0))
        self.assertEqual([w.layer for w in got], ["480V BRN"])
        self.v.cancel()


if __name__ == "__main__":
    unittest.main()
