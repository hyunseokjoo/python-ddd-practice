from uuid import UUID

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.bootstrap.container import RequestContainerDependency
from app.domains.orders.application.create_order import (
    CreateOrderCommand,
)

router = APIRouter()


class CreateOrderResponse(BaseModel):
    order_id: UUID


@router.post("", status_code=201, response_model=CreateOrderResponse)
def create_order(
    response: Response,
    container: RequestContainerDependency,
) -> CreateOrderResponse:
    order_id = container.orders().create_order(
        CreateOrderCommand(),
    )
    response.headers["Location"] = f"/orders/{order_id}"
    return CreateOrderResponse(order_id=order_id)
