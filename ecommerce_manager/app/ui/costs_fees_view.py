from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QTableWidget, QVBoxLayout

from ..models import Listing
from ..services.costs_service import CostsService
from ..services.inventory_service import InventoryService
from ..services.products_service import ProductsService
from .helpers import (
    BaseView,
    FormDialog,
    combo_current_id,
    configure_table,
    from_qdate,
    money_text,
    parse_decimal,
    parse_int,
    parse_percentage,
    rate_text,
    section_label,
    set_table_rows,
)


class CostsFeesView(BaseView):
    def __init__(self, engine):
        super().__init__(engine)
        self.listing_combo = QComboBox()
        self.listing_combo.currentIndexChanged.connect(self.refresh_histories)

        refresh = QPushButton("Refresh")
        add_cost = QPushButton("Add cost version")
        add_fee = QPushButton("Add fee version")
        add_price = QPushButton("Add price version")
        refresh.clicked.connect(self.refresh)
        add_cost.clicked.connect(self.add_cost_version)
        add_fee.clicked.connect(self.add_fee_version)
        add_price.clicked.connect(self.add_price_version)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #1f6f43;")
        note = QLabel("New versions do not modify historical sales or existing FIFO inventory batches.")
        note.setWordWrap(True)
        self.summary_label = QLabel("Select a listing to view current stock and version history.")
        self.summary_label.setObjectName("MutedLabel")
        self.summary_label.setWordWrap(True)

        selector = QHBoxLayout()
        selector.addWidget(self.listing_combo, 1)
        selector.addWidget(refresh)
        selector.addWidget(add_cost)
        selector.addWidget(add_fee)
        selector.addWidget(add_price)

        self.cost_table = QTableWidget()
        configure_table(
            self.cost_table,
            [
                "ID",
                "Active",
                "Effective range",
                "Supplier unit",
                "Inbound",
                "Warehouse",
                "Prep",
                "Other",
                "Total",
                "Notes",
            ],
        )
        self.fee_table = QTableWidget()
        configure_table(
            self.fee_table,
            [
                "ID",
                "Active",
                "Effective range",
                "Referral",
                "FBA",
                "Storage",
                "Shipping",
                "Other",
                "Total",
                "Fee %",
                "Notes",
            ],
        )
        self.price_table = QTableWidget()
        configure_table(self.price_table, ["ID", "Active", "Effective range", "Suggested price", "BuyBox %", "Notes"])

        layout = QVBoxLayout(self)
        layout.addLayout(selector)
        layout.addWidget(self.summary_label)
        layout.addWidget(note)
        layout.addWidget(self.status_label)
        layout.addWidget(section_label("Cost history"))
        layout.addWidget(self.cost_table)
        layout.addWidget(section_label("Fee history"))
        layout.addWidget(self.fee_table)
        layout.addWidget(section_label("Price history"))
        layout.addWidget(self.price_table)
        self.refresh()

    def refresh(self) -> None:
        def action():
            current = combo_current_id(self.listing_combo)
            self.listing_combo.blockSignals(True)
            self.listing_combo.clear()
            with self.session_scope() as session:
                for listing in ProductsService(session).list_listings(active_only=True):
                    self.listing_combo.addItem(f"{listing.sku} - {listing.listing_name}", listing.id)
            if current is not None:
                idx = self.listing_combo.findData(current)
                if idx >= 0:
                    self.listing_combo.setCurrentIndex(idx)
            self.listing_combo.blockSignals(False)
            self.refresh_histories()

        self.run_action(action)

    def refresh_histories(self, *_args) -> None:
        listing_id = combo_current_id(self.listing_combo)
        if listing_id is None:
            self.summary_label.setText("Select a listing to view current stock and version history.")
            set_table_rows(self.cost_table, [])
            set_table_rows(self.fee_table, [])
            set_table_rows(self.price_table, [])
            return

        def action():
            with self.session_scope() as session:
                listing = session.get(Listing, listing_id)
                if listing is None:
                    raise ValueError("Selected listing no longer exists.")
                costs = CostsService(session)
                current_stock = InventoryService(session).current_stock(listing.base_product_id)
                sellable_stock = current_stock // listing.units_per_listing
                self.summary_label.setText(
                    " | ".join(
                        [
                            f"SKU: {listing.sku}",
                            f"ASIN: {listing.asin or ''}",
                            f"Listing: {listing.listing_name}",
                            f"Units/listing: {listing.units_per_listing}",
                            f"Physical stock: {current_stock}",
                            f"Sellable stock: {sellable_stock}",
                        ]
                    )
                )
                set_table_rows(
                    self.cost_table,
                    [
                        [
                            version.id,
                            "Active" if version.effective_to is None else "",
                            self._range_text(version.effective_from, version.effective_to),
                            money_text(version.supplier_unit_cost),
                            money_text(version.inbound_shipping_cost_per_unit),
                            money_text(version.warehouse_cost_per_unit),
                            money_text(version.prep_cost_per_unit),
                            money_text(version.other_cost_per_unit),
                            money_text(version.total_landed_cost_per_unit),
                            "View notes" if version.notes else "",
                        ]
                        for version in costs.list_product_cost_versions(listing.base_product_id)
                    ],
                )
                set_table_rows(
                    self.fee_table,
                    [
                        [
                            version.id,
                            "Active" if version.effective_to is None else "",
                            self._range_text(version.effective_from, version.effective_to),
                            money_text(version.referral_fee),
                            money_text(version.fba_fee),
                            money_text(version.storage_fee),
                            money_text(version.amazon_shipping_or_fulfillment_fee),
                            money_text(version.other_marketplace_fee),
                            money_text(version.estimated_total_fee),
                            rate_text(version.fee_percentage),
                            "View notes" if version.notes else "",
                        ]
                        for version in costs.list_marketplace_fee_versions(listing.id, listing.marketplace_id)
                    ],
                )
                set_table_rows(
                    self.price_table,
                    [
                        [
                            version.id,
                            "Active" if version.effective_to is None else "",
                            self._range_text(version.effective_from, version.effective_to),
                            money_text(version.suggested_selling_price),
                            rate_text(version.buybox_percentage),
                            "View notes" if version.notes else "",
                        ]
                        for version in costs.list_price_versions(listing.id, listing.marketplace_id)
                    ],
                )

        self.run_action(action)

    def add_cost_version(self) -> None:
        listing_id = self._selected_listing_id()
        if listing_id is None:
            return
        dialog = FormDialog("Add cost version", self)
        helper = QLabel(
            "Do not include Amazon fees or Amazon shipping here if you are using Ingreso Neto from Amazon. "
            "These costs are for internal landed inventory cost only."
        )
        helper.setWordWrap(True)
        dialog.form.addRow(helper)
        dialog.form.addRow(section_label("Effective date"))
        effective_from = dialog.add_date("Effective from")
        dialog.form.addRow(section_label("Supplier cost"))
        dialog.form.addRow(QLabel("Supplier lot cost: total cost paid to supplier for the lot."))
        supplier_lot_cost = dialog.add_line("Supplier lot cost", "0")
        dialog.form.addRow(QLabel("Supplier lot units: physical units in that supplier lot."))
        supplier_lot_units = dialog.add_line("Supplier lot units", "1")
        dialog.form.addRow(QLabel("Supplier unit cost: supplier lot cost / supplier lot units."))
        supplier_unit_cost = dialog.add_line("Supplier unit cost", "")
        dialog.form.addRow(section_label("Internal costs"))
        dialog.form.addRow(QLabel("Inbound shipping / unit: internal inbound shipping cost per physical unit."))
        inbound = dialog.add_line("Inbound shipping / unit", "0")
        dialog.form.addRow(QLabel("Warehouse / unit: internal warehouse or handling cost per physical unit."))
        warehouse = dialog.add_line("Warehouse / unit", "0")
        dialog.form.addRow(QLabel("Prep / unit: labeling, bundling, prep, packaging."))
        prep = dialog.add_line("Prep / unit", "0")
        dialog.form.addRow(QLabel("Other / unit: other internal cost."))
        other = dialog.add_line("Other / unit", "0")
        dialog.form.addRow(section_label("Total landed cost"))
        dialog.form.addRow(QLabel("Total landed / unit: internal COGS per physical unit."))
        total = dialog.add_line("Total landed / unit", "")
        notes = dialog.add_text("Notes")
        if dialog.exec() != dialog.Accepted:
            return

        def action():
            created_id = None
            with self.session_scope() as session:
                listing = session.get(Listing, listing_id)
                if listing is None:
                    raise ValueError("Selected listing no longer exists.")
                version = CostsService(session).create_product_cost_version(
                    base_product_id=listing.base_product_id,
                    effective_from=from_qdate(effective_from),
                    supplier_lot_cost=parse_decimal(supplier_lot_cost.text(), "Supplier lot cost"),
                    supplier_lot_units=parse_int(supplier_lot_units.text(), "Supplier lot units"),
                    supplier_unit_cost=parse_decimal(supplier_unit_cost.text(), "Supplier unit cost", required=False),
                    inbound_shipping_cost_per_unit=parse_decimal(inbound.text(), "Inbound shipping"),
                    warehouse_cost_per_unit=parse_decimal(warehouse.text(), "Warehouse cost"),
                    prep_cost_per_unit=parse_decimal(prep.text(), "Prep cost"),
                    other_cost_per_unit=parse_decimal(other.text(), "Other cost"),
                    total_landed_cost_per_unit=parse_decimal(total.text(), "Total landed cost", required=False),
                    notes=notes.toPlainText().strip() or None,
                )
                created_id = version.id
            self.refresh_histories()
            self.status_label.setText(f"Created version ID {created_id}")

        self.run_action(action)

    def add_fee_version(self) -> None:
        listing_id = self._selected_listing_id()
        if listing_id is None:
            return
        dialog = FormDialog("Add fee version", self)
        helper = QLabel(
            "These fees are used for estimates when net received is missing. "
            "If actual Amazon net received exists, profit uses net received directly."
        )
        helper.setWordWrap(True)
        dialog.form.addRow(helper)
        effective_from = dialog.add_date("Effective from")
        referral = dialog.add_line("Referral fee", "0")
        fba = dialog.add_line("FBA fee", "0")
        storage = dialog.add_line("Storage fee", "0")
        shipping = dialog.add_line("Amazon shipping/fulfillment", "0")
        other = dialog.add_line("Other marketplace fee", "0")
        total = dialog.add_line("Estimated total fee", "")
        fee_percentage = dialog.add_line("Fee percentage (0.21, 21, or 21%)", "0")
        notes = dialog.add_text("Notes")
        if dialog.exec() != dialog.Accepted:
            return

        def action():
            created_id = None
            with self.session_scope() as session:
                listing = session.get(Listing, listing_id)
                if listing is None:
                    raise ValueError("Selected listing no longer exists.")
                version = CostsService(session).create_marketplace_fee_version(
                    listing_id=listing.id,
                    marketplace_id=listing.marketplace_id,
                    effective_from=from_qdate(effective_from),
                    referral_fee=parse_decimal(referral.text(), "Referral fee"),
                    fba_fee=parse_decimal(fba.text(), "FBA fee"),
                    storage_fee=parse_decimal(storage.text(), "Storage fee"),
                    amazon_shipping_or_fulfillment_fee=parse_decimal(shipping.text(), "Amazon shipping"),
                    other_marketplace_fee=parse_decimal(other.text(), "Other marketplace fee"),
                    estimated_total_fee=parse_decimal(total.text(), "Estimated total fee", required=False),
                    fee_percentage=parse_percentage(fee_percentage.text(), "Fee percentage"),
                    notes=notes.toPlainText().strip() or None,
                )
                created_id = version.id
            self.refresh_histories()
            self.status_label.setText(f"Created version ID {created_id}")

        self.run_action(action)

    def add_price_version(self) -> None:
        listing_id = self._selected_listing_id()
        if listing_id is None:
            return
        dialog = FormDialog("Add price version", self)
        helper = QLabel("Suggested price does not change historical sale prices.")
        helper.setWordWrap(True)
        dialog.form.addRow(helper)
        effective_from = dialog.add_date("Effective from")
        price = dialog.add_line("Suggested selling price", "0")
        buybox = dialog.add_line("BuyBox percentage (0.21, 21, or 21%)", "0")
        notes = dialog.add_text("Notes")
        if dialog.exec() != dialog.Accepted:
            return

        def action():
            created_id = None
            with self.session_scope() as session:
                listing = session.get(Listing, listing_id)
                if listing is None:
                    raise ValueError("Selected listing no longer exists.")
                version = CostsService(session).create_price_version(
                    listing_id=listing.id,
                    marketplace_id=listing.marketplace_id,
                    effective_from=from_qdate(effective_from),
                    suggested_selling_price=parse_decimal(price.text(), "Suggested price"),
                    buybox_percentage=parse_percentage(buybox.text(), "BuyBox percentage"),
                    notes=notes.toPlainText().strip() or None,
                )
                created_id = version.id
            self.refresh_histories()
            self.status_label.setText(f"Created version ID {created_id}")

        self.run_action(action)

    def _selected_listing_id(self) -> int | None:
        listing_id = combo_current_id(self.listing_combo)
        if listing_id is None:
            self.run_action(lambda: (_ for _ in ()).throw(ValueError("Select a listing first.")))
            return None
        return listing_id

    @staticmethod
    def _range_text(effective_from, effective_to) -> str:
        return f"{effective_from} -> {effective_to or 'current'}"
