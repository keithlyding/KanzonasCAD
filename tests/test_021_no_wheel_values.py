"""The mouse wheel never changes a number box or a closed drop-down list; it is left for what
they sit in to scroll (the owner, 0.21.3: "if I scroll the mouse wheel over an input field with
up/down arrows on the side, the number will scroll up or down ... Let's get rid of that
entirely")."""
import unittest

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QWheelEvent
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QColorDialog, QComboBox, QDialog,
                               QDoubleSpinBox, QInputDialog, QScrollArea, QSpinBox,
                               QVBoxLayout, QWidget)

from tests.util import APP, window

from kanzonascad import no_wheel


def wheel(w, down=True):
    """A wheel notch over w; True when something took it."""
    pos = QPointF(w.width() / 2, w.height() / 2)
    ev = QWheelEvent(pos, w.mapToGlobal(pos), QPoint(0, 0), QPoint(0, -120 if down else 120),
                     Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
    QApplication.sendEvent(w, ev)
    return ev.isAccepted()


class NoWheelTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()            # (the main window calls no_wheel.install)
        self.page = QScrollArea()
        inner = QWidget()
        lay = QVBoxLayout(inner)
        self.spin = QSpinBox()
        self.spin.setRange(0, 100)
        self.spin.setValue(50)
        self.dspin = QDoubleSpinBox()
        self.dspin.setValue(1.5)
        self.combo = QComboBox()
        self.combo.addItems(["14", "12", "10"])
        self.edit_combo = QComboBox()
        self.edit_combo.setEditable(True)
        self.edit_combo.addItems(["1:1", "1:2", "1:4"])
        for w in (self.spin, self.dspin, self.combo, self.edit_combo):
            lay.addWidget(w)
        self.page.setWidget(inner)
        self.page.show()
        APP.processEvents()

    def tearDown(self):
        self.page.close()
        self.v.project.saved_at = len(self.v.project.undo_stack)
        self.win.close()

    def test_numbers_and_lists_keep_their_value(self):
        for w in (self.spin, self.dspin, self.combo, self.edit_combo):
            w.setFocus()                        # (even with the keyboard on it)
            APP.processEvents()
            for down in (True, False, True):
                self.assertFalse(wheel(w, down))            # (left for the page to scroll)
        self.assertEqual(self.spin.value(), 50)
        self.assertEqual(self.dspin.value(), 1.5)
        self.assertEqual(self.combo.currentIndex(), 0)
        self.assertEqual(self.edit_combo.currentIndex(), 0)

    def test_over_a_number_boxs_text_too(self):
        self.assertFalse(wheel(self.spin.lineEdit()))
        self.assertEqual(self.spin.value(), 50)

    def test_the_arrows_and_typing_still_change_it(self):
        self.spin.stepUp()
        self.assertEqual(self.spin.value(), 51)

    def test_qts_own_windows_through_get_item_and_get_color(self):
        # (their boxes are Qt's, not of the Python classes: guarded one window at a time)
        dlg = QInputDialog()
        dlg.setComboBoxItems(["14", "12", "10"])
        no_wheel.guard(dlg)
        dlg.show()
        APP.processEvents()
        box = dlg.findChild(QComboBox)
        self.assertFalse(wheel(box))
        self.assertEqual(box.currentIndex(), 0)
        dlg.close()
        colors = QColorDialog()
        no_wheel.guard(colors)
        colors.show()
        APP.processEvents()
        spins = colors.findChildren(QAbstractSpinBox)
        self.assertTrue(spins)
        before = [b.text() for b in spins]
        for b in spins:
            self.assertFalse(wheel(b))
        self.assertEqual([b.text() for b in spins], before)
        colors.close()

    def test_get_item_answers_as_qt_does(self):
        real = QDialog.exec
        try:
            QDialog.exec = lambda dlg: QDialog.Accepted
            self.assertEqual(no_wheel.get_item(None, "t", "l", ["a", "b", "c"], 1, False),
                             ("b", True))
            QDialog.exec = lambda dlg: QDialog.Rejected
            self.assertFalse(no_wheel.get_item(None, "t", "l", ["a", "b"], 0, False)[1])
            self.assertFalse(no_wheel.get_color(QColor("#ff0000"), None, "c").isValid())
            QDialog.exec = lambda dlg: QDialog.Accepted
            self.assertEqual(no_wheel.get_color(QColor("#ff0000"), None, "c").name(),
                             "#ff0000")
        finally:
            QDialog.exec = real

    def test_without_it_the_wheel_would_change_them(self):
        # (the check above means something: Qt's own handling takes the wheel)
        saved = {cls: cls.wheelEvent for cls in no_wheel.BOXES}
        try:
            for cls, fn in no_wheel.QT_WHEEL.items():
                cls.wheelEvent = fn
            wheel(self.spin)
            wheel(self.combo)
            self.assertNotEqual((self.spin.value(), self.combo.currentIndex()), (50, 0))
        finally:
            for cls, fn in saved.items():
                cls.wheelEvent = fn


if __name__ == "__main__":
    unittest.main()
