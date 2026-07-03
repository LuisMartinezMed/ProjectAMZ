from __future__ import annotations

from sqlalchemy import select

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout

from ..database import seed_defaults
from ..models import AppSetting
from .helpers import BaseView, button_row, configure_table


SETTING_GROUPS = {
    "Sales velocity": ["default_sales_velocity_days"],
    "Restock planning": [
        "default_supplier_lead_time_days",
        "default_shipping_days",
        "default_safety_stock_days",
        "default_target_stock_days",
        "default_reorder_review_days",
    ],
    "Inventory behavior": ["allow_negative_inventory"],
    "Localization": ["currency", "timezone"],
}


class SettingsView(BaseView):
    def __init__(self, engine):
        super().__init__(engine)
        self.table = QTableWidget()
        configure_table(self.table, ["Group", "Key", "Value"])
        refresh = QPushButton("Refresh")
        save = QPushButton("Save")
        reset = QPushButton("Reset defaults")
        refresh.clicked.connect(self.refresh)
        save.clicked.connect(self.save)
        reset.clicked.connect(self.reset_defaults)
        note = QLabel("Changes affect future calculations and planning defaults. Historical sales remain unchanged.")
        note.setObjectName("MutedLabel")
        note.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addLayout(button_row(refresh, save, reset))
        layout.addWidget(note)
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self) -> None:
        def action():
            with self.session_scope() as session:
                settings = {setting.key: setting for setting in session.scalars(select(AppSetting)).all()}
                rows = []
                for group, keys in SETTING_GROUPS.items():
                    for key in keys:
                        rows.append((group, settings.get(key)))
                self.table.setRowCount(len(rows))
                for row, (group, setting) in enumerate(rows):
                    group_item = QTableWidgetItem(group)
                    group_item.setFlags(group_item.flags() & ~Qt.ItemIsEditable)
                    key = setting.key if setting else ""
                    value = setting.value if setting else ""
                    key_item = QTableWidgetItem(key)
                    key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(row, 0, group_item)
                    self.table.setItem(row, 1, key_item)
                    self.table.setItem(row, 2, QTableWidgetItem(value))

        self.run_action(action)

    def save(self) -> None:
        def action():
            with self.session_scope() as session:
                for row in range(self.table.rowCount()):
                    key_item = self.table.item(row, 1)
                    if key_item is None or not key_item.text():
                        continue
                    value = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
                    setting = session.scalar(select(AppSetting).where(AppSetting.key == key_item.text()))
                    if setting:
                        setting.value = value
            self.refresh()

        self.run_action(action, success="Settings saved.")

    def reset_defaults(self) -> None:
        def action():
            with self.session_scope() as session:
                for setting in session.scalars(select(AppSetting)).all():
                    session.delete(setting)
                session.flush()
                seed_defaults(session)
            self.refresh()

        self.run_action(action, success="Defaults restored.")
