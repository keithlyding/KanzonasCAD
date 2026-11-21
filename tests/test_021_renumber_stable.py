"""Renumber sheet gives a page's devices 01, 02, 03... every time (the owner, Nov 2026: "Sometimes
they do; other times they do 204, 205, 206. Sometimes it's 210, 204, 205"). A footprint (or a
drive's power section on another sheet) linked to a device carries its tag; counted as a device
of its own, it held the number, so the devices skipped it, then got it back once the footprint
had followed: 204, then 201, then 204..."""
import unittest

from tests.util import APP

from kanzonascad import model as M
from kanzonascad import tags


def block(name, kind):
    return M.BlockDef(name, kind, [M.Circle((0, 0), 0.1)],
                      [{"name": "1", "pos": (-0.2, 0)}, {"name": "2", "pos": (0.2, 0)}],
                      (0, 0.2), 0.1, "", "", "device", "", "M")


class RenumberStableTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(APP)
        p = self.p = M.Project()
        self.panel = p.make_sheet("Panel", "panel")
        self.page = p.make_sheet("Power", "schematic")
        coil, fp = block("Coil", "symbol"), block("Coil FP", "footprint")
        with p.edit("draw") as ed:
            ed.add_sheet(self.panel)
            ed.add_sheet(self.page)
            ed.sheet_meta(self.page, number="2")
            for i, x in enumerate((1.0, 3.0, 5.0)):
                dev = "d%d" % i
                ed.add(self.page, M.Insert("Coil", (x, 5.0), 0.0, 1.0, False,
                                           {"TAG": "M2%02d" % (i + 1), "DEV": dev}, coil))
                ed.add(self.panel, M.Insert("Coil FP", (x, 2.0), 0.0, 1.0, False,
                                            {"TAG": "M2%02d" % (i + 1), "PARENT": dev}, fp))

    def tags_on(self, sheet):
        return sorted(e.attrs.get("TAG") for e in sheet.inserts())

    def test_the_same_tags_every_time(self):
        for _k in range(3):
            with self.p.edit("renumber") as ed:
                tags.renumber_sheet(ed, self.p, self.page)
                tags.sync_children(ed, self.p)
            self.assertEqual(self.tags_on(self.page), ["M201", "M202", "M203"])
            self.assertEqual(self.tags_on(self.panel), ["M201", "M202", "M203"])


if __name__ == "__main__":
    unittest.main()
