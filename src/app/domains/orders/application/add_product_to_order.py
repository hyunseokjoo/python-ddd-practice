from uuid import UUID

from loguru import logger
from pydantic import BaseModel, ConfigDict
from sqlalchemy_transactional.asyncio import transactional

from app.domains.orders.application.exceptions import OrderNotFound
from app.domains.orders.domain.order_line import OrderLine
from app.domains.orders.domain.repository import OrderRepository


class AddProductToOrderCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    order_id: UUID
    line: OrderLine


@logger.catch(
    reraise=True,
    message=(
        "작업 실패: {record[exception].type.__name__} use_case=add_product_to_order"
    ),
)
@transactional
async def add_product_to_order(
    command: AddProductToOrderCommand,
    orders: OrderRepository,
) -> None:
    order = await orders.get(command.order_id)
    if order is None:
        raise OrderNotFound(str(command.order_id))
    order.add_line(command.line)
    await orders.save(order)
    logger.info("상품 추가 처리 order_id={}", command.order_id)
