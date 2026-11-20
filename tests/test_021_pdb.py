"""Power distribution blocks (the owner, Nov 2026: "If I have a power distribution block, 3
phase, 1:18, how do I make all parts of the schematic tie back to the pd block"; "append A-Z on
each child wire"; "it would have to automatically resize based on the spacing of the wires"):
a 3-pole block PDB1 (L1-L3 in) and its outlets PDB1-1, PDB1-2... (T1-T3 out) on any sheet; each
outlet's wires take their phase's number with the outlet's letter; outlets number themselves
on their block; more outlets than the block has (OUTLETS, 1:18) are flagged; placed on a bus
of another spacing, the block is drawn to fit it."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import dupes
from kanzonascad import model as M
from kanzonascad import tags
from kanzonascad import wirenums


class PdbTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.s = self.v.sheet()
        self.said = []
        self.v.message = lambda text: self.said.append(text)
        lib = self.win.library
        self.par = lib.get("symbol", "Distribution block 3-pole")
        self.out = lib.get("symbol", "Distribution block outlet 3-pole")

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def place(self, defn, at, tag=None):
        self.v.run(C.InsertCmd, defn, {})
        type_in(self.v, "%r,%r" % at)
        if tag:
            type_in(self.v, tag)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        return [e for e in self.v.sheet().inserts() if e.defn.wiring == "pdb"][-1]

    def wire_pins(self, ins, out=False):
        with self.p.edit("wires") as ed:
            for _n, q in ins.pin_points():
                ed.add(self.v.sheet(), M.Wire([q, (q[0] + 1.5, q[1])] if out else
                                              [(q[0] - 2.0, q[1]), q]))

    def number(self):
        with self.p.edit("numbers") as ed:
            wirenums.sync(ed, self.p)

    def num_at(self, sheet, q):
        return next(w.num for w in sheet.wires() if w.touches(q))

    def test_outlets_take_their_phase_with_a_letter(self):
        pdb = self.place(self.par, (5.0, 5.0))
        self.wire_pins(pdb)
        o1 = self.place(self.out, (3.0, 1.0), pdb.attrs["TAG"])
        self.wire_pins(o1, out=True)
        # (the second outlet on another sheet: the letters follow the outlets' numbers)
        self.win.add_sheet()
        s2 = self.v.sheet()
        self.assertIsNot(s2, self.s)
        o2 = self.place(self.out, (3.0, 1.0), pdb.attrs["TAG"])
        self.wire_pins(o2, out=True)
        self.number()
        tag = pdb.attrs["TAG"]
        o1 = self.s.entities[o1.id]
        o2 = s2.entities[o2.id]
        self.assertEqual((o1.attrs["OUTLET"], o2.attrs["OUTLET"]), ("1", "2"))
        self.assertEqual(o1.tag_text().text, tag + "-1")
        self.assertEqual(o2.tag_text().text, tag + "-2")
        ins = dict(self.s.entities[pdb.id].pin_points())
        for j in (1, 2, 3):
            base = self.num_at(self.s, ins["L%d" % j])
            self.assertEqual(self.num_at(self.s, dict(o1.pin_points())["T%d" % j]), base + "A")
            self.assertEqual(self.num_at(s2, dict(o2.pin_points())["T%d" % j]), base + "B")
        # (each phase its own number: L1, L2 and L3 never share one)
        self.assertEqual(len({self.num_at(self.s, q) for q in ins.values()}), 3)

    def test_too_many_outlets_are_flagged(self):
        pdb = self.place(self.par, (5.0, 5.0))
        with self.p.edit("outlets") as ed:
            ed.change(self.s, self.s.entities[pdb.id].copy(
                attrs=dict(self.s.entities[pdb.id].attrs, OUTLETS="1:2")))
        for i in range(3):
            self.place(self.out, (3.0 + 2.0 * i, 1.0), pdb.attrs["TAG"])
        over = dupes.over_outlets(self.p)
        tag = pdb.attrs["TAG"]
        self.assertEqual(list(over), [tag])
        self.assertEqual(over[tag][0], 2)
        self.assertEqual([e.attrs["OUTLET"] for _s, e in over[tag][1]], ["3"])
        self.assertTrue(dupes.marks(self.p, self.s))
        self.assertIn("outlet 3 is drawn", dupes.describe(self.p, {}, {}, over))
        self.assertEqual(dupes.outlets_allowed("1:18"), 18)
        self.assertEqual(dupes.outlets_allowed("18"), 18)
        self.assertIsNone(dupes.outlets_allowed(""))

    def test_drawn_to_fit_the_bus(self):
        with self.p.edit("bus") as ed:
            for y in (6.0, 5.25, 4.5):
                ed.add(self.s, M.Wire([(1.0, y), (9.0, y)]))
        pdb = self.place(self.par, (5.0, 6.0))
        self.assertEqual(dict(pdb.pin_points()),
                         {"L1": (5.0, 6.0), "L2": (5.0, 5.25), "L3": (5.0, 4.5)})
        self.assertIn('0.75" poles', pdb.block)
        self.assertTrue(any("drawn to fit the bus" in t for t in self.said), self.said)
        # (on a bus of its own spacing: the library's block as it is)
        with self.p.edit("bus 2") as ed:
            for y in (2.0, 1.5, 1.0):
                ed.add(self.s, M.Wire([(1.0, y), (9.0, y)]))
        pdb2 = self.place(self.par, (5.0, 2.0))
        self.assertEqual(pdb2.block, "Distribution block 3-pole")

    def test_a_copied_outlet_numbers_itself_again(self):
        pdb = self.place(self.par, (5.0, 5.0))
        o1 = self.place(self.out, (3.0, 1.0), pdb.attrs["TAG"])
        o1 = self.s.entities[o1.id]
        self.assertEqual(o1.attrs.get("OUTLET"), "1")
        got = tags.retag_copies(self.p, self.s, [o1])
        self.assertNotIn("OUTLET", got[0].attrs)


if __name__ == "__main__":
    unittest.main()
