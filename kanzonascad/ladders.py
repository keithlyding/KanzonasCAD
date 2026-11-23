"""Ladders and their rung numbers (the owner, 0.22: "Let's do ladder references as an option").

A ladder (model.Ladder) is two rails with numbered rungs. On a sheet that gives places by
ladder (Project properties or Sheet properties: References, Ladder), a device's place is the
number of the rung it is on: cross-references, reports and the status bar read 603 (or 6-03)
in place of 6-D1. Off every ladder, a place is still its grid zone.

Rung numbers are worked out here, after every change that could move them (sync): on each
sheet, its ladders left to right, then top down; a ladder whose first number isn't typed
(first None) carries on from the one before it. "hundreds" (project setting ladder_numbers):
the page number times 100 on (page 6: 600, 601...); "prefix": the page, a dash, the rung from
01 (6-01, 6-02...). A page that isn't a number (E6) counts by its place in the project.

No Qt here."""


def numbering(project):
    got = project.settings.get("ladder_numbers")
    return got if got in ("hundreds", "prefix") else "hundreds"


def _page(project, sheet):
    """The sheet's page number as a whole number: its own when it is one, else its place."""
    try:
        return int(str(project.sheet_number(sheet)).strip())
    except ValueError:
        return project.sheets.index(sheet) + 1


def wanted(project, sheet):
    """{ladder id: (start, prefix, pad)}: how each ladder on the sheet numbers its rungs."""
    how = numbering(project)
    out = {}
    if how == "prefix":
        nxt, prefix, pad = 1, "%s-" % project.sheet_number(sheet), 2
    else:
        nxt, prefix, pad = _page(project, sheet) * 100, "", 0
    for lad in sheet.ladders():
        start = lad.first if lad.first is not None else nxt
        out[lad.id] = (start, prefix, pad)
        nxt = start + lad.rungs
    return out


def sync(ed, project, sheets=None):
    """Every ladder's numbers as they should be now (only those that changed are changed)."""
    for s in (sheets if sheets is not None else project.sheets):
        if not s.ladders():
            continue
        for lid, (start, prefix, pad) in wanted(project, s).items():
            lad = s.entities.get(lid)
            if lad is not None and (lad.start, lad.prefix, lad.pad) != (start, prefix, pad):
                ed.change(s, lad.copy(start=start, prefix=prefix, pad=pad))
