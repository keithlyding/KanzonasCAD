"""No slop in the code or the text people read (tools/slop_check.py; the owner: "please add a
search for slop in future testing"), on every build; and each of the scanner's checks finds the
slop it is for (a check that finds nothing proves nothing)."""
import importlib.util
import os
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("slop_check",
                                              os.path.join(ROOT, "tools", "slop_check.py"))
slop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(slop)


class SlopTest(unittest.TestCase):
    def test_no_slop(self):
        found = slop.run()
        self.assertEqual(found, [], "\n" + "\n".join("%s:%d: %s: %s" % f for f in found))

    def _scan(self, check, text, *more):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "x.py")
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        rep = slop.Report()
        check(rep, [p], *more)
        return [k for k, _p, _l, _w in rep.found]

    def test_each_check_finds_its_slop(self):
        self.assertEqual(self._scan(slop.swallowed, "try:\n    x()\nexcept Exception:\n    pass\n"),
                         ["swallowed error"])
        self.assertEqual(self._scan(slop.swallowed, "try:\n    x()\nexcept Exception:  # (why)\n"
                                                    "    pass\n"), [])
        self.assertEqual(self._scan(slop.swallowed, "try:\n    x()\nexcept ValueError:\n    pass\n"),
                         [])
        self.assertEqual(self._scan(slop.placeholders, "# TODO later\ntodo = []\n"),
                         ["placeholder"])
        self.assertEqual(self._scan(slop.prints, "print('hi')\n"), ["print"])
        self.assertEqual(self._scan(slop.unused_imports, "import os\nimport re\nre.x\n"),
                         ["unused import"])
        self.assertEqual(self._scan(slop.filler, "A seamless, robust tool.\nUnlock a layer.\n"),
                         ["filler word"])
        self.assertEqual(self._scan(slop.empty_tests, "def test_a():\n    x = 1\n"
                                                      "def test_b():\n    assert True\n"),
                         ["test checks nothing", "test checks nothing"])
        self.assertEqual(self._scan(slop.commented_code, "# x = compute(1)\n# (why: a note)\n"),
                         ["commented-out code"])
        lines = "".join("value_%d = compute_something_long(%d, 'a fairly long argument')\n" % (i, i)
                        for i in range(9))
        self.assertIn("repeated block", self._scan(slop.repeated_blocks, lines + "\n" + lines))

    def test_stale_and_dead(self):
        d = tempfile.mkdtemp()
        mod = os.path.join(d, "thing.py")
        with open(mod, "w", encoding="utf-8") as f:
            f.write('"""Uses thing.helper and thing.gone."""\n\n\ndef helper():\n    return 1\n\n\n'
                    'def unused_one():\n    return 2\n\n\nhelper()\n')
        rep = slop.Report()
        slop.stale_references(rep, [mod], [mod])
        self.assertEqual([w for _k, _p, _l, w in rep.found], ["thing.gone doesn't exist"])
        rep = slop.Report()
        slop.dead_code(rep, [mod], [mod])
        self.assertEqual([w for _k, _p, _l, w in rep.found], ["unused_one is never used"])


class DrawingSlopTest(unittest.TestCase):
    """The battery's drawing-slop checks find what they are for."""

    def test_near_miss(self):
        from kanzonascad import model as M
        from tests import battery_checks as BC
        p = M.Project.new()
        s = p.sheets[0]
        with p.edit("wires") as ed:
            ed.add(s, M.Wire([(1, 1), (3, 1)]))
            ed.add(s, M.Wire([(3, 1), (3, 3)]))             # (joined: fine)
            ed.add(s, M.Wire([(5, 1), (7, 1)]))
            ed.add(s, M.Wire([(7.002, 1), (7.002, 3)]))     # (0.002" short: looks joined)
        near = BC.near_misses(s)
        self.assertTrue(near)
        self.assertTrue(all(abs(d - 0.002) < 1e-9 for _i, _p, _k, d in near))

    def test_drift(self):
        from kanzonascad import model as M
        from tests import battery_checks as BC
        a = M.Line((1, 1), (2, 3))
        BC.same_place(a, a.moved(1.1, -0.7).moved(-1.1, 0.7), "moved and back")
        with self.assertRaises(AssertionError):
            BC.same_place(a, a.moved(0.0001, 0), "a hair off")


if __name__ == "__main__":
    unittest.main()
