import os
import tempfile
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import tags


def devices(view):
    return sorted((e for e in view.sheet().entities.values() if tags.is_device(e)),
                  key=lambda e: e.attrs["TAG"])


class TagTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = False
        lib = self.win.library
        self.coil = lib.get("symbol", "Relay coil")
        self.motor_coil = lib.get("symbol", "Contactor coil")
        self.contact = lib.get("symbol", "Contact NO")
        self.ground = lib.get("symbol", "Ground")
        with self.v.project.edit("page 6") as ed:
            ed.sheet_meta(self.v.sheet(), number="6")

    def tearDown(self):
        for i in range(self.win.tabs.count()):
            p = self.win.tabs.widget(i).project
            p.saved_at = len(p.undo_stack)
        self.win.close()

    def place(self, defn, at, attrs=None):
        self.v.run(C.InsertCmd, defn, attrs or {})
        type_in(self.v, "%g,%g" % at)
        return [e for e in self.v.sheet().entities.values() if isinstance(e, M.Insert)][-1]

    def tag_of(self, ins):
        return self.v.sheet().entities[ins.id].attrs.get("TAG")

    def test_new_devices_number_themselves_by_page(self):
        a = self.place(self.coil, (2, 8))
        b = self.place(self.coil, (2, 7))
        m = self.place(self.motor_coil, (2, 6))
        self.assertEqual([self.tag_of(x) for x in (a, b, m)], ["CR601", "CR602", "M601"])
        self.assertTrue(a.attrs.get("DEV"))
        self.assertNotEqual(a.attrs["DEV"], b.attrs["DEV"])
        # a contact takes its device's tag (asked for: Enter takes the nearest CR coil); a
        # symbol without a prefix gets no tag
        self.v.run(C.InsertCmd, self.contact, {})
        type_in(self.v, "5,8", "")
        got = [e for e in self.v.sheet().entities.values() if tags.is_child(e)][-1]
        self.assertEqual((got.attrs.get("TAG"), got.attrs.get("PARENT")),
                         ("CR601", a.attrs["DEV"]))
        self.assertEqual(self.place(self.ground, (5, 5)).attrs.get("TAG", ""), "")
        # deleting CR601 frees 01 for the next one
        with self.v.project.edit("del") as ed:
            ed.remove(self.v.sheet(), a.id)
        self.assertEqual(self.tag_of(self.place(self.coil, (2, 5))), "CR601")

    def test_copies_get_their_own_tag_and_id(self):
        a = self.place(self.coil, (2, 8))
        self.v.set_selection({a.id})
        self.v.run(C.CopyCmd)
        type_in(self.v, "0,0", "@2,0", "")
        ds = devices(self.v)
        self.assertEqual([d.attrs["TAG"] for d in ds], ["CR601", "CR602"])
        self.assertNotEqual(ds[0].attrs["DEV"], ds[1].attrs["DEV"])
        # pasted onto page 7: CR701
        self.v.set_selection({a.id})
        self.assertTrue(self.win.copy_clip())
        self.win.add_sheet()
        self.assertEqual(self.v.project.sheet_number(self.v.sheet()), "2")
        with self.v.project.edit("page 7") as ed:
            ed.sheet_meta(self.v.sheet(), number="7")
        self.win.paste()
        type_in(self.v, "3,3")
        self.assertEqual([d.attrs["TAG"] for d in devices(self.v)], ["CR701"])

    def test_tags_follow_their_page_number(self):
        a = self.place(self.coil, (2, 8))
        locked = self.place(self.coil, (2, 7), {"TAG": "CR699", "TAG_LOCK": "1"})
        with self.v.project.edit("page 9") as ed:
            ed.sheet_meta(self.v.sheet(), number="9")
        self.assertEqual(self.tag_of(a), "CR901")
        self.assertEqual(self.tag_of(locked), "CR699")         # locked: as typed
        self.v.project.undo()
        self.assertEqual(self.tag_of(a), "CR601")
        # moving sheets changes automatic page numbers: tags follow
        p = self.v.project
        with p.edit("number by position") as ed:
            ed.sheet_meta(p.sheets[0], number=None)
        with p.edit("new first sheet") as ed:
            ed.add_sheet(p.make_sheet("Front"), 0)
        self.assertEqual(p.sheet_number(self.v.sheet()), "2")
        self.assertEqual(self.tag_of(a), "CR201")

    def test_renumber_sheet_in_order_skipping_locked(self):
        v = self.v
        right = self.place(self.coil, (10, 9))       # zone row A, far right
        left = self.place(self.coil, (2, 9))         # row A, left
        low = self.place(self.coil, (2, 3))          # lower row, left
        keep = self.place(self.coil, (6, 6), {"TAG": "CR601", "TAG_LOCK": "1"})
        self.win.renumber_sheet()
        # across then down: left, right (row A), then low; 01 is locked, so 02, 03, 04
        self.assertEqual([self.tag_of(x) for x in (left, right, low, keep)],
                         ["CR602", "CR603", "CR604", "CR601"])
        with v.project.edit("order") as ed:
            ed.sheet_meta(v.sheet(), number_order="down")
        self.win.renumber_sheet()
        # down then across: left column first (left, low), then right
        self.assertEqual([self.tag_of(x) for x in (left, low, right)],
                         ["CR602", "CR603", "CR604"])
        v.project.undo()
        self.assertEqual(self.tag_of(low), "CR604")

    def test_untagged_devices_from_before_get_numbers(self):
        old = self.place(self.coil, (2, 8))
        with self.v.project.edit("as in 0.3") as ed:     # a device placed before tags existed
            ed.change(self.v.sheet(), old.copy(attrs={}))
        self.assertEqual(self.v.sheet().entities[old.id].tag_text().text, "CR?")
        self.win.renumber_sheet()
        self.assertEqual(self.tag_of(old), "CR601")
        self.assertTrue(self.v.sheet().entities[old.id].attrs.get("DEV"))


class LibraryDeleteTest(unittest.TestCase):
    def test_placed_blocks_survive_deleting_their_library_source(self):
        from kanzonascad.library import Library
        lib = Library(tempfile.mkdtemp())
        mine = M.BlockDef("My relay", "symbol", [M.Circle((0, 0), 0.2)],
                          [{"name": "A1", "pos": (-0.25, 0)}], (0, 0.3), prefix="CR",
                          role="parent")
        lib.save_block(mine)
        p = M.Project.new()
        with p.edit("insert") as ed:
            ed.block(lib.get("symbol", "My relay"))
            ed.add(p.sheets[0], M.Insert("My relay", (3, 3), defn=p.blocks["My relay"]))
        path = os.path.join(tempfile.mkdtemp(), "p.kzcad")
        p.save(path)
        self.assertTrue(lib.delete_block("symbol", "My relay"))
        self.assertIsNone(lib.get("symbol", "My relay"))
        q = M.Project.load(path)
        ins = list(q.sheets[0].entities.values())[0]
        self.assertIsNotNone(ins.defn)
        self.assertEqual(ins.defn.entities[0].radius, 0.2)
        self.assertEqual(ins.pin_points()[0][1], (2.75, 3.0))
