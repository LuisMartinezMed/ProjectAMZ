from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QTableWidget, QVBoxLayout

from ..services.inventory_service import InventoryService
from ..services.products_service import ProductsService
from ..services.reports_service import ReportsService
from .helpers import (
    BaseView,
    DateRangeFilter,
    FormDialog,
    SearchBar,
    button_row,
    combo_current_id,
    configure_table,
    from_qdate,
    money_text,
    parse_decimal,
    parse_int,
    section_label,
    set_table_rows,
    show_info,
)


class InventoryView(BaseView):
    def __init__(self, engine):
        super().__init__(engine)
        self.search = SearchBar("Search product, listing, SKU")
        self.search.text_changed.connect(self.refresh)
        self.movement_type = QComboBox()
        self.movement_type.addItem("All movements", "all")
        for movement in ("initial_stock", "purchase_received", "sale", "adjustment"):
            self.movement_type.addItem(movement, movement)
        self.movement_type.currentIndexChanged.connect(self.refresh)
        self.date_range = DateRangeFilter()
        self.product_stock_table = QTableWidget()
        configure_table(self.product_stock_table, ["Product ID", "Base product", "Physical stock"])
        self.listing_stock_table = QTableWidget()
        configure_table(self.listing_stock_table, ["Listing ID", "SKU", "Listing", "Base product", "Units/listing", "Physical", "Sellable"])
        self.batch_table = QTableWidget()
        configure_table(self.batch_table, ["Batch ID", "Base product", "Received", "Initial", "Remaining", "Unit cost", "Status", "Location"])
        self.movement_table = QTableWidget()
        configure_table(self.movement_table, ["Movement ID", "Base product", "Date", "Type", "Qty change", "Reference", "Ref ID", "Notes"])
        refresh = QPushButton("Refresh")
        initial = QPushButton("Add initial stock")
        adjustment = QPushButton("Add stock adjustment")
        receive_po = QPushButton("Receive purchase order")
        refresh.clicked.connect(self.refresh)
        initial.clicked.connect(self.add_initial_stock)
        adjustment.clicked.connect(self.add_adjustment)
        receive_po.clicked.connect(lambda: show_info(self, "Purchases", "Use the Purchases screen to receive purchase order lines into FIFO."))
        filters = QHBoxLayout()
        filters.addWidget(self.search, 1)
        filters.addWidget(QLabel("Movement type"))
        filters.addWidget(self.movement_type)
        filters.addWidget(self.date_range)
        warning = QLabel(
            "Stock is calculated from FIFO batches and inventory movements. Do not manually edit stock totals."
        )
        warning.setObjectName("MutedLabel")
        warning.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addLayout(button_row(refresh, initial, adjustment, receive_po))
        layout.addLayout(filters)
        layout.addWidget(warning)
        layout.addWidget(section_label("Current stock by base product"))
        layout.addWidget(self.product_stock_table)
        layout.addWidget(section_label("Equivalent sellable stock by listing"))
        layout.addWidget(self.listing_stock_table)
        layout.addWidget(section_label("FIFO inventory batches"))
        layout.addWidget(self.batch_table)
        layout.addWidget(section_label("Inventory movements"))
        layout.addWidget(self.movement_table)
        self.refresh()

    def refresh(self, *_args) -> None:
        def action():
            query = self.search.text().lower()
            movement_filter = self.movement_type.currentData()
            start = self.date_range.start()
            end = self.date_range.end()
            with self.session_scope() as session:
                reports = ReportsService(session)
                product_rows = [
                    row for row in reports.current_stock_by_product()
                    if not query or query in f"{row.id} {row.name}".lower()
                ]
                set_table_rows(
                    self.product_stock_table,
                    [[row.id, row.name, int(row.physical_stock or 0)] for row in product_rows],
                )
                listing_rows = [
                    row
                    for row in reports.current_stock_by_listing()
                    if not query
                    or query
                    in f"{row['sku']} {row['listing_name']} {row['base_product_name']}".lower()
                ]
                set_table_rows(
                    self.listing_stock_table,
                    [
                        [row["listing_id"], row["sku"], row["listing_name"], row["base_product_name"], row["units_per_listing"], row["physical_stock"], row["equivalent_listing_stock"]]
                        for row in listing_rows
                    ],
                )
                batch_rows = [
                    row for row in reports.fifo_batches()
                    if not query or query in f"{row.id} {row.base_product_name}".lower()
                ]
                set_table_rows(
                    self.batch_table,
                    [
                        [row.id, row.base_product_name, row.received_date, row.initial_physical_units, row.remaining_physical_units, money_text(row.unit_landed_cost), row.status, row.warehouse_location or ""]
                        for row in batch_rows
                    ],
                )
                movement_rows = [
                    row
                    for row in reports.inventory_movements()
                    if (movement_filter == "all" or row.movement_type == movement_filter)
                    and start <= row.movement_date <= end
                    and (not query or query in f"{row.id} {row.base_product_name} {row.movement_type} {row.notes or ''}".lower())
                ]
                set_table_rows(
                    self.movement_table,
                    [
                        [row.id, row.base_product_name, row.movement_date, row.movement_type, row.physical_quantity_change, row.reference_type or "", row.reference_id or "", row.notes or ""]
                        for row in movement_rows
                    ],
                )

        self.run_action(action)

    def _product_dialog(self, title: str) -> FormDialog:
        dialog = FormDialog(title, self)
        combo = dialog.add_combo("Base product")
        with self.session_scope() as session:
            for product in ProductsService(session).list_base_products(active_only=True):
                combo.addItem(product.name, product.id)
        dialog.product_combo = combo
        return dialog

    def add_initial_stock(self) -> None:
        dialog = self._product_dialog("Add initial stock")
        received = dialog.add_date("Received date")
        units = dialog.add_line("Physical units", "1")
        cost = dialog.add_line("Unit landed cost", "0")
        location = dialog.add_line("Warehouse location", "")
        notes = dialog.add_text("Notes")
        if dialog.exec() != dialog.Accepted:
            return

        def action():
            product_id = combo_current_id(dialog.product_combo)
            if product_id is None:
                raise ValueError("Select a product.")
            with self.session_scope() as session:
                InventoryService(session).create_initial_stock(
                    base_product_id=product_id,
                    received_date=from_qdate(received),
                    physical_units=parse_int(units.text(), "Physical units"),
                    unit_landed_cost=parse_decimal(cost.text(), "Unit landed cost"),
                    warehouse_location=location.text().strip() or None,
                    notes=notes.toPlainText().strip() or None,
                )
            self.refresh()

        self.run_action(action, success="Initial stock added.")

    def add_adjustment(self) -> None:
        dialog = self._product_dialog("Add stock adjustment")
        adjustment_date = dialog.add_date("Adjustment date")
        qty = dialog.add_line("Quantity change", "0")
        reason = dialog.add_line("Reason", "")
        notes = dialog.add_text("Notes")
        if dialog.exec() != dialog.Accepted:
            return

        def action():
            product_id = combo_current_id(dialog.product_combo)
            if product_id is None:
                raise ValueError("Select a product.")
            with self.session_scope() as session:
                InventoryService(session).adjust_stock(
                    base_product_id=product_id,
                    adjustment_date=from_qdate(adjustment_date),
                    physical_quantity_change=parse_int(qty.text(), "Quantity change"),
                    reason=reason.text().strip() or "manual",
                    notes=notes.toPlainText().strip() or None,
                )
            self.refresh()

        self.run_action(action, success="Stock adjustment added.")
