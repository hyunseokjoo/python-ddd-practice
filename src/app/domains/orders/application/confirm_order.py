from uuid import UUID

from loguru import logger
from pydantic import BaseModel, ConfigDict

from app.domains.orders.application.exceptions import OrderNotFound
from app.domains.orders.domain.repository import OrderRepository


class ConfirmOrderCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    order_id: UUID


@logger.catch(
    reraise=True,
    message=("작업 실패: {record[exception].type.__name__} use_case=confirm_order"),
)
async def confirm_order(
    command: ConfirmOrderCommand,
    orders: OrderRepository,
) -> None:
    order = await orders.get(command.order_id)
    if order is None:
        raise OrderNotFound(str(command.order_id))
    order.confirm()
    await orders.save(order)
    logger.info("주문 확정 처리 order_id={}", command.order_id)
