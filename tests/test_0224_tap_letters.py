"""Tap numbers with letters (the owner, 0.22.4: "In addition to -1, can we add a, b, c, etc for
wire taps? Also -a, -b, -c, etc. This would be a project wide setting, able to be overridden by
sheet and by wire"; asked: a tap off a tap takes the other kind, "Alternate", and the letters
lowercase so a tap isn't taken for a distribution outlet's 6001A): 2007-1, 2007a or 2007-a; off
those 2007-1a, 2007a1, 2007-a1; the wire's own choice first, then its sheet's, then the
project's."""
import os
import tempfile
import unittest

from PySide6.QtWidgets import QComboBox, QDialog

from tests.util import APP, window

from kanzonascad import dialogs
from kanzonascad import model as M
from kanzonascad import reports
from kanzonascad import wirenums


class TapLetterTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.s = self.v.sheet()
        with self.p.edit("page") as ed:
            ed.sheet_meta(self.s, number="2")
        self.assertEqual(wirenums.tap_mode(self.p), "suffix")
        self.assertEqual(self.p.settings["tap_style"], "-1")

    def tearDown(self):
        self.win.__dict__.pop("ask_wire_number", None)
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def draw(self, sheet=None):
        """A wire (y = 8) tapped three times (x = 3, 6, 9), its first tap tapped again (y = 5)
        and that one tapped again (x = 4.5)."""
        s = sheet or self.s
        with self.p.edit("taps") as ed:
            ed.add(s, M.Wire([(1.0, 8.0), (12.0, 8.0)]))
            for x in (3.0, 6.0, 9.0):
                ed.add(s, M.Wire([(x, 8.0), (x, 4.0)]))
            ed.add(s, M.Wire([(3.0, 5.0), (5.0, 5.0)]))
            ed.add(s, M.Wire([(4.5, 5.0), (4.5, 2.0)]))

    def num(self, at, sheet=None):
        return [w.num for w in (sheet or self.s).wires() if w.touches(at)][0]

    def nums(self, sheet=None):
        return [self.num(q, sheet) for q in ((1.0, 8.0), (3.0, 4.0), (6.0, 4.0), (9.0, 4.0),
                                             (5.0, 5.0), (4.5, 2.0))]

    def setting(self, style):
        with self.p.edit("style") as ed:
            ed.project_settings({"tap_style": style})

    def test_each_style(self):
        self.draw()
        b = self.num((1.0, 8.0))
        want = {"-1": ["-1", "-2", "-3", "-1a", "-1a1"],
                "a": ["a", "b", "c", "a1", "a1a"],
                "-a": ["-a", "-b", "-c", "-a1", "-a1a"]}
        for style in ("a", "-a", "-1"):
            self.setting(style)
            self.assertEqual(self.nums(), [b] + [b + t for t in want[style]], style)

    def test_letters_go_on_past_z(self):
        self.assertEqual([wirenums.tap_suffix("a", i) for i in (0, 25, 26, 27)],
                         ["a", "z", "aa", "ab"])
        self.assertEqual(wirenums.tap_suffix("-a", 26), "-aa")

    def test_a_sheet_chooses_otherwise(self):
        self.setting("-1")
        self.draw()
        self.win.add_sheet()
        s2 = self.v.sheet()
        self.assertIsNot(s2, self.s)
        self.draw(s2)
        with self.p.edit("sheet") as ed:
            ed.sheet_meta(s2, tap_style="a")
        b1, b2 = self.num((1.0, 8.0)), self.num((1.0, 8.0), s2)
        self.assertEqual(self.num((3.0, 4.0)), b1 + "-1")
        self.assertEqual(self.num((3.0, 4.0), s2), b2 + "a")
        self.assertEqual(self.num((5.0, 5.0), s2), b2 + "a1")
        # (back to the project's)
        with self.p.edit("sheet") as ed:
            ed.sheet_meta(s2, tap_style=None)
        self.assertEqual(self.num((3.0, 4.0), s2), b2 + "-1")

    def test_a_wire_chooses_otherwise_in_its_wire_number_window(self):
        with self.p.edit("sheet") as ed:
            ed.sheet_meta(self.s, tap_style="a")       # (a sheet's choice, under the wire's)
        self.draw()
        b = self.num((1.0, 8.0))
        tap = [w for w in self.s.wires() if w.touches((6.0, 4.0))][0]
        asked = []

        def ask(num, tap_of=None, own="", locked=False):
            asked.append(self.win._asking_tap_style)
            return num, own, locked, "-a"
        self.win.ask_wire_number = ask
        self.win.edit_wire_number(tap)
        self.assertEqual(asked, [("", "a")])
        self.assertEqual(self.num((6.0, 4.0)), b + "-b")
        self.assertEqual(self.num((3.0, 4.0)), b + "a")        # (the others: as their sheet)
        self.assertEqual([w.tap_style for w in self.s.wires() if w.touches((6.0, 4.0))], ["-a"])
        self.p.undo()
        self.assertEqual(self.num((6.0, 4.0)), b + "b")
        # (a window answering as before 0.22.4, without a style: the wire's stays)
        self.win.ask_wire_number = lambda num, tap_of=None, own="", locked=False: (num, own,
                                                                                   locked)
        self.win.edit_wire_number([w for w in self.s.wires() if w.touches((6.0, 4.0))][0])
        self.assertEqual(self.num((6.0, 4.0)), b + "b")

    def test_kept_when_saved_and_opened(self):
        self.setting("-a")
        self.draw()
        with self.p.edit("sheet") as ed:
            ed.sheet_meta(self.s, tap_style="a")
            w = [w for w in self.s.wires() if w.touches((9.0, 4.0))][0]
            ed.change(self.s, w.copy(tap_style="-1"))
        path = os.path.join(tempfile.mkdtemp(), "taps.kzcad")
        self.p.save(path, backups=0)
        q = M.Project.load(path)
        s = q.sheet_by_id(self.s.id)
        self.assertEqual(q.settings["tap_style"], "-a")
        self.assertEqual(s.tap_style, "a")
        self.assertEqual([w.tap_style for w in s.wires() if w.touches((9.0, 4.0))], ["-1"])
        self.assertEqual(self.nums(s), self.nums())
        b = self.num((1.0, 8.0))
        self.assertEqual(self.num((9.0, 4.0)), b + "-3")
        self.assertEqual(self.num((3.0, 4.0)), b + "a")

    def test_trimmed_wires_keep_it(self):
        # (the pieces a wire is cut into are new wires: each keeps its tap style)
        from kanzonascad import wires as W
        self.draw()
        w = [w for w in self.s.wires() if w.touches((1.0, 8.0))][0].copy(tap_style="a")
        pieces, _ends = W.trim_wire(self.s, w, (7.5, 8.0))
        self.assertGreaterEqual(len(pieces), 2)
        self.assertEqual({x.tap_style for x in pieces}, {"a"})

    def test_terminal_count_with_letters(self):
        self.setting("a")
        self.draw()
        b = self.num((1.0, 8.0))
        rows, totals = reports.terminal_count_rows(self.p)
        self.assertEqual([r[:2] for r in rows], [[b, ", ".join(
            sorted([b + "a", b + "b", b + "c", b + "a1", b + "a1a"]))]])
        self.assertEqual(totals, (6, 5))

    def answer_with(self, name, data):
        seen = {}

        def answer(dlg):
            box = dlg.findChild(QComboBox, name)
            seen["items"] = [box.itemText(i) for i in range(box.count())]
            seen["was"] = box.currentData()
            seen["enabled"] = box.isEnabled()
            box.setCurrentIndex(box.findData(data))
            return QDialog.Accepted
        return answer, seen

    def test_project_properties(self):
        self.draw()
        answer, seen = self.answer_with("tap_style", "-a")
        real = dialogs.QDialog.exec
        dialogs.QDialog.exec = answer
        try:
            self.win.project_properties(1)
        finally:
            dialogs.QDialog.exec = real
        self.assertEqual(seen["was"], "-1")
        self.assertTrue(seen["enabled"])
        self.assertEqual(len(seen["items"]), 3)
        self.assertEqual(self.p.settings["tap_style"], "-a")
        self.assertEqual(self.num((3.0, 4.0)), self.num((1.0, 8.0)) + "-a")

    def test_sheet_properties(self):
        self.setting("a")
        self.draw()
        answer, seen = self.answer_with("sheet_tap_style", "-1")
        real = dialogs.QDialog.exec
        dialogs.QDialog.exec = answer
        try:
            dialogs.sheet_properties(self.win, self.p, self.s)
        finally:
            dialogs.QDialog.exec = real
        self.assertIsNone(seen["was"])
        self.assertIn("a, b, c", seen["items"][0])             # (As the project (a, b, c))
        self.assertEqual(self.s.tap_style, "-1")
        self.assertEqual(self.num((3.0, 4.0)), self.num((1.0, 8.0)) + "-1")

    def test_wire_number_window(self):
        answer, seen = self.answer_with("wire_tap_style", "a")
        real = dialogs.QDialog.exec
        dialogs.QDialog.exec = answer
        try:
            out = dialogs.wire_number_dialog(self.win, "2007-1", "2007", "", False, "suffix",
                                             "", "-a")
        finally:
            dialogs.QDialog.exec = real
        self.assertEqual(out[3], "a")
        self.assertIn("-a, -b, -c", seen["items"][0])           # (As the sheet (-a, -b, -c))
        self.assertEqual(len(seen["items"]), 4)


if __name__ == "__main__":
    unittest.main()
