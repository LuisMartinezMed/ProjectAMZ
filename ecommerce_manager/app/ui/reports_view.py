from __future__ import annotations

import openpyxl
from PySide6.QtWidgets import QFileDialog, QComboBox, QHBoxLayout, QPushButton, QTableWidget, QVBoxLayout

from ..services.products_service import ProductsService
from ..services.reports_service import ReportsService
from ..services.restock_service import RestockService
from .helpers import BaseView, DateRangeFilter, configure_table, money_text, rate_text, set_table_rows, write_csv


class ReportsView(BaseView):
    def __init__(self, engine):
        super().__init__(engine)
        self.date_range = DateRangeFilter()
        self.report_selector = QComboBox()
        for label in (
            "Profit by listing",
            "Profit by product",
            "Inventory valuation",
            "Sales velocity",
            "Stockout forecast",
        ):
            self.report_selector.addItem(label, label)
        refresh = QPushButton("Refresh")
        export_csv = QPushButton("Export CSV")
        export_excel = QPushButton("Export Excel")
        refresh.clicked.connect(self.refresh)
        export_csv.clicked.connect(self.export_csv)
        export_excel.clicked.connect(self.export_excel)
        self.report_selector.currentIndexChanged.connect(self.refresh)
        controls = QHBoxLayout()
        controls.addWidget(self.report_selector)
        controls.addWidget(self.date_range)
        controls.addWidget(refresh)
        controls.addWidget(export_csv)
        controls.addWidget(export_excel)
        controls.addStretch(1)
        self.table = QTableWidget()
        self.current_headers: list[str] = []
        self.current_rows: list[list] = []
        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self, *_args) -> None:
        def action():
            report = self.report_selector.currentText()
            with self.session_scope() as session:
                headers, rows = self._build_report(session, report)
            self.current_headers = headers
            self.current_rows = rows
            configure_table(self.table, headers)
            set_table_rows(self.table, rows)

        self.run_action(action)

    def _build_report(self, session, report: str) -> tuple[list[str], list[list]]:
        reports = ReportsService(session)
        start = self.date_range.start()
        end = self.date_range.end()
        if report == "Profit by listing":
            headers = ["SKU", "Listing", "Units sold", "Gross", "Net", "COGS", "Profit", "Margin", "ROI"]
            rows = [
                [
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
                for row in reports.profit_by_listing(start_date=start, end_date=end)
            ]
            return headers, rows
        if report == "Profit by product":
            headers = ["Base product", "Units sold", "Gross", "Net", "COGS", "Profit", "Margin", "ROI"]
            return headers, [
                [
                    row.base_product_name,
                    row.listings_sold,
                    money_text(row.gross),
                    money_text(row.net),
                    money_text(row.cogs),
                    money_text(row.profit),
                    rate_text(row.margin),
                    rate_text(row.roi),
                ]
                for row in reports.profit_by_product(start_date=start, end_date=end)
            ]
        if report == "Inventory valuation":
            headers = ["Product ID", "Remaining units", "Inventory value"]
            return headers, [[row.base_product_id, int(row.units or 0), money_text(row.value)] for row in reports.inventory_valuation()]
        if report == "Sales velocity":
            restock = RestockService(session)
            days = max(1, (end - start).days + 1)
            headers = ["SKU", "Listing", "Avg daily listing sales", "Avg daily physical consumption", "Days coverage", "Status"]
            rows = []
            for listing in ProductsService(session).list_listings(active_only=True):
                rec = restock.recommendation_for_listing(listing.id, as_of_date=end, velocity_days=days)
                rows.append(
                    [
                        listing.sku,
                        listing.listing_name,
                        rec.average_daily_listing_sales,
                        rec.average_daily_physical_consumption,
                        rec.days_of_coverage or "",
                        rec.urgency_status,
                    ]
                )
            return headers, rows
        restock = RestockService(session)
        days = max(1, (end - start).days + 1)
        headers = ["SKU", "Listing", "Stockout date", "Suggested reorder date", "Recommended units", "Status"]
        rows = []
        for listing in ProductsService(session).list_listings(active_only=True):
            rec = restock.recommendation_for_listing(listing.id, as_of_date=end, velocity_days=days)
            rows.append(
                [
                    listing.sku,
                    listing.listing_name,
                    rec.estimated_stockout_date or "",
                    rec.suggested_reorder_date or "",
                    rec.recommended_order_physical_units,
                    rec.urgency_status,
                ]
            )
        return headers, rows

    def export_csv(self) -> None:
        def action():
            path, _ = QFileDialog.getSaveFileName(self, "Export report", "projectamz_report.csv", "CSV (*.csv)")
            if not path:
                return
            write_csv(path, self.current_headers, self.current_rows)

        self.run_action(action, success="Report exported.")

    def export_excel(self) -> None:
        def action():
            path, _ = QFileDialog.getSaveFileName(self, "Export report", "projectamz_report.xlsx", "Excel (*.xlsx)")
            if not path:
                return
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Report"
            ws.append(self.current_headers)
            for row in self.current_rows:
                ws.append(row)
            wb.save(path)

        self.run_action(action, success="Report exported.")
