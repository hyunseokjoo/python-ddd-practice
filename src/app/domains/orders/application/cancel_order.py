from uuid import UUID

from loguru import logger
from pydantic import BaseModel, ConfigDict

from app.domains.orders.application.exceptions import OrderNotFound
from app.domains.orders.domain.repository import OrderRepository


class CancelOrderCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    order_id: UUID


@logger.catch(
    reraise=True,
    message=("작업 실패: {record[exception].type.__name__} use_case=cancel_order"),
)
async def cancel_order(
    command: CancelOrderCommand,
    orders: OrderRepository,
) -> None:
    order = await orders.get(command.order_id)
    if order is None:
        raise OrderNotFound(str(command.order_id))
    order.cancel()
    await orders.save(order)
    logger.info("주문 취소 처리 order_id={}", command.order_id)
