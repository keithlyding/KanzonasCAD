"""main's build skips the tests only on files a pull request's build already passed
(tools/already_tested.py; the owner, Nov 2026: "If main has moved and the code differs, the full
tests run as they do now")."""
import importlib.util
import io
import os
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "already_tested", os.path.join(ROOT, "tools", "already_tested.py"))
T = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T)

REPO = "keithlyding/KanzonasCAD"


def commit(sha, tree, parents=()):
    return {"sha": sha, "commit": {"tree": {"sha": tree}},
            "parents": [{"sha": p} for p in parents]}


def run(sha, **kw):
    r = {"id": 7, "head_sha": sha, "conclusion": "success", "event": "push",
         "path": ".github/workflows/build.yml", "head_repository": {"full_name": REPO}}
    r.update(kw)
    return r


class DecideTest(unittest.TestCase):
    def setUp(self):
        self.head = commit("h" * 40, "T1", ["b" * 40])
        self.merge = commit("m" * 40, "T1", ["a" * 40, "h" * 40])

    def decide(self, ref="refs/heads/main", event="push", merge=None, head="same", runs=None):
        return T.decide(ref, event, merge or self.merge, self.head if head == "same" else head,
                        [run("h" * 40)] if runs is None else runs, REPO)[0]

    def test_the_same_files_passed_skip(self):
        self.assertTrue(self.decide())

    def test_main_moved_the_files_differ_run(self):
        self.assertFalse(self.decide(merge=commit("m" * 40, "T2", ["a" * 40, "h" * 40])))

    def test_not_main_or_not_a_push_run(self):
        self.assertFalse(self.decide(ref="refs/heads/claude/x"))
        self.assertFalse(self.decide(event="workflow_dispatch"))

    def test_not_a_merge_run(self):
        self.assertFalse(self.decide(merge=commit("m" * 40, "T1", ["a" * 40])))
        self.assertFalse(self.decide(head=None))

    def test_another_commit_than_the_second_parent_run(self):
        self.assertFalse(self.decide(head=commit("x" * 40, "T1", ["b" * 40])))

    def test_only_a_passed_push_build_of_this_repository_counts(self):
        for bad in (run("h" * 40, conclusion="failure"), run("h" * 40, event="workflow_dispatch"),
                    run("h" * 40, path=".github/workflows/security-check.yml"),
                    run("h" * 40, head_repository={"full_name": "someone/fork"}),
                    run("z" * 40)):
            self.assertFalse(self.decide(runs=[bad]), bad)
        self.assertFalse(self.decide(runs=[]))

    def test_any_error_runs_the_tests(self):
        out = os.path.join(tempfile.mkdtemp(), "out")
        env = {"GITHUB_REPOSITORY": REPO, "GITHUB_SHA": "m" * 40, "GITHUB_REF": "refs/heads/main",
               "GITHUB_EVENT_NAME": "push", "GITHUB_TOKEN": "x", "GITHUB_OUTPUT": out}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(T, "_get", side_effect=OSError("no network")), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as said:
            self.assertEqual(T.main(), 0)
        with open(out, encoding="utf-8") as f:
            self.assertEqual(f.read(), "skip=false\n")
        self.assertIn("Tests run", said.getvalue())

    def test_it_reads_github_as_described(self):
        got = {"/repos/%s/commits/%s" % (REPO, "m" * 40): self.merge,
               "/repos/%s/commits/%s" % (REPO, "h" * 40): self.head}

        def get(path, _token):
            if "/actions/" in path:
                self.assertIn("head_sha=" + "h" * 40, path)
                return {"workflow_runs": [run("h" * 40)]}
            return got[path]
        env = {"GITHUB_REPOSITORY": REPO, "GITHUB_SHA": "m" * 40, "GITHUB_REF": "refs/heads/main",
               "GITHUB_EVENT_NAME": "push", "GITHUB_TOKEN": "x"}
        with mock.patch.object(T, "_get", side_effect=get):
            self.assertEqual(T.check(env)[0], True)


if __name__ == "__main__":
    unittest.main()
