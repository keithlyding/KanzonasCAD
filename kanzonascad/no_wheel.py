"""The mouse wheel never changes a number box (QSpinBox, QDoubleSpinBox) or a closed drop-down
list (QComboBox): it scrolls what they sit in instead (the owner, 0.21.3: "if I scroll the
mouse wheel over an input field with up/down arrows on the side, the number will scroll up or
down ... Let's get rid of that entirely ... it has a tendency of causing changes that I don't
even know I did").

One filter on the application, installed once (install), so the boxes Qt makes inside its own
small windows (QInputDialog's list, QColorDialog's numbers) are covered too. It looks at wheel
events only: the box doesn't get one, and Qt hands the wheel on to the box's parent, the page
or list that scrolls. An open drop-down list's own list still scrolls (it isn't a QComboBox).
Typing, the arrow keys and the up/down buttons still change a number."""

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QAbstractSpinBox, QApplication, QComboBox

_WHEEL = QEvent.Wheel


def _box(obj):
    """The number box or drop-down list obj is, or is part of (a number box's line edit),
    else None."""
    for w in (obj, getattr(obj, "parentWidget", lambda: None)()):
        if isinstance(w, (QAbstractSpinBox, QComboBox)):
            return w
    return None


class _NoWheel(QObject):
    def eventFilter(self, obj, ev):
        if ev.type() != _WHEEL or _box(obj) is None:
            return False
        ev.ignore()             # (not taken: Qt passes it on to the parent, which scrolls)
        return True


def install(app=None):
    """Put the filter on the application, once (later calls do nothing). Returns it."""
    app = app or QApplication.instance()
    got = getattr(app, "_kz_no_wheel", None)
    if got is None:
        got = _NoWheel(app)
        app.installEventFilter(got)
        app._kz_no_wheel = got
    return got
