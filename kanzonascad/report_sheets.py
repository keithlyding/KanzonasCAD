"""Reports drawn on sheets of the project (the roadmap's item 8: "report sheets drawn in the
project"; the owner wants it): a bill of materials, wire list, terminal strip list, terminal plan,
device wiring list, pull list, panel materials or the devices without a footprint as a table of lines and texts on sheets of
kind Report, as many as it takes, in the room the border and title block leave, so it prints
and goes to PDF with the drawings.

A report sheet remembers which report it shows (Sheet.report); Update report sheets draws them
all again from the drawing as it is now (they aren't kept up to date as you draw: a table
redrawn at every change would make every edit slow on a big project).

No Qt."""

from . import model as M

LAYER = "REPORT"
ROW_H = 0.25                # (paper inches: a row, its text 0.1" high)
TEXT_H = 0.1
ELLIPSIS = chr(0x2026)      # (a cell cut short ends in it)
PAD = 0.05


def kinds():
    """{key: title} of the reports a sheet can show, in menu order."""
    return {"bom": "Bill of materials", "wires": "Wire list", "terminals": "Terminal strip list",
            "terminal_plan": "Terminal plan", "wiring": "Device wiring list",
            "pull": "Pull list", "materials": "Panel materials",
            "missing_fp": "Devices without a footprint"}


def table(project, key):
    """(header, rows) of a report, from the drawing as it is."""
    from . import bom, materials, missing_fp, panelwiring, pull, reports, strips
    if key == "bom":
        return bom.table(project)
    if key == "wires":
        return reports.WIRE_HEAD, reports.wire_rows(project)
    if key == "terminals":
        return reports.TERM_HEAD, reports.terminal_rows(project)
    if key == "terminal_plan":
        return strips.table(project)
    if key == "wiring":
        return panelwiring.table(project)
    if key == "pull":
        return pull.table(project)
    if key == "materials":
        return materials.table(project)
    if key == "missing_fp":
        return missing_fp.table(project)
    raise KeyError(key)


def _fit(text, width):
    """text cut to width (paper inches, as the program measures text: model.text_width)
    with an ellipsis when it doesn't fit."""
    room = width - 2 * PAD
    if M.text_width(text, TEXT_H) <= room:
        return text
    lo, hi = 0, len(text)
    while lo < hi:                      # (the longest start that fits with the ellipsis)
        mid = (lo + hi + 1) // 2
        if M.text_width(text[:mid] + ELLIPSIS, TEXT_H) <= room:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo] + ELLIPSIS if lo else ""


def _widths(head, rows, room):
    """Column widths (paper inches) in proportion to what they hold, fitting room."""
    want = []
    for i, h in enumerate(head):
        cells = [str(h)] + [str(r[i]) for r in rows if i < len(r)]
        want.append(max(M.text_width(c[:60], TEXT_H) for c in cells) + 2 * PAD)
    total = sum(want) or 1.0
    if total <= room:
        return want
    # (short of room, the wide columns give it up: each column keeps what four characters need,
    # or less when it wants less; the rest shared out in proportion to what more each wants.
    # Shrunk all alike, the BOM's Item column came out too narrow for "3", left empty, the
    # long battery's seed 4792)
    floor = [min(w, M.text_width("8888", TEXT_H) + 2 * PAD) for w in want]
    spare = room - sum(floor)
    if spare <= 0:
        f = room / (sum(floor) or 1.0)
        return [w * f for w in floor]
    more = sum(w - lo for w, lo in zip(want, floor)) or 1.0
    return [lo + (w - lo) * spare / more for w, lo in zip(want, floor)]


def free_box(area, tb):
    """The biggest box of the drawing area clear of the title block (paper inches): above or
    below it, or beside it, wherever it is (the battery's seed 453: a title block moved to the
    top left left a box 0.57" wide beside it, where 0.21 looked only above a bottom one or
    beside a right-hand one, and every cell of the report came out empty). The whole area when
    the title block is outside it."""
    x0, y0, x1, y1 = area
    if tb is None or tb[0] >= x1 or tb[2] <= x0 or tb[1] >= y1 or tb[3] <= y0:
        return area
    boxes = [(x0, y0, x1, min(y1, tb[1])), (x0, max(y0, tb[3]), x1, y1),
             (x0, y0, min(x1, tb[0]), y1), (max(x0, tb[2]), y0, x1, y1)]
    # (room for the header and a few rows first, then the most room)
    return max(boxes, key=lambda b: ((b[3] - b[1]) >= 4 * ROW_H and b[2] > b[0],
                                     max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])))


def pages(project, sheet, head, rows):
    """The table on as many pages as it takes: [[entities of a page]], drawn in sheet's units
    in the room its frame and title block leave (every page the same shape as sheet)."""
    from .scalefit import room
    k = sheet.k()
    area, tb = room(project, sheet)
    x0, y0, x1, y1 = free_box(area, tb)
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


LAYOUT = ("size", "cols", "rows", "col_start", "row_start", "rotation", "scale", "scale_name",
          "show_border", "show_title_block")


def _layout(shape):
    d = shape.meta_dict()
    return {k: d[k] for k in LAYOUT if k in d}


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
        # (every page laid out as the first, the table drawn for it: a page whose scale was
        # changed on its own drew the first page's table eight times too big, the battery's
        # seed 409)
        if i < len(old):
            s = old[i]
            for eid in list(s.entities):
                ed.remove(s, eid)
            ed.sheet_meta(s, title=name, **_layout(shape))
        else:
            s = project.make_sheet(name, "report")
            meta = s.meta_dict()
            meta.update(_layout(shape))
            s.set_meta(meta)
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
