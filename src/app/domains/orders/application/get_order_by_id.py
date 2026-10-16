from uuid import UUID

from loguru import logger
from pydantic import BaseModel, ConfigDict
from sqlalchemy_transactional.asyncio import transactional

from app.domains.orders.application.exceptions import OrderNotFound
from app.domains.orders.domain.order import Order
from app.domains.orders.domain.repository import OrderRepository


class GetOrderByIdQuery(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    order_id: UUID


@logger.catch(
    reraise=True,
    message=("작업 실패: {record[exception].type.__name__} use_case=get_order_by_id"),
)
@transactional
async def get_order_by_id(
    query: GetOrderByIdQuery,
    orders: OrderRepository,
) -> Order:
    order = await orders.get(query.order_id)
    if order is None:
        raise OrderNotFound(str(query.order_id))
    logger.info("주문 상세 조회 처리 order_id={}", query.order_id)
    return order
