"""The mouse wheel never changes a number box (QSpinBox, QDoubleSpinBox) or a closed drop-down
list (QComboBox): it scrolls what they sit in instead (the owner, 0.21.3: "if I scroll the
mouse wheel over an input field with up/down arrows on the side, the number will scroll up or
down ... Let's get rid of that entirely ... it has a tendency of causing changes that I don't
even know I did").

install() gives the box classes a wheel handler that leaves the wheel untaken, so Qt hands it on
to the box's parent, the page or list that scrolls; nothing else pays for it (a filter on the
whole application ran on every event: the unit tests took a third longer). Boxes Qt makes
inside its own windows aren't of those Python classes: get_item and get_color, in place of
QInputDialog.getItem and QColorDialog.getColor, put a filter on that window's boxes alone. An
open drop-down list's own list still scrolls (it isn't a QComboBox). Typing, the arrow keys and
the up/down buttons still change a number."""

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractSpinBox, QColorDialog, QComboBox, QDialog,
                               QInputDialog)

BOXES = (QAbstractSpinBox, QComboBox)
QT_WHEEL = {cls: cls.wheelEvent for cls in BOXES}     # (Qt's own, as they were)


def _leave(_self, ev):
    ev.ignore()             # (not taken: Qt passes it on to the parent, which scrolls)


def install():
    """The box classes leave the wheel alone (once; later calls change nothing)."""
    for cls in BOXES:
        cls.wheelEvent = _leave


class _Filter(QObject):
    """Wheel events to the boxes it is put on (and their text) aren't taken."""

    def eventFilter(self, _obj, ev):
        if ev.type() == QEvent.Wheel:
            ev.ignore()
            return True
        return False


def guard(widget):
    """Every number box and drop-down list inside widget (one Qt made: its own windows'), and
    their text, leave the wheel alone. Returns the filter (kept by widget)."""
    f = _Filter(widget)
    for cls in BOXES:
        for box in widget.findChildren(cls):
            box.installEventFilter(f)
            line = box.lineEdit()
            if line is not None:
                line.installEventFilter(f)
    return f


def get_item(parent, title, label, items, current=0, editable=True):
    """QInputDialog.getItem, its list leaving the wheel alone: (text, ok)."""
    items = list(items)
    dlg = QInputDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setLabelText(label)
    dlg.setComboBoxItems(items)
    dlg.setComboBoxEditable(editable)
    if 0 <= current < len(items):
        dlg.setTextValue(items[current])
    guard(dlg)
    ok = dlg.exec() == QDialog.Accepted
    return dlg.textValue(), ok


def get_color(initial, parent, title):
    """QColorDialog.getColor, its number boxes leaving the wheel alone: the color picked, or
    an invalid one when cancelled."""
    dlg = QColorDialog(initial, parent)
    dlg.setWindowTitle(title)
    guard(dlg)
    if dlg.exec() != QDialog.Accepted:
        return QColor()
    return dlg.currentColor()      # (the one picked: OK took it)
