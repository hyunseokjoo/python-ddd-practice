import asyncio
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy_transactional.asyncio import current_session, transactional
from sqlalchemy_transactional.common import (
    Propagation,
    SessionNotBoundError,
    TransactionRequiredError,
)

from app.bootstrap.container import RequestContainer
from app.domains.orders.application.create_order import CreateOrderCommand
from app.domains.orders.domain.order import Order
from app.domains.orders.infrastructure.order_repository import SqlAlchemyOrderRepository
from app.domains.orders.infrastructure.persistence.order import OrderRow


async def test_required_use_cases_share_transaction_and_defer_commit(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    first_id, second_id = uuid4(), uuid4()
    container = RequestContainer()

    @transactional
    async def outer() -> None:
        session = current_session()
        await container.orders().create_order(CreateOrderCommand(order_id=first_id))
        await container.orders().create_order(CreateOrderCommand(order_id=second_id))
        assert current_session() is session
        assert await session.get(OrderRow, str(first_id)) is not None
        async with sessions() as verification:
            assert await verification.get(OrderRow, str(first_id)) is None
            assert await verification.get(OrderRow, str(second_id)) is None

    await outer()
    async with sessions() as verification:
        assert await verification.get(OrderRow, str(first_id)) is not None
        assert await verification.get(OrderRow, str(second_id)) is not None
    with pytest.raises(SessionNotBoundError):
        current_session()


@pytest.mark.parametrize("caught", [False, True])
async def test_required_inner_failure_uses_library_semantics(
    sessions: async_sessionmaker[AsyncSession],
    caught: bool,
) -> None:
    outer_id, inner_id = uuid4(), uuid4()
    orders = SqlAlchemyOrderRepository()

    @transactional
    async def inner() -> None:
        await orders.add(Order(inner_id))
        raise ValueError("inner failed")

    @transactional
    async def outer() -> None:
        await orders.add(Order(outer_id))
        if caught:
            with pytest.raises(ValueError, match="inner failed"):
                await inner()
        else:
            await inner()

    if caught:
        await outer()
    else:
        with pytest.raises(ValueError, match="inner failed"):
            await outer()
    async with sessions() as verification:
        assert (await verification.get(OrderRow, str(outer_id)) is not None) is caught
        assert (await verification.get(OrderRow, str(inner_id)) is not None) is caught
    with pytest.raises(SessionNotBoundError):
        current_session()


async def test_requires_new_commits_independently_and_restores_parent(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    outer_id, inner_id = uuid4(), uuid4()
    orders = SqlAlchemyOrderRepository()
    observed: list[AsyncSession] = []

    @transactional(Propagation.REQUIRES_NEW)
    async def inner() -> None:
        observed.append(current_session())
        await orders.add(Order(inner_id))

    @transactional
    async def outer() -> None:
        parent = current_session()
        observed.append(parent)
        await orders.add(Order(outer_id))
        await inner()
        assert current_session() is parent
        raise ValueError("outer failed")

    with pytest.raises(ValueError, match="outer failed"):
        await outer()
    assert observed[0] is not observed[1]
    async with sessions() as verification:
        assert await verification.get(OrderRow, str(outer_id)) is None
        assert await verification.get(OrderRow, str(inner_id)) is not None


async def test_nested_failure_rolls_back_only_savepoint(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    outer_id, inner_id = uuid4(), uuid4()
    orders = SqlAlchemyOrderRepository()

    @transactional(Propagation.NESTED)
    async def inner(parent: AsyncSession) -> None:
        assert current_session() is parent
        await orders.add(Order(inner_id))
        raise ValueError("savepoint failed")

    @transactional
    async def outer() -> None:
        await orders.add(Order(outer_id))
        with pytest.raises(ValueError, match="savepoint failed"):
            await inner(current_session())

    await outer()
    async with sessions() as verification:
        assert await verification.get(OrderRow, str(outer_id)) is not None
        assert await verification.get(OrderRow, str(inner_id)) is None


async def test_mandatory_requires_an_existing_transaction(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    @transactional(Propagation.MANDATORY)
    async def inner() -> AsyncSession:
        return current_session()

    with pytest.raises(TransactionRequiredError):
        await inner()

    @transactional
    async def outer() -> None:
        assert await inner() is current_session()

    await outer()


async def test_independent_tasks_get_separate_sessions(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    barrier = asyncio.Barrier(2)
    observed: list[AsyncSession] = []

    @transactional
    async def operation() -> None:
        session = current_session()
        observed.append(session)
        await barrier.wait()
        assert current_session() is session
        await SqlAlchemyOrderRepository().add(Order(uuid4()))

    await asyncio.gather(operation(), operation())
    assert observed[0] is not observed[1]
    with pytest.raises(SessionNotBoundError):
        current_session()


async def test_cancellation_rolls_back_and_clears_context(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    order_id = uuid4()
    started = asyncio.Event()

    @transactional
    async def operation() -> None:
        await SqlAlchemyOrderRepository().add(Order(order_id))
        started.set()
        await asyncio.Event().wait()

    async def run() -> None:
        try:
            await operation()
        finally:
            with pytest.raises(SessionNotBoundError):
                current_session()

    task = asyncio.create_task(run())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    async with sessions() as verification:
        assert await verification.get(OrderRow, str(order_id)) is None
