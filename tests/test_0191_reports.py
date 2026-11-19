"""Wire list and terminal strip list (the roadmap's reports: every wire by number with what it
lands on, every terminal with the wires on each side), worked out from the drawing."""
import os
import tempfile
import unittest

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import reports


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()
        lib = self.win.library
        coil = lib.get("symbol", "Relay coil")
        term = lib.get("symbol", "Terminal")
        with self.p.edit("x") as ed:
            ed.block(coil)
            ed.block(term)
            self.cr = ed.add(self.s, M.Insert(coil.name, (10.0, 10.0), attrs={"TAG": "CR1"},
                                              defn=self.p.blocks[coil.name]))
            self.tb = ed.add(self.s, M.Insert(term.name, (4.0, 10.0),
                                              attrs={"TAG": "TB1", "TERM": "4"},
                                              defn=self.p.blocks[term.name]))
        cr, tb = self.s.entities[self.cr.id], self.s.entities[self.tb.id]
        a1 = dict(cr.pin_points())
        tpins = sorted(tb.pin_points(), key=lambda t: t[1][0])
        with self.p.edit("w") as ed:
            # terminal's right pin to the coil's first pin; a field wire on the left pin
            ed.add(self.s, M.Wire([tpins[-1][1], list(a1.values())[0]]))
            ed.add(self.s, M.Wire([(1.0, tpins[0][1][1]), tpins[0][1]]))
        self.coil_pin = list(a1)[0]

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_wire_list(self):
        rows = reports.wire_rows(self.p)
        self.assertEqual(len(rows), 2)
        nums = [r[0] for r in rows]
        self.assertEqual(nums, sorted(nums))
        inner = [r for r in rows if "CR1:%s" % self.coil_pin in r[2]][0]
        self.assertIn("TB1-4", inner[2])
        self.assertEqual(inner[3], self.p.sheet_number(self.s))
        path = os.path.join(tempfile.mkdtemp(), "w.csv")
        self.assertEqual(reports.write_csv(path, reports.WIRE_HEAD, rows), 2)
        with open(path, encoding="utf-8") as f:
            self.assertTrue(f.readline().startswith("Wire,"))

    def test_terminal_list(self):
        rows = reports.terminal_rows(self.p)
        self.assertEqual(len(rows), 1)
        strip, term, left, right, where = rows[0]
        self.assertEqual((strip, term), ("TB1", "4"))
        wires = {r[0]: r for r in reports.wire_rows(self.p)}
        self.assertIn(right, wires)
        self.assertIn("CR1:", wires[right][2])
        self.assertIn(left, wires)
        self.assertNotEqual(left, right)
        self.assertTrue(where.startswith(self.p.sheet_number(self.s)))

    def test_the_windows(self):
        from PySide6.QtWidgets import QDialog, QTableWidget
        from kanzonascad import dialogs
        seen = []

        def look(dlg):
            t = dlg.findChild(QTableWidget, "report_table")
            seen.append((dlg.windowTitle(), t.rowCount()))
            return QDialog.Rejected
        real = dialogs.QDialog.exec
        try:
            dialogs.QDialog.exec = look
            self.win.acts["wire_list"].trigger()
            self.win.acts["terminal_list"].trigger()
        finally:
            dialogs.QDialog.exec = real
        self.assertEqual(seen, [("Wire list", 2), ("Terminal strip list", 1)])


if __name__ == "__main__":
    unittest.main()
