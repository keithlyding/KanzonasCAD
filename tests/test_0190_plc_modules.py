"""PLC I/O modules drawn whole (the owner, 0.19: "generic plc i/o schematic symbols ...
somewhat flexible (e.g., number of points). Also, not all i/o is wired the same. But in this
case, I need 1734-IB8, OB8(E), IE8C, and OE4C"; asked: one box for the whole module): each
terminal a pin on a rung with its number and what it is, as Rockwell's wiring diagrams give."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import bom
from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import symbols_jic as SJ


def terminals(defn):
    return [(p["name"], round(p["pos"][1], 6)) for p in defn.pins]


def texts(defn):
    return [t.text for t in defn.entities if isinstance(t, M.Text)]


class ModuleTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p, self.s = self.v.project, self.v.sheet()
        self.lib = self.win.library

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_terminal_maps(self):
        d = self.lib.get("symbol", "1734-IB8 module")
        self.assertEqual(terminals(d), [(str(i), -0.5 * i) for i in range(8)])
        self.assertEqual(texts(d), ["1734-IB8"] + ["%d  IN %d" % (i, i) for i in range(8)])
        self.assertEqual((d.catalog, d.manufacturer, d.prefix, d.role),
                         ("1734-IB8", "Allen-Bradley", "PLC", "parent"))
        for cat in ("1734-OB8", "1734-OB8E"):
            self.assertEqual(texts(self.lib.get("symbol", cat + " module"))[1:],
                             ["%d  OUT %d" % (i, i) for i in range(8)])
        self.assertEqual(texts(self.lib.get("symbol", "1734-IE8C module"))[1:],
                         ["%d  IN %d" % (i, i) for i in range(8)])
        # (the 4-channel current output: its own C and V on terminals 4-7)
        self.assertEqual(texts(self.lib.get("symbol", "1734-OE4C module"))[1:],
                         ["0  OUT 0", "1  OUT 1", "2  OUT 2", "3  OUT 3", "4  C", "5  C",
                          "6  V", "7  V"])
        self.assertEqual(set(texts(self.lib.get("symbol", "1734-VTM module"))[1:]),
                         {"%d  V" % i for i in range(8)})
        self.assertEqual(set(texts(self.lib.get("symbol", "1734-CTM module"))[1:]),
                         {"%d  C" % i for i in range(8)})

    def test_generic_sizes(self):
        for kind, word, n in SJ.IO_GENERIC:
            d = self.lib.get("symbol", "PLC %s module, %d points" % (kind, n))
            self.assertEqual(len(d.pins), n)
            self.assertEqual(texts(d)[-1], "%d  %s %d" % (n - 1, word, n - 1))

    def test_placed_wired_and_listed(self):
        self.v.run(C.InsertCmd, self.lib.get("symbol", "1734-IB8 module"), {"SLOT": "3"})
        type_in(self.v, "8,9")
        self.v.cancel()
        mod = [e for e in self.s.inserts() if e.block == "1734-IB8 module"][0]
        self.assertTrue(mod.attrs["TAG"].startswith("PLC"))
        with self.p.edit("wires") as ed:
            for _n, q in mod.pin_points()[:2]:
                ed.add(self.s, M.Wire([(q[0] - 2.0, q[1]), q]))
        nums = {w.num for w in self.s.wires()}
        self.assertEqual(len(nums), 2)                  # (each point its own wire number)
        shown = [t.text for t in mod.world_entities() if isinstance(t, M.Text)]
        self.assertIn("3", shown)                       # (its slot)
        rows = bom.rows(self.p)
        self.assertTrue(any(r["cat"] == "1734-IB8" and r["mfr"] == "Allen-Bradley"
                            for r in rows), rows)
        # a PLC input point can belong to it, as a contact to its coil
        from kanzonascad import tags
        self.assertIn(mod.attrs["TAG"], [d.attrs["TAG"] for _s, d in
                                         tags.candidates(self.p, self.s, "PLC", (0, 0))])


if __name__ == "__main__":
    unittest.main()
