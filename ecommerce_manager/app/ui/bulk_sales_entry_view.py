from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout

from ..services.sales_service import SaleLineInput, SalesService
from ..utils.dates import require_date
from .helpers import BaseView, button_row, configure_table, parse_decimal, parse_int


class BulkSalesEntryView(BaseView):
    HEADERS = ["Sale date", "SKU", "Quantity", "Gross revenue", "Net received", "Order ID", "Settlement ID", "Notes", "Status"]

    def __init__(self, engine):
        super().__init__(engine)
        self.table = QTableWidget()
        configure_table(self.table, self.HEADERS)
        self.table.setRowCount(5)
        add = QPushButton("Add row")
        remove = QPushButton("Remove selected")
        validate = QPushButton("Validate rows")
        save = QPushButton("Save all valid rows")
        clear_saved = QPushButton("Clear saved rows")
        add.clicked.connect(self.add_row)
        remove.clicked.connect(self.remove_selected_row)
        validate.clicked.connect(self.validate_rows)
        save.clicked.connect(self.save_rows)
        clear_saved.clicked.connect(self.clear_saved_rows)
        note = QLabel("All rows are validated before saving. If any row has an error, no rows are saved.")
        note.setObjectName("MutedLabel")
        note.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addLayout(button_row(add, remove, validate, save, clear_saved))
        layout.addWidget(note)
        layout.addWidget(self.table)

    def add_row(self) -> None:
        self.table.insertRow(self.table.rowCount())

    def remove_selected_row(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def _cell_text(self, row: int, col: int) -> str:
        item = self.table.item(row, col)
        return item.text().strip() if item else ""

    def _set_status(self, row: int, status: str) -> None:
        self.table.setItem(row, 8, QTableWidgetItem(status))

    def _row_input(self, row: int) -> SaleLineInput | None:
        if not any(self._cell_text(row, col) for col in range(8)):
            return None
        return SaleLineInput(
            sale_date=require_date(self._cell_text(row, 0), "Sale date"),
            sku=self._cell_text(row, 1) or None,
            asin=None,
            quantity_listings_sold=parse_int(self._cell_text(row, 2), "Quantity"),
            gross_revenue=parse_decimal(self._cell_text(row, 3), "Gross revenue"),
            net_received=parse_decimal(self._cell_text(row, 4), "Net received", required=False),
            order_id=self._cell_text(row, 5) or None,
            settlement_id=self._cell_text(row, 6) or None,
            notes=self._cell_text(row, 7) or None,
            source="bulk_entry",
        )

    def validate_rows(self) -> None:
        def action():
            with self.session_scope() as session:
                service = SalesService(session)
                for row in range(self.table.rowCount()):
                    try:
                        sale_input = self._row_input(row)
                        if sale_input is None:
                            self._set_status(row, "")
                            continue
                        preview = service.preview_sale_line(sale_input)
                        self._set_status(row, f"OK: profit {preview.profit}")
                    except Exception as exc:
                        self._set_status(row, f"ERROR: {exc}")

        self.run_action(action)

    def save_rows(self) -> None:
        def action():
            sale_inputs: list[tuple[int, SaleLineInput]] = []
            has_error = False
            with self.session_scope() as session:
                service = SalesService(session)
                for row in range(self.table.rowCount()):
                    try:
                        sale_input = self._row_input(row)
                        if sale_input is None:
                            self._set_status(row, "")
                            continue
                        service.preview_sale_line(sale_input)
                        self._set_status(row, "Ready")
                        sale_inputs.append((row, sale_input))
                    except Exception as exc:
                        self._set_status(row, f"ERROR: {exc}")
                        has_error = True
            if has_error:
                raise ValueError("Fix invalid bulk sales rows before saving. No rows were saved.")
            if not sale_inputs:
                raise ValueError("No rows to save.")
            with self.session_scope() as session:
                service = SalesService(session)
                for _, sale_input in sale_inputs:
                    service.add_sale_line(sale_input)
            for row, _ in sale_inputs:
                self._set_status(row, "Saved")

        self.run_action(action, success="Bulk sales saved.")

    def clear_saved_rows(self) -> None:
        for row in reversed(range(self.table.rowCount())):
            if self._cell_text(row, 8).lower() == "saved":
                self.table.removeRow(row)
