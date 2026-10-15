from uuid import UUID

from fastapi import APIRouter, Response

from app.bootstrap.container import RequestContainerDependency
from app.domains.orders.application.cancel_order import (
    CancelOrderCommand,
)

router = APIRouter()


@router.post("/{order_id}/cancel", status_code=204)
def cancel_order(
    order_id: UUID,
    container: RequestContainerDependency,
) -> Response:
    container.orders().cancel_order(
        CancelOrderCommand(order_id=order_id),
    )
    return Response(status_code=204)
