import pytest
from pydantic import ValidationError

from app.shared.database.connection import Settings, build_engine


@pytest.mark.parametrize(
    ("backend", "driver"), [("postgresql", "psycopg"), ("mysql", "pymysql")]
)
def test_environment_selects_database(
    monkeypatch: pytest.MonkeyPatch, backend: str, driver: str
) -> None:
    url = f"{backend}+{driver}://orders:password@localhost/custom_orders"
    monkeypatch.setenv("DATABASE_URL", url)
    engine = build_engine(Settings(_env_file=None).database_url)
    try:
        assert engine.dialect.name == backend
        assert engine.dialect.driver == driver
        assert engine.url.database == "custom_orders"
    finally:
        engine.dispose()


def test_postgresql_is_the_default_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    engine = build_engine(Settings(_env_file=None).database_url)
    try:
        assert engine.dialect.name == "postgresql"
        assert engine.dialect.driver == "psycopg"
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///orders.db",
        "mysql://localhost/orders",
        "postgresql://localhost/orders",
    ],
)
def test_settings_reject_other_databases(url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url=url)
