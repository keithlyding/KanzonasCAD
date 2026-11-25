"""Join (the owner, 0.26: "Unite / join lines", AutoCAD's JOIN, alias J): lines, arcs and
polylines that touch end to end become one object (lines in a line one line, arcs of one
circle one arc, other chains one polyline), in one step of Undo; what can't be joined (gaps,
overlaps, branches, an arc on a line, wires) is said on the command line and left as it is."""
import os
import tempfile
import unittest

from tests.util import APP, window

from kanzonascad import commands as C
from kanzonascad import join as J
from kanzonascad import model as M


def numbered(ents):
    for i, e in enumerate(ents):
        e.id = i + 1
    return ents


def joined(ents):
    made, notes = J.plan(numbered(ents))
    return [(e, sorted(old)) for e, old in made], notes


class PlanTest(unittest.TestCase):
    def test_lines_in_a_line_become_one_line(self):
        for a, b in ((((0, 0), (1, 0)), ((1, 0), (3, 0))), (((1, 0), (0, 0)), ((3, 0), (1, 0))),
                     (((1, 0), (0, 0)), ((1, 0), (3, 0))), (((0, 0), (1, 1)), ((2, 2), (1, 1)))):
            made, notes = joined([M.Line(*a), M.Line(*b)])
            self.assertEqual(len(made), 1, (a, b))
            e, old = made[0]
            self.assertIsInstance(e, M.Line)
            self.assertEqual(old, [1, 2])
            self.assertEqual(sorted([e.p1, e.p2]), _far_ends(a, b))
            self.assertEqual(notes, [])

    def test_a_chain_becomes_one_polyline_without_corners_where_it_runs_on(self):
        made, notes = joined([M.Line((0, 0), (1, 0)), M.Line((1, 0), (2, 0)),
                              M.Line((2, 1), (2, 0)), M.Polyline([(2, 1), (3, 1), (3, 3)])])
        self.assertEqual(notes, [])
        (e, old), = made
        self.assertEqual(old, [1, 2, 3, 4])
        self.assertIsInstance(e, M.Polyline)
        self.assertFalse(e.closed)
        self.assertIn(e.points, ([(0, 0), (2, 0), (2, 1), (3, 1), (3, 3)],
                                 [(3, 3), (3, 1), (2, 1), (2, 0), (0, 0)]))

    def test_a_closed_chain_becomes_a_closed_polyline(self):
        made, _notes = joined([M.Line((0, 0), (1, 0)), M.Line((1, 0), (1, 1)),
                               M.Line((1, 1), (0, 1)), M.Line((0, 1), (0, 0))])
        (e, old), = made
        self.assertTrue(e.closed)
        self.assertEqual(len(e.points), 4)
        self.assertEqual(sorted(e.points), [(0, 0), (0, 1), (1, 0), (1, 1)])

    def test_arcs_of_one_circle(self):
        made, _notes = joined([M.Arc((0, 0), 1, 0, 90), M.Arc((0, 0), 1, 90, 200)])
        (e, _old), = made
        self.assertIsInstance(e, M.Arc)
        self.assertEqual((e.start, e.end), (0.0, 200.0))
        made, _notes = joined([M.Arc((0, 0), 1, 90, 200), M.Arc((0, 0), 1, 200, 90)])
        self.assertIsInstance(made[0][0], M.Circle)
        # (another circle, or the same radius about another center: not joined)
        made, _notes = joined([M.Arc((0, 0), 1, 0, 90), M.Arc((0, 2), 1, 270, 0)])
        self.assertEqual(made, [])

    def test_what_must_not_join(self):
        cases = {
            "gap": [M.Line((0, 0), (1, 0)), M.Line((1.001, 0), (2, 0))],
            "overlap": [M.Line((0, 0), (2, 0)), M.Line((1, 0), (3, 0))],
            "fold": [M.Line((0, 0), (2, 0)), M.Line((2, 0), (1, 0))],
            "branch": [M.Line((0, 0), (1, 0)), M.Line((1, 0), (2, 0)), M.Line((1, 0), (1, 1))],
            "arc": [M.Arc((0, 0), 1, 0, 90), M.Line((1, 0), (2, 0))],
            "wire": [M.Wire([(0, 0), (1, 0)]), M.Wire([(1, 0), (2, 0)])],
            "other": [M.Circle((0, 0), 1), M.Text((0, 0), "X", 0.1)],
        }
        for what, ents in cases.items():
            made, notes = joined(ents)
            self.assertEqual(made, [], what)
            self.assertEqual(len(notes), 1, (what, notes))
            word = {"gap": "gap", "overlap": "overlap", "fold": "overlap", "branch": "branch", "arc": "arc",
                    "wire": "wire", "other": "left out"}[what]
            self.assertIn(word, notes[0], (what, notes))
        # (two arcs of one circle lying over each other)
        made, notes = joined([M.Arc((0, 0), 1, 0, 90), M.Arc((0, 0), 1, 45, 0)])
        self.assertEqual(made, [])

    def test_a_gap_is_said_with_its_size_and_place(self):
        _made, notes = joined([M.Line((0, 0), (1, 0)), M.Line((1.004, 0), (2, 0))])
        self.assertIn('0.0040"', notes[0])
        self.assertIn('1.000",0.000"', notes[0])
        # far apart is no gap: nothing said
        _made, notes = joined([M.Line((0, 0), (1, 0)), M.Line((3, 0), (4, 0))])
        self.assertEqual(notes, [])

    def test_the_first_drawn_gives_its_layer_and_color(self):
        a = M.Line((1, 0), (2, 0), layer="B", color="#ff0000")
        b = M.Line((0, 0), (1, 0), layer="A")
        b.id, a.id = 1, 2
        (e, _old), = J.plan([a, b])[0]
        self.assertEqual((e.layer, e.color), ("A", None))

    def test_thousands_at_once(self):
        import time
        ents = []
        for i in range(500):
            y = i * 0.5
            ents += [M.Line((0, y), (1, y)), M.Line((1, y), (2, y)), M.Line((2, y), (2, y + .25)),
                     M.Polyline([(2, y + .25), (3, y + .25), (3, y + .4)])]
        t = time.perf_counter()
        made, notes = joined(ents)
        took = time.perf_counter() - t
        self.assertEqual(len(made), 500)
        self.assertEqual(notes, [])
        self.assertLess(took, 2.0)


def _far_ends(a, b):
    """The two ends of two lines that touch end to end that aren't the shared one."""
    ends = [a[0], a[1], b[0], b[1]]
    return sorted(q for q in ends if ends.count(q) == 1)


def _by_id(d):
    return {e["id"]: e for sh in d["sheets"] for e in sh["entities"]}


class CommandTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()
        self.msgs = []
        self.v.messaged.connect(self.msgs.append)

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_joins_in_one_step_and_says_what_it_did(self):
        with self.p.edit("draw") as ed:
            a = ed.add(self.s, M.Line((0, 0), (1, 0)))
            b = ed.add(self.s, M.Line((1, 0), (2, 0)))
            c = ed.add(self.s, M.Line((2, 0), (2, 1)))
            d = ed.add(self.s, M.Line((5, 5), (6, 5)))
            e = ed.add(self.s, M.Line((6.002, 5), (7, 5)))
            far = ed.add(self.s, M.Line((9, 9), (9, 8)))
        before = self.p.to_dict()
        self.v.set_selection({a.id, b.id, c.id, d.id, e.id})
        n = len(self.p.undo_stack)
        self.assertIs(C.lookup("J"), C.JoinCmd)
        self.v.run(C.JoinCmd)
        self.assertEqual(len(self.p.undo_stack), n + 1)
        self.assertEqual(self.p.undo_stack[-1].name, "Join")
        got = [x for x in self.s.entities.values() if isinstance(x, M.Polyline)]
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].points, [(0, 0), (2, 0), (2, 1)])
        self.assertEqual(self.v.sel, {got[0].id})
        for i in (d.id, e.id, far.id):
            self.assertIn(i, self.s.entities)
        self.assertIn("Joined 3 objects into 1: 1 polyline", self.msgs)
        self.assertTrue(any("1 gap" in m for m in self.msgs), self.msgs)
        self.p.undo()
        self.assertEqual(_by_id(self.p.to_dict()), _by_id(before))
        self.p.redo()
        self.assertEqual(len(self.s.entities), 4)

    def test_asks_for_objects_when_none_selected(self):
        with self.p.edit("draw") as ed:
            a = ed.add(self.s, M.Line((0, 0), (1, 0)))
            b = ed.add(self.s, M.Line((1, 0), (3, 0)))
        self.v.run(C.JoinCmd)
        self.assertTrue(self.v.cmd.selecting())
        self.v.set_selection({a.id, b.id})
        self.v.enter()
        self.assertIsNone(self.v.cmd)
        (e,) = self.s.entities.values()
        self.assertEqual((e.p1, e.p2), ((0, 0), (3, 0)))

    def test_nothing_to_join_says_so(self):
        with self.p.edit("draw") as ed:
            w = ed.add(self.s, M.Wire([(0, 0), (1, 0)]))
        self.v.set_selection({w.id})
        self.v.run(C.JoinCmd)
        self.assertIn("Nothing joined", self.msgs)
        self.assertTrue(any("Clean up wires" in m for m in self.msgs))
        self.assertIn(w.id, self.s.entities)

    def test_saved_and_opened(self):
        with self.p.edit("draw") as ed:
            a = ed.add(self.s, M.Arc((0, 0), 1, 0, 90))
            b = ed.add(self.s, M.Arc((0, 0), 1, 90, 180))
        self.v.set_selection({a.id, b.id})
        self.v.run(C.JoinCmd)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "j.kzcad")
            self.p.save(path, backups=0)
            q = M.Project.load(path)
        (e,) = q.sheets[0].entities.values()
        self.assertEqual((e.kind, e.start, e.end), ("arc", 0.0, 180.0))

    def test_on_the_modify_menu_and_home_tab(self):
        a = self.win.acts["join"]
        mod = [m for m in self.win.menuBar().actions() if m.text() == "&Modify"][0].menu()
        self.assertIn(a, mod.actions())
        self.assertIn("JOIN", a.toolTip())
        self.assertIn("J", a.toolTip())


if __name__ == "__main__":
    unittest.main()
