"""Office / PDF-XChange style ribbon: tabs of labeled button groups.

Built from the app's existing QActions (so checked states, shortcuts, enabling and tooltips
stay in sync with the menus). Double-click a tab (or Ctrl+F1) to collapse it to just the
tab names; click a tab to open it again.

Compact like LibreOffice's tabbed bar: two rows of small buttons, group names optional. A tab
too wide for the window shows its big buttons small, group by group from the right (as Office
does: the owner, 0.18, "the schematic ribbon goes off the screen"); one still too wide scrolls
sideways (mouse wheel).
"""

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtWidgets import (QTabWidget, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
                               QToolButton, QLabel, QFrame, QSizePolicy, QScrollArea, QMenu)

LARGE_ICON = 20
SMALL_ICON = 16
ROWS = 2                       # small buttons stacked per column
SMALL_HEIGHT = 22              # one row of small buttons, pixels


class _Strip(QScrollArea):
    """A tab's contents; scrolls sideways with the mouse wheel when the window is narrow."""

    def __init__(self, inner):
        super().__init__()
        self.setWidget(inner)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.horizontalScrollBar().setFixedHeight(7)      # thin: only shows when it's needed

    def showEvent(self, e):
        # scroll instead of squeezing button names (measured now: icons are set after
        # building), the ribbon first showing big buttons small where the room is short
        rib = self.parent()
        while rib is not None and not isinstance(rib, Ribbon):
            rib = rib.parent()
        if rib is not None and rib.currentWidget() is self:
            rib.fit()
        else:
            self.widget().setMinimumWidth(self.widget().sizeHint().width())
        super().showEvent(e)

    def wheelEvent(self, e):
        bar = self.horizontalScrollBar()
        if bar.maximum() > 0:
            bar.setValue(bar.value() - e.angleDelta().y())
            e.accept()
        else:
            super().wheelEvent(e)

    def sizeHint(self):
        h = self.widget().sizeHint()
        bar = self.horizontalScrollBar()
        return QSize(h.width(), h.height() + (bar.sizeHint().height() if bar.maximum() > 0 else 0))


class SplitButton(QToolButton):
    """A small ribbon button for several similar commands, as AutoCAD's ribbon has (Circle with
    an arrow for Arc): clicking it runs the one its face shows, the arrow beside it lists them
    all. The face starts as the first and then shows the one last used, or the tool that is
    on (picked by its shortcut or a menu too). Made by split_button."""

    def __init__(self, actions, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.NoFocus)     # (as every ribbon button: the drawing keeps it)
        self.setPopupMode(QToolButton.MenuButtonPopup)
        menu = QMenu(self)
        menu.addActions(actions)
        self.setMenu(menu)
        self.setDefaultAction(actions[0])
        menu.triggered.connect(self.setDefaultAction)
        for a in actions:
            if a.isCheckable():
                a.toggled.connect(self._toggled)
        self.setAutoRaise(True)
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.setIconSize(QSize(SMALL_ICON, SMALL_ICON))
        self.setFixedHeight(SMALL_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _toggled(self, on):
        a = self.sender()
        if on and a is not None and a is not self.defaultAction():
            self.setDefaultAction(a)

    def sizeHint(self):
        # as wide as its widest face, so the tab doesn't shift when the face changes
        h = super().sizeHint()
        fm = self.fontMetrics()
        now = fm.horizontalAdvance(self.text())
        most = max((fm.horizontalAdvance(a.iconText()) for a in self.menu().actions()),
                   default=now)
        return QSize(h.width() + max(0, most - now), h.height())

    def minimumSizeHint(self):
        return self.sizeHint()


def split_button(actions):
    """One ribbon button (SplitButton) for actions (the first is its face at the start); with
    a single action, that action itself (a plain button). None when there is none."""
    actions = [a for a in actions if a is not None]
    if len(actions) < 2:
        return actions[0] if actions else None
    return SplitButton(actions)


STAGES = ("large", "small", "icons")     # a group's buttons, from the most room to the least


class _Group:
    """A ribbon group's buttons, shown as built ("large": icon over its name, the full height;
    "small": two rows, the name beside the icon) or, in a window too narrow, smaller
    ("small", then "icons": two rows of icons alone)."""

    def __init__(self, size, grid, widgets, box):
        self.size, self.grid, self.widgets, self.box = size, grid, widgets, box
        self.shown = None

    def show(self, stage):
        if stage == self.shown:
            return
        self.shown = stage
        for w in self.widgets:
            self.grid.removeWidget(w)
        col = k = 0
        for w in self.widgets:
            split = isinstance(w, SplitButton)
            plain = isinstance(w, QToolButton) and not split
            # (a layer box is placed as it is; a split button in a group of small ones keeps
            # its own look until it shows as an icon)
            if (plain or split) and stage == "large":
                w.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
                w.setIconSize(QSize(LARGE_ICON, LARGE_ICON))
                w.setMinimumWidth(44 if plain else 52)
                w.setFixedHeight(ROWS * SMALL_HEIGHT)
                w.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            elif plain or (split and (self.size == "large" or stage == "icons")):
                w.setToolButtonStyle(Qt.ToolButtonIconOnly if stage == "icons"
                                     else Qt.ToolButtonTextBesideIcon)
                w.setIconSize(QSize(SMALL_ICON, SMALL_ICON))
                w.setMinimumWidth(0)
                w.setFixedHeight(SMALL_HEIGHT)
                w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            elif split and self.size == "small" and stage == "small":
                w.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            w.updateGeometry()
            if stage == "large":
                self.grid.addWidget(w, 0, col, ROWS, 1)
                col += 1
            else:
                self.grid.addWidget(w, k % ROWS, k // ROWS)
                k += 1


class Ribbon(QTabWidget):
    collapsedChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDocumentMode(True)
        self.setObjectName("ribbon")
        self._collapsed = False
        self._labels = []
        self._groups = {}               # tab page -> [_Group, ...], left to right
        self._fitted = {}               # tab page -> the room it was fitted to
        self.currentChanged.connect(lambda _i: self.fit())
        self._show_labels = False
        self.tabBar().tabBarDoubleClicked.connect(lambda _i: self.set_collapsed(not self._collapsed))
        self.tabBar().tabBarClicked.connect(self._tab_clicked)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    # ---- building ---------------------------------------------------------------
    def add_tab(self, title, groups):
        """groups: [(group title, 'large' | 'small', [QAction | QWidget | None, ...])]"""
        page = QWidget()
        self._groups[page] = []
        row = QHBoxLayout(page)
        row.setContentsMargins(2, 1, 2, 1)
        row.setSpacing(2)
        for gtitle, size, items in groups:
            row.addWidget(self._group(gtitle, size, items, page))
            line = QFrame()
            line.setFrameShape(QFrame.VLine)
            line.setFrameShadow(QFrame.Sunken)
            row.addWidget(line)
        row.addStretch(1)
        self.addTab(_Strip(page), title)
        return page

    def tab_index(self, title):
        for i in range(self.count()):
            if self.tabText(i) == title:
                return i
        return -1

    def show_tab(self, title, on, select=False):
        """Show or hide a tab that only belongs to some work (Block: in a block's tab)."""
        i = self.tab_index(title)
        if i < 0:
            return
        if not on and self.currentIndex() == i:
            self.setCurrentIndex(0)
        self.setTabVisible(i, bool(on))
        if on and select:
            self.setCurrentIndex(i)

    def _group(self, title, size, items, page):
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(2, 0, 2, 0)
        v.setSpacing(0)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(1)
        grid.setVerticalSpacing(0)
        widgets = []
        for item in items:
            if item is None:
                continue
            if isinstance(item, QWidget):
                w = item
            else:
                w = QToolButton()
                w.setDefaultAction(item)
                w.setAutoRaise(True)
                # (clicked, it leaves the keyboard with the drawing, so Esc still cancels and
                # deselects: the owner, 0.16)
                w.setFocusPolicy(Qt.NoFocus)
            widgets.append(w)
        group = _Group(size, grid, widgets, box)
        self._groups[page].append(group)
        group.show(size)
        v.addLayout(grid, 1)
        label = QLabel(title)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: gray; font-size: 7pt;")
        label.setVisible(self._show_labels)
        self._labels.append(label)
        v.addWidget(label)
        return box

    def fit(self, width=None):
        """The shown tab in the room there is: its groups as built when they fit; else, group
        by group from the right, big buttons shown small, then small ones as icons alone (the
        name in the tooltip), until it fits (or nothing is left to make smaller)."""
        strip = self.currentWidget()
        if not isinstance(strip, _Strip):
            return
        page = strip.widget()
        groups = self._groups.get(page, [])
        room = width if width is not None else strip.viewport().width()
        if room <= 0 or self._fitted.get(page) == (room, self._show_labels):
            return                      # (as it was: a resize that changed nothing here)
        self._fitted[page] = (room, self._show_labels)
        row = page.layout()

        def need():
            # (added up from the groups' own sizes: the row's cached ones lag behind a change)
            m = row.contentsMargins()
            ws = [row.itemAt(i).widget() for i in range(row.count())]
            ws = [w for w in ws if w is not None]
            for g in groups:
                g.grid.invalidate()
                g.box.layout().invalidate()
            return m.left() + m.right() + row.spacing() * max(0, len(ws) - 1) + \
                sum(w.sizeHint().width() for w in ws)
        for g in groups:
            g.show(g.size)
        for step in ("small", "icons"):
            for g in reversed(groups):
                if need() <= room:
                    break
                if STAGES.index(g.shown) < STAGES.index(step):
                    g.show(step)
        page.setMinimumWidth(need())
        row.invalidate()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.fit()

    def compacted(self):
        """How the shown tab's groups are shown now, where not as built: {index: stage}."""
        strip = self.currentWidget()
        page = strip.widget() if isinstance(strip, _Strip) else None
        return {i: g.shown for i, g in enumerate(self._groups.get(page, []))
                if g.shown != g.size}

    def set_group_names(self, on):
        """Show the group names under the buttons (Microsoft Office style); off is compact."""
        self._show_labels = bool(on)
        for label in self._labels:
            label.setVisible(self._show_labels)
        self.fit()
        if not self._collapsed:
            self.setMaximumHeight(self.expanded_height())

    # ---- collapsing ------------------------------------------------------------
    def expanded_height(self):
        """Tab names, two rows of buttons, group names if shown and room for a thin scrollbar."""
        label = self._labels[0].sizeHint().height() if self._labels and self._show_labels else 0
        return self.tabBar().sizeHint().height() + ROWS * SMALL_HEIGHT + 2 + label + 2 + 7 + 4

    def set_collapsed(self, on):
        self._collapsed = bool(on)
        if on:
            self.setMaximumHeight(self.tabBar().sizeHint().height())
        else:
            self.setMaximumHeight(self.expanded_height())
        self.collapsedChanged.emit(self._collapsed)

    def _tab_clicked(self, _index):
        if self._collapsed:
            self.set_collapsed(False)
