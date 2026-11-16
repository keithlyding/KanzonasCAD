"""Symbols turned sideways (the owner, with a photo of CB201 and OL201 turned to run down the
page, their tags over the third pole: "I don't like the location of the tag when rotated
sideways either. I need to be able to move it. Plus, I want to be able to orient it either
direction and still connect to wires or devices properly").

- A tag turned sideways sits beside the symbol, starting at its spot and running away from it
  (left or right aligned, middle), clear of the drawing.
- A symbol's tag, and each attribute shown at one spot, has a grip of its own: dragged, it
  stays where it was put, in the block's own coordinates (it follows the symbol), saved.
- Insert flips a symbol with several pins when flipped the other way more of its pins land on
  wires or pins: a 3-pole symbol turned either way onto a vertical bus lands every pole."""
import os
import tempfile
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M

THREE = ["Circuit breaker 3-pole", "Disconnect 3-pole", "Fuses 3-pole",
         "Overload heaters 3-pole", "Fused disconnect 3-pole", "Starter 3-pole"]


class TurnedSymbolsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.lib = self.win.library
        self.p = self.v.project

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def insert(self, name, at, keys=()):
        before = set(self.v.sheet().entities)
        self.v.run(C.InsertCmd, self.lib.get("symbol", name), {})
        for k in keys:
            self.v.input_text(k)
        type_in(self.v, "%r,%r" % at)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        return [e for i, e in self.v.sheet().entities.items()
                if i not in before and isinstance(e, M.Insert)][0]

    def clear(self):
        s = self.v.sheet()
        with self.p.edit("clear") as ed:
            for i in list(s.entities):
                ed.remove(s, i)

    def bus(self, x0, side, vertical=True):
        with self.p.edit("bus") as ed:
            for i in range(3):
                k = x0 + side * i * 0.5
                ed.add(self.v.sheet(), M.Wire([(k, 10.0), (k, 2.0)] if vertical else
                                              [(0.0, k), (12.0, k)]))

    def test_every_pole_lands_on_a_bus_turned_and_flipped_any_way(self):
        for name in THREE:
            for keys in ((), ("F",), ("R",), ("R", "F"), ("R", "R"), ("R", "R", "F"),
                         ("R", "R", "R"), ("R", "R", "R", "F")):
                vertical = keys.count("R") % 2 == 1
                for side in (1, -1):
                    self.bus(6.0, side, vertical)
                    at = (6.0, 6.0)
                    e = self.insert(name, at, keys)
                    s = self.v.sheet()
                    ends = {q for w in s.wires() for q in (w.points[0], w.points[-1])}
                    off = [n for n, q in e.pin_points() if q not in ends]
                    self.assertEqual(off, [], "%s %s side %d" % (name, keys, side))
                    self.assertEqual(dict(e.pin_points())["L1"], at)
                    self.clear()

    def test_flips_only_to_land_more(self):
        # nothing to land on: as turned and flipped
        e = self.insert("Disconnect 3-pole", (3.0, 3.0), ("R", "F"))
        self.assertTrue(e.mirror)
        e = self.insert("Disconnect 3-pole", (6.0, 3.0), ("R",))
        self.assertFalse(e.mirror)
        # a one-pole symbol is never flipped for it
        self.bus(9.0, 1)
        e = self.insert("Fuse", (9.0, 6.0), ("R", "F"))
        self.assertTrue(e.mirror)

    def test_the_preview_is_where_it_will_land(self):
        self.bus(6.0, 1)
        v = self.v
        v.run(C.InsertCmd, self.lib.get("symbol", "Overload heaters 3-pole"), {})
        for k in "RRR":
            v.input_text(k)
        shown = v.cmd.preview((6.0, 6.0))[0]
        type_in(v, "6.0,6.0")
        placed = [e for e in v.sheet().inserts()][0]
        self.assertEqual(shown.pin_points(), placed.pin_points())

    def test_a_sideways_tag_is_beside_the_symbol(self):
        for name in THREE + ["Contact NO", "Relay coil", "Fuse"]:
            for keys in (("R",), ("R", "R", "R"), ("R", "F"), ("R", "R", "R", "F")):
                e = self.insert(name, (6.0, 6.0), keys)
                t = e.tag_text()
                self.assertIn(t.align, ("left", "right"))
                self.assertEqual(t.valign, "middle")
                tb = t.bbox()
                for q in e.defn.entities:
                    w = q._map(e.to_world, rot=e.angle, factor=e.scale, mirror=None)
                    b = w.bbox()
                    overlap = tb[0] < b[2] and b[0] < tb[2] and tb[1] < b[3] and b[1] < tb[3]
                    self.assertFalse(overlap, "%s %s: its tag over its drawing" % (name, keys))
                self.clear()
        # across, as before
        e = self.insert("Disconnect 3-pole", (6.0, 6.0))
        self.assertEqual((e.tag_text().align, e.tag_text().valign), ("center", "baseline"))

    def test_the_tag_has_a_grip_and_stays_where_it_is_dragged(self):
        e = self.insert("Circuit breaker 3-pole", (4.0, 6.0), ("R", "R", "R"))
        with self.p.edit("rating") as ed:
            ed.change(self.v.sheet(), e.copy(attrs=dict(e.attrs, RATING="30A")))
        s = self.v.sheet()
        e = s.entities[e.id]
        names = [n for n, _q in e.text_grips()]
        self.assertEqual(names, ["TAG", "RATING"])
        self.assertEqual(len(e.grips()), 3)
        pins = e.pin_points()
        self.v.run(C.GripCmd, e, 1)
        type_in(self.v, "7.5,3.25")
        e = s.entities[e.id]
        self.assertEqual(e.tag_text().pos, (7.5, 3.25))
        self.assertEqual(e.pin_points(), pins)
        # the rating's grip too
        self.v.run(C.GripCmd, e, 2)
        type_in(self.v, "7.5,2.5")
        e = s.entities[e.id]
        self.assertEqual(dict(e.text_grips())["RATING"], (7.5, 2.5))
        # it follows the symbol when it is moved
        with self.p.edit("move") as ed:
            ed.change(s, e.moved(1.0, 0.5))
        self.assertEqual(s.entities[e.id].tag_text().pos, (8.5, 3.75))
        # saved and opened as it is
        path = os.path.join(tempfile.mkdtemp(), "t.kzcad")
        self.p.save(path)
        again = M.Project.load(path).sheets[0].entities[e.id]
        self.assertEqual(again.tag_text().pos, (8.5, 3.75))
        # one step back puts it where it was
        self.p.undo()
        self.p.undo()
        self.p.undo()
        self.assertNotEqual(s.entities[e.id].tag_text().pos, (7.5, 3.25))

    def test_a_fuse_blocks_ratings_have_no_grip(self):
        e = self.insert("Fuses 3-pole", (4.0, 6.0))
        with self.p.edit("rating") as ed:
            ed.change(self.v.sheet(), e.copy(attrs=dict(e.attrs, RATING="30A")))
        e = self.v.sheet().entities[e.id]
        self.assertEqual([n for n, _q in e.text_grips()], ["TAG"])


if __name__ == "__main__":
    unittest.main()
