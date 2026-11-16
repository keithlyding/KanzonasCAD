"""Tags line up (the owner, with a photo of DS201 and FU201 at different heights: "my
attributes don't line up with each other between the two symbols"): the program's symbols put
their tags at one height above the wire for each kind (three-pole: TAG3_Y over L1; one-line:
TAG_Y), clear of the tallest drawing; Library > Update blocks from library... gives a project
that holds the old copies the library's, keeping the copies' tags, places and wires."""
import unittest

from PySide6.QtWidgets import QMessageBox

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import symbols_jic as J


class TagsLineUpTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.lib = self.win.library
        self.p = self.v.project
        # (a message box nobody answers would hang the run: answered here, and recorded)
        self.said = []
        self._info = QMessageBox.information
        QMessageBox.information = staticmethod(lambda *a, **k: self.said.append(a[2]))

    def tearDown(self):
        QMessageBox.information = self._info
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def insert(self, name, at):
        before = set(self.v.sheet().entities)
        self.v.run(C.InsertCmd, self.lib.get("symbol", name), {})
        type_in(self.v, "%r,%r" % at)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        return [e for i, e in self.v.sheet().entities.items()
                if i not in before and isinstance(e, M.Insert)][0]

    def chain(self, names, at):
        out, here = [], at
        for n in names:
            e = self.insert(n, here)
            out.append(e)
            here = e.pin_points()[len(e.pin_points()) // 2][1] if n.endswith("pole") \
                else e.pin_points()[-1][1]
            if n.endswith("pole"):
                here = dict(e.pin_points())["T1"]
        return out

    def test_three_pole_power_devices_in_a_row(self):
        row = self.chain(["Disconnect 3-pole", "Fuses 3-pole", "Contactor power contacts 3-pole",
                          "Overload heaters 3-pole", "Circuit breaker 3-pole"], (2.0, 8.0))
        ys = {round(e.tag_text().pos[1], 9) for e in row}
        self.assertEqual(len(ys), 1, ys)
        # clear of every one's drawing
        for e in row:
            top = e.pos[1] + max(q.bbox()[3] for q in e.defn.entities)   # (unturned)
            self.assertGreater(e.tag_text().pos[1], top)

    def test_one_line_symbols_on_a_rung(self):
        names = ["Pushbutton NC", "Pushbutton NO", "Contact NO", "Contact NC", "Emergency stop NC",
                 "Limit switch NO", "Overload contact NC", "Relay coil", "Pilot light", "Fuse"]
        row = self.chain(names, (1.0, 4.0))
        ys = {round(e.tag_text().pos[1], 9) for e in row}
        self.assertEqual(len(ys), 1, ys)
        for e in row:
            top = e.pos[1] + max(q.bbox()[3] for q in e.defn.entities)   # (unturned)
            self.assertGreater(e.tag_text().pos[1], top, e.block)

    def test_update_blocks_from_library(self):
        lib_ds = self.lib.get("symbol", "Disconnect 3-pole")
        ds = self.insert("Disconnect 3-pole", (2.0, 8.0))
        fu = self.insert("Fuses 3-pole", dict(ds.pin_points())["T1"])
        with self.p.edit("wire") as ed:
            w = ed.add(self.v.sheet(), M.Wire([(0.5, 8.0), (2.0, 8.0)]))
        # the project holds the copies as 0.15 drew them: tags at 0.72 and 0.64
        with self.p.edit("old copies") as ed:
            for name, y in (("Disconnect 3-pole", 0.72), ("Fuses 3-pole", 0.64)):
                d = M.BlockDef.from_dict(dict(self.p.blocks[name].to_dict(), tag_pos=[0.0, y]))
                ed.block(d)
        s = self.v.sheet()
        self.assertNotEqual(s.entities[ds.id].tag_text().pos[1],
                            s.entities[fu.id].tag_text().pos[1])
        tags = {e.id: e.attrs.get("TAG") for e in s.inserts()}
        places = {e.id: e.pos for e in s.inserts()}
        asked = []
        saved = QMessageBox.question
        QMessageBox.question = staticmethod(lambda *a, **k: asked.append(a[2]) or
                                            QMessageBox.Yes)
        try:
            self.assertEqual(self.win.update_blocks_from_library(), 2)
        finally:
            QMessageBox.question = saved
        self.assertIn("Disconnect 3-pole", asked[0])
        self.assertTrue(self.p.blocks["Disconnect 3-pole"].same_as(lib_ds))
        self.assertEqual(s.entities[ds.id].tag_text().pos[1], s.entities[fu.id].tag_text().pos[1])
        self.assertEqual(s.entities[ds.id].tag_text().pos[1], 8.0 - 0.5 + J.TAG3_Y)
        self.assertEqual({e.id: e.attrs.get("TAG") for e in s.inserts()}, tags)
        self.assertEqual({e.id: e.pos for e in s.inserts()}, places)
        self.assertEqual(s.entities[w.id].points[-1], dict(ds.pin_points())["L1"])
        # one step back
        self.p.undo()
        self.assertFalse(self.p.blocks["Disconnect 3-pole"].same_as(lib_ds))
        self.p.redo()
        # nothing left to update
        self.assertEqual(self.win.update_blocks_from_library(), 0)
        self.assertIn("same as the library", self.said[-1])


if __name__ == "__main__":
    unittest.main()
