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
            tb = (r[0] / k - MARGIN, r[1] / k, r[2] / k, r[3] / k + MARGIN)
    return area, tb


def free_boxes(area, tb):
    """The rectangles (paper inches) a drawing can sit in without touching the title block:
    the whole area, or, with a title block in the corner, the part above it and the part
    left of it (the largest first)."""
    if tb is None or tb[0] >= area[2] or tb[3] <= area[1]:
        return [area]
    above = (area[0], max(area[1], tb[3]), area[2], area[3])
    left = (area[0], area[1], min(area[2], tb[0]), area[3])
    boxes = [b for b in (above, left) if b[2] > b[0] and b[3] > b[1]]
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
    if tb is not None and b[0] < tb[2] and b[2] > tb[0] + MARGIN + tol and \
            b[1] < tb[3] - MARGIN - tol and b[3] > tb[1]:
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


def apply(project, sheet, name, scale, cabinet=False, center=False):
    """Give a sheet a scale in one undoable edit, with (when cabinet isn't False) its cabinet
    size, and (center) what is drawn moved to the middle of the room it fits best at that
    scale. Returns (dx, dy) moved, or None."""
    moved = None
    if center:
        box = drawing_box(sheet)
        if box is not None:
            area, tb = room(project, sheet)
            moved = centering(box, scale, area, tb)
    changes = abs(scale - sheet.scale) > 1e-12 or name != sheet.scale_name
    new_cab = M._cabinet(cabinet) if cabinet is not False else sheet.cabinet
    if not changes and new_cab == sheet.cabinet and not moved:
        return None
    with project.edit("Sheet scale") as ed:
        if changes:
            ed.sheet_scale(sheet, scale, name)
        if new_cab != sheet.cabinet:
            ed.sheet_meta(sheet, cabinet=new_cab)
        if moved and (abs(moved[0]) > 1e-9 or abs(moved[1]) > 1e-9):
            for e in list(sheet.entities.values()):
                ed.change(sheet, e.moved(*moved))
    return moved
