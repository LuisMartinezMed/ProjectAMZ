from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .bulk_sales_entry_view import BulkSalesEntryView
from .costs_fees_view import CostsFeesView
from .dashboard_view import DashboardView
from .import_export_view import ImportExportView
from .inventory_view import InventoryView
from .products_view import ProductsView
from .purchases_view import PurchasesView
from .reports_view import ReportsView
from .restock_view import RestockView
from .sales_view import SalesView
from .settings_view import SettingsView
from .style import APP_STYLESHEET


class PageShell(QWidget):
    def __init__(self, title: str, description: str, content: QWidget):
        super().__init__()
        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        description_label = QLabel(description)
        description_label.setObjectName("PageDescription")
        description_label.setWordWrap(True)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title_block.addWidget(title_label)
        title_block.addWidget(description_label)
        header.addLayout(title_block, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        layout.addLayout(header)
        layout.addWidget(content, 1)


class MainWindow(QMainWindow):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.setWindowTitle("ProjectAMZ - Amazon Operations Manager")
        self.setStyleSheet(APP_STYLESHEET)
        self.stack = QStackedWidget()
        self.nav_buttons: list[QPushButton] = []

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(210)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 14, 12, 14)
        sidebar_layout.setSpacing(6)
        app_title = QLabel("ProjectAMZ")
        app_title.setObjectName("AppTitle")
        sidebar_layout.addWidget(app_title)
        sidebar_layout.addSpacing(8)

        pages = [
            (
                "Dashboard",
                "Business overview, profit quality, stock, restock alerts, and data audit.",
                DashboardView(engine),
            ),
            (
                "Products & Listings",
                "Manage base products, Amazon listings, package units, status, links, and notes.",
                ProductsView(engine),
            ),
            (
                "Costs & Fees",
                "Versioned internal landed costs, marketplace fee estimates, and suggested prices.",
                CostsFeesView(engine),
            ),
            (
                "Sales",
                "Preview FIFO profit before saving manual Amazon sales.",
                SalesView(engine),
            ),
            (
                "Bulk Sales",
                "Validate and save multiple sales rows as one all-or-nothing operation.",
                BulkSalesEntryView(engine),
            ),
            (
                "Purchases",
                "Create supplier purchase orders, add lines, and receive inventory into FIFO.",
                PurchasesView(engine),
            ),
            (
                "Inventory",
                "Review current stock, sellable package stock, FIFO batches, and movements.",
                InventoryView(engine),
            ),
            (
                "Restock",
                "Plan replenishment using sales velocity, safety stock, lead time, and current stock.",
                RestockView(engine),
            ),
            (
                "Reports",
                "Run operational reports and export business data.",
                ReportsView(engine),
            ),
            (
                "Import / Export",
                "Preview Excel workbooks, audit warnings, import data, and export CSV reports.",
                ImportExportView(engine),
            ),
            (
                "Settings",
                "Adjust planning defaults, inventory behavior, currency, and timezone.",
                SettingsView(engine),
            ),
        ]

        for idx, (title, description, view) in enumerate(pages):
            self.stack.addWidget(PageShell(title, description, view))
            button = QPushButton(title)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, page_idx=idx: self.set_page(page_idx))
            sidebar_layout.addWidget(button)
            self.nav_buttons.append(button)
        sidebar_layout.addStretch(1)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(sidebar)
        root_layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.set_page(0)

    def set_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for idx, button in enumerate(self.nav_buttons):
            button.setChecked(idx == index)
