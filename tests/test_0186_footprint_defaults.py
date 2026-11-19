"""A linked footprint's manufacturer, catalog number and description default to the footprint
block's own (its Properties...), then the device's (the owner, 0.18.6: "shouldn't it default
to the footprint settings?")."""
import unittest

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import tags


def fp(**kw):
    return M.BlockDef("AB 100-C09", "footprint",
                      [M.Polyline([(0, 0), (2, 0), (2, 4), (0, 4)], True)], **kw)


def dev():
    d = M.BlockDef("Coil", "symbol", [M.Line((0, 0), (1, 0))], role="parent", prefix="M")
    return M.Insert("Coil", (1, 1), 0.0, 1.0, False,
                    {"TAG": "M1", "DEV": "d1", "MFR": "Siemens", "CAT": "3RT2015",
                     "DESC": "Motor starter"}, d)


class FootprintDefaultsTest(unittest.TestCase):
    def test_the_footprints_own_first(self):
        got = tags.link_footprint({}, dev(), fp(manufacturer="Allen-Bradley",
                                                catalog="100-C09D10"))
        self.assertNotIn("MFR", got)                    # (its block's: Allen-Bradley)
        self.assertNotIn("CAT", got)                    # (100-C09D10)
        self.assertEqual(got["DESC"], "Motor starter")  # (it has none: the device's)
        self.assertEqual((got["TAG"], got["PARENT"]), ("M1", "d1"))
        # typed on the copy: kept
        got = tags.link_footprint({"CAT": "100-C12"}, dev(), fp(catalog="100-C09D10"))
        self.assertEqual(got["CAT"], "100-C12")
        # a footprint with nothing of its own: the device's, as before
        got = tags.link_footprint({}, dev(), fp())
        self.assertEqual((got["MFR"], got["CAT"]), ("Siemens", "3RT2015"))

    def test_label_and_bill_of_materials(self):
        d = fp(catalog="100-C09D10", description="Contactor 9A")
        e = M.Insert(d.name, (10, 20), 0.0, 1.0, False, {"TAG": "M1"}, d, 0.1, "tag,cat,desc")
        self.assertEqual([t.text for _k, t in e.label_texts()],
                         ["M1", "100-C09D10", "Contactor 9A"])

    def test_the_window_shows_them(self):
        from PySide6.QtWidgets import QDialog, QLineEdit
        from kanzonascad import library_panel
        win, v = window()
        try:
            d = fp(manufacturer="Allen-Bradley", catalog="100-C09D10")
            e = M.Insert(d.name, (10, 20), 0.0, 1.0, False, {"TAG": "M1"}, d, 0.1, "tag")
            seen = {}

            def look(dlg):
                for w in dlg.findChildren(QLineEdit):
                    if w.placeholderText():
                        seen[w.placeholderText()] = w.text()
                return QDialog.Rejected
            real = library_panel.QDialog.exec
            library_panel.QDialog.exec = look
            try:
                library_panel.attributes_dialog(win, win.library, e, v.project, v.sheet(), {})
            finally:
                library_panel.QDialog.exec = real
            self.assertEqual(seen, {"Allen-Bradley (the footprint's)": "",
                                    "100-C09D10 (the footprint's)": ""})
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()
        self.assertTrue(APP)


if __name__ == "__main__":
    unittest.main()
