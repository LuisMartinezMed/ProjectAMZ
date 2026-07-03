from __future__ import annotations

from sqlalchemy import select

from PySide6.QtWidgets import QPushButton, QTableWidget, QVBoxLayout

from ..models import Supplier
from ..services.products_service import ProductsService
from ..services.purchases_service import PurchasesService
from .helpers import (
    BaseView,
    FormDialog,
    button_row,
    combo_current_id,
    configure_table,
    from_qdate,
    money_text,
    parse_decimal,
    parse_int,
    selected_row_id,
    set_table_rows,
)


class PurchasesView(BaseView):
    def __init__(self, engine):
        super().__init__(engine)
        self.po_table = QTableWidget()
        configure_table(self.po_table, ["PO ID", "Supplier", "Order date", "Expected", "Received", "Status", "Total", "Notes"])
        self.line_table = QTableWidget()
        configure_table(self.line_table, ["Line ID", "PO ID", "Product", "Ordered", "Received", "Lot cost", "Lot units", "Unit cost", "Inbound", "Notes"])
        refresh = QPushButton("Refresh")
        create_po = QPushButton("Create purchase order")
        add_line = QPushButton("Add purchase order line")
        receive = QPushButton("Receive selected line")
        refresh.clicked.connect(self.refresh)
        create_po.clicked.connect(self.create_purchase_order)
        add_line.clicked.connect(self.add_line)
        receive.clicked.connect(self.receive_line)
        layout = QVBoxLayout(self)
        layout.addLayout(button_row(refresh, create_po, add_line, receive))
        layout.addWidget(self.po_table)
        layout.addWidget(self.line_table)
        self.refresh()

    def refresh(self) -> None:
        def action():
            with self.session_scope() as session:
                purchases = PurchasesService(session)
                set_table_rows(
                    self.po_table,
                    [
                        [po.id, po.supplier.name, po.order_date, po.expected_arrival_date or "", po.received_date or "", po.status, money_text(po.total_cost), po.notes or ""]
                        for po in purchases.list_purchase_orders()
                    ],
                )
                set_table_rows(
                    self.line_table,
                    [
                        [line.id, line.purchase_order_id, line.base_product.name, line.ordered_physical_units, line.received_physical_units, money_text(line.supplier_lot_cost), line.supplier_lot_units, money_text(line.supplier_unit_cost), money_text(line.inbound_shipping_allocated), line.notes or ""]
                        for line in purchases.list_purchase_order_lines()
                    ],
                )

        self.run_action(action)

    def create_purchase_order(self) -> None:
        dialog = FormDialog("Create purchase order", self)
        supplier = dialog.add_line("Supplier name")
        order_date = dialog.add_date("Order date")
        expected = dialog.add_date("Expected arrival date")
        subtotal = dialog.add_line("Subtotal", "0")
        shipping = dialog.add_line("Shipping cost", "0")
        other = dialog.add_line("Other cost", "0")
        notes = dialog.add_text("Notes")
        if dialog.exec() != dialog.Accepted:
            return

        def action():
            supplier_name = supplier.text().strip()
            if not supplier_name:
                raise ValueError("Supplier name is required.")
            with self.session_scope() as session:
                supplier_obj = session.scalar(select(Supplier).where(Supplier.name == supplier_name))
                if supplier_obj is None:
                    supplier_obj = ProductsService(session).create_supplier(name=supplier_name)
                PurchasesService(session).create_purchase_order(
                    supplier_id=supplier_obj.id,
                    order_date=from_qdate(order_date),
                    expected_arrival_date=from_qdate(expected),
                    subtotal=parse_decimal(subtotal.text(), "Subtotal"),
                    shipping_cost=parse_decimal(shipping.text(), "Shipping cost"),
                    other_cost=parse_decimal(other.text(), "Other cost"),
                    notes=notes.toPlainText().strip() or None,
                )
            self.refresh()

        self.run_action(action, success="Purchase order created.")

    def add_line(self) -> None:
        po_id = selected_row_id(self.po_table)
        if po_id is None:
            self.run_action(lambda: (_ for _ in ()).throw(ValueError("Select a purchase order first.")))
            return
        dialog = FormDialog("Add purchase order line", self)
        product_combo = dialog.add_combo("Base product")
        with self.session_scope() as session:
            for product in ProductsService(session).list_base_products(active_only=True):
                product_combo.addItem(product.name, product.id)
        ordered = dialog.add_line("Ordered physical units", "1")
        lot_cost = dialog.add_line("Supplier lot cost", "0")
        lot_units = dialog.add_line("Supplier lot units", "1")
        inbound = dialog.add_line("Inbound shipping allocated", "0")
        notes = dialog.add_text("Notes")
        if dialog.exec() != dialog.Accepted:
            return

        def action():
            product_id = combo_current_id(product_combo)
            if product_id is None:
                raise ValueError("Select a product.")
            with self.session_scope() as session:
                PurchasesService(session).add_line(
                    purchase_order_id=po_id,
                    base_product_id=product_id,
                    ordered_physical_units=parse_int(ordered.text(), "Ordered units"),
                    supplier_lot_cost=parse_decimal(lot_cost.text(), "Supplier lot cost"),
                    supplier_lot_units=parse_int(lot_units.text(), "Supplier lot units"),
                    inbound_shipping_allocated=parse_decimal(inbound.text(), "Inbound shipping allocated"),
                    notes=notes.toPlainText().strip() or None,
                )
            self.refresh()

        self.run_action(action, success="Purchase order line added.")

    def receive_line(self) -> None:
        line_id = selected_row_id(self.line_table)
        if line_id is None:
            self.run_action(lambda: (_ for _ in ()).throw(ValueError("Select a purchase order line first.")))
            return
        dialog = FormDialog("Receive purchase order line", self)
        received_date = dialog.add_date("Received date")
        units = dialog.add_line("Received physical units (blank = ordered)", "")
        location = dialog.add_line("Warehouse location", "")
        notes = dialog.add_text("Notes")
        if dialog.exec() != dialog.Accepted:
            return

        def action():
            with self.session_scope() as session:
                PurchasesService(session).receive_line(
                    purchase_order_line_id=line_id,
                    received_date=from_qdate(received_date),
                    received_physical_units=parse_int(units.text(), "Received units", required=False),
                    warehouse_location=location.text().strip() or None,
                    notes=notes.toPlainText().strip() or None,
                )
            self.refresh()

        self.run_action(action, success="Purchase order received.")
