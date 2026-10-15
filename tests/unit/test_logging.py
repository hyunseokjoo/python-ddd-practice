import re
import sys
from collections.abc import Callable, Iterator
from io import StringIO
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from loguru import logger
from pydantic import BaseModel

from app.bootstrap.logging import configure_logging
from app.domains.orders.application.add_product_to_order import (
    AddProductToOrderCommand,
    add_product_to_order,
)
from app.domains.orders.application.cancel_order import CancelOrderCommand, cancel_order
from app.domains.orders.application.confirm_order import (
    ConfirmOrderCommand,
    confirm_order,
)
from app.domains.orders.application.create_order import CreateOrderCommand, create_order
from app.domains.orders.application.get_order_by_id import (
    GetOrderByIdQuery,
    get_order_by_id,
)
from app.domains.orders.application.list_orders_by_status import (
    ListOrdersByStatusQuery,
    list_orders_by_status,
)
from app.domains.orders.domain.exceptions import OrderRuleViolation
from app.domains.orders.domain.order import Order
from app.domains.orders.domain.order_line import OrderLine
from app.domains.orders.domain.repository import OrderRepository
from app.shared.database.uow import UnitOfWork

ORDER_ID = UUID(int=1)


@pytest.fixture
def logging_output(monkeypatch: pytest.MonkeyPatch) -> Iterator[StringIO]:
    output = StringIO()
    monkeypatch.setattr(sys, "stderr", output)
    configure_logging()
    yield output
    logger.remove()


@pytest.mark.parametrize(
    ("use_case", "command", "success_message"),
    [
        (create_order, CreateOrderCommand(order_id=ORDER_ID), "주문 생성 완료"),
        (
            add_product_to_order,
            AddProductToOrderCommand(
                order_id=ORDER_ID,
                line=OrderLine(product_id="pen", quantity=1, unit_price_won=1000),
            ),
            "상품 추가 완료",
        ),
        (confirm_order, ConfirmOrderCommand(order_id=ORDER_ID), "주문 확정 완료"),
        (cancel_order, CancelOrderCommand(order_id=ORDER_ID), "주문 취소 완료"),
        (get_order_by_id, GetOrderByIdQuery(order_id=ORDER_ID), "주문 상세 조회 완료"),
        (list_orders_by_status, ListOrdersByStatusQuery(), "주문 목록 조회 완료"),
    ],
)
@pytest.mark.parametrize("fails", [False, True])
def test_use_case_logs_outcome_and_preserves_errors(
    use_case: Callable[..., object],
    command: BaseModel,
    success_message: str,
    fails: bool,
    logging_output: StringIO,
) -> None:
    order = Order(
        ORDER_ID,
        (OrderLine(product_id="book", quantity=1, unit_price_won=12000),),
    )
    if use_case is cancel_order:
        order.confirm()
    orders = MagicMock(spec=OrderRepository)
    orders.get.return_value = order
    orders.list.return_value = [order]
    uow = MagicMock(spec=UnitOfWork)
    changes_order = use_case not in (get_order_by_id, list_orders_by_status)
    error = RuntimeError("sensitive SQL parameter")

    def commit() -> None:
        assert logging_output.getvalue() == ""
        if fails:
            raise error

    uow.commit.side_effect = commit
    if fails and not changes_order:
        orders.get.side_effect = error
        orders.list.side_effect = error
    arguments = (command, orders, uow) if changes_order else (command, orders)

    if fails:
        with pytest.raises(RuntimeError) as caught:
            use_case(*arguments)
        assert caught.value is error
    else:
        use_case(*arguments)
        if changes_order:
            uow.commit.assert_called_once()

    output = logging_output.getvalue()
    assert len(output.splitlines()) == 1
    assert re.match(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} [+-]\d{2}:\d{2}", output
    )
    assert f"{use_case.__module__}:{use_case.__name__}:" in output
    if fails:
        assert "ERROR" in output
        assert "작업 실패: RuntimeError" in output
        assert success_message not in output
        assert "sensitive SQL parameter" not in output
    else:
        assert "INFO" in output
        assert success_message in output


def test_rule_violation_logs_failure_without_committing(
    logging_output: StringIO,
) -> None:
    orders = MagicMock(spec=OrderRepository)
    orders.get.return_value = Order(ORDER_ID)
    uow = MagicMock(spec=UnitOfWork)

    with pytest.raises(OrderRuleViolation):
        confirm_order(ConfirmOrderCommand(order_id=ORDER_ID), orders, uow)

    output = logging_output.getvalue()
    assert "confirm_order:" in output
    assert "작업 실패: OrderRuleViolation" in output
    assert "완료" not in output
    uow.commit.assert_not_called()


def test_reconfiguring_logging_does_not_duplicate_output(
    logging_output: StringIO,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "stderr", logging_output)
    configure_logging()
    configure_logging()
    logger.info("한 번만 출력")
    assert logging_output.getvalue().count("한 번만 출력") == 1
