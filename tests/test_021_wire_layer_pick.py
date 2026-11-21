"""The layer wires go on (the owner, 0.21: "every time I reopen the project, the layer I had
selected reverts to the default wires layer", "project and per sheet (so both)", and
"Picking layer 0 should revert the wires default back to whatever the sheet default is"):
each sheet has a default, its own (Sheet properties, saved) or the project's (Project
properties, Wire layers); the Schematic tab's layer box lists the wire layers only and picks
one on top of it, per sheet, until a layer that isn't a wire layer is picked."""
import os
import tempfile
import unittest

from PySide6.QtWidgets import QComboBox, QDialog, QInputDialog

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import dialogs
from kanzonascad import model as M
from kanzonascad import wirelayers


class WireLayerPickTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        with self.p.edit("layers") as ed:
            wirelayers.add_preset(ed, self.p, ["24 VDC", "120 V"])
            ed.layer("NOTES", None, M.Layer("NOTES").to_dict())
        self.s1 = self.v.sheet()
        self.win.add_sheet()
        self.s2 = self.v.sheet()
        self.go(self.s1)

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def go(self, sheet):
        self.v.show_sheet(sheet.id)
        self.assertIs(self.v.sheet(), sheet)

    def pick(self, name):
        box = self.win.sch_layer_box
        i = box.findText(name)
        self.assertGreaterEqual(i, 0, name)
        box.setCurrentIndex(i)
        box.activated.emit(i)

    def wire(self, a, b):
        self.v.run(C.WireCmd)
        type_in(self.v, a, b)
        if self.v.cmd is not None:
            self.v.cmd.enter()
        if self.v.cmd is not None:
            self.v.cancel()
        return max(self.v.sheet().wires(), key=lambda w: w.id)

    def test_the_box_lists_the_wire_layers_only(self):
        box = self.win.sch_layer_box
        items = [box.itemText(i) for i in range(box.count())]
        self.assertEqual(items, wirelayers.wire_layers(self.p))
        self.assertIn("24VDC BLU", items)
        self.assertNotIn("NOTES", items)
        self.assertNotIn("SYMBOLS", items)
        self.assertEqual(box.currentText(), "WIRES")

    def test_a_pick_per_sheet_and_back_to_the_default(self):
        self.pick("24VDC BLU")
        self.assertEqual(self.wire("1,3", "5,3").layer, "24VDC BLU")
        self.go(self.s2)                                    # (its own default)
        self.assertEqual(self.win.sch_layer_box.currentText(), "WIRES")
        self.assertEqual(self.wire("1,3", "5,3").layer, "WIRES")
        self.go(self.s1)
        self.assertEqual(self.win.sch_layer_box.currentText(), "24VDC BLU")
        box = self.win.layer_box                            # (0, on the Home tab)
        box.activated.emit(box.findText("0"))
        self.assertEqual(self.v.layer(), "0")
        self.assertEqual(C.wire_layer(self.v), "WIRES")
        self.assertEqual(self.win.sch_layer_box.currentText(), "WIRES")

    def test_layer_0_goes_back_to_the_sheets_own_default(self):
        with self.p.edit("default") as ed:
            ed.sheet_meta(self.s1, wire_layer="120V BLK")
        self.assertEqual(C.wire_layer(self.v), "120V BLK")
        self.pick("24VDC BLU")
        self.assertEqual(C.wire_layer(self.v), "24VDC BLU")
        self.assertTrue(C.set_wire_layer(self.v, "0"))
        self.assertEqual(C.wire_layer(self.v), "120V BLK")
        self.assertEqual(self.wire("1,3", "5,3").layer, "120V BLK")

    def test_the_default_is_saved_the_pick_is_not(self):
        with self.p.edit("default") as ed:
            ed.sheet_meta(self.s1, wire_layer="120V RED")
        self.pick("24VDC BLU")
        self.assertEqual(self.s1.wire_layer, "120V RED")        # (a pick: not the default)
        path = os.path.join(tempfile.mkdtemp(), "x.kzcad")
        self.p.save(path)
        q = M.Project.load(path)                            # (reopened: the defaults)
        self.assertEqual(wirelayers.sheet_wire_layer(q, q.sheets[0]), "120V RED")
        self.assertEqual(wirelayers.sheet_wire_layer(q, q.sheets[1]), "WIRES")

    def test_a_pick_isnt_an_edit(self):
        n = len(self.p.undo_stack)
        self.pick("120V RED")
        self.assertEqual(len(self.p.undo_stack), n)
        self.assertEqual(C.wire_layer(self.v), "120V RED")

    def test_the_project_default_for_sheets_without_their_own(self):
        with self.p.edit("default") as ed:
            ed.sheet_meta(self.s1, wire_layer="24VDC BLU")
            ed.project_settings({"wire_layer": "120V BLK"})
        self.assertEqual(C.wire_layer(self.v), "24VDC BLU")        # (its own)
        self.go(self.s2)
        self.assertEqual(C.wire_layer(self.v), "120V BLK")         # (the project's)
        with self.p.edit("default") as ed:
            ed.project_settings({"wire_layer": "NOTES"})          # (not a wire layer)
        self.assertEqual(C.wire_layer(self.v), "WIRES")

    def test_selected_wires_move_to_the_layer_picked(self):
        w = self.wire("1,3", "5,3")
        with self.p.edit("line") as ed:
            ln = ed.add(self.s1, M.Line((1.0, 6.0), (5.0, 6.0), layer="NOTES"))
        self.v.set_selection({w.id, ln.id})
        self.pick("24VDC BLU")
        self.assertEqual(self.s1.entities[w.id].layer, "24VDC BLU")
        self.assertEqual(self.s1.entities[ln.id].layer, "NOTES")   # (not a wire: left)
        self.assertEqual(C.wire_layer(self.v), "WIRES")            # (moved, not picked)

    def test_a_wire_layer_picked_on_the_home_tab_is_the_sheets(self):
        box = self.win.layer_box
        i = box.findText("24VDC BLU")
        box.setCurrentIndex(i)
        box.activated.emit(i)
        self.assertEqual(C.wire_layer(self.v), "24VDC BLU")
        self.assertEqual(self.win.sch_layer_box.currentText(), "24VDC BLU")

    def test_sheet_properties_sets_it(self):
        self.pick("24VDC BLU")                  # (dropped: the new default is used at once)
        real = dialogs.QDialog.exec

        def answer(dlg):
            box = dlg.findChild(QComboBox, "sheet_wire_layer")
            box.setCurrentIndex(box.findData("120V WHT"))
            return QDialog.Accepted
        try:
            dialogs.QDialog.exec = answer
            self.win.sheet_properties()
        finally:
            dialogs.QDialog.exec = real
        self.assertEqual(self.s1.wire_layer, "120V WHT")
        self.assertEqual(C.wire_layer(self.v), "120V WHT")
        self.assertEqual(self.win.sch_layer_box.currentText(), "120V WHT")

        def back(dlg):
            box = dlg.findChild(QComboBox, "sheet_wire_layer")
            box.setCurrentIndex(0)                          # (as the project)
            return QDialog.Accepted
        try:
            dialogs.QDialog.exec = back
            self.win.sheet_properties()
        finally:
            dialogs.QDialog.exec = real
        self.assertIsNone(self.s1.wire_layer)

    def test_project_properties_wire_layers(self):
        self.pick("24VDC BLU")                  # (dropped: the new default is used at once)
        real = dialogs.QDialog.exec
        real_text = QInputDialog.getText

        def answer(dlg):
            table = dlg.findChild(dialogs.LayersDialog, "wire_layers_table")
            QInputDialog.getText = staticmethod(lambda *a, **k: ("CONTROL", True))
            table._new()                    # (a wire layer, whatever its name)
            names = [table.table.item(r, 0).data(0x0100)
                     for r in range(table.table.rowCount())]
            self.assertIn("CONTROL", names)
            self.assertNotIn("NOTES", names)
            box = dlg.findChild(QComboBox, "project_wire_layer")
            box.setCurrentIndex(box.findText("CONTROL"))
            return QDialog.Accepted
        try:
            dialogs.QDialog.exec = answer
            self.win.project_properties(3)
        finally:
            dialogs.QDialog.exec = real
            QInputDialog.getText = real_text
        self.assertTrue(self.p.layers["CONTROL"].wire)
        self.assertEqual(self.p.settings["wire_layer"], "CONTROL")
        self.assertEqual(self.wire("1,3", "5,3").layer, "CONTROL")
        self.assertEqual(M.Layer.from_dict(self.p.layers["CONTROL"].to_dict()).wire, True)

    def test_renaming_a_layer_keeps_the_sheets_and_projects(self):
        with self.p.edit("default") as ed:
            ed.sheet_meta(self.s1, wire_layer="24VDC BLU")
            ed.project_settings({"wire_layer": "24VDC BLU"})
        self.assertIsNotNone(self.s1.wire_layer)
        dlg = dialogs.LayersDialog(self.win, self.p, "0", wires_only=True)
        row = [dlg.table.item(r, 0).data(0x0100)
               for r in range(dlg.table.rowCount())].index("24VDC BLU")
        dlg.table.setCurrentCell(row, 0)
        real = QInputDialog.getText
        try:
            QInputDialog.getText = staticmethod(lambda *a, **k: ("24V CONTROL", True))
            dlg._rename()
        finally:
            QInputDialog.getText = real
        self.assertEqual(self.s1.wire_layer, "24V CONTROL")
        self.assertEqual(self.p.settings["wire_layer"], "24V CONTROL")
        self.go(self.s2)
        self.assertEqual(C.wire_layer(self.v), "24V CONTROL")


if __name__ == "__main__":
    unittest.main()
