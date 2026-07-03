# ProjectAMZ

Local/offline-first Amazon sales, inventory, profit, and restock manager.

The MVP replaces the spreadsheet's live references with SQLite records:

- immutable sale-line snapshots for price, fees, costs, COGS, profit, margin, and ROI;
- FIFO inventory batches and sale allocations;
- versioned product costs, listing costs, marketplace fees, and suggested prices;
- dashboard/restock metrics calculated from persisted sale snapshots and inventory ledger records.

## Quick Start

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

If `PySide6` is not installed, `python run.py` still initializes the SQLite database and prints a CLI summary.

## Excel Import

Use `ImportExportService.preview_workbook(path)` before importing. The importer reads:

- `Catálogo y Costos` / `Costos_Catalogo` for listings, initial cost versions, suggested prices, and initial stock;
- `Análisis de productos` / `TB_Analisis` for fee estimates when ASIN matches a listing;
- `Registro de Ventas` / `Ventas` for sale rows only when sales import is explicitly enabled.

Missing `Ingreso Neto` rows are skipped by default because historical profit should not be guessed silently.

## Database

Default database path: `data/ecommerce_manager.sqlite3`

Override with:

```powershell
$env:PROJECTAMZ_DB_URL = "sqlite:///C:/path/to/projectamz.sqlite3"
```

