from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow


def main() -> int:
    application = QApplication.instance() or QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("离线多人有声小说")
    window.setCentralWidget(QLabel("小说转听书工具", parent=window))
    window.resize(960, 640)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())

