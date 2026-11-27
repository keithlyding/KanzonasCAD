"""0.16.6, the owner's list: "If I'm making a schematic symbol, when making terminal numbers,
will they show up?" (they didn't: Show pin names); "Add the drive terminal symbol"; "automatic
numbering... 1,2,3...; A,B,C...; S1, S2, S3...; A1, B2,C3... top to bottom, left to right or
left to right, top to bottom" (Number texts); "Can you add chapters and search function to
help manual?"."""
import unittest

from tests.util import APP, window, type_in, NEAREST

from kanzonascad import commands as C
from kanzonascad import manual
from kanzonascad import model as M
from kanzonascad import numbering as N


class NumberingTest(unittest.TestCase):
    def test_sequences(self):
        self.assertEqual(N.labels(4), ["1", "2", "3", "4"])
        self.assertEqual(N.labels(3, "letter"), ["A", "B", "C"])
        self.assertEqual(N.labels(3, "lower", "a"), ["a", "b", "c"])
        self.assertEqual(N.labels(3, prefix="S"), ["S1", "S2", "S3"])
        self.assertEqual(N.labels(3, "letter_number"), ["A1", "B2", "C3"])
        self.assertEqual(N.labels(3, start="9", digits=2), ["09", "10", "11"])
        self.assertEqual(N.labels(3, "letter", "Y"), ["Y", "Z", "AA"])
        self.assertEqual(N.labels(3, start="10", step=10, prefix="TB1-", suffix="A"),
                         ["TB1-10A", "TB1-20A", "TB1-30A"])

    def test_order_by_rows_or_columns(self):
        ts = [M.Text((x, y), w, 0.1) for x, w in ((1.0, "1"), (3.0, "Relay 1 Common"))
              for y in (5.0, 4.0, 3.0)]
        down = [(t.pos) for t in N.ordered(ts, "down")]
        self.assertEqual(down, [(1.0, 5.0), (1.0, 4.0), (1.0, 3.0), (3.0, 5.0), (3.0, 4.0),
                                (3.0, 3.0)])
        across = [(t.pos) for t in N.ordered(ts, "across")]
        self.assertEqual(across, [(1.0, 5.0), (3.0, 5.0), (1.0, 4.0), (3.0, 4.0), (1.0, 3.0),
                                  (3.0, 3.0)])
        # a column of texts of different lengths lined up on their insertion points stays one
        col = [M.Text((1.0, 5.0 - i * 0.5), w, 0.1) for i, w in
               enumerate(["1", "Relay 1 Common", "X", "Safety +24V"])]
        self.assertEqual([t.text for t in N.ordered(col, "down")],
                         ["1", "Relay 1 Common", "X", "Safety +24V"])


class CommandsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        self.s, self.p = v.sheet(), v.project

    def tearDown(self):
        self.win.__dict__.pop("ask_numbering", None)
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def test_number_texts_replace_before_after_and_undo(self):
        with self.p.edit("t") as ed:
            ids = [ed.add(self.s, M.Text((1.0, y), "x", 0.1)).id for y in (5.0, 4.0, 3.0)]
        for mode, want in (("replace", ["S1", "S2", "S3"]), ("before", ["S1x", "S2x", "S3x"]),
                           ("after", ["xS1", "xS2", "xS3"])):
            self.win.ask_numbering = lambda n, m=mode: {"sequence": "number", "prefix": "S",
                                                         "order": "down", "mode": m}
            self.v.set_selection(set(ids))
            self.v.run(C.NumberCmd)
            self.assertEqual([self.s.entities[i].text for i in ids], want)
            self.p.undo()
            self.assertEqual([self.s.entities[i].text for i in ids], ["x"] * 3)

    def test_nothing_but_texts_are_numbered(self):
        with self.p.edit("t") as ed:
            t = ed.add(self.s, M.Text((1.0, 5.0), "x", 0.1))
            ln = ed.add(self.s, M.Line((0, 0), (1, 1)))
        self.win.ask_numbering = lambda n: {"sequence": "letter", "start": "A"}
        self.v.set_selection({t.id, ln.id})
        self.v.run(C.NumberCmd)
        self.assertEqual(self.s.entities[t.id].text, "A")

    def test_pin_names_show_when_asked(self):
        lib = self.win.library
        d = M.BlockDef.from_dict(dict(lib.get("symbol", "Contact NO").to_dict(),
                                      name="Mine", show_pins=True))
        self.v.run(C.InsertCmd, d, {})
        type_in(self.v, "3,5")
        while self.v.cmd is not None:
            self.v.cmd.enter()
        e = self.s.inserts()[0]
        texts = [w.text for w in e.world_entities() if isinstance(w, M.Text)]
        # (a contact's pins by its own numbers, numbered as placed: 13 and 14, 0.28)
        self.assertIn("13", texts)
        self.assertIn("14", texts)
        self.assertIn("PINS", e.shown_names())
        # hidden on that copy
        with self.p.edit("hide") as ed:
            ed.change(self.s, e.copy(hidden=["PINS"]))
        e = self.s.entities[e.id]
        self.assertEqual([w.text for w in e.world_entities() if isinstance(w, M.Text)
                          and w.text in ("13", "14")], [])
        # the built-in contacts show them since 0.28 (their numbers, 13-14); a coil doesn't; a
        # symbol saved and opened keeps the choice
        self.assertTrue(lib.get("symbol", "Contact NO").show_pins)
        self.assertFalse(lib.get("symbol", "Relay coil").show_pins)
        self.assertTrue(M.BlockDef.from_dict(d.to_dict()).show_pins)

    def test_pin_names_read_across_however_turned(self):
        d = M.BlockDef.from_dict(dict(self.win.library.get("symbol", "Contact NO").to_dict(),
                                      name="Mine", show_pins=True))
        for keys in ("", "R", "RR", "RRR"):
            e = M.Insert("Mine", (3.0, 5.0), 90.0 * len(keys), defn=d)
            for t in e.pin_texts():
                self.assertEqual(t.angle, 0.0)

    def test_drive_control_terminals(self):
        lib = self.win.library
        d = lib.get("symbol", "Drive control terminals")
        names = [q["name"] for q in d.pins]
        for n in ("S1", "S2", "S+", "01", "08", "11", "19", "R1", "R6", "C1", "C2"):
            self.assertIn(n, names)
        ys = [q["pos"][1] for q in d.pins]
        self.assertEqual(ys, sorted(ys, reverse=True))
        self.assertTrue(all(abs(q["pos"][0] + 0.25) < 1e-9 for q in d.pins))
        # a contact of its drive: the drive's tag
        self.v.run(C.InsertCmd, lib.get("symbol", "Variable frequency drive"), {})
        type_in(self.v, "2,9")
        while self.v.cmd is not None:
            self.v.cmd.enter()
        self.v.run(C.InsertCmd, d, {})
        type_in(self.v, "6,9", NEAREST)
        vfd, term = sorted(self.s.inserts(), key=lambda e: e.pos[0])
        self.assertEqual(term.attrs["TAG"], vfd.attrs["TAG"])
        self.assertEqual(term.attrs["PARENT"], vfd.attrs["DEV"])


class ManualTest(unittest.TestCase):
    def test_chapters_have_anchors_and_text(self):
        ch = manual.chapters()
        self.assertGreater(len(ch), 25)
        self.assertEqual(ch[0][:3], (2, "The window", "ch-1"))
        self.assertTrue(all('<a name="%s">' % a in manual.html() for _l, _t, a, _b in ch))
        wires = [b for _l, t, _a, b in ch if t == "Wires"][0]
        self.assertIn("Bus", wires)

    def test_search_and_chapters_in_the_window(self):
        win, _v = window()
        try:
            dlg = win.manual_dialog()
            dlg.show()
            n = dlg.chapters.topLevelItemCount()
            self.assertGreater(n, 20)
            dlg.search.setText("offset")
            shown = [dlg.chapters.topLevelItem(i).text(0) for i in range(n)
                     if not dlg.chapters.topLevelItem(i).isHidden()]
            self.assertTrue(any(t.startswith("Drawing") for t in shown), shown)
            self.assertLess(len(shown), n)
            self.assertRegex(dlg.count.text(), r"^1 of \d+$")
            dlg.go(1)
            self.assertRegex(dlg.count.text(), r"^2 of \d+$")
            dlg.go(-1)
            self.assertRegex(dlg.count.text(), r"^1 of \d+$")
            self.assertEqual(dlg.browser.textCursor().selectedText().lower(), "offset")
            dlg.search.setText("")
            self.assertEqual(sum(1 for i in range(n)
                                 if not dlg.chapters.topLevelItem(i).isHidden()), n)
            dlg.close()
        finally:
            win.close()


if __name__ == "__main__":
    unittest.main()
