"""Texts edited where they are (the owner's list, #14 "in-place text editing"): a double-click on
a text or a multi-line note opens an edit box over it on the drawing, at its size on the
screen; Enter (Ctrl+Enter in a multi-line note, where Enter starts a new line) keeps what was
typed, one Undo, as does clicking elsewhere; Esc leaves it as it was. Its height,
angle and justification stay in its window (right-click: Text properties...)."""

from PySide6.QtCore import Qt, QEvent, QObject
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLineEdit, QPlainTextEdit

from . import model as M


class InPlace:
    """The edit box over one text of a view; done(text or None) when it closes."""

    def __init__(self, view, ent, done):
        self.view, self.ent, self.done = view, ent, done
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
        box.show()
        box.setFocus()

    def finish(self, keep):
        if self.box is None:
            return
        box, self.box = self.box, None
        got = None
        if keep:
            got = box.toPlainText() if isinstance(box, QPlainTextEdit) else box.text()
        box.hide()
        box.deleteLater()
        self.view.setFocus()
        self.done(got)


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
            self.owner.finish(True)
        return False


def changed(ent, text):
    """The text with its new wording, or None when nothing changed or it would be empty."""
    if text is None:
        return None
    t = text if isinstance(ent, M.MText) else text.strip()
    if not t.strip() or t == ent.text:
        return None
    return ent.copy(text=t)
