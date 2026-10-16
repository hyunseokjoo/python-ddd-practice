from uuid import UUID, uuid4

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from app.domains.orders.domain.order import Order
from app.domains.orders.domain.repository import OrderRepository


class CreateOrderCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    order_id: UUID = Field(default_factory=uuid4)


@logger.catch(
    reraise=True,
    message=("작업 실패: {record[exception].type.__name__} use_case=create_order"),
)
async def create_order(
    command: CreateOrderCommand,
    orders: OrderRepository,
) -> UUID:
    await orders.add(Order(command.order_id))
    logger.info("주문 생성 처리 order_id={}", command.order_id)
    return command.order_id
