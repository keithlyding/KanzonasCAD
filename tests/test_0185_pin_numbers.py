"""A second wire on a pin (a double landing) asked how it is numbered, as a tap is, and
changeable later (the owner, 0.18.5: "my wires aren't labeled at all. They should have new
numbers"; asked: "Give me the option each time, and changeable")."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class PinNumberTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p, self.s = self.v.project, self.v.sheet()
        ds = self.win.library.get("symbol", "Disconnect 3-pole")
        with self.p.edit("x") as ed:
            ed.sheet_meta(self.s, number="2")
            ed.project_settings({"tap_numbers": "suffix"})
            ed.block(ds)
            ins = ed.add(self.s, M.Insert(ds.name, (10.0, 8.0), defn=self.p.blocks[ds.name]))
        self.pin = [q for _n, q in self.s.entities[ins.id].pin_points()][0]
        with self.p.edit("in") as ed:
            self.incoming = ed.add(self.s, M.Wire([(2.0, self.pin[1]), self.pin]))

    def tearDown(self):
        self.win.__dict__.pop("ask_wire_number", None)
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def drop(self, answer):
        a = self.pin
        self.v.run(C.WireCmd)
        type_in(self.v, "%r,%r" % a, "%r,%r" % (a[0] - 2, a[1] + 1),
                "%r,%r" % (a[0] - 2, 3.0))
        if self.v.cmd is not None and self.v.cmd.tapped is None:
            self.v.cmd.enter()
        self.assertIsNotNone(self.v.cmd)
        self.assertIn("Second wire on the pin", self.v._prompt[0])
        if answer:
            type_in(self.v, answer)
        else:
            self.v.enter()
        self.assertIsNone(self.v.cmd)
        return [w for w in self.s.wires() if w.id != self.incoming.id][0]

    def num(self, w):
        return self.s.entities[w.id].num

    def test_enter_numbers_it_off_the_wire(self):
        d = self.drop("")
        self.assertEqual(self.num(d), self.num(self.incoming) + "-1")

    def test_s_and_n(self):
        d = self.drop("S")
        self.assertEqual(self.num(d), self.num(self.incoming))
        self.p.undo()
        self.p.undo()
        d = self.drop("N")
        self.assertNotIn("-", self.num(d))
        self.assertNotEqual(self.num(d), self.num(self.incoming))

    def test_changeable_by_double_click(self):
        d = self.drop("S")
        asked = []

        def ask(num, tap_of=None, own="", locked=False):
            asked.append((tap_of, own))
            return num, "", locked
        self.win.ask_wire_number = ask
        self.win.edit_wire_number(self.s.entities[d.id])
        self.assertEqual(asked, [(self.num(self.incoming), "same")])
        self.assertEqual(self.num(d), self.num(self.incoming) + "-1")
        # (the wire already on the pin isn't offered it: its window has no Tapped off)
        asked.clear()
        self.win.edit_wire_number(self.s.entities[self.incoming.id])
        self.assertEqual(asked, [(None, "")])

    def test_saved(self):
        d = self.drop("")
        q = M.Project.from_dict(self.p.to_dict())
        self.assertTrue(q.sheets[0].entities[d.id].pin_tap)


if __name__ == "__main__":
    unittest.main()
