"""A footprint's label lines hidden and shown again come back at the size they should be (the
owner, 0.26: "Footprint tag sizing not consistent when showing/hiding"). Up to 0.25 a footprint
with every line hidden (the Footprint label menu's none, the attributes window's or the
Properties panel's Shown on it unticked) kept nothing of its label's sizing: Panel settings'
Footprint label height changed meanwhile left it at the old height, and its sheet's drawing
units per paper inch (label_k) were taken afresh when a line was shown again, so on a sheet
whose scale changed with its text kept as it was, the lines with sizes of their own came back
larger or smaller than the others."""
import json
import os
import tempfile
import unittest

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import scalefit


class HideShowTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()
        fpdef = self.win.library.get("footprint", "Breaker 1-pole (DIN)")
        with self.p.edit("panel") as ed:
            ed.sheet_meta(self.s, scale=0.25, kind="panel")
            ed.block(fpdef)
        self.fps = []
        for x in (5, 9):
            ins = M.Insert(fpdef.name, (x, 5), defn=self.p.blocks[fpdef.name],
                           attrs={"TAG": "CB%d" % x, "CAT": "1489-M1C"})
            # (as Insert places a footprint: its label at the project's height on its sheet)
            ins = ins.copy(label="tag,cat", tag_h=0.08 * self.s.k())
            with self.p.edit("add") as ed:
                self.fps.append(ed.add(self.s, ins))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def heights(self, f):
        return {k: round(t.height, 9) for k, t in self.s.entities[f.id].label_texts()}

    def show(self, f, label):
        """Shown on it, as the attributes window and the Properties panel change it."""
        cur = self.s.entities[f.id]
        with self.p.edit("Attributes") as ed:
            for sh, e in self.win.attribute_changes(self.p, self.s, cur, dict(cur.attrs),
                                                    {"label": label}):
                ed.change(sh, e)

    def test_project_height_changed_while_hidden(self):
        f, g = self.fps
        self.show(f, "")
        with self.p.edit("Project properties") as ed:
            ed.project_settings({"fp_label_height": 0.1})
        self.show(f, "tag,cat")
        self.assertEqual(self.heights(f), {"tag": 0.4, "cat": 0.4})
        self.assertEqual(self.heights(f), self.heights(g))

    def test_through_the_footprint_label_menu(self):
        f, g = self.fps
        self.v.set_selection({f.id})
        self.win.footprint_label("", None)
        with self.p.edit("Project properties") as ed:
            ed.project_settings({"fp_label_height": 0.12})
        self.win.footprint_label("tag", True)
        self.assertEqual(self.heights(f), {"tag": 0.48})
        self.assertEqual(self.heights(f)["tag"], self.heights(g)["tag"])

    def test_scale_changed_text_kept_while_hidden(self):
        f, g = self.fps
        with self.p.edit("sizes") as ed:
            for e in (f, g):
                ed.change(self.s, self.s.entities[e.id].copy(label_sizes={"TAG": 0.2}))
        before = self.heights(f)
        self.assertEqual(before, {"tag": 0.8, "cat": 0.32})
        self.show(f, "")
        # (Sheet scale, "Text and dimensions keep their size on paper" off: nothing changes)
        scalefit.apply(self.p, self.s, "", 0.5, paper_text=False)
        self.show(f, "tag,cat")
        self.assertEqual(self.heights(f), before)
        self.assertEqual(self.heights(g), before)

    def test_kept_hidden_through_save_open_and_undo(self):
        f, _g = self.fps
        with self.p.edit("sizes") as ed:
            ed.change(self.s, self.s.entities[f.id].copy(label_sizes={"TAG": 0.2}))
        before = self.heights(f)
        self.show(f, "")
        self.assertEqual(self.s.entities[f.id].label_k, 4.0)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "p.kzcad")
            self.p.save(path, backups=0)
            q = M.Project.load(path)
        e = q.sheets[0].entities[f.id]
        self.assertEqual(e.label_k, 4.0)
        # (opened, its sheet's scale changed with the text kept, then shown: as it was)
        with q.edit("scale") as ed:
            ed.sheet_scale(q.sheets[0], 0.5, paper_text=False)
        with q.edit("show") as ed:
            ed.change(q.sheets[0], q.sheets[0].entities[f.id].copy(label="tag,cat"))
        self.assertEqual({k: round(t.height, 9) for k, t in
                          q.sheets[0].entities[f.id].label_texts()}, before)
        q.saved_at = len(q.undo_stack)
        self.p.undo()
        self.assertEqual(self.heights(f), before)
        self.p.redo()
        self.assertEqual(self.heights(f), {})
        d = json.loads(json.dumps(self.p.to_dict()))
        self.assertEqual([x.get("label_k") for x in d["sheets"][0]["entities"]
                          if x.get("id") == f.id], [4.0])


if __name__ == "__main__":
    unittest.main()
