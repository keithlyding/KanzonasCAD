"""Footprint label (the owner: "I need to be able to display either a part number or a name
(as needed, and easily) on footprint blocks"; any of tag, part number, description or block
name, switched for the selection)."""
import unittest

from tests.util import APP, window

from kanzonascad import block_editor as BE
from kanzonascad import model as M


def box(name="AB 100-C09", **kw):
    return M.BlockDef(name, "footprint", [M.Polyline([(0, 0), (2, 0), (2, 4), (0, 4)], True)],
                      catalog="100-C09D10", **kw)


class LabelModelTest(unittest.TestCase):
    def ins(self, label, attrs=None, angle=0.0, defn=None):
        return M.Insert("AB 100-C09", (10, 20), angle, 1.0, False,
                        attrs if attrs is not None else
                        {"TAG": "M1", "CAT": "100-C09D10", "DESC": "Contactor 9A"},
                        defn or box(), 0.1, label)

    def texts(self, e):
        return [w for w in e.world_entities() if isinstance(w, M.Text)]

    def test_each_kind(self):
        want = {"tag": "M1", "cat": "100-C09D10", "desc": "Contactor 9A", "name": "AB 100-C09"}
        for k, v in want.items():
            t = self.texts(self.ins(k))
            self.assertEqual([x.text for x in t], [v], k)
            self.assertEqual(tuple(t[0].pos), (11.0, 22.0))     # the middle of the part
            self.assertEqual((t[0].align, t[0].valign), ("center", "middle"))
            self.assertAlmostEqual(t[0].height, 0.1)
        self.assertEqual(self.texts(self.ins("")), [])
        # an empty attribute: "?" (the part number falls back on the block's own)
        self.assertEqual(self.texts(self.ins("tag", {}))[0].text, "?")
        self.assertEqual(self.texts(self.ins("cat", {}))[0].text, "100-C09D10")

    def test_turned_reads_from_the_right_and_label_spot(self):
        t = self.texts(self.ins("tag", angle=90.0))[0]
        self.assertEqual(t.angle, 90.0)
        t = self.texts(self.ins("tag", angle=180.0))[0]
        self.assertEqual(t.angle, 0.0)
        t = self.texts(self.ins("tag", defn=box(tag_pos=(1, 3.5))))[0]
        self.assertEqual(tuple(t.pos), (11.0, 23.5))

    def test_saved_and_old_files(self):
        e = self.ins("cat")
        d = e.to_dict()
        self.assertEqual(d["label"], "cat")
        self.assertEqual(M.Insert._from(d, {"AB 100-C09": box()}).label, "cat")
        self.assertNotIn("label", self.ins("").to_dict())
        self.assertEqual(M.Insert._from(dict(d, label="bogus"), {}).label, "")


class LabelWindowTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.s = self.v.sheet()
        b = box()
        with self.p.edit("place") as ed:
            ed.block(b)
            self.a = ed.add(self.s, M.Insert(b.name, (2, 2), 0, 1, False, {"TAG": "M1"},
                                             self.p.blocks[b.name], layer="PANEL"))
            self.b = ed.add(self.s, M.Insert(b.name, (6, 2), 0, 1, False, {"TAG": "M2"},
                                             self.p.blocks[b.name], layer="PANEL"))
            self.line = ed.add(self.s, M.Line((0, 0), (1, 1)))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def test_switch_the_selection_in_one_step(self):
        self.v.set_selection({self.a.id, self.b.id, self.line.id})
        steps = len(self.p.undo_stack)
        self.win.acts["fp_label_cat"].trigger()
        ents = self.s.entities
        self.assertEqual([ents[i].label for i in (self.a.id, self.b.id)], ["cat", "cat"])
        self.assertEqual(len(self.p.undo_stack), steps + 1)
        h = self.p.settings.get("tag_height") * self.s.k()
        self.assertAlmostEqual(ents[self.a.id].tag_h, h)
        self.win.acts["fp_label_tag"].trigger()
        self.assertEqual(ents[self.b.id].label_text().text, "M2")
        self.win.acts["fp_label_none"].trigger()
        self.assertIsNone(self.s.entities[self.a.id].label_text())
        self.p.undo()
        self.assertEqual(self.s.entities[self.a.id].label, "tag")
        # nothing selected: says so, changes nothing
        self.v.set_selection({self.line.id})
        self.assertEqual(self.win.footprint_label("desc"), 0)

    def test_menus(self):
        acts = {b.text().replace("&", "") for a in self.win.menuBar().actions() if a.menu()
                for b in a.menu().actions()}
        self.assertIn("Footprint label", acts)

    def test_block_editor_label_spot(self):
        b = box()
        proj, sess = BE.open_block(b)
        s = proj.sheets[0]
        marks = [e for e in s.entities.values() if e.layer == BE.LAYER_TAG]
        self.assertEqual([m.text for m in marks], [BE.LABEL_TEXT])
        res = BE.to_block(proj, sess)
        self.assertIsNone(res.defn.tag_pos)                # left alone: automatic
        self.assertEqual(res.defn.to_dict(), b.to_dict())
        with proj.edit("move") as ed:
            ed.change(s, marks[0].moved(0, 1.5))
        res = BE.to_block(proj, sess)
        self.assertEqual(res.defn.tag_pos, (1.0, 3.5))
        self.assertEqual(res.defn.tag_height, b.tag_height)
        with proj.edit("erase") as ed:
            ed.remove(s, marks[0].id)
        self.assertIsNone(BE.to_block(proj, sess).defn.tag_pos)


if __name__ == "__main__":
    unittest.main()
