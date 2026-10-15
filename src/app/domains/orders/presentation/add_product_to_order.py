from uuid import UUID

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, Field

from app.bootstrap.container import RequestContainerDependency
from app.domains.orders.application.add_product_to_order import (
    AddProductToOrderCommand,
)
from app.domains.orders.domain.order_line import OrderLine

router = APIRouter()


class AddProductRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(min_length=1, max_length=100, pattern=r"\S")
    quantity: int = Field(gt=0, le=10000, strict=True)
    unit_price_won: int = Field(ge=0, le=1_000_000_000, strict=True)


@router.post("/{order_id}/lines", status_code=204)
def add_product_to_order(
    order_id: UUID,
    body: AddProductRequest,
    container: RequestContainerDependency,
) -> Response:
    container.orders().add_product_to_order(
        AddProductToOrderCommand(
            order_id=order_id,
            line=OrderLine.model_validate(body.model_dump()),
        ),
    )
    return Response(status_code=204)
