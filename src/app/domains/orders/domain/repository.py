from typing import Protocol
from uuid import UUID

from app.domains.orders.domain.order import Order


class OrderRepository(Protocol):
    def get(self, order_id: UUID) -> Order | None: ...

    def list(
        self, status: Order.Status | None, limit: int, offset: int
    ) -> list[Order]: ...

    def add(self, order: Order) -> None: ...

    def save(self, order: Order) -> None: ...
