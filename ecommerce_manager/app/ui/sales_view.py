from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
)

from ..models import Listing
from ..services.products_service import ProductsService
from ..services.reports_service import ReportsService
from ..services.sales_service import SaleLineInput, SalesService
from .helpers import (
    BaseView,
    configure_table,
    from_qdate,
    money_text,
    parse_decimal,
    parse_int,
    rate_text,
    section_label,
    set_table_rows,
    to_qdate,
)


class SalesView(BaseView):
    def __init__(self, engine):
        super().__init__(engine)
        self.sale_date = QDateEdit(to_qdate())
        self.sale_date.setCalendarPopup(True)
        self.sale_date.setDisplayFormat("yyyy-MM-dd")
        self.listing_combo = QComboBox()
        self.listing_combo.currentIndexChanged.connect(self.apply_listing_selection)
        self.sku = QLineEdit()
        self.asin = QLineEdit()
        self.quantity = QLineEdit("1")
        self.gross = QLineEdit("0")
        self.net = QLineEdit("")
        self.order_id = QLineEdit()
        self.settlement_id = QLineEdit()
        self.notes = QTextEdit()
        self.notes.setFixedHeight(64)
        self.preview_button = QPushButton("Preview")
        self.save_button = QPushButton("Save sale")
        self.clear_button = QPushButton("Clear form")
        self.preview_button.clicked.connect(self.preview_sale)
        self.save_button.clicked.connect(self.save_sale)
        self.clear_button.clicked.connect(self.clear_form)
        for widget in (self.quantity, self.gross, self.net, self.sku, self.asin):
            widget.editingFinished.connect(self.preview_sale_silent)
        self.sale_date.dateChanged.connect(self.preview_sale_silent)
        form_box = QGroupBox("Manual sale")
        form = QFormLayout(form_box)
        for label, widget in [
            ("Find listing", self.listing_combo),
            ("Sale date", self.sale_date),
            ("SKU", self.sku),
            ("ASIN", self.asin),
            ("Quantity sold", self.quantity),
            ("Gross revenue", self.gross),
            ("Net received from Amazon", self.net),
            ("Order ID", self.order_id),
            ("Settlement ID", self.settlement_id),
            ("Notes", self.notes),
        ]:
            form.addRow(label, widget)
        buttons = QHBoxLayout()
        buttons.addWidget(self.preview_button)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.clear_button)
        buttons.addStretch(1)
        form.addRow(buttons)

        self.help_label = QLabel(
            "Quantity sold = Amazon listings/packages sold. Physical units consumed = quantity sold x units per listing. "
            "If net received is entered, Amazon fees are not subtracted again."
        )
        self.help_label.setObjectName("MutedLabel")
        self.help_label.setWordWrap(True)
        self.preview_label = QLabel("Preview needs a listing, quantity, gross revenue, and available FIFO stock.")
        self.preview_label.setObjectName("MutedLabel")
        self.preview_label.setWordWrap(True)
        self.preview_table = QTableWidget()
        configure_table(self.preview_table, ["Field", "Value"])
        self.recent_table = QTableWidget()
        configure_table(
            self.recent_table,
            ["ID", "Date", "SKU", "Listing", "Qty", "Physical", "Gross", "Net", "COGS", "Profit", "Margin", "Source"],
        )
        refresh = QPushButton("Refresh recent sales")
        refresh.clicked.connect(self.refresh_recent_sales)

        layout = QVBoxLayout(self)
        layout.addWidget(form_box)
        layout.addWidget(self.help_label)
        layout.addWidget(section_label("Sale preview"))
        layout.addWidget(self.preview_label)
        layout.addWidget(self.preview_table)
        layout.addWidget(section_label("Recent sales"))
        layout.addWidget(refresh)
        layout.addWidget(self.recent_table)
        self.refresh_listings()
        self.refresh_recent_sales()

    def _sale_input(self) -> SaleLineInput:
        return SaleLineInput(
            sale_date=from_qdate(self.sale_date),
            sku=self.sku.text().strip() or None,
            asin=self.asin.text().strip() or None,
            quantity_listings_sold=parse_int(self.quantity.text(), "Quantity sold"),
            gross_revenue=parse_decimal(self.gross.text(), "Gross revenue"),
            net_received=parse_decimal(self.net.text(), "Net received", required=False),
            order_id=self.order_id.text().strip() or None,
            settlement_id=self.settlement_id.text().strip() or None,
            source="manual",
            notes=self.notes.toPlainText().strip() or None,
        )

    def preview_sale(self) -> None:
        def action():
            with self.session_scope() as session:
                preview = SalesService(session).preview_sale_line(self._sale_input())
            self._set_preview(preview)

        self.run_action(action)

    def preview_sale_silent(self, *_args) -> None:
        try:
            with self.session_scope() as session:
                preview = SalesService(session).preview_sale_line(self._sale_input())
            self._set_preview(preview)
        except Exception:
            self.preview_label.setText("Preview needs valid sale inputs and available FIFO stock.")

    def save_sale(self) -> None:
        def action():
            with self.session_scope() as session:
                SalesService(session).add_sale_line(self._sale_input())
            self.preview_label.setText("Sale saved.")
            self.refresh_recent_sales()
            self.refresh_listings()

        self.run_action(action, success="Sale saved.")

    def refresh_recent_sales(self) -> None:
        def action():
            with self.session_scope() as session:
                rows = []
                for row in ReportsService(session).recent_sales():
                    rows.append(
                        [
                            row.id,
                            row.sale_date,
                            row.sku_snapshot,
                            row.listing_name_snapshot,
                            row.quantity_listings_sold,
                            row.physical_units_consumed_snapshot,
                            money_text(row.gross_revenue),
                            money_text(row.net_received),
                            money_text(row.total_cogs_snapshot),
                            money_text(row.profit_snapshot),
                            rate_text(row.margin_snapshot),
                            row.source,
                        ]
                    )
                set_table_rows(self.recent_table, rows)

        self.run_action(action)

    def refresh_listings(self) -> None:
        current_sku = self.sku.text().strip()
        self.listing_combo.blockSignals(True)
        self.listing_combo.clear()
        self.listing_combo.addItem("Select listing", None)
        with self.session_scope() as session:
            for listing in ProductsService(session).list_listings(active_only=True):
                self.listing_combo.addItem(f"{listing.sku} - {listing.listing_name}", listing.id)
                if current_sku and listing.sku == current_sku:
                    self.listing_combo.setCurrentIndex(self.listing_combo.count() - 1)
        self.listing_combo.blockSignals(False)

    def apply_listing_selection(self, *_args) -> None:
        listing_id = self.listing_combo.currentData()
        if listing_id is None:
            return
        with self.session_scope() as session:
            listing = session.get(Listing, int(listing_id))
            if listing is None:
                return
            self.sku.setText(listing.sku)
            self.asin.setText(listing.asin or "")
        self.preview_sale_silent()

    def clear_form(self) -> None:
        self.listing_combo.setCurrentIndex(0)
        for widget in (self.sku, self.asin, self.quantity, self.gross, self.net, self.order_id, self.settlement_id):
            widget.clear()
        self.quantity.setText("1")
        self.gross.setText("0")
        self.notes.clear()
        set_table_rows(self.preview_table, [])
        self.preview_label.setText("Preview needs a listing, quantity, gross revenue, and available FIFO stock.")

    def _set_preview(self, preview) -> None:
        source = "estimated" if preview.net_received_estimated else "actual"
        self.preview_label.setText(f"{preview.sku} - {preview.listing_name}")
        set_table_rows(
            self.preview_table,
            [
                ["Listing selected", preview.listing_name],
                ["Units per listing", preview.units_per_listing],
                ["Physical units consumed", preview.physical_units_consumed],
                ["FIFO COGS", money_text(preview.total_cogs)],
                ["Net received", f"{money_text(preview.net_received)} ({source})"],
                ["Profit", money_text(preview.profit)],
                ["Margin", rate_text(preview.margin)],
                ["ROI", rate_text(preview.roi)],
                ["FIFO allocation", preview.allocation_summary],
            ],
        )
