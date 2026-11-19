"""Footprint labels in a color of their own (the owner, 0.18.7: "Footprints are generally going
to be layer 0, which is white/gray. I want the tagname to be discernible"; asked: a setting in
Panel settings)."""
import os
import tempfile
import unittest

from tests.util import APP, window

from kanzonascad import model as M


def box():
    return M.BlockDef("AB 100-C09", "footprint",
                      [M.Polyline([(0, 0), (2, 0), (2, 4), (0, 4)], True)])


class LabelColorTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()
        with self.p.edit("fp") as ed:
            ed.block(box())
            self.fp = ed.add(self.s, M.Insert("AB 100-C09", (10, 20), 0.0, 1.0, False,
                                              {"TAG": "M1"}, self.p.blocks["AB 100-C09"],
                                              0.1, "tag"))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def colors(self):
        e = self.s.entities[self.fp.id]
        texts = [w for w in e.world_entities() if isinstance(w, M.Text)]
        lines = [w for w in e.world_entities() if not isinstance(w, M.Text)]
        return {w.color for w in texts}, {w.color for w in lines}

    def test_setting(self):
        self.assertEqual(self.colors(), ({None}, {None}))       # (the footprint's: layer 0)
        with self.p.edit("color") as ed:
            ed.project_settings({"fp_label_color": "#00ffff"})
        self.assertEqual(self.colors(), ({"#00ffff"}, {None}))  # (the outline stays)
        path = os.path.join(tempfile.mkdtemp(), "x.kzcad")
        self.p.save(path)
        q = M.Project.load(path)
        e = q.sheets[0].entities[self.fp.id]
        self.assertEqual({w.color for w in e.world_entities() if isinstance(w, M.Text)},
                         {"#00ffff"})
        self.p.undo()
        self.assertEqual(self.colors(), ({None}, {None}))

    def test_new_ones_take_it_and_the_window(self):
        from PySide6.QtWidgets import QDialog, QCheckBox
        from kanzonascad import dialogs
        real = dialogs.QDialog.exec

        def answer(dlg):
            dlg.findChild(QCheckBox, "fp_label_color_on").setChecked(True)
            return QDialog.Accepted
        try:
            dialogs.QDialog.exec = answer
            self.win.project_properties(2)
        finally:
            dialogs.QDialog.exec = real
        self.assertEqual(self.p.settings["fp_label_color"], "#00ffff")
        self.assertEqual(self.colors()[0], {"#00ffff"})
        from kanzonascad import commands as C
        self.v.run(C.InsertCmd, self.p.blocks["AB 100-C09"], {})
        self.v.cmd.point((30.0, 20.0))
        if self.v.cmd is not None:
            self.v.cmd.enter()                                  # (a footprint of its own)
        self.v.cancel()
        new = [e for e in self.s.inserts() if e.id != self.fp.id]
        self.assertTrue(new)
        self.assertEqual(new[-1].label_color, "#00ffff")


if __name__ == "__main__":
    unittest.main()
