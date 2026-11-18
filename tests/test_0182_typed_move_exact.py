"""A move typed goes exactly as far as typed, every snap on (the owner, 0.18.2, a typed Move
of part of a panel, every snap on: "one of my vfds disappeared"; the battery, moving areas,
seed 1212: an object moved 1.5 where 2.5 was typed). The rail magnet, which locks a footprint
coming over a DIN rail onto it, took typed points too and shifted the whole selection; it
pulls only what the mouse places."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import osnap as OS

W = 35 * M.MM_IN


class TypedMoveExactTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on, v.osnap_modes = True, {m for m, _n, _t in OS.MODES}
        v.snap_on = v.ortho_on = v.polar_on = False
        v.scale = 20.0                          # (the magnet's reach: half an inch)
        self.p, self.s = v.project, v.sheet()
        box = M.BlockDef("Contactor", "footprint",
                         [M.Polyline([(0, 0), (2, 0), (2, 4), (0, 4)], True)])
        with self.p.edit("parts") as ed:
            ed.add(self.s, M.Rail((0, 5), (20, 5), "TS35x7.5", W, 7.5 * M.MM_IN))
            # (its rail point, its middle, at 4, 5.6: 0.6 over the rail)
            self.f = ed.add(self.s, M.Insert("Contactor", (3, 3.6), 0.0, 1.0, False, {}, box,
                                             None, layer="PANEL"))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_typed_goes_as_typed(self):
        self.v.set_selection({self.f.id})
        self.v.run(C.MoveCmd)
        type_in(self.v, "4,5.6", "@0,-0.45")            # (lands 0.15 over the rail)
        self.assertAlmostEqual(self.s.entities[self.f.id].pos[1], 3.15)

    def test_placed_by_the_mouse_still_locks(self):
        self.v.set_selection({self.f.id})
        self.v.run(C.MoveCmd)
        type_in(self.v, "4,5.6")
        self.v.cmd.point((4.0, 5.15))                   # (a click: the magnet pulls it on)
        self.assertAlmostEqual(self.s.entities[self.f.id].pos[1], 3.0)


if __name__ == "__main__":
    unittest.main()
