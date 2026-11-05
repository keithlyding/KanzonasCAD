"""A sheet's border, zone strips and title block, as plain entities (lines and texts), so the
screen, PDF and DXF all draw exactly the same frame.

The border and the zone strips (column numbers along the top, row letters down the left)
follow the sheet's size and zone counts. The title block is the project's own small drawing
(Project.title_block, edited with Edit title block): it is drawn in the lower right corner of
every sheet's drawing area, with every {Field} in its texts replaced by that field's value
(see fill_fields).
"""

import re
from contextlib import contextmanager

from .model import Line, Text

FRAME_LAYER = "BORDER"

# the default title block, inches
TB_WIDTH = 6.5
TB_ROW = 0.3125
TB_TITLE_ROW = 0.4375
LABEL_H = 0.055
VALUE_H = 0.1
TITLE_H = 0.16

# fields every title block can use besides the project's own (Project properties)
SHEET_FIELDS = ["Sheet", "Sheets", "Sheet title", "Print date"]
_FIELD = re.compile(r"\{([^{}]+)\}")
# the revision history's fields: the latest revision's, and "Rev 1" (the latest), "Rev 2"
# (the one before)... for a revision table in the title block
REV_FIELDS = ["Revision date", "Revision description", "Revision by"]
REV_ROWS = 20
_REV_ROW = re.compile(r"Rev \d+( date| description| by)?$")


def is_auto_field(name):
    """A field KanzonasCAD fills by itself (not one to type in Project properties)."""
    return name in SHEET_FIELDS or name == "Scale" or name in REV_FIELDS or \
        bool(_REV_ROW.match(name))


_printing = []                  # the moment of a PDF or DXF export under way (printing())


@contextmanager
def printing():
    """While a PDF or DXF is written: {Print date} is the date and time of it (on screen, it
    is today's date)."""
    _printing.append(stamp_now())
    try:
        yield
    finally:
        _printing.pop()


def stamp_now():
    """Now, as the print stamp writes it: 11/05/2026 3:14 PM."""
    import datetime
    t = datetime.datetime.now()
    return "%s %d:%02d %s" % (t.strftime("%m/%d/%Y"), t.hour % 12 or 12, t.minute,
                              "AM" if t.hour < 12 else "PM")


def print_date():
    """{Print date}: the export's moment while one is written, else today's date."""
    if _printing:
        return _printing[-1]
    from .model import today_text
    return today_text()


def sheet_revisions(project, sheet):
    """The revisions that apply to a sheet (all of them, or those naming it), oldest
    first."""
    return [r for r in project.revisions
            if r.get("sheets") is None or sheet.id in r["sheets"]]


def _box(x0, y0, x1, y1, out, layer="0"):
    out += [Line((x0, y0), (x1, y0), layer=layer), Line((x1, y0), (x1, y1), layer=layer),
            Line((x1, y1), (x0, y1), layer=layer), Line((x0, y1), (x0, y0), layer=layer)]


def _cell(out, x0, y0, x1, y1, label, value, value_h=VALUE_H):
    _box(x0, y0, x1, y1, out)
    out.append(Text((x0 + 0.04, y1 - 0.04 - LABEL_H), label, LABEL_H))
    if value:
        out.append(Text((x0 + 0.06, y0 + (y1 - y0 - LABEL_H) / 2 - value_h / 2 + 0.01), value,
                        value_h))


def default_title_block(sheet):
    """The title block a new project starts with, placed in the lower right corner of the
    drawing area of `sheet` (its texts hold {fields})."""
    out = []
    x0, y0, x1, _y1 = sheet.frame()
    tw = min(TB_WIDTH, x1 - x0)
    bx0, bx1 = x1 - tw, x1
    rows_y = [y0, y0 + TB_ROW, y0 + 2 * TB_ROW, y0 + 3 * TB_ROW,
              y0 + 3 * TB_ROW + TB_TITLE_ROW]
    third = tw / 3
    half = tw / 2
    q = tw / 6.5                # (the drawn-by row's four cells: 1.75, 1.5, 1.75, 1.5 in)
    _cell(out, bx0, rows_y[0], bx0 + 1.5 * third, rows_y[1], "DRAWING NO.", "{Drawing number}")
    _cell(out, bx0 + 1.5 * third, rows_y[0], bx0 + 2 * third, rows_y[1], "REV", "{Revision}")
    _cell(out, bx0 + 2 * third, rows_y[0], bx1, rows_y[1], "SHEET", "{Sheet} OF {Sheets}")
    xs = [bx0, bx0 + 1.75 * q, bx0 + 3.25 * q, bx0 + 5.0 * q, bx1]
    for (label, value), a, b in zip((("DRAWN BY", "{Drawn by}"), ("DRAWN", "{Drawn date}"),
                                     ("CHECKED BY", "{Checked by}"), ("REV DATE", "{Date}")),
                                    xs, xs[1:]):
        _cell(out, a, rows_y[1], b, rows_y[2], label, value)
    _cell(out, bx0, rows_y[2], bx0 + half, rows_y[3], "CUSTOMER", "{Customer}")
    _cell(out, bx0 + half, rows_y[2], bx1, rows_y[3], "PROJECT", "{Project}")
    _cell(out, bx0, rows_y[3], bx1, rows_y[4], "SHEET TITLE", "{Sheet title}", TITLE_H)
    out.append(_stamp(bx1 - 0.12, rows_y[3] + 0.03))      # (inside the title cell, low)
    return out


def _stamp(x, y):
    """The print stamp (when the paper copy was made), small, its right end at x (kept inside
    the title block: its outline sets a strip's size)."""
    return Text((x, y), "PRINTED {Print date}", LABEL_H, align="right")


STRIP_W = 1.75                  # a right-hand strip title block's width
STRIP_ROW = 0.375               # its rows' height (and a bottom strip's height, twice)
STRIP_FIELDS = [("SHEET", "{Sheet} OF {Sheets}"), ("REV", "{Revision}"),
                ("DRAWING NO.", "{Drawing number}"), ("SCALE", "{Scale}"),
                ("REV DATE", "{Date}"), ("CHECKED BY", "{Checked by}"),
                ("DRAWN", "{Drawn date}"), ("DRAWN BY", "{Drawn by}"),
                ("PROJECT", "{Project}"), ("CUSTOMER", "{Customer}")]


def strip_title_block(sheet, side):
    """A title block made for a strip (Project properties, Title block position): down the
    right ("right": cells stacked from the bottom, the sheet title above them, room for a logo
    or notes at the top) or along the bottom ("bottom": one row of cells across)."""
    out = []
    x0, y0, x1, y1 = sheet.frame()
    if side == "right":
        bx0 = x1 - STRIP_W
        _box(bx0, y0, x1, y1, out)
        y = y0
        for label, value in STRIP_FIELDS:
            _cell(out, bx0, y, x1, y + STRIP_ROW, label, value)
            y += STRIP_ROW
        _cell(out, bx0, y, x1, y + 2 * STRIP_ROW, "SHEET TITLE", "{Sheet title}", TITLE_H)
        out.append(_stamp(x1 - 0.12, y1 - 0.06 - LABEL_H))
        return out
    h = 2 * STRIP_ROW
    cells = [("CUSTOMER", "{Customer}", 2.0), ("PROJECT", "{Project}", 2.0),
             ("SHEET TITLE", "{Sheet title}", 3.0), ("DRAWN BY", "{Drawn by}", 1.0),
             ("DRAWN", "{Drawn date}", 0.9), ("CHECKED BY", "{Checked by}", 1.0),
             ("REV DATE", "{Date}", 0.9),
             ("SCALE", "{Scale}", 0.9), ("DRAWING NO.", "{Drawing number}", 1.6),
             ("REV", "{Revision}", 0.5), ("SHEET", "{Sheet} OF {Sheets}", 0.9)]
    total = sum(c[2] for c in cells)
    k = (x1 - x0) / total
    x = x0
    for label, value, w in cells:
        _cell(out, x, y0, x + w * k, y0 + h, label, value,
              TITLE_H if label == "SHEET TITLE" else VALUE_H)
        if label == "SHEET TITLE":
            out.append(_stamp(x + w * k - 0.12, y0 + 0.03))   # (inside the title cell, low)
        x += w * k
    return out


def field_values(project, sheet):
    v = dict(project.fields)
    v["Sheet"] = project.sheet_number(sheet)
    v["Sheets"] = str(len(project.sheets))
    v["Sheet title"] = sheet.title
    v["Scale"] = sheet.scale_text()
    v["Print date"] = print_date()
    # (a project from before Drawn date: the date typed in Project properties)
    if not str(v.get("Drawn date", "")).strip():
        v["Drawn date"] = project.fields.get("Date", "")
    # the revision history: the latest revision that applies to this sheet gives {Revision}
    # and {Date}; Rev 1 is the latest, Rev 2 the one before... (empty past the oldest)
    hist = sheet_revisions(project, sheet) if getattr(project, "revisions", None) else []
    for k in REV_FIELDS:
        v[k] = ""
    if hist:
        last = hist[-1]
        v["Revision"], v["Date"] = last["rev"], last["date"]
        v["Revision date"], v["Revision description"], v["Revision by"] = \
            last["date"], last["desc"], last["by"]
    for i in range(1, REV_ROWS + 1):
        r = hist[-i] if i <= len(hist) else None
        v["Rev %d" % i] = r["rev"] if r else ""
        v["Rev %d date" % i] = r["date"] if r else ""
        v["Rev %d description" % i] = r["desc"] if r else ""
        v["Rev %d by" % i] = r["by"] if r else ""
    # a sheet's own value of a field (its own revision, say) wins over the project's
    for k, val in sheet.fields.items():
        if str(val).strip():
            v[k] = str(val)
    return v


def fill_fields(text, values):
    """{Name} -> the value of field Name. A name that isn't a field stays as typed (so a typo
    shows on the sheet instead of vanishing)."""
    return _FIELD.sub(lambda m: values.get(m.group(1), m.group(0)), text)


def fields_used(project):
    """Field names the title block's texts use, in the order they appear."""
    out = []
    for e in project.title_block.entities.values():
        if isinstance(e, Text):
            for name in _FIELD.findall(e.text):
                if name not in out:
                    out.append(name)
    return out


def _title_block_place(project, sheet):
    """(its corner on the title block sheet, the move to this sheet's corner, factor): the
    title block is stored placed on the title block sheet (whose size may differ) and is drawn
    in this sheet's corner, enlarged by the sheet's factor on a scaled panel sheet (so it
    prints the same size)."""
    tb = project.title_block
    tx1, ty0 = tb.layout_frame()[2], tb.layout_frame()[1]
    x1, y0 = sheet.layout_frame()[2], sheet.layout_frame()[1]
    k = sheet.k() if sheet is not tb else 1.0
    return (tx1, ty0), (x1 - tx1, y0 - ty0), k


def title_block_entities(project, sheet):
    """The title block's entities placed on `sheet` with their fields filled in."""
    corner, (dx, dy), k = _title_block_place(project, sheet)
    values = field_values(project, sheet)
    out = []
    for e in project.title_block.entities.values():
        c = e.scaled(corner, k) if k != 1.0 else e
        c = c.moved(dx, dy) if (dx or dy) else c.copy()
        if isinstance(c, Text) and "{" in c.text:
            c = c.copy(text=fill_fields(c.text, values))
        c.id = None
        out.append(c)
    return _turned(sheet, out)


def _turned(sheet, ents):
    """The frame's entities, laid out unturned, turned with the sheet."""
    r = sheet.rotation if sheet is not None else 0
    if not r:
        return ents
    dx, dy = sheet.turn_offset()
    return [e.rotated((0.0, 0.0), r).moved(dx, dy) for e in ents]


def border_entities(sheet):
    """The border and the zone strips (column numbers along the top, row letters down the
    left), on layer BORDER."""
    out = []
    w, h = sheet.landscape_paper()
    k = sheet.k()
    m, s = sheet.MARGIN * k, sheet.STRIP * k
    _box(m, m, w - m, h - m, out, FRAME_LAYER)                  # border
    fx0, fy0, fx1, fy1 = sheet.layout_frame()
    x0, y0, x1, y1 = sheet.layout_zone_frame()  # (smaller than the frame beside a title strip)
    out.append(Line((fx0, fy1), (fx1, fy1), layer=FRAME_LAYER))  # under the column strip
    out.append(Line((fx0, fy0), (fx0, fy1), layer=FRAME_LAYER))  # right of the row strip
    if x1 < fx1 - 1e-9:                         # the title block strip down the right
        out.append(Line((x1, fy0), (x1, fy1 + s), layer=FRAME_LAYER))
    if y0 > fy0 + 1e-9:                         # the title block strip along the bottom
        out.append(Line((fx0 - s, y0), (fx1, y0), layer=FRAME_LAYER))
    cw = (x1 - x0) / sheet.cols
    rh = (y1 - y0) / sheet.rows
    th = min(0.12 * k, s * 0.55)
    for i in range(sheet.cols):
        if i:
            xx = x0 + i * cw
            out.append(Line((xx, y1), (xx, y1 + s), layer=FRAME_LAYER))
        out.append(Text((x0 + (i + 0.5) * cw, y1 + (s - th) / 2), str(sheet.col_labels()[i]), th,
                        align="center", layer=FRAME_LAYER))
    letters = sheet.row_labels()
    for j in range(sheet.rows):
        if j:
            yy = y1 - j * rh
            out.append(Line((x0 - s, yy), (x0, yy), layer=FRAME_LAYER))
        out.append(Text((x0 - s / 2, y1 - (j + 0.5) * rh - th / 2), letters[j], th,
                        align="center", layer=FRAME_LAYER))
    return _turned(sheet, out)


def frame_entities(project, sheet):
    """Border, zones and (on a real sheet) the filled-in title block."""
    out = border_entities(sheet)
    if sheet is not project.title_block:
        out += title_block_entities(project, sheet)
    return out


def title_block_rect(project, sheet):
    """The title block's box on `sheet`, or None when it is empty."""
    bb = project.title_block.extents()
    if bb is None:
        return None
    (cx, cy), (dx, dy), k = _title_block_place(project, sheet)
    return sheet.turn_rect(((bb[0] - cx) * k + cx + dx, (bb[1] - cy) * k + cy + dy,
                            (bb[2] - cx) * k + cx + dx, (bb[3] - cy) * k + cy + dy))

