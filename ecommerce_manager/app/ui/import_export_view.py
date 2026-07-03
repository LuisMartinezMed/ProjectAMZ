from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
)

from ..services.import_export_service import ImportExportService
from ..services.reports_service import ReportsService
from .helpers import BaseView, SectionHeader, configure_table, set_table_rows, write_csv


ACCOUNTING_WARNING = (
    "Costo Total ($) and Costo total por paquete (Luna+AMZ) include Amazon fees. "
    "They are not used as FIFO inventory COGS when actual net received is available."
)


class ImportExportView(BaseView):
    def __init__(self, engine):
        super().__init__(engine)
        self.path = QLineEdit()
        browse = QPushButton("Browse")
        preview = QPushButton("Preview workbook")
        import_button = QPushButton("Run import")
        export_button = QPushButton("Export listing profit CSV")
        self.import_catalog = QCheckBox("Import catalog/products/listings")
        self.import_catalog.setChecked(True)
        self.import_initial_stock = QCheckBox("Import initial stock")
        self.import_initial_stock.setChecked(True)
        self.import_sales = QCheckBox("Import sales")
        self.missing_net_strategy = QComboBox()
        self.missing_net_strategy.addItem("Skip missing net received", "skip")
        self.missing_net_strategy.addItem("Estimate from marketplace fees", "estimate")
        browse.clicked.connect(self.browse)
        preview.clicked.connect(self.preview)
        import_button.clicked.connect(self.import_workbook)
        export_button.clicked.connect(self.export_profit_csv)

        row = QHBoxLayout()
        row.addWidget(QLabel("Workbook"))
        row.addWidget(self.path, 1)
        row.addWidget(browse)

        self.warning = QLabel(ACCOUNTING_WARNING)
        self.warning.setObjectName("MutedLabel")
        self.warning.setWordWrap(True)

        self.detected_table = QTableWidget()
        configure_table(self.detected_table, ["Step", "Detail"])
        self.audit_table = QTableWidget()
        configure_table(self.audit_table, ["Import audit", "Count"])
        self.output = QTextEdit()
        self.output.setReadOnly(True)

        options = QHBoxLayout()
        options.addWidget(self.import_catalog)
        options.addWidget(self.import_initial_stock)
        options.addWidget(self.import_sales)
        options.addWidget(QLabel("Missing net"))
        options.addWidget(self.missing_net_strategy)
        options.addStretch(1)

        buttons = QHBoxLayout()
        for button in (preview, import_button, export_button):
            buttons.addWidget(button)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(SectionHeader("1. Select Excel workbook"))
        layout.addLayout(row)
        layout.addWidget(SectionHeader("2. Preview workbook and warnings"))
        layout.addWidget(self.warning)
        layout.addWidget(self.detected_table)
        layout.addWidget(SectionHeader("3. Choose import options"))
        layout.addLayout(options)
        layout.addLayout(buttons)
        layout.addWidget(SectionHeader("4. Import audit"))
        layout.addWidget(self.audit_table)
        layout.addWidget(SectionHeader("Warnings and details"))
        layout.addWidget(self.output)

    def browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Excel workbook", "", "Excel Workbooks (*.xlsx *.xlsm)")
        if path:
            self.path.setText(path)

    def preview(self) -> None:
        def action():
            if not self.path.text().strip():
                raise ValueError("Select a workbook path first.")
            with self.session_scope() as session:
                preview = ImportExportService(session).preview_workbook(self.path.text().strip())
            rows = [
                ["Workbook", preview.path],
                ["Catalog rows", preview.catalog_rows],
                ["Sales rows", preview.sales_rows],
                ["Analysis rows", preview.analysis_rows],
                ["Simulator rows", preview.simulator_rows],
            ]
            for sheet in preview.sheets:
                table_names = ", ".join(table["name"] for table in sheet["tables"]) or "no tables"
                rows.append([f"Sheet: {sheet['name']}", f"{sheet['dimension']} | {table_names}"])
            set_table_rows(self.detected_table, rows)
            self.output.setPlainText("\n".join(preview.warnings or ["No warnings."]))

        self.run_action(action)

    def import_workbook(self) -> None:
        def action():
            if not self.path.text().strip():
                raise ValueError("Select a workbook path first.")
            with self.session_scope() as session:
                result = ImportExportService(session).import_workbook(
                    self.path.text().strip(),
                    import_catalog=self.import_catalog.isChecked(),
                    import_initial_stock=self.import_initial_stock.isChecked(),
                    import_sales=self.import_sales.isChecked(),
                    missing_net_strategy=self.missing_net_strategy.currentData(),
                )
            set_table_rows(
                self.audit_table,
                [
                    ["Listings created", result.listings_created],
                    ["Cost versions created", result.cost_versions_created],
                    ["Fee versions created", result.fee_versions_created],
                    ["Price versions created", result.price_versions_created],
                    ["Inventory batches created", result.inventory_batches_created],
                    ["Sales imported", result.sales_imported],
                    ["Rows skipped", result.rows_skipped],
                ],
            )
            self.output.setPlainText("\n".join(result.warnings or ["Import completed with no warnings."]))

        self.run_action(action, success="Import complete.")

    def export_profit_csv(self) -> None:
        def action():
            path, _ = QFileDialog.getSaveFileName(self, "Export listing profit", "listing_profit.csv", "CSV (*.csv)")
            if not path:
                return
            with self.session_scope() as session:
                rows = ReportsService(session).profit_by_listing()
            write_csv(
                path,
                ["Listing ID", "SKU", "Listing", "Units sold", "Gross revenue", "Net received", "COGS", "Profit"],
                [
                    [
                        row.listing_id,
                        row.sku_snapshot,
                        row.listing_name_snapshot,
                        row.listings_sold,
                        row.gross,
                        row.net,
                        row.cogs,
                        row.profit,
                    ]
                    for row in rows
                ],
            )
            self.output.setPlainText(f"Exported {len(rows)} rows to {path}")

        self.run_action(action)
