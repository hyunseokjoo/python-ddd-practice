from uuid import UUID

from fastapi import APIRouter, Response

from app.bootstrap.container import RequestContainerDependency
from app.domains.orders.application.confirm_order import (
    ConfirmOrderCommand,
)

router = APIRouter()


@router.post("/{order_id}/confirm", status_code=204)
def confirm_order(
    order_id: UUID,
    container: RequestContainerDependency,
) -> Response:
    container.orders().confirm_order(
        ConfirmOrderCommand(order_id=order_id),
    )
    return Response(status_code=204)
