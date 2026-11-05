"""The Sheet scale window: pick a panel sheet's scale by seeing it. A preview of the sheet at
its paper size with the drawing (or the cabinet's front and side) inside at the scale picked,
the scale in plain words, how much of the room it takes, Fit, and the cabinet size. The
working out is scalefit's (no Qt)."""

from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox,
                               QPushButton, QLabel, QDoubleSpinBox, QCheckBox, QGroupBox,
                               QDialogButtonBox, QWidget, QSizePolicy, QMessageBox)

from . import model as M
from . import scalefit as F

GOOD, WARN, BAD = "#2e7d32", "#b26a00", "#c62828"


class Preview(QWidget):
    """The sheet's paper, its border, the title block and the drawing at the scale picked.

    Made with its dialog as its Qt parent, and it reads the dialog through parentWidget(),
    keeping no reference of its own. Before, it had no parent (and, put in a layout not yet on
    a widget, PySide left it owned by Python although Qt then gave it the dialog as parent),
    and its reference back to the dialog made a cycle: the dialog, which QDialog.exec() hands
    back to Python, outlived Sheet scale and was freed later by the garbage collector together
    with this widget, Python and Qt both deleting them, in whatever order the collector
    picked. That crashed (a segfault in the unit tests, about one run in four)."""

    def __init__(self, dlg):
        super().__init__(dlg)
        self.setMinimumSize(QSize(360, 240))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def paintEvent(self, _e):
        d = self.parentWidget()
        pw, ph = d.paper()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), self.palette().window())
        pad = 12
        k = min((self.width() - 2 * pad) / pw, (self.height() - 2 * pad) / ph)
        ox = (self.width() - pw * k) / 2
        oy = (self.height() + ph * k) / 2

        def r(x0, y0, x1, y1):                   # paper inches -> a widget rectangle
            return QRectF(ox + x0 * k, oy - y1 * k, (x1 - x0) * k, (y1 - y0) * k)

        p.setPen(QPen(QColor("#9e9e9e"), 1))
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawRect(r(0, 0, pw, ph))
        m = M.Sheet.MARGIN
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor("#424242"), 1))
        p.drawRect(r(m, m, pw - m, ph - m))
        if d.tb is not None:
            t = d.tb
            p.setBrush(QBrush(QColor("#e0e0e0")))
            p.setPen(QPen(QColor("#757575"), 1))
            p.drawRect(r(t[0] + F.MARGIN, t[1], t[2], t[3] - F.MARGIN))
            p.setPen(QColor("#616161"))
            p.setFont(QFont(self.font().family(), 7))
            p.drawText(r(t[0] + F.MARGIN, t[1], t[2], t[3] - F.MARGIN), Qt.AlignCenter,
                       "Title block")
        s = d.scale()
        if s is None:
            p.end()
            return
        boxes = d.shown_boxes(s)
        # (a drawing too big for the sheet is cut off at the paper's edge, as it would print)
        p.setClipRect(r(0, 0, pw, ph).adjusted(-1, -1, 1, 1))
        color = QColor({"good": GOOD, "warn": WARN, "bad": BAD}[d.state(s)])
        fill = QColor(color)
        fill.setAlpha(40)
        p.setFont(QFont(self.font().family(), 8))
        for (x0, y0, x1, y1), label, dashed in boxes:
            p.setBrush(QBrush(fill))
            pen = QPen(color, 2)
            if dashed:
                pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            rr = r(x0 * s, y0 * s, x1 * s, y1 * s)
            p.drawRect(rr)
            if label and rr.width() > 30 and rr.height() > 14:
                p.setPen(color.darker(130))
                p.drawText(rr, Qt.AlignCenter, label)
        p.end()


class SheetScaleDialog(QDialog):
    def __init__(self, parent, project, sheet, settings=None):
        super().__init__(parent)
        self.project, self.sheet, self.settings = project, sheet, settings
        self.setWindowTitle("Sheet scale - %s %s" % (project.sheet_number(sheet), sheet.title))
        self.area, self.tb = F.room(project, sheet)
        self.box = F.drawing_box(sheet)

        self.combo = QComboBox()
        self.combo.setObjectName("scale")
        self.combo.setEditable(True)
        self.combo.setMinimumContentsLength(14)
        for name, v in M.SCALE_PRESETS:
            tmp = M.Sheet()
            tmp.scale, tmp.scale_name = v, name
            self.combo.addItem(tmp.scale_text(), (name, v))
        i = next((j for j in range(self.combo.count())
                  if self.combo.itemData(j) == (sheet.scale_name, sheet.scale)), -1)
        if i >= 0:
            self.combo.setCurrentIndex(i)
        else:
            self.combo.setEditText(sheet.scale_text())
        self.fit_btn = QPushButton("Fit")
        self.fit_btn.setObjectName("fit")
        self.fit_btn.setToolTip("The biggest scale at which the drawing (or, with nothing "
                                "drawn yet, the cabinet) fits the sheet")
        self.fit_btn.clicked.connect(self.fit)
        self.words = QLabel()
        self.words.setObjectName("words")
        self.words.setStyleSheet("font-weight: bold;")
        self.usage = QLabel()
        self.usage.setObjectName("usage")
        self.usage.setWordWrap(True)

        # the cabinet: width x height x depth, real inches; depth 0 = only the front
        cab = sheet.cabinet or _last_cabinet(settings)
        self.cab = []
        for i, what in enumerate(("Width", "Height", "Depth")):
            b = QDoubleSpinBox()
            b.setObjectName("cabinet_" + what.lower())
            b.setRange(0, 1200)
            b.setDecimals(2)
            b.setSuffix(" in")
            b.setSpecialValueText("-")
            b.setValue(float(cab[i]) if cab and len(cab) > i else 0.0)
            b.valueChanged.connect(self._changed)
            self.cab.append(b)
        group = QGroupBox("Cabinet size (optional)")
        gl = QFormLayout(group)
        for b, what in zip(self.cab, ("Width", "Height", "Depth")):
            gl.addRow(what, b)
        note = QLabel("While nothing is drawn yet, Fit makes room for the cabinet's front "
                      "and, with a depth, its side beside it.")
        note.setWordWrap(True)
        note.setStyleSheet("color: gray;")
        gl.addRow(note)

        self.center = QCheckBox("Move the drawing to the middle of the free space")
        self.center.setObjectName("center")
        self.center.setToolTip("The drawing doesn't lie inside the border at this scale where "
                               "it is now: move all of it (one undoable step)")

        # the sheet turned: a tall, narrow cabinet may print bigger on a tall sheet
        self.orient = QComboBox()
        self.orient.setObjectName("rotation")
        for r, label in F.ROTATIONS:
            self.orient.addItem(label, r)
        self.orient.setCurrentIndex(max(self.orient.findData(sheet.rotation), 0))
        self.orient.setToolTip("Turn the sheet: its border, zones and title block turn with "
                               "it, the drawing stays upright (Ctrl+Shift+Plus / Minus)")
        self.suggest = QLabel()
        self.suggest.setObjectName("suggest")
        self.suggest.setWordWrap(True)
        self.turn_btn = QPushButton()
        self.turn_btn.setObjectName("turn")
        self.turn_btn.clicked.connect(self._turn_suggested)
        self._suggested = None
        self.paper_note = paper = QLabel()
        paper.setWordWrap(True)
        paper.setStyleSheet("color: gray;")

        row = QHBoxLayout()
        row.addWidget(self.combo, 1)
        row.addWidget(self.fit_btn)
        side = QVBoxLayout()
        side.addWidget(QLabel("Scale"))
        side.addLayout(row)
        side.addWidget(self.words)
        side.addWidget(self.usage)
        side.addWidget(self.center)
        orow = QHBoxLayout()
        orow.addWidget(QLabel("Sheet"))
        orow.addWidget(self.orient, 1)
        side.addLayout(orow)
        srow = QHBoxLayout()
        srow.addWidget(self.suggest, 1)
        srow.addWidget(self.turn_btn)
        side.addLayout(srow)
        side.addWidget(group)
        side.addWidget(paper)
        side.addStretch(1)
        self.preview = Preview(self)
        body = QHBoxLayout()
        body.addWidget(self.preview, 3)
        sidew = QWidget(self)               # (its parent from the start: see Preview)
        sidew.setLayout(side)
        sidew.setMaximumWidth(360)
        body.addWidget(sidew, 2)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(body, 1)
        lay.addWidget(buttons)
        self.resize(840, 540)
        self._center_touched = False
        self.center.toggled.connect(self._center_clicked)
        self.combo.currentIndexChanged.connect(self._changed)
        self.combo.editTextChanged.connect(self._changed)
        self.orient.currentIndexChanged.connect(self._turned)
        self._turned()

    # ---- what is picked -----------------------------------------------------------------
    def rotation(self):
        return self.orient.currentData()

    def orientation(self):
        return "portrait" if self.rotation() in (90, 270) else "landscape"

    def paper(self):
        """(width, height) of the paper as picked, inches."""
        return F.as_rotated(self.sheet, self.rotation()).paper_inches()

    def _turned(self, *_a):
        self.area, self.tb = F.room(self.project, F.as_rotated(self.sheet, self.rotation()))
        pw, ph = self.paper()
        self.paper_note.setText(
            "Paper: %s, %s. The drawing stays real size: the scale only sets how big it prints. "
            "Text, tags and dimension numbers keep their printed size."
            % (self.sheet.size.split(" (")[0], "%g x %g in" % (pw, ph)))
        self._changed()

    def _turn_suggested(self):
        if self._suggested is not None:
            self.orient.setCurrentIndex(self.orient.findData(self._suggested))
            self.fit()

    def picked(self):
        """(name, scale) in the box, or None when it can't be read."""
        from .dialogs import _scale_of
        return _scale_of(self.combo)

    def scale(self):
        got = self.picked()
        return got[1] if got else None

    def cabinet(self):
        w, h, d = (b.value() for b in self.cab)
        return [w, h, d] if w > 0 and h > 0 else None

    def size_and_kind(self):
        """(w, h, what) the scale has to fit: the drawing, else the cabinet, else None."""
        if self.box is not None:
            return self.box[2] - self.box[0], self.box[3] - self.box[1], "drawing"
        cb = F.cabinet_box(self.cabinet())
        if cb is not None:
            return cb[0], cb[1], "cabinet"
        return None

    def shown_boxes(self, s):
        """[(real box, label, dashed)] the preview draws at scale s."""
        if self.box is not None:
            b = self.box
            if self.center.isChecked():
                off = F.centering(b, s, self.area, self.tb)
                if off:
                    b = (b[0] + off[0], b[1] + off[1], b[2] + off[0], b[3] + off[1])
            return [(b, "Your drawing", False)]
        cab = self.cabinet()
        if not cab:
            return []
        w, h, dpt = cab
        whole = F.cabinet_box(cab)
        off = F.centering((0, 0, whole[0], whole[1]), s, self.area, self.tb) or (0, 0)
        out = [((off[0], off[1], off[0] + w, off[1] + h), "Front", True)]
        if dpt > 0:
            x = off[0] + w + F.GAP
            out.append(((x, off[1], x + dpt, off[1] + h), "Side", True))
        return out

    def state(self, s):
        got = self.size_and_kind()
        if got is None:
            return "good"
        w, h, _what = got
        if not F.fits(w, h, s, self.area, self.tb):
            return "bad"
        if self.box is not None and not self.center.isChecked() and \
                not F.placed_inside(self.box, s, self.area, self.tb):
            return "warn"
        return "good"

    # ---- reacting ---------------------------------------------------------------------------
    def _center_clicked(self, _on):
        self._center_touched = True
        self._show()

    def _changed(self, *_a):
        s = self.scale()
        if s is not None and self.box is not None and not self._center_touched:
            # offered (ticked) only when the drawing, where it is, isn't inside at this scale
            out = not F.placed_inside(self.box, s, self.area, self.tb)
            self.center.blockSignals(True)
            self.center.setChecked(out)
            self.center.blockSignals(False)
        self._show()

    def _show(self):
        got = self.picked()
        self.center.setVisible(self.box is not None)
        self.fit_btn.setEnabled(self.size_and_kind() is not None)
        if got is None:
            self.words.setText("Type a scale as 1:4 (or pick one)")
            self.usage.setText("")
            self.preview.update()
            return
        name, s = got
        self.words.setText(F.in_words(s, name))
        what = self.size_and_kind()
        if what is None:
            self.usage.setText("Nothing is drawn on this sheet yet. Give the cabinet's size "
                               "below and Fit picks the scale for it.")
            self.usage.setStyleSheet("")
        else:
            w, h, kind = what
            u = F.use(w, h, s, self.area, self.tb)
            cab = self.cabinet()
            if kind == "drawing":
                label = "Your drawing (%s x %s in)" % (_num(w), _num(h))
            elif cab[2] > 0:
                label = "The cabinet's front and side (%s x %s x %s in deep)" % (
                    _num(cab[0]), _num(cab[1]), _num(cab[2]))
            else:
                label = "The cabinet's front (%s x %s in)" % (_num(cab[0]), _num(cab[1]))
            st = self.state(s)
            if st == "bad":
                better = F.best_scale(w, h, self.area, self.tb, named=bool(name))
                tmp = M.Sheet()
                tmp.scale, tmp.scale_name = better[1], better[0]
                text = ("%s is too big at this scale: it needs %d%% of the room. Try %s, or "
                        "Fit." % (label, round(u * 100), tmp.scale_text()))
            elif st == "warn":
                text = ("%s fits at this scale (%d%% of the room), but not where it is: "
                        "tick Move to the middle." % (label, round(u * 100)))
            else:
                text = "%s takes %d%% of the room on the sheet." % (label, round(u * 100))
            self.usage.setText(text)
            self.usage.setStyleSheet("color: %s;" % {"good": GOOD, "warn": WARN,
                                                       "bad": BAD}[st])
        self._show_suggestion()
        self.preview.update()

    def _show_suggestion(self):
        """Offer the other way round when it prints bigger (never turned without asking)."""
        what = self.size_and_kind()
        got = None
        if what is not None:
            cur = self.picked()
            got = F.other_way(self.project, F.as_rotated(self.sheet, self.rotation()),
                              what[0], what[1],
                              named=bool(cur[0]) if cur else bool(self.sheet.scale_name))
        self._suggested = got[0] if got else None
        self.suggest.setVisible(got is not None)
        self.turn_btn.setVisible(got is not None)
        if got:
            rot, (name, v) = got
            here = F.best_scale(what[0], what[1], self.area, self.tb,
                                named=bool(name))
            way = "tall" if rot in (90, 270) else "wide"
            self.suggest.setText("Turned %s it prints bigger: %s instead of %s." % (
                way, _scale_text(name, v), _scale_text(*here)))
            self.turn_btn.setText("Turn it")

    def fit(self):
        got = self.size_and_kind()
        if got is None:
            return
        w, h, _kind = got
        cur = self.picked()
        name, s = F.best_scale(w, h, self.area, self.tb,
                               named=bool(cur[0]) if cur else bool(self.sheet.scale_name))
        i = next((j for j in range(self.combo.count()) if self.combo.itemData(j) == (name, s)),
                 -1)
        if i >= 0:
            self.combo.setCurrentIndex(i)
        else:
            tmp = M.Sheet()
            tmp.scale, tmp.scale_name = s, name
            self.combo.setEditText(tmp.scale_text())
        if self.box is not None and not F.placed_inside(self.box, s, self.area, self.tb):
            self.center.setChecked(True)

    def _ok(self):
        got = self.picked()
        if got is None:
            QMessageBox.warning(self, "Sheet scale", "Type the scale as 1:4 (or pick one "
                                                     "from the list).")
            return
        name, s = got
        cab = self.cabinet()
        if cab and self.settings is not None:
            self.settings.setValue("panel/cabinet", ",".join("%g" % v for v in cab))
        F.apply(self.project, self.sheet, name, s, cabinet=cab,
                center=self.box is not None and self.center.isChecked(),
                rotation=self.rotation())
        self.accept()


def _scale_text(name, v):
    tmp = M.Sheet()
    tmp.scale, tmp.scale_name = v, name
    return tmp.scale_text()


def _num(x):
    return ("%d" % round(x)) if abs(x - round(x)) < 0.005 else ("%.2f" % x).rstrip("0")


def _last_cabinet(settings):
    """The cabinet size used last (Options are per user), or None."""
    if settings is None:
        return None
    raw = str(settings.value("panel/cabinet", "") or "")
    try:
        v = [float(t) for t in raw.split(",")]
    except ValueError:
        return None
    return v if len(v) == 3 and v[0] > 0 and v[1] > 0 else None


def sheet_scale(parent, project, sheet, settings=None):
    """Show the Sheet scale window. True when the scale (or cabinet) changed."""
    before = (sheet.scale, sheet.scale_name, sheet.cabinet, sheet.rotation,
              project.undo_stack[-1:])
    dlg = SheetScaleDialog(parent, project, sheet, settings)
    if dlg.exec() != QDialog.Accepted:
        return False
    return (sheet.scale, sheet.scale_name, sheet.cabinet, sheet.rotation,
            project.undo_stack[-1:]) != before
