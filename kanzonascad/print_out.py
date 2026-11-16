"""Printing sheets (File > Print...): any of a project's sheets on a printer or into a PDF file,
each on its own page, fit to the printer's paper (turned to match it) or at its real size.

The same drawing as Export to PDF (render.SheetRenderer, black on white): only where it lands
on the page differs. QtPrintSupport is imported inside the functions that need it (start-up
stays light)."""

from .sheetframe import printing

LINE_WIDTH = 0.008          # inches on the printed page (as Export to PDF)


def placement(paper_w, paper_h, page_w, page_h, fit=True):
    """Where a sheet's paper (paper_w x paper_h inches) goes on a printer's page (the printable
    area, page_w x page_h inches): (turn, f, x, y). turn: the sheet is turned a quarter turn
    (counterclockwise) to match the page; f: page inches per sheet inch (fit: as big as the
    page holds, else 1, real size); (x, y): the top left corner of the sheet's paper as
    printed, from the page's top left (centered on the page; negative when a real-size sheet
    is bigger than the page, and the page shows its middle)."""
    def size(turn):
        return (paper_h, paper_w) if turn else (paper_w, paper_h)

    def scale(turn):
        w, h = size(turn)
        return min(page_w / w, page_h / h)
    if fit:
        turn = scale(True) > scale(False) + 1e-12
        f = scale(turn)
    else:
        # real size: turned when the sheet's long side and the page's don't match (less cut off)
        turn = (paper_w > paper_h) != (page_w > page_h) and abs(paper_w - paper_h) > 1e-9 \
            and abs(page_w - page_h) > 1e-9
        f = 1.0
    w, h = size(turn)
    return turn, f, (page_w - w * f) / 2, (page_h - h * f) / 2


def paint_sheet(painter, project, sheet, page_w, page_h, dpi, fit=True, mono=True,
                line_width=LINE_WIDTH):
    """Paint one sheet on a page of page_w x page_h inches at dpi device pixels an inch, the
    painter's origin at the page's top left (a printer's printable area, or a picture)."""
    from PySide6.QtGui import QPainter
    from .render import SheetRenderer
    w, h = sheet.paper_inches()
    turn, f, x, y = placement(w, h, page_w, page_h, fit)
    painter.save()
    try:
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setClipRect(0, 0, round(page_w * dpi), round(page_h * dpi))
        painter.translate(x * dpi, y * dpi)         # (the printed paper's top left)
        painter.scale(dpi * f, dpi * f)             # (now in sheet paper inches, y down)
        if turn:
            # turned a quarter turn counterclockwise: the sheet's left edge along the bottom
            painter.translate(0, w)
            painter.rotate(-90)
        painter.translate(0, h)
        # the drawing is in real inches, y up: a scaled panel sheet shrunk onto its paper
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


def print_sheets(project, printer, sheets, fit=True, mono=True):
    """Print sheets (in that order) on a QPrinter, one a page. Returns the page count."""
    from PySide6.QtGui import QPainter
    sheets = list(sheets)
    if not sheets:
        return 0
    painter = QPainter()
    if not painter.begin(printer):
        raise OSError("the printer couldn't start printing (is it on and connected?)")
    try:
        dpi = printer.resolution()
        pw, ph = page_inches(printer)
        for i, s in enumerate(sheets):
            if i:
                printer.newPage()
            paint_sheet(painter, project, s, pw, ph, dpi, fit, mono)
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
