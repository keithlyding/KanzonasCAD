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
        # (an output module, sourcing: on the left of its sheet, its terminals down its right,
        # each point's text to their right; the owner, 0.21.2: "Shouldn't the ob8e module
        # default to the left side of the screen (sourcing output)?")
        s3 = made[1]
        out = next(e for e in s3.inserts())
        q = dict(out.pin_points())["0"]
        self.assertGreater(q[0], out.bbox()[0] + 0.5)
        mid = (s3.paper()[0] * s3.k()) / 2.0
        self.assertLess(out.bbox()[2], mid)
        t3 = next(e for e in s3.entities.values() if isinstance(e, M.Text) and
                  e.text == "O:3/0  M101  CONVEYOR RUN")
        self.assertEqual(t3.align, "left")
        self.assertLess(G.dist((t3.pos[0] - 0.15, t3.pos[1] - 0.03), q), 1e-9)
        from kanzonascad.scalefit import outside
        self.assertIsNone(outside(self.p, s))
        said = self.said[-1]
        self.assertIn("no 1769-XX99 in the library", said)
        self.assertIn("has no point 9", said)
        self.p.undo()
        self.assertEqual(len(self.p.sheets), n)

    def test_modules_kept_when_saved_and_opened(self):
        # (the module's block wasn't put in the project: after saving and opening, the sheet
        # showed nothing where the module was; the battery, 0.22.4, seed 44)
        made = self.win.import_io_list(self.path)
        for s in made:
            for e in s.inserts():
                self.assertIn(e.block, self.p.blocks)
        path = os.path.join(self.dir, "io.kzcad")
        self.p.save(path, backups=0)
        q = M.Project.load(path)
        for s in made:
            got = [e for e in q.sheet_by_id(s.id).inserts()]
            self.assertEqual(len(got), 1)
            self.assertIsNotNone(got[0].defn)
            self.assertEqual(dict(got[0].pin_points()), dict(s.inserts()[0].pin_points()))

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

    def test_clear_of_a_big_title_block(self):
        # (a title block of yours over most of the lower sheet: the module and its texts went
        # over it, as the battery found, 0.25 seed 7; now moved clear, or the sheet given the
        # biggest scale they fit at)
        from kanzonascad.scalefit import outside
        with self.p.edit("big title block") as ed:
            ed.add(self.p.title_block, M.Polyline([(2.6, 0.5), (16.4, 0.5), (16.4, 6.1),
                                                   (2.6, 6.1)], True))
        made = self.win.import_io_list(self.path)
        self.assertEqual(len(made), 2)
        for s in made:
            self.assertIsNone(outside(self.p, s), s.title)
            texts = [e for e in s.entities.values() if isinstance(e, M.Text)]
            self.assertEqual(len(texts), 3 if s is made[0] else 1)
            # (each beside its terminal on paper, at the sheet's scale)
            k = s.k()
            pins = [q for _n, q in s.inserts()[0].pin_points()]
            for t in texts:
                self.assertAlmostEqual(t.height, io_list.TEXT_H * k)
                side = 0.15 * k if t.align == "right" else -0.15 * k
                self.assertLess(min(G.dist((t.pos[0] + side, t.pos[1] - 0.03 * k), q)
                                    for q in pins), 1e-9)


if __name__ == "__main__":
    unittest.main()
