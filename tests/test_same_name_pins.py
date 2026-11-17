"""The owner, 0.17.5, with a photo and the project: "When I move a vfd that's connected to bus
wires, the wires move with it. But when I move it, the ground wire doesn't. FYI, this is a
modified vfd. I added a ground connection". The drive had two pins named GND (line side and
load side); the wires on a moved symbol's pins were matched by pin name, so one GND's wire
stayed behind. Matched by name and which of that name, both follow (a move, and a change of
the block in Edit block)."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import block_editor
from kanzonascad import commands as C
from kanzonascad import model as M


class SameNamePinsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        self.s, self.p = v.sheet(), v.project
        self.d = M.BlockDef("Drive two grounds", "symbol",
                            [M.Line((0.0, -0.5), (1.0, -0.5)), M.Line((0.0, 0.5), (1.0, 0.5))],
                            pins=[{"name": "L1", "pos": (0.0, 0.5)},
                                  {"name": "GND", "pos": (0.0, -0.5)},
                                  {"name": "T1", "pos": (1.0, 0.5)},
                                  {"name": "GND", "pos": (1.0, -0.5)}],
                            prefix="VFD", tag_pos=(0.5, 0.8), role="device")
        with self.p.edit("x") as ed:
            ed.block(self.d)
            self.e = ed.add(self.s, M.Insert(self.d.name, (5.0, 5.0),
                                              defn=self.p.blocks[self.d.name]))
            for n, q in self.e.pin_points():
                out = -1.0 if q[0] < 5.5 else 1.0
                ed.add(self.s, M.Wire([q, (q[0] + out, q[1])]))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def wired(self):
        e = self.s.entities[self.e.id]
        return [any(w.touches(q) for w in self.s.wires()) for _n, q in e.pin_points()]

    def test_both_grounds_follow_a_move(self):
        self.v.set_selection({self.e.id})
        self.v.run(C.MoveCmd)
        type_in(self.v, "0,0", "0,2")
        self.assertEqual(self.s.entities[self.e.id].pos, (5.0, 7.0))
        self.assertEqual(self.wired(), [True, True, True, True])

    def test_and_a_change_in_edit_block(self):
        # the block's pins moved 1/4" down: every wire comes along, the two GND too
        d = M.BlockDef.from_dict(self.p.blocks[self.d.name].to_dict())
        d.pins = [dict(q, pos=(q["pos"][0], q["pos"][1] - 0.25)) for q in d.pins]
        with self.p.edit("block") as ed:
            block_editor.update_copies(ed, self.p, d)
        self.assertEqual(self.wired(), [True, True, True, True])

    def test_pin_keys(self):
        got = M.pin_keys([("GND", (0, 0)), ("L1", (1, 1)), ("GND", (2, 2))])
        self.assertEqual(got, {("GND", 0): (0, 0), ("L1", 0): (1, 1), ("GND", 1): (2, 2)})


if __name__ == "__main__":
    unittest.main()
