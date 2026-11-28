"""Terminal strips (0.27, the roadmap's item 4: "strips, jumpers, a strip editor, a terminal
plan report"): a strip's terminals found from the drawing, in its order, with the wires and
what they land on each side (internal: inside the strip's location; external: going out of
it), reordered, renumbered, spares and jumpers added in the Terminal strips window and written
back in one step; the terminal plan as a report, a report sheet and a file."""
import os
import tempfile
import unittest

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import report_sheets as RS
from kanzonascad import strip_window, strips, tags


class StripTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.s = self.v.sheet()
        lib = self.win.library
        self.term, self.strip, self.coil, self.light, self.conn = (
            lib.get("symbol", n) for n in ("Terminal", "Terminal strip", "Relay coil",
                                           "Pilot light", "Off-sheet connector"))
        with self.p.edit("blocks") as ed:
            for b in (self.term, self.strip, self.coil, self.light, self.conn):
                ed.block(self.p.blocks.get(b.name) or b)
            ed.sheet_meta(self.s, location="MCP")
            self.tb = ed.add(self.s, M.Insert(self.strip.name, (1, 10), defn=self.strip,
                                              attrs=tags.new_attrs(self.p, self.s, self.strip,
                                                                   {})))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def defn(self, d):
        return self.p.blocks[d.name]

    def terminal(self, ed, y, x=5.0, s=None, field=True, turned=False, num=None, strip=True):
        """A terminal at (x, y): a coil wired to its left pin, a pilot light in the FIELD (or
        not) to its right pin (turned: the terminal turned round, the field on its left pin)."""
        s = s or self.s
        attrs = {"TAG": self.tb.attrs["TAG"]} if strip else {"TAG": "TB9"}
        if num is not None:
            attrs["TERM"] = num
        t = ed.add(s, M.Insert(self.term.name, (x, y), defn=self.defn(self.term),
                               attrs=attrs, angle=180.0 if turned else 0.0))
        if strip:
            t = ed.change(s, t.copy(attrs=tags.link_attrs(t.attrs, self.tb)))
        pins = dict(t.pin_points())
        left, right = sorted(pins.values())
        c = ed.add(s, M.Insert(self.coil.name, (x - 3, y), defn=self.defn(self.coil),
                               attrs=tags.new_attrs(self.p, s, self.coil, {})))
        ed.add(s, M.Wire([max(q for _n, q in c.pin_points()), left]))
        lt = ed.add(s, M.Insert(self.light.name, (x + 3, y), defn=self.defn(self.light),
                                attrs=tags.new_attrs(self.p, s, self.light,
                                                     {"LOC": "FIELD"} if field else {})))
        ed.add(s, M.Wire([right, min(q for _n, q in lt.pin_points())]))
        return t, c, lt

    def three(self):
        with self.p.edit("terminals") as ed:
            got = [self.terminal(ed, 8 - i) for i in range(3)]
        return [(self.s.entities[t.id], c, lt) for t, c, lt in got]

    def only(self):
        got = strips.find(self.p)
        self.assertEqual(len(got), 1, [st.tag for st in got])
        return got[0]

    # ---- found from the drawing ---------------------------------------------------------
    def test_terminals_in_number_order_with_both_sides(self):
        got = self.three()
        st = self.only()
        self.assertEqual(st.tag, self.tb.attrs["TAG"])
        self.assertEqual(st.loc, "MCP")
        self.assertEqual([r.num for r in st.rows], ["1", "2", "3"])
        for r, (t, c, lt) in zip(st.rows, got):
            self.assertEqual([e.id for _s, e in r.places], [t.id])
            self.assertEqual(strips.to_text(self.p, st, r.inside), c.attrs["TAG"] + ":A2")
            self.assertEqual(strips.to_text(self.p, st, r.outside), lt.attrs["TAG"] +
                             ":1 (FIELD)")
            wl = {w.num for w in self.s.wires() if w.touches(dict(t.pin_points())["1"])}
            self.assertEqual(set(r.inside.wires), wl)
            self.assertNotEqual(r.inside.wires, r.outside.wires)

    def test_field_on_the_left_is_the_external_side(self):
        # (turned round, the field wire on its left pin: that side goes out of the MCP)
        with self.p.edit("t") as ed:
            t, c, lt = self.terminal(ed, 8, turned=True)
            t2, c2, lt2 = self.terminal(ed, 7, field=False)
        st = self.only()
        a, b = st.rows
        self.assertEqual(a.inside.pin, "2")
        self.assertIn("(FIELD)", strips.to_text(self.p, st, a.outside))
        self.assertIn(c.attrs["TAG"], strips.to_text(self.p, st, a.inside))
        # (no other location: left pin internal, as drawn)
        self.assertEqual((b.inside.pin, b.outside.pin), ("1", "2"))
        self.assertEqual(strips.to_text(self.p, st, b.outside), lt2.attrs["TAG"] + ":1")

    def test_through_an_off_sheet_connector(self):
        # (the wire goes on to sheet 2 through an off-sheet connector: what it lands on there)
        s2 = self.p.make_sheet("Two")
        with self.p.edit("two sheets") as ed:
            ed.add_sheet(s2)
            t = ed.add(self.s, M.Insert(self.term.name, (5, 8), defn=self.defn(self.term),
                                        attrs=tags.link_attrs({}, self.tb)))
            right = dict(t.pin_points())["2"]
            ed.add(self.s, M.Wire([right, (8, 8)]))
            ed.add(self.s, M.Insert(self.conn.name, (8, 8), defn=self.defn(self.conn),
                                    attrs={"TAG": "A"}))
            ed.add(s2, M.Insert(self.conn.name, (2, 5), defn=self.defn(self.conn),
                                attrs={"TAG": "A"}))
            lt = ed.add(s2, M.Insert(self.light.name, (6, 5), defn=self.defn(self.light),
                                     attrs=tags.new_attrs(self.p, s2, self.light, {})))
            ed.add(s2, M.Wire([(2, 5), min(q for _n, q in lt.pin_points())]))
        st = self.only()
        self.assertEqual(strips.to_text(self.p, st, st.rows[0].outside), lt.attrs["TAG"] + ":1")
        self.assertIs(st.rows[0].outside.to[0][0], s2)

    def test_two_terminals_on_one_device_pin(self):
        # (two wires landed on one pin: each terminal goes there, and through it to the other)
        with self.p.edit("t") as ed:
            c = ed.add(self.s, M.Insert(self.coil.name, (2, 8), defn=self.defn(self.coil),
                                        attrs=tags.new_attrs(self.p, self.s, self.coil, {})))
            a2 = dict(c.pin_points())["A2"]
            for y in (8.0, 7.0):
                t = ed.add(self.s, M.Insert(self.term.name, (5, y), defn=self.defn(self.term),
                                            attrs=tags.link_attrs({}, self.tb)))
                left = dict(t.pin_points())["1"]
                ed.add(self.s, M.Wire([a2, (a2[0], y), left] if y != a2[1] else [a2, left]))
        st = self.only()
        tb = self.tb.attrs["TAG"]
        self.assertEqual([strips.to_text(self.p, st, r.inside) for r in st.rows],
                         [c.attrs["TAG"] + ":A2, %s-2" % tb, c.attrs["TAG"] + ":A2, %s-1" % tb])

    def test_one_number_drawn_twice_is_one_terminal(self):
        s2 = self.p.make_sheet("Two")
        with self.p.edit("t") as ed:
            ed.add_sheet(s2)
            a = self.terminal(ed, 8, num="5")
            b = self.terminal(ed, 6, s=s2, num="5")
        st = self.only()
        self.assertEqual([r.num for r in st.rows], ["5"])
        r = st.rows[0]
        self.assertEqual(len(r.places), 2)
        self.assertEqual(strips.to_text(self.p, st, r.inside), ", ".join(sorted(
            [a[1].attrs["TAG"] + ":A2", b[1].attrs["TAG"] + ":A2"])))

    def test_a_strip_with_no_strip_symbol_goes_by_its_tag(self):
        with self.p.edit("t") as ed:
            self.terminal(ed, 8, strip=False, num="1")
            self.terminal(ed, 7, strip=False, num="2")
        got = [st for st in strips.find(self.p) if st.tag == "TB9"]
        self.assertEqual(len(got), 1)
        lay = strips.Layout(got[0])
        lay.move([1], -1)
        with self.p.edit("Terminal strips") as ed:
            strips.apply(ed, self.p, [lay])
        self.assertIn("tag:TB9", self.p.settings["strips"])
        # (a strip symbol given that tag later: its terminals link to it, and it keeps the
        # order kept by the tag)
        with self.p.edit("strip") as ed:
            ed.add(self.s, M.Insert(self.strip.name, (1, 1), defn=self.defn(self.strip),
                                    attrs=tags.new_attrs(self.p, self.s, self.strip,
                                                         {"TAG": "TB9"})))
        st = next(st for st in strips.find(self.p) if st.tag == "TB9")
        self.assertIsNotNone(st.dev)
        self.assertEqual([r.num for r in st.rows], ["2", "1"])
        lay = strips.Layout(st)
        lay.add_spare()
        with self.p.edit("Terminal strips") as ed:
            strips.apply(ed, self.p, [lay])
        self.assertNotIn("tag:TB9", self.p.settings["strips"])
        self.assertEqual(self.p.settings["strips"][st.key]["order"], ["2", "1", "3"])

    # ---- edited ---------------------------------------------------------------------------
    def test_a_jumper_to_an_unnumbered_terminal_is_not_shown(self):
        # (0.30, the battery, seed 526: a jumper from a numbered terminal to a TB? one showed
        # J1 on the numbered one in the window, and the strip kept no jumper)
        self.three()
        lay = strips.Layout(self.only())
        lay.rows[2]["num"] = None                   # (a terminal not numbered yet)
        self.assertTrue(lay.add_jumper([0, 2]))
        self.assertEqual(lay.jumpers(), [])
        self.assertEqual(lay.jumper_names(), {})
        self.assertTrue(lay.add_jumper([0, 1]))     # (two numbered: shown and kept)
        self.assertEqual(lay.jumper_names(), {0: "J1", 1: "J1"})
        self.assertEqual(lay.jumpers(), [[lay.rows[0]["num"], lay.rows[1]["num"]]])

    def test_reorder_renumber_spare_jumper_in_one_step(self):
        got = self.three()
        before = self.p.to_dict()
        n_undo = len(self.p.undo_stack)
        lay = strips.Layout(self.only())
        self.assertEqual(lay.move([2], -1), [1])               # 1, 3, 2
        self.assertEqual(lay.add_spare(0), 1)                  # 1, (4), 3, 2
        self.assertEqual(lay.rows[1]["num"], "4")
        self.assertTrue(lay.add_jumper([0, 2]))
        self.assertTrue(lay.changed())
        with self.p.edit("Terminal strips") as ed:
            strips.apply(ed, self.p, [lay])
        self.assertEqual(len(self.p.undo_stack), n_undo + 1)
        st = self.only()
        self.assertEqual([(r.num, r.spare) for r in st.rows],
                         [("1", False), ("4", True), ("3", False), ("2", False)])
        self.assertEqual(st.jumpers, [["1", "3"]])
        self.assertEqual(strips.jumper_text(st, st.rows[2]), "J1: 1, 3")
        # renumbered in that order: the drawing's terminals take the new numbers
        lay = strips.Layout(st)
        lay.renumber(1)
        with self.p.edit("Terminal strips") as ed:
            self.assertEqual(strips.apply(ed, self.p, [lay]), 1)       # (2 is 4 now)
        nums = {e.id: e.attrs["TERM"] for e in self.s.inserts() if strips.is_terminal(e)}
        self.assertEqual(nums, {got[0][0].id: "1", got[2][0].id: "3", got[1][0].id: "4"})
        st = self.only()
        self.assertEqual([r.num for r in st.rows], ["1", "2", "3", "4"])
        self.assertEqual(st.jumpers, [["1", "3"]])          # (the jumper went with them)
        self.assertEqual(self.p.settings["strips"][st.key], {"spares": ["2"],
                                                             "jumpers": [["1", "3"]]})
        # each one undo
        self.p.undo()
        self.p.undo()
        self.assertEqual(self.p.to_dict(), before)
        # and kept with the project
        self.p.redo()
        self.p.redo()
        path = os.path.join(tempfile.mkdtemp(), "strips.kzcad")
        self.p.save(path, backups=0)
        q = M.Project.load(path)
        st2 = strips.find(q)[0]
        self.assertEqual([(r.num, r.spare, r.jumper) for r in st2.rows],
                         [(r.num, r.spare, r.jumper) for r in self.only().rows])

    def test_turned_round_and_renumbered_is_a_change(self):
        # (the numbers read 1, 2, 3 as before, but each terminal has another: the self-test's
        # budget found it written back as no change)
        got = self.three()
        lay = strips.Layout(self.only())
        lay.rows.reverse()
        lay.renumber(1)
        self.assertTrue(lay.changed())
        with self.p.edit("Terminal strips") as ed:
            self.assertEqual(strips.apply(ed, self.p, [lay]), 2)
        self.assertEqual(self.s.entities[got[2][0].id].attrs["TERM"], "1")

    def test_a_terminal_placed_later_goes_after_the_one_below_it(self):
        self.three()
        lay = strips.Layout(self.only())
        lay.move([0], 1)                                    # 2, 1, 3
        with self.p.edit("Terminal strips") as ed:
            strips.apply(ed, self.p, [lay])
        with self.p.edit("one more") as ed:
            self.terminal(ed, 4, num="4")
            self.terminal(ed, 3, num="1.5")
        self.assertEqual([r.num for r in self.only().rows], ["2", "1", "1.5", "3", "4"])
        self.assertEqual(strips.ordered(["3", "1", "2"], ["2", "x"]), ["1", "2", "3"])

    def test_a_terminal_numbered_as_a_spare_takes_its_place(self):
        self.three()
        lay = strips.Layout(self.only())
        lay.add_spare(0)
        with self.p.edit("Terminal strips") as ed:
            strips.apply(ed, self.p, [lay])
        with self.p.edit("one more") as ed:
            t, _c, _l = self.terminal(ed, 4)
        self.assertEqual(self.s.entities[t.id].attrs["TERM"], "4")     # (the lowest free)
        st = self.only()
        self.assertEqual([(r.num, r.spare) for r in st.rows],
                         [("1", False), ("4", False), ("2", False), ("3", False)])
        self.assertEqual(st.rows[1].places[0][1].id, t.id)

    def test_numbers_typed_and_refused(self):
        self.three()
        lay = strips.Layout(self.only())
        self.assertIn("already", lay.set_number(0, "2"))
        self.assertIsNotNone(lay.set_number(0, "  "))
        self.assertIsNone(lay.set_number(0, "PE"))
        self.assertFalse(lay.add_jumper([1]))
        self.assertEqual(lay.remove_spares([0, 1]), 0)       # (drawn: stay)
        lay.add_jumper([0, 1, 2])
        self.assertEqual(lay.remove_jumper([1, 2]), 2)        # (one left alone: no jumper)
        self.assertEqual(lay.jumpers(), [])
        self.assertIsNone(lay.rows[0]["jumper"])
        self.assertEqual(strips.clean_jumpers([["1", "2"], ["2", "3"], ["9", "1"]],
                                              {"1", "2", "3"}), [["1", "2", "3"]])

    # ---- the window ---------------------------------------------------------------------
    def test_the_window(self):
        got = self.three()
        self.v.set_selection({got[1][0].id})
        n_undo = len(self.p.undo_stack)
        seen = {}
        real = strip_window.StripEditorDialog.exec

        def answer(dlg):
            seen["header"] = dlg.header.text()
            t = dlg.table
            seen["rows"] = t.rowCount()
            seen["out"] = t.item(0, 4).text()
            dlg.pick([2])
            dlg.buttons["up"].click()
            self.assertEqual(dlg.picked(), [1])
            dlg.buttons["spare"].click()                        # (after 3: 1, 3, 4, 2)
            dlg.pick([0, 1])
            dlg.buttons["jumper"].click()
            self.assertEqual(t.item(0, 5).text(), "J1")
            t.item(3, 0).setText("3")                           # (refused: 3 is there)
            self.assertEqual(t.item(3, 0).text(), "2")
            seen["cells"] = [t.item(i, 0).text() for i in range(t.rowCount())]
            dlg.buttons["renumber"].click()
            seen["after"] = [t.item(i, 0).text() for i in range(t.rowCount())]
            return strip_window.QDialog.Accepted
        strip_window.StripEditorDialog.exec = answer
        from PySide6.QtWidgets import QMessageBox
        warn = QMessageBox.warning
        QMessageBox.warning = staticmethod(lambda *a, **k: seen.setdefault("warned", a[2]))
        try:
            self.assertTrue(self.win.terminal_strips())
        finally:
            strip_window.StripEditorDialog.exec = real
            QMessageBox.warning = warn
        self.assertIn(self.tb.attrs["TAG"], seen["header"])
        self.assertEqual(seen["rows"], 3)
        self.assertIn("(FIELD)", seen["out"])
        self.assertIn("already", seen["warned"])
        self.assertEqual(seen["cells"], ["1", "3", "4", "2"])
        self.assertEqual(seen["after"], ["1", "2", "3", "4"])
        self.assertEqual(len(self.p.undo_stack), n_undo + 1)
        st = self.only()
        self.assertEqual([(r.num, r.spare) for r in st.rows],
                         [("1", False), ("2", False), ("3", True), ("4", False)])
        self.assertEqual(st.jumpers, [["1", "2"]])
        self.assertEqual(self.s.entities[got[2][0].id].attrs["TERM"], "2")

    def test_the_window_cancelled_or_empty(self):
        self.three()
        real = strip_window.StripEditorDialog.exec

        def answer(dlg):
            dlg.pick([0])
            dlg.buttons["down"].click()
            return strip_window.QDialog.Rejected
        strip_window.StripEditorDialog.exec = answer
        try:
            n = len(self.p.undo_stack)
            self.assertFalse(self.win.terminal_strips())
            self.assertEqual(len(self.p.undo_stack), n)
        finally:
            strip_window.StripEditorDialog.exec = real
        q = M.Project.new()
        dlg = strip_window.StripEditorDialog(self.win, q)
        self.assertIn("No terminal strips", dlg.header.text())
        self.assertFalse(dlg.apply())
        dlg.deleteLater()

    # ---- the terminal plan ---------------------------------------------------------------
    def test_terminal_plan(self):
        got = self.three()
        lay = strips.Layout(self.only())
        lay.add_spare()
        lay.add_jumper([0, 1])
        with self.p.edit("Terminal strips") as ed:
            strips.apply(ed, self.p, [lay])
        head, rows = strips.table(self.p)
        self.assertEqual(head, strips.PLAN_HEAD)
        tag = self.tb.attrs["TAG"]
        self.assertEqual([r[:2] for r in rows], [[tag, "1"], [tag, "2"], [tag, "3"],
                                                  [tag, "4"]])
        c, lt = got[0][1], got[0][2]
        self.assertEqual(rows[0][3], c.attrs["TAG"] + ":A2")
        self.assertEqual(rows[0][5], lt.attrs["TAG"] + ":1 (FIELD)")
        self.assertEqual(rows[0][6], "J1: 1, 2")
        self.assertEqual(rows[3][2:], ["", "", "", "", "", "spare"])
        self.assertEqual(rows[0][7], self.p.zone_text(self.s, *got[0][0].pos))
        # the report window, its file, and a report sheet
        seen = {}
        from kanzonascad import dialogs
        real = dialogs.report_dialog
        dialogs.report_dialog = lambda _w, title, h, r, *a: seen.update(title=title, rows=r)
        try:
            self.win.acts["terminal_plan"].trigger()
        finally:
            dialogs.report_dialog = real
        self.assertEqual((seen["title"], seen["rows"]), ("Terminal plan", rows))
        from kanzonascad import reports
        path = os.path.join(tempfile.mkdtemp(), "plan.xlsx")
        self.assertEqual(reports.write_csv(path, head, rows, "Terminal plan"), 4)
        made = self.win.report_sheet("terminal_plan")
        self.assertEqual([m.report for m in made], ["terminal_plan"])
        texts = {e.text for e in made[0].entities.values() if isinstance(e, M.Text)}
        self.assertIn("J1: 1, 2", texts)
        self.assertIn("terminal_plan", RS.kinds())


if __name__ == "__main__":
    unittest.main()
