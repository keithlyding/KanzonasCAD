"""The Print window (File > Print..., Ctrl+P): the printer (or a PDF file), its paper, copies
and orientation; what to print of each sheet (the whole sheet, its extents, what the window
shows, or a window picked on the drawing); which sheets (this one, all, or those ticked);
Fit to paper or Actual size; black on white or the layers' colors; and a preview of the pages
beside it, drawn again as they change (the owner: "Printing needs to support preview as well",
"whole page, window, extents, etc")."""

from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox,
                               QSpinBox, QRadioButton, QButtonGroup, QListWidget,
                               QListWidgetItem, QPushButton, QCheckBox, QDialogButtonBox,
                               QLabel, QGroupBox, QFileDialog, QMessageBox, QWidget,
                               QToolButton, QSizePolicy)

PDF_FILE = "PDF file"
AREA_NAMES = [("sheet", "Whole sheet"), ("extents", "Extents (everything drawn)"),
              ("display", "Display (what the window shows)"),
              ("window", "Window (two corners you pick)")]
ORIENTATIONS = [("auto", "Automatic (turned to suit each sheet)"), ("portrait", "Portrait"),
                ("landscape", "Landscape")]


class PagePreview(QWidget):
    """One printed page as it will come out: the paper, its printable area, and the sheet on
    it (print_out.paint_sheet, as the printer gets it)."""

    def __init__(self, dialog):
        super().__init__()
        self.dialog = dialog
        self.page = 0
        self.setMinimumSize(320, 380)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._cache = None              # (key, QPixmap)

    def paintEvent(self, _e):
        from PySide6.QtGui import QPixmap
        d = self.dialog
        key = (self.width(), self.height(), self.page, d.settings_key())
        if self._cache is None or self._cache[0] != key:
            dpr = self.devicePixelRatioF()
            pm = QPixmap(max(1, round(self.width() * dpr)), max(1, round(self.height() * dpr)))
            pm.setDevicePixelRatio(dpr)
            p = QPainter(pm)
            self.draw(p)
            p.end()
            self._cache = (key, pm)
        p = QPainter(self)
        p.drawPixmap(0, 0, self._cache[1])
        p.end()

    def draw(self, p):
        from . import print_out
        d = self.dialog
        p.fillRect(QRectF(0, 0, self.width(), self.height()), QColor(110, 110, 110))
        paper_w, paper_h, (mx, my, pw, ph) = d.page_geometry()
        k = min((self.width() - 24) / paper_w, (self.height() - 24) / paper_h)
        x0 = (self.width() - paper_w * k) / 2
        y0 = (self.height() - paper_h * k) / 2
        p.fillRect(QRectF(x0 + 4, y0 + 4, paper_w * k, paper_h * k), QColor(60, 60, 60))
        p.fillRect(QRectF(x0, y0, paper_w * k, paper_h * k), QColor("white"))
        pen = QPen(QColor(200, 200, 200), 1, Qt.DashLine)
        p.setPen(pen)
        p.drawRect(QRectF(x0 + mx * k, y0 + my * k, pw * k, ph * k))      # (printable area)
        sheets = d.sheets()
        if not sheets:
            return
        s = sheets[min(self.page, len(sheets) - 1)]
        p.save()
        p.translate(x0 + mx * k, y0 + my * k)
        area, rect = d.area()
        print_out.paint_sheet(p, d.project, s, pw, ph, k, d.fit.isChecked(),
                              d.mono.isChecked(), line_width=max(print_out.LINE_WIDTH, 1.0 / k),
                              box=print_out.area_box(s, area, rect, d.project),
                              turn_ok=d.orientation() == "auto")
        p.restore()


class PrintDialog(QDialog):
    PICK = 2                    # exec()'s result: pick a window on the drawing, then come back

    def __init__(self, parent, project, current, chosen=(), display=None):
        """current: the sheet shown; chosen: the ids of the sheets selected in the Sheets
        list (two or more: "These sheets" starts with them ticked); display: the drawing
        units the window shows (x0, y0, x1, y1), for Display."""
        super().__init__(parent)
        from PySide6.QtPrintSupport import QPrinterInfo
        self.setWindowTitle("Print")
        self.project = project
        self.current = current
        self.display = display
        self.window_rect = None         # two corners picked (Window)
        self._printers = {}             # (printer, paper, orientation) -> QPrinter
        outer = QHBoxLayout(self)
        left = QVBoxLayout()
        outer.addLayout(left, 0)

        form = QFormLayout()
        self.printer_box = QComboBox()
        self.infos = list(QPrinterInfo.availablePrinters())
        default = QPrinterInfo.defaultPrinter().printerName()
        for info in self.infos:
            self.printer_box.addItem(info.printerName(), info)
        self.printer_box.addItem(PDF_FILE, None)
        names = [i.printerName() for i in self.infos]
        self.printer_box.setCurrentIndex(names.index(default) if default in names else 0)
        self.printer_box.currentIndexChanged.connect(self._fill_papers)
        form.addRow("Printer:", self.printer_box)
        self.paper_box = QComboBox()
        self.paper_box.currentIndexChanged.connect(lambda _i: self._update())
        form.addRow("Paper:", self.paper_box)
        self.orient_box = QComboBox()
        for key, text in ORIENTATIONS:
            self.orient_box.addItem(text, key)
        self.orient_box.currentIndexChanged.connect(lambda _i: self._update())
        form.addRow("Orientation:", self.orient_box)
        self.copies = QSpinBox()
        self.copies.setRange(1, 99)
        form.addRow("Copies:", self.copies)
        left.addLayout(form)

        g = QGroupBox("What to print")
        gl = QHBoxLayout(g)
        self.area_box = QComboBox()
        for key, text in AREA_NAMES:
            self.area_box.addItem(text, key)
        if display is None:
            self.area_box.model().item(2).setEnabled(False)
        self.area_box.currentIndexChanged.connect(self._area_changed)
        gl.addWidget(self.area_box, 1)
        self.pick_button = QPushButton("Pick window <")
        self.pick_button.setToolTip("Pick the two corners of what to print on the drawing")
        self.pick_button.clicked.connect(self.pick_window)
        gl.addWidget(self.pick_button)
        left.addWidget(g)

        g = QGroupBox("Sheets")
        gl = QVBoxLayout(g)
        self.which = QButtonGroup(self)
        self.this_one = QRadioButton("This sheet (%s %s)" % (project.sheet_number(current),
                                                               current.title or "(untitled)"))
        self.all_of_them = QRadioButton("All sheets (%d)" % len(project.sheets))
        self.these = QRadioButton("These sheets:")
        for k, b in enumerate((self.this_one, self.all_of_them, self.these)):
            self.which.addButton(b, k)
            gl.addWidget(b)
        self.list = QListWidget()
        self.list.setMaximumHeight(140)
        chosen = set(chosen)
        for s in project.sheets:
            it = QListWidgetItem("%s   %s" % (project.sheet_number(s), s.title or "(untitled)"))
            it.setData(Qt.UserRole, s.id)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            on = s.id in chosen if len(chosen) > 1 else s is current
            it.setCheckState(Qt.Checked if on else Qt.Unchecked)
            self.list.addItem(it)
        self.list.itemChanged.connect(lambda _i: (self.these.setChecked(True),
                                                  self._update()))
        gl.addWidget(self.list)
        row = QHBoxLayout()
        self.tick_buttons = []
        for text, on in (("Tick all", True), ("Tick none", False)):
            b = QPushButton(text)
            b.clicked.connect(lambda _c=False, on=on: self._tick_all(on))
            row.addWidget(b)
            self.tick_buttons.append(b)
        row.addStretch(1)
        gl.addLayout(row)
        (self.these if len(chosen) > 1 else
         self.this_one if current in project.sheets else self.all_of_them).setChecked(True)
        self.which.idClicked.connect(lambda _k: self._update())
        left.addWidget(g)

        g = QGroupBox("Size")
        gl = QVBoxLayout(g)
        self.fit = QRadioButton("Fit to paper (as big as the paper holds)")
        self.actual = QRadioButton("Actual size (as on the sheet's own paper; past the "
                                   "paper's edges is cut off)")
        self.fit.setChecked(True)
        self.fit.toggled.connect(lambda _on: self._update())
        gl.addWidget(self.fit)
        gl.addWidget(self.actual)
        left.addWidget(g)
        self.mono = QCheckBox("Black on white (else in the layers' colors)")
        self.mono.setChecked(True)
        self.mono.toggled.connect(lambda _on: self._update())
        left.addWidget(self.mono)
        self.note = QLabel()
        self.note.setWordWrap(True)
        left.addWidget(self.note)
        left.addStretch(1)

        right = QVBoxLayout()
        outer.addLayout(right, 1)
        self.preview_page = PagePreview(self)
        right.addWidget(self.preview_page, 1)
        nav = QHBoxLayout()
        self.prev_button = QToolButton()
        self.prev_button.setText("<")
        self.prev_button.clicked.connect(lambda: self.show_page(self.preview_page.page - 1))
        self.next_button = QToolButton()
        self.next_button.setText(">")
        self.next_button.clicked.connect(lambda: self.show_page(self.preview_page.page + 1))
        self.page_label = QLabel()
        nav.addStretch(1)
        nav.addWidget(self.prev_button)
        nav.addWidget(self.page_label)
        nav.addWidget(self.next_button)
        nav.addStretch(1)
        right.addLayout(nav)
        bb = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.preview_button = bb.addButton("Full preview...", QDialogButtonBox.ActionRole)
        self.preview_button.clicked.connect(self.preview)
        self.print_button = bb.addButton("Print", QDialogButtonBox.AcceptRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        right.addWidget(bb)
        self._redraw = QTimer(self, singleShot=True, interval=120)
        self._redraw.timeout.connect(self.preview_page.update)
        self._fill_papers()
        self._area_changed()
        self.resize(1050, 700)

    # ---- what was chosen -------------------------------------------------------------------
    def area(self):
        """(area, rect): what of each sheet is printed (print_out.area_box)."""
        a = self.area_box.currentData()
        return a, (self.display if a == "display" else self.window_rect if a == "window"
                   else None)

    def orientation(self):
        return self.orient_box.currentData()

    def one_sheet_only(self):
        """Display and Window are of the sheet shown."""
        return self.area_box.currentData() in ("display", "window")

    def sheets(self):
        p = self.project
        k = self.which.checkedId()
        if k == 0 or self.one_sheet_only():
            return [self.current] if self.current in p.sheets else []
        if k == 1:
            return list(p.sheets)
        ids = {self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())
               if self.list.item(i).checkState() == Qt.Checked}
        return [s for s in p.sheets if s.id in ids]

    def to_pdf(self):
        return self.printer_box.currentData() is None

    def settings_key(self):
        """What the preview depends on (it is drawn again when this changes)."""
        area, rect = self.area()
        return (self.printer_box.currentIndex(), self.paper_box.currentIndex(),
                self.orientation(), area, rect, tuple(s.id for s in self.sheets()),
                self.fit.isChecked(), self.mono.isChecked(), self.project.revision)

    def _tick_all(self, on):
        self.list.blockSignals(True)
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(Qt.Checked if on else Qt.Unchecked)
        self.list.blockSignals(False)
        self.these.setChecked(True)
        self._update()

    def _area_changed(self, _i=None):
        if self.area_box.currentData() == "window" and self.window_rect is None and \
                self.isVisible():
            self.pick_window()
            return
        self._update()

    def _fill_papers(self):
        from PySide6.QtGui import QPageSize
        info = self.printer_box.currentData()
        self.paper_box.blockSignals(True)
        self.paper_box.clear()
        sizes = list(info.supportedPageSizes()) if info is not None else []
        if not sizes:
            sizes = [QPageSize(k) for k in (QPageSize.Letter, QPageSize.Legal,
                                            QPageSize.Tabloid, QPageSize.AnsiC,
                                            QPageSize.AnsiD, QPageSize.AnsiE, QPageSize.A4,
                                            QPageSize.A3)]
        default = info.defaultPageSize() if info is not None else QPageSize(QPageSize.Letter)
        at = 0
        for i, ps in enumerate(sizes):
            self.paper_box.addItem(ps.name(), ps)
            if ps.isEquivalentTo(default):
                at = i
        self.paper_box.setCurrentIndex(at)
        self.paper_box.blockSignals(False)
        self._update()

    def _update(self):
        one = self.one_sheet_only()
        for w in [self.all_of_them, self.these, self.list] + self.tick_buttons:
            w.setEnabled(not one)
        self.pick_button.setVisible(self.area_box.currentData() == "window")
        n = len(self.sheets())
        self.print_button.setText("Print %d sheet%s" % (n, "" if n == 1 else "s"))
        ok = n > 0 and not (self.area_box.currentData() == "window" and
                            self.window_rect is None)
        self.print_button.setEnabled(ok)
        self.preview_button.setEnabled(ok)
        notes = []
        if not self.infos:
            notes.append("No printer was found: printing goes into a PDF file.")
        if one:
            notes.append("%s prints the sheet shown." % self.area_box.currentText().split(
                " (")[0])
        self.note.setText(" ".join(notes))
        self.show_page(self.preview_page.page)

    def show_page(self, i):
        n = len(self.sheets())
        i = max(0, min(i, n - 1))
        self.preview_page.page = i
        self.page_label.setText("Page %d of %d" % (i + 1, n) if n else "Nothing to print")
        self.prev_button.setEnabled(i > 0)
        self.next_button.setEnabled(i < n - 1)
        self._redraw.start()

    def pick_window(self):
        """Hide, so the window can be picked on the drawing (the caller does it and opens
        this again: exec() gives PICK)."""
        self.done(self.PICK)

    def set_window(self, rect):
        """The two corners picked (None: picking was cancelled)."""
        if rect is not None:
            self.window_rect = rect
        elif self.window_rect is None and self.area_box.currentData() == "window":
            self.area_box.setCurrentIndex(0)
        self._update()

    # ---- printing --------------------------------------------------------------------------
    def make_printer(self, path=None):
        """A QPrinter set as chosen (path: the PDF file's, when printing into one)."""
        from PySide6.QtGui import QPageLayout
        from PySide6.QtPrintSupport import QPrinter
        info = self.printer_box.currentData()
        pr = QPrinter(info, QPrinter.HighResolution) if info is not None else \
            QPrinter(QPrinter.HighResolution)
        if info is None:
            pr.setOutputFormat(QPrinter.PdfFormat)
            if path:
                pr.setOutputFileName(path)
        ps = self.paper_box.currentData()
        if ps is not None:
            pr.setPageSize(ps)
        # (Automatic: each sheet is turned to match a portrait page instead)
        pr.setPageOrientation(QPageLayout.Landscape if self.orientation() == "landscape"
                              else QPageLayout.Portrait)
        pr.setCopyCount(self.copies.value())
        pr.setDocName(self.project.fields.get("Project", "") or "KanzonasCAD drawing")
        return pr

    def page_geometry(self):
        """(paper width, paper height, (left, top, width, height) of the printable area), in
        inches, for the printer, paper and orientation chosen."""
        from PySide6.QtPrintSupport import QPrinter
        key = (self.printer_box.currentIndex(), self.paper_box.currentIndex(),
               self.orientation())
        pr = self._printers.get(key)
        if pr is None:
            pr = self._printers[key] = self.make_printer()
        paper = pr.paperRect(QPrinter.Inch)
        page = pr.pageRect(QPrinter.Inch)
        return paper.width(), paper.height(), (page.x() - paper.x(), page.y() - paper.y(),
                                               page.width(), page.height())

    def _print_on(self, printer):
        from . import print_out
        area, rect = self.area()
        return print_out.print_sheets(self.project, printer, self.sheets(),
                                      self.fit.isChecked(), self.mono.isChecked(), area, rect,
                                      turn_ok=self.orientation() == "auto")

    def preview(self):
        from PySide6.QtPrintSupport import QPrintPreviewDialog
        dlg = QPrintPreviewDialog(self.make_printer(), self)
        dlg.setWindowTitle("Print preview")
        dlg.paintRequested.connect(self._print_on)
        dlg.resize(1000, 800)
        dlg.exec()

    def run(self, start_dir=""):
        """Print what was chosen once the window was accepted. Returns the page count, or
        None (nothing printed: no PDF file chosen)."""
        import os
        path = None
        if self.to_pdf():
            name = (self.project.path and os.path.splitext(
                os.path.basename(self.project.path))[0]) or "Drawing"
            path, _f = QFileDialog.getSaveFileName(self, "Print into a PDF file",
                                                   os.path.join(start_dir, name + ".pdf"),
                                                   "PDF (*.pdf)")
            if not path:
                return None
        if path is None:
            try:
                return self._print_on(self.make_printer(None))
            except OSError as ex:
                QMessageBox.warning(self, "Print", "Couldn't print:\n%s" % ex)
                return None
        from .dialogs import write_failed
        from .fileio import written_whole
        try:
            # (written beside it, then put in its place: a PDF open in another program is
            # said, never left as it was without a word, 0.26)
            with written_whole(path) as tmp:
                printer = self.make_printer(tmp)
                n = self._print_on(printer)
                del printer             # (the file closed before it is put in its place)
        except OSError as ex:
            write_failed(self, "Print", path, ex)
            return None
        return n
