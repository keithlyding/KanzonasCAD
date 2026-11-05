# KanzonasCAD: rules for every change (all AI agents and people)

This file is read by every coding agent working on this repo (Claude, ChatGPT/Codex, Grok...)
and by people. `CLAUDE.md` just points here. Read all of it before editing.

A free electrical CAD program in Python (PySide6 + ezdxf) for Windows and Linux, with an
AutoCAD-like way of working (command line, object snaps, grips, window selection) and a short
list of commands. US practice: JIC/NFPA symbols, US device tags (CR1, M1), grid-style
cross-references (6-D1), wire numbers that start with the page number (6001). Drawings are in
inches on ANSI sheets. It shares its look (menus, ribbon, theme, icons) with KanzonasPDF.

`.github/workflows/build.yml` builds a Windows folder (job `build`, the check the rule protecting `main` requires) and a Linux folder (job
`linux`), each running the unit tests and its own `--selftest`. On `main`, job `publish` then
makes a GitHub release `v<version>` with both downloads and that version's RELEASE_NOTES.md
section, once per version and only when both builds are green (full releases, not pre-releases:
the owner's choice). A merge that doesn't change `__version__` publishes nothing. The app's
update box (`updates.py`) shows those notes and installs the release.

## Branches and merging (several agents work here at once)
- Start every task from the latest `main`, on a new branch of your own named
  `<agent>/<task>` (for example `chatgpt/wire-numbers`, `grok/symbol-library`).
  One branch per task.
- Never push to `main`, and never to another agent's branch.
- Merge only through a pull request to `main`, and only once both builds on your branch are
  green. Never skip, disable or weaken a test to get green.
- **Take the version number at merge time, not at the start.** Just before merging, merge
  the latest `main` into your branch, then set `__version__` to the next number after the one
  on `main` and add your CHANGELOG row above the newest one.
- **Version numbers:** 0.x until the owner calls it ready for real work. Bump the middle
  number (0.2, 0.3) for a significant new capability (a new kind of work: wires, symbols,
  wire numbers, cross-references, reports...); everything else bumps the last number
  (0.2 -> 0.2.1). Plain numbers only (0.2, not 0.20).
- Every push to any branch runs both builds, as in KanzonasPDF (no separate pull-request
  run). Push when a piece of work is done, not after every small edit; then open its pull
  request and merge once the branch's builds are green: build and publish in one go (the
  owner's choice). Never hold builds back with GitHub's skip-ci marker: a branch whose newest
  commit carries it has no run, and its pull request can't merge.

## Every user-facing change must update, in the same commit:
1. **The user manual** `kanzonascad/manual.py` (Help > User manual, F1). Describe new or
   changed commands, menu items, shortcuts and behavior, and correct anything the change made
   untrue (including the keyboard shortcut table). Name menu commands exactly as the menu
   shows them: the self-test check "user manual covers every command" fails the build when a
   menu command is missing, but it cannot catch wording that has become wrong.
2. **The version**: `__version__` in `kanzonascad/__init__.py` (see above).
3. **CHANGELOG.md**: a row for the new version.
4. **RELEASE_NOTES.md**: a few plain-language lines under `## <version>` (New / Fixed). The
   build fails without them.

## Before pushing
- `QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -p "test_*.py" -t .` must pass
  (`-t .` loads `tests/__init__.py`, which tears Qt down in order at exit).
- `QT_QPA_PLATFORM=offscreen python -m kanzonascad --selftest selftest.log` must exit 0.
- New dependencies: add the minimum to `requirements.txt` and the exact version and license
  to `constraints.txt`. Keep the license of every dependency compatible with MIT (no GPL or
  AGPL libraries: KanzonasCAD does not use PyMuPDF).

## Security updates
- `.github/workflows/security-check.yml` runs every Monday (and by hand): pip-audit on
  `constraints.txt`, and `tools/check_dependencies.py` for newer ezdxf, ezdwg and PySide6
  releases (they read untrusted DXF, DWG and picture files; their fixes don't always get a PyPI
  advisory). It reports in one open issue labeled `security`. Act on it promptly: bump the pin in
  `constraints.txt` on a branch, read the release notes, and release when both builds are green.

## Design rules
- **The model has no Qt** (`model.py`, `geometry.py`, `trim.py`, `sheetframe.py`): it can be
  loaded, edited, checked and exported without a window.
- **Entities are values.** A change replaces an entity with a changed copy (same id) through
  `Project.edit(...)`, which records before/after for Undo. Never change an entity in place:
  caches on entity objects (bounding box, snap points) rely on it.
- **Every change goes through one Edit** (`with project.edit("Name") as ed:`), so it can be
  undone, marks the project modified and refreshes the views. A failed step puts back what
  it had already done.
- **Never walk every entity on a mouse move or paint.** Hit tests, snaps and window selection
  go through the sheet's spatial index (`Sheet.query`); drawing goes through the renderer's
  per-chunk paths (`render.py`), which rebuild only the chunks a change touched.
- **Errors are not swallowed.** Don't wrap code in `except Exception: pass`. Catch the errors
  you expect and tell the user (a message box or the command line). Hidden failures are what
  makes some CAD programs untrustworthy.
- Windows and Linux: anything platform-specific goes behind `sys.platform` and keeps the other
  platform's behavior identical.
- American spelling in all user-visible text. Units are inches.
- Start-up must not import heavy libraries (ezdxf, openpyxl...): import them inside the
  function that needs them. The self-test fails if start-up imports ezdxf.

## Performance budget (checked by the self-test "speed budget")
On a 60,000-line sheet: opened and drawn < 5 s, ten zoomed repaints < 2 s, 1,000 lines added
one edit each < 2 s, 1,000 lines moved in one edit < 2 s, a mouse move < 30 ms, peak memory
< 800 MB. Typical today: 0.6 s, 0.2 s, 0.4 s, 0.06 s, 0.5 ms, 180 MB.

## Plans and decisions
The order of work and the owner's decisions are in docs/ROADMAP.md: read it before starting a
feature, and update it when a decision changes.

## Credits
KanzonasCAD's electrical features (cross-references, device tags, terminals, reports) will
draw on ideas and, where it fits, code from KatieCAD (https://github.com/Merecete/KatieCAD,
MIT License, Copyright (c) 2026 Merecete). Any code taken from it keeps its copyright notice
in the file it lands in and is listed in NOTICE.md.
