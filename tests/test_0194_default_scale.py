"""The project's scale for new sheets, one for panel sheets and one for every other kind,
each sheet's own afterward (the owner, 0.19.4: "a project default for scale, which can be
overridden on individual sheets"; asked: one per kind, new sheets only)."""
import os
import tempfile
import unittest

from PySide6.QtWidgets import QComboBox

from tests.util import APP, window

from kanzonascad import dialogs
from kanzonascad import model as M


class DefaultScaleTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def set_defaults(self, schematic, panel):
        with self.p.edit("scales") as ed:
            ed.project_settings({"scale_schematic": list(schematic),
                                 "scale_panel": list(panel)})

    def new_sheet_after(self, sheet):
        self.v.show_sheet(sheet.id)
        before = {s.id for s in self.p.sheets}
        self.win.add_sheet()
        return [s for s in self.p.sheets if s.id not in before][0]

    def test_starts_at_one_to_one(self):
        self.assertEqual(self.p.sheets[0].scale, 1.0)
        self.assertEqual(self.p.default_scale("panel"), (1.0, ""))

    def test_new_sheets_take_their_kinds_scale(self):
        first = self.p.sheets[0]
        self.set_defaults((0.5, ""), (1 / 48, '1/4" = 1\'-0"'))
        s = self.new_sheet_after(first)
        self.assertEqual((s.kind, s.scale, s.scale_name), ("schematic", 0.5, ""))
        with self.p.edit("panel") as ed:
            ed.sheet_meta(s, kind="panel")
        t = self.new_sheet_after(s)                 # (a panel sheet after a panel sheet)
        self.assertEqual((t.kind, t.scale, t.scale_name),
                         ("panel", 1 / 48, '1/4" = 1\'-0"'))
        # (the sheets already made keep theirs; s keeps its own after its kind changed)
        self.assertEqual(first.scale, 1.0)
        self.assertEqual(s.scale, 0.5)
        # (report and other sheets: the schematic one)
        self.assertEqual(self.p.make_sheet("R", "report").scale, 0.5)
        self.assertEqual(self.p.make_sheet("O", "other").scale, 0.5)

    def test_a_sheets_own_scale_overrides(self):
        self.set_defaults((1 / 4, ""), (1 / 8, ""))
        s = self.new_sheet_after(self.p.sheets[0])
        with self.p.edit("Sheet scale") as ed:
            ed.sheet_scale(s, 1 / 10)
        self.assertEqual(s.scale, 1 / 10)
        self.set_defaults((1 / 2, ""), (1 / 8, ""))  # (changed again: s keeps its own)
        self.assertEqual(s.scale, 1 / 10)

    def test_kept_in_the_file_and_undone(self):
        self.set_defaults((1 / 3, ""), (1 / 12, '1" = 1\'-0"'))
        fd, path = tempfile.mkstemp(suffix=".kcad")
        os.close(fd)
        try:
            self.p.save(path)
            q = M.Project.load(path)
        finally:
            os.remove(path)
        self.assertEqual(q.default_scale("schematic"), (1 / 3, ""))
        self.assertEqual(q.default_scale("panel"), (1 / 12, '1" = 1\'-0"'))
        self.p.undo()
        self.assertEqual(self.p.default_scale("panel"), (1.0, ""))

    def test_unreadable_setting_is_one_to_one(self):
        self.p.settings["scale_panel"] = "junk"
        self.assertEqual(self.p.default_scale("panel"), (1.0, ""))
        self.p.settings["scale_panel"] = [0, ""]
        self.assertEqual(self.p.default_scale("panel"), (1.0, ""))

    def test_box_shows_and_reads_a_scale(self):
        for k, name in ((1 / 4, ""), (1 / 48, '1/4" = 1\'-0"'), (1 / 7, "")):
            box = dialogs._scale_box(k, name)
            self.assertIsInstance(box, QComboBox)
            got = dialogs._scale_of(box)
            self.assertEqual(got[0], name)
            self.assertAlmostEqual(got[1], k)


if __name__ == "__main__":
    unittest.main()
