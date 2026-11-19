"""Picking the device a contact belongs to (P) picks with the pick box and lights the device
under the cursor (the owner, 0.19.2: "the cursor looks more like I'm drawing a line somewhere
and doesn't highlight the parent when I browse over it"): only a device lights up, not a wire
across it; a click on it takes it."""
import unittest

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import QEvent

from tests.util import APP, window

from kanzonascad import commands as C
from kanzonascad import model as M


def move(v, p):
    q = v.to_screen(p)
    ev = QMouseEvent(QEvent.MouseMove, QPointF(q), QPointF(q), Qt.NoButton, Qt.NoButton,
                     Qt.NoModifier)
    v.mouseMoveEvent(ev)


class PickDeviceHoverTest(unittest.TestCase):
    def test_lights_the_device_only(self):
        win, v = window()
        try:
            p, s = v.project, v.sheet()
            coil = win.library.get("symbol", "Relay coil")
            with p.edit("x") as ed:
                ed.block(coil)
                cr = ed.add(s, M.Insert(coil.name, (10.0, 10.0), attrs={"TAG": "CR1", "DEV": "d1"},
                                        defn=p.blocks[coil.name]))
                ed.add(s, M.Wire([(2.0, 15.0), (18.0, 15.0)]))
            cr = s.entities[cr.id]
            got = []
            v.run(C.PickDeviceCmd, got.append)
            self.assertTrue(v.cmd.picking)                  # (the pick box, not a crosshair)
            move(v, (9.9, 10.0))                            # (on the coil's circle)
            self.assertIs(v._hover.id if v._hover else None, cr.id)
            self.assertEqual(v.cursor_hint(), "pick")
            move(v, (6.0, 15.0))                            # (over the wire: nothing lit)
            self.assertIsNone(v._hover)
            v.cmd.pick((9.9, 10.0))
            self.assertEqual([e.id for e in got], [cr.id])
            self.assertIsNone(v.cmd)
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()
        self.assertTrue(APP)


if __name__ == "__main__":
    unittest.main()
