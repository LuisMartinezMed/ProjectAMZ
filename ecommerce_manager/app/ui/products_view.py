from __future__ import annotations

import logging

from sqlalchemy import select

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QTableWidget, QVBoxLayout

from ..models import Listing, Supplier
from ..services.products_service import ProductsService, infer_units_per_listing
from ..services.reports_service import ReportsService
from .helpers import (
    BaseView,
    FormDialog,
    SearchBar,
    button_row,
    configure_table,
    parse_int,
    selected_row_id,
    section_label,
    set_table_rows,
    show_error,
    show_info,
)


logger = logging.getLogger(__name__)


class ListingDialog(FormDialog):
    def __init__(self, title: str, parent=None, listing: Listing | None = None):
        super().__init__(title, parent)
        base_product = listing.base_product if listing else None
        self.form.addRow(section_label("Base product"))
        self.product_name = self.add_line("Base product name", base_product.name if base_product else "")
        self.brand = self.add_line("Brand", base_product.brand if base_product else "")
        self.category = self.add_line("Category", base_product.category if base_product else "")
        self.supplier = self.add_line("Supplier name (optional)", base_product.supplier.name if base_product and base_product.supplier else "")
        self.form.addRow(section_label("Amazon listing"))
        self.sku = self.add_line("SKU", listing.sku if listing else "")
        self.asin = self.add_line("ASIN", listing.asin if listing and listing.asin else "")
        self.listing_name = self.add_line("Listing name", listing.listing_name if listing else "")
        helper = QLabel(
            "Units per listing means how many physical units are consumed when one Amazon listing/package is sold.\n"
            "Examples: Febreze pack of 8 = 8; Mitchum pack of 4 = 4; UNO Junior individual = 1."
        )
        helper.setWordWrap(True)
        self.form.addRow(helper)
        inferred_units = infer_units_per_listing(listing.listing_name if listing else "")
        self.units_per_listing = self.add_line(
            "Units per listing",
            str(listing.units_per_listing if listing else inferred_units),
        )
        self.form.addRow(section_label("Links / notes"))
        self.amazon_url = self.add_line("Amazon URL", listing.amazon_product_url if listing and listing.amazon_product_url else "")
        self.supplier_url = self.add_line(
            "Supplier URL",
            base_product.supplier_product_url if base_product and base_product.supplier_product_url else "",
        )
        self.notes = self.add_text("Notes", listing.notes if listing and listing.notes else "")

    def values(self) -> dict:
        return {
            "base_product_name": self.product_name.text().strip(),
            "brand": self.brand.text().strip() or None,
            "category": self.category.text().strip() or None,
            "supplier_name": self.supplier.text().strip() or None,
            "sku": self.sku.text().strip(),
            "asin": self.asin.text().strip() or None,
            "listing_name": self.listing_name.text().strip(),
            "units_per_listing": parse_int(self.units_per_listing.text(), "Units per listing"),
            "amazon_product_url": self.amazon_url.text().strip() or None,
            "supplier_product_url": self.supplier_url.text().strip() or None,
            "notes": self.notes.toPlainText().strip() or None,
        }


class ProductsView(BaseView):
    def __init__(self, engine):
        super().__init__(engine)
        self.search = SearchBar("Search SKU, ASIN, listing, or base product")
        self.search.text_changed.connect(self.refresh)
        self.status_filter = QComboBox()
        self.status_filter.addItem("Active", "active")
        self.status_filter.addItem("Inactive", "inactive")
        self.status_filter.addItem("All", "all")
        self.status_filter.currentIndexChanged.connect(self.refresh)
        self.status_label = QLabel("")
        self.status_label.setObjectName("MutedLabel")
        self.table = QTableWidget()
        configure_table(
            self.table,
            [
                "ID",
                "SKU",
                "ASIN",
                "Listing name",
                "Base product",
                "Units/listing",
                "Physical stock",
                "Sellable stock",
                "Status",
            ],
        )
        self.table.hideColumn(0)
        refresh = QPushButton("Refresh")
        add = QPushButton("Add product/listing")
        edit = QPushButton("Edit selected")
        deactivate = QPushButton("Deactivate selected")
        refresh.clicked.connect(self.refresh)
        add.clicked.connect(self.add_listing)
        edit.clicked.connect(self.edit_listing)
        deactivate.clicked.connect(self.deactivate_listing)

        filters = QHBoxLayout()
        filters.addWidget(self.search, 1)
        filters.addWidget(QLabel("Status"))
        filters.addWidget(self.status_filter)

        layout = QVBoxLayout(self)
        layout.addLayout(button_row(refresh, add, edit, deactivate))
        layout.addLayout(filters)
        layout.addWidget(self.status_label)
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self, selected_listing_id: int | None = None) -> None:
        if type(selected_listing_id) is not int:
            selected_listing_id = None

        def action():
            selected_id = selected_listing_id if selected_listing_id is not None else selected_row_id(self.table)
            query = self.search.text().lower()
            status_filter = self.status_filter.currentData()
            with self.session_scope() as session:
                stock_by_listing = {
                    row["listing_id"]: row for row in ReportsService(session).current_stock_by_listing()
                }
                rows = []
                for listing in ProductsService(session).list_listings():
                    if status_filter != "all" and listing.status != status_filter:
                        continue
                    searchable = " ".join(
                        [
                            listing.sku,
                            listing.asin or "",
                            listing.listing_name,
                            listing.base_product.name,
                        ]
                    ).lower()
                    if query and query not in searchable:
                        continue
                    stock = stock_by_listing.get(listing.id, {})
                    rows.append(
                        [
                            listing.id,
                            listing.sku,
                            listing.asin or "",
                            listing.listing_name,
                            listing.base_product.name,
                            listing.units_per_listing,
                            stock.get("physical_stock", 0),
                            stock.get("equivalent_listing_stock", 0),
                            listing.status,
                        ]
                    )
                logger.debug("ProductsView refresh loaded %s listings from %s", len(rows), self.engine.url)
                set_table_rows(self.table, rows)
                if selected_id is not None:
                    self._select_listing_row(selected_id)

        self.run_action(action)

    def add_listing(self) -> None:
        dialog = ListingDialog("Add product/listing", self)

        def save() -> None:
            try:
                values = dialog.values()
                with self.session_scope() as session:
                    products = ProductsService(session)
                    marketplace = products.get_marketplace("Amazon")
                    supplier_id = self._get_or_create_supplier_id(session, values["supplier_name"])
                    product = products.create_base_product(
                        name=values["base_product_name"],
                        brand=values["brand"],
                        category=values["category"],
                        supplier_id=supplier_id,
                        supplier_product_url=values["supplier_product_url"],
                    )
                    listing = products.create_listing(
                        marketplace_id=marketplace.id,
                        base_product_id=product.id,
                        sku=values["sku"],
                        asin=values["asin"],
                        listing_name=values["listing_name"],
                        units_per_listing=values["units_per_listing"],
                        amazon_product_url=values["amazon_product_url"],
                        notes=values["notes"],
                    )
                    listing_id = listing.id
                    logger.info(
                        "ProductsView committed product/listing product_id=%s listing_id=%s sku=%r",
                        product.id,
                        listing.id,
                        listing.sku,
                    )
                dialog.accept()
                self.refresh(listing_id)
                self.status_label.setText(f"Created listing ID {listing_id}")
                show_info(self, "Done", "Product/listing created.")
            except Exception as exc:
                show_error(dialog, "Save failed", exc)

        self._replace_dialog_accept(dialog, save)
        dialog.exec()

    def edit_listing(self) -> None:
        listing_id = selected_row_id(self.table)
        if listing_id is None:
            self.run_action(lambda: (_ for _ in ()).throw(ValueError("Select a listing first.")))
            return
        with self.session_scope() as session:
            listing = session.get(Listing, listing_id)
            if listing is None:
                self.run_action(lambda: (_ for _ in ()).throw(ValueError("Listing not found.")))
                return
            # Copy loaded object data while the session is open for the dialog.
            dialog = ListingDialog("Edit listing", self, listing)
        def save() -> None:
            try:
                values = dialog.values()
                with self.session_scope() as session:
                    products = ProductsService(session)
                    listing = products.update_listing(
                        listing_id,
                        base_product_name=values["base_product_name"],
                        brand=values["brand"],
                        category=values["category"],
                        supplier_product_url=values["supplier_product_url"],
                        sku=values["sku"],
                        asin=values["asin"],
                        listing_name=values["listing_name"],
                        units_per_listing=values["units_per_listing"],
                        amazon_product_url=values["amazon_product_url"],
                        notes=values["notes"],
                    )
                    listing.base_product.supplier_id = self._get_or_create_supplier_id(session, values["supplier_name"])
                    logger.info(
                        "ProductsView committed listing update listing_id=%s sku=%r",
                        listing.id,
                        listing.sku,
                    )
                dialog.accept()
                self.refresh(listing_id)
                self.status_label.setText(f"Updated listing ID {listing_id}")
                show_info(self, "Done", "Listing updated.")
            except Exception as exc:
                show_error(dialog, "Save failed", exc)

        self._replace_dialog_accept(dialog, save)
        dialog.exec()

    def deactivate_listing(self) -> None:
        listing_id = selected_row_id(self.table)
        if listing_id is None:
            self.run_action(lambda: (_ for _ in ()).throw(ValueError("Select a listing first.")))
            return

        def action():
            with self.session_scope() as session:
                ProductsService(session).deactivate_listing(listing_id)
            self.refresh()

        self.run_action(action, success="Listing deactivated.")

    def _select_listing_row(self, listing_id: int) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.text() == str(listing_id):
                self.table.selectRow(row)
                return

    def _get_or_create_supplier_id(self, session, supplier_name: str | None) -> int | None:
        if not supplier_name:
            return None
        supplier = session.scalar(select(Supplier).where(Supplier.name == supplier_name))
        if supplier is None:
            supplier = ProductsService(session).create_supplier(name=supplier_name)
        return supplier.id

    def _replace_dialog_accept(self, dialog: ListingDialog, callback) -> None:
        try:
            dialog.buttons.accepted.disconnect()
        except (TypeError, RuntimeError):
            pass
        dialog.buttons.accepted.connect(callback)
