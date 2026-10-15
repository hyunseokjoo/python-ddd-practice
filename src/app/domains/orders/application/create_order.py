from uuid import UUID, uuid4

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from app.domains.orders.domain.order import Order
from app.domains.orders.domain.repository import OrderRepository
from app.shared.database.uow import UnitOfWork


class CreateOrderCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    order_id: UUID = Field(default_factory=uuid4)


def create_order(
    command: CreateOrderCommand,
    orders: OrderRepository,
    uow: UnitOfWork,
) -> UUID:
    with (
        logger.catch(
            reraise=True, message="작업 실패: {record[exception].type.__name__}"
        ),
        uow,
    ):
        orders.add(Order(command.order_id))
        uow.commit()
    logger.info("주문 생성 완료 order_id={}", command.order_id)
    return command.order_id
