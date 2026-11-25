"""Paste: Enter puts the objects where they were copied from (the owner, 0.26: "pressing Enter
instead of clicking drops the pasted objects at the exact coordinates they were copied from (so
copy from one sheet and paste to another lands in the same spot)"). A click still places them
by their lower left corner."""
import unittest

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


def shapes(ents):
    out = []
    for e in ents:
        d = e.to_dict()
        d.pop("id", None)
        out.append(repr(sorted(d.items())))
    return sorted(out)


class PasteEnterTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.one = self.v.sheet()
        with self.p.edit("drawn") as ed:
            self.ents = [ed.add(self.one, M.Line((3.125, 4.5), (7.3, 6.0625))),
                         ed.add(self.one, M.Circle((5.0, 2.75), 0.4)),
                         ed.add(self.one, M.Text((10.37, 8.21), "PANEL A", 0.125))]

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def copy(self):
        self.v.set_selection({e.id for e in self.ents})
        self.assertTrue(self.win.copy_clip())

    def paste(self):
        self.win.paste()
        self.assertIsInstance(self.v.cmd, C.PasteCmd)

    def new_on(self, sheet, before):
        return [e for i, e in sheet.entities.items() if i not in before]

    def test_enter_on_another_sheet_lands_in_the_same_spot(self):
        self.copy()
        self.win.add_sheet()
        two = self.v.sheet()
        self.assertIsNot(two, self.one)
        before = set(two.entities)
        self.paste()
        self.assertIn("Enter", self.v._prompt[0])
        QTest.keyClick(self.v, Qt.Key_Return)
        self.assertIsNone(self.v.cmd)
        got = self.new_on(two, before)
        self.assertEqual(shapes(got), shapes(self.ents))
        self.assertEqual(self.v.sel, {e.id for e in got})
        self.assertEqual(len(self.one.entities), 3)        # (the originals as they were)
        self.p.undo()
        self.assertEqual(self.new_on(two, before), [])

    def test_enter_on_the_same_sheet_puts_a_copy_on_top(self):
        self.copy()
        before = set(self.one.entities)
        self.paste()
        self.v.enter()                  # (Space or a right-click does the same)
        got = self.new_on(self.one, before)
        self.assertEqual(shapes(got), shapes(self.ents))

    def test_a_point_still_places_them(self):
        self.copy()
        before = set(self.one.entities)
        self.paste()
        type_in(self.v, "20,10")        # (their lower left corner there)
        got = self.new_on(self.one, before)
        self.assertEqual(len(got), 3)
        low = min(e.bbox()[0] for e in got), min(e.bbox()[1] for e in got)
        self.assertAlmostEqual(low[0], 20.0, 9)
        self.assertAlmostEqual(low[1], 10.0, 9)


if __name__ == "__main__":
    unittest.main()
