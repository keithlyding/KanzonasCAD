"""Duplicate tags and wire numbers warned of (the owner, 0.18.1: "The sheet needs to warn me if
I duplicate a tag or wire number"; asked: marked red on the drawing until fixed, a message on
the command line when one appears, over the whole project; wires meant to share a number
aren't)."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import dupes
from kanzonascad import model as M
from kanzonascad import wirenums


class DuplicatesTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.s = self.v.sheet()
        for at in ("3,6", "3,3"):
            self.v.run(C.InsertCmd, self.win.library.get("symbol", "Relay coil"), {})
            type_in(self.v, at)
        self.a, self.b = sorted(self.s.inserts(), key=lambda e: e.pos[1], reverse=True)
        with self.p.edit("wires") as ed:
            self.w1 = ed.add(self.s, M.Wire([(8.0, 6.0), (10.0, 6.0)]))
            self.w2 = ed.add(self.s, M.Wire([(8.0, 3.0), (10.0, 3.0)]))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_none_to_start(self):
        self.assertEqual(dupes.find(self.p), ({}, {}))
        self.assertEqual(dupes.marks(self.p, self.s), [])

    def test_duplicate_tag(self):
        tag = self.a.attrs["TAG"]
        with self.p.edit("retag") as ed:
            b = self.s.entities[self.b.id]
            ed.change(self.s, b.copy(attrs=dict(b.attrs, TAG=tag, TAG_LOCK="1")))
        dup_tags, _n = dupes.find(self.p)
        self.assertEqual(list(dup_tags), [tag.upper()])
        self.assertEqual(len(dupes.marks(self.p, self.s)), 2)          # (both marked)
        self.assertIn("Duplicate tag %s" % tag.upper(), dupes.describe(self.p, dup_tags, {}))
        self.p.undo()
        self.assertEqual(dupes.find(self.p), ({}, {}))
        self.assertEqual(dupes.marks(self.p, self.s), [])

    def test_duplicate_wire_number_and_kept_on_purpose(self):
        with self.p.edit("nums") as ed:
            wirenums.set_number(ed, self.p, self.s, self.s.entities[self.w1.id], "999", True)
            wirenums.set_number(ed, self.p, self.s, self.s.entities[self.w2.id], "999", True)
        _t, dup_nums = dupes.find(self.p)
        self.assertEqual(list(dup_nums), ["999"])
        self.assertEqual(len(dup_nums["999"]), 2)
        self.assertTrue(dupes.marks(self.p, self.s))
        # kept on purpose ("No: just the same number"): not a duplicate
        with self.p.edit("same") as ed:
            ed.project_settings({"same_numbers": ["999"]})
        self.assertEqual(dupes.find(self.p)[1], {})

    def test_said_once_on_the_command_line(self):
        said = []
        self.win._say = lambda msg, ms=6000: said.append(msg)
        tag = self.a.attrs["TAG"]
        with self.p.edit("retag") as ed:
            b = self.s.entities[self.b.id]
            ed.change(self.s, b.copy(attrs=dict(b.attrs, TAG=tag, TAG_LOCK="1")))
        self.win._project_changed(self.win.doc())
        self.assertTrue(any("Duplicate tag" in m for m in said), said)
        n = len(said)
        with self.p.edit("other") as ed:
            ed.add(self.s, M.Line((0, 0), (1, 1)))
        self.win._project_changed(self.win.doc())
        self.assertEqual(len([m for m in said[n:] if "Duplicate" in m]), 0)   # (not again)

    def test_not_printed(self):
        from PySide6.QtGui import QImage, QPainter
        from kanzonascad import render
        tag = self.a.attrs["TAG"]
        with self.p.edit("retag") as ed:
            b = self.s.entities[self.b.id]
            ed.change(self.s, b.copy(attrs=dict(b.attrs, TAG=tag, TAG_LOCK="1")))
        calls = []
        r = render.SheetRenderer(self.p, self.s)
        r._paint_dupes = lambda painter: calls.append(1)
        img = QImage(200, 200, QImage.Format_ARGB32)
        p = QPainter(img)
        r.paint(p, pen_width=0.01)                                   # (a print: a width)
        p.end()
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
