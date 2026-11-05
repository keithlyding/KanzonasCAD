"""Ctrl+arrow moves the selection one snap step (Ctrl+Shift+arrow a tenth of one), as a Move:
one undoable step, wires keep to the pins they're on."""
import unittest

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class NudgeTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = False
        self.v.polar_on = self.v.ortho_on = False
        self.p = self.v.project
        self.s = self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def key(self, k, mods=Qt.ControlModifier):
        APP.sendEvent(self.v, QKeyEvent(QEvent.KeyPress, k, mods))

    def test_ctrl_arrows_move_one_snap_step_each_way(self):
        with self.p.edit("line") as ed:
            ln = ed.add(self.s, M.Line((2, 2), (4, 2)))
        self.v.set_selection({ln.id})
        step = self.v.snap_spacing
        steps = len(self.p.undo_stack)
        self.key(Qt.Key_Right)
        self.key(Qt.Key_Right)
        self.key(Qt.Key_Up)
        e = self.s.entities[ln.id]
        self.assertAlmostEqual(e.p1[0], 2 + 2 * step)
        self.assertAlmostEqual(e.p1[1], 2 + step)
        self.key(Qt.Key_Left)
        self.key(Qt.Key_Down)
        e = self.s.entities[ln.id]
        self.assertAlmostEqual(e.p1[0], 2 + step)
        self.assertAlmostEqual(e.p1[1], 2.0)
        self.assertEqual(len(self.p.undo_stack), steps + 5)     # one step each
        self.assertEqual(self.v.sel, {ln.id})                   # still selected
        self.key(Qt.Key_Right, Qt.ControlModifier | Qt.ShiftModifier)   # a tenth
        self.assertAlmostEqual(self.s.entities[ln.id].p1[0], 2 + step + step / 10)
        self.p.undo()
        self.assertAlmostEqual(self.s.entities[ln.id].p1[0], 2 + step)

    def test_plain_arrows_and_no_selection_do_nothing(self):
        with self.p.edit("line") as ed:
            ln = ed.add(self.s, M.Line((2, 2), (4, 2)))
        steps = len(self.p.undo_stack)
        self.key(Qt.Key_Right)                                  # nothing selected
        self.v.set_selection({ln.id})
        self.key(Qt.Key_Right, Qt.NoModifier)                   # no Ctrl
        self.assertEqual(len(self.p.undo_stack), steps)
        self.assertEqual(tuple(self.s.entities[ln.id].p1), (2.0, 2.0))

    def test_wire_follows_a_moved_symbol(self):
        coil = self.win.library.get("symbol", "Relay coil")
        self.v.run(C.InsertCmd, coil, {"TAG": "CR1"})
        type_in(self.v, "6,5")
        ins = max(self.s.inserts(), key=lambda e: e.id)
        pin = sorted((q for _n, q in ins.pin_points()), key=lambda q: (q[0], q[1]))[-1]
        self.v.run(C.WireCmd)
        type_in(self.v, "%g,%g" % pin, "%g,%g" % (pin[0] + 3, pin[1]))
        if self.v.cmd is not None:
            self.v.cmd.enter()
        wire = max(self.s.wires(), key=lambda w: w.id)
        self.v.set_selection({ins.id})
        self.key(Qt.Key_Up)
        moved = self.s.entities[ins.id]
        new_pin = sorted((q for _n, q in moved.pin_points()), key=lambda q: (q[0], q[1]))[-1]
        w = self.s.entities[wire.id]
        self.assertIn(tuple(round(c, 9) for c in new_pin),
                      [tuple(round(c, 9) for c in q) for q in w.points])

    def test_locked_layer_stays(self):
        with self.p.edit("lines") as ed:
            ed.layer("LOCKED", None, dict(M.Layer("LOCKED").to_dict(), locked=True))
            a = ed.add(self.s, M.Line((1, 1), (2, 1)))
            b = ed.add(self.s, M.Line((1, 3), (2, 3), layer="LOCKED"))
        self.v.set_selection({a.id, b.id})
        self.key(Qt.Key_Right)
        self.assertNotEqual(tuple(self.s.entities[a.id].p1), (1.0, 1.0))
        self.assertEqual(tuple(self.s.entities[b.id].p1), (1.0, 3.0))


if __name__ == "__main__":
    unittest.main()
