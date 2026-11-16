"""The Print window (File > Print..., Ctrl+P): the printer (or a PDF file), its paper and the
copies, which sheets (this one, all, or those ticked), Fit to paper or Actual size, black on
white or the layers' colors, a preview, then Print."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox,
                               QSpinBox, QRadioButton, QButtonGroup, QListWidget,
                               QListWidgetItem, QPushButton, QCheckBox, QDialogButtonBox,
                               QLabel, QGroupBox, QFileDialog, QMessageBox)

PDF_FILE = "PDF file"


class PrintDialog(QDialog):
    def __init__(self, parent, project, current, chosen=()):
        """current: the sheet shown; chosen: the ids of the sheets selected in the Sheets
        list (two or more: "These sheets" starts with them ticked)."""
        super().__init__(parent)
        from PySide6.QtPrintSupport import QPrinterInfo
        self.setWindowTitle("Print")
        self.project = project
        self.current = current
        lay = QVBoxLayout(self)

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
        form.addRow("Paper:", self.paper_box)
        self.copies = QSpinBox()
        self.copies.setRange(1, 99)
        form.addRow("Copies:", self.copies)
        lay.addLayout(form)

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
        for text, on in (("Tick all", True), ("Tick none", False)):
            b = QPushButton(text)
            b.clicked.connect(lambda _c=False, on=on: self._tick_all(on))
            row.addWidget(b)
        row.addStretch(1)
        gl.addLayout(row)
        (self.these if len(chosen) > 1 else
         self.this_one if current in project.sheets else self.all_of_them).setChecked(True)
        self.which.idClicked.connect(lambda _k: self._update())
        lay.addWidget(g)

        g = QGroupBox("Size")
        gl = QVBoxLayout(g)
        self.fit = QRadioButton("Fit to paper (each sheet as big as the paper holds, turned "
                                "to match it)")
        self.actual = QRadioButton("Actual size (as on the sheet's own paper: a bigger "
                                   "sheet is cut off)")
        self.fit.setChecked(True)
        gl.addWidget(self.fit)
        gl.addWidget(self.actual)
        lay.addWidget(g)
        self.mono = QCheckBox("Black on white (else in the layers' colors)")
        self.mono.setChecked(True)
        lay.addWidget(self.mono)
        self.note = QLabel()
        self.note.setWordWrap(True)
        lay.addWidget(self.note)

        bb = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.preview_button = bb.addButton("Preview...", QDialogButtonBox.ActionRole)
        self.preview_button.clicked.connect(self.preview)
        self.print_button = bb.addButton("Print", QDialogButtonBox.AcceptRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._fill_papers()
        self._update()

    # ---- what was chosen -------------------------------------------------------------------
    def sheets(self):
        p = self.project
        k = self.which.checkedId()
        if k == 0:
            return [self.current] if self.current in p.sheets else []
        if k == 1:
            return list(p.sheets)
        ids = {self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())
               if self.list.item(i).checkState() == Qt.Checked}
        return [s for s in p.sheets if s.id in ids]

    def to_pdf(self):
        return self.printer_box.currentData() is None

    def _tick_all(self, on):
        self.list.blockSignals(True)
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(Qt.Checked if on else Qt.Unchecked)
        self.list.blockSignals(False)
        self.these.setChecked(True)
        self._update()

    def _fill_papers(self):
        from PySide6.QtGui import QPageSize
        info = self.printer_box.currentData()
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

    def _update(self):
        n = len(self.sheets())
        self.print_button.setText("Print %d sheet%s" % (n, "" if n == 1 else "s"))
        self.print_button.setEnabled(n > 0)
        self.preview_button.setEnabled(n > 0)
        self.note.setText("" if self.infos else "No printer was found: printing goes into a "
                          "PDF file.")

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
        pr.setPageOrientation(QPageLayout.Portrait)     # (each sheet is turned to match it)
        pr.setCopyCount(self.copies.value())
        pr.setDocName(self.project.fields.get("Project", "") or "KanzonasCAD drawing")
        return pr

    def preview(self):
        from PySide6.QtPrintSupport import QPrintPreviewDialog
        from . import print_out
        pr = self.make_printer()
        dlg = QPrintPreviewDialog(pr, self)
        dlg.setWindowTitle("Print preview")
        dlg.paintRequested.connect(lambda printer: print_out.print_sheets(
            self.project, printer, self.sheets(), self.fit.isChecked(), self.mono.isChecked()))
        dlg.resize(1000, 800)
        dlg.exec()

    def run(self, start_dir=""):
        """Print what was chosen once the window was accepted. Returns the page count, or
        None (nothing printed: no PDF file chosen)."""
        import os
        from . import print_out
        path = None
        if self.to_pdf():
            name = (self.project.path and os.path.splitext(
                os.path.basename(self.project.path))[0]) or "Drawing"
            path, _f = QFileDialog.getSaveFileName(self, "Print into a PDF file",
                                                   os.path.join(start_dir, name + ".pdf"),
                                                   "PDF (*.pdf)")
            if not path:
                return None
        try:
            return print_out.print_sheets(self.project, self.make_printer(path), self.sheets(),
                                          self.fit.isChecked(), self.mono.isChecked())
        except OSError as ex:
            QMessageBox.warning(self, "Print", "Couldn't print:\n%s" % ex)
            return None
