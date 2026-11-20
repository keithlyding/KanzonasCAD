"""Reports drawn on sheets of the project (the roadmap's item 8: "report sheets drawn in the
project"; the owner wants it): a bill of materials, wire list, terminal strip list, pull list or
panel materials as a table of lines and texts on sheets of kind Report, as many as it takes, in
the room the border and title block leave, so it prints and goes to PDF with the drawings.

A report sheet remembers which report it shows (Sheet.report); Update report sheets draws them
all again from the drawing as it is now (they aren't kept up to date as you draw: a table
redrawn at every change would make every edit slow on a big project).

No Qt."""

from . import model as M

LAYER = "REPORT"
ROW_H = 0.25                # (paper inches: a row, its text 0.1" high)
TEXT_H = 0.1
CHAR_W = 0.07               # (about how wide a letter of that text is)
PAD = 0.05


def kinds():
    """{key: title} of the reports a sheet can show, in menu order."""
    return {"bom": "Bill of materials", "wires": "Wire list", "terminals": "Terminal strip list",
            "pull": "Pull list", "materials": "Panel materials"}


def table(project, key):
    """(header, rows) of a report, from the drawing as it is."""
    from . import bom, materials, pull, reports
    if key == "bom":
        return bom.table(project)
    if key == "wires":
        return reports.WIRE_HEAD, reports.wire_rows(project)
    if key == "terminals":
        return reports.TERM_HEAD, reports.terminal_rows(project)
    if key == "pull":
        return pull.table(project)
    if key == "materials":
        return materials.table(project)
    raise KeyError(key)


def _fit(text, width):
    """text cut to width (paper inches) with an ellipsis when it doesn't fit."""
    n = max(1, int((width - 2 * PAD) / CHAR_W))
    return text if len(text) <= n else text[:max(0, n - 1)] + "…"


def _widths(head, rows, room):
    """Column widths (paper inches) in proportion to what they hold, fitting room."""
    want = []
    for i, h in enumerate(head):
        n = max([len(str(h))] + [len(str(r[i])) for r in rows if i < len(r)])
        want.append(min(n, 60) * CHAR_W + 2 * PAD)
    total = sum(want) or 1.0
    f = min(1.0, room / total)
    return [w * f for w in want]


def pages(project, sheet, head, rows):
    """The table on as many pages as it takes: [[entities of a page]], drawn in sheet's units
    in the room its frame and title block leave (every page the same shape as sheet)."""
    from .scalefit import room
    k = sheet.k()
    area, tb = room(project, sheet)
    x0, y0, x1, y1 = area
    if tb is not None and tb[1] < y1:
        y0 = max(y0, tb[3])                 # (above the title block across the bottom)
        if y1 - y0 < 4 * ROW_H:
            y0 = area[1]
            x1 = min(x1, tb[0])             # (a tall title block on the right: beside it)
    widths = _widths(head, rows, x1 - x0)
    per = max(1, int((y1 - y0) / ROW_H) - 1)
    out = []
    for start in range(0, max(1, len(rows)), per):
        part = rows[start:start + per]
        ents = []
        n = len(part) + 1
        top = y1
        bottom = top - n * ROW_H
        right = x0 + sum(widths)
        for i in range(n + 1):
            y = top - i * ROW_H
            ents.append(M.Line((x0 * k, y * k), (right * k, y * k), layer=LAYER))
        x = x0
        for w in widths + [0.0]:
            ents.append(M.Line((x * k, top * k), (x * k, bottom * k), layer=LAYER))
            x += w
        for j, line in enumerate([head] + part):
            y = top - (j + 1) * ROW_H + (ROW_H - TEXT_H) / 2.0
            x = x0
            for i, w in enumerate(widths):
                val = str(line[i]) if i < len(line) else ""
                if val:
                    ents.append(M.Text(((x + PAD) * k, y * k), _fit(val, w), TEXT_H * k, 0.0,
                                       layer=LAYER))
                x += w
        out.append(ents)
    return out


def update(ed, project, key, after=None):
    """A report's sheets drawn again from the drawing (made when it has none, after the sheet
    after or at the end): its old report sheets replaced by as many as it takes now. Returns
    its sheets."""
    title = kinds()[key]
    old = [s for s in project.sheets if s.report == key]
    if old:
        at = project.sheets.index(old[0])
    elif after is not None and after in project.sheets:
        at = project.sheets.index(after) + 1
    else:
        at = len(project.sheets)
    shape = old[0] if old else project.make_sheet(title, "report")
    head, rows = table(project, key)
    got = pages(project, shape, head, rows)
    if LAYER not in project.layers:
        ed.layer(LAYER, None, M.Layer(LAYER).to_dict())
    made = []
    for i, ents in enumerate(got):
        name = title if len(got) == 1 else "%s (%d of %d)" % (title, i + 1, len(got))
        if i < len(old):
            s = old[i]
            for eid in list(s.entities):
                ed.remove(s, eid)
            ed.sheet_meta(s, title=name)
        else:
            s = project.make_sheet(name, "report")
            s.size, s.rotation, s.scale = shape.size, shape.rotation, shape.scale
            s.report = key
            ed.add_sheet(s, at + i)
        for e in ents:
            ed.add(s, e)
        made.append(s)
    for s in old[len(got):]:
        ed.remove_sheet(s)
    return made


def update_all(ed, project):
    """Every report the project has sheets for, drawn again. Returns how many reports."""
    keys = []
    for s in project.sheets:
        if s.report and s.report not in keys and s.report in kinds():
            keys.append(s.report)
    for key in keys:
        update(ed, project, key)
    return len(keys)
