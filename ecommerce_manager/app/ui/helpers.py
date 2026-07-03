from __future__ import annotations

import csv
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Sequence

from sqlalchemy.orm import Session

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QAbstractItemView,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..utils.money import parse_percentage as parse_percentage_value


def today_qdate() -> QDate:
    today = date.today()
    return QDate(today.year, today.month, today.day)


def to_qdate(value: date | None = None) -> QDate:
    value = value or date.today()
    return QDate(value.year, value.month, value.day)


def from_qdate(widget: QDateEdit) -> date:
    qdate = widget.date()
    return date(qdate.year(), qdate.month(), qdate.day())


def money_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        amount = Decimal(value)
        sign = "-" if amount < 0 else ""
        return f"{sign}${abs(amount):,.2f}"
    except Exception:
        return str(value)


def rate_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{Decimal(value) * 100:.1f}%"
    except Exception:
        return str(value)


def parse_decimal(text: str, field_name: str, *, required: bool = True) -> Decimal | None:
    raw = (text or "").strip().replace(",", "")
    if not raw:
        if required:
            raise ValueError(f"{field_name} is required")
        return None
    try:
        return Decimal(raw)
    except Exception as exc:
        raise ValueError(f"{field_name} must be a valid number") from exc


def parse_int(text: str, field_name: str, *, required: bool = True) -> int | None:
    raw = (text or "").strip()
    if not raw:
        if required:
            raise ValueError(f"{field_name} is required")
        return None
    try:
        return int(raw)
    except Exception as exc:
        raise ValueError(f"{field_name} must be a whole number") from exc


def parse_percentage(text: str, field_name: str, *, required: bool = True) -> Decimal | None:
    raw = (text or "").strip()
    if not raw:
        if required:
            raise ValueError(f"{field_name} is required")
        return None
    try:
        return parse_percentage_value(raw)
    except Exception as exc:
        raise ValueError(f"{field_name} must be a percentage like 0.21, 21, or 21%") from exc


def combo_current_id(combo: QComboBox) -> int | None:
    value = combo.currentData()
    if value is None:
        return None
    return int(value)


def configure_table(table: QTableWidget, headers: Sequence[str]) -> None:
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(list(headers))
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setWordWrap(False)
    table.setMinimumHeight(220)
    table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
    table.verticalHeader().setDefaultSectionSize(32)
    table.horizontalHeader().setMinimumSectionSize(90)
    table.horizontalHeader().setDefaultSectionSize(150)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)


def set_table_rows(table: QTableWidget, rows: Iterable[Sequence[Any]]) -> None:
    rows = list(rows)
    table.setRowCount(len(rows))
    for row_idx, row_values in enumerate(rows):
        for col_idx, value in enumerate(row_values):
            item = QTableWidgetItem("" if value is None else str(value))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            if isinstance(value, str) and value.startswith("-$"):
                item.setData(Qt.ForegroundRole, Qt.GlobalColor.red)
            table.setItem(row_idx, col_idx, item)


def selected_row_id(table: QTableWidget) -> int | None:
    row = table.currentRow()
    if row < 0:
        return None
    item = table.item(row, 0)
    if item is None or not item.text():
        return None
    return int(item.text())


def show_error(parent: QWidget, title: str, exc: Exception | str) -> None:
    QMessageBox.critical(parent, title, str(exc))


def show_info(parent: QWidget, title: str, message: str) -> None:
    QMessageBox.information(parent, title, message)


class MetricCard(QFrame):
    def __init__(self, title: str, value: str = "", subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setMinimumSize(180, 104)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("MetricCardTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("MetricCardValue")
        self.value_label.setMinimumHeight(34)
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("MutedLabel")
        self.subtitle_label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        if subtitle:
            layout.addWidget(self.subtitle_label)
        layout.addStretch(1)

    def set_value(self, value: Any, *, negative: bool = False) -> None:
        self.value_label.setText(str(value))
        self.value_label.setProperty("negative", negative)
        self.value_label.style().unpolish(self.value_label)
        self.value_label.style().polish(self.value_label)


class SectionHeader(QWidget):
    def __init__(self, title: str, description: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 14, 0, 4)
        layout.setSpacing(3)
        layout.addWidget(title_label)
        if description:
            desc = QLabel(description)
            desc.setObjectName("MutedLabel")
            desc.setWordWrap(True)
            layout.addWidget(desc)


class SearchBar(QWidget):
    def __init__(self, placeholder: str = "Search", parent: QWidget | None = None):
        super().__init__(parent)
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.input)

    @property
    def text_changed(self):
        return self.input.textChanged

    def text(self) -> str:
        return self.input.text().strip()


class StatusBadge(QLabel):
    def __init__(self, text: str = "", tone: str = "neutral", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName("StatusBadge")
        self.set_tone(tone)

    def set_tone(self, tone: str) -> None:
        self.setProperty("tone", tone)
        self.style().unpolish(self)
        self.style().polish(self)


class MoneyLabel(QLabel):
    def set_money(self, value: Any) -> None:
        self.setText(money_text(value))
        try:
            negative = Decimal(value or 0) < 0
        except Exception:
            negative = False
        self.setProperty("negative", negative)
        self.style().unpolish(self)
        self.style().polish(self)


class PercentageLabel(QLabel):
    def set_percentage(self, value: Any) -> None:
        self.setText(rate_text(value))
        try:
            negative = Decimal(value or 0) < 0
        except Exception:
            negative = False
        self.setProperty("negative", negative)
        self.style().unpolish(self)
        self.style().polish(self)


class DateRangeFilter(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.start_date = QDateEdit(to_qdate())
        self.end_date = QDateEdit(to_qdate())
        for widget in (self.start_date, self.end_date):
            widget.setCalendarPopup(True)
            widget.setDisplayFormat("yyyy-MM-dd")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Start"))
        layout.addWidget(self.start_date)
        layout.addWidget(QLabel("End"))
        layout.addWidget(self.end_date)

    def start(self) -> date:
        return from_qdate(self.start_date)

    def end(self) -> date:
        return from_qdate(self.end_date)


def grid_cards(cards: Sequence[MetricCard], columns: int = 4) -> QGridLayout:
    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(12)
    for idx, card in enumerate(cards):
        card.setMinimumSize(180, 104)
        grid.addWidget(card, idx // columns, idx % columns)
    rows = (len(cards) + columns - 1) // columns
    for row in range(rows):
        grid.setRowMinimumHeight(row, 108)
    for col in range(columns):
        grid.setColumnStretch(col, 1)
    return grid


class BaseView(QWidget):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine

    @contextmanager
    def session_scope(self):
        with Session(self.engine) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    def run_action(self, action, *, success: str | None = None) -> None:
        try:
            action()
            if success:
                show_info(self, "Done", success)
        except Exception as exc:
            show_error(self, "Action failed", exc)


class FormDialog(QDialog):
    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.form = QFormLayout()
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(self.form)
        layout.addWidget(self.buttons)

    def add_line(self, label: str, value: str = "") -> QLineEdit:
        field = QLineEdit(value)
        self.form.addRow(label, field)
        return field

    def add_text(self, label: str, value: str = "") -> QTextEdit:
        field = QTextEdit(value)
        field.setFixedHeight(72)
        self.form.addRow(label, field)
        return field

    def add_date(self, label: str, value: date | None = None) -> QDateEdit:
        field = QDateEdit(to_qdate(value))
        field.setCalendarPopup(True)
        field.setDisplayFormat("yyyy-MM-dd")
        self.form.addRow(label, field)
        return field

    def add_combo(self, label: str) -> QComboBox:
        combo = QComboBox()
        self.form.addRow(label, combo)
        return combo


def button_row(*buttons: QPushButton) -> QHBoxLayout:
    layout = QHBoxLayout()
    for button in buttons:
        layout.addWidget(button)
    layout.addStretch(1)
    return layout


def section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet("font-weight: 600; margin-top: 8px;")
    return label


def write_csv(path: str | Path, headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)
