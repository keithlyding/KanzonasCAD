"""Footprints show their tag and get it as they are placed (the owner, 0.16: "Footprints need
to be able to show its tag. Also, I need parts to auto label when inserting footprints in a
panel drawing"): placing a footprint asks which schematic device it is (Enter: the next one
with no footprint, a typed tag, L to list, N for none), links it (its tag follows the
device's), and it shows its tag to start (Panel settings: New footprints show)."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import bom
from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import tags


class FootprintTagTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.lib = self.win.library
        self.sch = self.v.sheet()
        for at in ("3,6", "3,4", "3,2"):
            self.v.run(C.InsertCmd, self.lib.get("symbol", "Relay coil"), {})
            type_in(self.v, at)
        self.coils = sorted(self.sch.inserts(), key=lambda e: e.attrs["TAG"])
        self.panel = self.p.make_sheet("Panel")
        self.panel.kind = "panel"
        with self.p.edit("panel") as ed:
            ed.add_sheet(self.panel, 1)
        self.v.show_sheet(self.panel.id)
        self.fp = self.lib.get("footprint", sorted(self.lib.blocks("footprint")[0])[0])

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def place(self, at, *keys, attrs=None):
        before = set(self.panel.entities)
        self.v.run(C.InsertCmd, self.fp, attrs or {})
        type_in(self.v, at, *keys)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        return [e for i, e in self.panel.entities.items() if i not in before][0]

    def test_enter_takes_the_next_device(self):
        a = self.place("5,5")
        b = self.place("9,5")
        self.assertEqual([a.attrs["TAG"], b.attrs["TAG"]],
                         [self.coils[0].attrs["TAG"], self.coils[1].attrs["TAG"]])
        self.assertEqual(a.attrs["PARENT"], self.coils[0].attrs["DEV"])
        self.assertEqual(a.label, "tag")
        self.assertEqual(a.label_text().text, a.attrs["TAG"])          # (shown on it)

    def test_typed_tag_and_none(self):
        last = self.coils[2].attrs["TAG"]
        a = self.place("5,5", last)
        self.assertEqual(a.attrs["TAG"], last)
        b = self.place("9,5", "N")
        self.assertNotIn("TAG", b.attrs)
        self.assertEqual(b.label, "name")                   # (no tag: its block's name)
        self.assertEqual(b.label_value(), self.fp.name)

    def test_the_list(self):
        self.win.pick_parent = lambda cands: cands[-1]
        a = self.place("5,5", "L")
        self.assertEqual(a.attrs["TAG"], self.coils[2].attrs["TAG"])

    def test_the_matching_part_first(self):
        with self.p.edit("cat") as ed:
            c = self.coils[2]
            ed.change(self.sch, c.copy(attrs=dict(c.attrs, CAT="700-HC14A1")))
        a = self.place("5,5", attrs={"CAT": "700-HC14A1"})
        self.assertEqual(a.attrs["TAG"], self.coils[2].attrs["TAG"])

    def test_its_tag_follows_the_device(self):
        a = self.place("5,5")
        c = self.coils[0]
        with self.p.edit("renumber") as ed:
            ed.change(self.sch, c.copy(attrs=dict(c.attrs, TAG="CR699", TAG_LOCK="1")))
        self.assertEqual(self.panel.entities[a.id].attrs["TAG"], "CR699")
        self.assertEqual(self.panel.entities[a.id].label_value(), "CR699")

    def test_one_part_on_the_bill_of_materials(self):
        self.place("5,5")
        relays = [r for r in bom.rows(self.p) if r["kind"] == "part"]
        self.assertEqual(sum(r["qty"] for r in relays), 3)    # (3 coils, one with a footprint)

    def test_no_device_left_and_the_setting(self):
        for at in ("5,5", "9,5", "13,5"):
            self.place(at)
        d = self.place("5,9")                       # (every coil has its footprint)
        self.assertNotIn("TAG", d.attrs)
        self.p.settings["footprint_label"] = ""
        e = self.place("9,9")
        self.assertEqual(e.label, "")

    def test_a_tag_typed_on_the_footprint_relinks_it(self):
        a = self.place("5,5")
        other = self.coils[1]
        from kanzonascad import library_panel
        saved = library_panel.attributes_dialog
        library_panel.attributes_dialog = lambda *args, **kw: dict(a.attrs,
                                                                  TAG=other.attrs["TAG"])
        try:
            self.win.edit_attributes(a)
        finally:
            library_panel.attributes_dialog = saved
        now = self.panel.entities[a.id]
        self.assertEqual(now.attrs["PARENT"], other.attrs["DEV"])
        library_panel.attributes_dialog = lambda *args, **kw: dict(now.attrs, TAG="XX9")
        try:
            self.win.edit_attributes(now)
        finally:
            library_panel.attributes_dialog = saved
        now = self.panel.entities[a.id]
        self.assertEqual(now.attrs["TAG"], "XX9")
        self.assertNotIn("PARENT", now.attrs)


if __name__ == "__main__":
    unittest.main()
