"""A number typed that two other wires already have (one kept with "just the same number"),
answered Source or Destination (the battery, seed 5102): the arrow goes on the one with an
open end; before, the first found was taken, and with no open end nothing was placed."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wirenums


class XrefOpenEndChoiceTest(unittest.TestCase):
    def test_arrow_on_the_wire_with_an_open_end(self):
        win, v = window()
        try:
            v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
            p, s = v.project, v.sheet()
            for at in ("3,6", "6,6"):
                v.run(C.InsertCmd, win.library.get("symbol", "Relay coil"), {})
                type_in(v, at)
            a, b = sorted(s.inserts(), key=lambda e: e.pos[0])
            pa = dict(a.pin_points())["A2"]
            pb = dict(b.pin_points())["A1"]
            with p.edit("wires") as ed:
                closed = ed.add(s, M.Wire([pa, pb]))                  # (on two pins)
                open_ = ed.add(s, M.Wire([(3.0, 2.0), (5.0, 2.0)]))
                mine = ed.add(s, M.Wire([(8.0, 2.0), (10.0, 2.0)]))
            with p.edit("nums") as ed:
                wirenums.set_number(ed, p, s, s.entities[closed.id], "777", True)
                wirenums.set_number(ed, p, s, s.entities[open_.id], "777", True)
            win.ask_wire_number = lambda n, tap_of=None, own=False, locked=False: ("777", own,
                                                                                    True)
            win.ask_cross_reference = lambda n, where: "destination"
            said = []
            from PySide6.QtWidgets import QMessageBox
            from unittest import mock
            with mock.patch.object(QMessageBox, "information",
                                   lambda *a, **k: said.append(a)):
                win.edit_wire_number(s.entities[mine.id])
            arrows = [e for e in s.inserts() if e.block in wirenums.ARROWS]
            self.assertEqual(said, [])
            self.assertEqual(sorted(e.block for e in arrows),
                             ["Destination arrow", "Source arrow"])
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()
        self.assertTrue(APP)


if __name__ == "__main__":
    unittest.main()
