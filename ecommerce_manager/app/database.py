from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import AppSetting, Base, Marketplace


logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "ecommerce_manager.sqlite3"
DEFAULT_DB_URL = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"


def get_database_url() -> str:
    return os.getenv("PROJECTAMZ_DB_URL", DEFAULT_DB_URL)


def _normalize_sqlite_url(url: str) -> tuple[str, Optional[Path]]:
    if not url.startswith("sqlite:///") or url == "sqlite:///:memory:":
        return url, None
    raw_path = url.replace("sqlite:///", "", 1)
    db_file = Path(raw_path)
    if not db_file.is_absolute():
        db_file = PROJECT_ROOT / db_file
    return f"sqlite:///{db_file.as_posix()}", db_file


def create_app_engine(database_url: Optional[str] = None, echo: bool = False) -> Engine:
    url, db_file = _normalize_sqlite_url(database_url or get_database_url())
    if db_file is not None:
        db_file.parent.mkdir(parents=True, exist_ok=True)
        logger.info("SQLite database path: %s", db_file)
    logger.info("Database URL: %s", url)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, echo=echo, future=True, connect_args=connect_args)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_db(engine: Optional[Engine] = None) -> Engine:
    engine = engine or create_app_engine()
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_defaults(session)
        session.commit()
    return engine


def seed_defaults(session: Session) -> None:
    amazon = session.scalar(select(Marketplace).where(Marketplace.name == "Amazon"))
    if amazon is None:
        session.add(Marketplace(name="Amazon", status="active"))

    defaults = {
        "default_sales_velocity_days": "30",
        "default_supplier_lead_time_days": "7",
        "default_shipping_days": "7",
        "default_safety_stock_days": "14",
        "default_target_stock_days": "45",
        "default_reorder_review_days": "7",
        "allow_negative_inventory": "false",
        "currency": "USD",
        "timezone": "America/Mexico_City",
    }
    existing = {
        setting.key
        for setting in session.scalars(select(AppSetting).where(AppSetting.key.in_(defaults))).all()
    }
    for key, value in defaults.items():
        if key not in existing:
            session.add(AppSetting(key=key, value=value))
