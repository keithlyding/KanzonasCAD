"""Cables between locations (the owner: "what cables need to be pulled between panels and where
all the wires need to be landed on both sides"): each sheet's location, a device's own (LOC),
wires landing in two locations listed run by run with their landings (terminals first), off-sheet
connectors followed; the cable, its type and the conductors' colors or numbers kept with the
project (undoable); CSV and PDF."""
import csv
import os
import tempfile
import unittest
from unittest import mock

from PySide6.QtWidgets import QDialog, QLineEdit, QListWidget, QTableWidget, QComboBox

from tests.util import APP, window, type_in  # noqa: F401

from kanzonascad import commands as C
from kanzonascad import dialogs
from kanzonascad import model as M
from kanzonascad import pull


class Builder:
    """Places library symbols and draws wires through the commands, as a user would."""

    def __init__(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.polar_on = v.ortho_on = False
        self.p = v.project
        self.lib = self.win.library

    def place(self, name, at, attrs=None):
        v = self.v
        before = set(v.sheet().entities)
        v.run(C.InsertCmd, self.lib.get("symbol", name), attrs or {})
        type_in(v, "%g,%g" % at)
        if v.cmd is not None:
            v.input_text("")
        if v.cmd is not None:
            v.cancel()
        return [e for i, e in v.sheet().entities.items()
                if i not in before and isinstance(e, M.Insert)][0].id

    def pins(self, iid):
        return list(dict(self.v.sheet().entities[iid].pin_points()).values())

    def wire(self, a, b):
        v = self.v
        v.run(C.WireCmd)
        type_in(v, "%g,%g" % a, "%g,%g" % b)
        if v.cmd is not None:
            v.cmd.enter()
        if v.cmd is not None:
            v.cancel()

    def located(self, sheet, loc):
        with self.p.edit("Sheet properties") as ed:
            ed.sheet_meta(sheet, location=loc)

    def two_panels(self):
        """MCP: a terminal strip, two terminals, a relay coil wired to terminal 1, a field
        pushbutton (LOC FIELD) wired to terminal 1's other side, terminal 2 to an off-sheet
        connector A; sheet JB-1: connector A wired to a pilot light."""
        p, v = self.p, self.v
        s1 = v.sheet()
        self.located(s1, "MCP")
        self.place("Terminal strip", (2, 9))
        t1 = self.place("Terminal", (4, 7))
        t2 = self.place("Terminal", (4, 5))
        cr = self.place("Relay coil", (8, 7))
        self.wire(self.pins(t1)[1], self.pins(cr)[0])
        pb = self.place("Pushbutton NO", (1, 7), {"LOC": "FIELD"})
        self.wire(self.pins(pb)[1], self.pins(t1)[0])
        a = self.place("Off-sheet connector", (2, 5), {"TAG": "A"})
        self.wire(self.pins(t2)[0], self.pins(a)[0])
        with p.edit("Add sheet") as ed:
            s2 = p.make_sheet("JB")
            ed.add_sheet(s2)
        v.show_sheet(s2.id)
        self.located(s2, "JB-1")
        a2 = self.place("Off-sheet connector", (2, 5), {"TAG": "A"})
        lt = self.place("Pilot light", (6, 5))
        self.wire(self.pins(a2)[0], self.pins(lt)[0])
        v.show_sheet(s1.id)
        return s1, s2

    def close(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()


class PullTest(unittest.TestCase):
    def setUp(self):
        self.b = Builder()

    def tearDown(self):
        self.b.close()

    def test_runs_and_landings(self):
        self.b.two_panels()
        rs, unplaced = pull.runs(self.b.p)
        self.assertEqual([r["name"] for r in rs], ["MCP ↔ FIELD", "MCP ↔ JB-1"])
        self.assertEqual(unplaced, 0)
        field = rs[0]["conductors"]
        self.assertEqual(len(field), 1)
        # on the panel side the terminal (not the coil the terminal is also wired to)
        self.assertEqual(field[0]["lands"]["MCP"], ["TB101-1"])
        self.assertEqual(field[0]["lands"]["FIELD"], ["PB101:2"])
        jb = rs[1]["conductors"][0]
        self.assertEqual(jb["lands"], {"MCP": ["TB101-2"], "JB-1": ["LT201:1"]})
        self.assertTrue(jb["num"])                      # (its wire number, as on the drawing)

    def test_no_locations_no_runs(self):
        b = self.b
        t = b.place("Terminal", (4, 7))
        cr = b.place("Relay coil", (8, 7))
        b.wire(b.pins(t)[1], b.pins(cr)[0])
        self.assertEqual(pull.runs(b.p), ([], 0))

    def test_partly_located_counted(self):
        b = self.b
        t = b.place("Terminal", (4, 7))
        cr = b.place("Relay coil", (8, 7), {"LOC": "FIELD"})
        lt = b.place("Pilot light", (8, 5))
        b.wire(b.pins(t)[1], b.pins(cr)[0])
        b.wire(b.pins(t)[1], b.pins(lt)[0])
        # one location only (the coil's) and a sheet without one: no run, one wire to locate
        self.assertEqual(pull.runs(b.p), ([], 1))

    def test_three_locations(self):
        b = self.b
        b.located(b.v.sheet(), "MCP")
        t = b.place("Terminal", (4, 7))
        pb = b.place("Pushbutton NO", (1, 7), {"LOC": "FIELD"})
        lt = b.place("Pilot light", (8, 7), {"LOC": "JB-1"})
        # one wire landing in three places (a terminal's two sides are two wires: see
        # test_terminal_sides)
        b.wire(b.pins(pb)[1], b.pins(t)[0])
        b.wire(b.pins(t)[0], b.pins(lt)[0])
        rs, _u = pull.runs(b.p)
        self.assertEqual(len(rs), 1)
        self.assertEqual(rs[0]["locs"], ["MCP", "FIELD", "JB-1"])
        head, rows = pull.table(b.p)
        self.assertIn("FIELD: PB", rows[0][-1])

    def test_terminal_sides(self):
        """A terminal's two sides are two wires (two numbers): field to terminal and terminal
        to the next box are two runs, each landing on the terminal."""
        b = self.b
        b.located(b.v.sheet(), "MCP")
        loose = b.place("Terminal", (10, 3))     # (no strip yet: no strip tag or number)
        b.place("Terminal strip", (2, 9))
        t = b.place("Terminal", (4, 7))
        pb = b.place("Pushbutton NO", (1, 7), {"LOC": "FIELD"})
        lt = b.place("Pilot light", (8, 7), {"LOC": "JB-1"})
        b.wire(b.pins(pb)[1], b.pins(t)[0])
        b.wire(b.pins(t)[1], b.pins(lt)[0])
        self.assertEqual(pull.landing_name(b.v.sheet().entities[loose], "1"), "TB?")
        rs, _u = pull.runs(b.p)
        self.assertEqual([r["name"] for r in rs], ["MCP \u2194 FIELD", "MCP \u2194 JB-1"])
        self.assertEqual([r["conductors"][0]["lands"]["MCP"] for r in rs],
                         [["TB101-1"], ["TB101-1"]])

    def test_location_saved_and_undone(self):
        s1, s2 = self.b.two_panels()
        path = os.path.join(tempfile.mkdtemp(), "p.kzcad")
        self.b.p.save(path, backups=0)
        q = M.Project.load(path)
        self.assertEqual([s.location for s in q.sheets], ["MCP", "JB-1"])
        self.b.p.undo()                                 # (the last: the pilot light's wire)
        self.b.p.redo()
        self.assertEqual(s2.location, "JB-1")

    def test_cables_kept_with_the_project(self):
        self.b.two_panels()
        p = self.b.p
        key = pull.runs(p)[0][0]["key"]
        num = pull.runs(p)[0][0]["conductors"][0]["num"]

        def run(dlg):
            dlg.findChild(QLineEdit, "cable_tag").setText("W101")
            dlg.findChild(QLineEdit, "cable_type").setText("4C #14 SOOW")
            mark = dlg.findChild(QComboBox, "marking")
            mark.setCurrentIndex(mark.findData("colors"))
            t = dlg.findChild(QTableWidget, "conductors")
            t.item(0, 1).setText("RED")
            return QDialog.Accepted
        with mock.patch.object(QDialog, "exec", run):
            self.assertTrue(dialogs.cables_dialog(self.b.win, p, tempfile.mkdtemp()))
        c = pull.cable(p, key)
        self.assertEqual((c["tag"], c["type"], c["marking"]), ("W101", "4C #14 SOOW", "colors"))
        self.assertEqual(c["colors"], {num: "RED"})
        head, rows = pull.table(p)
        self.assertEqual(rows[0][2:6], ["W101", "4C #14 SOOW", num, "RED"])
        self.assertEqual(rows[1][5], "BLK, #%s" % rows[1][4])   # (the other run: numbered)
        p.undo()
        self.assertEqual(pull.cable(p, key)["tag"], "")
        p.redo()
        self.assertEqual(pull.cable(p, key)["tag"], "W101")
        path = os.path.join(tempfile.mkdtemp(), "p.kzcad")
        p.save(path, backups=0)
        self.assertEqual(pull.cable(M.Project.load(path), key)["colors"], {num: "RED"})

    def test_cancel_keeps_nothing(self):
        self.b.two_panels()
        p = self.b.p

        def run(dlg):
            dlg.findChild(QLineEdit, "cable_tag").setText("W9")
            return QDialog.Rejected
        n = len(p.undo_stack)
        with mock.patch.object(QDialog, "exec", run):
            self.assertFalse(dialogs.cables_dialog(self.b.win, p, tempfile.mkdtemp()))
        self.assertEqual(len(p.undo_stack), n)

    def test_csv_and_pdf(self):
        self.b.two_panels()
        p = self.b.p
        d = tempfile.mkdtemp()
        n = pull.write_csv(p, os.path.join(d, "pull.csv"))
        with open(os.path.join(d, "pull.csv"), encoding="utf-8") as f:
            rows = list(csv.reader(f))
        self.assertEqual(n, 2)
        self.assertEqual(rows[0][0], "From")
        self.assertEqual(rows[1][6:], ["TB101-1", "PB101:2"])
        dialogs.write_pull_pdf(p, os.path.join(d, "pull.pdf"))
        with open(os.path.join(d, "pull.pdf"), "rb") as f:
            self.assertEqual(f.read(4), b"%PDF")

    def test_dialog_lists_runs_and_menu(self):
        self.b.two_panels()
        seen = []

        def run(dlg):
            lst = dlg.findChild(QListWidget, "runs")
            seen.append([lst.item(i).text() for i in range(lst.count())])
            seen.append(dlg.findChild(QTableWidget, "conductors").rowCount())
            return QDialog.Rejected
        with mock.patch.object(QDialog, "exec", run):
            self.b.win.show_cables()
        self.assertEqual(seen[0], ["MCP ↔ FIELD  (1)", "MCP ↔ JB-1  (1)"])
        self.assertEqual(seen[1], 1)
        acts = {a.text().replace("&", "") for m in self.b.win.menuBar().actions() if m.menu()
                for a in m.menu().actions()}
        self.assertIn("Cables between locations...", acts)

    def test_sheet_properties_location(self):
        p, v = self.b.p, self.b.v

        def run(dlg):
            dlg.findChild(QLineEdit, "location").setText("  MCP-2 ")
            return QDialog.Accepted
        with mock.patch.object(QDialog, "exec", run):
            self.assertTrue(dialogs.sheet_properties(self.b.win, p, v.sheet()))
        self.assertEqual(v.sheet().location, "MCP-2")

    def test_attributes_location(self):
        from kanzonascad.library_panel import attributes_dialog
        b = self.b
        lt = b.place("Pilot light", (6, 5))
        ins = b.v.sheet().entities[lt]

        def run(dlg):
            dlg.findChild(QLineEdit, "location").setText("FIELD")
            return QDialog.Accepted
        with mock.patch.object(QDialog, "exec", run):
            got = attributes_dialog(b.win, b.lib, ins, b.p, b.v.sheet())
        self.assertEqual(got["LOC"], "FIELD")

        def blank(dlg):
            return QDialog.Accepted
        with mock.patch.object(QDialog, "exec", blank):
            got = attributes_dialog(b.win, b.lib, ins, b.p, b.v.sheet())
        self.assertNotIn("LOC", got)                    # (none of its own: its sheet's)


if __name__ == "__main__":
    unittest.main()
