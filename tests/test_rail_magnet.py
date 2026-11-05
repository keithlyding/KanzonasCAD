"""Footprints onto DIN rail (the owner: "make centering a device on din rail more intuitive"
and "someone needs a way to pick where the middle of the din rail slot is on blocks ... Not
all objects are centered vertically on din rail"): placed, moved, copied or dragged, a
footprint whose rail point comes over a rail locks onto its centerline and slides along it;
near a footprint already on the rail, it butts against it; a block's rail point is set in
Edit block."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import block_editor as BE
from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import railsnap as RS

W = 35 * M.MM_IN                # a 35 mm rail


def box(name="Contactor", w=2.0, h=4.0, rail_pos=None):
    """A footprint w x h, its base point at its lower left corner."""
    return M.BlockDef(name, "footprint", [M.Polyline([(0, 0), (w, 0), (w, h), (0, h)], True)],
                      rail_pos=rail_pos)


def place(sheet, defn, at, angle=0.0):
    ins = M.Insert(defn.name, at, angle, 1.0, False, {}, defn, None, layer="PANEL")
    sheet._put(ins)
    return ins


class MagnetTest(unittest.TestCase):
    """railsnap.magnet itself (no window)."""

    def setUp(self):
        self.s = M.Sheet()
        self.rail = M.Rail((0, 5), (20, 5), "TS35x7.5", W, 7.5 * M.MM_IN)
        self.s._put(self.rail)

    def test_locks_across_and_slides_along(self):
        f = M.Insert("Contactor", (3, 3.3), 0.0, 1.0, False, {}, box(), None)
        # its middle (4, 5.3) is over the rail: it goes 0.3 down, and nowhere along
        dx, dy, hit = RS.magnet(self.s, [f], 0.0, 0.0, 0.1)
        self.assertAlmostEqual(dx, 0.0)
        self.assertAlmostEqual(dy, -0.3)
        self.assertEqual(hit["rail"], self.rail)
        self.assertFalse(hit["butted"])
        self.assertAlmostEqual(hit["point"][1], 5.0)
        # moved along the rail: still on it, wherever along it goes
        dx, dy, _hit = RS.magnet(self.s, [f], 7.13, 0.05, 0.1)
        self.assertAlmostEqual(dx, 7.13)
        self.assertAlmostEqual(dy, -0.3)

    def test_off_the_rail_nothing_changes(self):
        f = M.Insert("Contactor", (3, 9), 0.0, 1.0, False, {}, box(), None)
        self.assertEqual(RS.magnet(self.s, [f], 0.5, 0.25, 0.1), (0.5, 0.25, None))
        # past the end of the rail
        f = M.Insert("Contactor", (25, 3), 0.0, 1.0, False, {}, box(), None)
        self.assertIsNone(RS.magnet(self.s, [f], 0.0, 0.0, 0.1)[2])
        # a symbol, or a rail moved with what is on it, never
        sym = M.Insert("Coil", (3, 5), 0.0, 1.0, False, {},
                       M.BlockDef("Coil", "symbol", [M.Circle((0, 0), 0.2)]), None)
        self.assertIsNone(RS.magnet(self.s, [sym], 0.0, 0.0, 0.1)[2])
        f = M.Insert("Contactor", (3, 3.3), 0.0, 1.0, False, {}, box(), None)
        other = M.Rail((0, 15), (20, 15), "TS35x7.5", W, 7.5 * M.MM_IN)
        self.assertIsNone(RS.magnet(self.s, [f, other], 0.0, 0.0, 0.1)[2])

    def test_rail_point_not_in_the_middle(self):
        # the clip 3 in up a 4 in tall part: that height goes on the centerline
        f = M.Insert("Breaker", (3, 2.1), 0.0, 1.0, False, {}, box("Breaker", rail_pos=(1, 3)),
                     None)
        dx, dy, hit = RS.magnet(self.s, [f], 0.0, 0.0, 0.1)
        self.assertAlmostEqual(2.1 + dy, 2.0)
        self.assertAlmostEqual(hit["point"][1], 5.0)

    def test_vertical_rail_and_turned_footprint(self):
        rail = M.Rail((30, 0), (30, 20), "TS35x7.5", W, 7.5 * M.MM_IN)
        self.s._put(rail)
        # turned 90 degrees: its middle is at (pos.x - 2, pos.y + 1)
        f = M.Insert("Contactor", (32.4, 4), 90.0, 1.0, False, {}, box(), None)
        dx, dy, hit = RS.magnet(self.s, [f], 0.0, 0.0, 0.1)
        self.assertIs(hit["rail"], rail)
        self.assertAlmostEqual(32.4 + dx - 2.0, 30.0)
        self.assertAlmostEqual(dy, 0.0)

    def test_butts_against_a_neighbor(self):
        place(self.s, box(), (8, 3))                     # on the rail, 8 to 10 along
        f = M.Insert("Contactor", (10.06, 3.2), 0.0, 1.0, False, {}, box(), None)
        dx, dy, hit = RS.magnet(self.s, [f], 0.0, 0.0, 0.1)
        self.assertTrue(hit["butted"])
        self.assertAlmostEqual(10.06 + dx, 10.0)
        self.assertAlmostEqual(3.2 + dy, 3.0)
        # from the other side: its right end against the neighbor's left end
        dx, dy, hit = RS.magnet(self.s, [f], 8 - 2.04 - 10.06, 0.0, 0.1)
        self.assertTrue(hit["butted"])
        self.assertAlmostEqual(10.06 + dx, 6.0)
        # farther than the tolerance: it stays where it was put along the rail
        dx, dy, hit = RS.magnet(self.s, [f], 0.5, 0.0, 0.1)
        self.assertFalse(hit["butted"])
        self.assertAlmostEqual(dx, 0.5)
        # a part off the rail is no neighbor
        place(self.s, box(), (13, 9))
        dx, _dy, hit = RS.magnet(self.s, [f], 2.96, 0.0, 0.1)
        self.assertFalse(hit["butted"])

    def test_rail_pos_round_trip(self):
        b = box(rail_pos=(1, 3))
        self.assertEqual(M.BlockDef.from_dict(b.to_dict()).rail_pos, (1.0, 3.0))
        self.assertNotIn("rail_pos", box().to_dict())        # (old files unchanged)
        self.assertEqual(box().rail_point(), (1.0, 2.0))


class WindowTest(unittest.TestCase):
    """Through the commands and a drag."""

    def setUp(self):
        self.win, self.v = window()
        self.v.snap_on = self.v.polar_on = self.v.ortho_on = False
        self.v.osnap_on = True
        self.p = self.v.project
        self.s = self.v.sheet()
        with self.p.edit("rail") as ed:
            self.rail = ed.add(self.s, M.Rail((1, 5), (15, 5), "TS35x7.5", W, 7.5 * M.MM_IN))
        self.v.scale = 50.0             # (10 pixels: 0.2 in)

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def newest(self):
        return max(self.s.entities.values(), key=lambda e: e.id)

    def test_insert_lands_on_the_rail(self):
        self.v.run(C.InsertCmd, box())
        prev = self.v.cmd.preview((3, 3.4))[0]
        self.assertAlmostEqual(prev.pos[1], 3.0)
        type_in(self.v, "3,3.4")
        ins = self.newest()
        self.assertAlmostEqual(ins.pos[0], 3.0)
        self.assertAlmostEqual(ins.pos[1], 3.0)
        # with the object snaps off (F3), where it is put
        self.v.osnap_on = False
        self.v.run(C.InsertCmd, box())
        type_in(self.v, "8,3.4")
        self.assertEqual(tuple(self.newest().pos), (8.0, 3.4))

    def test_move_copy_and_drag(self):
        a = place(self.s, box(), (2, 0))
        self.v.set_selection({a.id})
        self.v.run(C.MoveCmd)
        type_in(self.v, "2,0", "4.13,3.25")
        a = self.s.entities[a.id]
        self.assertAlmostEqual(a.pos[0], 4.13)
        self.assertAlmostEqual(a.pos[1], 3.0)
        # a copy beside it butts against it
        self.v.set_selection({a.id})
        self.v.run(C.CopyCmd)
        type_in(self.v, "4.13,3", "6.2,3.1")
        b = self.newest()
        self.assertNotEqual(b.id, a.id)
        self.assertAlmostEqual(b.pos[0], 6.13)
        self.assertAlmostEqual(b.pos[1], 3.0)
        self.v.cancel() if self.v.cmd is not None else None
        # a drag: the same rule (the preview and the drop alike)
        c = place(self.s, box(), (10, 8))
        d = {"start": (11, 10), "ents": [c], "moved": True}
        dx, dy = self.v._drag_delta(d, (11.5, 5.4))
        self.assertAlmostEqual(dx, 0.5)
        self.assertAlmostEqual(8 + dy, 3.0)
        self.assertIsNotNone(self.v._rail_hit)
        self.v.osnap_on = False
        ddx, ddy = self.v._drag_delta(d, (11.5, 5.4))
        self.assertAlmostEqual(ddx, 0.5)
        self.assertAlmostEqual(ddy, -4.6)

    def test_block_editor_rail_marker(self):
        b = box("Breaker")
        proj, sess = BE.open_block(b)
        s = proj.sheets[0]
        marks = [e for e in s.entities.values() if e.layer == BE.LAYER_RAIL]
        self.assertEqual(len(marks), 1)
        self.assertEqual(marks[0].text, BE.RAIL_TEXT)
        # left where it is: stays automatic, the block the same
        res = BE.to_block(proj, sess)
        self.assertIsNone(res.defn.rail_pos)
        self.assertEqual(res.defn.to_dict(), b.to_dict())
        # moved up to the clip: the block's rail point
        with proj.edit("move") as ed:
            ed.change(s, marks[0].moved(0, 1.0))
        res = BE.to_block(proj, sess)
        self.assertEqual(res.defn.rail_pos, (1.0, 3.0))
        self.assertEqual(len(res.defn.entities), 1)      # (the marker isn't drawing)
        # saved, opened again: the marker where it was put, kept as it is
        BE.saved(sess, res)
        proj2, sess2 = BE.open_block(res.defn)
        m2 = [e for e in proj2.sheets[0].entities.values() if e.layer == BE.LAYER_RAIL][0]
        self.assertEqual(BE.to_block(proj2, sess2).defn.rail_pos, (1.0, 3.0))
        # erased: automatic again
        with proj2.edit("erase") as ed:
            ed.remove(proj2.sheets[0], m2.id)
        self.assertIsNone(BE.to_block(proj2, sess2).defn.rail_pos)
        # a symbol has no rail marker
        proj3, _s = BE.open_block(M.BlockDef("Coil", "symbol", [M.Circle((0, 0), 0.2)]))
        self.assertFalse([e for e in proj3.sheets[0].entities.values()
                          if e.layer == BE.LAYER_RAIL])


if __name__ == "__main__":
    unittest.main()
