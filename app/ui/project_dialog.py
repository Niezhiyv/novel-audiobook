from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


@dataclass(slots=True)
class ProjectDialogValues:
    title: str
    source_path: Path
    project_root: Path


class ProjectDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("创建小说项目")
        self.resize(560, 180)

        self.title_input = QLineEdit(self)
        self.source_input = QLineEdit(self)
        self.root_input = QLineEdit(self)
        source_button = QPushButton("选择 TXT", self)
        root_button = QPushButton("选择目录", self)

        source_row = QHBoxLayout()
        source_row.addWidget(self.source_input)
        source_row.addWidget(source_button)
        root_row = QHBoxLayout()
        root_row.addWidget(self.root_input)
        root_row.addWidget(root_button)

        form = QFormLayout()
        form.addRow("项目名称", self.title_input)
        form.addRow("小说 TXT", source_row)
        form.addRow("保存目录", root_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        source_button.clicked.connect(self._choose_source)
        root_button.clicked.connect(self._choose_root)

    def values(self) -> ProjectDialogValues:
        return ProjectDialogValues(
            title=self.title_input.text().strip(),
            source_path=Path(self.source_input.text().strip()),
            project_root=Path(self.root_input.text().strip()),
        )

    def _choose_source(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择小说 TXT",
            "",
            "文本文件 (*.txt);;所有文件 (*)",
        )
        if path:
            self.source_input.setText(path)
            if not self.title_input.text().strip():
                self.title_input.setText(Path(path).stem)

    def _choose_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择项目保存目录")
        if path:
            self.root_input.setText(path)

    def _validate_and_accept(self) -> None:
        values = self.values()
        if not values.title or not values.source_path.is_file() or not values.project_root:
            return
        self.accept()
