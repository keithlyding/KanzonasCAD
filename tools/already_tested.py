"""Whether main's build may skip the tests: its code is exactly a pull request's head whose build
passed (the owner, Nov 2026: "Don't re-run the tests on main for code the PR build already
passed ... If main has moved and the code differs, the full tests run as they do now").

    python tools/already_tested.py        (in a workflow step; writes skip=true or skip=false
                                           to $GITHUB_OUTPUT)

It says skip=true only when all of these hold, and skip=false on anything else, an error
included:
- the push is to main;
- the commit is a merge whose files (its tree) are exactly those of its second parent, the
  pull request's head (so main hadn't moved: the branch had main merged in before);
- that head has a build of this workflow, from a push in this repository, that succeeded.

The tree is every file, the workflow and the pinned dependencies with the code: the same tree is
the same program and the same tests. The apps are still built and self-tested on main; only the
unit tests and the batteries, already passed on that tree, are skipped."""

import json
import os
import sys
import urllib.request

WORKFLOW = ".github/workflows/build.yml"


def decide(ref, event, commit, head, runs, repo):
    """(skip, why) from main's commit and its pull-request parent (GitHub's commit objects, head
    None when there is no second parent) and that parent's successful runs."""
    if event != "push" or ref != "refs/heads/main":
        return False, "not a push to main"
    parents = commit.get("parents") or []
    if len(parents) != 2 or head is None:
        return False, "not a merge of a pull request"
    if head.get("sha") != parents[1].get("sha"):
        return False, "the second parent isn't the commit looked at"
    tree = commit.get("commit", {}).get("tree", {}).get("sha")
    if not tree or tree != head.get("commit", {}).get("tree", {}).get("sha"):
        return False, "main's files differ from the pull request's head (main had moved)"
    for r in runs:
        if r.get("head_sha") == head["sha"] and r.get("conclusion") == "success" and \
                r.get("event") == "push" and (r.get("path") or "").startswith(WORKFLOW) and \
                (r.get("head_repository") or {}).get("full_name") == repo:
            return True, "the same files passed in run %s on %s" % (r.get("id"), head["sha"][:7])
    return False, "no passed build of the pull request's head %s" % head["sha"][:7]


def _get(path, token):
    req = urllib.request.Request("https://api.github.com" + path, headers={
        "Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def check(env):
    repo, sha = env["GITHUB_REPOSITORY"], env["GITHUB_SHA"]
    ref, event = env.get("GITHUB_REF", ""), env.get("GITHUB_EVENT_NAME", "")
    if event != "push" or ref != "refs/heads/main":
        return decide(ref, event, {}, None, [], repo)
    token = env["GITHUB_TOKEN"]
    commit = _get("/repos/%s/commits/%s" % (repo, sha), token)
    parents = commit.get("parents") or []
    if len(parents) != 2:
        return decide(ref, event, commit, None, [], repo)
    head = _get("/repos/%s/commits/%s" % (repo, parents[1]["sha"]), token)
    runs = _get("/repos/%s/actions/workflows/build.yml/runs?head_sha=%s&status=success"
                "&event=push&per_page=50" % (repo, head["sha"]), token)
    return decide(ref, event, commit, head, runs.get("workflow_runs", []), repo)


def main():
    try:
        skip, why = check(os.environ)
    except (OSError, KeyError, ValueError) as e:       # (the API or the environment: test)
        skip, why = False, "couldn't tell (%s): the tests run" % e
    line = "Tests %s: %s" % ("skipped" if skip else "run", why)
    sys.stdout.write(line + "\n")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write("skip=%s\n" % ("true" if skip else "false"))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
