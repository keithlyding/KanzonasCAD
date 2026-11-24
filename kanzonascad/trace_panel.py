"""The Trace panel (Ctrl+E): every place a device, a wire or a PLC point appears in the
project, in a panel docked at the bottom of the window (or its left or right side, where it is
put back each time), as Studio 5000's Cross Reference tab (the owner, Nov 2026). Double-click
a row, or Enter on it, to go there: its sheet shown, the object selected and centered. Up and
Down move through the rows.

While it is open it follows the selection: clicking a device, a wire or a PLC point lists
its places at once (one lookup in where_used's index; nothing at all while it is closed).
A mixin of MainWindow (main_window.py), as block_window.py is."""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QDockWidget, QHBoxLayout, QHeaderView, QLabel, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget, QAbstractItemView)

from . import where_used as WU

COLUMNS = ("Where", "Sheet", "Role", "Name", "Description")
HINT = "Select a device, wire or PLC point (or point at one) and press Ctrl+E"
LEAST = (8.0, 5.0)              # paper inches shown around an object gone to, at the least


class RowTable(QTreeWidget):
    """The places, one a row; Enter (or a double-click) asks to go to the current one."""
    goRequested = Signal(object)

    def __init__(self):
        super().__init__()
        self.setColumnCount(len(COLUMNS))
        self.setHeaderLabels(list(COLUMNS))
        self.setRootIsDecorated(False)
        self.setUniformRowHeights(True)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAllColumnsShowFocus(True)
        h = self.header()
        h.setStretchLastSection(True)
        for i, w in enumerate((60, 140, 100, 110)):
            h.resizeSection(i, w)
        h.setSectionResizeMode(QHeaderView.Interactive)
        self.itemDoubleClicked.connect(lambda it, _c: self.goRequested.emit(it.data(0, Qt.UserRole)))

    def keyPressEvent(self, e):
        it = self.currentItem()
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and it is not None:
            self.goRequested.emit(it.data(0, Qt.UserRole))
            e.accept()
            return
        super().keyPressEvent(e)


class TracePanel(QWidget):
    """What the dock holds: a line saying what is listed, and the rows."""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(2)
        top = QHBoxLayout()
        self.header = QLabel(HINT)
        self.header.setObjectName("trace_header")
        f = self.header.font()
        f.setBold(True)
        self.header.setFont(f)
        tip = QLabel("Double-click or Enter: go there")
        tip.setEnabled(False)
        top.addWidget(self.header, 1)
        top.addWidget(tip)
        lay.addLayout(top)
        self.table = RowTable()
        lay.addWidget(self.table, 1)

    def show_rows(self, header, rows):
        self.header.setText(header)
        t = self.table
        t.clear()
        items = []
        for r in rows:
            it = QTreeWidgetItem([r.where, r.sheet, r.role, r.name, r.desc])
            it.setData(0, Qt.UserRole, r)
            it.setToolTip(4, r.desc)
            items.append(it)
        t.addTopLevelItems(items)
        if items:
            t.setCurrentItem(items[0])

    def rows(self):
        t = self.table
        return [t.topLevelItem(i).data(0, Qt.UserRole) for i in range(t.topLevelItemCount())]


class Tracing:
    """MainWindow's Trace: the dock, the lookup, following the selection, going to a row."""

    def _build_trace(self):
        self.trace_panel = TracePanel()
        self.trace_panel.table.goRequested.connect(self.trace_go)
        dock = self.trace_dock = QDockWidget(WU.NAME, self)
        dock.setObjectName("trace")
        dock.setWidget(self.trace_panel)
        dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.LeftDockWidgetArea |
                             Qt.RightDockWidgetArea)
        dock.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable |
                         QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        # (above the command line, which stays along the very bottom)
        self.splitDockWidget(dock, self.cmd_dock, Qt.Vertical)
        dock.hide()
        dock.visibilityChanged.connect(self._trace_shown)
        dock.dockLocationChanged.connect(self._trace_moved)
        self._trace_subject = None          # (project, subject) listed
        self._trace_going = False           # (a row being gone to: its selection not followed)
        self._trace_timer = QTimer(self, singleShot=True, interval=150)
        self._trace_timer.timeout.connect(self._trace_refresh)

    def trace(self):
        """Trace (Ctrl+E): the panel opened (or raised) and filled with the places of the
        object selected, else the one under the cursor; the rows take the keys (Up, Down,
        Enter)."""
        dock = self.trace_dock
        dock.show()
        dock.raise_()
        got = self._trace_pick(self.view(), cursor=True)
        if got is not None:
            self._trace_list(*got)
        elif self._trace_subject is None:
            self.trace_panel.show_rows(HINT, [])
        self.trace_panel.table.setFocus()
        return got is not None

    def _trace_pick(self, v, cursor=False):
        """(project, subject) of the view's selection (the first that stands for something),
        else (cursor) of the object under the cursor, else None."""
        if v is None:
            return None
        p, s = v.project, v.sheet()
        ents = [s.entities[i] for i in sorted(v.sel) if i in s.entities]
        # (devices and wires before anything else picked with them)
        ents.sort(key=lambda e: 0 if hasattr(e, "defn") else 1)
        for e in ents:
            sub = WU.subject_of(p, s, e)
            if sub is not None:
                return p, sub
        if cursor and not ents and v.cursor is not None:
            from .view import PICKBOX
            e = v.pick_entity(v.cursor)
            if e is not None:
                sub = WU.subject_of(p, s, e, v.cursor, PICKBOX / v.scale)
                if sub is not None:
                    return p, sub
        return None

    def _trace_list(self, project, subject):
        self._trace_subject = (project, subject)
        self.trace_panel.show_rows(*WU.lookup(project, subject))

    def _trace_follow(self):
        """The selection changed: listed when the panel is open (nothing done when not)."""
        if self._trace_going or not self.trace_dock.isVisible():
            return
        got = self._trace_pick(self.view())
        if got is not None and got != self._trace_subject:
            self._trace_list(*got)

    def _trace_changed(self, project):
        """The project changed: the list made again (once, shortly) while it is shown."""
        if self._trace_subject is not None and self._trace_subject[0] is project and \
                self.trace_dock.isVisible():
            self._trace_timer.start()

    def _trace_moved(self, area):
        """Moved off the bottom: the command line goes back to its own height there (it
        took the panel's room and stayed tall)."""
        if area != Qt.BottomDockWidgetArea and self.cmd_dock.isVisible():
            self.resizeDocks([self.cmd_dock], [self.cmd_dock.sizeHint().height()],
                             Qt.Vertical)

    def _trace_shown(self, on):
        if on and self._trace_subject is not None:
            self._trace_timer.start()       # (changes made while it was closed)

    def _trace_refresh(self):
        if self._trace_subject is not None and self.trace_dock.isVisible():
            p, sub = self._trace_subject
            if any(d.project is p for _w, d in self.documents()):
                self.trace_panel.show_rows(*WU.lookup(p, sub))

    def trace_go(self, row):
        """Go to a row's place: its project's tab, its sheet, the object selected and
        centered. Something no longer there is said on the command line (and the list made
        again). Returns whether it went."""
        if row is None or self._trace_subject is None:
            return False
        p = self._trace_subject[0]
        doc = self.doc() if self.doc() is not None and self.doc().project is p else next(
            (d for i in range(self.tabs.count()) for d in [self.tabs.widget(i)]
             if getattr(d, "project", None) is p and hasattr(d, "view")), None)
        s = p.sheet_by_id(row.sheet_id)
        ents = [s.entities[i] for i in row.ids if i in s.entities] if s is not None else []
        if doc is None or not ents:
            self._say("%s %s isn't there any more (the list is made again)" % (
                row.role, row.name) if doc is not None else
                "That project is closed: Trace has nothing to go to")
            self._trace_refresh()
            return False
        v = doc.view
        self.tabs.setCurrentWidget(doc)
        self._trace_going = True
        try:
            if v.cmd is not None:
                v.cancel()
            if s.id != v.sheet_id:
                self._leave_title_block(v)
                v.show_sheet(s.id)
            v.set_selection({e.id for e in ents})
            box = row.box
            if box[2] - box[0] > 0 or box[3] - box[1] > 0:
                box = None
                for e in ents:
                    bb = e.bbox()
                    box = bb if box is None else (min(box[0], bb[0]), min(box[1], bb[1]),
                                                  max(box[2], bb[2]), max(box[3], bb[3]))
            k = s.k()
            v.zoom_to(box, (LEAST[0] * k, LEAST[1] * k))
        finally:
            self._trace_going = False
        return True
