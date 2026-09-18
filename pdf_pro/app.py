"""PDF_Pro application entry."""

from __future__ import annotations

import os
import sys

from pdf_pro.constants import APP_ID, APP_NAME, ORG_NAME


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    # Never make outbound network connections.
    os.environ.setdefault("QT_LOGGING_RULES", "qt.network.ssl.warning=false")
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    from PySide6.QtCore import QCoreApplication

    QCoreApplication.setApplicationName(APP_NAME)
    QCoreApplication.setOrganizationName(ORG_NAME)
    QCoreApplication.setApplicationVersion("0.1.4")
    QCoreApplication.setOrganizationDomain(APP_ID)

    app = QApplication(argv)
    from pdf_pro.ui.theme import apply_theme

    apply_theme(app)
    from pdf_pro.paths import icon_path

    ic = icon_path(256)
    if ic.is_file():
        app.setWindowIcon(QIcon(str(ic)))
    from pdf_pro.ui.main_window import MainWindow

    win = MainWindow()
    win.show()
    if len(argv) > 1 and argv[1].lower().endswith(".pdf"):
        from pathlib import Path

        win.open_path(Path(argv[1]))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
