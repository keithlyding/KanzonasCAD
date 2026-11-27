"""0.29: IEC 81346-2 letter codes in a project of IEC 60617 symbols (tags.prefix_for): a relay
K, a contactor or a breaker Q, a pushbutton S, a terminal strip X... instead of the US prefixes;
a JIC project unchanged; a tag of the other letters kept, still following its page, until the
sheet is renumbered; contacts, footprints, copies, saved circuits and the duplicate-tag check
with the new letters."""

import tempfile
import unittest

from tests.util import window, type_in

from kanzonascad import commands as C
from kanzonascad import dupes
from kanzonascad import model as M
from kanzonascad import tags
from kanzonascad.library import Library

# IEC 81346-2:2019's main classes (Table 1)
CLASSES = set("ABCEFGHKMPQRSTUVWXYZ")


class LettersTest(unittest.TestCase):
    def setUp(self):
        self.syms = Library(tempfile.mkdtemp()).builtins("symbol")
        self.jic, self.iec = M.Project.new(), M.Project.new()
        self.iec.settings["symbol_standard"] = "iec"

    def test_jic_project_keeps_the_us_prefixes(self):
        for b in self.syms.values():
            self.assertEqual(tags.prefix_for(self.jic, b), b.prefix, b.name)

    def test_every_builtin_device_takes_an_81346_class_letter(self):
        for b in self.syms.values():
            if b.prefix:
                self.assertIn(tags.prefix_for(self.iec, b), CLASSES, b.name)
        want = {"Relay coil (IEC)": "K", "Timer coil (IEC)": "K", "Contact NO (IEC)": "K",
                "Contactor coil (IEC)": "Q", "Contactor main contacts 3-pole (IEC)": "Q",
                "Circuit breaker 3-pole (IEC)": "Q", "Disconnector 3-pole (IEC)": "Q",
                "Motor protection circuit breaker 3-pole": "Q",
                "Pushbutton NO (IEC)": "S", "Emergency stop NC (IEC)": "S",
                "Selector switch 3-position": "S", "Limit switch NO": "B",
                "Pressure switch NO": "B", "Power supply AC/DC": "T",
                "Fuse (IEC)": "F", "Thermal overload 3-pole (IEC)": "F",
                "Overload contact NC (IEC)": "F", "Indicator lamp (IEC)": "P",
                "Motor 3-phase (IEC)": "M", "Control transformer (IEC)": "T",
                "Variable frequency drive": "T", "Terminal strip": "X", "Terminal (IEC)": "X",
                "Distribution block 3-pole": "X", "1734-IB8 module": "K"}
        for name, letter in want.items():
            self.assertEqual(tags.prefix_for(self.iec, self.syms[name]), letter, name)

    def test_a_prefix_of_your_own_is_kept(self):
        mine = M.BlockDef("Horn", "symbol", [], [], (0, 0.2), 0.1, "Mine", "", "device", "",
                          "HN")
        self.assertEqual(tags.prefix_for(self.iec, mine), "HN")


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
        type_in(self.v, at, *typed)
        return [e for e in self.s.inserts() if e.block == name][-1]

    def test_devices_tagged_with_81346_letters(self):
        coil = self.place("Relay coil (IEC)", "8,5")
        k = self.place("Contact NO (IEC)", "3,5", "K101")
        km = self.place("Contactor coil (IEC)", "8,4")
        cb = self.place("Circuit breaker 3-pole (IEC)", "3,2")
        pb = self.place("Pushbutton NO (IEC)", "3,4")
        strip = self.place("Terminal strip", "12,7")
        self.assertEqual([e.attrs["TAG"] for e in (coil, km, cb, pb, strip)],
                         ["K101", "Q101", "Q102", "S101", "X101"])
        # (a contact shows its coil's tag, as in any project)
        k = self.s.entities[k.id]
        self.assertEqual((k.attrs["PARENT"], k.attrs["TAG"]), (coil.attrs["DEV"], "K101"))
        # (Renumber sheet: one count for every Q, the contactor and the breaker)
        with self.p.edit("renumber") as ed:
            tags.renumber_sheet(ed, self.p, self.s)
        got = sorted(e.attrs["TAG"] for e in self.s.inserts() if tags.is_device(e))
        self.assertEqual(got, ["K101", "Q101", "Q102", "S101", "X101"])

    def test_tags_from_before_kept_following_their_page_until_renumbered(self):
        with self.p.edit("JIC") as ed:
            ed.project_settings(dict(self.p.settings, symbol_standard="jic"))
        coil = self.place("Relay coil (IEC)", "8,5")
        self.assertEqual(coil.attrs["TAG"], "CR101")
        with self.p.edit("IEC") as ed:
            ed.project_settings(dict(self.p.settings, symbol_standard="iec"))
        self.assertEqual(self.s.entities[coil.id].attrs["TAG"], "CR101")   # (kept)
        with self.p.edit("page") as ed:
            ed.sheet_meta(self.s, number="2")
        self.assertEqual(self.s.entities[coil.id].attrs["TAG"], "CR201")   # (follows)
        with self.p.edit("fix") as ed:
            tags.fix_sheet(ed, self.p, self.s)                # (Update numbers, only fix)
        self.assertEqual(self.s.entities[coil.id].attrs["TAG"], "CR201")
        new = self.place("Relay coil (IEC)", "8,3")
        self.assertEqual(new.attrs["TAG"], "K201")
        with self.p.edit("renumber") as ed:
            tags.renumber_sheet(ed, self.p, self.s)
        self.assertEqual(sorted(e.attrs["TAG"] for e in self.s.inserts()
                                if tags.is_device(e)), ["K201", "K202"])

    def test_copies_and_saved_circuits_take_the_letters(self):
        coil = self.place("Relay coil (IEC)", "8,5")
        old = M.Insert("Relay coil (IEC)", (8, 3), defn=coil.defn,
                       attrs=dict(coil.attrs, TAG="CR105"))
        made = tags.retag_copies(self.p, self.s, [old])
        self.assertEqual(made[0].attrs["TAG"], "K105")      # (its count kept)
        self.place("Contact NO (IEC)", "3,5", "K101")
        self.v.set_selection(set(self.s.entities))
        self.win.ask_circuit_details = lambda name_="": ("Rung", "Control", "")
        try:
            self.v.run(C.SaveCircuitCmd)
            self.v.cmd.enter()
        finally:
            self.win.__dict__.pop("ask_circuit_details", None)
        c = self.lib.circuits()[0]["Rung"]
        self.win.ask_circuit = lambda: c
        try:
            self.win.insert_circuit()
        finally:
            self.win.__dict__.pop("ask_circuit", None)
        type_in(self.v, "1,1")
        coils = sorted(e.attrs["TAG"] for e in self.s.inserts() if e.block == "Relay coil (IEC)")
        self.assertEqual(coils, ["K101", "K102"])
        k = [e for e in self.s.inserts() if e.block == "Contact NO (IEC)"]
        self.assertEqual(sorted(e.attrs["TAG"] for e in k), ["K101", "K102"])

    def test_duplicate_letter_tags_found(self):
        a = self.place("Relay coil (IEC)", "8,5")
        b = self.place("Timer coil (IEC)", "8,3")
        self.assertEqual(b.attrs["TAG"], "K102")         # (a timer shares the relays' K)
        with self.p.edit("dup") as ed:
            ed.change(self.s, self.s.entities[b.id].copy(
                attrs=dict(b.attrs, TAG="K101", TAG_LOCK="1")))
        dup_tags = dupes.find(self.p)[0]
        self.assertIn("K101", dup_tags)
        self.assertEqual(a.attrs["TAG"], "K101")


if __name__ == "__main__":
    unittest.main()
