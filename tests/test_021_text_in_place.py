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

    # ---- justification over the box (the owner, 0.22.5: "I've lost the ability to justify
    # text") -------------------------------------------------------------------------------
    def bar_button(self, label):
        from PySide6.QtWidgets import QFrame, QToolButton
        bars = [f for f in self.v.findChildren(QFrame, "text_in_place_bar") if f.isVisible()]
        self.assertEqual(len(bars), 1)
        return next(b for b in bars[0].findChildren(QToolButton) if b.text() == label)

    def test_justify_with_the_words_one_undo(self):
        n = len(self.p.undo_stack)
        self.win.edit_text(self.s.entities[self.t.id])
        self.assertTrue(self.bar_button("Left").isChecked())
        QTest.mouseClick(self.bar_button("Right"), Qt.LeftButton)
        b = self.box()
        self.assertEqual(len(b), 1)                     # (still open: the button took no focus)
        self.assertTrue(self.bar_button("Right").isChecked())
        b[0].setText("MOTOR 2")
        QTest.keyClick(b[0], Qt.Key_Return)
        t = self.s.entities[self.t.id]
        self.assertEqual((t.text, t.align, t.pos, t.height, t.angle),
                         ("MOTOR 2", "right", (4.0, 4.0), 0.125, 30.0))
        self.assertEqual(len(self.p.undo_stack), n + 1)
        self.p.undo()
        self.assertEqual(self.s.entities[self.t.id].align, "left")

    def test_justify_only(self):
        self.win.edit_text(self.s.entities[self.t.id])
        QTest.mouseClick(self.bar_button("Center"), Qt.LeftButton)
        QTest.keyClick(self.box()[0], Qt.Key_Return)
        self.assertEqual(self.s.entities[self.t.id].align, "center")

    def test_a_notes_justification_keeps_its_top(self):
        self.win.edit_text(self.s.entities[self.m.id])
        QTest.mouseClick(self.bar_button("Right"), Qt.LeftButton)
        QTest.keyClick(self.box()[0], Qt.Key_Return, Qt.ControlModifier)
        self.assertEqual(self.s.entities[self.m.id].attach, "TR")

    def test_esc_drops_the_justification_too(self):
        self.win.edit_text(self.s.entities[self.t.id])
        QTest.mouseClick(self.bar_button("Right"), Qt.LeftButton)
        QTest.keyClick(self.box()[0], Qt.Key_Escape)
        self.assertEqual(self.s.entities[self.t.id].align, "left")

    def test_clicking_elsewhere_keeps(self):
        self.win.edit_text(self.s.entities[self.t.id])
        self.box()[0].setText("MOTOR 4")
        self.v.setFocus()
        for _ in range(3):
            APP.processEvents()
        self.assertEqual(self.s.entities[self.t.id].text, "MOTOR 4")
        self.assertEqual(self.box(), [])

    def test_more_opens_its_window_with_the_typing_kept(self):
        from kanzonascad import dialogs
        seen = []
        real = dialogs.edit_text_dialog
        dialogs.edit_text_dialog = lambda parent, ent: seen.append(ent) or None
        try:
            self.win.edit_text(self.s.entities[self.t.id])
            self.box()[0].setText("MOTOR 3")
            QTest.mouseClick(self.bar_button("More..."), Qt.LeftButton)
        finally:
            dialogs.edit_text_dialog = real
        self.assertEqual(self.s.entities[self.t.id].text, "MOTOR 3")
        self.assertEqual([e.text for e in seen], ["MOTOR 3"])
        self.assertEqual(self.box(), [])


if __name__ == "__main__":
    unittest.main()
