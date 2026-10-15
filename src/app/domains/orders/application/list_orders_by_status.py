from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from app.domains.orders.domain.order import Order
from app.domains.orders.domain.repository import OrderRepository


class ListOrdersByStatusQuery(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Order.Status | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


def list_orders_by_status(
    query: ListOrdersByStatusQuery,
    orders: OrderRepository,
) -> list[Order]:
    with logger.catch(
        reraise=True, message="작업 실패: {record[exception].type.__name__}"
    ):
        orders_found = orders.list(query.status, query.limit, query.offset)
    logger.info("주문 목록 조회 완료 count={}", len(orders_found))
    return orders_found
