"""A wire layer's color shown in its gauge label on every wire at once (the owner, 0.22.4, with
photos of 16 AWG and 14 AWG labels: "These wire colors aren't showing. None of them have it in
the whole project"; since 0.18.4 it showed only on wires turned on one by one with Wire color
label): Project properties, Schematic, "...and its color (14 AWG BLU)"; Wire color label still
turns it on or off for the wires picked, either way."""
import os
import tempfile
import unittest

from tests.util import APP, window

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wirenums


class WireColorShownTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()
        with self.p.edit("layer") as ed:
            ed.layer("WIRE BLU", None, M.Layer("WIRE BLU", "#0000ff", awg="16",
                                               wire_color="BLU").to_dict())
            ed.add(self.s, M.Wire([(1.0, 8.0), (9.0, 8.0)], layer="WIRE BLU"))
            ed.add(self.s, M.Wire([(1.0, 4.0), (9.0, 4.0)], layer="WIRE BLU"))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def labels(self):
        return sorted(t.text for t in wirenums.gauge_labels(self.p, self.s))

    def setting(self, on):
        with self.p.edit("colors") as ed:
            ed.project_settings({"wire_color_shown": on})

    def test_off_as_before_on_for_every_wire(self):
        self.assertEqual(self.labels(), ["16 AWG", "16 AWG"])
        self.setting(True)
        self.assertEqual(self.labels(), ["16 AWG BLU", "16 AWG BLU"])
        self.p.undo()
        self.assertEqual(self.labels(), ["16 AWG", "16 AWG"])

    def test_wire_color_label_turns_one_the_other_way(self):
        self.setting(True)
        top = [w for w in self.s.wires() if w.points[0][1] == 8.0][0]
        self.v.set_selection({top.id})
        self.v.run(C.WireColorLabelCmd)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        self.assertIs(self.s.entities[top.id].show_color, False)
        self.assertEqual(self.labels(), ["16 AWG", "16 AWG BLU"])
        self.setting(False)                         # (its own choice stays; the other follows)
        self.assertEqual(self.labels(), ["16 AWG", "16 AWG"])
        self.v.set_selection({top.id})
        self.v.run(C.WireColorLabelCmd)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        self.assertEqual(self.labels(), ["16 AWG", "16 AWG BLU"])

    def test_old_projects_and_the_three_choices_saved(self):
        # (a wire saved before 0.22.4 has show_color true or none: none follows the project,
        # which starts off, so it looks as it did)
        w = M.Wire.from_dict({"kind": "wire", "points": [[0, 0], [1, 0]], "id": 1})
        self.assertIsNone(w.show_color)
        on = M.Wire.from_dict({"kind": "wire", "points": [[0, 0], [1, 0]], "id": 2,
                               "show_color": True})
        self.assertIs(on.show_color, True)
        top = [w for w in self.s.wires() if w.points[0][1] == 8.0][0]
        with self.p.edit("off") as ed:
            ed.change(self.s, top.copy(show_color=False))
        self.setting(True)
        path = os.path.join(tempfile.mkdtemp(), "c.kzcad")
        self.p.save(path, backups=0)
        q = M.Project.load(path)
        s = q.sheet_by_id(self.s.id)
        self.assertTrue(q.settings["wire_color_shown"])
        self.assertEqual(sorted(str(w.show_color) for w in s.wires()), ["False", "None"])
        self.assertEqual(sorted(t.text for t in wirenums.gauge_labels(q, s)),
                         ["16 AWG", "16 AWG BLU"])

    def test_the_setting_in_project_properties(self):
        from PySide6.QtWidgets import QCheckBox, QDialog
        from kanzonascad import dialogs
        seen = {}

        def answer(dlg):
            box = dlg.findChild(QCheckBox, "wire_color_shown")
            seen["was"], seen["text"] = box.isChecked(), box.text()
            box.setChecked(True)
            return QDialog.Accepted
        real = dialogs.QDialog.exec
        dialogs.QDialog.exec = answer
        try:
            self.win.project_properties(1)
        finally:
            dialogs.QDialog.exec = real
        self.assertFalse(seen["was"])
        self.assertIn("14 AWG BLU", seen["text"])
        self.assertEqual(self.labels(), ["16 AWG BLU", "16 AWG BLU"])


if __name__ == "__main__":
    unittest.main()
