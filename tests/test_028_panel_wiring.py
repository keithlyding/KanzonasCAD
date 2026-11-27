"""Panel wiring (0.28, the roadmap's item 5): a per-device wiring list worked out from the
schematic (each device's and terminal's pins with their wire, its size, color and layer, and
where the wire goes, across sheets), and the footprints' terminals on a panel sheet labeled
with their wire and destination ("6001 → CR101:A1"), turned on per sheet, following every
change, readable however the footprint is turned; footprints with no terminal positions said
so, not guessed."""
import os
import tempfile
import unittest

from tests.util import APP, window

from kanzonascad import commands as C
from kanzonascad import dialogs
from kanzonascad import model as M
from kanzonascad import panelwiring as PW
from kanzonascad import render
from kanzonascad import report_sheets as RS
from kanzonascad import tags


class PanelWiringTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = p = self.v.project
        self.s = s = self.v.sheet()
        lib = self.win.library
        names = ("Contactor coil", "Contactor power contacts 3-pole", "Terminal",
                 "Terminal strip", "Pilot light", "Off-sheet connector")
        self.coil, self.power, self.term, self.strip, self.light, self.conn = (
            lib.get("symbol", n) for n in names)
        self.fp_k = lib.get("footprint", "Contactor 9-18 A")
        self.fp_t = lib.get("footprint", "Terminal block 2.5 mm2 (#12 AWG)")
        self.fp_ps = lib.get("footprint", "Power supply 24 VDC 5 A")     # (no pins)
        with p.edit("blocks") as ed:
            for b in (self.coil, self.power, self.term, self.strip, self.light, self.conn,
                      self.fp_k, self.fp_t, self.fp_ps):
                ed.block(p.blocks.get(b.name) or b)
            ed.sheet_meta(s, location="MCP")
            self.m = self._sym(ed, s, self.coil, (5, 5))
            self.k = ed.add(s, M.Insert(self.power.name, (5, 8), defn=p.blocks[self.power.name],
                                        attrs=tags.link_attrs({}, self.m)))
            self.tb = self._sym(ed, s, self.strip, (1, 10))
            self.t = ed.add(s, M.Insert(self.term.name, (9, 5), defn=p.blocks[self.term.name],
                                        attrs=tags.link_attrs({"TERM": "1"}, self.tb)))
            self.lt = self._sym(ed, s, self.light, (12, 5), LOC="FIELD")
            cp, tp, lp = (dict(x.pin_points()) for x in (self.m, self.t, self.lt))
            self.w1 = ed.add(s, M.Wire([cp["A2"], tp["1"]]))
            self.w2 = ed.add(s, M.Wire([tp["2"], lp["1"]], layer="WIRES"))
            self.ps = p.make_sheet("Panel", "panel")
            ed.add_sheet(self.ps)
            ed.sheet_meta(self.ps, location="MCP")
            self.fk = ed.add(self.ps, M.Insert(self.fp_k.name, (5, 5),
                                               defn=p.blocks[self.fp_k.name],
                                               attrs=tags.link_footprint({}, self.m)))
            self.ft = ed.add(self.ps, M.Insert(self.fp_t.name, (8, 5),
                                               defn=p.blocks[self.fp_t.name],
                                               attrs=tags.link_footprint({"TERM": "1"},
                                                                         self.tb),
                                               label="tag", tag_h=0.08))
        p.undo_stack.clear()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def _sym(self, ed, s, d, at, **attrs):
        return ed.add(s, M.Insert(d.name, at, defn=self.p.blocks[d.name],
                                  attrs=tags.new_attrs(self.p, s, d, dict(attrs))))

    def num(self, w):
        return self.s.entities[w.id].num

    def row(self, dev, pin):
        got = [r for r in PW.rows(self.p) if r[0] == dev and r[1] == pin]
        self.assertTrue(got, (dev, pin, [r[:2] for r in PW.rows(self.p)]))
        return got

    def swap(self, ed, name):
        """The contactor's footprint drawn with another block."""
        e = self.ps.entities[self.fk.id].copy(block=name)
        e.defn = self.p.blocks[name]
        ed.change(self.ps, e)

    def labels_on(self, on=True):
        with self.p.edit("labels") as ed:
            ed.sheet_meta(self.ps, terminal_labels=on)

    def texts(self):
        return sorted(t.text for t in PW.labels(self.p, self.ps))

    # ---- the wiring list ----------------------------------------------------------------
    def test_device_and_its_contacts_pin_by_pin(self):
        tag, tb = self.m.attrs["TAG"], self.tb.attrs["TAG"]
        rows = PW.rows(self.p)
        self.assertEqual([r[1] for r in rows if r[0] == tag],
                         ["A1", "A2", "L1", "L2", "L3", "T1", "T2", "T3"])
        r = self.row(tag, "A2")[0]
        self.assertEqual(r[2], self.num(self.w1))
        self.assertEqual(r[6], tb + "-1")
        self.assertEqual(r[7], "MCP")
        self.assertEqual(self.row(tag, "A1")[0][2:7], ["", "", "", "", ""])
        # (a terminal is a unit of its own, its two sides each a row)
        out = self.row(tb + "-1", "2")[0]
        self.assertEqual(out[2], self.num(self.w2))
        self.assertEqual(out[6], self.lt.attrs["TAG"] + ":1 (FIELD)")
        self.assertEqual(self.row(self.lt.attrs["TAG"], "1")[0][6], tb + "-1 (MCP)")
        self.assertEqual(PW.HEAD, PW.table(self.p)[0])

    def test_size_color_and_layer_of_the_wire(self):
        with self.p.edit("layer") as ed:
            ed.layer("24V", None, M.Layer("24V", "#0000ff", awg="16", wire_color="BLU",
                                          wire=True).to_dict())
            ed.change(self.s, self.s.entities[self.w2.id].copy(layer="24V"))
        r = self.row(self.lt.attrs["TAG"], "1")[0]
        self.assertEqual(r[3:6], ["16 AWG", "BLU", "24V"])
        with self.p.edit("size") as ed:
            ed.change(self.s, self.s.entities[self.w2.id].copy(awg="14"))
        self.assertEqual(self.row(self.lt.attrs["TAG"], "1")[0][3], "14 AWG")

    def test_across_sheets_through_off_sheet_connectors(self):
        p = self.p
        with p.edit("connectors") as ed:
            s2 = p.make_sheet("Two")
            ed.add_sheet(s2, 1)
            cp = dict(self.m.pin_points())
            c1 = ed.add(self.s, M.Insert(self.conn.name, (cp["A1"][0] - 2, cp["A1"][1]),
                                         defn=p.blocks[self.conn.name], attrs={"TAG": "X1"}))
            ed.add(self.s, M.Wire([cp["A1"], c1.pin_points()[0][1]]))
            c2 = ed.add(s2, M.Insert(self.conn.name, (3, 5), defn=p.blocks[self.conn.name],
                                     attrs={"TAG": "X1"}))
            lt2 = self._sym(ed, s2, self.light, (6, 5))
            ed.add(s2, M.Wire([c2.pin_points()[0][1], dict(lt2.pin_points())["1"]]))
        r = self.row(self.m.attrs["TAG"], "A1")[0]
        self.assertEqual(r[6], lt2.attrs["TAG"] + ":1")
        self.assertTrue(r[2])

    # ---- the Footprint column: where, or why not ------------------------------------------
    def test_footprint_column_says_where_or_why_not(self):
        tag = self.m.attrs["TAG"]
        where = self.row(tag, "A2")[0][9]
        q = dict(self.fk.pin_points())["A2"]
        self.assertEqual(where, self.p.zone_text(self.ps, *q))
        self.assertEqual(self.row(self.lt.attrs["TAG"], "1")[0][9], PW.NO_FOOTPRINT)
        with self.p.edit("no pins") as ed:
            self.swap(ed, self.fp_ps.name)
        self.assertEqual(self.row(tag, "A2")[0][9],
                         "%s (%s)" % (PW.NO_POSITIONS, self.fp_ps.name))
        found = PW.without_positions(self.p)
        self.assertEqual([f.id for _s, f in found], [self.fk.id])
        self.assertIn("1 footprint has no terminal positions", PW.describe_missing(found))
        self.assertIn(tag, PW.describe_missing(found))

    def test_a_pin_its_footprint_has_not(self):
        p = self.p
        d = M.BlockDef.from_dict(dict(p.blocks[self.fp_k.name].to_dict(), name="Mine"))
        d.pins = [q for q in d.pins if q["name"] != "A1"]
        with p.edit("mine") as ed:
            ed.block(d)
            self.swap(ed, "Mine")
        self.assertEqual(self.row(self.m.attrs["TAG"], "A1")[0][9], "no terminal A1 on Mine")

    # ---- terminal wire labels ---------------------------------------------------------------
    def test_labels_only_when_turned_on_and_as_the_schematic_says(self):
        self.assertEqual(PW.labels(self.p, self.ps), [])
        self.labels_on()
        tag, tb, lt = self.m.attrs["TAG"], self.tb.attrs["TAG"], self.lt.attrs["TAG"]
        n1, n2 = self.num(self.w1), self.num(self.w2)
        self.assertEqual(self.texts(), sorted([
            "%s → %s-1" % (n1, tb),             # (the contactor's A2)
            "%s → %s:A2" % (n1, tag),           # (the terminal's internal side)
            "%s → %s:1 (FIELD)" % (n2, lt)]))   # (out to the field)
        self.assertEqual(PW.labels(self.p, self.s), [], "a schematic sheet shows none")
        self.labels_on(False)
        self.assertEqual(PW.labels(self.p, self.ps), [])

    def test_labels_follow_every_change_and_undo(self):
        self.labels_on()
        before = self.texts()
        with self.p.edit("number") as ed:
            ed.change(self.s, self.s.entities[self.w1.id].copy(num="7777", num_lock=True))
        self.assertIn("7777 → %s-1" % self.tb.attrs["TAG"], self.texts())
        self.p.undo()
        self.assertEqual(self.texts(), before)
        with self.p.edit("light gone") as ed:
            ed.remove(self.s, self.lt.id)
        got = self.texts()
        self.assertNotIn("FIELD", " ".join(got))
        self.assertIn(self.num(self.w2), got)       # (the wire, landing nowhere else now)

    def test_labels_kept_readable_when_the_footprint_is_turned(self):
        self.labels_on()
        h = PW.label_height(self.p) * self.ps.k()
        for ang in (0.0, 90.0, 180.0, 270.0):
            with self.p.edit("turn") as ed:
                ed.change(self.ps, self.ps.entities[self.fk.id].copy(angle=ang))
            fk = self.ps.entities[self.fk.id]
            pins = dict(fk.pin_points())
            mine = [t for t in PW.labels(self.p, self.ps) if t.text.endswith("-1")]
            self.assertEqual(len(mine), 1)
            t = mine[0]
            self.assertIn(t.angle, (0.0, 90.0), "read across or upward at %g" % ang)
            self.assertAlmostEqual(t.height, h)
            # (just off its pin, on the way out of the footprint)
            q = pins["A2"]
            self.assertAlmostEqual(abs(t.pos[0] - q[0]) + abs(t.pos[1] - q[1]), 0.4 * h, 6)
            x0, y0, x1, y1 = t.bbox()
            bx0, by0, bx1, by1 = fk.bbox()
            inside = bx0 + 1e-6 < (x0 + x1) / 2 < bx1 - 1e-6 and \
                by0 + 1e-6 < (y0 + y1) / 2 < by1 - 1e-6
            self.assertFalse(inside, "the label over the footprint at %g" % ang)

    def test_a_wire_to_many_pins_names_two_and_how_many_more(self):
        # (a common or a neutral on five lights: the label stays short, the list names all)
        p = self.p
        with p.edit("lights") as ed:
            q = dict(self.m.pin_points())["A1"]
            ed.add(self.s, M.Wire([q, (q[0], 1.0), (q[0] + 6, 1.0)]))
            for i in range(5):
                lt = self._sym(ed, self.s, self.light, (q[0] + 1 + i, 0.5))
                a = dict(lt.pin_points())["1"]
                ed.add(self.s, M.Wire([a, (a[0], 1.0)]))
        self.labels_on()
        row = self.row(self.m.attrs["TAG"], "A1")[0]
        self.assertEqual(len(row[6].split(", ")), 5)
        got = [t.text for t in PW.labels(p, self.ps) if "+" in t.text]
        self.assertEqual(len(got), 1, self.texts())
        self.assertTrue(got[0].endswith(" +3"), got)
        self.assertEqual(got[0].split(PW.ARROW)[1][:-3], ", ".join(row[6].split(", ")[:2]))

    def test_label_height_is_the_projects_on_paper(self):
        self.labels_on()
        with self.p.edit("scale") as ed:
            ed.sheet_scale(self.ps, 0.25, "1:4")
        with self.p.edit("height") as ed:
            ed.project_settings({PW.HEIGHT: 0.07})
        got = PW.labels(self.p, self.ps)
        self.assertTrue(got)
        for t in got:
            self.assertAlmostEqual(t.height, 0.07 * 4)

    def test_terminal_footprint_shows_its_terminal(self):
        self.assertEqual(self.ft.label_value("tag"), self.tb.attrs["TAG"] + "-1")

    def test_footprint_typed_as_a_terminal_links_to_its_strip(self):
        v = self.v
        v.show_sheet(self.ps.id)
        v.run(C.InsertCmd, self.p.blocks[self.fp_t.name], {})
        v.input_text("12,5")
        self.assertIsNotNone(v.cmd)
        v.input_text(self.tb.attrs["TAG"] + "-2")
        new = [e for e in self.ps.inserts() if e.attrs.get("TERM") == "2"]
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0].attrs.get("PARENT"), self.tb.attrs["DEV"])
        # (and the terminal, once drawn on the schematic, is that footprint's)
        with self.p.edit("terminal 2") as ed:
            ed.add(self.s, M.Insert(self.term.name, (9, 3), defn=self.p.blocks[self.term.name],
                                    attrs=tags.link_attrs({"TERM": "2"}, self.tb)))
        r = self.row(self.tb.attrs["TAG"] + "-2", "1")[0]
        q = dict(new[0].pin_points())["1"]
        self.assertEqual(r[9], self.p.zone_text(self.ps, *q))

    def test_command_turns_them_on_in_one_step_and_says_what_has_no_positions(self):
        win, v = self.win, self.v
        with self.p.edit("no pins") as ed:
            self.swap(ed, self.fp_ps.name)
        n = len(self.p.undo_stack)
        v.show_sheet(self.s.id)
        win._update_ui()
        self.assertFalse(win.acts["terminal_labels"].isEnabled(), "not on a schematic sheet")
        v.show_sheet(self.ps.id)
        win._update_ui()
        said = []
        real = win._say
        win._say = lambda msg, *a: said.append(msg)
        try:
            win.acts["terminal_labels"].trigger()
        finally:
            win._say = real
        self.assertTrue(self.ps.terminal_labels)
        self.assertTrue(win.acts["terminal_labels"].isChecked())
        self.assertEqual(len(self.p.undo_stack), n + 1)
        self.assertIn("no terminal positions", said[-1])
        self.assertIn("2 terminals labeled", said[-1])
        self.p.undo()
        self.assertFalse(self.ps.terminal_labels)

    def test_kept_with_the_file(self):
        self.labels_on()
        before = self.texts()
        path = os.path.join(tempfile.mkdtemp(), "w.kzcad")
        self.p.save(path, backups=0)
        q = M.Project.load(path)
        ps = q.sheet_by_id(self.ps.id)
        self.assertTrue(ps.terminal_labels)
        self.assertEqual(sorted(t.text for t in PW.labels(q, ps)), before)
        self.assertEqual(PW.rows(q), PW.rows(self.p))

    # ---- drawn, exported, reported ----------------------------------------------------------
    def test_drawn_by_the_renderer_and_the_picture_follows(self):
        self.labels_on()
        v = self.v
        v.show_sheet(self.ps.id)
        drawn = []
        real = render.draw_texts

        def spy(painter, items, *a, **k):
            drawn.extend(items)
            return real(painter, items, *a, **k)
        render.draw_texts = spy
        try:
            v.repaint()
            APP.processEvents()
            got = list(drawn)
            key = v._drawing_key()
            with self.p.edit("number") as ed:
                ed.change(self.s, self.s.entities[self.w2.id].copy(num="8888",
                                                                   num_lock=True))
            self.assertNotEqual(v._drawing_key(), key, "an edit on another sheet")
            drawn.clear()
            v.repaint()
            APP.processEvents()
        finally:
            render.draw_texts = real
        strs = lambda items: " ".join(str(x) for x in items)     # noqa: E731
        self.assertIn("FIELD", strs(got))
        self.assertIn("8888", strs(drawn))

    def test_dxf_and_report_sheet(self):
        self.labels_on()
        from kanzonascad import fileio
        path = os.path.join(tempfile.mkdtemp(), "panel.dxf")
        fileio.export_dxf(self.p, self.ps, path)
        import ezdxf
        texts = [e.dxf.text for e in ezdxf.readfile(path).modelspace().query("TEXT")]
        self.assertIn("%s → %s:1 (FIELD)" % (self.num(self.w2), self.lt.attrs["TAG"]), texts)
        # (a terminal's footprint goes out as TB1 with its number, not its shown TB1-1)
        ents, _rep = fileio.read_dxf(path)
        back = [e for e in ents if isinstance(e, M.Insert) and e.block.startswith("Terminal")]
        self.assertEqual([e.attrs.get("TAG") for e in back], [self.tb.attrs["TAG"]])
        self.assertIn("wiring", RS.kinds())
        head, rows = RS.table(self.p, "wiring")
        self.assertEqual((head, rows), (PW.HEAD, PW.rows(self.p)))

    def test_menu_command_shows_the_list(self):
        seen = {}
        real = dialogs.report_dialog
        dialogs.report_dialog = lambda _w, title, h, rows, *a: seen.update(title=title, h=h,
                                                                           rows=rows)
        try:
            self.win.acts["wiring_list"].trigger()
        finally:
            dialogs.report_dialog = real
        self.assertEqual(seen["h"], PW.HEAD)
        self.assertEqual(seen["rows"], PW.rows(self.p))


if __name__ == "__main__":
    unittest.main()
