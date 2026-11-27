"""Contact pin numbers (0.28; the owner, Nov 27 2026: "13/14 and 21/22"): a contact placed is
numbered on its device the makers' way (its first NO 13-14, its first NC 21-22, then the
lowest free sequence: 31-32 NC, 33-34 NO...; timed contacts x5-x6 and x7-x8; an overload's
95-96 and 97-98); a copy or a contact moved to another device keeps its numbers unless that
device has them, then takes the next free pair; numbers typed are kept; drawings of before
0.28 keep 1 and 2. The numbers show on the drawing, in the cross-references under the coil,
in Trace, in the wiring list and the terminal wire labels, which find the screws of the same
names on the contactor and relay footprints (the control relays got pins)."""
import os
import tempfile
import unittest

from tests.util import APP, window, type_in, by_base_point

from kanzonascad import commands as C
from kanzonascad import fileio
from kanzonascad import model as M
from kanzonascad import panelwiring as PW
from kanzonascad import pinnumbers as PN
from kanzonascad import props_panel
from kanzonascad import tags
from kanzonascad import where_used
from kanzonascad import xrefs
from kanzonascad.footprints_generic import builtin_footprints


class ContactPinsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = p = self.v.project
        self.s = s = self.v.sheet()
        lib = self.win.library
        self.b = {n: lib.get("symbol", n) for n in (
            "Relay coil", "Contactor coil", "Contact NO", "Contact NC", "Contact NO timed close",
            "Contact NC timed open", "Timer coil", "Overload heaters 3-pole",
            "Overload contact NC", "Pushbutton NO", "Pushbutton contact NC",
            "Contactor power contacts 3-pole")}
        with p.edit("blocks") as ed:
            for b in self.b.values():
                ed.block(p.blocks.get(b.name) or b)
            self.cr = self.dev(ed, "Relay coil", (5, 5))
            self.cr2 = self.dev(ed, "Relay coil", (5, 3))
        p.undo_stack.clear()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def dev(self, ed, name, at):
        d = self.p.blocks[name]
        return ed.add(self.s, M.Insert(name, at, defn=d,
                                       attrs=tags.new_attrs(self.p, self.s, d, {})))

    def place(self, name, at, device=None, attrs=None):
        """A contact added in an edit of its own (as Insert adds it), linked to device."""
        d = self.p.blocks[name]
        a = dict(attrs or {})
        if device is not None:
            a = tags.link_attrs(a, device)
        with self.p.edit("Insert") as ed:
            e = ed.add(self.s, M.Insert(name, at, defn=d, attrs=a))
        return self.s.entities[e.id]

    def nums(self, e):
        return PN.numbers(self.s.entities[e.id])

    # ---- the rule -------------------------------------------------------------------------
    def test_first_no_and_nc_then_the_lowest_free_sequence(self):
        got = [self.nums(self.place(n, (6 + i, 8), self.cr)) for i, n in enumerate(
            ("Contact NO", "Contact NC", "Contact NC", "Contact NO", "Contact NO"))]
        self.assertEqual(got, [["13", "14"], ["21", "22"], ["31", "32"], ["43", "44"],
                               ["53", "54"]])

    def test_an_nc_drawn_first_is_still_21_22(self):
        got = [self.nums(self.place(n, (6 + i, 8), self.cr)) for i, n in enumerate(
            ("Contact NC", "Contact NO", "Contact NC"))]
        self.assertEqual(got, [["21", "22"], ["13", "14"], ["31", "32"]])

    def test_two_no_contacts_take_sequence_two(self):
        got = [self.nums(self.place(n, (6 + i, 8), self.cr)) for i, n in enumerate(
            ("Contact NO", "Contact NO", "Contact NC"))]
        self.assertEqual(got, [["13", "14"], ["23", "24"], ["31", "32"]])

    def test_sequence_counts_contacts_on_every_sheet(self):
        self.place("Contact NO", (6, 8), self.cr)
        with self.p.edit("sheet") as ed:
            s2 = self.p.make_sheet("Two")
            ed.add_sheet(s2)
            e = ed.add(s2, M.Insert("Contact NO", (3, 3), defn=self.p.blocks["Contact NO"],
                                    attrs=tags.link_attrs({}, self.cr)))
        self.assertEqual(PN.numbers(s2.entities[e.id]), ["23", "24"])

    def test_devices_are_numbered_apart(self):
        a = self.place("Contact NO", (6, 8), self.cr)
        b = self.place("Contact NO", (7, 8), self.cr2)
        self.assertEqual((self.nums(a), self.nums(b)), (["13", "14"], ["13", "14"]))

    def test_timed_contacts(self):
        with self.p.edit("timer") as ed:
            tr = self.dev(ed, "Timer coil", (9, 5))
        a = self.place("Contact NO timed close", (6, 8), tr)
        b = self.place("Contact NC timed open", (7, 8), tr)
        c = self.place("Contact NO", (8, 8), tr)
        self.assertEqual([self.nums(x) for x in (a, b, c)],
                         [["17", "18"], ["25", "26"], ["33", "34"]])

    def test_overload_contacts_95_96(self):
        with self.p.edit("ol") as ed:
            ol = self.dev(ed, "Overload heaters 3-pole", (9, 5))
        a = self.place("Overload contact NC", (6, 8), ol)
        b = self.place("Overload contact NC", (7, 8), ol)       # (95-96 taken)
        # (95-96 taken: the rule for any NC, its device's first plain NC sequence 2)
        self.assertEqual((self.nums(a), self.nums(b)), (["95", "96"], ["21", "22"]))

    def test_a_contact_on_its_own(self):
        self.assertEqual(self.nums(self.place("Contact NC", (6, 8))), ["21", "22"])

    def test_pushbutton_and_its_contact_block(self):
        with self.p.edit("pb") as ed:
            pb = self.dev(ed, "Pushbutton NO", (9, 5))
        self.assertEqual(self.nums(pb), ["13", "14"])
        blk = self.place("Pushbutton contact NC", (9, 4), pb)
        self.assertEqual(self.nums(blk), ["21", "22"])

    def test_power_contacts_and_coils_keep_their_names(self):
        k = self.place("Contactor power contacts 3-pole", (6, 8), self.cr)
        e = self.s.entities[k.id]
        self.assertFalse(PN.numberable(e))
        self.assertEqual([e.pin_number(n) for n, _q in e.pin_points()],
                         ["L1", "L2", "L3", "T1", "T2", "T3"])
        self.assertFalse(any(x.startswith("TERM") for x in e.attrs))
        self.assertFalse(PN.numberable(self.cr))

    def test_insert_command_numbers_it(self):
        tag = self.cr.attrs["TAG"]
        self.v.run(C.InsertCmd, self.p.blocks["Contact NC"], {})
        by_base_point(self.v)
        type_in(self.v, "7,8", tag)
        if self.v.cmd is not None:
            self.v.cmd.cancel()
        got = [e for e in self.s.inserts() if e.block == "Contact NC"]
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].attrs.get("PARENT"), self.cr.attrs["DEV"])
        self.assertEqual(PN.numbers(got[0]), ["21", "22"])
        self.p.undo()
        self.assertEqual([e for e in self.s.inserts() if e.block == "Contact NC"], [])
        self.p.redo()
        got = [e for e in self.s.inserts() if e.block == "Contact NC"]
        self.assertEqual(PN.numbers(got[0]), ["21", "22"])

    # ---- copies, other devices, typed numbers, old drawings ------------------------------------
    def test_copy_takes_the_next_free_pair(self):
        a = self.place("Contact NO", (6, 8), self.cr)
        self.v.set_selection({a.id})
        self.v.run(C.CopyCmd)
        type_in(self.v, "6,8", "@1,0")
        if self.v.cmd is not None:
            self.v.cmd.enter()
        new = [e for e in self.s.inserts() if e.block == "Contact NO" and e.id != a.id]
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0].attrs.get("PARENT"), self.cr.attrs["DEV"])
        self.assertEqual(PN.numbers(new[0]), ["23", "24"])
        self.assertEqual(self.nums(a), ["13", "14"])

    def test_moved_to_another_device_keeps_or_takes_the_next(self):
        a = self.place("Contact NO", (6, 8), self.cr)
        b = self.place("Contact NC", (7, 8), self.cr2)
        self.place("Contact NO", (8, 8), self.cr2)
        with self.p.edit("relink") as ed:
            ed.change(self.s, self.s.entities[b.id].copy(
                attrs=tags.link_attrs(self.s.entities[b.id].attrs, self.cr)))
        self.assertEqual(self.nums(b), ["21", "22"])         # (free on CR1: kept)
        with self.p.edit("relink") as ed:
            ed.change(self.s, self.s.entities[a.id].copy(
                attrs=tags.link_attrs(self.s.entities[a.id].attrs, self.cr2)))
        self.assertEqual(self.nums(a), ["23", "24"])         # (13-14 taken on CR2)

    def test_typed_numbers_are_kept(self):
        a = self.place("Contact NO", (6, 8), self.cr)
        b = self.place("Contact NO", (7, 8), self.cr)
        e = self.s.entities[b.id]
        fields = props_panel.block_fields(self.win, self.p, self.s, [e])
        f = [x for x in fields if x.key == "pin_numbers"][0]
        self.assertEqual(f.get(e), "23-24")
        with self.p.edit("typed") as ed:
            f.put(ed, self.s, e, "13-14")
        self.assertEqual(self.nums(b), ["13", "14"])           # (as typed, though taken)
        with self.p.edit("typed") as ed:
            f.put(ed, self.s, self.s.entities[b.id], "13")    # (not two: left alone)
        self.assertEqual(self.nums(b), ["13", "14"])
        with self.p.edit("typed") as ed:
            f.put(ed, self.s, self.s.entities[b.id], "")      # (blank: its block's)
        self.assertEqual(self.nums(b), ["1", "2"])
        # typed and moved to another device in one step: still as typed, though taken there
        self.place("Contact NO", (8, 8), self.cr2)                  # (13-14 on CR2)
        e = self.s.entities[a.id]
        with self.p.edit("both") as ed:
            ed.change(self.s, e.copy(attrs=PN.with_numbers(tags.link_attrs(e.attrs, self.cr2),
                                                           ["14", "13"])))
        self.assertEqual(self.nums(a), ["14", "13"])

    def test_old_contacts_keep_1_and_2(self):
        d = self.p.blocks["Contact NO"]
        old = M.Insert("Contact NO", (6, 8), defn=d, attrs=tags.link_attrs({}, self.cr))
        self.s._put(old)                    # (as a drawing of before 0.28 opens)
        self.assertEqual(PN.numbers(old), ["1", "2"])
        with self.p.edit("Move") as ed:
            ed.change(self.s, old.moved(1.0, 0.0))
        with self.p.edit("relink") as ed:
            e = self.s.entities[old.id]
            ed.change(self.s, e.copy(attrs=tags.link_attrs(e.attrs, self.cr2)))
        self.assertEqual(self.nums(old), ["1", "2"])
        path = os.path.join(tempfile.mkdtemp(), "old.kzcad")
        self.p.save(path)
        q = M.Project.load(path)
        e = [x for x in q.sheets[0].inserts() if x.block == "Contact NO"][0]
        self.assertEqual(PN.numbers(e), ["1", "2"])
        self.assertIsNone(PN.own(e))
        # a new one beside it on that device: 13-14 (1-2 is no sequence)
        self.assertEqual(self.nums(self.place("Contact NO", (8, 8), self.cr2)), ["13", "14"])

    # ---- where they show -------------------------------------------------------------------
    def test_shown_on_the_drawing_and_in_the_references(self):
        a = self.place("Contact NO", (6, 8), self.cr)
        e = self.s.entities[a.id]
        self.assertEqual(sorted(t.text for t in e.pin_texts()), ["13", "14"])
        lines = [t[2] for t in xrefs.shown(self.p, self.s)]
        self.assertTrue(any(t.startswith("NO 13-14 ") for t in lines), lines)
        self.assertEqual(where_used.role(e), "NO contact 13-14")

    def test_dxf_keeps_them(self):
        self.place("Contact NC", (6, 8), self.cr)
        path = os.path.join(tempfile.mkdtemp(), "pins.dxf")
        fileio.export_dxf(self.p, self.s, path)
        import ezdxf
        doc = ezdxf.readfile(path)
        refs = [r for r in doc.modelspace().query("INSERT") if r.dxf.name.startswith("Contact")]
        self.assertEqual(len(refs), 1)
        att = {a.dxf.tag: a.dxf.text for a in refs[0].attribs}
        self.assertEqual((att.get("TERM01"), att.get("TERM02")), ("21", "22"))
        texts = {t.dxf.text for t in doc.modelspace().query("TEXT")}
        self.assertTrue({"21", "22"} <= texts, texts)
        ents, _report = fileio.read_dxf(path)
        ins = [e for e in ents if isinstance(e, M.Insert) and e.block.startswith("Contact")]
        self.assertEqual(PN.numbers(ins[0]), ["21", "22"])

    def test_wiring_list_and_labels_find_the_footprints_screws(self):
        lib = self.win.library
        fp = lib.get("footprint", "Relay, ice cube 8-pin with base")
        a = self.place("Contact NO", (6, 8), self.cr)
        b = self.place("Contact NC", (6, 7), self.cr)
        ea, eb = self.s.entities[a.id], self.s.entities[b.id]
        with self.p.edit("wire") as ed:
            ed.block(self.p.blocks.get(fp.name) or fp)
            pa, pb = dict(ea.pin_points()), dict(eb.pin_points())
            ed.add(self.s, M.Wire([pa["2"], pb["1"]]))
            ps = self.p.make_sheet("Panel", "panel")
            ed.add_sheet(ps)
            f = ed.add(ps, M.Insert(fp.name, (5, 5), defn=self.p.blocks[fp.name],
                                    attrs=tags.link_footprint({}, self.cr)))
            ed.sheet_meta(ps, terminal_labels=True)
        tag = self.cr.attrs["TAG"]
        rows = {r[1]: r for r in PW.rows(self.p) if r[0] == tag}
        for n in ("A1", "A2", "13", "14", "21", "22"):
            self.assertIn(n, rows)
            self.assertFalse(rows[n][9].startswith("no "), rows[n])
        self.assertEqual(rows["14"][6], "%s:21" % tag)
        texts = [t.text for t in PW.labels(self.p, ps)]
        self.assertEqual(len(texts), 2, texts)
        self.assertTrue(all(t.endswith(tag + ":21") or t.endswith(tag + ":14") for t in texts),
                        texts)
        pins = dict(self.p.blocks[fp.name].pins and
                    [(p["name"], p["pos"]) for p in self.p.blocks[fp.name].pins])
        at = {round(t.pos[1], 3) for t in PW.labels(self.p, ps)}
        self.assertEqual(len(at), 2)
        self.assertIsNotNone(f)
        self.assertEqual(pins["13"], pins["11"])            # (pole 1's common: both)

    # ---- the footprints ----------------------------------------------------------------------
    def test_footprints_have_the_contact_screws(self):
        fps = {b.name: b for b in builtin_footprints()}
        want = {"Contactor 9-18 A": {"A1", "A2", "13", "14", "21", "22", "L1", "T3"},
                "Contactor 25-38 A": {"A1", "A2", "13", "14", "21", "22"},
                "Overload relay 9-18 A": {"95", "96", "97", "98", "L1", "T3"},
                "Relay, ice cube 8-pin with base": {"A1", "A2", "13", "14", "21", "22",
                                                    "11", "12", "23", "24"},
                "Relay, ice cube 14-pin with base": {"A1", "A2"} | {
                    "%d%d" % (n, k) for n in range(1, 5) for k in range(1, 5)},
                "Relay, slim interface 6 mm": {"A1", "A2", "11", "12", "13", "14"},
                "Timer relay 22.5 mm": {"A1", "A2", "15", "16", "17", "18", "25", "26", "27",
                                        "28"}}
        for name, names in want.items():
            have = [p["name"] for p in fps[name].pins]
            self.assertEqual(len(have), len(set(have)), name)
            self.assertTrue(names <= set(have), (name, sorted(names - set(have))))
            bb = fps[name].entities[0].bbox()          # (each inside its outline)
            for p in fps[name].pins:
                x, y = p["pos"]
                self.assertTrue(bb[0] < x < bb[2] and bb[1] < y < bb[3], (name, p))


if __name__ == "__main__":
    unittest.main()
