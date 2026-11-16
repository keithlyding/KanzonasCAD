"""Shared test helpers: one QApplication, a window with a fresh project."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

APP = QApplication.instance() or QApplication([])


def window():
    from kanzonascad.main_window import MainWindow
    w = MainWindow()
    w.resize(1200, 800)
    d = w.new_project()
    w.show()
    APP.processEvents()
    return w, d.view


def type_in(view, *items):
    """Feed typed input to the running command, as the command line does."""
    for t in items:
        assert view.cmd is not None, "no command running for %r" % (t,)
        ok = view.input_text(t)
        assert ok, "input %r was not used" % (t,)


def by_base_point(view):
    """Hold the symbol being inserted by its base point (B until past its pins), as tests
    written before 0.16 placed symbols: since then Insert holds a symbol by its first pin
    (tests/test_insert_hold.py checks that)."""
    cmd = view.cmd
    for _i in range(len(cmd.holds) - 1):
        assert view.input_text("B")
