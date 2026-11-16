"""Dashed boxes (the owner: "I need to be able to add a dashed box and write whatever note I
want inside of it and it not be attached to a child or parent", and boxes that belong to a
device, picked by "type, select a dropdown of parents that are already in the drawing, or be
able to navigate to a sheet and select it"); and a contact's device picked on the drawing (P)."""
import os
import tempfile
import unittest

from PySide6.QtWidgets import QApplication

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import fileio
from kanzonascad import model as M
from kanzonascad import tags
from kanzonascad import xrefs


class DashBoxTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        self.lib = self.win.library
        self.p = v.project

    def tearDown(self):
        self.win.__dict__.pop("ask_dash_box", None)
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def insert(self, name, at):
        s = self.v.sheet()
        before = set(s.entities)
        self.v.run(C.InsertCmd, self.lib.get("symbol", name), {})
        type_in(self.v, "%r,%r" % at)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        return [e for i, e in s.entities.items() if i not in before and isinstance(e, M.Insert)][0]

    def box(self, a, b, answer):
        self.win.ask_dash_box = lambda box: answer
        s = self.v.sheet()
        before = set(s.entities)
        self.v.run(C.DashBoxCmd)
        type_in(self.v, "%r,%r" % a, "%r,%r" % b)
        got = [e for i, e in s.entities.items() if i not in before and isinstance(e, M.DashBox)]
        return got[0] if got else None

    def test_a_box_with_a_note_and_nothing_else(self):
        b = self.box((2.0, 8.0), (6.0, 5.0), {"text": "FIELD WIRING\nBY OTHERS", "device": None})
        self.assertEqual(b.points, [(2.0, 8.0), (6.0, 8.0), (6.0, 5.0), (2.0, 5.0)])
        self.assertEqual(b.text, "FIELD WIRING\nBY OTHERS")
        self.assertEqual(b.attrs, {})
        self.assertEqual(b.tag(), "")
        texts = [e.text for e in b.parts() if isinstance(e, M.Text)]
        self.assertEqual(texts, ["FIELD WIRING", "BY OTHERS"])
        # the note inside the box, near its top left corner
        x, y = b.note_point()
        self.assertTrue(2.0 < x < 2.5 and 7.5 < y < 8.0, (x, y))
        # dashes all on its outline, with gaps
        dashes = b.dash_pieces()
        self.assertGreater(len(dashes), 20)
        on = lambda q: any(abs(G) < 1e-9 for G in (q[0] - 2, q[0] - 6, q[1] - 5, q[1] - 8))
        self.assertTrue(all(on(a) and on(c) for a, c in dashes))
        total = sum(((c[0] - a[0]) ** 2 + (c[1] - a[1]) ** 2) ** 0.5 for a, c in dashes)
        self.assertLess(total, 14.0 * 0.8)
        self.assertGreater(total, 14.0 * 0.5)
        self.assertEqual(self.v.sheet().entities[b.id].layer, "NOTES")

    def test_corners_stretch_and_it_stays_a_rectangle(self):
        b = self.box((2.0, 8.0), (6.0, 5.0), {"text": "X", "device": None})
        c = b.with_grip(2, (7.0, 4.0))
        self.assertEqual(c.points, [(2.0, 8.0), (7.0, 8.0), (7.0, 4.0), (2.0, 4.0)])
        c = b.with_grip(0, (1.0, 9.0))
        self.assertEqual(c.points, [(1.0, 9.0), (6.0, 9.0), (6.0, 5.0), (1.0, 5.0)])
        # the note's grip
        n = len(b.points)
        self.assertEqual(b.with_grip(n, (3.0, 6.0)).note_point(), (3.0, 6.0))

    def test_belongs_to_a_device_from_the_list_follows_it(self):
        coil = self.insert("Contactor coil", (3.0, 3.0))
        dev = self.v.sheet().entities[coil.id]
        b = self.box((2.0, 8.0), (6.0, 5.0), {"text": "BUCKET 3", "device": dev})
        self.assertEqual(b.attrs["PARENT"], dev.attrs["DEV"])
        self.assertEqual(b.tag(), dev.attrs["TAG"])
        s = self.v.sheet()
        # the coil lists where the box is; the box says where the coil is
        refs = xrefs.live(self.p, s)
        here = self.p.zone_text(s, 2.0, 8.0)
        coil_at = self.p.zone_text(s, *dev.pos)
        self.assertIn(here, [t for _x, _y, t, _h in refs])
        self.assertIn(coil_at, [t for _x, _y, t, _h in refs])
        # retagged, the box follows
        with self.p.edit("retag") as ed:
            ed.change(s, dev.copy(attrs=dict(dev.attrs, TAG="M77", TAG_LOCK="1")))
        self.assertEqual(s.entities[b.id].tag(), "M77")
        # the device deleted: the box keeps its tag, shown "?" beside it
        with self.p.edit("erase") as ed:
            ed.remove(s, coil.id)
        self.assertEqual(s.entities[b.id].tag(), "M77")
        self.assertIn("?", [t for _x, _y, t, _h in xrefs.live(self.p, s)])

    def test_picked_on_another_sheet(self):
        s1 = self.v.sheet()
        self.win.add_sheet()
        s2 = self.p.sheets[1]
        self.v.show_sheet(s2.id)
        coil = self.insert("Relay coil", (4.0, 5.0))
        self.v.show_sheet(s1.id)
        self.win.ask_dash_box = lambda box: {"text": "N", "device": None, "pick": True}
        self.v.run(C.DashBoxCmd)
        type_in(self.v, "2,8", "6,5")
        self.assertIsInstance(self.v.cmd, C.PickDeviceCmd)
        self.v.show_sheet(s2.id)
        QApplication.processEvents()
        self.assertIsInstance(self.v.cmd, C.PickDeviceCmd)    # (still picking there)
        # a click on nothing says so and goes on
        self.v.cmd.point((20.0, 1.0))
        self.assertIsInstance(self.v.cmd, C.PickDeviceCmd)
        self.v.cmd.point(dict(coil.pin_points())["A1"])
        for _i in range(3):
            QApplication.processEvents()
        self.assertEqual(self.v.sheet_id, s1.id)
        b = [e for e in s1.entities.values() if isinstance(e, M.DashBox)]
        self.assertEqual(len(b), 1)
        self.assertEqual(b[0].tag(), s2.entities[coil.id].attrs["TAG"])
        self.assertIn(self.p.zone_text(s2, *s2.entities[coil.id].pos),
                      [t for _x, _y, t, _h in xrefs.live(self.p, s1)])

    def test_esc_while_picking_makes_nothing(self):
        s1 = self.v.sheet()
        self.win.ask_dash_box = lambda box: {"text": "", "device": None, "pick": True}
        self.v.run(C.DashBoxCmd)
        type_in(self.v, "2,8", "6,5")
        self.v.escape()
        for _i in range(3):
            QApplication.processEvents()
        self.assertIsNone(self.v.cmd)
        self.assertFalse(any(isinstance(e, M.DashBox) for e in s1.entities.values()))
        self.assertIsNone(self.win._picking)

    def test_a_contacts_device_picked_on_another_sheet(self):
        s1 = self.v.sheet()
        self.win.add_sheet()
        s2 = self.p.sheets[1]
        self.v.show_sheet(s2.id)
        self.insert("Relay coil", (4.0, 5.0))
        second = self.insert("Relay coil", (4.0, 7.0))
        self.v.show_sheet(s1.id)
        self.v.run(C.InsertCmd, self.lib.get("symbol", "Contact NO"), {})
        type_in(self.v, "3.0,3.0")
        self.assertTrue(self.v.input_text("P"))
        self.v.show_sheet(s2.id)
        QApplication.processEvents()
        self.v.cmd.point(dict(second.pin_points())["A1"])
        for _i in range(3):
            QApplication.processEvents()
        c = s1.inserts()
        self.assertEqual(len(c), 1)
        self.assertEqual(c[0].attrs["PARENT"], second.attrs["DEV"])
        self.assertEqual(dict(c[0].pin_points())["1"], (3.0, 3.0))

    def test_saved_opened_exported_and_turned(self):
        coil = self.insert("Contactor coil", (3.0, 3.0))
        dev = self.v.sheet().entities[coil.id]
        b = self.box((2.0, 8.0), (6.0, 5.0), {"text": "NOTE", "device": dev})
        d = tempfile.mkdtemp()
        path = os.path.join(d, "t.kzcad")
        self.p.save(path)
        again = M.Project.load(path).sheets[0].entities[b.id]
        self.assertEqual(again.to_dict(), b.to_dict())
        dxf = os.path.join(d, "t.dxf")
        fileio.export_dxf(self.p, self.v.sheet(), dxf)
        import ezdxf
        doc = ezdxf.readfile(dxf)
        texts = {e.dxf.text for e in doc.modelspace().query("TEXT")}
        self.assertIn("NOTE", texts)
        self.assertIn(dev.attrs["TAG"], texts)
        r = b.rotated((0.0, 0.0), 90.0)
        self.assertEqual([tuple(round(c, 9) for c in q) for q in r.points],
                         [(-8.0, 2.0), (-8.0, 6.0), (-5.0, 6.0), (-5.0, 2.0)])
        m = b.mirrored((0.0, 0.0), (0.0, 1.0))
        self.assertEqual(sorted(q[0] for q in m.points), [-6.0, -6.0, -2.0, -2.0])

    def test_esc_while_picking_for_a_box_leaves_it_as_it_was(self):
        coil = self.insert("Contactor coil", (3.0, 3.0))
        dev = self.v.sheet().entities[coil.id]
        b = self.box((2.0, 8.0), (6.0, 5.0), {"text": "N", "device": dev})
        self.win.ask_dash_box = lambda box: {"text": "N", "device": None, "pick": True}
        self.win.edit_text(b)
        self.v.escape()
        for _i in range(3):
            QApplication.processEvents()
        self.assertEqual(self.v.sheet().entities[b.id].attrs, b.attrs)

    def test_double_click_edits_it(self):
        b = self.box((2.0, 8.0), (6.0, 5.0), {"text": "OLD", "device": None})
        self.win.ask_dash_box = lambda box: {"text": "NEW\nLINE", "device": None}
        self.win.edit_text(b)
        self.assertEqual(self.v.sheet().entities[b.id].text, "NEW\nLINE")

    def test_the_device_list(self):
        self.insert("Contactor coil", (3.0, 3.0))
        self.insert("Relay coil", (6.0, 3.0))
        self.insert("Contact NO", (9.0, 3.0))
        got = [e.attrs["TAG"] for _s, e in tags.device_choices(self.p)]
        self.assertEqual(len(got), 2)               # (devices only: not the contact)


if __name__ == "__main__":
    unittest.main()
