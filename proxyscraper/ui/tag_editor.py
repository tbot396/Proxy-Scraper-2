from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from proxyscraper.core.tag_manager import TagManager


class TagEditor(QWidget):
    tag_added = Signal(str)
    tag_removed = Signal(str)

    def __init__(self, tag_manager: TagManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tag_manager = tag_manager
        self._init_ui()
        self._load_tags()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        input_layout = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Neues Tag eingeben...")
        self.input.returnPressed.connect(self._add_tag)
        input_layout.addWidget(self.input)

        add_btn = QPushButton("Hinzufügen")
        add_btn.clicked.connect(self._add_tag)
        input_layout.addWidget(add_btn)

        remove_btn = QPushButton("Entfernen")
        remove_btn.clicked.connect(self._remove_tag)
        input_layout.addWidget(remove_btn)

        layout.addLayout(input_layout)

    def _load_tags(self) -> None:
        self.list_widget.clear()
        for tag in self.tag_manager.get_tags():
            self.list_widget.addItem(tag)

    def _add_tag(self) -> None:
        tag = self.input.text().strip()
        if not tag:
            return
        if self.tag_manager.add_tag(tag):
            self.list_widget.addItem(tag)
            self.tag_added.emit(tag)
        self.input.clear()

    def _remove_tag(self) -> None:
        selected = self.list_widget.currentItem()
        if not selected:
            return
        tag = selected.text()
        if self.tag_manager.remove_tag(tag):
            self.list_widget.takeItem(self.list_widget.row(selected))
            self.tag_removed.emit(tag)

    def refresh(self) -> None:
        self._load_tags()
