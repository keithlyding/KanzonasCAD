import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wires


def wires_of(view):
    return sorted((e for e in view.sheet().entities.values() if isinstance(e, M.Wire)),
                  key=lambda w: (w.points[0][0], w.points[0][1]))


class WireModelTest(unittest.TestCase):
    def test_end_moved_keeps_wires_square(self):
        w = M.Wire([(0, 0), (2, 0)])
        self.assertEqual(w.end_moved(-1, (3, 0)).points, [(0, 0), (3, 0)])
        jog = w.end_moved(-1, (2, 1)).points
        self.assertEqual(jog, [(0, 0), (1, 0), (1, 1), (2, 1)])
        l_shape = M.Wire([(0, 0), (2, 0), (2, 2)])
        self.assertEqual(l_shape.end_moved(0, (0, 0.5)).points, [(0, 0.5), (2, 0.5), (2, 2)])
        self.assertEqual(w.layer, "WIRES")

    def test_junction_dots(self):
        p = M.Project.new()
        s = p.sheets[0]
        with p.edit("w") as ed:
            ed.add(s, M.Wire([(1, 1), (5, 1)]))
            ed.add(s, M.Wire([(3, 1), (3, 3)]))           # a T onto the middle
            ed.add(s, M.Wire([(5, 1), (6, 1)]))           # end to end: no dot
        self.assertEqual(wires.junctions(s), [(3.0, 1.0)])


class WireCommandTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = False
        self.coil = self.win.library.get("symbol", "Relay coil")

    def tearDown(self):
        self.v.project.saved_at = len(self.v.project.undo_stack)
        self.win.close()

    def place(self, defn, at, angle_keys=()):
        self.v.run(C.InsertCmd, defn, {})
        type_in(self.v, *angle_keys, "%g,%g" % at)
        return [e for e in self.v.sheet().entities.values() if isinstance(e, M.Insert)][-1]

    def test_wire_routes_square_and_ends_on_a_pin(self):
        v = self.v
        ins = self.place(self.coil, (6, 4))              # pins at 5.75,4 and 6.25,4
        v.run(C.WireCmd)
        type_in(v, "2,6", "5.75,4")                      # ends by itself on pin A1
        self.assertIsNone(v.cmd)
        w = wires_of(v)[0]
        self.assertEqual(w.points, [(2.0, 6.0), (5.75, 6.0), (5.75, 4.0)])
        # moving the coil drags the wire end along
        v.set_selection({ins.id})
        v.run(C.MoveCmd)
        type_in(v, "6,4", "@1,0")
        w = wires_of(v)[0]
        self.assertEqual(w.points[-1], (6.75, 4.0))
        self.assertTrue(all(abs(a[0] - b[0]) < 1e-9 or abs(a[1] - b[1]) < 1e-9
                            for a, b in zip(w.points, w.points[1:])))
        v.project.undo()
        self.assertEqual(wires_of(v)[0].points[-1], (5.75, 4.0))

    def test_symbol_dropped_on_a_rung_is_wired_in(self):
        v = self.v
        v.run(C.WireCmd)
        type_in(v, "2,5", "8,5", "")
        contact = self.win.library.get("symbol", "Contact NO")
        self.place(contact, (4, 5))
        ws = wires_of(v)
        self.assertEqual([w.points for w in ws], [[(2.0, 5.0), (3.75, 5.0)],
                                                  [(4.25, 5.0), (8.0, 5.0)]])
        v.repaint()
        v.project.undo()
        self.assertEqual(len(wires_of(v)), 1)

    def test_selected_wire_moves_with_symbol_not_twice(self):
        v = self.v
        ins = self.place(self.coil, (6, 4))
        v.run(C.WireCmd)
        type_in(v, "4,4", "5.75,4")
        w = wires_of(v)[0]
        v.set_selection({ins.id, w.id})
        v.run(C.MoveCmd)
        type_in(v, "0,0", "@0,1")
        self.assertEqual(wires_of(v)[0].points, [(4.0, 5.0), (5.75, 5.0)])

    def test_flip_corner_and_undo_click(self):
        v = self.v
        v.run(C.WireCmd)
        type_in(v, "1,1")
        v.cursor = (3, 2)
        type_in(v, "F")
        type_in(v, "3,2", "")
        self.assertEqual(wires_of(v)[0].points, [(1.0, 1.0), (1.0, 2.0), (3.0, 2.0)])


class WireKeptTest(unittest.TestCase):
    def test_starting_another_command_keeps_the_wire(self):
        w, v = window()
        try:
            v.osnap_on = v.snap_on = False
            v.run(C.WireCmd)
            type_in(v, "1,1", "3,1")
            v.run(C.LineCmd)                    # starting something else
            v.cancel()
            self.assertEqual([e.points for e in v.sheet().entities.values()],
                             [[(1.0, 1.0), (3.0, 1.0)]])
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            w.close()


class BusTest(unittest.TestCase):
    def test_paths_keep_spacing_through_turns(self):
        paths = C.bus_paths([(0, 5), (4, 5), (4, 1)], 3, 0.5)
        self.assertEqual(paths[0], [(0.0, 5.0), (4.0, 5.0), (4.0, 1.0)])
        # going right, the others are below; turning down, they stay on the inside
        self.assertEqual(paths[1], [(0.0, 4.5), (3.5, 4.5), (3.5, 1.0)])
        self.assertEqual(paths[2], [(0.0, 4.0), (3.0, 4.0), (3.0, 1.0)])
        flipped = C.bus_paths([(0, 5), (4, 5)], 2, 0.5, flip=True)
        self.assertEqual(flipped[1], [(0.0, 5.5), (4.0, 5.5)])

    def test_bus_command(self):
        w, v = window()
        try:
            v.osnap_on = v.snap_on = False
            v.run(C.BusCmd)
            type_in(v, "4", "12mm", "1,8", "6,8", "6,3", "9,3", "")
            ws = wires_of(v)
            self.assertEqual(len(ws), 4)
            gap = 12 / 25.4
            ys = sorted(round(x.points[0][1], 6) for x in ws)
            self.assertAlmostEqual(ys[-1] - ys[-2], gap, 5)
            self.assertTrue(all(len(x.points) == 4 for x in ws))      # two turns each
            v.run(C.BusCmd)                       # it remembers 4 and 12 mm
            type_in(v, "", "", "1,1", "3,1")
            v.cancel()                            # Esc keeps it
            self.assertEqual(len(wires_of(v)), 8)
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            w.close()
