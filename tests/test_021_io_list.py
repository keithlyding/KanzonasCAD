"""PLC I/O from a spreadsheet (the owner's list, #14; the owner chose it): Sheets > Import I/O
list... brings in an I/O list's modules, each on a sheet of its own, with every point's
address, tag and description beside its terminal; a module or point the library hasn't got is
left out and named; one step."""
import os
import tempfile
import unittest

from tests.util import APP, window

from kanzonascad import geometry as G
from kanzonascad import io_list
from kanzonascad import model as M

LIST = """Slot,Catalog,Point,Address,Tag,Description
2,1734-IB8,0,I:2/0,PB101,START PUSHBUTTON
2,1734-IB8,1,I:2/1,PB102,STOP PUSHBUTTON
2,1734-IB8,7,I:2/7,LS201,PALLET PRESENT
3,1734-OB8,0,O:3/0,M101,CONVEYOR RUN
4,1769-XX99,0,I:4/0,X1,NOT IN THE LIBRARY
2,1734-IB8,9,I:2/9,X2,NO SUCH POINT
"""


class IoListTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.said = []
        self.win._say = lambda text, *a: self.said.append(text)
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "io.csv")
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(LIST)

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_modules_on_sheets_with_their_points(self):
        n = len(self.p.sheets)
        made = self.win.import_io_list(self.path)
        self.assertEqual([s.title for s in made], ["Slot 2 - 1734-IB8", "Slot 3 - 1734-OB8"])
        self.assertEqual(len(self.p.sheets), n + 2)
        s = made[0]
        mod = next(e for e in s.inserts())
        self.assertEqual((mod.block, mod.attrs.get("SLOT")), ("1734-IB8 module", "2"))
        self.assertTrue(mod.attrs.get("TAG", "").startswith("PLC"))
        pins = dict(mod.pin_points())
        texts = {e.text: e for e in s.entities.values() if isinstance(e, M.Text)}
        t = texts["I:2/0  PB101  START PUSHBUTTON"]
        self.assertEqual(t.align, "right")
        self.assertLess(G.dist((t.pos[0] + 0.15, t.pos[1] - 0.03), pins["0"]), 1e-9)
        self.assertIn("I:2/7  LS201  PALLET PRESENT", texts)
        from kanzonascad.scalefit import outside
        self.assertIsNone(outside(self.p, s))
        said = self.said[-1]
        self.assertIn("no 1769-XX99 in the library", said)
        self.assertIn("has no point 9", said)
        self.p.undo()
        self.assertEqual(len(self.p.sheets), n)

    def test_columns_by_name_any_order(self):
        path = os.path.join(self.dir, "b.csv")
        with open(path, "w", encoding="utf-8") as f:
            f.write("DESC,TAG,point,CATALOG NUMBER,Rack\nRUN,M1,0,1734-OB8,5\n")
        rows = io_list.read_rows(path)
        self.assertEqual(rows, [{"slot": "5", "catalog": "1734-OB8", "point": "0",
                                 "address": "", "tag": "M1", "desc": "RUN"}])
        with open(path, "w", encoding="utf-8") as f:
            f.write("Name,Thing\nA,B\n")
        with self.assertRaises(ValueError):
            io_list.read_rows(path)

    def test_excel(self):
        try:
            from openpyxl import Workbook
        except ImportError:
            self.skipTest("openpyxl isn't installed")
        wb = Workbook()
        ws = wb.active
        for line in LIST.strip().splitlines():
            ws.append(line.split(","))
        path = os.path.join(self.dir, "io.xlsx")
        wb.save(path)
        self.assertEqual(len(self.win.import_io_list(path)), 2)


if __name__ == "__main__":
    unittest.main()
