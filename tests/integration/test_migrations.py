from io import StringIO

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.shared.database.connection import build_engine


def test_migration_has_one_revision() -> None:
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    assert [revision.revision for revision in script.walk_revisions()] == ["0001"]


def test_migration_matches_models_and_is_reversible(database_url: str) -> None:
    config = Config("alembic.ini")
    config.attributes["database_url"] = database_url
    command.check(config)
    engine = build_engine(database_url)
    try:
        assert set(inspect(engine).get_table_names()) == {
            "alembic_version",
            "orders",
            "order_lines",
        }
    finally:
        engine.dispose()
    command.downgrade(config, "base")
    engine = build_engine(database_url)
    try:
        assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    finally:
        engine.dispose()
    command.upgrade(config, "head")
    command.check(config)


@pytest.mark.parametrize("driver", ["postgresql+psycopg", "mysql+pymysql"])
def test_migrations_compile_for_supported_databases(driver: str) -> None:
    output = StringIO()
    config = Config("alembic.ini", output_buffer=output)
    config.attributes["database_url"] = f"{driver}://orders:password@localhost/orders"

    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE orders" in sql
    assert "CREATE TABLE order_lines" in sql
    assert "outbox_events" not in sql

    output.seek(0)
    output.truncate()
    command.downgrade(config, "head:base", sql=True)
    assert "DROP TABLE order_lines" in output.getvalue()
    assert "DROP TABLE orders" in output.getvalue()
