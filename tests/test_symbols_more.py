import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import tags, wirenums


class MoreSymbolsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = False
        self.p = self.v.project
        self.lib = self.win.library
        with self.p.edit("page 6") as ed:
            ed.sheet_meta(self.v.sheet(), number="6")

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def place(self, name, at, *more):
        self.v.run(C.InsertCmd, self.lib.get("symbol", name), {})
        type_in(self.v, "%g,%g" % at, *more)
        return max((e for e in self.v.sheet().entities.values() if isinstance(e, M.Insert)),
                   key=lambda e: e.id)

    def now(self, e):
        return self.v.sheet().entities[e.id]

    def test_three_pole_symbols_line_up_with_a_bus(self):
        # a 3-wire bus at 1/2 inch, then the breaker dropped on it: each pole cuts its wire
        self.v.run(C.BusCmd)
        type_in(self.v, "3", "0.5", "1,6.5", "8,6.5", "")
        cb = self.place("Circuit breaker 3-pole", (4, 6))
        pins = dict(cb.pin_points())
        self.assertEqual([pins["L%d" % i][1] for i in (1, 2, 3)], [6.5, 6.0, 5.5])
        self.assertEqual(len({w.num for w in self.v.sheet().wires()}), 6)
        self.assertEqual(self.now(cb).attrs["TAG"], "CB601")

    def test_power_contacts_belong_to_the_contactor(self):
        coil = self.place("Contactor coil", (3, 2))
        k = self.place("Contactor power contacts 3-pole", (4, 7), "")
        self.assertEqual(self.now(k).attrs.get("PARENT"), coil.attrs["DEV"])
        self.assertEqual(self.now(k).attrs["TAG"], "M601")

    def test_terminals_number_themselves_on_their_strip(self):
        strip = self.place("Terminal strip", (12, 2))
        a = self.place("Terminal", (3, 8), "")
        b = self.place("Terminal", (3, 7), "")
        self.assertEqual([self.now(t).attrs.get("TERM") for t in (a, b)], ["1", "2"])
        self.assertEqual(self.now(a).attrs["TAG"], strip.attrs["TAG"])
        # the number shows on the drawing
        texts = [w.text for w in self.now(a).world_entities() if isinstance(w, M.Text)]
        self.assertIn("1", texts)
        # a copy takes the next free number
        self.v.set_selection({a.id})
        self.v.run(C.CopyCmd)
        type_in(self.v, "3,8", "6,8", "")
        terms = sorted(e.attrs.get("TERM") for e in self.v.sheet().inserts() if tags.numbered(e))
        self.assertEqual(terms, ["1", "2", "3"])

    def test_plc_points_list_under_their_card(self):
        from kanzonascad import xrefs
        card = self.place("PLC I/O card", (12, 3))
        pt = self.place("PLC input", (3, 8), "")
        with self.p.edit("addr") as ed:
            ed.change(self.v.sheet(), self.now(pt).copy(
                attrs=dict(self.now(pt).attrs, ADDR="I:0/3")))
        self.assertEqual(self.now(pt).attrs["PARENT"], card.attrs["DEV"])
        texts = [w.text for w in self.now(pt).world_entities() if isinstance(w, M.Text)]
        self.assertIn("I:0/3", texts)
        self.assertIn(self.p.zone_text(self.v.sheet(), 3, 8),
                      [t[2] for t in xrefs.live(self.p, self.v.sheet())])

    def test_every_builtin_symbol_survives_saving(self):
        from kanzonascad.symbols_jic import builtin_symbols
        new = {"Circuit breaker 3-pole", "Disconnect 3-pole", "Fuses 3-pole",
               "Contactor power contacts 3-pole", "Overload heaters 3-pole", "Motor 3-phase",
               "Variable frequency drive", "Power supply AC/DC", "PLC input", "PLC output",
               "Distribution block 4-way", "Off-sheet connector"}
        for d in builtin_symbols():
            again = M.BlockDef.from_dict(d.to_dict())
            self.assertEqual(again.to_dict(), d.to_dict(), d.name)
            for p in (d.pins if d.name in new else []):     # pins on the 1/8 inch snap
                for c in p["pos"]:
                    self.assertAlmostEqual(c * 8, round(c * 8), msg="%s pin %s" % (d.name, p))


if __name__ == "__main__":
    unittest.main()
