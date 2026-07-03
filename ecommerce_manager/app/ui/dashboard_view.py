from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTableWidget, QVBoxLayout

from ..services.products_service import ProductsService
from ..services.reports_service import ReportsService
from ..services.restock_service import RestockService
from .helpers import (
    BaseView,
    DateRangeFilter,
    MetricCard,
    SectionHeader,
    configure_table,
    grid_cards,
    money_text,
    rate_text,
    set_table_rows,
    to_qdate,
)


class DashboardView(BaseView):
    def __init__(self, engine):
        super().__init__(engine)
        self.date_range = DateRangeFilter()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        self.note = QLabel(
            "Profit = actual Amazon net received - FIFO internal landed COGS. "
            "Amazon fees are not subtracted again when actual net received is available."
        )
        self.note.setObjectName("MutedLabel")
        self.note.setWordWrap(True)

        self.metric_cards = {
            "gross": MetricCard("Gross revenue"),
            "net": MetricCard("Net received"),
            "cogs": MetricCard("COGS"),
            "profit": MetricCard("Profit"),
            "margin": MetricCard("Margin"),
            "roi": MetricCard("ROI"),
            "listings": MetricCard("Listings sold"),
            "physical": MetricCard("Physical units consumed"),
        }

        self.top_table = QTableWidget()
        configure_table(
            self.top_table,
            ["SKU", "Listing", "Units sold", "Gross", "Net", "COGS", "Profit", "Margin", "ROI"],
        )
        self.low_margin_table = QTableWidget()
        configure_table(
            self.low_margin_table,
            ["SKU", "Listing", "Units sold", "Gross", "Net", "COGS", "Profit", "Margin", "ROI"],
        )
        self.stock_table = QTableWidget()
        configure_table(
            self.stock_table,
            ["SKU", "Listing", "Units/listing", "Physical stock", "Sellable stock"],
        )
        self.restock_table = QTableWidget()
        configure_table(
            self.restock_table,
            ["SKU", "Listing", "Days coverage", "Suggested reorder date", "Status"],
        )
        self.audit_table = QTableWidget()
        configure_table(self.audit_table, ["Audit check", "Count"])

        controls = QHBoxLayout()
        controls.addWidget(self.date_range)
        controls.addWidget(refresh)
        controls.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.note)
        layout.addLayout(grid_cards(list(self.metric_cards.values()), columns=4))
        layout.addWidget(SectionHeader("Top listings by profit"))
        layout.addWidget(self.top_table)
        layout.addWidget(SectionHeader("Low margin / losing listings", "Rows appear when profit is negative or margin is below 5%."))
        layout.addWidget(self.low_margin_table)
        layout.addWidget(SectionHeader("Current stock by listing"))
        layout.addWidget(self.stock_table)
        layout.addWidget(SectionHeader("Restock alerts preview"))
        layout.addWidget(self.restock_table)
        layout.addWidget(SectionHeader("Data audit", "Review these counts before relying on the dashboard."))
        layout.addWidget(self.audit_table)
        self.refresh()

    def refresh(self) -> None:
        def action():
            with self.session_scope() as session:
                reports = ReportsService(session)
                start = self.date_range.start()
                end = self.date_range.end()
                metrics = reports.dashboard_metrics(start_date=start, end_date=end)
                self.metric_cards["gross"].set_value(money_text(metrics.total_gross_revenue))
                self.metric_cards["net"].set_value(money_text(metrics.total_net_received))
                self.metric_cards["cogs"].set_value(money_text(metrics.total_cogs))
                self.metric_cards["profit"].set_value(
                    money_text(metrics.total_profit),
                    negative=metrics.total_profit < 0,
                )
                self.metric_cards["margin"].set_value(rate_text(metrics.margin), negative=(metrics.margin or 0) < 0)
                self.metric_cards["roi"].set_value(rate_text(metrics.roi), negative=(metrics.roi or 0) < 0)
                self.metric_cards["listings"].set_value(metrics.total_listings_sold)
                self.metric_cards["physical"].set_value(metrics.total_physical_units_consumed)

                profit_rows = reports.profit_by_listing(start_date=start, end_date=end)
                set_table_rows(self.top_table, [self._profit_row(row) for row in profit_rows[:10]])
                low_margin = [
                    row
                    for row in profit_rows
                    if row.profit < 0 or (row.margin is not None and row.margin < Decimal("0.05"))
                ]
                set_table_rows(self.low_margin_table, [self._profit_row(row) for row in low_margin])
                set_table_rows(
                    self.stock_table,
                    [
                        [
                            row["sku"],
                            row["listing_name"],
                            row["units_per_listing"],
                            row["physical_stock"],
                            row["equivalent_listing_stock"],
                        ]
                        for row in reports.current_stock_by_listing()
                    ],
                )
                restock = RestockService(session)
                restock_rows = []
                for listing in ProductsService(session).list_listings(active_only=True):
                    rec = restock.recommendation_for_listing(
                        listing.id,
                        as_of_date=self.date_range.end(),
                        velocity_days=max(1, (self.date_range.end() - self.date_range.start()).days + 1),
                    )
                    restock_rows.append(
                        [
                            listing.sku,
                            listing.listing_name,
                            rec.days_of_coverage or "",
                            rec.suggested_reorder_date or "",
                            rec.urgency_status,
                        ]
                    )
                set_table_rows(self.restock_table, restock_rows)
                audit = reports.data_audit()
                set_table_rows(
                    self.audit_table,
                    [
                        ["Products/listings", f"{audit.products} / {audit.listings}"],
                        ["Sales", audit.sales],
                        ["Inventory batches", audit.inventory_batches],
                        ["Products with no cost version", audit.products_without_cost_version],
                        ["Listings with no fee version", audit.listings_without_fee_version],
                        ["Sales with estimated net received", audit.sales_with_estimated_net_received],
                        ["Sales needing review", audit.sales_needing_review],
                        ["Listings with negative profit", audit.listings_with_negative_profit],
                        ["Listings with margin below 5%", audit.listings_with_margin_below_5],
                        ["Listings with zero or low stock", audit.listings_with_zero_or_low_stock],
                        ["Products with stock discrepancy", audit.products_with_stock_discrepancy],
                    ],
                )

        self.run_action(action)

    def _profit_row(self, row) -> list:
        return [
            row.sku_snapshot,
            row.listing_name_snapshot,
            row.listings_sold,
            money_text(row.gross),
            money_text(row.net),
            money_text(row.cogs),
            money_text(row.profit),
            rate_text(row.margin),
            rate_text(row.roi),
        ]
