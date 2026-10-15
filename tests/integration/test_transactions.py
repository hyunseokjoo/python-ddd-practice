from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.domains.orders.application.add_product_to_order import (
    AddProductToOrderCommand,
    add_product_to_order,
)
from app.domains.orders.application.confirm_order import (
    ConfirmOrderCommand,
    confirm_order,
)
from app.domains.orders.domain.order import Order
from app.domains.orders.domain.order_line import OrderLine
from app.domains.orders.infrastructure.order_repository import SqlAlchemyOrderRepository
from app.domains.orders.infrastructure.persistence.order import OrderRow
from app.domains.orders.infrastructure.persistence.order_line import OrderLineRow
from app.shared.database.uow import ConcurrentModification, SqlAlchemyUnitOfWork


def seed_order(sessions: sessionmaker[Session]) -> UUID:
    order = Order(uuid4())
    order.add_line(OrderLine(product_id="book", quantity=2, unit_price_won=12000))
    with sessions() as session, SqlAlchemyUnitOfWork(session) as uow:
        SqlAlchemyOrderRepository(session).add(order)
        uow.commit()
    return order.id


@pytest.mark.parametrize("failure", ["before_commit", "during_commit"])
def test_order_and_lines_rollback_together(
    sessions: sessionmaker[Session], failure: str
) -> None:
    order_id = seed_order(sessions)
    with sessions() as session:
        expected = RuntimeError if failure == "before_commit" else IntegrityError
        mysql_check_failure = (
            failure == "during_commit" and session.get_bind().dialect.name == "mysql"
        )
        if mysql_check_failure:
            # PyMySQL은 CHECK 제약 위반(3819)을 OperationalError로 전달한다.
            expected = OperationalError
        with pytest.raises(expected) as raised:
            with SqlAlchemyUnitOfWork(session) as uow:
                orders = SqlAlchemyOrderRepository(session)
                order = orders.get(order_id)
                assert order is not None
                order.add_line(
                    OrderLine(product_id="pen", quantity=1, unit_price_won=1000)
                )
                orders.save(order)
                if failure == "before_commit":
                    session.flush()
                    raise RuntimeError("operation failed after flushing both tables")
                # DB 제약 위반을 커밋 중 발생시켜 실제 트랜잭션의 롤백을 검증한다.
                session.add(
                    OrderLineRow(
                        order_id=str(order_id),
                        position=2,
                        product_id="invalid",
                        quantity=0,
                        unit_price_won=1000,
                    )
                )
                uow.commit()
        if mysql_check_failure:
            assert raised.value.orig.args[0] == 3819
        assert not session.in_transaction()

    with sessions() as verification:
        order = verification.get(OrderRow, str(order_id))
        assert order is not None
        assert order.status == "draft"
        assert order.version == 1
        details = SqlAlchemyOrderRepository(verification).get(order_id)
        assert details is not None and details.total_won == 24000
        assert len(details.lines) == 1


def test_confirmation_commits_order(sessions: sessionmaker[Session]) -> None:
    order_id = seed_order(sessions)
    with sessions() as session:
        confirm_order(
            ConfirmOrderCommand(order_id=order_id),
            SqlAlchemyOrderRepository(session),
            SqlAlchemyUnitOfWork(session),
        )
    with sessions() as verification:
        order = verification.get(OrderRow, str(order_id))
        assert order is not None and order.status == "confirmed"
        details = SqlAlchemyOrderRepository(verification).get(order_id)
        assert details is not None and details.total_won == 24000


def test_product_addition_commits_order_and_lines(
    sessions: sessionmaker[Session],
) -> None:
    order_id = seed_order(sessions)
    with sessions() as session:
        add_product_to_order(
            AddProductToOrderCommand(
                order_id=order_id,
                line=OrderLine(product_id="pen", quantity=1, unit_price_won=1000),
            ),
            SqlAlchemyOrderRepository(session),
            SqlAlchemyUnitOfWork(session),
        )
    with sessions() as verification:
        details = SqlAlchemyOrderRepository(verification).get(order_id)
        assert details is not None
        assert details.version == 2
        assert details.total_won == 25000
        assert len(details.lines) == 2


def test_leaving_uow_without_commit_rolls_back(sessions: sessionmaker[Session]) -> None:
    order_id = uuid4()
    with sessions() as session, SqlAlchemyUnitOfWork(session):
        SqlAlchemyOrderRepository(session).add(Order(order_id))
    with sessions() as verification:
        assert verification.get(OrderRow, str(order_id)) is None


def test_list_returns_aggregates_that_can_be_saved(
    sessions: sessionmaker[Session],
) -> None:
    order_id = seed_order(sessions)
    with sessions() as session, SqlAlchemyUnitOfWork(session) as uow:
        orders = SqlAlchemyOrderRepository(session)
        order = orders.list(Order.Status.DRAFT, limit=20, offset=0)[0]
        assert order.id == order_id
        assert order.version == 1
        order.confirm()
        orders.save(order)
        uow.commit()
        reloaded = orders.get(order_id)
        assert reloaded is not None
        assert reloaded.status == Order.Status.CONFIRMED
        assert reloaded.version == 2
        assert reloaded.total_won == 24000


def test_stale_order_cannot_overwrite_a_newer_version(
    sessions: sessionmaker[Session],
) -> None:
    order_id = seed_order(sessions)
    with sessions() as stale, sessions() as fresh:
        stale_repo = SqlAlchemyOrderRepository(stale)
        fresh_repo = SqlAlchemyOrderRepository(fresh)
        with pytest.raises(ConcurrentModification):
            with SqlAlchemyUnitOfWork(stale) as stale_uow:
                old = stale_repo.get(order_id)
                assert old is not None
                with SqlAlchemyUnitOfWork(fresh) as fresh_uow:
                    latest = fresh_repo.get(order_id)
                    assert latest is not None
                    latest.add_line(
                        OrderLine(product_id="pen", quantity=1, unit_price_won=1000)
                    )
                    fresh_repo.save(latest)
                    fresh_uow.commit()
                old.confirm()
                stale_repo.save(old)
                stale_uow.commit()
    with sessions() as verification:
        result = SqlAlchemyOrderRepository(verification).get(order_id)
        assert result is not None
        assert result.status == Order.Status.DRAFT
        assert result.total_won == 25000
        assert len(result.lines) == 2
        assert result.version == 2
