"""Texts edited where they are (the owner's list, #14 "in-place text editing"): a double-click on
a text or a multi-line note opens an edit box over it on the drawing, at its size on the
screen; Enter (Ctrl+Enter in a multi-line note, where Enter starts a new line) keeps what was
typed, one Undo, as does clicking elsewhere; Esc leaves it as it was. Over the box, its
justification: Left, Center and Right (kept with the wording, the same Undo), and More... for
its whole window (height, angle, the vertical justification). The owner, 0.22.5: "Now that we're
editing text on the document instead of the pop up, I've lost the ability to justify text"."""

from PySide6.QtCore import Qt, QEvent, QObject, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLineEdit, QPlainTextEdit, QToolButton)

from . import model as M

SIDES = (("left", "Left", "L"), ("center", "Center", "C"), ("right", "Right", "R"))


def side_of(ent):
    """A text's horizontal justification: left, center or right (a note's, from where it is
    attached: TL left, TC center...)."""
    if isinstance(ent, M.MText):
        return {"L": "left", "C": "center", "R": "right"}[ent.attach[1]]
    return ent.align


def with_side(ent, side):
    """The text justified to side (left, center, right), its insertion point where it is: a
    note keeps its top, middle or bottom."""
    if isinstance(ent, M.MText):
        return ent.copy(attach=ent.attach[0] + {"left": "L", "center": "C", "right": "R"}[side])
    return ent.copy(align=side)


class InPlace:
    """The edit box over one text of a view; done(text or None) when it closes."""

    def __init__(self, view, ent, done, more=None):
        self.view, self.ent, self.done = view, ent, done
        self.side = side_of(ent)
        self.more = more                # (More...: its whole window, the typing kept)
        multi = isinstance(ent, M.MText)
        box = QPlainTextEdit(view) if multi else QLineEdit(view)
        box.setObjectName("text_in_place")
        f = QFont(view.font())
        f.setPixelSize(max(9, int(round(ent.height * view.scale))))
        box.setFont(f)
        box.setStyleSheet("background: #fffbe6; color: black; border: 1px solid #3070ff;")
        if multi:
            box.setPlainText(ent.text)
        else:
            box.setText(ent.text)
            box.selectAll()
        bb = ent.bbox()
        a, b = view.to_screen((bb[0], bb[3])), view.to_screen((bb[2], bb[1]))
        w = max(120, int(b.x() - a.x()) + 40)
        h = max(f.pixelSize() + 10, int(b.y() - a.y()) + 10)
        box.setGeometry(int(a.x()) - 4, int(a.y()) - 4, w, h if multi else f.pixelSize() + 10)
        self.box = box
        self._keys = _Keys(self, box)
        box.installEventFilter(self._keys)
        self.bar = self._make_bar(view, box)
        self._show_side()
        box.show()
        box.setFocus()

    def _make_bar(self, view, box):
        """Left, Center, Right and More... just over the box; they never take the focus, so
        clicking one doesn't close the box."""
        bar = QFrame(view)
        bar.setObjectName("text_in_place_bar")
        bar.setStyleSheet("background: #fffbe6; border: 1px solid #3070ff;")
        row = QHBoxLayout(bar)
        row.setContentsMargins(1, 1, 1, 1)
        row.setSpacing(1)
        self.buttons = {}
        for side, label, _l in SIDES:
            b = QToolButton(bar)
            b.setText(label)
            b.setCheckable(True)
            b.setFocusPolicy(Qt.NoFocus)
            b.setToolTip("Justify %s (kept with what you typed: Enter)" % label.lower())
            b.clicked.connect(lambda _c=False, side=side: self.set_side(side))
            row.addWidget(b)
            self.buttons[side] = b
        m = QToolButton(bar)
        m.setText("More...")
        m.setFocusPolicy(Qt.NoFocus)
        m.setToolTip("The text's window: its height, angle and justification")
        m.clicked.connect(self._more)
        m.setEnabled(self.more is not None)
        row.addWidget(m)
        bar.adjustSize()
        g = box.geometry()
        bar.move(g.x(), max(0, g.y() - bar.height() - 2))
        bar.show()
        return bar

    def set_side(self, side):
        self.side = side
        self._show_side()
        if self.box is not None:
            self.box.setFocus()

    def _show_side(self):
        for side, b in self.buttons.items():
            b.setChecked(side == self.side)
        if isinstance(self.box, QLineEdit):
            self.box.setAlignment({"left": Qt.AlignLeft, "center": Qt.AlignHCenter,
                                   "right": Qt.AlignRight}[self.side])

    def focus_left(self):
        """The box lost the focus: kept (and closed) unless it went to its own buttons or
        came back."""
        from PySide6.QtWidgets import QApplication
        if self.box is None:
            return
        w = QApplication.focusWidget()
        if w is self.box or (w is not None and self.bar.isAncestorOf(w)) or \
                self.bar.underMouse():
            self.box.setFocus()
            return
        self.finish(True)

    def _more(self):
        more = self.more
        self.finish(True)               # (what was typed kept first, then the window)
        if more is not None:
            more()

    def finish(self, keep):
        if self.box is None:
            return
        box, self.box = self.box, None
        got = None
        if keep:
            got = box.toPlainText() if isinstance(box, QPlainTextEdit) else box.text()
        box.hide()
        box.deleteLater()
        self.bar.hide()
        self.bar.deleteLater()
        self.view.setFocus()
        self.done(got, self.side if keep else None)


class _Keys(QObject):
    """The edit box's keys and focus: Enter keeps, Esc drops, leaving it keeps."""

    def __init__(self, owner, box):
        super().__init__(box)
        self.owner = owner

    def eventFilter(self, obj, e):
        if e.type() == QEvent.ShortcutOverride and e.key() in (
                Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter):
            e.accept()                  # (the box's keys, not the window's Esc shortcut)
            return False
        if e.type() == QEvent.KeyPress:
            k, mods = e.key(), e.modifiers()
            if k == Qt.Key_Escape:
                self.owner.finish(False)
                return True
            multi = isinstance(obj, QPlainTextEdit)
            if k in (Qt.Key_Return, Qt.Key_Enter) and (not multi or mods & Qt.ControlModifier):
                self.owner.finish(True)
                return True
        elif e.type() == QEvent.FocusOut:
            # (a click on its own Left, Center, Right or More... isn't leaving it: told after
            # the click has gone where it went)
            QTimer.singleShot(0, self.owner.focus_left)
        return False


def changed(ent, text, side=None):
    """The text with its new wording and justification (side: left, center, right, or None
    for as it was), or None when nothing changed or it would be empty."""
    if text is None:
        return None
    t = text if isinstance(ent, M.MText) else text.strip()
    if not t.strip():
        return None
    new = ent if t == ent.text else ent.copy(text=t)
    if side is not None and side != side_of(ent):
        new = with_side(new, side)
    return None if new is ent else new
