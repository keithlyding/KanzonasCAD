"""Source and destination arrows show the device at their wire's other end on a second line
(the owner, 0.19.3: "I can see that the switch connection goes to page x but also that it
goes to device x"), set for the project, a sheet, or one arrow, each overriding the one
before."""
import os
import tempfile
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import xrefs


class XrefDeviceTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.lib = self.win.library
        with self.p.edit("sheets") as ed:
            ed.add_sheet(self.p.make_sheet("Two"))
        self.s1, self.s2 = self.p.sheets
        with self.p.edit("w") as ed:
            ed.add(self.s1, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
            ed.add(self.s2, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
        # (a coil at each far end: one on page 1 before the source, one on page 2 after the
        # destination)
        self.c1 = self.place(self.s1, "Relay coil", (1.75, 5.0))
        self.c2 = self.place(self.s2, "Relay coil", (6.0, 5.0))
        self.src = self.place(self.s1, "Source arrow", (6.0, 5.0))
        self.dst = self.place(self.s2, "Destination arrow", (2.0, 5.0), answer="")
        self.t1 = self.c1.attrs["TAG"]
        self.t2 = self.c2.attrs["TAG"]
        self.assertNotEqual(self.t1, self.t2)

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def place(self, sheet, name, at, answer=None):
        self.v.show_sheet(sheet.id)
        self.v.run(C.InsertCmd, self.lib.get("symbol", name), {})
        type_in(self.v, "%g,%g" % at)
        if self.v.cmd is not None and answer is not None:
            type_in(self.v, answer)
        return [e for e in sheet.inserts() if e.defn.name == name][-1]

    def lines(self, sheet):
        """The arrow's reference lines on a sheet, top to bottom (level text)."""
        got = [it for it in xrefs.live(self.p, sheet)
               if "/" in it[2] or it[2] in (self.t1, self.t2)]
        return [t for _x, _y, t, *_r in sorted(got, key=lambda it: -it[1])]

    def arrow(self, sheet, block):
        return [e for e in sheet.inserts() if e.block == block][0]

    def test_second_line_both_ways(self):
        a = self.lines(self.s1)
        self.assertEqual(len(a), 2, a)
        self.assertIn("/", a[0])
        self.assertEqual(a[1], self.t2)              # (the source: the device on page 2)
        b = self.lines(self.s2)
        self.assertEqual(b[1:], [self.t1])           # (the destination: the one on page 1)
        # (the second line right under the first, one line down, both starting at the
        # arrow's side, clear of the arrow)
        items = sorted((it for it in xrefs.live(self.p, self.s1) if it[2] in a),
                       key=lambda it: -it[1])
        boxes = [xrefs.text_item(it).bbox() for it in items]
        self.assertAlmostEqual(boxes[0][0], boxes[1][0], places=5)   # (centers kept to 6 places)
        self.assertGreater(boxes[1][0], self.arrow(self.s1, "Source arrow").bbox()[2])
        self.assertAlmostEqual(items[0][1] - items[1][1],
                               items[0][3] * xrefs.LINE)

    def test_project_sheet_arrow_levels(self):
        with self.p.edit("off") as ed:
            ed.project_settings(dict(self.p.settings, xref_device=False))
        self.assertEqual(len(self.lines(self.s1)), 1)
        self.assertEqual(len(self.lines(self.s2)), 1)
        # (a sheet shown: that sheet only)
        with self.p.edit("sheet") as ed:
            ed.sheet_meta(self.s2, xref_device=True)
        self.assertEqual(len(self.lines(self.s1)), 1)
        self.assertEqual(self.lines(self.s2)[1:], [self.t1])
        # (one arrow off overrides its sheet)
        d = self.arrow(self.s2, "Destination arrow")
        with self.p.edit("arrow") as ed:
            ed.change(self.s2, d.copy(attrs=dict(d.attrs, XDEV="0")))
        self.assertEqual(len(self.lines(self.s2)), 1)
        # (and one on, on a sheet that follows a project with it off)
        s = self.arrow(self.s1, "Source arrow")
        with self.p.edit("arrow") as ed:
            ed.change(self.s1, s.copy(attrs=dict(s.attrs, XDEV="1")))
        self.assertEqual(self.lines(self.s1)[1:], [self.t2])
        # (all of it kept in the file)
        fd, path = tempfile.mkstemp(suffix=".kcad")
        os.close(fd)
        try:
            self.p.save(path)
            q = M.Project.load(path)
        finally:
            os.remove(path)
        self.assertFalse(q.settings["xref_device"])
        self.assertTrue(q.sheets[1].xref_device)
        self.assertIsNone(q.sheets[0].xref_device)
        self.assertEqual(self.arrow(q.sheets[0], "Source arrow").attrs.get("XDEV"), "1")
        self.assertEqual(self.arrow(q.sheets[1], "Destination arrow").attrs.get("XDEV"), "0")

    def test_undo_takes_the_sheet_setting_back(self):
        with self.p.edit("sheet") as ed:
            ed.sheet_meta(self.s1, xref_device=False)
        self.assertEqual(len(self.lines(self.s1)), 1)
        self.p.undo()
        self.assertEqual(self.lines(self.s1)[1:], [self.t2])

    def test_far_devices_each_way(self):
        names = xrefs.far_devices(self.s2, self.arrow(self.s2, "Destination arrow"))
        self.assertEqual(names, [self.t2])
        self.assertEqual(xrefs.far_devices(self.s1, self.arrow(self.s1, "Source arrow")),
                         [self.t1])


if __name__ == "__main__":
    unittest.main()
