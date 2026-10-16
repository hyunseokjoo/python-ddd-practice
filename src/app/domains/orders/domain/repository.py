from typing import Protocol
from uuid import UUID

from app.domains.orders.domain.order import Order


class OrderRepository(Protocol):
    async def get(self, order_id: UUID) -> Order | None: ...

    async def list(
        self, status: Order.Status | None, limit: int, offset: int
    ) -> list[Order]: ...

    async def add(self, order: Order) -> None: ...

    async def save(self, order: Order) -> None: ...
