"""0.29 with 0.28: contact pin numbers (pinnumbers.py) and panel wiring (panelwiring.py) in a
project of IEC 60617 symbols, its tags in IEC 81346-2 letters (K101, X101): numbers come per
device by its hidden id, never by tag letters; every built-in contact (JIC, Allen-Bradley and
IEC) shows its numbers; a saved circuit's contacts keep their numbers on the new device."""

import tempfile
import unittest

from tests.util import window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import panelwiring as PW
from kanzonascad import pinnumbers as PN
from kanzonascad.library import Library


class ContactPinsShownTest(unittest.TestCase):
    def test_every_builtin_contact_shows_its_numbers(self):
        syms = Library(tempfile.mkdtemp()).builtins("symbol")
        contacts = [b for b in syms.values() if b.contact and len(b.pins) == 2 and
                    all(p["name"].isdigit() for p in b.pins)]
        names = {b.name for b in contacts}
        # (the IEC ones and the Allen-Bradley ones are made apart from the JIC list)
        self.assertTrue({"Contact NO (IEC)", "Overload contact NC (IEC)",
                         "Overload contact NO", "Selector switch 3-position contact, closed left"}
                        <= names, names)
        self.assertEqual([b.name for b in contacts if not b.show_pins], [])


class IECProjectTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.polar_on = self.v.ortho_on = False
        self.p, self.s = self.v.project, self.v.sheet()
        self.lib = self.win.library = Library(tempfile.mkdtemp())
        with self.p.edit("IEC") as ed:
            ed.project_settings(dict(self.p.settings, symbol_standard="iec"))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def place(self, name, at, *typed):
        self.v.run(C.InsertCmd, self.lib.get("symbol", name), {})
        type_in(self.v, "%g,%g" % at, *typed)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        return [e for e in self.s.inserts() if e.block == name][-1]

    def test_contacts_numbered_on_a_k_device(self):
        coil = self.place("Relay coil (IEC)", (10, 8))
        self.assertTrue(coil.attrs["TAG"].startswith("K"), coil.attrs)
        got = []
        for i, n in enumerate(("Contact NO (IEC)", "Contact NC (IEC)", "Contact NO (IEC)")):
            k = self.place(n, (3 + 2 * i, 8), coil.attrs["TAG"])
            k = self.s.entities[k.id]
            self.assertEqual(k.attrs.get("PARENT"), coil.attrs["DEV"])
            got.append(PN.numbers(k))
        self.assertEqual(got, [["13", "14"], ["21", "22"], ["33", "34"]])

    def test_wiring_list_with_x_strips_and_k_devices(self):
        coil = self.place("Relay coil (IEC)", (10, 8))
        strip = self.place("Terminal strip", (2, 12))
        self.assertTrue(strip.attrs["TAG"].startswith("X"), strip.attrs)
        term = self.place("Terminal (IEC)", (14, 8), strip.attrs["TAG"])
        term = self.s.entities[term.id]
        self.assertEqual(term.attrs.get("PARENT"), strip.attrs["DEV"], term.attrs)
        num = term.attrs["TERM"]
        a2 = dict(self.s.entities[coil.id].pin_points())["A2"]
        t1 = dict(term.pin_points())[term.defn.pins[0]["name"]]
        with self.p.edit("wire") as ed:
            ed.add(self.s, M.Wire([a2, t1]))
        rows = PW.rows(self.p)
        k, x = coil.attrs["TAG"], strip.attrs["TAG"]
        self.assertTrue(any(r[0] == k and r[1] == "A2" and r[6] == "%s-%s" % (x, num) for r in rows),
                        [r[:7] for r in rows])
        self.assertTrue(any(r[0] == "%s-%s" % (x, num) and r[6] == k + ":A2" for r in rows),
                        [r[:7] for r in rows])

    def test_saved_circuit_keeps_its_contacts_numbers(self):
        coil = self.place("Relay coil (IEC)", (10, 5))
        self.place("Contact NC (IEC)", (3, 5), coil.attrs["TAG"])
        self.place("Contact NO (IEC)", (5, 5), coil.attrs["TAG"])
        self.v.set_selection(set(self.s.entities))
        self.win.ask_circuit_details = lambda name_="": ("Rung", "Control", "")
        try:
            self.v.run(C.SaveCircuitCmd)
            self.v.cmd.enter()
        finally:
            self.win.__dict__.pop("ask_circuit_details", None)
        c = self.lib.circuits()[0]["Rung"]
        before = set(self.s.entities)
        self.win.ask_circuit = lambda: c
        try:
            self.win.insert_circuit()
        finally:
            self.win.__dict__.pop("ask_circuit", None)
        type_in(self.v, "3,2")
        self.assertIsNone(self.v.cmd)
        new = [e for i, e in self.s.entities.items() if i not in before and
               isinstance(e, M.Insert)]
        coil2 = [e for e in new if e.block == "Relay coil (IEC)"][0]
        self.assertTrue(coil2.attrs["TAG"].startswith("K"))
        self.assertNotEqual(coil2.attrs["TAG"], coil.attrs["TAG"])
        got = {e.block: (e.attrs.get("PARENT"), PN.numbers(e)) for e in new if e.defn.contact}
        self.assertEqual(got, {"Contact NC (IEC)": (coil2.attrs["DEV"], ["21", "22"]),
                               "Contact NO (IEC)": (coil2.attrs["DEV"], ["13", "14"])})


if __name__ == "__main__":
    unittest.main()
