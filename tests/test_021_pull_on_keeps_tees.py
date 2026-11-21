"""A moved wire end that stops a few thousandths short of a wire is put on it (pull_on, after
Stretch or a grip), without taking anything joined to it off its run (the long battery, seed
4213: an end stretched 0.0086" above a slanted wire was pulled onto the nearest point of it,
0.003" across, sliding its run with it, and the wire teed into that run was left 0.003" away).

- the end slides along the line of its own run onto the wire: the run keeps its line;
- when that doesn't meet the wire, the end is put on the nearest point, its run sliding with
  it; when that would take something joined off the run, the run stays and a piece the length
  of the gap goes on to the point."""
import unittest

from tests.util import APP

from kanzonascad import model as M
from kanzonascad import wires


def sheet_of(*ws):
    p = M.Project()
    s = p.make_sheet("S", "schematic")
    with p.edit("draw") as ed:
        ed.add_sheet(s)
        made = [ed.add(s, M.Wire(pts)) for pts in ws]
    return p, s, made


class PullOnTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(APP)

    def test_slides_along_its_run_and_keeps_the_tee(self):
        # (the battery's drawing, seed 4213 step 2508, as Stretch left it)
        p, s, (run, slanted, tee) = sheet_of(
            [(-26.5, 66.25), (-22.5, 66.25), (-22.5, 68.75)],
            [(-18.25, 70.5), (-25.5, 67.5), (-25.5, 69.5)],
            [(-22.5, 67.0), (-22.25, 67.0), (-22.25, 63.0)])
        with p.edit("pull") as ed:
            self.assertEqual(wires.pull_on(ed, s, [(run.id, -1)]), 1)
        got = s.entities[run.id].points
        self.assertEqual(got[1], (-22.5, 66.25))
        self.assertEqual(got[2][0], -22.5)                 # (its run kept its line)
        self.assertLess(abs(got[2][1] - (70.5 - 3.0 * 4.25 / 7.25)), 1e-9)   # (on the wire)
        self.assertEqual(wires.near_misses(s, [s.entities[tee.id].points[0], got[2]]), [])

    def test_a_piece_added_when_sliding_would_take_a_tee_off(self):
        # (an end 0.005" beside a wire running the same way: sliding along its run never meets
        # it, and putting it on the nearest point would slide the run off the tee)
        p, s, (run, beside, tee) = sheet_of(
            [(0.0, 0.0), (2.0, 0.0), (2.0, 1.0)],
            [(2.005, 0.5), (2.005, 3.0)],
            [(2.0, 0.25), (3.0, 0.25)])
        with p.edit("pull") as ed:
            self.assertEqual(wires.pull_on(ed, s, [(run.id, -1)]), 1)
        got = s.entities[run.id].points
        self.assertEqual(got[:3], run.points)              # (its run where it was)
        self.assertEqual(got[3], (2.005, 1.0))             # (a piece on to the wire)
        self.assertEqual(wires.near_misses(s, [(2.0, 0.25), got[-1]]), [])

    def test_still_pulled_onto_the_nearest_point_when_nothing_is_on_its_run(self):
        p, s, (run, beside) = sheet_of(
            [(0.0, 0.0), (2.0, 0.0), (2.0, 1.0)],
            [(2.005, 0.5), (2.005, 3.0)])
        with p.edit("pull") as ed:
            self.assertEqual(wires.pull_on(ed, s, [(run.id, -1)]), 1)
        self.assertLess(abs(s.entities[run.id].points[-1][0] - 2.005), 1e-9)


if __name__ == "__main__":
    unittest.main()
