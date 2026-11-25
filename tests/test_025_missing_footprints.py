"""Devices without a footprint (0.25; the owner: "make a check, so any schematic block in the
drawing that's not assigned to a panel footprint will give me some sort of alert"): which
devices count (devices and parents, not contacts, arrows or the field; not those ticked No
footprint needed), which have one (a footprint on a panel sheet linked to them, or with their
tag), the orange marks (on to start, Project properties turns them off), the status bar's
count and its list (double-click or Enter goes to the device), the report (a report sheet,
CSV and Excel) and the flag kept through the attributes window, save and open."""
import os
import sys
import tempfile
import unittest
from unittest import mock

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QCheckBox, QDialog

from tests.util import APP, window

from kanzonascad import missing_fp as MF
from kanzonascad import model as M
from kanzonascad import report_sheets as RS
from kanzonascad import tags


class Base(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()
        lib = self.win.library
        self.coil = lib.get("symbol", "Relay coil")
        self.no = lib.get("symbol", "Contact NO")
        self.light = lib.get("symbol", "Pilot light")
        self.arrow = lib.get("symbol", "Off-sheet connector")
        self.fpdef = lib.get("footprint", "Breaker 1-pole (DIN)")
        with self.p.edit("blocks") as ed:
            for d in (self.coil, self.no, self.light, self.arrow, self.fpdef):
                ed.block(d)
            self.panel = ed.add_sheet(self.p.make_sheet("Panel", "panel"))

    def tearDown(self):
        for i in range(self.win.tabs.count()):
            d = self.win.tabs.widget(i)
            d.project.saved_at = len(d.project.undo_stack)
        if getattr(self.win, "missing_fp_dialog", None) is not None:
            self.win.missing_fp_dialog.close()
        self.win.close()
        self.assertTrue(APP)

    def add(self, defn, at, sheet=None, **attrs):
        with self.p.edit("add") as ed:
            return ed.add(sheet or self.s, M.Insert(defn.name, at, defn=self.p.blocks[defn.name],
                                                    attrs=attrs))

    def footprint(self, device=None, at=(5, 5), sheet=None, **attrs):
        d = self.p.blocks[self.fpdef.name]
        if device is not None:
            attrs = tags.link_footprint(attrs, device, d)
        return self.add(self.fpdef, at, sheet or self.panel, **attrs)

    def missing(self):
        return [e.attrs.get("TAG") for _s, e in MF.find(self.p).missing]


class WhichDevicesTest(Base):
    def test_devices_and_parents_count_contacts_and_arrows_dont(self):
        self.add(self.coil, (2, 8), TAG="CR101", DEV="c1")
        self.add(self.light, (4, 8), TAG="LT101", DEV="l1")
        self.add(self.no, (6, 8), TAG="CR101", PARENT="c1")
        self.add(self.arrow, (8, 8), TAG="A")
        self.assertEqual(sorted(self.missing()), ["CR101", "LT101"])

    def test_a_linked_footprint_on_a_panel_sheet(self):
        c = self.add(self.coil, (2, 8), TAG="CR101", DEV="c1")
        self.footprint(c)
        self.assertEqual(self.missing(), [])
        # (on a schematic sheet it doesn't count)
        with self.p.edit("kind") as ed:
            ed.sheet_meta(self.panel, kind="schematic")
        self.assertEqual(self.missing(), ["CR101"])

    def test_an_unlinked_footprint_with_its_tag(self):
        self.add(self.coil, (2, 8), TAG="CR101", DEV="c1")
        self.footprint(TAG="cr101")
        self.assertEqual(self.missing(), [])
        # (a footprint linked to another device with the same tag: not this one's)
        other = self.add(self.coil, (4, 8), TAG="CR102", DEV="c2")
        self.footprint(other, TAG="CR101")
        self.assertEqual(self.missing(), [])
        self.assertEqual(MF.find(self.p).missing, [])

    def test_field_locations(self):
        self.add(self.coil, (2, 8), TAG="CR101", DEV="c1", LOC="FIELD")
        self.add(self.coil, (4, 8), TAG="CR102", DEV="c2", LOC="JB-1")
        self.add(self.coil, (6, 8), TAG="CR103", DEV="c3", LOC="MCP")
        self.add(self.coil, (8, 8), TAG="CR104", DEV="c4")
        # (no panel sheet names a location: only FIELD is the field)
        self.assertEqual(sorted(self.missing()), ["CR102", "CR103", "CR104"])
        with self.p.edit("loc") as ed:
            ed.sheet_meta(self.panel, location="MCP")
        # (now JB-1, which no panel sheet is, is the field too)
        self.assertEqual(sorted(self.missing()), ["CR103", "CR104"])
        with self.p.edit("loc") as ed:
            ed.sheet_meta(self.s, location="JB-1")
        # (a device takes its sheet's location: CR104 now in JB-1)
        self.assertEqual(sorted(self.missing()), ["CR103"])

    def test_no_footprint_needed(self):
        c = self.add(self.coil, (2, 8), TAG="CR101", DEV="c1")
        self.assertEqual(self.missing(), ["CR101"])
        with self.p.edit("flag") as ed:
            ed.change(self.s, c.copy(attrs=MF.with_flag(c.attrs, True)))
        self.assertEqual(self.missing(), [])
        # (saved and opened, kept)
        path = os.path.join(tempfile.mkdtemp(), "f.kzcad")
        self.p.save(path, backups=0)
        q = M.Project.load(path)
        self.assertEqual(q.sheet_by_id(self.s.id).entities[c.id].attrs.get("NO_FP"), "1")
        self.assertEqual(MF.find(q).missing, [])

    def test_attributes_window_sets_the_flag(self):
        from kanzonascad import library_panel
        c = self.add(self.coil, (2, 8), TAG="CR101", DEV="c1")
        real = library_panel.QDialog.exec

        def tick(on):
            def answer(dlg):
                b = dlg.findChild(QCheckBox, "no_footprint")
                assert b is not None
                b.setChecked(on)
                return QDialog.Accepted
            return answer
        try:
            library_panel.QDialog.exec = tick(True)
            self.win.edit_attributes(self.s.entities[c.id])
            self.assertEqual(self.s.entities[c.id].attrs.get("NO_FP"), "1")
            self.assertEqual(self.missing(), [])
            library_panel.QDialog.exec = tick(False)
            self.win.edit_attributes(self.s.entities[c.id])
            self.assertNotIn("NO_FP", self.s.entities[c.id].attrs)
            self.assertEqual(self.missing(), ["CR101"])
        finally:
            library_panel.QDialog.exec = real

    def test_kept_until_the_project_changes(self):
        c = self.add(self.coil, (2, 8), TAG="CR101", DEV="c1")
        a = MF.find(self.p)
        self.assertIs(MF.find(self.p), a)
        self.footprint(c)
        b = MF.find(self.p)
        self.assertIsNot(b, a)
        self.assertEqual(len(b), 0)
        self.p.undo()
        self.assertEqual(len(MF.find(self.p)), 1)


class AlertsTest(Base):
    def test_status_bar_count(self):
        b = self.win.missing_fp_button
        self.assertTrue(b.isHidden())
        c = self.add(self.coil, (2, 8), TAG="CR101", DEV="c1")
        self.add(self.coil, (4, 8), TAG="CR102", DEV="c2")
        self.assertEqual(b.text(), "2 devices without a footprint")
        self.assertFalse(b.isHidden())
        self.footprint(c)
        self.assertEqual(b.text(), "1 device without a footprint")
        self.p.undo()
        self.assertEqual(b.text(), "2 devices without a footprint")

    def test_marks_follow_the_setting(self):
        c = self.add(self.coil, (2, 8), TAG="CR101", DEV="c1")
        self.assertEqual(MF.marks(self.p, self.s), [c.bbox()])
        self.assertEqual(MF.marks(self.p, self.panel), [])
        from kanzonascad import dialogs
        real = dialogs.QDialog.exec

        def off(dlg):
            b = dlg.findChild(QCheckBox, "fp_missing_marks")
            assert b is not None and b.isChecked()
            b.setChecked(False)
            return QDialog.Accepted
        dialogs.QDialog.exec = off
        try:
            self.win.project_properties(2)
        finally:
            dialogs.QDialog.exec = real
        self.assertFalse(self.p.settings["fp_missing_marks"])
        self.assertEqual(MF.marks(self.p, self.s), [])
        # (the count stays)
        self.assertEqual(self.win.missing_fp_button.text(), "1 device without a footprint")
        self.p.undo()
        self.assertEqual(MF.marks(self.p, self.s), [c.bbox()])

    @staticmethod
    def orange(img):
        want = QColor("#ff8c00")
        n = 0
        for y in range(0, img.height(), 2):
            for x in range(0, img.width(), 2):
                c = img.pixelColor(x, y)
                if abs(c.red() - want.red()) < 30 and abs(c.green() - want.green()) < 30 \
                        and c.blue() < 60:
                    n += 1
        return n

    def drawn(self):
        r = self.v.renderer()
        img = QImage(400, 300, QImage.Format_ARGB32)
        img.fill(Qt.black)
        qp = QPainter(img)
        w, h = self.s.paper()
        qp.scale(400 / w, -300 / h)
        qp.translate(0, -h)
        r.paint(qp)
        qp.end()
        return img

    def test_marks_drawn_orange_on_screen_only(self):
        self.assertEqual(self.orange(self.drawn()), 0)
        c = self.add(self.coil, (8, 6), TAG="CR101", DEV="c1")
        self.assertGreater(self.orange(self.drawn()), 0)
        self.footprint(c)
        self.assertEqual(self.orange(self.drawn()), 0)
        self.p.undo()
        # (printed: never)
        r = self.v.renderer()
        img = QImage(400, 300, QImage.Format_ARGB32)
        img.fill(Qt.white)
        qp = QPainter(img)
        w, h = self.s.paper()
        qp.scale(400 / w, -300 / h)
        qp.translate(0, -h)
        r.paint(qp, pen_width=0.01)
        qp.end()
        self.assertEqual(self.orange(img), 0)

    def test_list_goes_to_the_device(self):
        with self.p.edit("s2") as ed:
            s2 = ed.add_sheet(self.p.make_sheet("Two"))
        self.add(self.coil, (2, 8), TAG="CR101", DEV="c1")
        far = self.add(self.coil, (12, 3), s2, TAG="CR201", DEV="c2")
        self.win.missing_fp_button.click()
        dlg = self.win.missing_fp_dialog
        self.assertTrue(dlg.isVisible())
        t = dlg.table
        self.assertEqual(t.rowCount(), 2)
        self.assertEqual([t.item(i, 0).text() for i in range(2)], ["CR101", "CR201"])
        # double-click the second row
        t.itemDoubleClicked.emit(t.item(1, 0))
        self.assertIs(self.v.sheet(), s2)
        self.assertEqual(self.v.sel, {far.id})
        x0, y0, x1, y1 = far.bbox()
        cx, cy = self.v.center
        self.assertAlmostEqual(cx, (x0 + x1) / 2, places=6)
        self.assertAlmostEqual(cy, (y0 + y1) / 2, places=6)
        # Enter on the first
        t.setCurrentCell(0, 0)
        QTest.keyClick(t, Qt.Key_Return)
        self.assertIs(self.v.sheet(), self.s)
        self.assertEqual(len(self.v.sel), 1)
        # (the list follows the project)
        self.footprint(far)
        self.assertEqual(t.rowCount(), 1)

    def test_report_sheet_and_files(self):
        self.add(self.coil, (2, 8), TAG="CR101", DEV="c1", DESC="Run relay")
        self.assertIn("missing_fp", RS.kinds())
        self.assertEqual(RS.kinds()["missing_fp"], "Devices without a footprint")
        head, rows = RS.table(self.p, "missing_fp")
        self.assertEqual(head, MF.HEAD)
        self.assertEqual(rows[0][:4], ["CR101", "Run relay", self.coil.name, "1"])
        made = self.win.report_sheet("missing_fp")
        self.assertEqual(len(made), 1)
        texts = {e.text for e in made[0].entities.values() if isinstance(e, M.Text)}
        self.assertIn("CR101", texts)
        self.assertIn("Run relay", texts)
        from kanzonascad import reports
        folder = tempfile.mkdtemp()
        for name in ("m.csv", "m.xlsx"):
            path = os.path.join(folder, name)
            self.assertEqual(reports.write_csv(path, head, rows, "Devices without a footprint"),
                             1)
            self.assertGreater(os.path.getsize(path), 0)
        import openpyxl
        ws = openpyxl.load_workbook(os.path.join(folder, "m.xlsx")).active
        self.assertEqual(ws["A2"].value, "CR101")

    def test_dialog_saves(self):
        self.add(self.coil, (2, 8), TAG="CR101", DEV="c1")
        dlg = self.win.show_missing_footprints()
        path = os.path.join(tempfile.mkdtemp(), "list.csv")
        from kanzonascad import dialogs
        with mock.patch("PySide6.QtWidgets.QFileDialog.getSaveFileName",
                        return_value=(path, "")), \
                mock.patch.object(dialogs.QMessageBox, "information") as said:
            dlg.save.click()
        self.assertTrue(said.called)
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        self.assertEqual(lines[0], ",".join(MF.HEAD))
        self.assertTrue(lines[1].startswith("CR101,"))

    @unittest.skipIf(sys.platform == "win32", "Windows' offscreen Qt draws no text")
    def test_status_text_shown(self):
        self.add(self.coil, (2, 8), TAG="CR101", DEV="c1")
        self.assertEqual(self.win.missing_fp_button.text(), "1 device without a footprint")
        self.win.missing_fp_button.resize(self.win.missing_fp_button.sizeHint())
        img = self.win.missing_fp_button.grab().toImage()
        self.assertGreater(self.orange(img), 0, "the count isn't written in orange")


if __name__ == "__main__":
    unittest.main()
