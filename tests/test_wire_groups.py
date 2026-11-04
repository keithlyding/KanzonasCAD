import random
import unittest

from kanzonascad import model as M
from kanzonascad import wirenums, wires, crossings


def partition(groups):
    by = {}
    for i, r in groups.items():
        by.setdefault(r, set()).add(i)
    return sorted(sorted(g) for g in by.values())


def fresh_dots_and_crossings(sheet):
    saved = (sheet._junctions, sheet._junction_state, sheet._crossings, sheet._crossing_state)
    sheet._junctions = sheet._junction_state = sheet._crossings = sheet._crossing_state = None
    got = (wires.junctions(sheet), sorted(crossings.found(sheet)))
    (sheet._junctions, sheet._junction_state, sheet._crossings,
     sheet._crossing_state) = saved
    return got


def fresh(sheet):
    saved = sheet._wire_groups, getattr(sheet, "_wire_adj", None)
    sheet._wire_groups = sheet._wire_adj = None
    got = partition(wirenums._sheet_groups(sheet))
    sheet._wire_groups, sheet._wire_adj = saved
    return got


class WireGroupsTest(unittest.TestCase):
    def test_kept_up_to_date_matches_a_fresh_count(self):
        rnd = random.Random(7)
        p = M.Project.new()
        s = p.sheets[0]
        for step in range(400):
            ws = s.wires()
            with p.edit("step") as ed:
                r = rnd.random()
                if r < 0.5 or not ws:
                    a = (rnd.randint(0, 20) * 0.5, rnd.randint(0, 10) * 0.5)
                    b = (a[0], rnd.randint(0, 10) * 0.5) if rnd.random() < 0.5 else \
                        (rnd.randint(0, 20) * 0.5, a[1])
                    if a != b:
                        ed.add(s, M.Wire([a, b]))
                elif r < 0.7:
                    ed.remove(s, rnd.choice(ws).id)
                else:
                    w = rnd.choice(ws)
                    ed.change(s, w.moved(rnd.choice([-0.5, 0, 0.5]), rnd.choice([-0.5, 0.5])))
            if rnd.random() < 0.1:
                p.undo()
            self.assertEqual(partition(wirenums._sheet_groups(s)), fresh(s), "step %d" % step)
            kept = (wires.junctions(s), sorted(crossings.found(s)))
            self.assertEqual(kept, fresh_dots_and_crossings(s), "step %d" % step)

    def test_t_and_corner_connections(self):
        p = M.Project.new()
        s = p.sheets[0]
        with p.edit("w") as ed:
            a = ed.add(s, M.Wire([(0, 0), (4, 0)]))
            b = ed.add(s, M.Wire([(2, 0), (2, 3)]))          # T onto a's middle
            c = ed.add(s, M.Wire([(5, 5), (7, 5), (7, 8)]))
            d = ed.add(s, M.Wire([(7, 5), (9, 5)]))          # ends on c's corner
            e = ed.add(s, M.Wire([(1, 1), (1, -1)]))         # crosses a: not connected
        g = wirenums._sheet_groups(s)
        self.assertEqual(g[a.id], g[b.id])
        self.assertEqual(g[c.id], g[d.id])
        self.assertNotEqual(g[a.id], g[e.id])
        self.assertNotEqual(g[a.id], g[c.id])


if __name__ == "__main__":
    unittest.main()
