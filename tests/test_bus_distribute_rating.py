"""The owner's list of Nov 16:
- "how do I put in my fuse ratings?": a Rating attribute on the protection and power symbols,
  shown under the symbol once typed, at one height for each kind; the bill of materials tells
  ratings apart.
- "When adding wire bus... it needs to grab the connection locations from the symbol I'm
  connecting to": a bus started on a symbol's pin takes that side's pins (how many, how far
  apart), the others landing on their pins whichever way it heads.
- "I need the wires to not only be able to turn but also be able to be straight": S.
- "I also need to be able to set the layers for a bus (brown orange yellow or just black)": L.
- "I need to be able to distribute objects as well, both vertically and horizontally"."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import bom
from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import symbols_jic as J


class Base(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.lib = self.win.library
        self.p = self.v.project
        self.s = self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def insert(self, name, at, attrs=None):
        before = set(self.s.entities)
        self.v.run(C.InsertCmd, self.lib.get("symbol", name), attrs or {})
        type_in(self.v, "%r,%r" % at)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        return [e for i, e in self.s.entities.items() if i not in before and
                isinstance(e, M.Insert)][0]

    def bus(self, *inputs):
        before = set(self.s.entities)
        self.v.run(C.BusCmd)
        for t in inputs:
            self.assertTrue(self.v.input_text(t), t)
        if self.v.cmd is not None:
            self.v.cmd.enter()
        return [e for i, e in self.s.entities.items() if i not in before and
                isinstance(e, M.Wire)]

    def ends(self, ws):
        return {(tuple(w.points[0]), tuple(w.points[-1])) for w in ws}


class RatingTest(Base):
    def test_shown_under_the_symbol_once_typed(self):
        e = self.insert("Fuses 3-pole", (3.0, 6.0))
        texts = [t.text for t in e.world_entities() if isinstance(t, M.Text)]
        self.assertNotIn("30A", texts)
        with self.p.edit("rating") as ed:
            ed.change(self.s, e.copy(attrs=dict(e.attrs, RATING="30A")))
        e = self.s.entities[e.id]
        got = [t for t in e.world_entities() if isinstance(t, M.Text) and t.text == "30A"]
        self.assertEqual(len(got), 1)
        body_bottom = e.pos[1] + min(q.bbox()[1] for q in e.defn.entities)
        self.assertLess(got[0].bbox()[3], body_bottom)          # (under its poles)

    def test_ratings_line_up_and_the_symbols_have_one(self):
        rated = ["Fuse", "Circuit breaker 1-pole", "Disconnect 1-pole", "Overload heater"]
        for n in rated + ["Fuses 3-pole", "Circuit breaker 3-pole", "Disconnect 3-pole",
                          "Overload heaters 3-pole", "Motor 3-phase", "Motor",
                          "Control transformer", "Variable frequency drive",
                          "Power supply AC/DC"]:
            self.assertIn("RATING", [a["attr"] for a in self.lib.get("symbol", n).attr_texts],
                          n)
        ys = {[a for a in self.lib.get("symbol", n).attr_texts if a["attr"] == "RATING"][0][
            "pos"][1] for n in rated}
        self.assertEqual(ys, {J.RATING_Y})

    def test_the_bill_of_materials_tells_ratings_apart(self):
        for at, r in (((2.0, 2.0), "30A"), ((4.0, 2.0), "30A"), ((6.0, 2.0), "10A")):
            e = self.insert("Fuse", at)
            with self.p.edit("rating") as ed:
                ed.change(self.s, e.copy(attrs=dict(e.attrs, RATING=r)))
        rows = [r for r in bom.rows(self.p) if r["kind"] == "part"]
        got = sorted((r["qty"], r["desc"]) for r in rows)
        self.assertEqual(got, [(1, "Fuse, 10A"), (2, "Fuse, 30A")])

    def test_the_attributes_window_has_it(self):
        from PySide6.QtWidgets import QDialog, QLineEdit
        from kanzonascad.library_panel import attributes_dialog
        e = self.insert("Fuse", (2.0, 2.0))
        seen = {}

        def answer(dlg):
            for w in dlg.findChildren(QLineEdit):
                if w.placeholderText().startswith("30A"):
                    w.setText("15A")
                    seen["rating"] = True
            return QDialog.Accepted
        saved = QDialog.exec
        QDialog.exec = answer
        try:
            attrs = attributes_dialog(self.win, self.lib, e, self.p, self.s)
        finally:
            QDialog.exec = saved
        self.assertTrue(seen.get("rating"))
        self.assertEqual(attrs.get("RATING"), "15A")


class BusTest(Base):
    def test_a_bus_from_a_disconnect_lands_on_the_fuses(self):
        ds = self.insert("Disconnect 3-pole", (3.0, 6.0))
        fu = self.insert("Fuses 3-pole", (6.0, 6.0))
        d, f = dict(ds.pin_points()), dict(fu.pin_points())
        # started on its middle pole, 5 wires and 1" asked for before: the symbol's 3, 1/2"
        self.v._bus_count, self.v._bus_spacing = 5, 1.0
        ws = self.bus("%r,%r" % d["T2"], "%r,%r" % f["L1"])
        self.assertEqual(self.ends(ws), {(d["T%d" % i], f["L%d" % i]) for i in (1, 2, 3)})

    def test_whichever_way_it_heads(self):
        ds = self.insert("Disconnect 3-pole", (5.0, 6.0))
        d = dict(ds.pin_points())
        ws = self.bus("%r,%r" % d["L3"], "1,6")                     # left, from L3
        self.assertEqual({w.points[0] for w in ws}, {d["L1"], d["L2"], d["L3"]})
        # down then across: the poles still each on their own wire
        ws = self.bus("%r,%r" % d["T1"], "8,3")
        starts = sorted(w.points[0] for w in ws)
        self.assertEqual(starts, sorted([d["T1"], d["T2"], d["T3"]]))
        self.assertEqual(len({tuple(map(tuple, w.points)) for w in ws}), 3)

    def test_a_contact_is_not_a_side(self):
        c = self.insert("Contact NO", (4.0, 4.0))
        self.assertIsNone(C.pin_side(self.s, dict(c.pin_points())["1"]))
        ds = self.insert("Disconnect 3-pole", (8.0, 6.0))
        got = C.pin_side(self.s, dict(ds.pin_points())["L2"])
        self.assertEqual((len(got[0]), got[1]), (3, 0.5))

    def test_straight_has_no_corner(self):
        ws = self.bus("S", "1,1", "5,1.3", "5,4")
        for w in ws:
            self.assertEqual(len(w.points), 3)          # straight across, then straight up
            self.assertTrue(all(abs(a[0] - b[0]) < 1e-9 or abs(a[1] - b[1]) < 1e-9
                                for a, b in zip(w.points, w.points[1:])))
        first = [w for w in ws if w.points[0] == (1.0, 1.0)][0]
        self.assertEqual(first.points[1], (5.0, 1.0))  # (the click straight across from 1,1)

    def test_count_and_spacing_by_hand(self):
        ws = self.bus("N", "4", "0.25", "1,8", "4,8")      # (N: how many, then how far apart)
        self.assertEqual(sorted(w.points[0][1] for w in ws), [7.25, 7.5, 7.75, 8.0])

    def test_layers(self):
        self.win.ask_bus_layers = lambda count, cur: [
            "WIRE BROWN", "WIRE ORANGE", "WIRE YELLOW"][:count]
        ws = self.bus("L", "1,8", "4,8")
        by_y = sorted(ws, key=lambda w: -w.points[0][1])
        self.assertEqual([w.layer for w in by_y], ["WIRE BROWN", "WIRE ORANGE", "WIRE YELLOW"])
        self.assertEqual(self.p.layers["WIRE BROWN"].color, C.WIRE_LAYER_COLORS["WIRE BROWN"])
        # remembered for the next bus; wires on any layer still join
        ws2 = self.bus("1,5", "4,5")
        self.assertEqual(sorted(w.layer for w in ws2),
                         ["WIRE BROWN", "WIRE ORANGE", "WIRE YELLOW"])
        from kanzonascad import wires
        self.assertTrue(wires.connects_at(self.s, (4.0, 8.0)))

    def test_the_layers_window_presets(self):
        from PySide6.QtWidgets import QComboBox, QDialog
        from kanzonascad import dialogs
        got = {}

        def answer(dlg):
            box = dlg.findChildren(QComboBox)[0]
            box.setCurrentIndex(box.findText("All black"))
            return QDialog.Accepted
        saved = QDialog.exec
        QDialog.exec = answer
        try:
            got["l"] = dialogs.bus_layers(self.win, self.p, 3, ["WIRES"])
        finally:
            QDialog.exec = saved
        self.assertEqual(got["l"], ["WIRE BLACK"] * 3)


class DistributeTest(Base):
    def lines(self, xs, w=0.5):
        with self.p.edit("lines") as ed:
            return [ed.add(self.s, M.Line((x, 1.0), (x + w, 1.0 + (i % 2)))).id
                    for i, x in enumerate(xs)]

    def run_it(self, ids, key):
        self.v.set_selection(set(ids))
        self.v.run(C.DistributeCmd)
        self.assertTrue(self.v.input_text(key))

    def test_horizontally_equal_gaps_ends_stay(self):
        ids = self.lines([1.0, 1.7, 2.1, 6.0])
        before = {i: self.s.entities[i].bbox() for i in ids}
        self.run_it(ids, "H")
        boxes = sorted((self.s.entities[i].bbox() for i in ids), key=lambda b: b[0])
        gaps = [b[0] - a[2] for a, b in zip(boxes, boxes[1:])]
        self.assertTrue(max(gaps) - min(gaps) < 1e-9, gaps)
        self.assertEqual(self.s.entities[ids[0]].bbox(), before[ids[0]])
        self.assertEqual(self.s.entities[ids[-1]].bbox(), before[ids[-1]])
        for i in ids:                                   # (only across)
            self.assertEqual(self.s.entities[i].bbox()[1], before[i][1])
        self.p.undo()
        self.assertEqual({i: self.s.entities[i].bbox() for i in ids}, before)

    def test_vertically(self):
        with self.p.edit("lines") as ed:
            ids = [ed.add(self.s, M.Line((1.0, y), (2.0, y + 0.25))).id
                   for y in (1.0, 1.4, 1.5, 5.0, 2.2)]
        self.run_it(ids, "V")
        boxes = sorted((self.s.entities[i].bbox() for i in ids), key=lambda b: b[1])
        gaps = [b[1] - a[3] for a, b in zip(boxes, boxes[1:])]
        self.assertTrue(max(gaps) - min(gaps) < 1e-9, gaps)

    def test_on_the_snap_grid_with_snap_on(self):
        self.v.snap_on = True
        k = self.v.snap_spacing
        ids = self.lines([1.0, 1.25, 1.375, 4.0])
        before = {i: self.s.entities[i].bbox()[0] for i in ids}
        self.run_it(ids, "H")
        for i in ids:
            d = self.s.entities[i].bbox()[0] - before[i]
            self.assertAlmostEqual(d / k, round(d / k), places=9)

    def test_symbols_take_their_wires(self):
        a = self.insert("Pilot light", (2.0, 4.0))
        b = self.insert("Pilot light", (2.0, 4.5))
        c = self.insert("Pilot light", (2.0, 8.0))
        with self.p.edit("wire") as ed:
            w = ed.add(self.s, M.Wire([(0.5, 4.5), (2.0, 4.5)]))
        self.run_it([a.id, b.id, c.id], "V")
        nb = self.s.entities[b.id]
        self.assertEqual(self.s.entities[w.id].points[-1], dict(nb.pin_points())["1"])

    def test_needs_three(self):
        ids = self.lines([1.0, 3.0])
        self.v.set_selection(set(ids))
        self.v.run(C.DistributeCmd)
        self.assertIsNone(self.v.cmd)


if __name__ == "__main__":
    unittest.main()
