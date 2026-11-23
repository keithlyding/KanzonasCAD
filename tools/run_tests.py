"""Run the unit tests in several processes at once (the owner, Nov 2026: the Windows build spent
55 of its 62 minutes running them one after another).

    python tools/run_tests.py [-j N]

Every tests/test_*.py runs, in groups handed out to N processes (default: the number of
processors, at most 4) as each finishes its last group; the biggest files go first, so a slow one
doesn't start last. Each process is an ordinary `python -m unittest tests.test_a tests.test_b ...`
(tests/__init__.py tears Qt down at its exit and gives it its own settings file, library and
recovery folder), so nothing is shared between them. It fails when any group fails, and when the
groups together ran fewer tests than unittest discover finds (a file whose import failed)."""

import argparse
import os
import re
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_modules():
    """tests.test_* module names, the biggest file first (a rough guess at the slowest)."""
    folder = os.path.join(ROOT, "tests")
    names = [f[:-3] for f in os.listdir(folder) if f.startswith("test_") and f.endswith(".py")]
    names.sort(key=lambda n: (-os.path.getsize(os.path.join(folder, n + ".py")), n))
    return ["tests." + n for n in names]


def groups(mods, jobs):
    """mods in about four groups per process, each group a run of neighbours in mods (so the
    biggest files make up the first groups)."""
    n = max(1, min(len(mods), jobs * 4))
    size = -(-len(mods) // n)
    return [mods[k:k + size] for k in range(0, len(mods), size)]


def discovered():
    """How many tests unittest discover finds, counted in a process of its own (loading them
    imports every test module)."""
    code = ("import unittest; print(unittest.defaultTestLoader.discover("
            "'tests', pattern='test_*.py', top_level_dir='.').countTestCases())")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    if out.returncode != 0:
        sys.stdout.write(out.stdout + out.stderr)
        raise SystemExit("couldn't count the tests")
    return int(out.stdout.strip().splitlines()[-1])


def run(jobs):
    todo = groups(test_modules(), jobs)
    lock = threading.Lock()
    results = []

    def worker():
        while True:
            with lock:
                if not todo:
                    return
                mods = todo.pop(0)
            start = time.time()
            out = subprocess.run([sys.executable, "-m", "unittest"] + mods, cwd=ROOT,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            ran = re.findall(r"^Ran (\d+) tests? in", out.stdout, re.M)
            with lock:
                results.append((mods, out.returncode, int(ran[-1]) if ran else 0,
                                time.time() - start, out.stdout))
                sys.stdout.write("%s %3d tests %6.1f s  %s ... (%d files)\n" % (
                    "ok  " if out.returncode == 0 else "FAIL", results[-1][2],
                    results[-1][3], mods[0], len(mods)))
                sys.stdout.flush()

    threads = [threading.Thread(target=worker) for _k in range(jobs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-j", "--jobs", type=int, default=min(4, os.cpu_count() or 1))
    args = ap.parse_args()
    start = time.time()
    expected = discovered()
    results = run(max(1, args.jobs))
    failed = [r for r in results if r[1] != 0]
    for mods, code, _ran, _secs, out in failed:
        sys.stdout.write("\n==== FAILED (exit %d): %s\n%s\n" % (code, " ".join(mods), out))
    ran = sum(r[2] for r in results)
    sys.stdout.write("\nRan %d tests (discover finds %d) in %d groups, %d processes, %.1f s\n"
                     % (ran, expected, len(results), args.jobs, time.time() - start))
    if failed:
        sys.stdout.write("FAILED: %d group(s)\n" % len(failed))
        return 1
    if ran != expected:
        sys.stdout.write("FAILED: %d test(s) ran, discover finds %d\n" % (ran, expected))
        return 1
    sys.stdout.write("OK\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
