from __future__ import annotations

import logging
import os
import sys
from pathlib import Path


if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))
    __package__ = "ecommerce_manager.app"

from sqlalchemy.orm import Session

from .database import create_app_engine, init_db
from .services.reports_service import ReportsService


def run() -> int:
    logging.basicConfig(
        level=getattr(logging, os.getenv("PROJECTAMZ_LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="[ProjectAMZ] %(levelname)s %(name)s: %(message)s",
    )
    engine = init_db(create_app_engine())
    try:
        from PySide6.QtWidgets import QApplication

        from .ui.main_window import MainWindow
    except ImportError:
        with Session(engine) as session:
            metrics = ReportsService(session).dashboard_metrics()
        print("ProjectAMZ local database is ready.")
        print("PySide6 is not installed, so the desktop UI was not started.")
        print(f"Gross revenue: {metrics.total_gross_revenue}")
        print("Install requirements and run again to launch the UI.")
        return 0

    app = QApplication(sys.argv)
    window = MainWindow(engine)
    window.resize(1180, 760)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
