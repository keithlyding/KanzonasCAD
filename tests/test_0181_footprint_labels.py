"""Footprint labels (the owner, 0.18.1: "I need to be able to move footprint attributes (or
select where to display them). I also think the footprint font is too big. Also, the show tag
option needs to show for showing of more than one attribute. Also, once linked, I should be
able to see and show the attributes from the linked schematic device"; asked: 0.08", a grip
for each, edit from either): several lines shown at once, each with a grip of its own; their
own height (Panel settings, 0.08" to start; older projects take it); a linked device's ratings
on its footprint, the same both ways."""
import unittest
from unittest import mock

from PySide6.QtWidgets import QCheckBox, QDialog, QLineEdit

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import tags


def box(name="AB 100-C09"):
    return M.BlockDef(name, "footprint", [M.Polyline([(0, 0), (2, 0), (2, 4), (0, 4)], True)],
                      catalog="100-C09D10")


def ins(label, attrs=None, angle=0.0):
    return M.Insert("AB 100-C09", (10, 20), angle, 1.0, False,
                    attrs if attrs is not None else
                    {"TAG": "M1", "DESC": "Contactor 9A", "HP": "5"}, box(), 0.1, label)


class LabelLinesTest(unittest.TestCase):
    def test_several_lines_stacked_in_the_middle(self):
        e = ins("tag,cat,HP")
        got = e.label_texts()
        self.assertEqual([(k, t.text) for k, t in got],
                         [("tag", "M1"), ("cat", "100-C09D10"), ("HP", "5HP")])
        ys = [t.pos[1] for _k, t in got]
        self.assertAlmostEqual(ys[1], 22.0)                     # (the middle line: the middle)
        self.assertAlmostEqual(ys[0] - ys[1], M.LABEL_LINE * 0.1)
        self.assertAlmostEqual(ys[1] - ys[2], M.LABEL_LINE * 0.1)
        self.assertEqual({t.pos[0] for _k, t in got}, {11.0})
        # every line is drawn
        drawn = [w.text for w in e.world_entities() if isinstance(w, M.Text)]
        self.assertEqual(drawn, ["M1", "100-C09D10", "5HP"])

    def test_turned_stacks_across(self):
        got = ins("tag,cat", angle=90.0).label_texts()
        self.assertEqual({t.angle for _k, t in got}, {90.0})
        self.assertNotAlmostEqual(got[0][1].pos[0], got[1][1].pos[0])
        self.assertAlmostEqual(got[0][1].pos[1], got[1][1].pos[1])

    def test_an_empty_rating_has_no_line(self):
        self.assertEqual([k for k, _t in ins("tag,VOLTS,HP").label_texts()], ["tag", "HP"])

    def test_each_line_has_a_grip_and_moves_with_the_part(self):
        e = ins("tag,cat")
        names = [n for n, _q in e.text_grips()]
        self.assertEqual(names, ["@TAG", "@CAT"])
        moved = e.with_grip(2, (15.0, 30.0))                    # the part number dragged
        got = dict(moved.label_texts())
        self.assertEqual(tuple(got["cat"].pos), (15.0, 30.0))
        self.assertEqual(tuple(got["tag"].pos), tuple(dict(e.label_texts())["tag"].pos))
        later = moved.moved(1.0, 2.0)                           # it follows the part
        self.assertEqual(tuple(dict(later.label_texts())["cat"].pos), (16.0, 32.0))
        d = later.to_dict()                                     # and is saved
        back = M.Insert._from(d, {"AB 100-C09": box()})
        self.assertEqual(tuple(dict(back.label_texts())["cat"].pos), (16.0, 32.0))

    def test_saved_label_keys(self):
        self.assertEqual(M.label_keys("tag,cat,HP,bogus key,tag"), ["tag", "cat", "HP"])
        e = ins("cat,tag")
        self.assertEqual(M.Insert._from(e.to_dict(), {}).label, "cat,tag")


class FootprintLabelWindowTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.lib = self.win.library
        self.sch = self.v.sheet()
        self.v.run(C.InsertCmd, self.lib.get("symbol", "Relay coil"), {})
        type_in(self.v, "3,6")
        self.coil = self.sch.inserts()[0]
        with self.p.edit("rating") as ed:
            ed.change(self.sch, self.coil.copy(attrs=dict(self.coil.attrs, VOLTS="24")))
        self.panel = self.p.make_sheet("Panel")
        self.panel.kind = "panel"
        with self.p.edit("panel") as ed:
            ed.add_sheet(self.panel, 1)
        self.v.show_sheet(self.panel.id)
        fp = self.lib.get("footprint", sorted(self.lib.blocks("footprint")[0])[0])
        self.v.run(C.InsertCmd, fp, {})
        type_in(self.v, "5,5", "")                  # (Enter: the coil)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        self.fp = self.panel.inserts()[0]

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def coil_now(self):
        return self.sch.entities[self.coil.id]

    def fp_now(self):
        return self.panel.entities[self.fp.id]

    def test_new_footprint_label_height(self):
        self.assertAlmostEqual(self.fp_now().tag_h, 0.08 * self.panel.k())
        with self.p.edit("settings") as ed:
            ed.project_settings({"fp_label_height": 0.06})
        self.assertAlmostEqual(self.fp_now().tag_h, 0.06 * self.panel.k())

    def test_older_project_takes_the_new_height(self):
        d = self.p.to_dict()
        d["settings"] = {k: v for k, v in d["settings"].items() if k != "fp_label_height"}
        old_h = 0.1 * self.panel.k()                # (labels were the tag height)
        for sd in d["sheets"]:
            for ed_ in sd["entities"]:
                if ed_.get("label"):
                    ed_["tag_h"] = old_h
        q = M.Project.from_dict(d)
        e = [x for s in q.sheets for x in s.inserts() if x.label][0]
        self.assertAlmostEqual(e.tag_h, 0.08 * self.panel.k())

    def test_linked_ratings_follow_the_device(self):
        self.assertEqual(self.fp_now().attrs.get("VOLTS"), "24")
        with self.p.edit("rating") as ed:
            c = self.coil_now()
            ed.change(self.sch, c.copy(attrs=dict(c.attrs, VOLTS="120", HP="2")))
        self.assertEqual((self.fp_now().attrs.get("VOLTS"), self.fp_now().attrs.get("HP")),
                         ("120", "2"))

    def test_menu_shows_several_and_ticks(self):
        self.v.set_selection({self.fp.id})
        a = self.win.acts
        self.assertTrue(a["fp_label_tag"].isChecked())
        a["fp_label_cat"].trigger()
        self.assertEqual(M.label_keys(self.fp_now().label), ["tag", "cat"])
        self.assertTrue(a["fp_label_cat"].isChecked())
        a["fp_label_tag"].trigger()                             # (again: not any more)
        self.assertEqual(M.label_keys(self.fp_now().label), ["cat"])
        self.assertFalse(a["fp_label_tag"].isChecked())

    def test_window_shows_and_edits_the_device(self):
        def answer(dlg):
            boxes = {c.objectName(): c for c in dlg.findChildren(QCheckBox)}
            edits = {e.objectName(): e for e in dlg.findChildren(QLineEdit)}
            self.assertIn("label_VOLTS", boxes)                 # (the device's rating offered)
            self.assertEqual(edits["linked_VOLTS"].text(), "24")
            boxes["label_VOLTS"].setChecked(True)
            boxes["label_tag"].setChecked(True)
            edits["linked_VOLTS"].setText("480")
            return QDialog.Accepted
        steps = len(self.p.undo_stack)
        with mock.patch.object(QDialog, "exec", answer):
            self.win.edit_attributes(self.fp_now())
        self.assertEqual(len(self.p.undo_stack), steps + 1)     # one step
        self.assertEqual(self.coil_now().attrs.get("VOLTS"), "480")     # on the device
        self.assertEqual(M.label_keys(self.fp_now().label), ["tag", "VOLTS"])
        self.assertEqual([t.text for _k, t in self.fp_now().label_texts()],
                         [self.coil_now().attrs["TAG"], "480V"])
        self.p.undo()
        self.assertEqual(self.coil_now().attrs.get("VOLTS"), "24")
        self.assertEqual(self.fp_now().attrs.get("VOLTS"), "24")

    def test_unlinked_footprint_keeps_its_own(self):
        self.assertIsNotNone(tags.parent_of(self.p, self.fp_now()))
        with self.p.edit("unlink") as ed:
            e = self.fp_now()
            ed.change(self.panel, e.copy(attrs={k: v for k, v in e.attrs.items()
                                                if k not in ("PARENT", "TAG")}))
        with self.p.edit("own") as ed:
            e = self.fp_now()
            ed.change(self.panel, e.copy(attrs=dict(e.attrs, VOLTS="12")))
        self.assertEqual(self.fp_now().attrs.get("VOLTS"), "12")
        self.assertEqual(self.coil_now().attrs.get("VOLTS"), "24")


if __name__ == "__main__":
    unittest.main()
