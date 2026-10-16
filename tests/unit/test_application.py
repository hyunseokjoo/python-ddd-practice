from collections.abc import Callable
from unittest.mock import Mock
from uuid import UUID

import pytest

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
from app.domains.orders.application.exceptions import OrderNotFound
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

pytestmark = pytest.mark.usefixtures("transaction_context")

ORDER_ID = UUID(int=1)


@pytest.fixture
def orders() -> Mock:
    return Mock(spec_set=OrderRepository)


@pytest.fixture
def order() -> Order:
    return Order(
        ORDER_ID,
        (OrderLine(product_id="book", quantity=2, unit_price_won=12000),),
    )


async def test_create_order_stores_a_draft(orders: Mock) -> None:
    order_id = await create_order(CreateOrderCommand(order_id=ORDER_ID), orders)

    assert order_id == ORDER_ID
    orders.add.assert_awaited_once()
    saved = orders.add.call_args.args[0]
    assert saved.id == ORDER_ID
    assert saved.status == Order.Status.DRAFT
    assert saved.lines == ()


async def test_add_product_saves_the_changed_order(orders: Mock, order: Order) -> None:
    orders.get.return_value = order
    line = OrderLine(product_id="pen", quantity=3, unit_price_won=1000)

    await add_product_to_order(
        AddProductToOrderCommand(order_id=ORDER_ID, line=line), orders
    )

    orders.get.assert_awaited_once_with(ORDER_ID)
    assert order.lines[-1] == line
    assert order.total_won == 27000
    orders.save.assert_awaited_once_with(order)


async def test_confirm_order_saves_the_confirmed_order(
    orders: Mock, order: Order
) -> None:
    orders.get.return_value = order

    await confirm_order(ConfirmOrderCommand(order_id=ORDER_ID), orders)

    orders.get.assert_awaited_once_with(ORDER_ID)
    assert order.status == Order.Status.CONFIRMED
    orders.save.assert_awaited_once_with(order)


async def test_cancel_order_saves_the_cancelled_order(
    orders: Mock, order: Order
) -> None:
    order.confirm()
    orders.get.return_value = order

    await cancel_order(CancelOrderCommand(order_id=ORDER_ID), orders)

    orders.get.assert_awaited_once_with(ORDER_ID)
    assert order.status == Order.Status.CANCELLED
    orders.save.assert_awaited_once_with(order)


@pytest.mark.parametrize(
    ("use_case", "command"),
    [
        (
            add_product_to_order,
            AddProductToOrderCommand(
                order_id=ORDER_ID,
                line=OrderLine(product_id="book", quantity=1, unit_price_won=1000),
            ),
        ),
        (confirm_order, ConfirmOrderCommand(order_id=ORDER_ID)),
        (cancel_order, CancelOrderCommand(order_id=ORDER_ID)),
    ],
    ids=["add_product", "confirm", "cancel"],
)
async def test_missing_order_is_not_saved(
    use_case: Callable[..., None],
    command: AddProductToOrderCommand | ConfirmOrderCommand | CancelOrderCommand,
    orders: Mock,
) -> None:
    orders.get.return_value = None

    with pytest.raises(OrderNotFound, match=str(ORDER_ID)):
        await use_case(command, orders)

    orders.get.assert_awaited_once_with(ORDER_ID)
    orders.save.assert_not_awaited()


async def test_rule_violation_is_not_saved(orders: Mock) -> None:
    orders.get.return_value = Order(ORDER_ID)

    with pytest.raises(OrderRuleViolation):
        await confirm_order(ConfirmOrderCommand(order_id=ORDER_ID), orders)

    orders.save.assert_not_awaited()


async def test_save_failure_is_propagated(orders: Mock, order: Order) -> None:
    orders.get.return_value = order
    error = RuntimeError("save failed")
    orders.save.side_effect = error

    with pytest.raises(RuntimeError) as caught:
        await confirm_order(ConfirmOrderCommand(order_id=ORDER_ID), orders)

    assert caught.value is error


async def test_get_order_returns_the_aggregate(orders: Mock, order: Order) -> None:
    orders.get.return_value = order

    result = await get_order_by_id(GetOrderByIdQuery(order_id=ORDER_ID), orders)

    assert result is order
    orders.get.assert_awaited_once_with(ORDER_ID)
    orders.add.assert_not_awaited()
    orders.save.assert_not_awaited()


async def test_get_missing_order_raises_not_found(orders: Mock) -> None:
    orders.get.return_value = None

    with pytest.raises(OrderNotFound, match=str(ORDER_ID)):
        await get_order_by_id(GetOrderByIdQuery(order_id=ORDER_ID), orders)


@pytest.mark.parametrize("status", [None, Order.Status.CONFIRMED])
async def test_list_orders_passes_filter_and_pagination_to_repository(
    orders: Mock, order: Order, status: Order.Status | None
) -> None:
    orders.list.return_value = [order]

    result = await list_orders_by_status(
        ListOrdersByStatusQuery(status=status, limit=5, offset=10), orders
    )

    assert result == [order]
    orders.list.assert_awaited_once_with(status, 5, 10)
    orders.add.assert_not_awaited()
    orders.save.assert_not_awaited()
