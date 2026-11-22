"""Wires on PLC input and output points numbered by the point's address (the owner, 0.21: "wire
numbers for wires connecting to a PLC input or output (not power) should have the option of
being numbered according to its I/O point"; chose the address as written: output slot 3 point 0
O:3/0, input slot 2 point 7 I:2/7). Project setting wire_numbers_io, off to start."""
import os
import tempfile
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import dupes
from kanzonascad import model as M
from kanzonascad import wirenums

LIST = """Slot,Catalog,Point,Address,Tag,Description
3,1734-OB8E,0,Local:3:O.Data.0,M101,CONVEYOR RUN
3,1734-OB8E,1,,M102,NO ADDRESS
"""


class IoWireNumbersTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p, self.s = self.v.project, self.v.sheet()
        self.lib = self.win.library

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def place(self, block, at, attrs):
        before = set(self.s.entities)
        self.v.run(C.InsertCmd, self.lib.get("symbol", block), attrs)
        type_in(self.v, at)
        self.v.cancel()
        return next(e for i, e in self.s.entities.items()
                    if i not in before and isinstance(e, M.Insert))

    def wire_to(self, mod, pin, run=2.0):
        """A wire from the module's pin out to a load (two pieces: a bend), its id."""
        q = dict(mod.pin_points())[pin]
        with self.p.edit("wire") as ed:
            w = ed.add(self.s, M.Wire([q, (q[0] - run, q[1]), (q[0] - run, q[1] + 0.25)]))
        return w.id

    def num(self, wid, sheet=None):
        return (sheet or self.s).entities[wid].num

    def set_io(self, on):
        with self.p.edit("settings") as ed:
            ed.project_settings({"wire_numbers_io": on})

    def test_off_by_default_numbers_as_ever(self):
        self.assertFalse(wirenums.by_io_address(self.p))
        mod = self.place("1734-OB8E module", "8,9", {"SLOT": "3"})
        w = self.wire_to(mod, "0")
        self.assertIsNotNone(wirenums.split(self.num(w)), self.num(w))

    def test_output_and_input_points_take_their_address(self):
        out = self.place("1734-OB8E module", "8,9", {"SLOT": "3"})
        inp = self.place("1734-IB8 module", "14,9", {"SLOT": "2"})
        w0 = self.wire_to(out, "0")
        w7 = self.wire_to(inp, "7")
        page = (self.num(w0), self.num(w7))
        self.set_io(True)
        self.assertEqual((self.num(w0), self.num(w7)), ("O:3/0", "I:2/7"))
        # (every wire of the group: the wire and the one joined to its end)
        q = self.s.entities[w0].points[-1]
        with self.p.edit("on") as ed:
            more = ed.add(self.s, M.Wire([q, (q[0], q[1] + 1.0)]))
        self.assertEqual(self.num(more.id), "O:3/0")
        self.assertFalse(self.s.entities[w0].num_lock)
        # the SLOT changed: the next numbering follows
        out = self.s.entities[out.id]
        with self.p.edit("slot") as ed:
            ed.change(self.s, out.copy(attrs=dict(out.attrs, SLOT="5")))
        self.assertEqual(self.num(w0), "O:5/0")
        # undo, redo
        self.p.undo()
        self.assertEqual(self.num(w0), "O:3/0")
        self.p.redo()
        self.assertEqual(self.num(w0), "O:5/0")
        # turned off: page numbers again
        self.set_io(False)
        for w in (w0, w7):
            self.assertIsNotNone(wirenums.split(self.num(w)), self.num(w))
        self.p.undo()
        self.assertEqual((self.num(w0), self.num(w7)), ("O:5/0", "I:2/7"))
        while self.p.undo_stack and self.p.settings.get("wire_numbers_io"):
            self.p.undo()
        self.assertEqual((self.num(w0), self.num(w7)), page)

    def test_power_terminals_keep_a_normal_number(self):
        mod = self.place("1734-OE4C module", "8,9", {"SLOT": "3"})
        wc = self.wire_to(mod, "4")         # (C)
        wv = self.wire_to(mod, "6")         # (V)
        wo = self.wire_to(mod, "1")         # (OUT 1)
        self.set_io(True)
        self.assertEqual(self.num(wo), "O:3/1")
        for w in (wc, wv):
            self.assertIsNotNone(wirenums.split(self.num(w)), self.num(w))

    def test_rtn_terminal_keeps_a_normal_number(self):
        mod = self.place("PLC analog input module, 4 channels IN/RTN", "8,9", {"SLOT": "6"})
        win = self.wire_to(mod, "4")        # (IN-1)
        rtn = self.wire_to(mod, "3")        # (RTN-1)
        self.set_io(True)
        self.assertEqual(self.num(win), "I:6/1")
        self.assertIsNotNone(wirenums.split(self.num(rtn)), self.num(rtn))

    def test_no_slot_no_address_numbers_as_ever(self):
        mod = self.place("1734-OB8E module", "8,9", {})
        w = self.wire_to(mod, "0")
        self.set_io(True)
        self.assertIsNotNone(wirenums.split(self.num(w)), self.num(w))

    def test_a_locked_number_stays(self):
        mod = self.place("1734-OB8E module", "8,9", {"SLOT": "3"})
        w = self.wire_to(mod, "0")
        with self.p.edit("typed") as ed:
            wirenums.set_number(ed, self.p, self.s, self.s.entities[w], "MY1", True)
        self.set_io(True)
        self.assertEqual(self.num(w), "MY1")

    def test_point_symbol_takes_its_addr(self):
        pt = self.place("PLC output", "8,9", {"ADDR": "O:4/2"})
        w = self.wire_to(pt, "OUT", run=-2.0)
        self.set_io(True)
        self.assertEqual(self.num(w), "O:4/2")

    def test_continued_piece_takes_its_modules_slot(self):
        mod = self.place("PLC digital output module, 16 points, points 0-7", "8,9",
                         {"SLOT": "7"})
        before = set(self.s.entities)
        self.v.run(C.InsertCmd, self.lib.get(
            "symbol", "PLC digital output module, points 8-15 continued"), {})
        type_in(self.v, "16,9")
        if self.v.cmd is not None:
            type_in(self.v, mod.attrs["TAG"])
        self.v.cancel()
        cont = next(e for i, e in self.s.entities.items()
                    if i not in before and isinstance(e, M.Insert))
        w = self.wire_to(cont, "9")
        self.set_io(True)
        self.assertEqual(self.num(w), "O:7/9")

    def test_two_wires_on_one_address_are_duplicates_not_joined(self):
        a = self.place("1734-OB8E module", "8,9", {"SLOT": "3"})
        b = self.place("1734-OB8E module", "14,9", {"SLOT": "3"})
        wa = self.wire_to(a, "0")
        wb = self.wire_to(b, "0")
        self.set_io(True)
        self.assertEqual((self.num(wa), self.num(wb)), ("O:3/0", "O:3/0"))
        _tags, nums = dupes.find(self.p)
        self.assertEqual(len(nums.get("O:3/0", ())), 2)
        gs, _dist = wirenums.groups(self.p)
        self.assertEqual(sum(1 for ws in gs.values()
                             if any(w.id in (wa, wb) for _s, w in ws)), 2)

    def test_every_wire_on_a_point_takes_its_address(self):
        # (two wires on one terminal are two groups, a pin joining none: both on IN 6, the
        # second kept a page number, the battery, seed 435)
        mod = self.place("1734-IB8 module", "8,9", {"SLOT": "2"})
        q = dict(mod.pin_points())["6"]
        with self.p.edit("wires") as ed:
            # (one through the terminal, as a wire drawn before a module was moved onto it,
            # one ending on it: the battery's seed 435)
            wa = ed.add(self.s, M.Wire([(q[0] + 1.0, q[1]), (q[0] - 3.0, q[1]),
                                        (q[0] - 3.0, q[1] - 0.5)])).id
            wb = ed.add(self.s, M.Wire([(q[0] - 2.5, q[1] + 2.5), (q[0] - 2.5, q[1] + 1.0),
                                        q])).id
        gs, _dist = wirenums.groups(self.p)
        self.assertEqual(sum(1 for ws in gs.values()
                             if any(w.id in (wa, wb) for _s, w in ws)), 2)   # (two groups)
        self.set_io(True)
        self.assertEqual((self.num(wa), self.num(wb)), ("I:2/6", "I:2/6"))
        self.set_io(False)
        self.assertNotIn("I:2/6", (self.num(wa), self.num(wb)))

    def test_imported_address_as_written_and_kept_on_save(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "io.csv")
        with open(path, "w", encoding="utf-8") as f:
            f.write(LIST)
        made = self.win.import_io_list(path)
        s = made[0]
        mod = next(e for e in s.inserts())
        self.assertEqual(mod.attrs.get("ADDR0"), "Local:3:O.Data.0")
        self.assertNotIn("ADDR1", mod.attrs)
        # (kept on the module, not shown on it)
        self.assertNotIn("ADDR0", [n for n, *_r in mod.attr_spots()])
        pins = dict(mod.pin_points())
        ws = {}
        with self.p.edit("wires") as ed:
            for pin in ("0", "1"):
                q = pins[pin]
                ws[pin] = ed.add(s, M.Wire([q, (q[0] - 3.0, q[1])])).id
        self.set_io(True)
        self.assertEqual(self.num(ws["0"], s), "Local:3:O.Data.0")
        self.assertEqual(self.num(ws["1"], s), "O:3/1")
        out = os.path.join(d, "io.kzcad")
        self.p.save(out, backups=0)
        q = M.Project.load(out)
        self.assertTrue(q.settings.get("wire_numbers_io"))
        qs = q.sheet_by_id(s.id)
        self.assertEqual(qs.entities[ws["0"]].num, "Local:3:O.Data.0")
        self.assertEqual(qs.entities[mod.id].attrs.get("ADDR0"), "Local:3:O.Data.0")


if __name__ == "__main__":
    unittest.main()
