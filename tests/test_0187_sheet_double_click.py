"""Double-clicking a sheet in the Sheets list opens its Sheet properties (the owner, 0.18.7:
"I'd like to be able to double click on a sheet in the left hand panel to open up sheet
properties"): a first click that shows another sheet no longer rebuilds the list under the
mouse, which lost the second click."""
import unittest
from unittest import mock

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from tests.util import APP, window


class SheetDoubleClickTest(unittest.TestCase):
    def test_double_click_opens_sheet_properties(self):
        win, v = window()
        try:
            with v.project.edit("sheet") as ed:
                ed.add_sheet(v.project.make_sheet("Two"))
            win._fill_sheets()
            win.show()
            APP.processEvents()
            lst = win.sheet_list
            two = v.project.sheets[1]
            item = [lst.item(i) for i in range(lst.count())
                    if lst.item(i).data(Qt.UserRole) == two.id][0]
            at = lst.visualItemRect(item).center()
            seen = []
            with mock.patch("kanzonascad.dialogs.sheet_properties",
                            lambda parent, project, sheet: seen.append(sheet) or False):
                QTest.mouseClick(lst.viewport(), Qt.LeftButton, Qt.NoModifier, at)
                QTest.mouseDClick(lst.viewport(), Qt.LeftButton, Qt.NoModifier, at)
                APP.processEvents()
            self.assertIs(v.sheet(), two)
            self.assertEqual(seen, [two])
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()


if __name__ == "__main__":
    unittest.main()
