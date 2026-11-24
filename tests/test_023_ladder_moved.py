"""A ladder moved keeps its rungs and their spacing exactly: the spacing was scaled by the
rails' new width over the old, which a move leaves the same but floating point not always,
0.9999999999999999 (the long battery, seed 4782: "moving Ladder 564 changed its rungs")."""
import random
import unittest

from kanzonascad import model as M


class LadderMovedTest(unittest.TestCase):
    def test_moved_anywhere_the_spacing_stays(self):
        rnd = random.Random(4782)
        changed = []
        for _i in range(2000):
            a = (rnd.uniform(-500, 3000), rnd.uniform(-2000, 500))
            w = rnd.uniform(1, 400)
            lad = M.Ladder(a, (a[0] + w, a[1]), rungs=rnd.randint(1, 30),
                           spacing=rnd.choice([0.5, 4.0, 0.125 * 7]))
            d = (rnd.choice([-1, 0, 1]) * rnd.choice([0.5, 4.0, 2.0 / 3]),
                 rnd.choice([-1, 1]) * rnd.choice([0.5, 4.0, 2.0 / 3]))
            now = lad.moved(*d)
            if (now.rungs, now.spacing) != (lad.rungs, lad.spacing):
                changed.append((a, w, d, lad.spacing, now.spacing))
        self.assertEqual(changed[:3], [], "%d changed" % len(changed))

    def test_scaled_the_spacing_follows(self):
        lad = M.Ladder((1.0, 10.0), (9.0, 10.0), rungs=8, spacing=0.5)
        self.assertAlmostEqual(lad.scaled((1.0, 10.0), 2.0).spacing, 1.0)


if __name__ == "__main__":
    unittest.main()
