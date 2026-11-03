"""A sheet's border, zone strips and title block, as plain entities (lines and texts), so the
screen, PDF and DXF all draw exactly the same frame.

The border and the zone strips (column numbers along the top, row letters down the left)
follow the sheet's size and zone counts. The title block is the project's own small drawing
(Project.title_block, edited with Edit title block): it is drawn in the lower right corner of
every sheet's drawing area, with every {Field} in its texts replaced by that field's value
(see fill_fields).
"""

import re

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
SHEET_FIELDS = ["Sheet", "Sheets", "Sheet title"]
_FIELD = re.compile(r"\{([^{}]+)\}")


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
    _cell(out, bx0, rows_y[0], bx0 + 1.5 * third, rows_y[1], "DRAWING NO.", "{Drawing number}")
    _cell(out, bx0 + 1.5 * third, rows_y[0], bx0 + 2 * third, rows_y[1], "REV", "{Revision}")
    _cell(out, bx0 + 2 * third, rows_y[0], bx1, rows_y[1], "SHEET", "{Sheet} OF {Sheets}")
    _cell(out, bx0, rows_y[1], bx0 + third, rows_y[2], "DRAWN BY", "{Drawn by}")
    _cell(out, bx0 + third, rows_y[1], bx0 + 2 * third, rows_y[2], "CHECKED BY", "{Checked by}")
    _cell(out, bx0 + 2 * third, rows_y[1], bx1, rows_y[2], "DATE", "{Date}")
    _cell(out, bx0, rows_y[2], bx0 + half, rows_y[3], "CUSTOMER", "{Customer}")
    _cell(out, bx0 + half, rows_y[2], bx1, rows_y[3], "PROJECT", "{Project}")
    _cell(out, bx0, rows_y[3], bx1, rows_y[4], "SHEET TITLE", "{Sheet title}", TITLE_H)
    return out


def field_values(project, sheet):
    v = dict(project.fields)
    v["Sheet"] = project.sheet_number(sheet)
    v["Sheets"] = str(len(project.sheets))
    v["Sheet title"] = sheet.title
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


def _title_block_offset(project, sheet):
    """How far the title block moves to sit in this sheet's corner: it is stored placed on
    the title block sheet (whose size may differ)."""
    tb = project.title_block
    tx1, ty0 = tb.frame()[2], tb.frame()[1]
    x1, y0 = sheet.frame()[2], sheet.frame()[1]
    return x1 - tx1, y0 - ty0


def title_block_entities(project, sheet):
    """The title block's entities placed on `sheet` with their fields filled in."""
    dx, dy = _title_block_offset(project, sheet)
    values = field_values(project, sheet)
    out = []
    for e in project.title_block.entities.values():
        c = e.moved(dx, dy) if (dx or dy) else e.copy()
        if isinstance(c, Text) and "{" in c.text:
            c = c.copy(text=fill_fields(c.text, values))
        c.id = None
        out.append(c)
    return out


def border_entities(sheet):
    """The border and the zone strips (column numbers along the top, row letters down the
    left), on layer BORDER."""
    out = []
    w, h = sheet.paper()
    m, s = sheet.MARGIN, sheet.STRIP
    _box(m, m, w - m, h - m, out, FRAME_LAYER)                  # border
    x0, y0, x1, y1 = sheet.frame()
    out.append(Line((x0, y1), (x1, y1), layer=FRAME_LAYER))     # under the column strip
    out.append(Line((x0, y0), (x0, y1), layer=FRAME_LAYER))     # right of the row strip
    cw = (x1 - x0) / sheet.cols
    rh = (y1 - y0) / sheet.rows
    th = min(0.12, s * 0.55)
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
    return out


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
    dx, dy = _title_block_offset(project, sheet)
    return (bb[0] + dx, bb[1] + dy, bb[2] + dx, bb[3] + dy)

