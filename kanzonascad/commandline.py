"""The command line along the bottom of the window, as in AutoCAD: a few lines of history,
the current prompt with its options as buttons, and the input box. Type a command name or
alias (L, PL, C, M, CO, RO, TR...) and press Enter or Space; Enter on an empty line repeats
the last command. While a command runs it takes points (3,4  @1,0  @2<45), numbers and the
option letters shown in brackets."""

from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton)

from . import commands as C

HISTORY_LINES = 3


class CommandLine(QWidget):
    otherCommand = Signal(str)          # undo, redo, save... (commands.OTHER)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.view = None
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 2, 4, 2)
        v.setSpacing(2)
        self.history = QPlainTextEdit()
        self.history.setReadOnly(True)
        self.history.setFocusPolicy(Qt.NoFocus)
        self.history.setMaximumBlockCount(500)
        mono = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        self.history.setFont(mono)
        line_h = self.history.fontMetrics().lineSpacing()
        self.history.setFixedHeight(line_h * HISTORY_LINES + 8)
        v.addWidget(self.history)
        row = QHBoxLayout()
        row.setSpacing(4)
        self.label = QLabel()
        self.label.setTextFormat(Qt.RichText)
        row.addWidget(self.label)
        self.options = QHBoxLayout()
        self.options.setSpacing(2)
        row.addLayout(self.options)
        self.edit = QLineEdit()
        self.edit.setFont(mono)
        self.edit.setPlaceholderText("Type a command (L, PL, REC, C, A, T, M, CO, RO, SC, MI, "
                                     "E, TR, Z) and press Enter")
        self.edit.installEventFilter(self)
        row.addWidget(self.edit, 1)
        v.addLayout(row)
        self._buttons = []
        self._typing = False
        self.show_prompt("", [], False)

    def attach(self, view):
        """Follow a drawing view (the current tab's)."""
        if self.view is not None:
            for sig, slot in ((self.view.promptChanged, self.show_prompt),
                              (self.view.messaged, self.add_history)):
                try:
                    sig.disconnect(slot)
                except (RuntimeError, TypeError):
                    pass
        self.view = view
        if view is not None:
            view.promptChanged.connect(self.show_prompt)
            view.messaged.connect(self.add_history)
            self.show_prompt(*view._prompt)

    # ---- showing ---------------------------------------------------------------------------
    def add_history(self, text):
        self.history.appendPlainText(text)
        self.history.verticalScrollBar().setValue(self.history.verticalScrollBar().maximum())

    def show_prompt(self, text, options, typing):
        for b in self._buttons:
            b.hide()
            self.options.removeWidget(b)
            b.deleteLater()
        self._buttons = []
        self._typing = bool(typing)
        if not text:
            self.label.setText("<b>Command:</b>")
            return
        opts = "".join(" [%s]" % "/".join(lbl for lbl, _k in options)) if options else ""
        self.label.setText("<b>%s</b>%s:" % (text, opts))
        for label, key in options:
            b = QPushButton(label)
            b.setFocusPolicy(Qt.NoFocus)
            b.setFlat(True)
            b.setStyleSheet("QPushButton { color: #2f7bff; padding: 0 4px; }")
            b.clicked.connect(lambda _c=False, k=key: self._submit(k))
            self.options.addWidget(b)
            self._buttons.append(b)

    # ---- typing ----------------------------------------------------------------------------
    def take_key(self, event):
        """A key typed over the drawing: start typing here."""
        self.edit.setFocus()
        self.edit.insert(event.text())

    def eventFilter(self, obj, e):
        if obj is self.edit and e.type() == QEvent.KeyPress:
            k = e.key()
            if k in (Qt.Key_Return, Qt.Key_Enter) or (k == Qt.Key_Space and not self._typing):
                self._submit(self.edit.text())
                return True
            if k == Qt.Key_Escape:
                self.edit.clear()
                if self.view is not None:
                    self.view.cancel()
                    self.view.setFocus()
                return True
        return super().eventFilter(obj, e)

    def _submit(self, text):
        self.edit.clear()
        v = self.view
        if v is None:
            return
        if v.cmd is not None:
            shown = text if text else "<Enter>"
            self.add_history("  " + shown)
            if not v.input_text(text):
                self.add_history("Invalid input: %s" % text)
            if v.cmd is not None and self._typing:
                self.edit.setFocus()        # (TEXT: the next line is typed here too)
            else:
                v.setFocus()
            return
        t = text.strip()
        if not t:
            v.enter()
            v.setFocus()
            return
        self.add_history("Command: %s" % t.upper())
        if v.run_name(t):
            v.setFocus()
            return
        other = C.OTHER.get(t.upper())
        if other:
            self.otherCommand.emit(other)
            v.setFocus()
            return
        self.add_history('Unknown command "%s". Press F1 for the list of commands.' % t.upper())
