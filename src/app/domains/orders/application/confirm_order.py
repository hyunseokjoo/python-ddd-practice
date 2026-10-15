from uuid import UUID

from loguru import logger
from pydantic import BaseModel, ConfigDict

from app.domains.orders.application.exceptions import OrderNotFound
from app.domains.orders.domain.repository import OrderRepository
from app.shared.database.uow import UnitOfWork


class ConfirmOrderCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    order_id: UUID


def confirm_order(
    command: ConfirmOrderCommand,
    orders: OrderRepository,
    uow: UnitOfWork,
) -> None:
    with (
        logger.catch(
            reraise=True, message="작업 실패: {record[exception].type.__name__}"
        ),
        uow,
    ):
        order = orders.get(command.order_id)
        if order is None:
            raise OrderNotFound(str(command.order_id))
        order.confirm()
        orders.save(order)
        uow.commit()
    logger.info("주문 확정 완료 order_id={}", command.order_id)
