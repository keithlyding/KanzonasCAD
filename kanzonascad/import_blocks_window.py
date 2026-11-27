"""Library > Import blocks from folder...: the window that lists the blocks found in a folder
of DWG and DXF files (or one drawing), and puts the ticked ones in the library
(block_import.py does the reading and writing, without Qt). Files are read one at a time and
blocks written a few at a time on threads (the event loop turning meanwhile: only the
library's files are written there), under a progress window with Cancel, so the
program never stops answering."""

import os
import time

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QCheckBox, QTableWidget, QTableWidgetItem, QComboBox,
                               QDialogButtonBox, QFileDialog, QFormLayout, QHeaderView,
                               QMessageBox, QProgressDialog, QApplication, QAbstractItemView)

from . import block_import as BI
from .render import block_pixmap

TITLE = "Import blocks from folder"
KINDS = (("symbol", "Schematic symbol"), ("footprint", "Panel footprint"))
CHOICE_LABELS = (("skip", "Skip it"), ("replace", "Replace it"), ("both", "Keep both"))
THUMB = 40
FILL_ROWS = 25          # (rows listed between two turns of the event loop)
WRITERS = 8             # (block files written at once: put_in)
COLUMNS = ("Block", "Kind", "Pins", "File", "Status", "Name already in the library")


class Progress:
    """A progress window over work done a piece at a time on the event loop; longest: the
    longest piece of work between two event loop turns, in seconds (the self-test's
    budget)."""

    def __init__(self, parent, text, total):
        self.dlg = QProgressDialog(text, "Cancel", 0, max(total, 1), parent)
        self.dlg.setObjectName("import_blocks_progress")
        self.dlg.setWindowTitle(TITLE)
        self.dlg.setWindowModality(Qt.WindowModal)
        self.dlg.setMinimumDuration(300)
        self.dlg.setValue(0)
        self.longest = 0.0
        self._t = time.perf_counter()

    def tick(self, done, text=None):
        """After one piece: the window updated and the event loop run; False when Cancel was
        pressed."""
        self.longest = max(self.longest, time.perf_counter() - self._t)
        if text:
            self.dlg.setLabelText(text)
        self.dlg.setValue(done)
        QApplication.processEvents()
        self._t = time.perf_counter()
        return not self.dlg.wasCanceled()

    def turn(self):
        """A turn of the event loop while work goes on elsewhere (a thread)."""
        self.longest = max(self.longest, time.perf_counter() - self._t)
        QApplication.processEvents()
        self._t = time.perf_counter()

    def close(self):
        self.dlg.reset()
        self.dlg.close()
        self.dlg.deleteLater()


def scan(parent, paths):
    """The blocks of these files (Found rows), read one file at a time; None when Cancel was
    pressed. Returns (rows, the longest step in seconds)."""
    prog = Progress(parent, "Reading %d drawing%s..." % (len(paths), "" if len(paths) == 1
                                                          else "s"), len(paths))
    rows = []
    try:
        for i, (path, got) in enumerate(BI.read_all(paths)):
            rows += got
            if not prog.tick(i + 1, "Reading %s (%d of %d)..." % (
                    os.path.basename(path), i + 1, len(paths))):
                return None, prog.longest
        return rows, prog.longest
    finally:
        prog.close()


class _Cancelled(Exception):
    """Cancel pressed while blocks were being put in."""


def _wait(prog, fut):
    """The event loop turned until fut (a write on its thread) is done; its error or None."""
    from concurrent.futures import wait
    while not wait([fut], timeout=0.01).done:
        prog.turn()
    return fut.exception()


def put_in(parent, importer):
    """The importer's blocks put in the library: each decided on the event loop
    (Importer.next_write), its file written on a thread (Importer.write: no Qt, no project,
    only the library's file), up to WRITERS at a time, the event loop turning meanwhile;
    Cancel puts the library back as it was (on a thread too). Returns (finished, the
    longest time the event loop waited, in seconds).

    Nothing here waits on the disk on the event loop: Importer.next_write decides from the
    library's files listed when the Importer was made, and every read, write, rename and
    flush is the threads', and they do no Python work to speak of that the event loop would
    wait its turn behind (0.27.1: one step of 0.45 s on the Windows build, the event loop
    looking for each file and the threads making each file's text).

    A block file is flushed to disk (fsync) before it takes its name, a wait on the disk: one
    took 0.22 s on the Windows build, and the self-test's 200, one after the other, took 12
    and 15 s there on a busy disk (2 s on a quiet one). Written a few at a time, the waits
    overlap."""
    from collections import deque
    from concurrent.futures import ThreadPoolExecutor
    prog = Progress(parent, "Putting %d block%s in the library..." % (
        importer.total(), "" if importer.total() == 1 else "s"), importer.total())
    busy = deque()              # [(write, its future)], oldest first
    done = 0

    def finish_oldest():
        nonlocal done
        w, fut = busy.popleft()
        error = _wait(prog, fut)
        if error is not None and not isinstance(error, OSError):
            raise error
        importer.wrote(w, None if error else fut.result(), error)
        done += 1
        if not prog.tick(done):
            raise _Cancelled

    try:
        with ThreadPoolExecutor(WRITERS) as pool:
            try:
                while True:
                    w = importer.next_write()
                    if w is False:
                        break
                    if w is None:               # (skipped)
                        done += 1
                        if not prog.tick(done):
                            raise _Cancelled
                        continue
                    # (a file a row before this one is still writing: that one first)
                    while busy and (len(busy) >= WRITERS or
                                    any(os.path.normcase(o.path) == os.path.normcase(w.path)
                                        for o, _f in busy)):
                        finish_oldest()
                    busy.append((w, pool.submit(importer.write, w)))
                while busy:
                    finish_oldest()
            except _Cancelled:
                for _w, fut in busy:            # (those not started yet aren't)
                    fut.cancel()
                for w, fut in busy:             # (those started finish before rollback)
                    if not fut.cancelled():
                        error = _wait(prog, fut)
                        importer.wrote(w, None if error else fut.result(), error)
                busy.clear()
                error = _wait(prog, pool.submit(importer.rollback))     # (the disk: a thread)
                if error is not None:
                    raise error
                return False, prog.longest
        return True, prog.longest
    finally:
        prog.close()


class ImportBlocksDialog(QDialog):
    """The blocks found, each with a tick box, its name, kind, pins, file and status, and the
    category and library they go to."""

    def __init__(self, parent, library, start_dir=""):
        super().__init__(parent)
        self.setObjectName("import_blocks")
        self.setWindowTitle(TITLE)
        self.library = library
        self.start_dir = start_dir or os.path.expanduser("~")
        self.source = ""
        self.folder = None
        self.rows = []
        self.longest = 0.0
        self.fill_step = 0.0
        self._filling = False
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.source_label = QLabel("No folder chosen")
        self.source_label.setObjectName("source")
        self.source_label.setWordWrap(True)
        top.addWidget(self.source_label, 1)
        b = QPushButton("Folder...")
        b.setObjectName("choose_folder")
        b.clicked.connect(self.choose_folder)
        top.addWidget(b)
        b = QPushButton("One drawing...")
        b.setObjectName("choose_file")
        b.clicked.connect(self.choose_file)
        top.addWidget(b)
        self.subfolders = QCheckBox("Include subfolders")
        self.subfolders.setObjectName("subfolders")
        self.subfolders.toggled.connect(self._rescan)
        top.addWidget(self.subfolders)
        lay.addLayout(top)
        lay.addWidget(QLabel("Bring in the blocks you made yourself: tick the ones to import. "
                             "Pins come from AutoCAD Electrical's wire connection attributes "
                             "(X1TERM01...); a block without them comes in as a panel "
                             "footprint. Change a row's kind if the guess is wrong."))
        lay.itemAt(lay.count() - 1).widget().setWordWrap(True)
        t = self.table = QTableWidget(0, len(COLUMNS))
        t.setObjectName("blocks")
        t.setHorizontalHeaderLabels(COLUMNS)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.verticalHeader().setVisible(False)
        t.setWordWrap(False)            # (a long reason on one line; all of it in its tooltip)
        t.setIconSize(QSize(THUMB, THUMB))
        t.verticalHeader().setDefaultSectionSize(THUMB + 6)
        h = t.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setSectionResizeMode(4, QHeaderView.Stretch)
        t.itemChanged.connect(self._ticked)
        lay.addWidget(t, 1)
        self.count_label = QLabel("")
        self.count_label.setObjectName("count")
        lay.addWidget(self.count_label)
        row = QHBoxLayout()
        for key, text in (("tick_all", "Tick all"), ("tick_none", "Tick none")):
            b = QPushButton(text)
            b.setObjectName(key)
            b.clicked.connect(lambda _c=False, on=key == "tick_all": self.tick_all(on))
            row.addWidget(b)
        row.addSpacing(16)
        row.addWidget(QLabel("Selected rows (all when none is):"))
        for key, label in KINDS:
            b = QPushButton(label)
            b.setObjectName("selected_" + key)
            b.clicked.connect(lambda _c=False, k=key: self.set_selected(kind=k))
            row.addWidget(b)
        for key, label in CHOICE_LABELS:
            b = QPushButton(label)
            b.setObjectName("selected_" + key)
            b.setToolTip("When the name is already in the library: " + label.lower())
            b.clicked.connect(lambda _c=False, k=key: self.set_selected(choice=k))
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        form = QFormLayout()
        cat = self.category = QComboBox()
        cat.setObjectName("category")
        cat.setEditable(True)
        cats = set()
        for k in ("symbol", "footprint"):
            blocks, _bad = library.blocks(k)
            cats |= {b.category for b in blocks.values() if b.category and not b.builtin}
        cat.addItems(sorted(cats | {"Imported"}, key=str.lower))
        cat.setCurrentText("Imported")
        form.addRow("Category", cat)
        tgt = self.target = QComboBox()
        tgt.setObjectName("target")
        names = {"first": "Your library", "second": "Second library"}
        for key, lib, ok in BI.libraries(library):
            tgt.addItem("%s (%s)%s" % (names[key], lib.folder, "" if ok else ": read-only"),
                        key)
            if not ok:
                tgt.model().item(tgt.count() - 1).setEnabled(False)
        want = "second" if library.save_second else "first"
        at = tgt.findData(want)
        if at >= 0 and tgt.model().item(at).isEnabled():
            tgt.setCurrentIndex(at)
        form.addRow("Put them in", tgt)
        lay.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.import_button = buttons.addButton("Import", QDialogButtonBox.AcceptRole)
        self.import_button.setObjectName("import")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.resize(980, 560)

    # ---- where the blocks come from ----------------------------------------------------------
    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, TITLE, self.folder or self.start_dir)
        if folder:
            self.set_folder(folder)
        return bool(folder)

    def choose_file(self):
        path, _f = QFileDialog.getOpenFileName(
            self, "Import blocks from one drawing", self.folder or self.start_dir,
            "Drawings (*.dwg *.dxf *.DWG *.DXF);;All files (*)")
        if path:
            self.set_file(path)
        return bool(path)

    def set_folder(self, folder):
        self.folder = folder
        self.source = folder
        self._rescan()

    def set_file(self, path):
        self.folder = os.path.dirname(path)
        self.source = path
        self._rescan()

    def _rescan(self):
        if not self.source:
            return
        if os.path.isdir(self.source):
            paths = BI.drawing_files(self.source, self.subfolders.isChecked())
            what = "%s%s: %d drawing%s" % (self.source, ", with its subfolders"
                                           if self.subfolders.isChecked() else "",
                                           len(paths), "" if len(paths) == 1 else "s")
        else:
            paths = [self.source]
            what = self.source
        self.source_label.setText(what)
        rows, longest = scan(self, paths)
        self.longest = max(self.longest, longest)
        self.set_rows(rows if rows is not None else [])
        if rows is None:
            self.count_label.setText("Reading was cancelled: nothing listed")

    # ---- the list ------------------------------------------------------------------------------
    def set_rows(self, rows):
        self.rows = list(rows)
        t = self.table
        self._filling = True
        t.setRowCount(len(self.rows))
        # (filled a few rows at a time, the event loop run between: a folder of hundreds of
        # blocks, each with its picture and two lists, doesn't hold the program up)
        self.fill_step = 0.0
        t0 = time.perf_counter()
        for i, r in enumerate(self.rows):
            if i and i % FILL_ROWS == 0:
                self.fill_step = max(self.fill_step, time.perf_counter() - t0)
                QApplication.processEvents()
                t0 = time.perf_counter()
            it = QTableWidgetItem(r.name)
            it.setFlags((it.flags() | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable)
            if r.defn is None:
                it.setFlags(it.flags() & ~Qt.ItemIsUserCheckable & ~Qt.ItemIsEnabled)
            else:
                it.setCheckState(Qt.Checked if r.ticked else Qt.Unchecked)
                it.setIcon(QIcon(block_pixmap(r.defn, THUMB)))
            t.setItem(i, 0, it)
            kind = QComboBox()
            kind.setObjectName("kind_%d" % i)
            for key, label in KINDS:
                kind.addItem(label, key)
            kind.setCurrentIndex(0 if r.kind == "symbol" else 1)
            kind.setEnabled(r.defn is not None)
            kind.currentIndexChanged.connect(lambda _n, i=i: self._kind_changed(i))
            t.setCellWidget(i, 1, kind)
            t.setItem(i, 2, self._plain(str(r.pins()) if r.defn is not None else ""))
            src = os.path.relpath(r.path, self.folder) if self.folder else r.path
            t.setItem(i, 3, self._plain(src))
            t.setItem(i, 4, self._plain(""))
            choice = QComboBox()
            choice.setObjectName("taken_%d" % i)
            for key, label in CHOICE_LABELS:
                choice.addItem(label, key)
            choice.setCurrentIndex(max(choice.findData(r.choice), 0))
            choice.currentIndexChanged.connect(lambda _n, i=i: self._choice_changed(i))
            t.setCellWidget(i, 5, choice)
        self._filling = False
        t.resizeColumnsToContents()
        self.refresh_status()
        self.fill_step = max(self.fill_step, time.perf_counter() - t0)

    @staticmethod
    def _plain(text):
        it = QTableWidgetItem(text)
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
        return it

    def refresh_status(self):
        sts = BI.statuses(self.library, self.rows)
        files = len({r.path for r in self.rows})
        bad = 0
        for i, (r, st) in enumerate(zip(self.rows, sts)):
            if st == "error":
                text = "Can't be read: %s" % r.error
                bad += 1
            elif st == "taken":
                text = "Name already in the library"
            else:
                text = "New"
            if r.whole:
                text += " (the whole drawing, with its blocks)"
            item = self.table.item(i, 4)
            item.setText(text)
            item.setToolTip(text)
            self.table.cellWidget(i, 5).setEnabled(st == "taken")
        ticked = sum(1 for r in self.rows if r.ticked and r.defn is not None)
        found = len(self.rows) - bad
        self.count_label.setText("%d block%s found in %d file%s, %d ticked%s" % (
            found, "" if found == 1 else "s", files, "" if files == 1 else "s", ticked,
            ("; %d can't be read" % bad) if bad else ""))
        return sts

    def _ticked(self, item):
        if self._filling or item.column() != 0:
            return
        self.rows[item.row()].ticked = item.checkState() == Qt.Checked
        self.refresh_status()

    def _kind_changed(self, i):
        self.rows[i].kind = self.table.cellWidget(i, 1).currentData()
        if not self._filling:
            self.refresh_status()

    def _choice_changed(self, i):
        self.rows[i].choice = self.table.cellWidget(i, 5).currentData()

    def selected(self):
        got = sorted({ix.row() for ix in self.table.selectionModel().selectedRows()})
        return got or list(range(len(self.rows)))

    def tick_all(self, on):
        self._filling = True
        for i, r in enumerate(self.rows):
            if r.defn is not None:
                r.ticked = on
                self.table.item(i, 0).setCheckState(Qt.Checked if on else Qt.Unchecked)
        self._filling = False
        self.refresh_status()

    def set_selected(self, kind=None, choice=None):
        """The selected rows (all when none is) made one kind, or given one choice for a name
        already in the library."""
        self._filling = True
        for i in self.selected():
            if self.rows[i].defn is None:
                continue
            # (the row's own boxes changed: their signals set the row's kind and choice)
            if kind is not None:
                box = self.table.cellWidget(i, 1)
                box.setCurrentIndex(box.findData(kind))
            if choice is not None:
                box = self.table.cellWidget(i, 5)
                box.setCurrentIndex(box.findData(choice))
        self._filling = False
        self.refresh_status()

    def importer(self):
        """The Importer of what is ticked (OSError: the library chosen can't be written)."""
        return BI.Importer(self.library, self.rows, self.category.currentText(),
                           self.target.currentData() or "first")


def import_blocks(win, library, start_dir=""):
    """Library > Import blocks from folder...: a folder asked for, its blocks listed, the
    ticked ones put in the library, then what was done told. Returns the Importer (None when
    nothing was imported: cancelled, or the library can't be written)."""
    dlg = ImportBlocksDialog(win, library, start_dir)
    try:
        if not dlg.choose_folder():
            return None
        if dlg.exec() != QDialog.Accepted:
            return None
        try:
            imp = dlg.importer()
        except OSError as ex:
            QMessageBox.warning(win, TITLE, "Couldn't import the blocks:\n%s" % ex)
            return None
        done, _longest = put_in(win, imp)
        unread = [r for r in dlg.rows if r.defn is None]
        if not done:
            QMessageBox.information(win, TITLE, "Cancelled: the library is as it was.")
            return None
        where = imp.dest.folder
        QMessageBox.information(win, TITLE, "%s\n\nThey are in %s, category %s." % (
            imp.summary(unread), where, imp.category) if imp.imported else imp.summary(unread))
        return imp
    finally:
        dlg.deleteLater()
