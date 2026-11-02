# KanzonasCAD

A free, open-source electrical CAD program for Windows and Linux, for people who know
AutoCAD but want fewer commands and fewer surprises.

- AutoCAD-style drawing: command line, object snaps, ortho, grips, window/crossing selection.
- Projects of ANSI sheets with a grid of zones (6-D1 references) and a title block.
- DXF in and out, PDF out.
- US practice: JIC/NFPA symbols, CR1/M1 tags, wire numbers that start with the page number
  (coming: see the plan below).

Status: **0.1, the foundation**. Next: a JIC/NFPA symbol library and wires that stay
connected, then device tags and grid cross-references, wire numbering, and reports.

## Run from source

    pip install -r requirements.txt -c constraints.txt
    python -m kanzonascad

Self-test: `python -m kanzonascad --selftest selftest.log` (exit code 0 = passed).
Tests: `python -m unittest discover -s tests -p "test_*.py" -t .`

Press F1 in the app for the user manual. Rules for contributors (people and AI agents) are in
[AGENTS.md](AGENTS.md).

MIT License. See NOTICE.md for the libraries it is built on.
