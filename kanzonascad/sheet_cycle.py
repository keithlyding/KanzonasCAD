"""Moving between sheets from the keyboard.

Ctrl+Tab shows the next sheet in page order and Ctrl+Shift+Tab the one before, going round
from the last to the first (the owner, 0.22.2: "if I'm on sheet 13 of 15 and hit ctrl + tab,
the next sheet is 14, then 15, then 1 ... no more alternating between pages").

Ctrl+` (the key above Tab) goes through the sheets most recently shown first (the owner,
0.21.2: "Kind of like how AB's Studio 5000 cycles through? It defaults to the last page you
were on, but I can keep holding ctrl and tapping tab to go through the rest of the sheets";
0.22.2: "I do like the alternating feature but we need to use a different hot key combo").
Each view keeps the sheets in the order they were last shown. Ctrl+` picks the one before the
sheet shown, each ` more (Ctrl held) the next, Ctrl+Shift+` goes back; a list shows them
meanwhile, the pick highlighted, and letting Ctrl go shows it. Esc, Ctrl still held, puts the
list away and stays where it was.

The first Ctrl+` is a shortcut of the window; only while cycling does a key filter on the
application watch for Ctrl let go, Esc and more `s, and it is taken off at the end: a filter
there for good runs on every event (a test run's hundreds of windows, each with its own,
slowed it to a crawl)."""

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QFrame, QListWidget, QVBoxLayout
from shiboken6 import isValid


def order(view):
    """The view's sheets, the one shown first, then the others as last shown, then those never
    shown in page order (not the title block)."""
    p = view.project
    ids = [s.id for s in p.sheets]
    seen = [i for i in getattr(view, "sheet_history", []) if i in ids]
    cur = view.sheet_id
    out = [cur] if cur in ids else []
    out += [i for i in seen if i not in out]
    out += [i for i in ids if i not in out]
    return out


def shown(view):
    """Note the sheet the view shows as the most recent (not while cycling)."""
    hist = [i for i in getattr(view, "sheet_history", []) if i != view.sheet_id]
    view.sheet_history = [view.sheet_id] + hist[:199]


class _List(QFrame):
    """The sheets while Ctrl is held: page number and title, the pick highlighted. It never
    takes the keyboard."""

    def __init__(self, parent):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setFrameShape(QFrame.Box)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        self.items = QListWidget()
        self.items.setFocusPolicy(Qt.NoFocus)
        lay.addWidget(self.items)

    def show_for(self, view, ids, k):
        p = view.project
        by_id = {s.id: s for s in p.sheets}
        self.items.clear()
        for i in ids:
            s = by_id[i]
            self.items.addItem("%s   %s" % (p.sheet_number(s), s.title or ""))
        self.items.setCurrentRow(k)
        h = min(len(ids), 20) * (self.items.sizeHintForRow(0) + 2) + 12
        self.resize(max(260, self.items.sizeHintForColumn(0) + 40), h)
        c = view.mapToGlobal(view.rect().center())
        self.move(c.x() - self.width() // 2, c.y() - self.height() // 2)
        self.show()
        self.raise_()


class SheetCycler(QObject):
    """Ctrl+` for one main window: its shortcut starts (step), then, while cycling, a key
    filter on the application steps on with ` and Shift+` (Ctrl held) through
    order(view), shows the pick when Ctrl is let go and stays with Esc."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.ids = None             # (cycling: the order when it began, and the pick)
        self.k = 0
        self.filtering = False      # (the application's key filter on: while cycling only)
        self.actions = []           # (its shortcuts: install)
        self.list = _List(win)

    def step(self, back=False):
        v = self.win.view()
        if v is None:
            return
        if self.ids is None:
            self.ids, self.k = order(v), 0
        if len(self.ids) < 2:
            self.ids = None
            return
        self.k = (self.k + (-1 if back else 1)) % len(self.ids)
        self.list.show_for(v, self.ids, self.k)
        self._filter(True)

    def finish(self, go=True):
        ids, k = self.ids, self.k
        self.ids = None
        self._filter(False)
        self.list.hide()
        v = self.win.view()
        if go and ids and v is not None and k:
            v.show_sheet(ids[k])

    def _filter(self, on):
        if on != self.filtering:
            app = QApplication.instance()
            (app.installEventFilter if on else app.removeEventFilter)(self)
            self.filtering = on

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t not in (QEvent.ShortcutOverride, QEvent.KeyPress, QEvent.KeyRelease,
                     QEvent.ApplicationDeactivate):
            return False
        if not isValid(self.win) or self.ids is None:
            QApplication.instance().removeEventFilter(self)     # (its window gone, or done)
            self.filtering = False
            return False
        if t in (QEvent.ShortcutOverride, QEvent.KeyPress):
            key, mods = ev.key(), ev.modifiers()
            if key in RECENT_KEYS and mods & Qt.ControlModifier:
                if t == QEvent.KeyPress:
                    self.step(back=key == Qt.Key_AsciiTilde or bool(mods & Qt.ShiftModifier))
                ev.accept()
                return True
            if key in (Qt.Key_Tab, Qt.Key_Backtab):
                ev.accept()                 # (no page step in the middle of a cycle)
                return True
            if self.ids is not None and key == Qt.Key_Escape:
                if t == QEvent.KeyPress:
                    self.finish(go=False)
                ev.accept()
                return True
        elif t == QEvent.KeyRelease and self.ids is not None and ev.key() == Qt.Key_Control:
            self.finish()
        elif t == QEvent.ApplicationDeactivate and self.ids is not None:
            self.finish(go=False)
        return False


def next_sheet(win, back=False):
    """Show the next sheet in page order (back: the one before), from the last round to the
    first."""
    v = win.view()
    if v is None:
        return
    ids = [s.id for s in v.project.sheets]
    if len(ids) < 2:
        return
    k = ids.index(v.sheet_id) if v.sheet_id in ids else -1
    v.show_sheet(ids[(k + (-1 if back else 1)) % len(ids)])


RECENT_KEYS = (Qt.Key_QuoteLeft, Qt.Key_AsciiTilde)     # (` and, with Shift on it, ~)


class _KeyAction(QAction):
    """A shortcut that works even when the key reads as two of its own spellings. Windows
    reports Ctrl+Shift+Tab as both Ctrl+Shift+Tab and Ctrl+Backtab (qwindowskeymapper's
    possibleKeyCombinations), and Ctrl+Shift+` as Ctrl+Shift+` and Ctrl+~: with more than one
    registered, Qt marks the shortcut ambiguous and a plain QAction does nothing (the owner,
    0.22.3: "Ctrl +shift+tab does not work"). Each key has one action here, and no other action
    of the window uses these keys (tests/test_021_sheet_cycle), so ambiguous only ever means
    two spellings of this one."""

    def event(self, e):
        if e.type() == QEvent.Shortcut and e.isAmbiguous():
            self.trigger()
            return True
        return super().event(e)


def install(win):
    """Ctrl+Tab and Ctrl+Shift+Tab (page order), Ctrl+` and Ctrl+Shift+` (most recent first)
    for the main window win: shortcuts of the window (no filter on the application until
    cycling starts)."""
    cyc = SheetCycler(win)
    keys = (([QKeySequence(Qt.CTRL | Qt.Key_Tab)], lambda: next_sheet(win)),
            ([QKeySequence(Qt.CTRL | Qt.SHIFT | Qt.Key_Tab),
              QKeySequence(Qt.CTRL | Qt.SHIFT | Qt.Key_Backtab),
              QKeySequence(Qt.CTRL | Qt.Key_Backtab)], lambda: next_sheet(win, back=True)),
            ([QKeySequence(Qt.CTRL | Qt.Key_QuoteLeft)], lambda: cyc.step()),
            ([QKeySequence(Qt.CTRL | Qt.SHIFT | Qt.Key_QuoteLeft),
              QKeySequence(Qt.CTRL | Qt.SHIFT | Qt.Key_AsciiTilde),
              QKeySequence(Qt.CTRL | Qt.Key_AsciiTilde)], lambda: cyc.step(back=True)))
    for seqs, run in keys:
        act = _KeyAction(win)
        act.setShortcuts(seqs)
        act.setShortcutContext(Qt.WindowShortcut)
        act.triggered.connect(lambda _c=False, r=run: r())
        win.addAction(act)
        cyc.actions.append(act)
    return cyc
