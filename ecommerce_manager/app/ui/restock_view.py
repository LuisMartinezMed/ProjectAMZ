from __future__ import annotations

from PySide6.QtWidgets import QDateEdit, QFormLayout, QGroupBox, QLabel, QLineEdit, QPushButton, QTableWidget, QVBoxLayout

from ..services.products_service import ProductsService
from ..services.restock_service import RestockService
from .helpers import BaseView, DateRangeFilter, configure_table, from_qdate, parse_int, set_table_rows, to_qdate


class RestockView(BaseView):
    def __init__(self, engine):
        super().__init__(engine)
        self.as_of = QDateEdit(to_qdate())
        self.as_of.setCalendarPopup(True)
        self.as_of.setDisplayFormat("yyyy-MM-dd")
        self.velocity_range = DateRangeFilter()
        self.velocity_days = QLineEdit("30")
        self.safety_days = QLineEdit("14")
        self.target_days = QLineEdit("45")
        refresh = QPushButton("Refresh recommendations")
        refresh.clicked.connect(self.refresh)
        controls = QGroupBox("Analysis settings")
        form = QFormLayout(controls)
        form.addRow("Velocity date range", self.velocity_range)
        form.addRow("As-of date", self.as_of)
        form.addRow("Analysis days override", self.velocity_days)
        form.addRow("Safety stock days", self.safety_days)
        form.addRow("Target stock days", self.target_days)
        form.addRow(refresh)
        note = QLabel("Status values: urgent, soon, healthy, overstock.")
        note.setObjectName("MutedLabel")
        note.setWordWrap(True)

        self.table = QTableWidget()
        configure_table(
            self.table,
            [
                "SKU",
                "Listing",
                "Units/listing",
                "Physical stock",
                "Sellable stock",
                "Avg daily sales",
                "Avg daily physical",
                "Days coverage",
                "Stockout date",
                "Reorder date",
                "Recommended units",
                "Recommended supplier lots",
                "Status",
            ],
        )
        layout = QVBoxLayout(self)
        layout.addWidget(controls)
        layout.addWidget(note)
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self, *_args) -> None:
        def action():
            with self.session_scope() as session:
                restock = RestockService(session)
                rows = []
                range_days = max(1, (self.velocity_range.end() - self.velocity_range.start()).days + 1)
                velocity_days = parse_int(self.velocity_days.text(), "Analysis days", required=False) or range_days
                for listing in ProductsService(session).list_listings(active_only=True):
                    rec = restock.recommendation_for_listing(
                        listing.id,
                        as_of_date=from_qdate(self.as_of),
                        velocity_days=velocity_days,
                        safety_stock_days=parse_int(self.safety_days.text(), "Safety stock days"),
                        target_stock_days=parse_int(self.target_days.text(), "Target stock days"),
                    )
                    rows.append(
                        [
                            listing.sku,
                            listing.listing_name,
                            listing.units_per_listing,
                            rec.current_physical_stock,
                            rec.equivalent_listing_stock,
                            rec.average_daily_listing_sales,
                            rec.average_daily_physical_consumption,
                            rec.days_of_coverage or "",
                            rec.estimated_stockout_date or "",
                            rec.suggested_reorder_date or "",
                            rec.recommended_order_physical_units,
                            rec.recommended_order_supplier_lots,
                            rec.urgency_status,
                        ]
                    )
                set_table_rows(self.table, rows)

        self.run_action(action)
