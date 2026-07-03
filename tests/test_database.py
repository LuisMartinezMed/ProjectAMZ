from __future__ import annotations

from pathlib import Path

from ecommerce_manager.app.database import DEFAULT_DB_PATH, create_app_engine


def test_default_database_path_is_absolute_and_project_scoped(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    engine = create_app_engine()
    try:
        assert DEFAULT_DB_PATH.is_absolute()
        assert Path(engine.url.database) == DEFAULT_DB_PATH
    finally:
        engine.dispose()

