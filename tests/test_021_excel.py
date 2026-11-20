"""Reports as Excel workbooks (the roadmap's item 8: "Excel export (openpyxl, MIT, imported only
when exporting)"): every report's Save as CSV or Excel... writes an .xlsx when that's the file's
type: one sheet, the header bold and kept in sight, columns wide enough, counts as numbers and
a wire number written with leading zeros kept as written; CSV as before."""
import csv
import os
import tempfile
import unittest

from tests.util import APP, window

from kanzonascad import bom
from kanzonascad import reports


class ExcelTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def test_workbook(self):
        path = os.path.join(self.dir, "wire list.xlsx")
        head = ["Wire", "Count", "Where"]
        rows = [["0012", "3", "Sheet 1, A2"], ["2004A", "12", "Sheet 2, C4"]]
        self.assertEqual(reports.write_csv(path, head, rows, "Wire list"), 2)
        from openpyxl import load_workbook
        ws = load_workbook(path).active
        self.assertEqual(ws.title, "Wire list")
        self.assertEqual([c.value for c in ws[1]], head)
        self.assertTrue(ws["A1"].font.bold)
        self.assertEqual(ws.freeze_panes, "A2")
        self.assertEqual([c.value for c in ws[2]], ["0012", 3, "Sheet 1, A2"])
        self.assertEqual([c.value for c in ws[3]], ["2004A", 12, "Sheet 2, C4"])
        self.assertGreaterEqual(ws.column_dimensions["C"].width, len("Sheet 2, C4"))

    def test_csv_as_before(self):
        path = os.path.join(self.dir, "wire list.csv")
        reports.write_csv(path, ["Wire"], [["0012"]])
        with open(path, newline="", encoding="utf-8") as f:
            self.assertEqual(list(csv.reader(f)), [["Wire"], ["0012"]])

    def test_bill_of_materials(self):
        win, v = window()
        try:
            path = os.path.join(self.dir, "bom.xlsx")
            n = bom.write_csv(v.project, path)
            from openpyxl import load_workbook
            ws = load_workbook(path).active
            self.assertEqual(ws.title, "Bill of materials")
            self.assertEqual(ws.max_row, n + 1)
        finally:
            win.close()
        self.assertTrue(APP)


if __name__ == "__main__":
    unittest.main()
