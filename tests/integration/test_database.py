from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError

from app.domains.orders.infrastructure.persistence.order import OrderRow
from app.domains.orders.infrastructure.persistence.order_line import OrderLineRow
from app.shared.database.connection import build_engine, open_database


def test_database_enforces_foreign_keys_and_cascades(database_url: str) -> None:
    engine = build_engine(database_url)
    order_id = str(uuid4())
    line = {
        "order_id": order_id,
        "position": 0,
        "product_id": "book",
        "quantity": 1,
        "unit_price_won": 1000,
    }
    try:
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(insert(OrderLineRow).values(**line))
        with engine.begin() as connection:
            connection.execute(
                insert(OrderRow).values(id=order_id, status="draft", version=1)
            )
            connection.execute(insert(OrderLineRow).values(**line))
            connection.execute(delete(OrderRow).where(OrderRow.id == order_id))
            assert (
                connection.scalar(select(func.count()).select_from(OrderLineRow)) == 0
            )
    finally:
        engine.dispose()


def test_database_disposes_engine_after_failure(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = build_engine(database_url)
    monkeypatch.setattr(
        "app.shared.database.connection.build_engine", lambda url: engine
    )
    try:
        with patch.object(engine, "dispose", wraps=engine.dispose) as dispose:
            with pytest.raises(RuntimeError, match="application failed"):
                with open_database(database_url) as sessions:
                    with sessions() as session:
                        assert session.get_bind() is engine
                        assert session.expire_on_commit is False
                    raise RuntimeError("application failed")
            dispose.assert_called_once_with()
    finally:
        engine.dispose()
