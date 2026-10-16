from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, insert, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

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


async def test_database_disposes_engine_after_failure(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = make_url(database_url)
    if url.drivername == "mysql+pymysql":
        url = url.set(drivername="mysql+aiomysql")
    engine = create_async_engine(url)
    monkeypatch.setattr(
        "app.shared.database.connection.create_async_engine",
        lambda *args, **kwargs: engine,
    )
    try:
        with patch.object(
            type(engine), "dispose", autospec=True, wraps=engine.dispose
        ) as dispose:
            with pytest.raises(RuntimeError, match="application failed"):
                async with open_database(database_url) as sessions:
                    async with sessions() as session:
                        assert session.bind is engine
                        assert session.sync_session.expire_on_commit is False
                    raise RuntimeError("application failed")
            dispose.assert_awaited_once()
    finally:
        await engine.dispose()
