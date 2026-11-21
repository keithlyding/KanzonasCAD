"""Texts edited where they are (the owner's list, #14): a double-click on a text or multi-line
note opens an edit box over it; Enter keeps (Ctrl+Enter in a multi-line note), Esc drops,
clicking elsewhere keeps; one Undo; its height and angle untouched; Text properties... (right
click) still opens its window."""
import unittest

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLineEdit, QPlainTextEdit

from tests.util import APP, window

from kanzonascad import model as M


class TextInPlaceTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.s = self.v.sheet()
        with self.p.edit("texts") as ed:
            self.t = ed.add(self.s, M.Text((4.0, 4.0), "MOTOR 1", 0.125, 30.0))
            self.m = ed.add(self.s, M.MText((4.0, 6.0), "NOTE 1\nNOTE 2", 0.1, 0.0, "TL",
                                            2.0))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def box(self):
        got = self.v.findChildren(QLineEdit, "text_in_place") + \
            self.v.findChildren(QPlainTextEdit, "text_in_place")
        return [b for b in got if b.isVisible()]

    def test_enter_keeps_and_one_undo(self):
        n = len(self.p.undo_stack)
        self.win.edit_text(self.s.entities[self.t.id])
        b = self.box()
        self.assertEqual(len(b), 1)
        self.assertEqual(b[0].text(), "MOTOR 1")
        b[0].setText("MOTOR 2")
        QTest.keyClick(b[0], Qt.Key_Return)
        t = self.s.entities[self.t.id]
        self.assertEqual((t.text, t.height, t.angle), ("MOTOR 2", 0.125, 30.0))
        self.assertEqual(len(self.p.undo_stack), n + 1)
        self.assertEqual(self.box(), [])
        self.p.undo()
        self.assertEqual(self.s.entities[self.t.id].text, "MOTOR 1")

    def test_esc_drops(self):
        n = len(self.p.undo_stack)
        self.win.edit_text(self.s.entities[self.t.id])
        b = self.box()[0]
        b.setText("WRONG")
        QTest.keyClick(b, Qt.Key_Escape)
        self.assertEqual(self.s.entities[self.t.id].text, "MOTOR 1")
        self.assertEqual(len(self.p.undo_stack), n)

    def test_multi_line_needs_ctrl_enter(self):
        self.win.edit_text(self.s.entities[self.m.id])
        b = self.box()[0]
        self.assertIsInstance(b, QPlainTextEdit)
        b.setPlainText("NOTE 1\nNOTE 2\nNOTE 3")
        QTest.keyClick(b, Qt.Key_Return, Qt.ControlModifier)
        self.assertEqual(self.s.entities[self.m.id].text, "NOTE 1\nNOTE 2\nNOTE 3")

    def test_empty_or_same_changes_nothing(self):
        n = len(self.p.undo_stack)
        self.win.edit_text(self.s.entities[self.t.id])
        b = self.box()[0]
        b.setText("   ")
        QTest.keyClick(b, Qt.Key_Return)
        self.assertEqual(self.s.entities[self.t.id].text, "MOTOR 1")
        self.assertEqual(len(self.p.undo_stack), n)


if __name__ == "__main__":
    unittest.main()
