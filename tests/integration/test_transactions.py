from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy_transactional.asyncio import current_session, transactional
from sqlalchemy_transactional.common import Propagation, SessionNotBoundError

from app.domains.orders.application.add_product_to_order import (
    AddProductToOrderCommand,
    add_product_to_order,
)
from app.domains.orders.application.confirm_order import (
    ConfirmOrderCommand,
    confirm_order,
)
from app.domains.orders.application.get_order_by_id import (
    GetOrderByIdQuery,
    get_order_by_id,
)
from app.domains.orders.domain.order import Order
from app.domains.orders.domain.order_line import OrderLine
from app.domains.orders.infrastructure.order_repository import SqlAlchemyOrderRepository
from app.domains.orders.infrastructure.persistence.order_line import OrderLineRow


@transactional
async def seed_order() -> UUID:
    order = Order(uuid4())
    order.add_line(OrderLine(product_id="book", quantity=2, unit_price_won=12000))
    await SqlAlchemyOrderRepository().add(order)
    return order.id


async def load_order(order_id: UUID) -> Order:
    return await get_order_by_id(
        GetOrderByIdQuery(order_id=order_id), SqlAlchemyOrderRepository()
    )


@pytest.mark.parametrize("failure", ["before_commit", "during_commit"])
async def test_order_and_lines_rollback_together(
    sessions: async_sessionmaker[AsyncSession], failure: str
) -> None:
    order_id = await seed_order()

    @transactional
    async def change() -> None:
        orders = SqlAlchemyOrderRepository()
        order = await orders.get(order_id)
        assert order is not None
        order.add_line(OrderLine(product_id="pen", quantity=1, unit_price_won=1000))
        await orders.save(order)
        if failure == "before_commit":
            await current_session().flush()
            raise RuntimeError("operation failed after flushing both tables")
        current_session().add(
            OrderLineRow(
                order_id=str(order_id),
                position=2,
                product_id="invalid",
                quantity=0,
                unit_price_won=1000,
            )
        )

    mysql_check_failure = (
        failure == "during_commit" and sessions.kw["bind"].dialect.name == "mysql"
    )
    expected = RuntimeError if failure == "before_commit" else IntegrityError
    if mysql_check_failure:
        expected = OperationalError
    with pytest.raises(expected) as raised:
        await change()
    if mysql_check_failure:
        assert raised.value.orig.args[0] == 3819
    with pytest.raises(SessionNotBoundError):
        current_session()
    order = await load_order(order_id)
    assert order.status == Order.Status.DRAFT
    assert order.version == 1
    assert order.total_won == 24000
    assert len(order.lines) == 1


async def test_confirmation_commits_order(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    order_id = await seed_order()
    await confirm_order(
        ConfirmOrderCommand(order_id=order_id), SqlAlchemyOrderRepository()
    )
    order = await load_order(order_id)
    assert order.status == Order.Status.CONFIRMED
    assert order.total_won == 24000


async def test_product_addition_commits_order_and_lines(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    order_id = await seed_order()
    await add_product_to_order(
        AddProductToOrderCommand(
            order_id=order_id,
            line=OrderLine(product_id="pen", quantity=1, unit_price_won=1000),
        ),
        SqlAlchemyOrderRepository(),
    )
    order = await load_order(order_id)
    assert order.version == 2
    assert order.total_won == 25000
    assert len(order.lines) == 2


async def test_list_returns_aggregates_that_can_be_saved(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    order_id = await seed_order()

    @transactional
    async def change() -> None:
        orders = SqlAlchemyOrderRepository()
        order = (await orders.list(Order.Status.DRAFT, limit=20, offset=0))[0]
        assert order.id == order_id
        assert order.version == 1
        order.confirm()
        await orders.save(order)
        reloaded = await orders.get(order_id)
        assert reloaded is not None
        assert reloaded.status == Order.Status.CONFIRMED
        assert reloaded.version == 2
        assert reloaded.total_won == 24000

    await change()


async def test_stale_order_cannot_overwrite_a_newer_version(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    order_id = await seed_order()
    orders = SqlAlchemyOrderRepository()

    @transactional(Propagation.REQUIRES_NEW)
    async def fresh_change() -> None:
        latest = await orders.get(order_id)
        assert latest is not None
        latest.add_line(OrderLine(product_id="pen", quantity=1, unit_price_won=1000))
        await orders.save(latest)

    @transactional
    async def stale_change() -> None:
        old = await orders.get(order_id)
        assert old is not None
        await fresh_change()
        old.confirm()
        await orders.save(old)

    with pytest.raises(StaleDataError):
        await stale_change()
    result = await load_order(order_id)
    assert result.status == Order.Status.DRAFT
    assert result.total_won == 25000
    assert len(result.lines) == 2
    assert result.version == 2
