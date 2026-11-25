"""Printing sheets (File > Print...): any of a project's sheets on a printer or into a PDF file,
each on its own page, fit to the printer's paper (turned to match it) or at its real size:
the whole sheet, what is drawn on it (extents), what a window shows, or a window picked.

The same drawing as Export to PDF (render.SheetRenderer, black on white): only where it lands
on the page differs. QtPrintSupport is imported inside the functions that need it (start-up
stays light)."""

from PySide6.QtCore import Qt

from .sheetframe import printing

LINE_WIDTH = 0.008          # inches on the printed page (as Export to PDF)


def placement(paper_w, paper_h, page_w, page_h, fit=True, turn=None):
    """Where a sheet's paper (paper_w x paper_h inches; or the part of it printed) goes on a
    printer's page (the printable area, page_w x page_h inches): (turn, f, x, y). turn: the
    sheet is turned a quarter turn (counterclockwise) to match the page (None: when that
    suits it; False: never); f: page inches per sheet inch (fit: as big as the page holds,
    else 1, real size); (x, y): the top left corner of the sheet's paper as printed, from the
    page's top left (centered on the page; negative when a real-size sheet is bigger than the
    page, and the page shows its middle)."""
    def size(turned):
        return (paper_h, paper_w) if turned else (paper_w, paper_h)

    def scale(turned):
        w, h = size(turned)
        return min(page_w / w, page_h / h)
    if turn is None:
        if fit:
            turn = scale(True) > scale(False) + 1e-12
        else:
            # real size: turned when its long side and the page's don't match (less cut off)
            turn = (paper_w > paper_h) != (page_w > page_h) and \
                abs(paper_w - paper_h) > 1e-9 and abs(page_w - page_h) > 1e-9
    f = scale(turn) if fit else 1.0
    w, h = size(turn)
    return turn, f, (page_w - w * f) / 2, (page_h - h * f) / 2


AREAS = ("sheet", "extents", "display", "window")


def drawn_box(project, sheet):
    """The box (drawing units) of everything drawn on a sheet: its objects, and what is drawn
    beside them without being objects (cross-references, wire numbers), or None."""
    from . import wirenums, xrefs
    boxes = [sheet.extents()]
    if project is not None:
        boxes += [t.bbox() for t in xrefs.texts(project, sheet)]
        boxes += [t.bbox() for t in wirenums.labels(project, sheet)]
        boxes += [t.bbox() for t in wirenums.gauge_labels(project, sheet)]
    boxes = [b for b in boxes if b is not None]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes),
            max(b[3] for b in boxes))


def area_box(sheet, area="sheet", rect=None, project=None):
    """The part of a sheet printed, in its paper inches (x0, y0, x1, y1; y up from the paper's
    lower left): "sheet", its whole paper; "extents", everything drawn on it (drawn_box, a hair
    more for the lines' width; the whole paper with nothing drawn); "display" and "window",
    rect (in drawing units: what a window shows, or two corners picked)."""
    w, h = sheet.paper_inches()
    s = sheet.scale
    if area == "extents":
        rect = drawn_box(project, sheet)
        if rect is None:
            return (0.0, 0.0, w, h)
        m = max(rect[2] - rect[0], rect[3] - rect[1]) * s * 0.01 + 0.05
        b = tuple(c * s for c in rect)
        return (b[0] - m, b[1] - m, b[2] + m, b[3] + m)
    if area in ("display", "window") and rect is not None:
        x0, x1 = sorted((rect[0], rect[2]))
        y0, y1 = sorted((rect[1], rect[3]))
        if x1 - x0 > 1e-9 and y1 - y0 > 1e-9:
            return (x0 * s, y0 * s, x1 * s, y1 * s)
    return (0.0, 0.0, w, h)


def paint_sheet(painter, project, sheet, page_w, page_h, dpi, fit=True, mono=True,
                line_width=LINE_WIDTH, box=None, turn_ok=True):
    """Paint one sheet on a page of page_w x page_h inches at dpi device pixels an inch, the
    painter's origin at the page's top left (a printer's printable area, or a picture). box:
    the part printed (area_box; the whole paper when None), cut off at its edges; turn_ok:
    the part may be turned a quarter turn to match the page (Orientation: Automatic)."""
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QPainter
    from .render import SheetRenderer
    if box is None:
        box = area_box(sheet)
    bw, bh = box[2] - box[0], box[3] - box[1]
    turn, f, x, y = placement(bw, bh, page_w, page_h, fit)
    if not turn_ok and turn:
        turn, f, x, y = placement(bw, bh, page_w, page_h, fit, turn=False)
    painter.save()
    try:
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setClipRect(0, 0, round(page_w * dpi), round(page_h * dpi))
        painter.translate(x * dpi, y * dpi)         # (the printed part's top left)
        painter.scale(dpi * f, dpi * f)             # (now in paper inches, y down)
        if turn:
            # turned a quarter turn counterclockwise: its left edge along the bottom
            painter.translate(0, bw)
            painter.rotate(-90)
        painter.setClipRect(QRectF(0, 0, bw, bh), Qt.IntersectClip)
        # the paper's inches, y up, the part's top left at the origin; the drawing is in real
        # inches: a scaled panel sheet shrunk onto its paper
        painter.translate(-box[0], box[3])
        painter.scale(sheet.scale, -sheet.scale)
        with printing():                            # ({Print date}: now)
            # (line widths are the printed page's: as thin on a sheet shrunk to fit)
            SheetRenderer(project, sheet, dark=False, mono=mono).paint(
                painter, pen_width=line_width / f * sheet.k())
    finally:
        painter.restore()


def page_inches(printer):
    """(width, height) in inches of a printer's printable area (where its painter draws)."""
    from PySide6.QtPrintSupport import QPrinter
    r = printer.pageRect(QPrinter.DevicePixel)
    dpi = printer.resolution()
    return r.width() / dpi, r.height() / dpi


def print_sheets(project, printer, sheets, fit=True, mono=True, area="sheet", rect=None,
                 turn_ok=True):
    """Print sheets (in that order) on a QPrinter, one a page: their area (area_box) fit to
    the page or at its real size. Returns the page count."""
    from PySide6.QtGui import QPainter
    sheets = list(sheets)
    if not sheets:
        return 0
    painter = QPainter()
    if not painter.begin(printer):
        from PySide6.QtPrintSupport import QPrinter
        if printer.outputFormat() == QPrinter.PdfFormat:
            # (a PDF file that can't be opened for writing: open in another program, 0.26)
            import errno
            raise PermissionError(errno.EACCES, "the PDF file couldn't be written",
                                  printer.outputFileName())
        raise OSError("the printer couldn't start printing (is it on and connected?)")
    try:
        dpi = printer.resolution()
        pw, ph = page_inches(printer)
        for i, s in enumerate(sheets):
            if i:
                printer.newPage()
            paint_sheet(painter, project, s, pw, ph, dpi, fit, mono,
                        box=area_box(s, area, rect, project), turn_ok=turn_ok)
    finally:
        painter.end()
    return len(sheets)


def pdf_printer(path, page_size=None, resolution=300):
    """A QPrinter that writes a PDF file (the Print window's "PDF file", and the tests)."""
    from PySide6.QtGui import QPageSize
    from PySide6.QtPrintSupport import QPrinter
    pr = QPrinter(QPrinter.HighResolution)
    pr.setOutputFormat(QPrinter.PdfFormat)
    pr.setOutputFileName(path)
    pr.setResolution(resolution)
    pr.setPageSize(page_size or QPageSize(QPageSize.Letter))
    return pr
