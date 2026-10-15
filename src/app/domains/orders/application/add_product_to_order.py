from uuid import UUID

from loguru import logger
from pydantic import BaseModel, ConfigDict

from app.domains.orders.application.exceptions import OrderNotFound
from app.domains.orders.domain.order_line import OrderLine
from app.domains.orders.domain.repository import OrderRepository
from app.shared.database.uow import UnitOfWork


class AddProductToOrderCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    order_id: UUID
    line: OrderLine


def add_product_to_order(
    command: AddProductToOrderCommand,
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
        order.add_line(command.line)
        orders.save(order)
        uow.commit()
    logger.info("상품 추가 완료 order_id={}", command.order_id)
