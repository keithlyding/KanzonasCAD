import os
import tempfile
import unittest

from kanzonascad import geometry as G
from kanzonascad import model as M
from kanzonascad.trim import trim, entity_intersections


def approx(a, b, eps=1e-6):
    return abs(a[0] - b[0]) < eps and abs(a[1] - b[1]) < eps


class GeometryTest(unittest.TestCase):
    def test_arc_from_3_points_is_counterclockwise(self):
        c, r, s, e = G.arc_from_3_points((1, 0), (0, 1), (-1, 0))
        self.assertTrue(approx(c, (0, 0)))
        self.assertAlmostEqual(r, 1)
        self.assertAlmostEqual(s, 0)
        self.assertAlmostEqual(e, 180)
        # the same three points picked the other way round keep the arc through (0, 1)
        c, r, s, e = G.arc_from_3_points((-1, 0), (0, 1), (1, 0))
        self.assertAlmostEqual(s, 0)
        self.assertAlmostEqual(e, 180)

    def test_intersections(self):
        self.assertTrue(approx(G.segment_intersections((0, 0), (2, 2), (0, 2), (2, 0))[0], (1, 1)))
        self.assertEqual(G.segment_intersections((0, 0), (1, 0), (0, 1), (1, 1)), [])
        pts = G.line_circle_intersections((-2, 0), (2, 0), (0, 0), 1)
        self.assertEqual(len(pts), 2)
        self.assertEqual(len(G.circle_circle_intersections((0, 0), 1, (1, 0), 1)), 2)

    def test_mirror(self):
        self.assertTrue(approx(G.mirror_point((1, 2), (0, 0), (0, 1)), (-1, 2)))


class EntityTest(unittest.TestCase):
    def test_round_trip_every_kind(self):
        ents = [M.Line((0, 0), (1, 1), layer="WIRES"), M.Polyline([(0, 0), (1, 0), (1, 1)], True),
                M.Circle((2, 2), 0.5, color="#ff0000"), M.Arc((3, 3), 1, 10, 200),
                M.Text((1, 1), "CR1", 0.125, 90, "center")]
        for e in ents:
            d = e.to_dict()
            back = M.Entity.from_dict(d)
            self.assertEqual(back.to_dict(), d)

    def test_transforms_return_copies(self):
        ln = M.Line((0, 0), (1, 0), id=5)
        m = ln.moved(1, 1)
        self.assertEqual(ln.p1, (0.0, 0.0))
        self.assertEqual(m.p1, (1.0, 1.0))
        self.assertEqual(m.id, 5)
        r = ln.rotated((0, 0), 90)
        self.assertTrue(approx(r.p2, (0, 1)))
        a = M.Arc((0, 0), 1, 0, 90).mirrored((0, 0), (0, 1))
        self.assertAlmostEqual(a.start, 90)
        self.assertAlmostEqual(a.end, 180)

    def test_mirrored_text_stays_readable(self):
        t = M.Text((1, 0), "ABC", 0.1, 0, "left")
        m = t.mirrored((0, 0), (0, 1))          # left-right flip
        self.assertTrue(approx(m.pos, (-1, 0)))
        self.assertAlmostEqual(m.angle, 0)
        self.assertEqual(m.align, "right")

    def test_hits_and_windows(self):
        ln = M.Line((0, 0), (2, 0))
        self.assertAlmostEqual(ln.distance((1, 0.5)), 0.5)
        self.assertTrue(ln.inside((-1, -1, 3, 1)))
        self.assertFalse(ln.inside((0.5, -1, 3, 1)))
        self.assertTrue(ln.crosses((0.5, -1, 3, 1)))
        c = M.Circle((0, 0), 1)
        self.assertFalse(c.crosses((-0.1, -0.1, 0.1, 0.1)))   # window wholly inside the circle
        self.assertTrue(c.crosses((0.9, -0.1, 1.2, 0.1)))


class ProjectTest(unittest.TestCase):
    def test_undo_redo_and_modified(self):
        p = M.Project.new()
        s = p.sheets[0]
        self.assertFalse(p.is_modified())
        with p.edit("Line") as ed:
            ln = ed.add(s, M.Line((0, 0), (1, 0)))
        self.assertTrue(p.is_modified())
        with p.edit("Move") as ed:
            ed.change(s, ln.moved(1, 0))
        self.assertEqual(s.entities[ln.id].p1, (1.0, 0.0))
        p.undo()
        self.assertEqual(s.entities[ln.id].p1, (0.0, 0.0))
        p.undo()
        self.assertNotIn(ln.id, s.entities)
        self.assertFalse(p.is_modified())
        p.redo()
        p.redo()
        self.assertEqual(s.entities[ln.id].p1, (1.0, 0.0))

    def test_failed_edit_is_put_back(self):
        p = M.Project.new()
        s = p.sheets[0]
        with self.assertRaises(RuntimeError):
            with p.edit("Bad") as ed:
                ed.add(s, M.Line((0, 0), (1, 0)))
                raise RuntimeError("boom")
        self.assertEqual(len(s.entities), 0)
        self.assertEqual(p.undo_stack, [])

    def test_sheets_undo(self):
        p = M.Project.new()
        with p.edit("New sheet") as ed:
            s2 = ed.add_sheet(M.Sheet(title="Two"))
        with p.edit("Line") as ed:
            ed.add(s2, M.Line((0, 0), (1, 1)))
        with p.edit("Move sheet") as ed:
            ed.move_sheet(1, 0)
        self.assertEqual(p.sheets[0].title, "Two")
        self.assertEqual(p.sheet_number(p.sheets[0]), "1")
        with p.edit("Delete sheet") as ed:
            ed.remove_sheet(p.sheets[0])
        self.assertEqual(len(p.sheets), 1)
        p.undo()
        self.assertEqual(p.sheets[0].title, "Two")
        self.assertEqual(len(p.sheets[0].entities), 1)
        p.undo()
        self.assertEqual(p.sheets[1].title, "Two")

    def test_zones_and_reference_format(self):
        p = M.Project.new()
        s = p.sheets[0]
        x0, y0, x1, y1 = s.frame()
        # top left zone is A1, bottom right is F10 on a 10 x 6 grid
        self.assertEqual(s.zone_at(x0 + 0.01, y1 - 0.01), ("A", 1))
        self.assertEqual(s.zone_at(x1 - 0.01, y0 + 0.01), ("F", 10))
        self.assertIsNone(s.zone_at(0, 0))
        with p.edit("Number") as ed:
            ed.sheet_meta(s, number="6")
        cw = (x1 - x0) / s.cols
        rh = (y1 - y0) / s.rows
        self.assertEqual(p.zone_text(s, x0 + cw * 0.5, y1 - rh * 3.5), "6-D1")

    def test_save_load(self):
        p = M.Project.new()
        s = p.sheets[0]
        with p.edit("Draw") as ed:
            ed.add(s, M.Line((0, 0), (1, 0), layer="WIRES"))
            ed.add(s, M.Text((1, 1), "M1", 0.2))
            ed.layer("NEW", None, M.Layer("NEW", "#00ff00").to_dict())
            ed.project_fields(dict(p.fields, Customer="ACME"), "{sheet}.{row}{col}")
        path = os.path.join(tempfile.mkdtemp(), "t.kzcad")
        p.save(path)
        self.assertFalse(p.is_modified())
        q = M.Project.load(path)
        self.assertEqual(q.to_dict(), p.to_dict())
        self.assertEqual(q.fields["Customer"], "ACME")
        self.assertEqual(q.zone_format, "{sheet}.{row}{col}")
        # ids keep counting after the loaded ones
        with q.edit("More") as ed:
            e = ed.add(q.sheets[0], M.Line((0, 0), (0, 1)))
        self.assertEqual(e.id, 3)

    def test_spatial_index_follows_changes(self):
        p = M.Project.new()
        s = p.sheets[0]
        with p.edit("Line") as ed:
            ln = ed.add(s, M.Line((1, 1), (1.2, 1)))
        self.assertIn(ln.id, [e.id for e in s.query((0.9, 0.9, 1.3, 1.1))])
        with p.edit("Move") as ed:
            ed.change(s, ln.moved(5, 5))
        self.assertEqual(s.query((0.9, 0.9, 1.3, 1.1)), [])
        self.assertEqual([e.id for e in s.query((5.9, 5.9, 6.3, 6.1))], [ln.id])


class TrimTest(unittest.TestCase):
    def test_line_between_two_cutters(self):
        a = M.Line((0, 0), (10, 0), id=1)
        c1 = M.Line((3, -1), (3, 1), id=2)
        c2 = M.Line((7, -1), (7, 1), id=3)
        out = trim(a, (5, 0), [c1, c2])
        self.assertEqual(len(out), 2)
        self.assertTrue(approx(out[0].p2, (3, 0)))
        self.assertTrue(approx(out[1].p1, (7, 0)))
        # an end piece goes entirely
        out = trim(a, (1, 0), [c1, c2])
        self.assertEqual(len(out), 1)
        self.assertTrue(approx(out[0].p1, (3, 0)) and approx(out[0].p2, (10, 0)))

    def test_uncrossed_object_goes(self):
        self.assertEqual(trim(M.Line((0, 0), (1, 0), id=1), (0.5, 0), []), [])

    def test_circle_becomes_arc(self):
        c = M.Circle((0, 0), 1, id=1)
        cut = M.Line((-2, 0), (2, 0), id=2)
        out = trim(c, (0, 1), [cut])        # remove the top half
        self.assertEqual(len(out), 1)
        self.assertIsInstance(out[0], M.Arc)
        self.assertAlmostEqual(out[0].start, 180)
        self.assertAlmostEqual(out[0].end, 0)

    def test_arc_and_polyline(self):
        arc = M.Arc((0, 0), 1, 0, 180, id=1)
        cut = M.Line((0, -2), (0, 2), id=2)
        out = trim(arc, G.polar((0, 0), 1, 30), [cut])
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0].start, 90)
        pl = M.Polyline([(0, 0), (4, 0), (4, 4)], id=3)
        out = trim(pl, (3, 0), [M.Line((2, -1), (2, 1), id=4)])
        self.assertEqual(len(out), 1)
        self.assertTrue(approx(out[0].p1, (0, 0)) and approx(out[0].p2, (2, 0)))

    def test_closed_polyline(self):
        sq = M.Polyline([(0, 0), (4, 0), (4, 4), (0, 4)], True, id=1)
        cut = M.Line((2, -1), (2, 5), id=2)
        out = trim(sq, (4, 2), [cut])       # cut away the right half
        self.assertEqual(len(out), 1)
        xs = [p[0] for p in out[0].points]
        self.assertLessEqual(max(xs), 2 + 1e-9)

    def test_intersections_between_kinds(self):
        self.assertEqual(len(entity_intersections(M.Circle((0, 0), 1), M.Arc((1, 0), 1, 90, 270))), 2)


if __name__ == "__main__":
    unittest.main()
