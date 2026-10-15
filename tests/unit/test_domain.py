from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domains.orders.domain.exceptions import OrderRuleViolation
from app.domains.orders.domain.order import Order
from app.domains.orders.domain.order_line import OrderLine


def line(**changes: object) -> OrderLine:
    return OrderLine.model_validate(
        {"product_id": "book", "quantity": 2, "unit_price_won": 12000, **changes}
    )


@pytest.mark.parametrize("quantity", [0, -1, True, "2"])
def test_quantity_must_be_a_positive_integer(quantity: object) -> None:
    with pytest.raises(ValidationError):
        line(quantity=quantity)


def test_line_is_immutable() -> None:
    item = line()
    with pytest.raises(ValidationError):
        item.quantity = 3


def test_empty_order_cannot_be_confirmed() -> None:
    order = Order(uuid4())
    with pytest.raises(OrderRuleViolation, match="상품"):
        order.confirm()
    assert order.status == Order.Status.DRAFT


def test_order_calculates_total_and_product_count() -> None:
    order = Order(uuid4())
    assert order.total_won == 0
    assert order.item_count == 0
    order.add_line(line())
    order.add_line(line(product_id="pen", quantity=3, unit_price_won=1000))
    assert order.total_won == 27000
    assert order.item_count == 2


def test_confirmation_freezes_order() -> None:
    order = Order(uuid4())
    order.add_line(line())
    order.confirm()
    assert order.total_won == 24000
    assert order.status == Order.Status.CONFIRMED
    with pytest.raises(OrderRuleViolation):
        order.add_line(line(product_id="pen"))
    with pytest.raises(OrderRuleViolation):
        order.confirm()


def test_duplicate_product_is_rejected() -> None:
    order = Order(uuid4())
    order.add_line(line())
    with pytest.raises(OrderRuleViolation, match="이미"):
        order.add_line(line())
    assert len(order.lines) == 1


def test_only_confirmed_order_can_be_cancelled() -> None:
    order = Order(uuid4())
    with pytest.raises(OrderRuleViolation):
        order.cancel()
    order.add_line(line())
    order.confirm()
    order.cancel()
    assert order.status == Order.Status.CANCELLED
    with pytest.raises(OrderRuleViolation):
        order.confirm()
    with pytest.raises(OrderRuleViolation):
        order.cancel()


def test_rehydration_preserves_invariants() -> None:
    with pytest.raises(OrderRuleViolation):
        Order(uuid4(), status=Order.Status.CONFIRMED)
