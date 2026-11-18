"""The owner, 0.18, with a photo of a sheet whose 3-phase bus runs right along the top row of
motor branches, down the right side and back left along the bottom row: "Can automatic wire
numbering track this? As it stands now, my sheet would get renumbered. 209 would be the far
left, and 216 would be the far right. Can it track my bus?" (asked: follow the bus; wire numbers
in the same order).

Numbering order "Along the wires" from a source (Numbering source): each branch off the bus in
the order its drop leaves it, the top row left to right and then the bottom row right to left;
a branch's wires numbered together, before the next branch's."""
import unittest

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import tags
from kanzonascad import wirenums


def placed(p, s, d, want_y_above=True):
    """A 3-pole symbol turned so its L1-L3 are in a row across, left to right, above T1-T3."""
    for ang in (0.0, 90.0, 180.0, 270.0):
        for mir in (False, True):
            e = M.Insert(d.name, (0.0, 0.0), ang, 1.0, mir, defn=p.blocks[d.name])
            q = dict(e.pin_points())
            ls = [q["L1"], q["L2"], q["L3"]]
            if len({round(a[1], 6) for a in ls}) == 1 and ls[0][0] < ls[1][0] < ls[2][0] \
                    and q["T1"][1] < q["L1"][1]:
                return e
    raise AssertionError("no turn puts %s's poles across" % d.name)


class NumberAlongWiresTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        self.p, self.s = v.project, v.sheet()
        p, s, lib = self.p, self.s, self.win.library
        ds = lib.get("symbol", "Disconnect 3-pole")
        cb = lib.get("symbol", "Circuit breaker 3-pole")
        with p.edit("x") as ed:
            for d in (ds, cb):
                ed.block(d)
            self.ds = ed.add(s, M.Insert(ds.name, (1.0, 9.0), defn=p.blocks[ds.name]))
            src = sorted((q for n, q in self.ds.pin_points() if n.startswith("T")),
                         key=lambda q: -q[1])                 # (T1 at the top)
            # the bus: phase i along the top at y 10, 9.5, 9, down at x 15.5, 15, 14.5, back
            # along the bottom at y 4, 4.5, 5 (the outer phase outside all round)
            for i, q in enumerate(src):
                yt, xr, yb = 10.0 - 0.5 * i, 15.5 - 0.5 * i, 4.0 + 0.5 * i
                ed.add(s, M.Wire([q, (q[0] + 0.5, q[1]), (q[0] + 0.5, yt), (xr, yt),
                                  (xr, yb), (2.0, yb)]))
            self.cbs = []
            for row, xs, yb_of in (("top", (3.5, 7.0, 10.5), lambda i: 10.0 - 0.5 * i),
                                   ("bottom", (3.5, 7.0, 10.5), lambda i: 4.0 + 0.5 * i)):
                for x in xs:
                    e = placed(p, s, cb)
                    q = dict(e.pin_points())
                    y_pin = 7.0 if row == "top" else 1.5
                    e = e.moved(x - q["L1"][0], y_pin - q["L1"][1])
                    e = ed.add(s, e.copy(attrs={"TAG": "CB?", "DEV": "d%s%d" % (row, x)}))
                    q = dict(e.pin_points())
                    for i in range(3):
                        lq = q["L%d" % (i + 1)]
                        ed.add(s, M.Wire([(lq[0], yb_of(i)), lq]))      # (a drop)
                        tq = q["T%d" % (i + 1)]
                        ed.add(s, M.Wire([tq, (tq[0], tq[1] - 1.0)]))   # (on to the load)
                    self.cbs.append((row, x, e.id))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def order_along(self):
        with self.p.edit("order") as ed:
            ed.sheet_meta(self.s, number_order="wires", number_from=self.ds.id)
            n = tags.renumber_sheet(ed, self.p, self.s)
            wirenums.sync(ed, self.p, renumber=self.s)
        return n

    def test_tags_follow_the_bus(self):
        self.order_along()
        got = {(row, x): tags.split(self.s.entities[i].attrs["TAG"], "CB")[1]
               for row, x, i in self.cbs}
        # the top row left to right, then (round the right side) the bottom row right to left
        self.assertEqual([got[("top", x)] for x in (3.5, 7.0, 10.5)], [1, 2, 3])
        self.assertEqual([got[("bottom", x)] for x in (10.5, 7.0, 3.5)], [4, 5, 6])

    def test_a_branchs_wires_come_together(self):
        # (a drop off the bus is the bus's conductor, with its number: a branch's own wires
        # are those out of its breaker)
        self.order_along()
        s = self.s
        counts = {}
        for row, x, i in self.cbs:
            e = s.entities[i]
            q = dict(e.pin_points())
            nums = [wirenums.split(w.num)[1] for w in s.wires()
                    for n in ("T1", "T2", "T3") if w.touches(q[n])
                    and w.num]
            counts[(row, x)] = (min(nums), max(nums))
        order = [("top", 3.5), ("top", 7.0), ("top", 10.5),
                 ("bottom", 10.5), ("bottom", 7.0), ("bottom", 3.5)]
        for a, b in zip(order, order[1:]):
            self.assertLess(counts[a][1], counts[b][0], (a, counts[a], b, counts[b]))

    def t_counts(self):
        s = self.s
        out = {}
        for row, x, i in self.cbs:
            q = dict(s.entities[i].pin_points())
            out[(row, x)] = min(wirenums.split(w.num)[1] for w in s.wires()
                                for n in ("T1", "T2", "T3") if w.touches(q[n]) and w.num)
        return out

    def test_wire_order_a_project_and_a_sheet_setting(self):
        # (the owner, 0.18: "for wire numberings following the same order as tags, it should
        # be both a sheet and project setting")
        with self.p.edit("off") as ed:
            ed.project_settings({"wire_order_tags": False})
        self.order_along()
        got = self.t_counts()
        # the tags still along the bus...
        tag = tags.split(self.s.entities[self.cbs[3][2]].attrs["TAG"], "CB")[1]
        self.assertEqual(tag, 6)                    # (bottom row, left: the last along it)
        # ...the wires across and down: the bottom row left to right
        bottom = [got[("bottom", x)] for x in (3.5, 7.0, 10.5)]
        self.assertEqual(bottom, sorted(bottom))
        # the sheet says otherwise: along the bus again (right to left at the bottom)
        with self.p.edit("sheet") as ed:
            ed.sheet_meta(self.s, wire_order_tags=True)
            wirenums.sync(ed, self.p, renumber=self.s)
        got = self.t_counts()
        bottom = [got[("bottom", x)] for x in (10.5, 7.0, 3.5)]
        self.assertEqual(bottom, sorted(bottom))
        # saved and opened
        q = M.Project.from_dict(self.p.to_dict())
        self.assertIs(q.sheets[0].wire_order_tags, True)
        self.assertIs(q.settings["wire_order_tags"], False)

    def test_without_a_source_as_before(self):
        with self.p.edit("order") as ed:
            ed.sheet_meta(self.s, number_order="wires", number_from=None)
            tags.renumber_sheet(ed, self.p, self.s)
        got = {(row, x): tags.split(self.s.entities[i].attrs["TAG"], "CB")[1]
               for row, x, i in self.cbs}
        self.assertEqual([got[("bottom", x)] for x in (3.5, 7.0, 10.5)], [4, 5, 6])


class NumberSourceCommandTest(unittest.TestCase):
    def test_click_the_source(self):
        from kanzonascad import commands as C
        win, v = window()
        try:
            p, s = v.project, v.sheet()
            d = win.library.get("symbol", "Disconnect 3-pole")
            with p.edit("x") as ed:
                ed.block(d)
                e = ed.add(s, M.Insert(d.name, (5.0, 5.0), defn=p.blocks[d.name]))
            v.center, v.scale = (5.0, 5.0), 100.0
            v.run(C.NumberSourceCmd)
            v.cmd.pick((5.0, 5.0))
            self.assertIsNone(v.cmd)
            self.assertEqual((s.number_order, s.number_from), ("wires", e.id))
            # saved and opened
            q = M.Project.from_dict(p.to_dict()).sheets[0]
            self.assertEqual((q.number_order, q.number_from), ("wires", e.id))
            p.undo()
            self.assertEqual(s.number_order, "across")
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()


if __name__ == "__main__":
    unittest.main()
