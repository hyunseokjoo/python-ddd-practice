from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.bootstrap.container import RequestContainerDependency
from app.domains.orders.application.list_orders_by_status import (
    ListOrdersByStatusQuery,
)
from app.domains.orders.domain.order import Order

router = APIRouter()


class OrderSummary(BaseModel):
    order_id: UUID
    status: Order.Status
    total_won: int
    item_count: int
    version: int


@router.get("", response_model=list[OrderSummary])
def list_orders_by_status(
    query: Annotated[ListOrdersByStatusQuery, Query()],
    container: RequestContainerDependency,
) -> list[OrderSummary]:
    return [
        OrderSummary(
            order_id=order.id,
            status=order.status,
            total_won=order.total_won,
            item_count=order.item_count,
            version=order.version,
        )
        for order in container.orders().list_orders_by_status(query)
    ]
