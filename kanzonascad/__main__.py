"""Start KanzonasCAD:  python -m kanzonascad [project.kzcad | drawing.dxf ...]
Self-test:  python -m kanzonascad --selftest selftest.log  (exit code 0 when every check passed)"""

import argparse
import os
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kanzonascad")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--selftest", metavar="LOG", help="run the self-test, write LOG, exit")
    args = ap.parse_args(argv)

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("KanzonasCAD")
    app.setOrganizationName("KanzonasCAD")
    from .theme import app_icon
    app.setWindowIcon(app_icon())

    if args.selftest:
        from .selftest import run
        return run(args.selftest)

    from .main_window import MainWindow
    win = MainWindow()
    opened = False
    for f in args.files:
        if os.path.exists(f) and win.open_path(f) is not None:
            opened = True
    win.show()
    if win.offer_recovery():
        opened = True
    if not opened:
        win.new_project()
    from PySide6.QtCore import QTimer
    QTimer.singleShot(5000, win.start_update_check)     # (once the window is up)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
