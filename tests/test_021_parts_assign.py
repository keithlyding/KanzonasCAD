"""Parts on devices (the roadmap's item 6 and the owner's "Save to library as part", Nov 2026):
Assign part puts one library part on every selected device that uses its symbol, in one edit,
the project's brand listed first, a copy of the part kept in the project; Save to library as
part makes a part of a placed device (its maker, catalog number, description, symbol and the
footprint linked to it)."""
import tempfile
import unittest

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import partsassign as PA
from kanzonascad.library import Library, Part


class PartsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.win.library = Library(tempfile.mkdtemp())
        self.lib = self.win.library
        self.p = self.v.project
        self.s = self.v.sheet()
        self.said = []
        self.win._say = lambda text, *a: self.said.append(text)
        lib = self.lib
        coil = lib.get("symbol", "Contactor coil")
        relay = lib.get("symbol", "Relay coil")
        with self.p.edit("devices") as ed:
            self.m = [ed.add(self.s, M.Insert(coil.name, (2.0 + 2 * i, 2.0), 0.0, 1.0, False,
                                              {"TAG": "M%d" % (i + 1)}, coil, 0.1))
                      for i in range(3)]
            self.cr = ed.add(self.s, M.Insert(relay.name, (2.0, 5.0), 0.0, 1.0, False,
                                              {"TAG": "CR1"}, relay, 0.1))
        self.ab = Part(manufacturer="Allen-Bradley", catalog="100-C09D10",
                       description="Contactor 9A", symbol="Contactor coil")
        self.sie = Part(manufacturer="Siemens", catalog="3RT2015", description="Contactor",
                        symbol="Contactor coil")
        for part in (self.ab, self.sie):
            lib.save_part(part)

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_assigned_to_every_selected_device_of_its_symbol(self):
        self.v.set_selection({e.id for e in self.m} | {self.cr.id})
        offered = []

        def ask(parts, brand):
            offered.append(([p.catalog for p in parts], brand))
            return self.sie.id, "Siemens"
        self.win.ask_part = ask
        self.assertEqual(self.win.assign_part(), 3)
        # (yours, and the program's own Allen-Bradley parts of the selected symbols since
        # 0.29: yours standing for the built-in one of its catalog number)
        builtin = sorted(p.catalog for p in self.lib.builtin_parts().values()
                         if p.symbol in ("Contactor coil", "Relay coil") and
                         p.catalog != "100-C09D10")
        self.assertEqual(offered[0], (["100-C09D10"] + builtin + ["3RT2015"], ""))
        for e in self.m:
            a = self.s.entities[e.id].attrs
            self.assertEqual((a["MFR"], a["CAT"], a["PART"]), ("Siemens", "3RT2015",
                                                               self.sie.id))
            self.assertEqual(a["TAG"], e.attrs["TAG"])
        self.assertNotIn("CAT", self.s.entities[self.cr.id].attrs)   # (another symbol)
        self.assertTrue(any("use another symbol" in t for t in self.said))
        self.assertEqual(self.p.settings["parts"][self.sie.id]["catalog"], "3RT2015")
        self.assertEqual(self.p.settings["brand"], "Siemens")
        # (the brand first next time)
        self.assertEqual([p.catalog for p in PA.candidates(self.lib, self.m, "siemens")],
                         ["3RT2015", "100-C09D10"] + [c for c in builtin
                                                      if c.startswith("100-")])
        # (the library's part gone: the drawing keeps its own copy)
        self.lib.delete_part(self.sie.id)
        self.assertEqual(self.p.settings["parts"][self.sie.id]["manufacturer"], "Siemens")
        self.p.undo()
        self.assertNotIn("CAT", self.s.entities[self.m[0].id].attrs)

    def test_nothing_selected_or_no_part(self):
        self.v.set_selection(set())
        self.assertEqual(self.win.assign_part(), 0)
        self.assertTrue(any("select the devices" in t for t in self.said))
        # (a symbol no part uses, built-in parts included: a relay coil has some since 0.29)
        timer = self.lib.get("symbol", "Timer coil")
        with self.p.edit("timer") as ed:
            tr = ed.add(self.s, M.Insert(timer.name, (6.0, 5.0), 0.0, 1.0, False,
                                         {"TAG": "TR1"}, timer, 0.1))
        self.v.set_selection({tr.id})
        self.assertEqual(self.win.assign_part(), 0)
        self.assertTrue(any("No part in your library uses Timer coil" in t for t in self.said))

    def test_save_to_library_as_part(self):
        self.v.set_selection({self.cr.id})
        self.assertIsNone(self.win.save_as_part())
        self.assertTrue(any("catalog number first" in t for t in self.said))
        with self.p.edit("cat") as ed:
            ed.change(self.s, self.s.entities[self.cr.id].copy(attrs=dict(
                self.s.entities[self.cr.id].attrs, MFR="AB", CAT="700-HC14Z24",
                DESC="Relay 24 VDC")))
        part = self.win.save_as_part()
        self.assertEqual((part.manufacturer, part.catalog, part.description, part.symbol),
                         ("AB", "700-HC14Z24", "Relay 24 VDC", "Relay coil"))
        got = [p for p in self.lib.parts() if p.catalog == "700-HC14Z24"]
        self.assertEqual(len(got), 1)
        again = self.win.save_as_part()                 # (the same part: updated, not twice)
        self.assertEqual(again.id, got[0].id)
        self.assertEqual(len([p for p in self.lib.parts() if p.catalog == "700-HC14Z24"]), 1)
        self.v.set_selection({e.id for e in self.m})
        self.assertIsNone(self.win.save_as_part())
        self.assertTrue(any("select one device" in t for t in self.said))


if __name__ == "__main__":
    unittest.main()
