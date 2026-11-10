"""Choosing a panel sheet's scale: the room a sheet has, what fits at which scale, the best
scale, and a scale in plain words. No Qt (the Sheet scale window, dialogs.SheetScaleDialog,
shows what this works out).

Everything here is in two kinds of units: paper inches (what prints) and real inches (the
drawing, which is real size). At a scale s (paper / real, 1:4 = 0.25) a real length L prints
L * s long.
"""
import math

from . import model as M

GAP = 6.0           # real inches between a cabinet's front and its side, when Fit leaves room
MARGIN = 0.25       # paper inches kept clear inside the zone frame and around the title block


def room(project, sheet):
    """What a sheet has room for, in paper inches (the same at every scale): (x0, y0, x1, y1)
    of the zone frame less MARGIN, and the corner title block's box (or None: a title block
    strip is already outside the zone frame, or there is none)."""
    k = sheet.k()
    x0, y0, x1, y1 = sheet.zone_frame()
    area = (x0 / k + MARGIN, y0 / k + MARGIN, x1 / k - MARGIN, y1 / k - MARGIN)
    tb = None
    if not sheet.reserve and sheet is not project.title_block:
        from .sheetframe import title_block_rect
        r = title_block_rect(project, sheet)
        if r is not None:
            tb = (r[0] / k - MARGIN, r[1] / k - MARGIN, r[2] / k + MARGIN, r[3] / k + MARGIN)
    return area, tb


def as_rotated(sheet, rotation):
    """A stand-in for `sheet` turned to `rotation` (degrees counterclockwise: 0, 90, 180,
    270), for asking room() what that would give. The sheet itself if it is already so."""
    if sheet.rotation == rotation:
        return sheet
    tmp = M.Sheet(size=sheet.size, cols=sheet.cols, rows=sheet.rows)
    tmp.scale, tmp.scale_name, tmp.reserve = sheet.scale, sheet.scale_name, sheet.reserve
    tmp.rotation = rotation
    return tmp


def quarter_turn(rotation):
    """The rotation a quarter turn clockwise from `rotation` (Rotate sheet clockwise)."""
    return (rotation - 90) % 360


def other_way(project, sheet, w, h, named=False):
    """(rotation, (name, scale)) when a quarter turn (clockwise) lets a drawing w x h (real
    inches) print bigger than the sheet as it is turned now, else None."""
    here = best_scale(w, h, *room(project, sheet), named=named)
    r = quarter_turn(sheet.rotation)
    there = best_scale(w, h, *room(project, as_rotated(sheet, r)), named=named)
    return (r, there) if there[1] > here[1] + 1e-12 else None


def free_boxes(area, tb):
    """The rectangles (paper inches) a drawing can sit in without touching the title block:
    the whole area, or, with a title block in a corner (wherever the sheet's turn put it),
    the parts beside it, above or below it (the largest first)."""
    if tb is None or tb[0] >= area[2] or tb[2] <= area[0] or tb[1] >= area[3] or \
            tb[3] <= area[1]:
        return [area]
    a0, a1, a2, a3 = area
    cands = [(a0, a1, min(a2, tb[0]), a3), (max(a0, tb[2]), a1, a2, a3),
             (a0, a1, a2, min(a3, tb[1])), (a0, max(a1, tb[3]), a2, a3)]
    boxes = [b for b in cands if b[2] - b[0] > 1e-6 and b[3] - b[1] > 1e-6]
    boxes.sort(key=lambda b: -(b[2] - b[0]) * (b[3] - b[1]))
    return boxes


def fits(w, h, scale, area, tb):
    """True when a drawing w x h (real inches) printed at `scale` fits in one of the free
    boxes."""
    pw, ph = w * scale, h * scale
    return any(pw <= b[2] - b[0] + 1e-9 and ph <= b[3] - b[1] + 1e-9
               for b in free_boxes(area, tb))


def use(w, h, scale, area, tb):
    """How much of the room a drawing w x h takes at `scale`: the larger of its share of the
    best box's width and height (1.0 = it just fits; over 1: it doesn't)."""
    pw, ph = w * scale, h * scale
    best = None
    for b in free_boxes(area, tb):
        u = max(pw / max(b[2] - b[0], 1e-9), ph / max(b[3] - b[1], 1e-9))
        best = u if best is None else min(best, u)
    return best if best is not None else math.inf


def cabinet_box(cabinet):
    """The real size (w, h) a cabinet's drawing needs: its front, and its side beside it
    (GAP apart) when the depth is given. None when there is no size."""
    if not cabinet:
        return None
    w, h = float(cabinet[0]), float(cabinet[1])
    d = float(cabinet[2]) if len(cabinet) > 2 and cabinet[2] else 0.0
    if w <= 0 or h <= 0:
        return None
    return (w + GAP + d, h) if d > 0 else (w, h)


def drawing_box(sheet):
    """The box (real inches) of what is drawn on the sheet, or None (kept per sheet version:
    the status bar asks on every change)."""
    got = getattr(sheet, "_fit_box", None)
    if got is None or got[0] != sheet.version:
        got = sheet._fit_box = (sheet.version, sheet.extents())
    return got[1]


def presets_like(sheet_name):
    """The scale presets to choose among: architectural ones (3" = 1'-0"...) for a sheet whose
    scale has such a name, 1:N ones otherwise; biggest print first."""
    named = bool(sheet_name)
    out = [(n, v) for n, v in M.SCALE_PRESETS if bool(n) == named]
    if named:
        out.append(("", 1.0))
    out.sort(key=lambda t: -t[1])
    return out


def best_scale(w, h, area, tb, named=False):
    """(name, scale): the biggest preset (architectural ones when `named`) at which a drawing
    w x h (real inches) fits; past the presets, the next whole 1:N that does."""
    for name, v in presets_like("x" if named else ""):
        if fits(w, h, v, area, tb):
            return name, v
    n = max(1, int(math.ceil(use(w, h, 1.0, area, tb) - 1e-9)))
    while not fits(w, h, 1.0 / n, area, tb) and n < 100000:
        n += 1
    return "", 1.0 / n


def in_words(scale, name=""):
    """A scale in plain words: '1 inch on paper = 4 inches of panel'."""
    if name and "=" in name:
        paper, real = (t.strip() for t in name.split("=", 1))
        return "%s on paper = %s of panel" % (_spoken(paper), _spoken(real))
    if abs(scale - 1.0) < 1e-9:
        return "Printed at real size: 1 inch on paper = 1 inch of panel"
    if scale < 1:
        return "1 inch on paper = %s inches of panel" % _num(1.0 / scale)
    return "%s inches on paper = 1 inch of panel" % _num(scale)


def _num(x):
    return ("%d" % round(x)) if abs(x - round(x)) < 1e-9 else ("%.3g" % x)


def _spoken(t):
    """3" -> 3 inches, 1'-0" -> 1 foot, 1-1/2" -> 1-1/2 inches."""
    t = t.replace(" ", "")
    if t in ("1'-0\"", "1'"):
        return "1 foot"
    if t.endswith('"'):
        n = t[:-1]
        # (1 inch, 1/4 inch, 3/4 inch; 3 inches, 1-1/2 inches)
        one = n == "1" or ("/" in n and "-" not in n)
        return ("%s inch" if one else "%s inches") % n
    return t


def outside(project, sheet):
    """Why what is drawn doesn't fit the sheet as it is placed now: 'past the border' or
    'over the title block', or None when it fits (or nothing is drawn)."""
    box = drawing_box(sheet)
    if box is None:
        return None
    k = sheet.k()
    area, tb = room(project, sheet)
    b = tuple(c / k for c in box)                       # paper inches
    tol = 0.01
    # (the margins are what Fit keeps clear, not the limit: the limit is the frame itself)
    if b[0] < area[0] - MARGIN - tol or b[1] < area[1] - MARGIN - tol or \
            b[2] > area[2] + MARGIN + tol or b[3] > area[3] + MARGIN + tol:
        return "past the border"
    if tb is not None:
        t = (tb[0] + MARGIN, tb[1] + MARGIN, tb[2] - MARGIN, tb[3] - MARGIN)  # (the block)
        if b[0] < t[2] - tol and b[2] > t[0] + tol and b[1] < t[3] - tol and \
                b[3] > t[1] + tol:
            return "over the title block"
    return None


def centering(box, scale, area, tb):
    """(dx, dy) in real inches that puts a drawing box (real inches) in the middle of the
    free box it fits best at `scale`, or None when it fits none."""
    w, h = box[2] - box[0], box[3] - box[1]
    pw, ph = w * scale, h * scale
    for b in free_boxes(area, tb):
        if pw <= b[2] - b[0] + 1e-9 and ph <= b[3] - b[1] + 1e-9:
            cx, cy = (b[0] + b[2]) / 2 / scale, (b[1] + b[3]) / 2 / scale
            return cx - (box[0] + box[2]) / 2, cy - (box[1] + box[3]) / 2
    return None


def placed_inside(box, scale, area, tb):
    """True when a drawing box (real inches) at `scale`, where it is, lies inside one of the
    free boxes."""
    b = tuple(c * scale for c in box)
    return any(b[0] >= f[0] - 1e-6 and b[1] >= f[1] - 1e-6 and b[2] <= f[2] + 1e-6 and
               b[3] <= f[3] + 1e-6 for f in free_boxes(area, tb))


def fit_for(project, sheet):
    """(name, scale) Fit picks for a sheet: from what is drawn, or, with nothing drawn, from
    its cabinet size (front and side). None when there is neither."""
    box = drawing_box(sheet)
    if box is not None:
        w, h = box[2] - box[0], box[3] - box[1]
    else:
        cb = cabinet_box(sheet.cabinet)
        if cb is None:
            return None
        w, h = cb
    area, tb = room(project, sheet)
    return best_scale(w, h, area, tb, named=bool(sheet.scale_name))


def turned_offset(project, sheet, rotation, scale=None):
    """(dx, dy) real inches that keeps what is drawn on the page when the sheet is turned to
    `rotation` (at `scale`, the sheet's own when None): the same distance from the paper's
    middle, or, when that leaves it outside, the middle of the room it fits best. None when
    nothing is drawn or nothing need move."""
    box = drawing_box(sheet)
    if box is None:
        return None
    scale = sheet.scale if scale is None else scale
    tmp = as_rotated(sheet, rotation)
    tmp_scaled = M.Sheet(size=tmp.size)
    tmp_scaled.rotation, tmp_scaled.scale, tmp_scaled.reserve = rotation, scale, tmp.reserve
    w0, h0 = (v / scale for v in sheet.paper_inches())     # (both papers at the new scale)
    w1, h1 = (v / scale for v in tmp_scaled.paper_inches())
    dx, dy = (w1 - w0) / 2, (h1 - h0) / 2
    moved = (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)
    area, tb = room(project, tmp_scaled)
    if not placed_inside(moved, scale, area, tb):
        c = centering(box, scale, area, tb)
        if c is not None:
            dx, dy = c
    return (dx, dy) if abs(dx) > 1e-9 or abs(dy) > 1e-9 else None


def apply(project, sheet, name, scale, cabinet=False, center=False, rotation=None,
          paper_text=True):
    """Give a sheet a scale in one undoable edit, with (when cabinet isn't False) its cabinet
    size, (rotation) the sheet turned, and (center) what is drawn moved to the middle of the
    room it fits best at that scale (turned, what is drawn is kept on the page anyway).
    Returns (dx, dy) moved, or None."""
    rotation = sheet.rotation if rotation is None else rotation % 360
    turn = rotation != sheet.rotation
    moved = None
    if center:
        box = drawing_box(sheet)
        if box is not None:
            area, tb = room(project, as_rotated(sheet, rotation))
            moved = centering(box, scale, area, tb)
    elif turn:
        moved = turned_offset(project, sheet, rotation, scale)
    changes = abs(scale - sheet.scale) > 1e-12 or name != sheet.scale_name
    new_cab = M._cabinet(cabinet) if cabinet is not False else sheet.cabinet
    if not changes and new_cab == sheet.cabinet and not moved and not turn:
        return None
    with project.edit("Rotate sheet" if turn and not changes else "Sheet scale") as ed:
        if turn:
            ed.sheet_meta(sheet, rotation=rotation)
        if changes:
            ed.sheet_scale(sheet, scale, name, paper_text)
        if new_cab != sheet.cabinet:
            ed.sheet_meta(sheet, cabinet=new_cab)
        if moved and (abs(moved[0]) > 1e-9 or abs(moved[1]) > 1e-9):
            for e in list(sheet.entities.values()):
                ed.change(sheet, e.moved(*moved))
    return moved


ROTATIONS = [(0, "Upright (as laid out)"), (270, "Turned clockwise"), (180, "Upside down"),
             (90, "Turned counterclockwise")]


def rotate(project, sheet, clockwise=True):
    """Turn a sheet a quarter turn (Rotate sheet clockwise / counterclockwise): its border,
    zones and title block with it, the drawing upright and kept on the page. One undoable
    edit. Returns the new rotation."""
    r = (sheet.rotation + (-90 if clockwise else 90)) % 360
    apply(project, sheet, sheet.scale_name, sheet.scale, rotation=r)
    return r


def placement(project, sheet, box):
    """Where place_on_sheet puts a drawing whose box is box: None (left where it is), or
    (rescale, scale name, scale, dx, dy). Also used before a drawing is added (opening a big
    DWG: its pieces placed once instead of added, then moved)."""
    if box is None:
        return None
    k = sheet.k()
    w, h = sheet.paper()
    tol = 0.01 * k
    if box[0] >= -tol and box[1] >= -tol and box[2] <= w + tol and box[3] <= h + tol:
        return None
    area, tb = room(project, sheet)
    bw, bh = box[2] - box[0], box[3] - box[1]
    name, v = sheet.scale_name, sheet.scale
    rescale = not fits(bw, bh, v, area, tb)
    if rescale:
        name, v = best_scale(bw, bh, area, tb, named=bool(sheet.scale_name))
    dx, dy = centering(box, v, area, tb)
    return rescale, name, v, dx, dy


def place_on_sheet(project, sheet):
    """A drawing opened from a DXF or DWG put on the page (its coordinates are the other
    program's: often far from KanzonasCAD's sheet). Left where it is when it already lies on
    the paper (a DXF exported from KanzonasCAD, border and all, or one drawn on a sheet of
    this size); else moved to the middle of the free room at the sheet's scale when it fits;
    else the sheet gets the biggest scale it fits at (Fit; the drawing stays real size) and
    it is centered. Returns what was done: None, "moved" or the new scale's text."""
    plan = placement(project, sheet, drawing_box(sheet))
    if plan is None:
        return None
    rescale, name, v, dx, dy = plan
    with project.edit("Place the drawing") as ed:
        if rescale:
            # (sheet_meta, not sheet_scale: the DXF's texts are its own real size, not
            # KanzonasCAD's paper-sized ones, and keep their height)
            ed.sheet_meta(sheet, scale=float(v), scale_name=name)
        for e in list(sheet.entities.values()):
            ed.change(sheet, e.moved(dx, dy))
    return sheet.scale_text() if rescale else "moved"
