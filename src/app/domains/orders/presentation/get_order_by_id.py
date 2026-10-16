from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from app.bootstrap.container import RequestContainerDependency
from app.domains.orders.application.get_order_by_id import (
    GetOrderByIdQuery,
)
from app.domains.orders.domain.order import Order
from app.domains.orders.domain.order_line import OrderLine

router = APIRouter()


class OrderDetails(BaseModel):
    order_id: UUID
    status: Order.Status
    total_won: int
    item_count: int
    version: int
    lines: tuple[OrderLine, ...]


@router.get("/{order_id}", response_model=OrderDetails)
async def get_order_by_id(
    order_id: UUID,
    container: RequestContainerDependency,
) -> OrderDetails:
    order = await container.orders().get_order_by_id(
        GetOrderByIdQuery(order_id=order_id)
    )
    return OrderDetails(
        order_id=order.id,
        status=order.status,
        total_won=order.total_won,
        item_count=order.item_count,
        version=order.version,
        lines=order.lines,
    )
