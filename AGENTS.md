# KanzonasCAD: rules for every change (all AI agents and people)

This file is read by every coding agent working on this repo (Claude, ChatGPT/Codex, Grok...)
and by people. `CLAUDE.md` just points here. Read all of it before editing.

A free electrical CAD program in Python (PySide6 + ezdxf) for Windows and Linux, with an
AutoCAD-like way of working (command line, object snaps, grips, window selection) and a short
list of commands. US practice: JIC/NFPA symbols, US device tags (CR1, M1), grid-style
cross-references (6-D1), wire numbers that start with the page number (6001). Drawings are in
inches on ANSI sheets. It shares its look (menus, ribbon, theme, icons) with KanzonasPDF.

`.github/workflows/build.yml` builds, as KanzonasPDF's does: on Windows (job `build`, the
check the rule protecting `main` requires) the app folder, its zip, the setup, the portable zip
and the PortableApps.com layout; on Linux (job `linux`, packaging/linux/) the app folder as a
tar.gz and an AppImage made from it; each runs the unit tests and its own `--selftest` (the
Windows build also inside the installed, portable and PortableApps.com copies, the Linux build
inside the AppImage). On `main`, job `publish` then makes a GitHub release `v<version>` with
the downloads, their `SHA256SUMS.txt` and that version's RELEASE_NOTES.md section, once per version and only when both
builds are green (full releases, not pre-releases: the owner's choice). A merge that doesn't
change `__version__` publishes nothing. The app's update box (`updates.py`) shows those notes
and installs the release.

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

## The battery
`tests/battery.py` is the exhaustive battery: random editing (thousands of steps with the model
checked after each, the wire groups, dots and crossings kept up to date checked against a
fresh count, save/open round trips, undo all the way back and redo all the way forward), every
menu command in three states, file round trips, speed at scale and pictures. A short run of it
is part of the unit tests (`tests/test_battery_quick.py`) and so runs on every build; run the
long one by hand before a release with a few seeds:
`QT_QPA_PLATFORM=offscreen python tests/battery.py OUT_DIR --ops 3000 --seed N`. A failure it
finds becomes a fix and a unit test of its own.

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
- **Where things are kept goes through `paths.py`.** Settings come from `paths.settings()`
  (never `QSettings(...)` directly), and a folder of the program's own from
  `paths.portable_data_dir()` / `paths.data_dir()`: a `portable.txt` beside KanzonasCAD.exe puts
  them all in a data folder beside it (the portable zip; `data=` and `updates=off` in it for
  the PortableApps.com package, tools/make_portableapps.py and docs/portableapps.md). The
  Windows build checks that the portable copies keep their settings there and leave the
  registry alone.
- American spelling in all user-visible text. Units are inches.
- Start-up must not import heavy libraries (ezdxf, openpyxl...): import them inside the
  function that needs them. The self-test fails if start-up imports ezdxf.

## Packaging (as KanzonasPDF's; keep the two alike)
- The Linux AppImage builds on Ubuntu 22.04 (glibc 2.35): `packaging/linux/make_appimage.py`
  fails the build if a bundled file needs a newer glibc, libstdc++ (C++ ABI) or libgcc_s, or
  if a library in `packaging/linux/excludelist` (the computer's own) is still bundled; it checks
  the desktop file and the AppStream metadata
  (`io.github.keithlyding.kanzonascad.metainfo.xml`). appimagetool is pinned by SHA-256 in the
  workflow, and the AppImage runtime is cut from it (pinned too): update both together, and
  with KanzonasPDF's.
- The AppImage's release name never changes (`KanzonasCAD-x86_64.AppImage`): Update now puts
  the new one at the old one's place (`updates.AppImageUpdater`, `replace_appimage`). The
  other downloads carry the version in their names.
- The icon: the owner's pictures `assets/kanzonascad-icon-source.png` (the app: a violet tile,
  "CAD" in violet, as in the logo) and `assets/kanzonascad-setup-source.png` (the installer: a
  blue tile). `tools/make_icons.py` makes the .png and .ico files from them, then
  `tools/make_paf_icon.py` the PortableApps.com icon `assets/portableapps-appicon.ico` from
  `assets/kanzonascad.png`: run both when the icon changes.

## Logos
Every Kanzonas logo comes from the Kanzonas-Site repository's `brand/` folder
(https://github.com/keithlyding/Kanzonas-Site), the single source of truth for logos (the owner's
decision): its `make_logos.py`, artwork, fonts and `SPEC.md`. Never make or edit a logo here.
To change one, change it there, then copy its files in as its `brand/README.md` says
(`assets/kanzonascad-logo.png`, `kanzonascad/resources/logo.png`), as a user-facing change.

## Performance budget (checked by the self-test "speed budget")
On a 60,000-line sheet: opened and drawn < 5 s, ten zoomed repaints < 2 s, 1,000 lines added
one edit each < 2 s, 1,000 lines moved in one edit < 2 s, a mouse move < 30 ms, a mouse move in
a command with the snaps on and the screen drawn < 30 ms (zoomed out and in), peak memory
< 800 MB. Typical today: 0.6 s, 0.2 s, 0.4 s, 0.06 s, 0.5 ms, a few ms, 180 MB. The view keeps a
picture of the drawing (`CadView._drawing_picture`), drawn again only when its key changes (the
view, the project's revision, the sheet, the title block, the layers): a mouse move only draws
the crosshair, snap marker and rubber band over it. Anything that changes how the drawing looks
must change that key (an edit does).

## Plans and decisions
The order of work and the owner's decisions are in docs/ROADMAP.md: read it before starting a
feature, and update it when a decision changes.

## Credits
KanzonasCAD's electrical features (cross-references, device tags, terminals, reports) will
draw on ideas and, where it fits, code from KatieCAD (https://github.com/Merecete/KatieCAD,
MIT License, Copyright (c) 2026 Merecete). Any code taken from it keeps its copyright notice
in the file it lands in and is listed in NOTICE.md.
