"""Every command's preview paints with the mouse over the page (the owner, 0.16: "When trying
to insert bus wires now, my mouse disappears when it goes over the page"). Bus kept a value
named shift, which the view takes for Move's "the objects shifted" step and calls: every paint
failed before the crosshair was drawn, and the page hides the mouse for the crosshair. Tests
and the battery typed their points and never painted a command on its way."""
import traceback
import unittest

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QDialog, QMessageBox

from tests.util import APP, window

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad.view import CadView


def commands():
    out = []
    for name in sorted(dir(C)):
        k = getattr(C, name)
        if isinstance(k, type) and issubclass(k, C.Command) and k is not C.Command \
                and not name.startswith("_"):
            out.append(k)
    return out


class PaintEveryCommandTest(unittest.TestCase):
    def setUp(self):
        self.errors = []
        real = CadView.paintEvent
        errors = self.errors

        def paint(view, e):
            try:
                return real(view, e)
            except Exception:
                errors.append(traceback.format_exc())
                raise
        self._real = real
        CadView.paintEvent = paint
        # (a dialog or message box nobody answers would hang the run)
        self._exec = QDialog.exec
        QDialog.exec = lambda d: QDialog.Rejected
        self._boxes = {}
        for n in ("information", "warning", "question", "critical"):
            self._boxes[n] = getattr(QMessageBox, n)
            setattr(QMessageBox, n, staticmethod(lambda *a, **k: QMessageBox.No))
        self.win, self.v = window()
        v = self.v
        with v.project.edit("objects") as ed:
            s = v.sheet()
            ed.add(s, M.Line((2.0, 2.0), (6.0, 2.0)))
            ed.add(s, M.Wire([(2.0, 4.0), (8.0, 4.0)]))
            ed.add(s, M.Wire([(2.0, 4.5), (8.0, 4.5)]))
            ed.add(s, M.Wire([(2.0, 5.0), (8.0, 5.0)]))
        v.center, v.scale = (5.0, 5.0), 60.0      # (the objects in the middle of the view)

    def tearDown(self):
        CadView.paintEvent = self._real
        QDialog.exec = self._exec
        for n, f in self._boxes.items():
            setattr(QMessageBox, n, f)
        p = self.v.project
        p.saved_at = len(p.undo_stack)
        self.win.close()

    def move_and_paint(self, world):
        v = self.v
        pos = v.to_screen(world).toPoint()
        APP.sendEvent(v, QMouseEvent(QMouseEvent.MouseMove, QPointF(pos), QPointF(v.mapToGlobal(pos)),
                                     Qt.NoButton, Qt.NoButton, Qt.NoModifier))
        v.repaint()
        APP.processEvents()

    def test_every_command_paints_on_its_way(self):
        v = self.v
        ran = []
        for k in commands():
            args = ()
            if k is C.InsertCmd:
                args = (self.win.library.get("symbol", "Fuses 3-pole"), {})
            v.sel = set(v.sheet().entities)         # (those that work on a selection)
            try:
                v.run(k, *args)
            except TypeError:
                continue                            # (needs what only its menu gives it)
            if v.cmd is None:
                continue
            seen = len(self.errors)
            for at, typed in (((2.0, 4.5), "2,4.5"), ((5.0, 7.0), "5,7"), ((7.0, 3.0), None)):
                if v.cmd is None:
                    break
                self.move_and_paint(at)
                if typed is not None and v.cmd is not None:
                    v.input_text(typed)
            self.assertEqual(self.errors[seen:], [], k.__name__)
            ran.append(k.__name__)
            if v.cmd is not None:
                v.cancel()
        self.assertIn("BusCmd", ran)
        self.assertGreater(len(ran), 30, ran)

    def test_the_bus_keeps_its_crosshair(self):
        v = self.v
        v.run(C.BusCmd)
        self.move_and_paint((3.0, 6.0))
        v.input_text("3,6")
        self.move_and_paint((3.0, 8.0))
        self.assertEqual(self.errors, [])
        v.cancel()


if __name__ == "__main__":
    unittest.main()
