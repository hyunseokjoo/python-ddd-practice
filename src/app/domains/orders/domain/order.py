from enum import StrEnum
from uuid import UUID

from app.domains.orders.domain.exceptions import OrderRuleViolation
from app.domains.orders.domain.order_line import OrderLine


class Order:
    class Status(StrEnum):
        DRAFT = "draft"
        CONFIRMED = "confirmed"
        CANCELLED = "cancelled"

    def __init__(
        self,
        order_id: UUID,
        lines: tuple[OrderLine, ...] = (),
        status: Order.Status = Status.DRAFT,
        *,
        version: int = 1,
    ) -> None:
        if status != Order.Status.DRAFT and not lines:
            raise OrderRuleViolation("상품이 없는 주문은 확정·취소 상태일 수 없습니다.")
        if len({line.product_id for line in lines}) != len(lines):
            raise OrderRuleViolation("이미 추가한 상품입니다.")
        self._id = order_id
        self._lines = tuple(OrderLine.model_validate(line) for line in lines)
        self._status = status
        self._version = version

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def lines(self) -> tuple[OrderLine, ...]:
        return self._lines

    @property
    def status(self) -> Order.Status:
        return self._status

    @property
    def version(self) -> int:
        # 조회 시점의 저장 버전이다. 저장 후 최신 버전은 다시 조회한다.
        return self._version

    @property
    def total_won(self) -> int:
        return sum(line.subtotal for line in self._lines)

    @property
    def item_count(self) -> int:
        return len(self._lines)

    def add_line(self, line: OrderLine) -> None:
        self._require_status(Order.Status.DRAFT)
        if any(existing.product_id == line.product_id for existing in self._lines):
            raise OrderRuleViolation("이미 추가한 상품입니다.")
        self._lines += (OrderLine.model_validate(line),)

    def confirm(self) -> None:
        self._require_status(Order.Status.DRAFT)
        if not self._lines:
            raise OrderRuleViolation("상품이 없는 주문은 확정할 수 없습니다.")
        self._status = Order.Status.CONFIRMED

    def cancel(self) -> None:
        self._require_status(Order.Status.CONFIRMED)
        self._status = Order.Status.CANCELLED

    def _require_status(self, expected: Order.Status) -> None:
        if self._status != expected:
            raise OrderRuleViolation(
                f"{expected.value} 상태에서만 가능한 작업입니다: {self._status.value}"
            )
