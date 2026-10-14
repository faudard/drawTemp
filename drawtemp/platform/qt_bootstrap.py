"""Opt-in Qt 6 composition probe; never changes the legacy launchers or projects."""
import argparse
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="Create Widgets + Quick, then exit")
    args = parser.parse_args(argv)
    if sys.version_info[:2] != (3, 12):
        parser.error("The R0 Qt preview is qualified on Python 3.12 only")
    try:
        from PySide6.QtCore import QTimer, QUrl, qVersion
        from PySide6.QtWidgets import QApplication, QMainWindow
        from PySide6.QtQuickWidgets import QQuickWidget
    except ImportError as exc:
        print('Qt 6 unavailable: install with python -m pip install ".[qt6]". ' + str(exc), file=sys.stderr)
        return 2
    app = QApplication([sys.argv[0]])
    window = QMainWindow()
    window.setWindowTitle("DrawTemp 5.0 — R0 Qt 6 Foundation")
    view = QQuickWidget()
    view.setResizeMode(QQuickWidget.SizeRootObjectToView)
    view.setSource(QUrl.fromLocalFile(str(Path(__file__).resolve().parents[1] / "render/Foundation.qml")))
    if view.status() == QQuickWidget.Error:
        print("\n".join(error.toString() for error in view.errors()), file=sys.stderr)
        return 1
    window.setCentralWidget(view)
    window.resize(960, 540)
    window.show()
    if args.smoke:
        QTimer.singleShot(150, app.quit)
    status = app.exec()
    if view.status() == QQuickWidget.Error or view.rootObject() is None:
        return 1
    print("Qt " + qVersion() + ": Widgets + shared Quick component loaded")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
