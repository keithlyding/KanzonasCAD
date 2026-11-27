"""0.29: the Allen-Bradley PLC modules' pins (the owner, Nov 27 2026, "Both"): named by
Rockwell's terminal numbers with the point beside each ("2  IN 0") for a module whose terminal
block is in allen_bradley.TERMINALS (all 13, from the Rockwell publications cited there; the
1769 ones by position from the top, Rockwell printing no screw numbers), else by point; wire
numbers by address and Import I/O list go by the point either way, never by the pin's name;
the wiring list and terminal wire labels name the pin by its screw number (PLC1:11)."""

import unittest
from unittest import mock

from tests.util import APP, window, type_in

from kanzonascad import allen_bradley as AB
from kanzonascad import autolayer
from kanzonascad import commands as C
from kanzonascad import io_list
from kanzonascad import model as M
from kanzonascad import panelwiring as PW
from kanzonascad import tags
from kanzonascad import wirenums
from kanzonascad.wirenums import io_address

# a terminal block whose numbers aren't its points (as a 20-pin RTB's: points on the even
# terminals, commons after them): made up here, only to test the drawing of one
MADE_UP = ("a test, not a Rockwell publication",
           [("2", "IN 0"), ("4", "IN 1"), ("1", "IN 2"), ("3", "IN 3"),
            ("5", "GND-0"), ("6", "GND-0")])


def module(cat):
    return next(b for b in AB.ab_io_modules() if b.catalog == cat)


def drawn(b):
    """[(pin name, the text beside it)] of a module, top to bottom (worked out from its
    drawing: the text on each pin's row)."""
    out = []
    for p in sorted(b.pins, key=lambda p: -p["pos"][1]):
        y = p["pos"][1]
        texts = [e.text for e in b.entities if isinstance(e, M.Text) and
                 abs(e.pos[1] - (y - 0.03)) < 1e-9]
        assert len(texts) == 1, (b.name, p, texts)
        name, _sep, what = texts[0].partition("  ")
        assert name == p["name"], (b.name, p["name"], texts[0])
        out.append((name, what))
    return out


def points(b):
    """{pin: (I or O, point)} as io_points finds them."""
    return wirenums.io_points(b)


class TerminalsTest(unittest.TestCase):
    def test_by_point_without_rockwells_numbers(self):
        with mock.patch.dict(AB.TERMINALS, clear=True):
            for cat, _fam, _desc, word, n in AB.IO:
                b = module(cat)
                self.assertEqual([p["name"] for p in b.pins], [str(i) for i in range(n)], cat)
                self.assertIn("named by point", b.description, cat)
                self.assertEqual(wirenums.io_points(b),
                                 {str(i): (word[0], i) for i in range(n)}, cat)

    def test_terminal_numbers_with_the_point_beside(self):
        with mock.patch.dict(AB.TERMINALS, {"1769-IQ16": MADE_UP}):
            b = module("1769-IQ16")
        self.assertEqual([p["name"] for p in b.pins], ["2", "4", "1", "3", "5", "6"])
        texts = {e.text for e in b.entities if isinstance(e, M.Text)}
        self.assertTrue({"2  IN 0", "4  IN 1", "1  IN 2", "5  GND-0"} <= texts, texts)
        self.assertIn(MADE_UP[0], b.description)
        # wire numbers by address: the point of each pin, not its name; a common none
        self.assertEqual(wirenums.io_points(b), {"2": ("I", 0), "4": ("I", 1),
                                                 "1": ("I", 2), "3": ("I", 3)})
        pts = wirenums.io_points(b)
        self.assertEqual(io_address(*pts["1"], {"SLOT": "4"}), "I:4/2")
        # Import I/O list: point 0's text goes beside terminal 2
        self.assertEqual(io_list._point_pins(b), {0: "2", 1: "4", 2: "1", 3: "3"})

    def test_every_module_from_a_cited_publication(self):
        self.assertEqual(set(AB.TERMINALS), {row[0] for row in AB.IO})
        for cat, (pub, terms) in AB.TERMINALS.items():
            b = module(cat)
            self.assertEqual(drawn(b), terms, cat)
            self.assertEqual(len({t for t, _w in terms}), len(terms), cat)   # (no screw twice)
            self.assertIn(pub, b.description, cat)
            self.assertTrue(pub.startswith(cat[:4]), (cat, pub))
            # (a module of points: as many as its catalog says, each once or, an analog
            # channel with a voltage and a current terminal, twice)
            word, n = next((r[3], r[4]) for r in AB.IO if r[0] == cat)
            self.assertEqual(sorted(set(points(b).values())),
                             [(word[0], i) for i in range(n)], cat)
            # (a point's text from Import I/O list goes beside its first terminal, top down)
            want = {}
            for t, _w in terms:
                if t in points(b):
                    want.setdefault(points(b)[t][1], t)
            self.assertEqual(io_list._point_pins(b), want, cat)

    def test_controllogix_1756(self):
        ib = drawn(module("1756-IB16"))
        self.assertEqual(ib[:2], [("1", "IN-0"), ("2", "IN-1")])
        self.assertEqual(ib[8:12], [("9", "GND-0"), ("10", "GND-0"), ("11", "IN-8"),
                                    ("12", "IN-9")])
        self.assertEqual(ib[-1], ("20", "GND-1"))
        self.assertEqual(points(module("1756-IB16"))["18"], ("I", 15))
        ob = dict(drawn(module("1756-OB16E")))
        self.assertEqual((ob["9"], ob["10"], ob["19"], ob["20"]),
                         ("RTN OUT-0", "DC-0(+)", "RTN OUT-1", "DC-1(+)"))
        self.assertEqual(points(module("1756-OB16E"))["11"], ("O", 8))
        self.assertNotIn("9", points(module("1756-OB16E")))         # (a return: no point)
        f = dict(drawn(module("1756-IF8")))
        self.assertEqual(len(f), 36)
        self.assertEqual((f["1"], f["2"], f["9"], f["10"], f["27"], f["36"]),
                         ("i RTN-0", "IN-0", "RTN", "RTN", "RTN", "Not used"))
        self.assertEqual(points(module("1756-IF8")),
                         {"2": ("I", 0), "4": ("I", 1), "6": ("I", 2), "8": ("I", 3),
                          "12": ("I", 4), "14": ("I", 5), "16": ("I", 6), "18": ("I", 7)})
        of8 = module("1756-OF8")
        self.assertEqual(dict(drawn(of8))["2"], "VOUT-4")
        # (a channel's voltage and current terminals both its point; RTN none)
        self.assertEqual((points(of8)["1"], points(of8)["3"], points(of8)["2"]),
                         (("O", 0), ("O", 0), ("O", 4)))
        self.assertNotIn("5", points(of8))

    def test_compactlogix_1769_by_position(self):
        iq = module("1769-IQ16")
        self.assertIn("by position from the top", iq.description)
        d = dict(drawn(iq))
        self.assertEqual([p["name"] for p in iq.pins], [str(i) for i in range(1, 19)])
        self.assertEqual((d["1"], d["9"], d["10"], d["11"], d["18"]),
                         ("IN 0", "DC COM 1", "IN 9", "IN 8", "DC COM 2"))
        self.assertEqual((points(iq)["10"], points(iq)["11"]), (("I", 9), ("I", 8)))
        ob = dict(drawn(module("1769-OB16")))
        self.assertEqual((ob["1"], ob["2"], ob["17"], ob["18"]),
                         ("+VDC", "OUT 0", "OUT 15", "DC COM"))
        ow = dict(drawn(module("1769-OW8")))
        self.assertEqual([ow[str(i)] for i in (1, 4, 5, 10, 11, 12, 15, 18)],
                         ["(blank)", "(blank)", "VAC-VDC 1", "VAC-VDC 2", "OUT 5", "OUT 4",
                          "(blank)", "(blank)"])
        f4 = module("1769-IF4")
        d = dict(drawn(f4))
        self.assertEqual([d[str(i)] for i in (1, 2, 3, 4, 17, 18)],
                         ["V in 0+", "V/I in 0-", "I in 0+", "ANLG Com", "+24V dc", "dc NEUT"])
        self.assertEqual((points(f4)["1"], points(f4)["3"], points(f4)["13"]),
                         (("I", 0), ("I", 0), ("I", 3)))
        self.assertNotIn("2", points(f4))                           # (V/I in 0-: a return)
        # 1769-OF2: positions 1-4 and 15-18 blacked out, no screw: no pin
        of2 = module("1769-OF2")
        self.assertEqual(drawn(of2), [
            ("5", "V out 0+"), ("6", "I out 0+"), ("7", "ANLG Com"), ("8", "NC"),
            ("9", "V out 1+"), ("10", "I out 1+"), ("11", "ANLG Com"), ("12", "NC"),
            ("13", "+24V dc"), ("14", "dc NEUT")])
        self.assertEqual(points(of2), {"5": ("O", 0), "6": ("O", 0), "9": ("O", 1),
                                       "10": ("O", 1)})

    def test_compact_5000_5069(self):
        ib = drawn(module("5069-IB16"))
        self.assertEqual(ib[0], ("0", "IN 0"))
        self.assertEqual(ib[15:], [("15", "IN 15"), ("16", "No Connect"),
                                   ("17", "No Connect")])
        ob = module("5069-OB16")
        self.assertEqual(drawn(ob)[16:], [("16", "LA+"), ("17", "LA-")])
        self.assertIn("counted from the top", ob.description)
        self.assertEqual(points(ob)["15"], ("O", 15))

    def test_point_io_1734(self):
        self.assertEqual(drawn(module("1734-IB4")),
                         [("0", "In 0"), ("1", "In 1"), ("2", "In 2"), ("3", "In 3"),
                          ("4", "C"), ("5", "C"), ("6", "V"), ("7", "V")])
        self.assertEqual(points(module("1734-IB4")), {str(i): ("I", i) for i in range(4)})
        ob = module("1734-OB4E")
        self.assertEqual(drawn(ob)[4:], [(str(i), "C") for i in range(4, 8)])
        self.assertEqual(points(ob), {str(i): ("O", i) for i in range(4)})

    def test_auto_wire_layer_of_rockwells_labels(self):
        for cat, pin, want in (("1756-OF8", "3", "24VDC BLU"),           # (IOUT-0)
                               ("1756-OF8", "5", "24VDC BLU-WHT"),       # (RTN)
                               ("1756-IB16", "9", "24VDC BLU-WHT"),      # (GND-0)
                               ("1756-OB16E", "10", "24VDC BLU"),        # (DC-0(+))
                               ("1756-OB16E", "9", "24VDC BLU-WHT"),     # (RTN OUT-0)
                               ("1769-IQ16", "9", "24VDC BLU-WHT"),      # (DC COM 1)
                               ("1769-OB16", "1", "24VDC BLU"),          # (+VDC)
                               ("1769-IF4", "1", "24VDC BLU"),           # (V in 0+)
                               ("1769-IF4", "2", "24VDC BLU-WHT"),       # (V/I in 0-)
                               ("1769-OF2", "7", "24VDC BLU-WHT"),       # (ANLG Com)
                               ("1769-OF2", "13", "24VDC BLU"),          # (+24V dc)
                               ("5069-OB16", "16", "24VDC BLU"),         # (LA+)
                               ("5069-OB16", "17", "24VDC BLU-WHT"),     # (LA-)
                               ("1734-IB4", "0", "24VDC BLU"),           # (In 0)
                               ("1769-OF2", "8", None),                  # (NC)
                               ("5069-IB16", "16", None)):               # (No Connect)
            self.assertEqual(autolayer.block_layer(module(cat), pin), want, (cat, pin))


class InAProjectTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p, self.s = self.v.project, self.v.sheet()
        self.lib = self.win.library

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def place(self, block, at, attrs):
        before = set(self.s.entities)
        self.v.run(C.InsertCmd, self.lib.get("symbol", block), attrs)
        type_in(self.v, at)
        self.v.cancel()
        return next(e for i, e in self.s.entities.items()
                    if i not in before and isinstance(e, M.Insert))

    def wire_to(self, mod, pin, run=2.0):
        q = dict(mod.pin_points())[pin]
        with self.p.edit("wire") as ed:
            w = ed.add(self.s, M.Wire([q, (q[0] - run, q[1]), (q[0] - run, q[1] + 0.1)]))
        return w.id

    def num(self, wid):
        return self.s.entities[wid].num

    def test_wire_numbers_by_address_follow_the_point(self):
        iq = self.place("1769-IQ16 module", "12,9", {"SLOT": "4"})
        of8 = self.place("1756-OF8 module", "20,9", {"SLOT": "7"})
        ib = self.place("5069-IB16 module", "28,9", {"SLOT": "2"})
        ws = {"iq 11": self.wire_to(iq, "11"),          # (position 11: IN 8)
              "iq 10": self.wire_to(iq, "10"),          # (position 10: IN 9)
              "iq 1": self.wire_to(iq, "1"),            # (IN 0)
              "iq 9": self.wire_to(iq, "9"),            # (DC COM 1: no point)
              "of8 3": self.wire_to(of8, "3", -2.0),    # (IOUT-0)
              "of8 2": self.wire_to(of8, "2", -2.0),    # (VOUT-4)
              "ib 0": self.wire_to(ib, "0")}            # (terminal 0: IN 0)
        with self.p.edit("settings") as ed:
            ed.project_settings({"wire_numbers_io": True})
        got = {k: self.num(w) for k, w in ws.items()}
        self.assertEqual({k: n for k, n in got.items() if k != "iq 9"},
                         {"iq 11": "I:4/8", "iq 10": "I:4/9", "iq 1": "I:4/0",
                          "of8 3": "O:7/0", "of8 2": "O:7/4", "ib 0": "I:2/0"})
        self.assertIsNotNone(wirenums.split(got["iq 9"]), got)     # (a page number)

    def test_wiring_list_names_the_screw(self):
        strip_d = self.lib.get("symbol", "Terminal strip")
        term_d = self.lib.get("symbol", "Terminal")
        iq = self.place("1769-IQ16 module", "12,9", {"SLOT": "4"})
        q = dict(iq.pin_points())["11"]                     # (IN 8)
        with self.p.edit("strip") as ed:
            for d in (strip_d, term_d):
                ed.block(self.p.blocks.get(d.name) or d)
            tb = ed.add(self.s, M.Insert(strip_d.name, (2, 12),
                                         defn=self.p.blocks[strip_d.name],
                                         attrs=tags.new_attrs(self.p, self.s, strip_d, {})))
            t = ed.add(self.s, M.Insert(term_d.name, (q[0] - 3.0, q[1]),
                                        defn=self.p.blocks[term_d.name],
                                        attrs=tags.link_attrs({"TERM": "4"}, tb)))
        t = self.s.entities[t.id]
        tq = max(t.pin_points(), key=lambda np: np[1][0])[1]
        with self.p.edit("wire") as ed:
            ed.add(self.s, M.Wire([tq, q]))
        plc = self.s.entities[iq.id].attrs["TAG"]
        strip = self.s.entities[tb.id].attrs["TAG"]
        rows = PW.rows(self.p)
        self.assertTrue(any(r[0] == plc and r[1] == "11" and r[6] == strip + "-4"
                            for r in rows), [r[:7] for r in rows])
        self.assertTrue(any(r[0] == strip + "-4" and r[6] == plc + ":11" for r in rows),
                        [r[:7] for r in rows])
        # every screw of the module listed, a row each, by its number
        self.assertEqual([r[1] for r in rows if r[0] == plc],
                         [str(i) for i in range(1, 19)])


if __name__ == "__main__":
    unittest.main()
