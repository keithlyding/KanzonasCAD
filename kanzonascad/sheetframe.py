"""A sheet's border, zone grid and title block, as plain entities (lines and texts), so the
screen, PDF and DXF all draw exactly the same frame. They are not part of the sheet's
entities: they follow the sheet's size, zones and the project's title block fields."""

from .model import Line, Text, row_letters

FRAME_LAYER = "BORDER"

# title block, inches
TB_WIDTH = 6.5
TB_ROW = 0.3125
TB_TITLE_ROW = 0.4375
LABEL_H = 0.055
VALUE_H = 0.1
TITLE_H = 0.16


def _box(x0, y0, x1, y1, out):
    out += [Line((x0, y0), (x1, y0)), Line((x1, y0), (x1, y1)), Line((x1, y1), (x0, y1)),
            Line((x0, y1), (x0, y0))]


def _cell(out, x0, y0, x1, y1, label, value, value_h=VALUE_H):
    _box(x0, y0, x1, y1, out)
    out.append(Text((x0 + 0.04, y1 - 0.04 - LABEL_H), label, LABEL_H))
    if value:
        out.append(Text((x0 + 0.06, y0 + (y1 - y0 - LABEL_H) / 2 - value_h / 2 + 0.01), value,
                        value_h))


def frame_entities(project, sheet):
    out = []
    w, h = sheet.paper()
    m, s = sheet.MARGIN, sheet.STRIP
    _box(m, m, w - m, h - m, out)                       # outer border
    x0, y0, x1, y1 = sheet.frame()
    _box(x0, y0, x1, y1, out)                           # drawing area
    # zone strips: column numbers along the top and bottom, row letters down both sides
    cw = (x1 - x0) / sheet.cols
    rh = (y1 - y0) / sheet.rows
    th = min(0.12, s * 0.55)
    for i in range(sheet.cols):
        cx = x0 + (i + 0.5) * cw
        if i:
            xx = x0 + i * cw
            out.append(Line((xx, y1), (xx, y1 + s)))
            out.append(Line((xx, y0 - s), (xx, y0)))
        for yy in (y1 + (s - th) / 2, y0 - s + (s - th) / 2):
            out.append(Text((cx, yy), str(i + 1), th, align="center"))
    letters = row_letters(sheet.rows)
    for j in range(sheet.rows):
        cy = y1 - (j + 0.5) * rh
        if j:
            yy = y1 - j * rh
            out.append(Line((x0 - s, yy), (x0, yy)))
            out.append(Line((x1, yy), (x1 + s, yy)))
        for xx in (x0 - s / 2, x1 + s / 2):
            out.append(Text((xx, cy - th / 2), letters[j], th, align="center"))
    # title block, bottom right of the drawing area
    f = project.fields
    tw = min(TB_WIDTH, x1 - x0)
    bx0, bx1 = x1 - tw, x1
    rows_y = [y0, y0 + TB_ROW, y0 + 2 * TB_ROW, y0 + 3 * TB_ROW,
              y0 + 3 * TB_ROW + TB_TITLE_ROW]
    total = len(project.sheets)
    num = project.sheet_number(sheet)
    third = tw / 3
    half = tw / 2
    # bottom row: drawing number, revision, sheet n of N
    _cell(out, bx0, rows_y[0], bx0 + 1.5 * third, rows_y[1], "DRAWING NO.", f.get("Drawing number", ""))
    _cell(out, bx0 + 1.5 * third, rows_y[0], bx0 + 2 * third, rows_y[1], "REV", f.get("Revision", ""))
    _cell(out, bx0 + 2 * third, rows_y[0], bx1, rows_y[1], "SHEET", "%s OF %d" % (num, total))
    _cell(out, bx0, rows_y[1], bx0 + third, rows_y[2], "DRAWN BY", f.get("Drawn by", ""))
    _cell(out, bx0 + third, rows_y[1], bx0 + 2 * third, rows_y[2], "CHECKED BY", f.get("Checked by", ""))
    _cell(out, bx0 + 2 * third, rows_y[1], bx1, rows_y[2], "DATE", f.get("Date", ""))
    _cell(out, bx0, rows_y[2], bx0 + half, rows_y[3], "CUSTOMER", f.get("Customer", ""))
    _cell(out, bx0 + half, rows_y[2], bx1, rows_y[3], "PROJECT", f.get("Project", ""))
    _cell(out, bx0, rows_y[3], bx1, rows_y[4], "SHEET TITLE", sheet.title.upper(), TITLE_H)
    for e in out:
        e.layer = FRAME_LAYER
    return out


def title_block_rect(sheet):
    x0, y0, x1, y1 = sheet.frame()
    tw = min(TB_WIDTH, x1 - x0)
    return (x1 - tw, y0, x1, y0 + 3 * TB_ROW + TB_TITLE_ROW)
