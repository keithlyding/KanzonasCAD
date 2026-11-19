"""Taps set one by one follow the project again (the owner, 0.18.4: "I had already changed all
these wires manually to be a number of their own. But I did unlock everything but it left
that setting, even though I changed it for the whole project")."""
import unittest

from PySide6.QtWidgets import QDialog, QCheckBox, QComboBox

from tests.util import APP, window

from kanzonascad import dialogs
from kanzonascad import model as M


class TapsFollowProjectTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()
        with self.p.edit("w") as ed:
            ed.sheet_meta(self.s, number="2")
            ed.project_settings({"tap_numbers": "same"})
            ed.add(self.s, M.Wire([(1.0, 8.0), (12.0, 8.0)]))
            for x in (3.0, 6.0):
                ed.add(self.s, M.Wire([(x, 8.0), (x, 4.0)]))
        with self.p.edit("own") as ed:          # (each drop given a number of its own)
            for w in list(self.s.wires()):
                if w.points[0][1] != w.points[-1][1]:
                    ed.change(self.s, w.copy(own_num=True))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def num(self, at):
        return [w.num for w in self.s.wires() if w.touches(at)][0]

    def props(self, setting, tick=None):
        real = dialogs.QDialog.exec
        seen = {}

        def go(dlg):
            box = dlg.findChild(QComboBox, "tap_numbers")
            box.setCurrentIndex(box.findData(setting))
            allb = dlg.findChild(QCheckBox, "tap_numbers_all")
            seen["ticked"] = allb.isChecked()
            if tick is not None:
                allb.setChecked(tick)
            return QDialog.Accepted
        dialogs.QDialog.exec = go
        try:
            self.win.project_properties(1)
        finally:
            dialogs.QDialog.exec = real
        return seen

    def test_changing_the_setting_brings_them_back(self):
        bus = self.num((1.0, 8.0))
        self.assertNotIn("-", self.num((3.0, 4.0)))         # (their own numbers)
        seen = self.props("suffix")
        self.assertTrue(seen["ticked"])                     # (ticked itself)
        self.assertEqual((self.num((3.0, 4.0)), self.num((6.0, 4.0))),
                         (bus + "-1", bus + "-2"))
        self.assertFalse(any(w.own_num for w in self.s.wires()))
        self.p.undo()                                       # (one step)
        self.assertTrue(any(w.own_num for w in self.s.wires()))

    def test_left_alone_unless_asked(self):
        self.props("suffix", tick=False)
        self.assertNotIn("-", self.num((3.0, 4.0)))
        self.assertTrue(all(w.own_num for w in self.s.wires()
                            if w.points[0][1] != w.points[-1][1]))
        # (and asked later, the setting the same)
        self.props("suffix", tick=True)
        self.assertEqual(self.num((3.0, 4.0)), self.num((1.0, 8.0)) + "-1")


if __name__ == "__main__":
    unittest.main()
