"""0.19.6, the owner's answers: a sheet with nothing on it takes the project's scale for a
kind it is changed to ("If nothing on the page, change to default scale"); and an arrow's
device line passes through terminals to the device past them ("Yes")."""
import unittest

from PySide6.QtWidgets import QComboBox, QDialog

from tests.util import APP, window

from kanzonascad import dialogs
from kanzonascad import model as M
from kanzonascad import xrefs
from kanzonascad.wirenums import ARROWS


class KindScaleTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        with self.p.edit("scales") as ed:
            ed.project_settings({"scale_schematic": [1.0, ""], "scale_panel": [1 / 8, ""]})

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_empty_sheet_takes_the_kinds_scale(self):
        s = self.p.sheets[0]
        self.assertEqual(self.p.kind_scale(s, "panel"), (1 / 8, ""))
        self.assertEqual(self.p.kind_scale(s, "report"), (1.0, ""))
        with self.p.edit("a line") as ed:
            ed.add(s, M.Line((0, 0), (1, 1)))
        self.assertIsNone(self.p.kind_scale(s, "panel"))       # (something on it: its own)
        self.assertIsNone(self.p.kind_scale(self.p.title_block, "panel"))

    def run_dialog(self, sheet, kind):
        """Sheet properties with its kind changed, then OK."""
        seen = {}

        def answer(dlg):
            box = [w for w in dlg.findChildren(QComboBox) if w.findData("panel") >= 0
                   and w.findData("schematic") >= 0][0]
            box.setCurrentIndex(box.findData(kind))
            seen["scale"] = dlg.findChild(QComboBox, "scale").currentText()
            return QDialog.Accepted
        old = QDialog.exec
        QDialog.exec = answer
        try:
            dialogs.sheet_properties(self.win, self.p, sheet)
        finally:
            QDialog.exec = old
        return seen["scale"]

    def test_sheet_properties_changes_an_empty_sheets_scale(self):
        s = self.p.sheets[0]
        shown = self.run_dialog(s, "panel")
        self.assertEqual((s.kind, s.scale), ("panel", 1 / 8))
        self.assertIn("8", shown)
        self.p.undo()
        self.assertEqual((s.kind, s.scale), ("schematic", 1.0))

    def test_a_sheet_with_a_drawing_keeps_its_scale(self):
        s = self.p.sheets[0]
        with self.p.edit("a line") as ed:
            ed.add(s, M.Line((0, 0), (1, 1)))
        self.run_dialog(s, "panel")
        self.assertEqual((s.kind, s.scale), ("panel", 1.0))


class PastTerminalsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.lib = self.win.library
        self.s = self.p.sheets[0]

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def put(self, ed, name, pos, attrs=None):
        d = self.lib.get("symbol", name)
        return ed.add(self.s, M.Insert(name, pos, 0.0, 1.0, False, dict(attrs or {}), d, 0.1))

    def arrow_to_terminal(self, ed):
        """A destination arrow at (2, 5), its wire to terminal TB1-12 (pins at 3.97 / 4.03)."""
        a = self.put(ed, ARROWS[1], (2.0, 5.0), {"TAG": "Q"})
        ed.add(self.s, M.Wire([(2.0, 5.0), (3.96875, 5.0)]))
        self.put(ed, "Terminal", (4.0, 5.0), {"TAG": "TB1", "TERM": "12"})
        return a

    def test_through_a_terminal_to_the_device(self):
        with self.p.edit("w") as ed:
            a = self.arrow_to_terminal(ed)
            ed.add(self.s, M.Wire([(4.03125, 5.0), (6.0, 5.0)]))
            self.put(ed, "Relay coil", (6.25, 5.0), {"TAG": "PLC1"})
        self.assertEqual(xrefs.far_device(self.s, self.s.entities[a.id]), "PLC1")

    def test_through_two_terminals(self):
        with self.p.edit("w") as ed:
            a = self.arrow_to_terminal(ed)
            ed.add(self.s, M.Wire([(4.03125, 5.0), (5.96875, 5.0)]))
            self.put(ed, "Terminal", (6.0, 5.0), {"TAG": "TB2", "TERM": "3"})
            ed.add(self.s, M.Wire([(6.03125, 5.0), (8.0, 5.0)]))
            self.put(ed, "Relay coil", (8.25, 5.0), {"TAG": "PLC1"})
        self.assertEqual(xrefs.far_device(self.s, self.s.entities[a.id]), "PLC1")

    def test_nothing_past_the_terminal_shows_it(self):
        with self.p.edit("w") as ed:
            a = self.arrow_to_terminal(ed)
        self.assertEqual(xrefs.far_device(self.s, self.s.entities[a.id]), "TB1-12")

    def test_a_tee_past_the_terminal_shows_it(self):
        with self.p.edit("w") as ed:
            a = self.arrow_to_terminal(ed)
            ed.add(self.s, M.Wire([(4.03125, 5.0), (6.0, 5.0)]))
            ed.add(self.s, M.Wire([(5.0, 5.0), (5.0, 3.0)]))
            self.put(ed, "Relay coil", (6.25, 5.0), {"TAG": "CR1"})
            self.put(ed, "Relay coil", (5.25, 3.0), {"TAG": "CR2"})
        self.assertEqual(xrefs.far_device(self.s, self.s.entities[a.id]), "TB1-12")


if __name__ == "__main__":
    unittest.main()
