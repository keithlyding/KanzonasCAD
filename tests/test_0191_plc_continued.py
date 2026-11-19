"""PLC modules with two terminals a channel and modules over two sheets (the owner's 1756-IF16
drawing: IN-0 on terminal 2 above RTN-0 on 1, and "SLOT 7 CONTINUED" on the next sheet)."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


def texts(defn):
    return [t.text for t in defn.entities if isinstance(t, M.Text)]


class ContinuedTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.lib = self.win.library
        with self.p.edit("two") as ed:
            ed.add_sheet(self.p.make_sheet("Two"))
        self.s1, self.s2 = self.p.sheets

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_in_rtn_terminals(self):
        d = self.lib.get("symbol", "PLC analog input module, 8 channels IN/RTN")
        self.assertEqual(texts(d)[:4], ["2  IN-0", "1  RTN-0", "4  IN-1", "3  RTN-1"])
        self.assertEqual(len(d.pins), 16)
        cont = self.lib.get("symbol", "PLC analog input module, channels 8-15 IN/RTN continued")
        self.assertEqual(texts(cont)[:3], ["CONTINUED", "18  IN-8", "17  RTN-8"])
        self.assertEqual(cont.role, "child")

    def test_continued_on_the_next_sheet_follows_the_module(self):
        self.v.show_sheet(self.s1.id)
        self.v.run(C.InsertCmd, self.lib.get(
            "symbol", "PLC digital input module, 16 points, points 0-7"), {"SLOT": "7"})
        type_in(self.v, "10,10")
        self.v.cancel()
        mod = [e for e in self.s1.inserts()][0]
        tag = mod.attrs["TAG"]
        self.v.show_sheet(self.s2.id)
        self.v.run(C.InsertCmd, self.lib.get(
            "symbol", "PLC digital input module, points 8-15 continued"), {})
        type_in(self.v, "10,10")
        if self.v.cmd is not None:
            type_in(self.v, tag)                # (its module, by its tag)
        self.v.cancel()
        cont = [e for e in self.s2.inserts()][0]
        self.assertEqual(cont.attrs.get("PARENT"), mod.attrs["DEV"])
        self.assertEqual(cont.attrs["TAG"], tag)
        self.assertEqual([n for n, _q in cont.pin_points()][:2], ["8", "9"])
        # renumbered or retagged, the piece follows
        with self.p.edit("retag") as ed:
            ed.change(self.s1, mod.copy(attrs=dict(mod.attrs, TAG="PLC7", TAG_LOCK="1")))
        self.assertEqual(self.s2.entities[cont.id].attrs["TAG"], "PLC7")


if __name__ == "__main__":
    unittest.main()
