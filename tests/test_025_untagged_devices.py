"""A device with no tag (the long battery, 0.25, seed 4913: "a footprint's tag isn't its
device's", then "footprint shows , its device is None"): a symbol made with Make block was
placed with no tag and no hidden id; its tag locked (Lock numbers), then copied, the copy got
a hidden id but, locked, no tag; a footprint linked to it showed an empty tag for a device
with none. Make block now tags the copy it places as Insert does, and a copy of a device
locked with no tag gets one."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import tags


class UntaggedDevicesTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p, self.s = self.v.project, self.v.sheet()

    def tearDown(self):
        for name in ("Untagged coil",):
            self.win.library.delete_block("symbol", name)
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_make_block_tags_the_device_it_places(self):
        with self.p.edit("draw") as ed:
            a = ed.add(self.s, M.Circle((5, 5), 0.125))
            b = ed.add(self.s, M.Line((4.75, 5), (4.875, 5)))
        self.v.set_selection({a.id, b.id})
        self.win.ask_block_details = lambda ents: {
            "kind": "symbol", "name": "Untagged coil", "category": "", "description": "",
            "role": "device", "contact": "", "prefix": "CR", "pin_names": ["A1", "A2"],
            "replace": True}
        self.v.run(C.MakeBlockCmd)
        type_in(self.v, "5,5", "4.75,5", "5.25,5", "", "5,5.25")
        ins = self.s.inserts()[0]
        self.assertEqual(ins.attrs.get("TAG"), "CR101")
        self.assertTrue(ins.attrs.get("DEV"))
        self.assertIn(ins.attrs["DEV"], tags.devices(self.p))

    def test_copy_of_a_device_locked_with_no_tag_gets_one(self):
        d = M.BlockDef("Untagged coil", "symbol", [M.Circle((0, 0), 0.125)],
                       pins=[{"name": "A1", "pos": (-0.25, 0)}], role="device", prefix="CR")
        with self.p.edit("place") as ed:
            ed.block(d)
            e = ed.add(self.s, M.Insert(d.name, (5, 5), defn=self.p.blocks[d.name],
                                        attrs={"TAG_LOCK": "1"}))
        got = tags.retag_copies(self.p, self.s, [e.copy()])[0]
        self.assertEqual(got.attrs.get("TAG"), "CR101")
        self.assertTrue(got.attrs.get("DEV"))
        # a locked tag is still kept as typed
        with self.p.edit("tag") as ed:
            ed.change(self.s, e.copy(attrs={"TAG_LOCK": "1", "TAG": "K7"}))
        got = tags.retag_copies(self.p, self.s, [self.s.entities[e.id].copy()])[0]
        self.assertEqual(got.attrs.get("TAG"), "K7")
        # a footprint linked to the copy shows its tag
        with self.p.edit("copy") as ed:
            c = ed.add(self.s, tags.retag_copies(
                self.p, self.s, [self.s.entities[e.id].copy(attrs={"TAG_LOCK": "1"})])[0])
        fp = tags.link_footprint({}, c)
        self.assertEqual(fp["TAG"], c.attrs["TAG"])
        self.assertTrue(fp["TAG"])


if __name__ == "__main__":
    unittest.main()
