import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bootstrap.container import RequestContainer
from app.domains.orders.application.create_order import CreateOrderCommand
from app.domains.orders.domain.order import Order
from app.domains.orders.infrastructure.order_repository import SqlAlchemyOrderRepository
from app.domains.orders.infrastructure.persistence.order import OrderRow


async def test_use_cases_share_session_and_commit_only_at_outer_boundary(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    first_id, second_id = uuid4(), uuid4()
    async with sessions.begin() as session:
        container = RequestContainer(session=session)
        await container.orders().create_order(CreateOrderCommand(order_id=first_id))
        await container.orders().create_order(CreateOrderCommand(order_id=second_id))
        assert session.in_transaction()
        assert await session.get(OrderRow, str(first_id)) is not None
        async with sessions() as verification:
            assert await verification.get(OrderRow, str(first_id)) is None
            assert await verification.get(OrderRow, str(second_id)) is None
    async with sessions() as verification:
        assert await verification.get(OrderRow, str(first_id)) is not None
        assert await verification.get(OrderRow, str(second_id)) is not None


@pytest.mark.parametrize("caught", [False, True])
async def test_only_exceptions_leaving_outer_boundary_cause_rollback(
    sessions: async_sessionmaker[AsyncSession],
    caught: bool,
) -> None:
    first_id, second_id = uuid4(), uuid4()

    async def inner(orders: SqlAlchemyOrderRepository) -> None:
        await orders.add(Order(second_id))
        raise ValueError("inner failed")

    async def outer() -> None:
        async with sessions.begin() as session:
            orders = SqlAlchemyOrderRepository(session)
            await orders.add(Order(first_id))
            if caught:
                with pytest.raises(ValueError, match="inner failed"):
                    await inner(orders)
            else:
                await inner(orders)

    if caught:
        await outer()
    else:
        with pytest.raises(ValueError, match="inner failed"):
            await outer()
    async with sessions() as verification:
        assert (await verification.get(OrderRow, str(first_id)) is not None) is caught
        assert (await verification.get(OrderRow, str(second_id)) is not None) is caught


async def test_separate_session_commits_independently(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    outer_id, inner_id = uuid4(), uuid4()
    with pytest.raises(ValueError, match="outer failed"):
        async with sessions.begin() as outer:
            await SqlAlchemyOrderRepository(outer).add(Order(outer_id))
            async with sessions.begin() as inner:
                assert inner is not outer
                await SqlAlchemyOrderRepository(inner).add(Order(inner_id))
            raise ValueError("outer failed")
    async with sessions() as verification:
        assert await verification.get(OrderRow, str(outer_id)) is None
        assert await verification.get(OrderRow, str(inner_id)) is not None


async def test_explicit_savepoint_rolls_back_only_inner_changes(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    outer_id, inner_id = uuid4(), uuid4()
    async with sessions.begin() as session:
        orders = SqlAlchemyOrderRepository(session)
        await orders.add(Order(outer_id))
        with pytest.raises(ValueError, match="savepoint failed"):
            async with session.begin_nested():
                await orders.add(Order(inner_id))
                raise ValueError("savepoint failed")
    async with sessions() as verification:
        assert await verification.get(OrderRow, str(outer_id)) is not None
        assert await verification.get(OrderRow, str(inner_id)) is None


async def test_independent_tasks_use_separate_sessions(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    first_id, second_id = uuid4(), uuid4()
    barrier = asyncio.Barrier(2)
    observed: list[AsyncSession] = []

    async def operation(order_id: UUID) -> None:
        async with sessions.begin() as session:
            observed.append(session)
            await barrier.wait()
            await SqlAlchemyOrderRepository(session).add(Order(order_id))

    await asyncio.gather(operation(first_id), operation(second_id))
    assert observed[0] is not observed[1]
    async with sessions() as verification:
        assert await verification.get(OrderRow, str(first_id)) is not None
        assert await verification.get(OrderRow, str(second_id)) is not None


async def test_cancellation_rolls_back(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    order_id = uuid4()
    started = asyncio.Event()

    async def operation() -> None:
        async with sessions.begin() as session:
            await SqlAlchemyOrderRepository(session).add(Order(order_id))
            started.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(operation())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    async with sessions() as verification:
        assert await verification.get(OrderRow, str(order_id)) is None
